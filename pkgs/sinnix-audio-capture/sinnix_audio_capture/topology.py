"""Parse `pw-mon -a -p` into a lightweight PipeWire object-graph JSONL
stream (node/port/link add/remove events), for post-hoc attribution --
correlating which app was the audio source at a given timestamp against the
MPRIS capture lane (modules/services/capture-mpris.nix) by timestamp.

`-a` (--hide-params) drops the bulky SPA pod parameter dumps that make raw
`pw-mon` output unusably heavy; `-p` (--print-separator) prints a blank
line after every event, which is what makes this streamable line-by-line
instead of needing to buffer the whole graph. Verified live on sinnix-prime
2026-08-12 against `pw-mon -a -p`: an `added:`/`removed:` block looks like

    added:
        id: 49
        permissions: rwxm-
        type: PipeWire:Interface:Node (version 3)
        properties:
            factory.name = "api.alsa.seq.bridge"
            node.name = "Midi-Bridge"
            media.class = "Midi/Bridge"
            object.id = "49"

    added:
        id: 93
        permissions: r-x--
        type: PipeWire:Interface:Link (version 3)
        output-node-id: 60
        output-port-id: 55
        input-node-id: 83
        input-port-id: 81
        ...

Everything that isn't a Node/Port/Link (Core, Module, Factory, Client,
Metadata, SecurityContext, Profiler...) is skipped entirely -- that's most
of the graph's churn (module/factory registration at every client connect)
and none of it is useful for "who was making sound when".

`removed:` blocks only ever carry an id (the object is already gone by the
time pw-mon reports it), so this module keeps a small id->kind cache built
from `added:` events observed during this process's own lifetime to
classify removals. A removal for an id that predates this process starting
(so the cache has no entry for it) is dropped entirely rather than guessed
or reported with an unknown kind -- there is no type field on a `removed:`
block, so nothing distinguishes "a Node/Port/Link we never saw added" from
the ordinary Client/Module/Factory teardown churn this module otherwise
skips, and reporting every unclassifiable removal would reintroduce exactly
the noise the Node/Port/Link filter above exists to avoid.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

_TOP_LEVEL_RE = re.compile(r"^\t([A-Za-z][\w.-]*):\s*(.*)$")
_TYPE_RE = re.compile(r"^([\w:]+)\s*\(version \d+\)$")
_PROPERTY_RE = re.compile(r"^\s*([\w.-]+)\s*=\s*(.*)$")

_KIND_BY_TYPE = {
    "PipeWire:Interface:Node": "node",
    "PipeWire:Interface:Port": "port",
    "PipeWire:Interface:Link": "link",
}


@dataclass
class TopologyEvent:
    action: str  # "added" | "removed"
    id: int
    kind: str | None  # "node" | "port" | "link" | None (unknown, see module doc)
    summary: dict = field(default_factory=dict)


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def _summarize(kind: str, fields: dict, properties: dict) -> dict:
    if kind == "node":
        return {
            k: properties[k]
            for k in ("node.name", "node.description", "media.class")
            if k in properties
        }
    if kind == "port":
        out = {
            k: properties[k] for k in ("port.name", "port.direction") if k in properties
        }
        if "node.id" in properties:
            out["node.id"] = properties["node.id"]
        return out
    if kind == "link":
        return {
            k: fields[k]
            for k in (
                "output-node-id",
                "output-port-id",
                "input-node-id",
                "input-port-id",
            )
            if k in fields
        }
    return {}


def parse_pw_mon_stream(
    lines: Iterable[str], *, id_kind_cache: dict[int, str] | None = None
) -> Iterator[TopologyEvent]:
    """Parse pw-mon -a -p output lines into TopologyEvents for Node/Port/Link
    objects only. `id_kind_cache` (id -> kind), if given, is mutated in
    place: added Node/Port/Link ids are recorded into it and consulted to
    classify later `removed:` blocks for the same id."""
    cache = {} if id_kind_cache is None else id_kind_cache

    action: str | None = None
    obj_id: int | None = None
    obj_type: str | None = None
    fields: dict = {}
    properties: dict = {}
    in_properties = False

    def finalize() -> TopologyEvent | None:
        nonlocal action, obj_id, obj_type, fields, properties, in_properties
        event: TopologyEvent | None = None
        if action is not None and obj_id is not None:
            kind = _KIND_BY_TYPE.get(obj_type or "")
            if action == "added":
                if kind is not None:
                    cache[obj_id] = kind
            else:  # removed
                kind = cache.pop(obj_id, None)
            if kind is not None:
                event = TopologyEvent(
                    action=action,
                    id=obj_id,
                    kind=kind,
                    summary=_summarize(kind, fields, properties),
                )
        action = None
        obj_id = None
        obj_type = None
        fields = {}
        properties = {}
        in_properties = False
        return event

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if stripped in ("added:", "removed:"):
            event = finalize()
            if event is not None:
                yield event
            action = stripped[:-1]
            continue
        if action is None:
            continue
        if stripped == "" and not in_properties:
            event = finalize()
            if event is not None:
                yield event
            continue
        if stripped == "properties:":
            in_properties = True
            continue
        if in_properties:
            if stripped == "" or _TOP_LEVEL_RE.match(line):
                # Blank line or an unindented field ends the properties
                # block (e.g. `format:` param dumps after a Link's props).
                in_properties = False
                if stripped == "":
                    continue
            else:
                prop_match = _PROPERTY_RE.match(line)
                if prop_match:
                    properties[prop_match.group(1)] = _strip_quotes(prop_match.group(2))
                continue
        top_match = _TOP_LEVEL_RE.match(line)
        if not top_match:
            continue
        key, value = top_match.group(1), top_match.group(2)
        if key == "id":
            try:
                obj_id = int(value)
            except ValueError:
                obj_id = None
        elif key == "type":
            type_match = _TYPE_RE.match(value)
            obj_type = type_match.group(1) if type_match else value
        elif key in (
            "output-node-id",
            "output-port-id",
            "input-node-id",
            "input-port-id",
        ):
            fields[key] = value

    event = finalize()
    if event is not None:
        yield event


def event_payload(event: TopologyEvent) -> dict:
    return {
        "action": event.action,
        "kind": event.kind,
        "id": event.id,
        **event.summary,
    }


TOPOLOGY_LANE = "audio-topology"


def run_topology(
    *,
    capture_root: Path,
    pw_mon_bin: str = "pw-mon",
    popen=subprocess.Popen,
    writer_factory=None,
    stop_event=None,
) -> int:
    """Live entry point (`sinnix-audio-capture topology`): spawn `pw-mon -a
    -p`, parse it, and write one sinnix-capture-v1 envelope per Node/Port/
    Link add/remove event to the audio-topology lane."""
    from sinnix_capture.writer import CaptureWriter

    if writer_factory is None:
        writer_factory = lambda: CaptureWriter(capture_root, TOPOLOGY_LANE)  # noqa: E731

    writer = writer_factory()
    proc = popen([pw_mon_bin, "-a", "-p"], stdout=subprocess.PIPE, text=True)
    assert proc.stdout is not None
    id_kind_cache: dict[int, str] = {}
    written = 0
    try:
        for event in parse_pw_mon_stream(proc.stdout, id_kind_cache=id_kind_cache):
            if stop_event is not None and stop_event.is_set():
                break
            writer.write(event_payload(event))
            written += 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    return written
