#!/usr/bin/env python3
"""Seal yesterday's-and-older WeeChat IRC log files with a content hash.

Walks ``<root>/_raw/<channel>/`` and renames every ``YYYY-MM-DD.log`` older
than ``SEAL_BUFFER_DAYS`` (default: 2 days) to ``YYYY-MM-DD.b2-<12hex>.log``.
The hash is the first 12 hex chars of blake2b over the file contents: short
enough to fit in a filename, long enough (48 bits) to be collision-safe for
any plausible corpus size.

Why 2 days, not 1? WeeChat keeps a per-buffer logger fd open until the next
line for that buffer crosses the date boundary. For dormant channels that go
quiet across midnight the fd lingers — sealing on day+1 would risk renaming a
still-open fd, and any subsequent write would mutate the hash-named file
silently. day+2 guarantees the fd is closed (the fresh day's file has been
opened on the previous run).

Idempotent: already-sealed files are skipped.

History: lived at ``<lake>/irc/scripts/seal_logs.py`` until 2026-08-24; moved
into this repo so the lake holds data only. The former top-level
``lesswrong → _raw/#lesswrong`` browsing symlinks are gone with the move —
they double-counted in every du/find sweep and confused three separate
analysis sessions; browse ``_raw/`` directly.

Run via the systemd user timer (weechat-log-sealer.nix) or by hand:

    python3 seal_logs.py <irc-root>
"""
from __future__ import annotations

import hashlib
import re
import sys
from datetime import date, timedelta
from pathlib import Path

SEAL_BUFFER_DAYS = 2
HASH_LENGTH_HEX = 12  # 48 bits
SEALED_RE = re.compile(r"\.b2-[0-9a-f]+$")
FILENAME_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def file_date(path: Path) -> date | None:
    """Parse the calendar date a log file represents.

    Recognises ``YYYY-MM-DD.log`` (live) and ``YYYY-MM-DD.b2-<hex>.log``
    (sealed). Returns ``None`` for any other shape.
    """
    match = FILENAME_DATE_RE.match(path.stem)
    if match is None:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def blake2b_hex(path: Path, hex_chars: int = HASH_LENGTH_HEX) -> str:
    h = hashlib.blake2b(digest_size=hex_chars // 2)
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def seal_file(path: Path) -> Path | None:
    if SEALED_RE.search(path.stem):
        return None
    digest = blake2b_hex(path)
    target = path.with_name(f"{path.stem}.b2-{digest}.log")
    if target.exists():
        # Different fd already produced this; leave both alone for inspection.
        print(f"  conflict: {target.name} already exists, leaving {path.name}", file=sys.stderr)
        return None
    path.rename(target)
    return target


def seal_all(root: Path, buffer_days: int = SEAL_BUFFER_DAYS) -> tuple[int, int]:
    raw = root / "_raw"
    if not raw.is_dir():
        print(f"no _raw under {root}; nothing to seal", file=sys.stderr)
        return (0, 0)
    threshold = date.today() - timedelta(days=buffer_days)
    sealed_count = 0
    skipped_recent = 0
    for chan_dir in sorted(raw.iterdir()):
        if not chan_dir.is_dir() or chan_dir.is_symlink():
            continue
        for log in sorted(chan_dir.glob("*.log")):
            if SEALED_RE.search(log.stem):
                continue
            log_day = file_date(log)
            if log_day is None:
                continue
            if log_day > threshold:
                skipped_recent += 1
                continue
            if seal_file(log) is not None:
                sealed_count += 1
    print(f"sealed {sealed_count} files (skipped {skipped_recent} within {buffer_days}-day buffer)")
    return (sealed_count, skipped_recent)


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: seal_logs.py <irc-root>", file=sys.stderr)
        raise SystemExit(2)
    root = Path(sys.argv[1]).resolve()
    seal_all(root)


if __name__ == "__main__":
    main()
