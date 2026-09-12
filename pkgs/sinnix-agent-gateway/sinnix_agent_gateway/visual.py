"""Private source snapshots and an isolated visual decoding boundary."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .results import ProtocolError


def snapshot(source: Path, destination: Path) -> None:
    """Stream a stable regular file into private storage, never opening a FIFO."""
    try:
        descriptor = os.open(source, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ProtocolError("invalid_request", "source is not a regular file")
            if before.st_size > shutil.disk_usage(destination.parent).free:
                raise ProtocolError(
                    "response_bound",
                    "insufficient space for a private original snapshot",
                )
            with destination.open("xb") as output:
                destination.chmod(0o600)
                remaining = before.st_size
                while remaining:
                    data = handle.read(min(1024 * 1024, remaining))
                    if not data:
                        raise ProtocolError(
                            "source_changed", "source changed during snapshot"
                        )
                    output.write(data)
                    remaining -= len(data)
            after = os.fstat(handle.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise ProtocolError("source_changed", "source changed during snapshot")
    except FileNotFoundError as exc:
        raise ProtocolError("not_found", "source is missing") from exc
    except PermissionError as exc:
        raise ProtocolError("policy_denied", "source is not readable") from exc
    except OSError as exc:
        raise ProtocolError(
            "owner_failed", "could not create private source snapshot"
        ) from exc


def decode(
    path: Path,
    directory: Path,
    *,
    render: bool,
    pages: list[int],
    mode: str = "fit",
    max_edge: int = 1600,
    crop: dict | None = None,
    budget: int = 3 * 1024 * 1024,
) -> dict[str, Any]:
    request = {
        "path": str(path),
        "directory": str(directory),
        "render": render,
        "pages": pages,
        "mode": mode,
        "max_edge": max_edge,
        "crop": crop,
        "budget": budget,
    }
    encoded = json.dumps(request)
    if len(encoded.encode()) > 32_768:
        raise ProtocolError(
            "response_bound",
            "selected-page metadata exceeds decoder request budget; split the selection",
        )
    try:
        # Files keep native parser diagnostics out of gateway memory; the child
        # also bounds file size, including these streams, before importing parsers.
        with (
            tempfile.TemporaryFile(dir=directory) as stdout,
            tempfile.TemporaryFile(dir=directory) as stderr,
        ):
            # The installed console wrapper adds the gateway and decoder
            # dependencies to *this* interpreter with ``site.addsitedir``.
            # ``sys.executable -m …`` starts the base Nix Python again, which
            # has none of those paths.  Pass the already-resolved, trusted
            # interpreter search path explicitly to the disposable process.
            # Do not inherit an ambient PYTHONPATH, which could turn a visual
            # read into arbitrary code loading.
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join(
                entry for entry in sys.path if entry
            )
            environment["PYTHONNOUSERSITE"] = "true"
            completed = subprocess.run(
                [sys.executable, "-m", "sinnix_agent_gateway.visual_decoder"],
                input=encoded,
                text=True,
                stdout=stdout,
                stderr=stderr,
                env=environment,
                timeout=30,
                check=False,
            )
            stdout.seek(0)
            result_bytes = stdout.read(1024 * 1024 + 1)
    except subprocess.TimeoutExpired as exc:
        raise ProtocolError(
            "response_bound",
            "visual decoder exceeded 30 seconds; request fewer pages or a smaller view",
        ) from exc
    except OSError as exc:
        raise ProtocolError("unavailable", "visual decoder could not start") from exc
    if completed.returncode:
        raise ProtocolError(
            "response_bound", "visual decoder failed within its resource bounds"
        )
    if len(result_bytes) > 1024 * 1024:
        raise ProtocolError(
            "response_bound",
            "selected-page metadata exceeds response budget; split the selection",
        )
    try:
        result = json.loads(result_bytes)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ProtocolError(
            "owner_failed", "visual decoder returned an invalid result"
        ) from exc
    if "error" in result:
        raise ProtocolError(result["error"], result["message"])
    return result
