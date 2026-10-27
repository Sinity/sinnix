"""One-shot, writer-serialized migration of legacy embedded outcomes."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from itertools import zip_longest
from pathlib import Path
from typing import Any

from sinnix_lib.lock import flock


class CompactionError(RuntimeError):
    """Compaction verification or publication failed."""


# These fields belong to both the event envelope and the outcome record.
_SHARED = {"attempt", "outcome", "exit_code", "unit", "pool"}


def _rewrite(raw: bytes, jobs: Path) -> tuple[bytes, bool]:
    try:
        event = json.loads(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return raw, False
    if (
        not isinstance(event, dict)
        or event.get("kind") != "queue-task"
        or event.get("phase") != "finished"
        or "execution_receipt" not in event
        or "outcome_ref" in event
    ):
        return raw, False
    job = event.get("job_id")
    attempt = event.get("attempt")
    if not isinstance(job, str) or Path(job).name != job or job in {".", "..", ""}:
        return raw, True
    candidates = []
    if type(attempt) is int and attempt > 0:
        candidates.append(jobs / f"{job}.attempts" / str(attempt) / "output.outcome")
    candidates.append(jobs / f"{job}.outcome")
    for candidate in candidates:
        try:
            path = candidate.resolve(strict=True)
            payload = path.read_bytes()
            outcome = json.loads(payload)
            if not isinstance(outcome, dict) or "execution_receipt" not in outcome:
                continue
            # Reconstruct the exact bytes used by the legacy publisher from
            # the embedded fields, including any newer outcome extensions.
            embedded = {key: event[key] for key in outcome}
            digest = hashlib.sha256(payload).hexdigest()
            if (
                hashlib.sha256(
                    json.dumps(embedded, sort_keys=True).encode()
                ).hexdigest()
                != digest
            ):
                continue
        except (OSError, ValueError, KeyError, UnicodeDecodeError, RecursionError):
            continue
        compact = {
            key: value
            for key, value in event.items()
            if key not in outcome or key in _SHARED
        }
        compact["outcome_ref"] = {"path": str(path), "sha256": digest}
        return json.dumps(
            compact, sort_keys=True, separators=(",", ":")
        ).encode() + b"\n", True
    return raw, True


def compact_events(spool: Path, jobs: Path) -> dict[str, Any]:
    """Stream into a same-directory file, verify, then replace under the append lock.

    Memory is bounded by one event and its outcome. Invalid records are copied
    byte-for-byte; an unterminated tail refuses the entire migration.
    """
    temporary: Path | None = None
    try:
        with flock(spool.with_name(spool.name + ".lock")):
            with spool.open("rb") as source:
                metadata = os.fstat(source.fileno())
                if not stat.S_ISREG(metadata.st_mode) or spool.is_symlink():
                    raise CompactionError(
                        "event log must be a regular file, not a symlink"
                    )
                counts = {
                    "events_rewritten": 0,
                    "events_kept": 0,
                    "receipts_unresolved": 0,
                }
                with tempfile.NamedTemporaryFile(
                    dir=spool.parent, prefix=f".{spool.name}.compact-", delete=False
                ) as target:
                    temporary = Path(target.name)
                    os.fchown(target.fileno(), metadata.st_uid, metadata.st_gid)
                    os.fchmod(target.fileno(), stat.S_IMODE(metadata.st_mode))
                    for raw in source:
                        if not raw.endswith(b"\n"):
                            raise CompactionError(
                                "unterminated event log tail; original retained"
                            )
                        rewritten, receipt = _rewrite(raw, jobs)
                        changed = rewritten != raw
                        counts["events_rewritten" if changed else "events_kept"] += 1
                        counts["receipts_unresolved"] += int(receipt and not changed)
                        target.write(rewritten)
                    target.flush()
                    os.fsync(target.fileno())
                # Re-read both files, proving row count, unchanged bytes, and
                # that every rewritten row still resolves to the embedded data.
                source.seek(0)
                verified = 0
                with temporary.open("rb") as candidate:
                    for original, rewritten in zip_longest(source, candidate):
                        if original is None or rewritten is None:
                            raise CompactionError("compaction changed the line count")
                        if (
                            original != rewritten
                            and _rewrite(original, jobs)[0] != rewritten
                        ):
                            raise CompactionError(
                                "rewritten outcome no longer resolves"
                            )
                        verified += 1
                if verified != counts["events_rewritten"] + counts["events_kept"]:
                    raise CompactionError("compaction line count verification failed")
                after = temporary.stat().st_size
                os.replace(temporary, spool)
                temporary = None
                directory = os.open(spool.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
                return {
                    "bytes_before": metadata.st_size,
                    "bytes_after": after,
                    **counts,
                }
    except OSError as exc:
        raise CompactionError(f"event compaction failed: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
