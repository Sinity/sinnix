"""Past durations: the job event log, the task-runner history, closed Beads.

Every range this module returns carries the number of samples behind it, and
says so when that number is small.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SIZES = ("small", "medium", "large", "xlarge")
# A size class for closed tasks that carry only the older single estimate.
SIZE_UPPER_MINUTES = (("small", 60), ("medium", 240), ("large", 960))
THIN_SAMPLES = 8
MAX_SAMPLES_PER_KEY = 400
MAX_RECENT_JOBS = 300


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def quantile(ordered: list[float], fraction: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize(values: Iterable[float], basis: str) -> dict[str, Any]:
    """The 10th to 90th percentile of ``values`` with the sample count.

    ``basis`` says in plain words what the samples are. With no samples the
    range is absent; with fewer than ``THIN_SAMPLES`` it is marked thin and
    widened to the observed minimum and maximum.
    """
    ordered = sorted(float(value) for value in values if value is not None)
    count = len(ordered)
    if not count:
        return {
            "samples": 0,
            "basis": basis,
            "thin": True,
            "note": f"no history: 0 {basis}",
        }
    thin = count < THIN_SAMPLES
    low = ordered[0] if thin else quantile(ordered, 0.10)
    high = ordered[-1] if thin else quantile(ordered, 0.90)
    summary = {
        "samples": count,
        "basis": basis,
        "thin": thin,
        "low_seconds": round(low),
        "median_seconds": round(quantile(ordered, 0.50)),
        "high_seconds": round(high),
    }
    if thin:
        summary["note"] = (
            f"rests on only {count} {basis}; the range is the observed "
            "minimum to maximum"
        )
    return summary


class JobLog:
    """The agentctl event log, folded incrementally.

    The first refresh reads the whole file; later ones read only the bytes
    appended since. Nothing is written back and no record is dropped from the
    log itself.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0
        self.identity: tuple[int, int] | None = None
        self.starts: dict[tuple[str, int], float] = {}
        self.run_seconds: dict[str, deque[float]] = {}
        self.wait_seconds: dict[str, deque[float]] = {}
        self.recent: deque[dict[str, Any]] = deque(maxlen=MAX_RECENT_JOBS)
        self.finished_count = 0
        self.first_at: str | None = None
        self.error: str | None = None

    def refresh(self) -> None:
        try:
            info = os.stat(self.path)
        except OSError as error:
            self.error = str(error)
            return
        identity = (info.st_dev, info.st_ino)
        if identity != self.identity or info.st_size < self.offset:
            self.__init__(self.path)  # a replaced log is read from the start
            self.identity = identity
        if info.st_size == self.offset:
            return
        try:
            with open(self.path, "rb") as handle:
                handle.seek(self.offset)
                while True:
                    line = handle.readline()
                    if not line.endswith(b"\n"):
                        break  # a partial last line is read next time
                    self.offset += len(line)
                    if b'"queue-task"' in line:
                        self._fold(line)
            self.error = None
        except OSError as error:
            self.error = str(error)

    def _fold(self, line: bytes) -> None:
        try:
            event = json.loads(line)
        except ValueError:
            return
        if not isinstance(event, dict):
            return
        at = parse_time(event.get("emitted_at"))
        if at is None:
            return
        if self.first_at is None:
            self.first_at = event["emitted_at"]
        job_id, phase = event.get("job_id"), event.get("phase")
        if event.get("kind") != "queue-task" or not isinstance(job_id, str):
            return
        key = (job_id, int(event.get("attempt") or 0))
        label = str(event.get("label") or "")
        if phase == "started":
            self.starts[key] = at.timestamp()
            queued = parse_time(event.get("enqueued_at"))
            pool = event.get("pool")
            if queued is not None and isinstance(pool, str) and key[1] <= 1:
                self.wait_seconds.setdefault(
                    pool, deque(maxlen=MAX_SAMPLES_PER_KEY)
                ).append(max(0.0, (at - queued).total_seconds()))
            return
        if phase != "finished":
            return
        started = self.starts.pop(key, None)
        seconds = at.timestamp() - started if started is not None else None
        outcome = str(event.get("outcome") or "")
        self.finished_count += 1
        if seconds is not None and outcome == "success" and label:
            self.run_seconds.setdefault(
                label, deque(maxlen=MAX_SAMPLES_PER_KEY)
            ).append(seconds)
        self.recent.append(
            {
                "project": event.get("project"),
                "operation": event.get("operation"),
                "label": label,
                "pool": event.get("pool"),
                "job_id": job_id,
                "attempt": key[1],
                "task_id": event.get("task_id"),
                "outcome": outcome,
                "exit_code": event.get("exit_code"),
                "ended_at": event["emitted_at"],
                "seconds": round(seconds) if seconds is not None else None,
                "working_directory": event.get("working_directory"),
                "caller": event.get("caller"),
            }
        )

    def sample_count(self) -> int:
        return sum(len(values) for values in self.run_seconds.values())


class TaskRunnerHistory:
    """Run durations from the devkit task-runner history database."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.last_id = 0
        self.run_seconds: dict[str, deque[float]] = {}
        self.rows = 0
        self.error: str | None = None

    def refresh(self) -> None:
        if not self.path.exists():
            self.error = "history database absent"
            return
        try:
            connection = sqlite3.connect(
                f"file:{self.path}?mode=ro", uri=True, timeout=5
            )
            try:
                cursor = connection.execute(
                    "select id, project, command, duration_ms from runs "
                    "where id > ? and status = 'passed' and duration_ms is not null "
                    "order by id",
                    (self.last_id,),
                )
                for run_id, project, command, duration in cursor:
                    self.last_id = run_id
                    self.rows += 1
                    self.run_seconds.setdefault(
                        f"{project}:{command}", deque(maxlen=MAX_SAMPLES_PER_KEY)
                    ).append(duration / 1000)
            finally:
                connection.close()
            self.error = None
        except sqlite3.Error as error:
            self.error = str(error)


def bead_size(row: dict[str, Any]) -> str | None:
    """The size class a Bead carries: a ``size:`` label, else its estimate."""
    for label in row.get("labels") or []:
        if isinstance(label, str) and label.startswith("size:"):
            size = label[5:].replace("extra-large", "xlarge").replace("-", "")
            if size in SIZES:
                return size
    minutes = row.get("estimated_minutes")
    if isinstance(minutes, (int, float)) and minutes > 0:
        for size, upper in SIZE_UPPER_MINUTES:
            if minutes <= upper:
                return size
        return "xlarge"
    return None


def bead_kind(row: dict[str, Any]) -> str:
    """The kind of work: a ``kind:`` label, else the issue type."""
    for label in row.get("labels") or []:
        if isinstance(label, str) and label.startswith("kind:") and label[5:]:
            return label[5:]
    return str(row.get("issue_type") or "task")


def bead_own_range(row: dict[str, Any]) -> dict[str, int] | None:
    """The time range the agent recorded on the Bead, in seconds."""
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        return None
    try:
        low = float(metadata["estimate_low_minutes"])
        high = float(metadata["estimate_high_minutes"])
    except (KeyError, TypeError, ValueError):
        return None
    if low < 0 or high < low:
        return None
    return {"low_seconds": round(low * 60), "high_seconds": round(high * 60)}


def bead_sample(project: str, row: dict[str, Any]) -> dict[str, Any] | None:
    """One closed Bead as a duration sample, or None without both timestamps."""
    created, closed = (
        parse_time(row.get("created_at")),
        parse_time(row.get("closed_at")),
    )
    if created is None or closed is None or closed < created:
        return None
    started = parse_time(row.get("started_at"))
    labels = [label for label in row.get("labels") or [] if isinstance(label, str)]
    return {
        "project": project,
        "kind": bead_kind(row),
        "size": bead_size(row),
        "size_from_label": any(label.startswith("size:") for label in labels),
        "human": "human" in labels,
        "total_seconds": (closed - created).total_seconds(),
        "claimed_seconds": (closed - started).total_seconds()
        if started is not None and closed >= started
        else None,
    }


def estimate_range(
    samples: list[dict[str, Any]], kind: str | None, size: str | None
) -> dict[str, Any]:
    """How long closed tasks like this took, from claim to close.

    Falls back in the open: same kind and size, then the size alone, then the
    kind alone, then every closed task. The answer names the set it used.
    """
    claimed = [sample for sample in samples if sample["claimed_seconds"] is not None]
    attempts: list[tuple[str, list[dict[str, Any]]]] = []
    if kind and size:
        attempts.append(
            (
                f"closed tasks of kind {kind} and size {size}",
                [s for s in claimed if s["kind"] == kind and s["size"] == size],
            )
        )
    if size:
        attempts.append(
            (f"closed tasks of size {size}", [s for s in claimed if s["size"] == size])
        )
    if kind:
        attempts.append(
            (
                f"closed tasks of kind {kind}, any size",
                [s for s in claimed if s["kind"] == kind],
            )
        )
    attempts.append(("closed tasks of any kind and size", claimed))
    chosen_basis, chosen = attempts[-1]
    for basis, matching in attempts:
        if len(matching) >= THIN_SAMPLES:
            chosen_basis, chosen = basis, matching
            break
    else:
        # Nothing reaches the threshold: use the most specific non-empty set.
        for basis, matching in attempts:
            if matching:
                chosen_basis, chosen = basis, matching
                break
    exact_basis, exact = attempts[0]
    result = {
        "kind": kind,
        "size": size,
        "claim_to_close": summarize(
            (s["claimed_seconds"] for s in chosen), chosen_basis
        ),
        "created_to_close": summarize(
            (s["total_seconds"] for s in chosen), chosen_basis
        ),
        "exact_match_samples": len(exact),
        "size_labelled_samples": sum(1 for s in chosen if s["size_from_label"]),
    }
    if chosen_basis != exact_basis:
        result["fallback"] = (
            f"only {len(exact)} {exact_basis}; the range uses {chosen_basis}"
        )
    return result
