"""Track PipeWire's default source/sink node names.

The two canonical channels (`mic`, `sink-monitor`) must never hardcode a
node name -- they resolve the *default* audio source/sink at capture time
and react when the operator changes the active device (unplug a headset,
switch outputs in the desktop shell, ...).

`pw-metadata -n default` is a long-running subscription: on start it prints
the current values, then one `update:` line every time a tracked key
changes, for as long as the process runs. Sample lines:

    update: id:0 key:'default.audio.sink' value:'{"name":"bluez_output.AC_80_0A_D4_08_48.1"}' type:'Spa:String:JSON'
    update: id:0 key:'default.audio.source' value:'{"name":"alsa_input.usb-FiiO_DigiHug_USB_Audio-01.analog-stereo"}' type:'Spa:String:JSON'

Only `default.audio.sink` / `default.audio.source` are tracked here --
`default.configured.audio.{sink,source}` is the operator's *preference*,
not necessarily the node that's actually active right now, and
`target.node` is unrelated per-stream routing metadata.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

_LINE_RE = re.compile(
    r"^update:\s+id:(?P<id>-?\d+)\s+key:'(?P<key>[^']*)'\s+value:'(?P<value>.*)'\s+type:'(?P<type>[^']*)'\s*$"
)

_TRACKED_KEYS = {
    "default.audio.sink": "sink",
    "default.audio.source": "source",
}


def parse_default_line(line: str) -> tuple[str, str | None] | None:
    """Parse one `pw-metadata -n default` output line.

    Returns `(kind, node_name)` where `kind` is "sink" or "source" and
    `node_name` is the resolved `node.name`, or `None` if unset / the value
    couldn't be decoded. Returns `None` (not a tuple) for any line that
    isn't an update to a tracked key -- callers should just skip it.
    """
    match = _LINE_RE.match(line.strip())
    if match is None:
        return None
    key = match.group("key")
    kind = _TRACKED_KEYS.get(key)
    if kind is None:
        return None
    raw_value = match.group("value")
    if not raw_value or raw_value == "null":
        return (kind, None)
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return (kind, None)
    name = decoded.get("name") if isinstance(decoded, dict) else None
    return (kind, name)


@dataclass
class DefaultTargets:
    sink: str | None = None
    source: str | None = None

    def apply(self, kind: str, name: str | None) -> bool:
        """Update the tracked value; returns True if it actually changed."""
        current = getattr(self, kind)
        if current == name:
            return False
        setattr(self, kind, name)
        return True


def resolve_target(channel: str, targets: DefaultTargets) -> str | None:
    """The PipeWire node *name* a canonical channel should capture from, or
    None if the relevant default isn't known yet (nothing to connect to).

    This is a node name to look up (via `resolve_node_serial`), not the
    final `pw-record --target` value -- see that function's docstring for
    why `--target <name>` is not used directly. The sink-monitor channel
    targets the *sink* node's own name, unmodified: a sink's monitor ports
    live on the sink node itself (there is no separate `<sink-name>.monitor`
    node; it does not appear in `pw-dump`), and a Capture-direction stream
    that resolves onto the sink node attaches to its monitor ports
    automatically.
    """
    if channel == "mic":
        return targets.source
    if channel == "sink-monitor":
        return targets.sink
    raise ValueError(f"unknown canonical audio channel: {channel!r}")


def resolve_node_serial(
    pw_dump_bin: str,
    node_name: str,
    *,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> str | None:
    """Resolve a PipeWire node name to its stable `object.serial`, for use
    as a `pw-record --target` value.

    Do not pass a node name as `--target`. `pw-record --target <node-name>`
    does *string* name matching and does not reliably attach a
    Capture-direction stream to the right node once the connection is
    re-established mid-session: the stream falls back to WirePlumber's
    default-object auto-link, which silently lands on the wrong device (both
    the mic and sink-monitor recorders end up consuming the mic's own ALSA
    source), and even when the fallback picks the right device that link is
    serviced by a slow reconnect path rather than the real-time audio graph,
    delivering PCM in bursts seconds apart and losing most of the hour.
    Passing `--target <serial>` (a stable numeric `object.serial`, resolved
    here from a live `pw-dump`) links immediately via the normal real-time
    path with no such stall.

    Returns None if `pw-dump` fails or no node with that name is currently
    present (transient race at startup/device-switch); callers should fall
    back to targeting by name in that case rather than blocking forever.
    """
    try:
        proc = run([pw_dump_bin], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    try:
        objects = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(objects, list):
        return None
    for obj in objects:
        if not isinstance(obj, dict) or obj.get("type") != "PipeWire:Interface:Node":
            continue
        info = obj.get("info") or {}
        props = info.get("props") or {}
        if props.get("node.name") == node_name:
            serial = props.get("object.serial")
            if serial is not None:
                return str(serial)
    return None
