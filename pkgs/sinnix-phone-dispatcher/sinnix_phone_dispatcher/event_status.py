"""Read the retained phone-status tail without loading unbounded event lines."""

from __future__ import annotations

import io
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

MAX_TAIL_BYTES = 4 * 1024 * 1024
MAX_RECORD_BYTES = 1024 * 1024


def _display(value: object) -> str:
    return ''.join(char if char.isprintable() else ' ' for char in value)[:1024] if isinstance(value, str) else ''


def read_event_status(path: Path | None) -> dict:
    if path is None:
        return {"state": "missing"}
    try:
        # Nonblocking open must precede the descriptor check: a FIFO can hang
        # before a pathname-only type check is able to reject it.
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise OSError('event status source is not a regular file')
            size = handle.seek(0, 2)
            start = max(0, size - MAX_TAIL_BYTES)
            partial_head = False
            if start:
                handle.seek(start - 1)
                partial_head = handle.read(1) != b'\n'
            handle.seek(start)
            payload = handle.read(size - start)
    except FileNotFoundError:
        return {"state": "missing"}
    except OSError as error:
        return {"state": "unavailable", "reason": str(error)}
    if not size:
        return {"state": "empty"}
    if partial_head:
        payload = payload.partition(b'\n')[2]
    newest = chunk = upload = None
    skipped = 0
    for line in io.BytesIO(payload):
        if not line.endswith(b'\n') or len(line) > MAX_RECORD_BYTES:
            skipped += 1
            continue
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            if not isinstance(record, dict) or not isinstance(record.get('ts'), str):
                raise ValueError('missing timestamp')
            stamp = datetime.fromisoformat(record['ts'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('timestamp has no timezone')
            stamp = stamp.astimezone(timezone.utc)
        except (ValueError, UnicodeDecodeError, OverflowError, RecursionError):
            skipped += 1
            continue
        if newest is None or stamp >= newest[0]:
            newest = (stamp, record['ts'])
        kind = record.get('kind')
        if kind == 'chunk_closed' and isinstance(record.get('chunk'), str):
            if chunk is None or stamp >= chunk[0]:
                chunk = (stamp, _display(record['chunk']))
        if isinstance(kind, str) and kind.startswith('chunk_upload'):
            if upload is None or stamp >= upload[0]:
                upload = (stamp, _display(kind), _display(record.get('reason')))
    result = {"state": "observed" if newest else "no_readable_records", "skipped_records": skipped}
    if newest:
        result['ts'] = newest[1]
    if chunk:
        result['chunk'] = chunk[1]
    if upload:
        result['upload'] = upload[1] + (f" — {upload[2]}" if upload[2] else '')
    return result
