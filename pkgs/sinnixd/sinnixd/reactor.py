"""Model-free campaign reactor over the Sinnix event spool.

The reactor is deliberately a small durable state machine.  The event spool is
the input authority, the versioned board is the externalized campaign state,
and reactions are registered by event kind rather than inferred from prose.
No harvester or strategist behavior belongs here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol


BOARD_SCHEMA_VERSION = 1
EVENT_SCHEMA_VERSION = 1
CURSOR_SCHEMA_VERSION = 1
DEFAULT_INTERVAL_SECONDS = 10
DEFAULT_KEEPER_BACKOFF_SECONDS = 600
MAX_KEEPER_BACKOFF_SECONDS = 6 * 60 * 60
MAX_BOARD_LANES = 2_000
MAX_BOARD_PRS = 2_000
MAX_BOARD_ERRORS = 100
MAX_EVENT_BYTES = 1_000_000


class ReactorError(ValueError):
    """An event, board, or cursor violates the reactor contract."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReactorError(f"invalid timestamp: {value!r}") from error
    if parsed.tzinfo is None:
        raise ReactorError("timestamps must include a timezone")
    return parsed.astimezone(UTC)


def _required_string(value: Mapping[str, Any], name: str) -> str:
    result = value.get(name)
    if not isinstance(result, str) or not result:
        raise ReactorError(f"event field {name!r} must be a non-empty string")
    return result


def _optional_string(value: Mapping[str, Any], name: str) -> str | None:
    result = value.get(name)
    if result is not None and (not isinstance(result, str) or not result):
        raise ReactorError(f"event field {name!r} must be a non-empty string or null")
    return result


def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        descriptor = os.open(
            temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
        )
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def append_event(path: Path, event: Mapping[str, Any]) -> None:
    """Append one complete, versioned event and make it visible durably."""

    encoded = (json.dumps(dict(event), sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_EVENT_BYTES:
        raise ReactorError("event exceeds the reactor event size bound")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


@dataclass(frozen=True)
class LaneRecord:
    job_id: str
    project: str
    phase: str
    checkout: Mapping[str, Any] | None
    completed_at: str | None
    review_ready: bool
    updated_at: str

    @classmethod
    def from_event(cls, event: Mapping[str, Any], *, updated_at: str) -> LaneRecord:
        job_id = _required_string(event, "job_id")
        project = _required_string(event, "project")
        phase = _required_string(event, "phase")
        checkout = event.get("checkout")
        if checkout is not None and not isinstance(checkout, Mapping):
            raise ReactorError("lane checkout must be an object or null")
        completed_at = _optional_string(event, "completed_at")
        return cls(
            job_id=job_id,
            project=project,
            phase=phase,
            checkout=dict(checkout) if checkout is not None else None,
            completed_at=completed_at,
            review_ready=project == "polylogue" and phase == "succeeded",
            updated_at=updated_at,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> LaneRecord:
        required = {
            "job_id",
            "project",
            "phase",
            "checkout",
            "completed_at",
            "review_ready",
            "updated_at",
        }
        if set(value) != required:
            raise ReactorError("board lane record has an invalid shape")
        if not isinstance(value["review_ready"], bool):
            raise ReactorError("board lane review_ready must be boolean")
        record = cls(
            job_id=_required_string(value, "job_id"),
            project=_required_string(value, "project"),
            phase=_required_string(value, "phase"),
            checkout=(
                dict(value["checkout"])
                if isinstance(value["checkout"], Mapping)
                else None
            ),
            completed_at=_optional_string(value, "completed_at"),
            review_ready=value["review_ready"],
            updated_at=_required_string(value, "updated_at"),
        )
        if value["checkout"] is not None and not isinstance(value["checkout"], Mapping):
            raise ReactorError("board lane checkout must be an object or null")
        _parse_time(record.updated_at)
        return record

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "project": self.project,
            "phase": self.phase,
            "checkout": dict(self.checkout) if self.checkout is not None else None,
            "completed_at": self.completed_at,
            "review_ready": self.review_ready,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class PullRequestRecord:
    repo: str
    pr: str
    state: str
    bead_id: str | None
    bead_close_status: str
    decision_receipt: Mapping[str, Any] | None
    error: str | None
    updated_at: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PullRequestRecord:
        required = {
            "repo",
            "pr",
            "state",
            "bead_id",
            "bead_close_status",
            "decision_receipt",
            "error",
            "updated_at",
        }
        if set(value) != required:
            raise ReactorError("board pull request record has an invalid shape")
        receipt = value["decision_receipt"]
        if receipt is not None and not isinstance(receipt, Mapping):
            raise ReactorError("board decision receipt must be an object or null")
        result = cls(
            repo=_required_string(value, "repo"),
            pr=_required_string(value, "pr"),
            state=_required_string(value, "state"),
            bead_id=_optional_string(value, "bead_id"),
            bead_close_status=_required_string(value, "bead_close_status"),
            decision_receipt=dict(receipt) if receipt is not None else None,
            error=_optional_string(value, "error"),
            updated_at=_required_string(value, "updated_at"),
        )
        _parse_time(result.updated_at)
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "pr": self.pr,
            "state": self.state,
            "bead_id": self.bead_id,
            "bead_close_status": self.bead_close_status,
            "decision_receipt": (
                dict(self.decision_receipt) if self.decision_receipt is not None else None
            ),
            "error": self.error,
            "updated_at": self.updated_at,
        }


@dataclass
class CampaignBoard:
    """Versioned external board; maps are keyed by stable event identities."""

    updated_at: str = field(default_factory=_now)
    lanes: dict[str, LaneRecord] = field(default_factory=dict)
    prs: dict[str, PullRequestRecord] = field(default_factory=dict)
    keeper: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> CampaignBoard:
        try:
            value = json.loads(path.read_text())
        except FileNotFoundError:
            return cls()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ReactorError(f"campaign board is unreadable: {error}") from error
        if not isinstance(value, Mapping):
            raise ReactorError("campaign board must be a JSON object")
        if "schema_version" not in value:
            return cls._migrate_legacy(value)
        if value.get("schema_version") != BOARD_SCHEMA_VERSION:
            raise ReactorError("campaign board has an unsupported schema version")
        if not isinstance(value.get("updated_at"), str):
            raise ReactorError("campaign board updated_at is invalid")
        _parse_time(value["updated_at"])
        raw_lanes = value.get("lanes")
        raw_prs = value.get("prs")
        raw_keeper = value.get("keeper")
        raw_errors = value.get("errors")
        if not isinstance(raw_lanes, Mapping) or not isinstance(raw_prs, Mapping):
            raise ReactorError("campaign board lanes and prs must be objects")
        if not isinstance(raw_keeper, Mapping) or not isinstance(raw_errors, list):
            raise ReactorError("campaign board keeper and errors have invalid types")
        if len(raw_lanes) > MAX_BOARD_LANES or len(raw_prs) > MAX_BOARD_PRS:
            raise ReactorError("campaign board exceeds its bounded record count")
        lanes = {
            str(key): LaneRecord.from_dict(record)
            for key, record in raw_lanes.items()
            if isinstance(key, str) and isinstance(record, Mapping)
        }
        prs = {
            str(key): PullRequestRecord.from_dict(record)
            for key, record in raw_prs.items()
            if isinstance(key, str) and isinstance(record, Mapping)
        }
        if len(lanes) != len(raw_lanes) or len(prs) != len(raw_prs):
            raise ReactorError("campaign board contains malformed records")
        keeper: dict[str, dict[str, Any]] = {}
        for key, record in raw_keeper.items():
            if not isinstance(key, str) or not isinstance(record, Mapping):
                raise ReactorError("campaign board keeper record is malformed")
            expected = {"emitted_at", "backoff_seconds", "next_eligible_at"}
            if (
                set(record) != expected
                or isinstance(record["backoff_seconds"], bool)
                or not isinstance(record["backoff_seconds"], int)
            ):
                raise ReactorError("campaign board keeper record is malformed")
            _parse_time(str(record["emitted_at"]))
            _parse_time(str(record["next_eligible_at"]))
            keeper[key] = dict(record)
        errors: list[dict[str, str]] = []
        for error in raw_errors[-MAX_BOARD_ERRORS:]:
            if not isinstance(error, Mapping) or set(error) != {"offset", "message", "at"}:
                raise ReactorError("campaign board error record is malformed")
            errors.append({key: str(error[key]) for key in ("offset", "message", "at")})
        return cls(value["updated_at"], lanes, prs, keeper, errors)

    @classmethod
    def _migrate_legacy(cls, value: Mapping[str, Any]) -> CampaignBoard:
        """Read v0 helper output once, then rewrite it as typed board state."""
        updated = value.get("updated")
        if not isinstance(updated, str):
            updated = _now()
        try:
            _parse_time(updated)
        except ReactorError:
            updated = _now()
        lanes: dict[str, LaneRecord] = {}
        raw_lanes = value.get("lanes", {})
        if isinstance(raw_lanes, Mapping):
            for job_id, phase in raw_lanes.items():
                if isinstance(job_id, str) and isinstance(phase, str):
                    lanes[job_id] = LaneRecord(
                        job_id, "unknown", phase, None, None, False, updated
                    )
        prs: dict[str, PullRequestRecord] = {}
        raw_prs = value.get("prs", {})
        if isinstance(raw_prs, Mapping):
            for pr, raw in raw_prs.items():
                if not isinstance(pr, str) or not isinstance(raw, Mapping):
                    continue
                repo = raw.get("repo", "unknown")
                state = raw.get("state", "UNKNOWN")
                if not isinstance(repo, str) or not repo or not isinstance(state, str):
                    continue
                bead_id = raw.get("bead")
                bead_id = bead_id if isinstance(bead_id, str) and bead_id else None
                prs[f"{repo}#{pr}"] = PullRequestRecord(
                    repo,
                    pr,
                    state,
                    bead_id,
                    "closed" if raw.get("bead_closed") is True else "not-attempted",
                    None,
                    None,
                    updated,
                )
        return cls(updated, lanes, prs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": BOARD_SCHEMA_VERSION,
            "updated_at": self.updated_at,
            "lanes": {key: value.to_dict() for key, value in sorted(self.lanes.items())},
            "prs": {key: value.to_dict() for key, value in sorted(self.prs.items())},
            "keeper": dict(sorted(self.keeper.items())),
            "errors": self.errors[-MAX_BOARD_ERRORS:],
        }

    def save(self, path: Path) -> None:
        _atomic_write(path, self.to_dict())

    def record_error(self, offset: int, message: str) -> None:
        self.errors.append({"offset": str(offset), "message": message, "at": _now()})
        self.errors = self.errors[-MAX_BOARD_ERRORS:]


class ReactionHandler(Protocol):
    def __call__(self, event: Mapping[str, Any], context: "ReactionContext") -> None: ...


@dataclass
class ReactionContext:
    board: CampaignBoard
    bead_closer: "BeadCloser"
    project_roots: Mapping[str, Path]


class BeadCloser(Protocol):
    def close(self, bead_id: str, reason: str, *, cwd: Path) -> tuple[bool, str | None]: ...


@dataclass(frozen=True)
class Reaction:
    event_kind: str
    name: str
    handler: ReactionHandler


class ReactionRegistry:
    """Typed event-kind registry; duplicate registrations are rejected."""

    def __init__(self) -> None:
        self._reactions: dict[str, Reaction] = {}

    def register(self, event_kind: str, name: str, handler: ReactionHandler) -> None:
        if not event_kind or event_kind in self._reactions:
            raise ReactorError(f"reaction already registered for {event_kind!r}")
        self._reactions[event_kind] = Reaction(event_kind, name, handler)

    def dispatch(self, event: Mapping[str, Any], context: ReactionContext) -> bool:
        kind = event.get("kind")
        if not isinstance(kind, str):
            raise ReactorError("event kind must be a string")
        reaction = self._reactions.get(kind)
        if reaction is None:
            return False
        reaction.handler(event, context)
        return True


def _lane_reaction(event: Mapping[str, Any], context: ReactionContext) -> None:
    phase = event.get("phase")
    if phase not in {"succeeded", "failed", "cancelled", "timeout", "missing"}:
        return
    updated_at = _now()
    record = LaneRecord.from_event(event, updated_at=updated_at)
    context.board.lanes[record.job_id] = record
    context.board.updated_at = updated_at


def _repo_name(repo: str) -> str:
    return repo.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")


def _receipt(event: Mapping[str, Any]) -> tuple[str, str, Mapping[str, Any]] | None:
    raw = event.get("decision_receipt")
    if not isinstance(raw, Mapping):
        return None
    bead_id = raw.get("bead_id")
    reason = raw.get("reason")
    if not isinstance(bead_id, str) or not bead_id or not isinstance(reason, str) or not reason:
        raise ReactorError("merge decision receipt must contain bead_id and reason")
    receipt_id = raw.get("receipt_id")
    if receipt_id is not None and (not isinstance(receipt_id, str) or not receipt_id):
        raise ReactorError("merge decision receipt_id must be a non-empty string")
    return bead_id, reason, raw


def _merge_reaction(event: Mapping[str, Any], context: ReactionContext) -> None:
    repo = _required_string(event, "repo")
    pr = _required_string(event, "pr")
    state = _required_string(event, "state")
    key = f"{repo}#{pr}"
    prior = context.board.prs.get(key)
    receipt_value = event.get("decision_receipt")
    receipt = dict(receipt_value) if isinstance(receipt_value, Mapping) else None
    bead_id = receipt.get("bead_id") if receipt is not None else None
    if bead_id is not None and (not isinstance(bead_id, str) or not bead_id):
        raise ReactorError("merge decision receipt bead_id must be a non-empty string")
    close_status = prior.bead_close_status if prior is not None else "not-attempted"
    error = prior.error if prior is not None else None
    if state == "MERGED" and close_status not in {"closed", "missing-receipt"}:
        if receipt is None:
            close_status = "missing-receipt"
            error = "merged PR has no decision-time receipt"
        else:
            result = _receipt(event)
            if result is None:
                close_status = "missing-receipt"
                error = "merged PR has no decision-time receipt"
            else:
                bead_id, reason, _ = result
                root_name = event.get("project")
                project_name = root_name if isinstance(root_name, str) and root_name else _repo_name(repo)
                root = context.project_roots.get(project_name)
                if root is None:
                    close_status = "failed"
                    error = f"no configured project root for {project_name}"
                else:
                    closed, close_error = context.bead_closer.close(
                        bead_id, reason, cwd=root
                    )
                    close_status = "closed" if closed else "failed"
                    error = close_error
    context.board.prs[key] = PullRequestRecord(
        repo=repo,
        pr=pr,
        state=state,
        bead_id=bead_id,
        bead_close_status=close_status,
        decision_receipt=receipt,
        error=error,
        updated_at=_now(),
    )
    context.board.updated_at = _now()


def default_reactions() -> ReactionRegistry:
    registry = ReactionRegistry()
    registry.register("attested-agent", "lane-success-to-review-ready", _lane_reaction)
    registry.register("merge_close", "merge-to-bead-close", _merge_reaction)
    return registry


class SubprocessBeadCloser:
    def __init__(self, executable: str = "bd", actor: str = "sinnix-reactor") -> None:
        self.executable = executable
        self.actor = actor

    def close(self, bead_id: str, reason: str, *, cwd: Path) -> tuple[bool, str | None]:
        try:
            result = subprocess.run(
                [
                    self.executable,
                    "close",
                    bead_id,
                    "--force",
                    "--actor",
                    self.actor,
                    "--reason",
                    reason,
                ],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return False, str(error)
        if result.returncode == 0:
            return True, None
        detail = (result.stderr or result.stdout).strip()
        return False, detail[:512] or f"bd close exited {result.returncode}"


@dataclass
class SpoolCursor:
    offset: int = 0
    device: int | None = None
    inode: int | None = None

    @classmethod
    def load(cls, path: Path) -> SpoolCursor:
        try:
            value = json.loads(path.read_text())
        except FileNotFoundError:
            return cls()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ReactorError(f"reactor cursor is unreadable: {error}") from error
        if not isinstance(value, Mapping) or value.get("schema_version") != CURSOR_SCHEMA_VERSION:
            raise ReactorError("reactor cursor has an unsupported schema version")
        offset = value.get("offset")
        device = value.get("device")
        inode = value.get("inode")
        if (
            isinstance(offset, bool)
            or not isinstance(offset, int)
            or offset < 0
            or (device is not None and not isinstance(device, int))
            or (inode is not None and not isinstance(inode, int))
        ):
            raise ReactorError("reactor cursor has invalid fields")
        return cls(offset, device, inode)

    def save(self, path: Path) -> None:
        _atomic_write(
            path,
            {
                "schema_version": CURSOR_SCHEMA_VERSION,
                "offset": self.offset,
                "device": self.device,
                "inode": self.inode,
            },
        )


def _validate_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ReactorError("event must be a JSON object")
    event = dict(value)
    schema = event.get("schema_version", EVENT_SCHEMA_VERSION)
    if schema != EVENT_SCHEMA_VERSION:
        raise ReactorError("event has an unsupported schema version")
    _required_string(event, "kind")
    return event


def _active_lane_count(path: Path | None) -> int | None:
    if path is None or not path.is_dir():
        return None
    count = 0
    for record_path in path.glob("*.json"):
        try:
            record = json.loads(record_path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(record, Mapping):
            continue
        spec = record.get("spec")
        state = record.get("state")
        if (
            isinstance(spec, Mapping)
            and spec.get("kind") == "attested-agent"
            and isinstance(state, Mapping)
            and not state.get("terminal", False)
        ):
            count += 1
    return count


@dataclass
class CampaignReactor:
    event_spool: Path
    board_path: Path
    state_dir: Path
    project_roots: Mapping[str, Path] = field(default_factory=dict)
    jobs_state_dir: Path | None = None
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    min_active_lanes: int = 3
    keeper_backoff_seconds: int = DEFAULT_KEEPER_BACKOFF_SECONDS
    max_keeper_backoff_seconds: int = MAX_KEEPER_BACKOFF_SECONDS
    bead_closer: BeadCloser = field(default_factory=SubprocessBeadCloser)
    registry: ReactionRegistry = field(default_factory=default_reactions)

    def __post_init__(self) -> None:
        if self.interval_seconds < 1 or self.min_active_lanes < 1:
            raise ReactorError("reactor intervals and lane targets must be positive")
        if self.keeper_backoff_seconds < 1 or self.max_keeper_backoff_seconds < 1:
            raise ReactorError("keeper backoff values must be positive")
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._cursor = SpoolCursor.load(self.state_dir / "cursor.json")
        self._board = CampaignBoard.load(self.board_path)

    @property
    def cursor_path(self) -> Path:
        return self.state_dir / "cursor.json"

    def _available_events(self) -> list[tuple[int, dict[str, Any]]]:
        try:
            stat = self.event_spool.stat()
        except FileNotFoundError:
            return []
        if self._cursor.device != stat.st_dev or self._cursor.inode != stat.st_ino or stat.st_size < self._cursor.offset:
            self._cursor.offset = 0
        self._cursor.device = stat.st_dev
        self._cursor.inode = stat.st_ino
        events: list[tuple[int, dict[str, Any]]] = []
        with self.event_spool.open("rb") as handle:
            handle.seek(self._cursor.offset)
            while True:
                offset = handle.tell()
                line = handle.readline()
                if not line or not line.endswith(b"\n"):
                    break
                if len(line) > MAX_EVENT_BYTES:
                    events.append((offset, {"kind": "__invalid__", "error": "event line exceeds size bound"}))
                    continue
                try:
                    events.append((offset, _validate_event(json.loads(line))))
                except (ReactorError, UnicodeDecodeError, json.JSONDecodeError) as error:
                    events.append((offset, {"kind": "__invalid__", "error": str(error)}))
                self._cursor.offset = handle.tell()
        return events

    def _pending_keeper_actions(self) -> list[tuple[str, str]]:
        actions: list[tuple[str, str]] = []
        ready = sorted(
            job_id for job_id, lane in self._board.lanes.items() if lane.review_ready
        )
        if ready:
            actions.append(("review-ready", "review " + ",".join(ready[:12])))
        close_pending = sorted(
            key
            for key, pr in self._board.prs.items()
            if pr.state == "MERGED" and pr.bead_close_status not in {"closed"}
        )
        if close_pending:
            actions.append(("bead-close", "close " + ",".join(close_pending[:12])))
        active = _active_lane_count(self.jobs_state_dir)
        if active is not None and self._board.lanes and active < self.min_active_lanes:
            actions.append(("lanes-low", f"active lanes {active} < {self.min_active_lanes}"))
        return actions

    def _emit_keeper(self) -> None:
        actions = self._pending_keeper_actions()
        active_keys = {key for key, _ in actions}
        for key in list(self._board.keeper):
            if key not in active_keys:
                del self._board.keeper[key]
        now = datetime.now(UTC)
        for key, action in actions:
            prior = self._board.keeper.get(key)
            if prior is not None and now < _parse_time(str(prior["next_eligible_at"])):
                continue
            prior_backoff = (
                int(prior["backoff_seconds"])
                if prior is not None
                else self.keeper_backoff_seconds
            )
            next_backoff = min(prior_backoff * 2, self.max_keeper_backoff_seconds)
            event_id = hashlib.sha256(
                f"{key}:{action}".encode()
            ).hexdigest()[:32]
            append_event(
                self.event_spool,
                {
                    "schema_version": EVENT_SCHEMA_VERSION,
                    "event_id": event_id,
                    "kind": "keeper",
                    "project": "polylogue",
                    "phase": "actionable",
                    "reasons": [key],
                    "actions": [action],
                    "emitted_at": _now(),
                },
            )
            emitted_at = datetime.now(UTC)
            self._board.keeper[key] = {
                "emitted_at": emitted_at.isoformat(),
                "backoff_seconds": next_backoff,
                "next_eligible_at": (emitted_at + timedelta(seconds=next_backoff)).isoformat(),
            }

    def run_once(self) -> int:
        processed = 0
        context = ReactionContext(self._board, self.bead_closer, self.project_roots)
        for offset, event in self._available_events():
            if event.get("kind") == "__invalid__":
                self._board.record_error(offset, str(event.get("error", "invalid event")))
            else:
                self.registry.dispatch(event, context)
            self._board.updated_at = _now()
            self._board.save(self.board_path)
            self._cursor.save(self.cursor_path)
            processed += 1
        self._emit_keeper()
        self._board.updated_at = _now()
        self._board.save(self.board_path)
        self._cursor.save(self.cursor_path)
        return processed

    def run(self) -> None:
        while True:
            try:
                self.run_once()
            except (OSError, ReactorError) as error:
                print(f"sinnixd-reactor: {error}", file=sys.stderr, flush=True)
            time.sleep(self.interval_seconds)


def _project_root(value: str) -> tuple[str, Path]:
    name, separator, path = value.partition("=")
    if not separator or not name or not path or not Path(path).is_absolute():
        raise argparse.ArgumentTypeError("project root must be project=/absolute/path")
    return name, Path(path)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="sinnixd-reactor")
    result.add_argument("--event-spool", type=Path, default=Path("/realm/state/agentctl/events.jsonl"))
    result.add_argument("--board", type=Path, default=Path("/realm/tmp/work/campaign-board.json"))
    result.add_argument("--state-dir", type=Path, default=Path("/realm/state/sinnixd/reactor"))
    result.add_argument("--jobs-state-dir", type=Path)
    result.add_argument("--project-root", type=_project_root, action="append", default=[])
    result.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    result.add_argument("--min-active-lanes", type=int, default=3)
    result.add_argument("--keeper-backoff-seconds", type=int, default=DEFAULT_KEEPER_BACKOFF_SECONDS)
    result.add_argument("--max-keeper-backoff-seconds", type=int, default=MAX_KEEPER_BACKOFF_SECONDS)
    result.add_argument("--bd", default="bd")
    result.add_argument("--once", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    project_roots = dict(arguments.project_root)
    reactor = CampaignReactor(
        event_spool=arguments.event_spool,
        board_path=arguments.board,
        state_dir=arguments.state_dir,
        project_roots=project_roots,
        jobs_state_dir=arguments.jobs_state_dir,
        interval_seconds=arguments.interval_seconds,
        min_active_lanes=arguments.min_active_lanes,
        keeper_backoff_seconds=arguments.keeper_backoff_seconds,
        max_keeper_backoff_seconds=arguments.max_keeper_backoff_seconds,
        bead_closer=SubprocessBeadCloser(arguments.bd),
    )
    if arguments.once:
        reactor.run_once()
    else:
        reactor.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
