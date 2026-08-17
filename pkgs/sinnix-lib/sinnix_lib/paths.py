"""Common path/environment resolution.

The single source for "where does sinnix state live" answers that scripts
resolved ad hoc. Values mirror the Nix-side declarations (foundation.nix,
runtime.nix); env overrides exist for tests, not for configuration — the
configuration authority stays in Nix.
"""

from __future__ import annotations

import os
from pathlib import Path


def runtime_dir() -> Path:
    """/run/sinnix (system scope) — the sentinel/reducer runtime root."""
    return Path(os.environ.get("SINNIX_RUNTIME_DIR", "/run/sinnix"))


def user_runtime_dir() -> Path:
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    return Path(xdg) if xdg else Path(f"/run/user/{os.getuid()}")


def inventory_path() -> Path:
    return Path(os.environ.get("SINNIX_RUNTIME_INVENTORY", "/etc/sinnix/runtime-inventory.json"))


def transitions_ledger() -> Path:
    return runtime_dir() / "health-transitions.jsonl"


def state_dir(name: str) -> Path:
    """Durable service state root for *name* under /realm/state."""
    return Path(os.environ.get("SINNIX_STATE_ROOT", "/realm/state")) / name
