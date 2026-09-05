"""Wayland selection capture: MIME choice, blob store, payload, write.

Both selection lanes (the clipboard and the PRIMARY selection) run the same
pipeline over a different ``wl-paste`` invocation. A lane supplies its own
list/paste commands, its lane name and one gate -- content de-duplication or
a settle debounce -- and this module owns everything between: which offered
MIME type to take, whether it is text or binary, the content-addressed blob
store, the envelope payload and the write.

Commands arrive as strings and are split with ``shlex``; nothing runs under a
shell. The chosen MIME type is appended to the paste command's argv.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

from .writer import CaptureWriter

# Most specific offered type wins: real image formats, then file-manager
# copies, then the plain-text variants. Anything unrecognized falls back to
# whatever the source offered first, so app-specific rich-text and custom
# formats are still captured rather than dropped.
PREFERRED_MIMES = (
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/bmp",
    "image/tiff",
    "image/webp",
    "text/uri-list",
    "text/plain;charset=utf-8",
    "text/plain",
    "STRING",
    "UTF8_STRING",
)

# Fan-out of the content-addressed blob store: one directory level keyed by
# this many leading characters of the sha256.
BLOB_SHARD_CHARS = 2


def pick_mime(offered: str) -> str | None:
    """The MIME type to request, or None when nothing is on offer."""
    types = [line for line in offered.splitlines() if line]
    if not types:
        return None
    for candidate in PREFERRED_MIMES:
        if candidate in types:
            return candidate
    return types[0]


def is_binary_mime(mime: str) -> bool:
    """Whether content of this type goes to a blob instead of inline text."""
    return mime.startswith("image/") or mime == "application/octet-stream"


def store_blob(lane_dir: Path, content: bytes, digest: str) -> Path:
    """Write content once under its own sha256 and return the blob path."""
    shard_dir = lane_dir / "blobs" / digest[:BLOB_SHARD_CHARS]
    shard_dir.mkdir(parents=True, exist_ok=True)
    blob_path = shard_dir / digest
    if not blob_path.exists():
        # Staged and renamed: the name is a content hash, so a blob
        # interrupted mid-write would otherwise stay truncated forever --
        # every later capture of the same content finds the path present
        # and skips it.
        tmp_path = shard_dir / f".{digest}.tmp"
        tmp_path.write_bytes(content)
        tmp_path.chmod(0o600)
        os.replace(tmp_path, blob_path)
    return blob_path


def source_window(raw: str) -> dict:
    """Normalize a window-attribution command's JSON to class/title."""
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        parsed = None
    if not isinstance(parsed, dict):
        return {"class": None, "title": None}
    return {"class": parsed.get("class"), "title": parsed.get("title")}


def _run(argv: list[str]) -> tuple[int, bytes]:
    """A command's exit status and stdout; a status of -1 means it never ran."""
    if not argv:
        return (-1, b"")
    try:
        completed = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return (-1, b"")
    return (completed.returncode, completed.stdout)


def _drain_watch_payload() -> None:
    """Consume the selection payload ``wl-paste --watch`` writes to stdin.

    Any nested clipboard request issued before this drain can deadlock: the
    selection owner blocks writing this payload while we wait on that same
    owner for a second transfer.
    """
    stream = getattr(sys.stdin, "buffer", sys.stdin)
    if stream is None:
        return
    try:
        while stream.read(65536):
            pass
    except (AttributeError, OSError, ValueError):
        return


def _is_duplicate(state_path: Path, key: str) -> bool:
    """Whether this content is the one the lane captured last.

    Only the most recent selection is tracked: this is a linear stream, not
    a history de-duplication.
    """
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        previous: str | None = state_path.read_text()
    except OSError:
        previous = None
    if previous == key:
        return True
    state_path.write_text(key)
    return False


def _is_superseded(state_path: Path, debounce_ms: int) -> bool:
    """Whether a newer trigger claimed the lane during our settle window.

    Toolkits re-offer a selection on every internal extend step rather than
    once at gesture end, so one gesture fires the watch command repeatedly
    within tens of milliseconds. Each invocation stamps a unique trigger,
    sleeps, and yields to whichever stamp is latest at wake-up -- which
    collapses a burst without de-duplicating content, so two distinct
    selections carrying the same text both still land.
    """
    state_path.parent.mkdir(parents=True, exist_ok=True)
    trigger = f"{time.monotonic_ns()}-{os.getpid()}"
    state_path.write_text(trigger)
    time.sleep(debounce_ms / 1000.0)
    try:
        return state_path.read_text() != trigger
    except OSError:
        return False


def capture_selection(
    *,
    capture_root: Path,
    lane: str,
    list_command: str,
    paste_command: str,
    window_command: str | None = None,
    dedup_state: Path | None = None,
    debounce_ms: int | None = None,
    debounce_state: Path | None = None,
) -> int:
    if debounce_ms is not None and debounce_state is None:
        raise ValueError("a debounce window needs a trigger file to arbitrate on")

    _drain_watch_payload()

    # Types the source printed count even if it then exited nonzero: a
    # partially failed offer still names something worth asking for.
    _, offered = _run(shlex.split(list_command))
    mime = pick_mime(offered.decode("utf-8", "replace"))
    if mime is None:
        # Nothing offered right now (selection cleared, or the owner is
        # gone) -- there is nothing to capture.
        return 0

    # A failed transfer is not a capture: its output is a truncated prefix
    # of the selection, which would be recorded as the whole of it.
    status, content = _run([*shlex.split(paste_command), mime])
    if status != 0 or not content:
        return 0

    digest = hashlib.sha256(content).hexdigest()

    if dedup_state is not None and _is_duplicate(dedup_state, f"{mime}:{digest}"):
        return 0
    if debounce_ms is not None and _is_superseded(debounce_state, debounce_ms):
        return 0

    window_status, window_json = (
        _run(shlex.split(window_command)) if window_command else (-1, b"")
    )
    window = source_window(
        window_json.decode("utf-8", "replace") if window_status == 0 else "null"
    )

    size = len(content)
    if is_binary_mime(mime):
        raw_ref: str | None = str(
            store_blob(Path(capture_root) / lane, content, digest)
        )
        payload = {
            "category": "binary",
            "mime": mime,
            "sha256": digest,
            "size": size,
            "source_window": window,
        }
    else:
        raw_ref = None
        payload = {
            "category": "text",
            "mime": mime,
            "text": content.decode("utf-8", "replace"),
            "size": size,
            "source_window": window,
        }

    CaptureWriter(capture_root, lane).write(payload, raw_ref=raw_ref)
    return 0
