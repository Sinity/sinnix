"""Batched systemd unit probes.

The blank-line-delimited ``systemctl show`` block parser existed in bash
(health sentinel), in Python (hub renderer), and in sinnix-observe — three
dialects of one parser. This is the one implementation, with the sentinel's
sudo/user-bus bridge for probing another user's manager from a system unit.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

DEFAULT_PROPERTIES = ("Id", "ActiveState", "SubState", "Type", "Result", "WantedBy")


def _parse_blocks(text: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    block: dict[str, str] = {}
    for line in [*text.splitlines(), ""]:
        if not line.strip():
            if block.get("Id"):
                out[block["Id"]] = block
            block = {}
            continue
        key, _, value = line.partition("=")
        block[key] = value
    return out


def show_units(
    units: Sequence[str],
    *,
    user: bool = False,
    properties: Sequence[str] = DEFAULT_PROPERTIES,
) -> dict[str, dict[str, str]]:
    """One batched ``systemctl [--user] show`` call → {unit: {prop: value}}.

    Unknown units come back with ``ActiveState=inactive`` from systemd
    itself; absence from the result means the call failed entirely.
    """
    if not units:
        return {}
    cmd = ["systemctl", *(["--user"] if user else []), "show", *units]
    for prop in properties:
        cmd += ["-p", prop]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0 and not proc.stdout:
        return {}
    return _parse_blocks(proc.stdout)


def show_units_as_user(
    units: Sequence[str],
    uid: int,
    *,
    bus_path: Path | None = None,
    properties: Sequence[str] = DEFAULT_PROPERTIES,
) -> dict[str, dict[str, str]]:
    """Probe another user's manager from a privileged caller (the
    sentinel's sudo + session-bus bridge, factored out)."""
    if not units:
        return {}
    bus = bus_path or Path(f"/run/user/{uid}/bus")
    if not bus.is_socket():
        return {}
    cmd = [
        "sudo",
        "-u",
        f"#{uid}",
        f"XDG_RUNTIME_DIR=/run/user/{uid}",
        f"DBUS_SESSION_BUS_ADDRESS=unix:path={bus}",
        "systemctl",
        "--user",
        "show",
        *units,
    ]
    for prop in properties:
        cmd += ["-p", prop]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0 and not proc.stdout:
        return {}
    return _parse_blocks(proc.stdout)
