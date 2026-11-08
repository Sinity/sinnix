"""Polylogue daemon status reader (`polylogue status --json`)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..runtime_inventory import polylogue_archive

POLYLOGUE_UNIT = "polylogue-live.service"
# Database files of the Rust archive. Original bytes live in the blob store
# (`blobs/`, `segments/` in later builds), which is not listed here.
POLYLOGUE_FILES = ("archive.db", "index.db", "embeddings.db")


def _archive_root() -> Path | None:
    configured = polylogue_archive().get("archiveRoot")
    return Path(configured) if isinstance(configured, str) and configured else None


def polylogue_files() -> dict[str, Any]:
    root = _archive_root()
    rows: list[dict[str, Any]] = []
    if root is None:
        return {"root": None, "files": rows}
    for name in POLYLOGUE_FILES:
        path = root / name
        try:
            size = path.stat().st_size if path.is_file() else None
            state = (
                "present"
                if size is not None
                else ("missing" if not path.exists() else "inaccessible")
            )
        except OSError:
            size, state = None, "inaccessible"
        rows.append({"name": name, "path": str(path), "state": state, "bytes": size})
    return {"root": str(root), "files": rows}


def _status_command() -> list[str] | None:
    override = os.environ.get("SINNIX_OBSERVE_POLYLOGUE")
    executable = override or shutil.which("polylogue")
    return [executable, "status", "--json"] if executable else None


def collect_polylogue_status(timeout: float = 20.0) -> dict[str, Any]:
    """Ask the running daemon for its status; report a gap when it cannot answer."""
    source: dict[str, Any] = {
        "unit": POLYLOGUE_UNIT,
        "available": False,
        "archive": polylogue_files(),
    }
    command = _status_command()
    if command is None:
        source["gaps"] = ["polylogue.status.no_executable"]
        return source
    try:
        done = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        source["gaps"] = ["polylogue.status.unreachable"]
        source["error"] = str(error)
        return source
    if done.returncode != 0:
        source["gaps"] = ["polylogue.status.failed"]
        source["error"] = (done.stderr or done.stdout).strip()[:500]
        return source
    try:
        status = json.loads(done.stdout)
    except json.JSONDecodeError:
        source["gaps"] = ["polylogue.status.unreadable"]
        return source
    store = status.get("store") or {}
    source.update(
        available=True,
        pid=status.get("pid"),
        uptime_seconds=status.get("uptime_seconds"),
        busy=status.get("busy"),
        passes=status.get("passes"),
        mode=(status.get("mode") or {}).get("state"),
        last_pass=status.get("last_pass"),
        store={
            key: store.get(key)
            for key in (
                "sessions",
                "messages",
                "inputs",
                "revisions",
                "stored_bytes",
                "parse_states",
                "search_pending",
            )
        },
    )
    return source
