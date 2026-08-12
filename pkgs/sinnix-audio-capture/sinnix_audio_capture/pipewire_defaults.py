"""Track PipeWire's default source/sink node names.

The two canonical channels (`mic`, `sink-monitor`) must never hardcode a
node name -- they resolve the *default* audio source/sink at capture time
and react when the operator changes the active device (unplug a headset,
switch outputs in the desktop shell, ...).

`pw-metadata -n default` is a long-running subscription: on start it prints
the current values, then one `update:` line every time a tracked key
changes, for as long as the process runs. Sample line (captured live on
sinnix-prime 2026-08-12):

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
    """PipeWire `--target` value for a canonical channel, or None if the
    relevant default isn't known yet (nothing to connect to)."""
    if channel == "mic":
        return targets.source
    if channel == "sink-monitor":
        return f"{targets.sink}.monitor" if targets.sink else None
    raise ValueError(f"unknown canonical audio channel: {channel!r}")
