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
import re
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Protocol

from .campaign import frontier_order
from .packets import PacketConfig, SubprocessBdReader, compile_launch_snapshot

BOARD_SCHEMA_VERSION = 1
EVENT_SCHEMA_VERSION = 1
CURSOR_SCHEMA_VERSION = 1
DEFAULT_INTERVAL_SECONDS = 10
DEFAULT_KEEPER_BACKOFF_SECONDS = 600
MAX_KEEPER_BACKOFF_SECONDS = 6 * 60 * 60
MAX_BOARD_LANES = 2_000
MAX_BOARD_PRS = 2_000
MAX_BOARD_ERRORS = 100
_DURABLE_KEEPER_PREFIXES = (
    "operation:",
    "refill:",
    "retry:",
    "dispose:",
    "park:",
    "judged:",
)
MAX_EVENT_BYTES = 1_000_000
ADVANCE_DISPATCHES_PER_TICK = 3
# A dispatch record older than this names a head, receipt, or PR round that
# no longer exists; keeping it only hides the live entries on the board.
DURABLE_KEEPER_MAX_AGE_SECONDS = 3 * 24 * 60 * 60
DEFAULT_REFILL_SPACING_SECONDS = 300
MAX_REFILL_BACKOFF_SECONDS = 3600
DEFAULT_PR_AGE_THRESHOLD_SECONDS = 60 * 60
DEFAULT_VERIFY_ALL_FAILURE_THRESHOLD = 3
MAX_CORPUS_FAILURES = 32
DEFAULT_LANE_GATE_THRESHOLD = 0
MAX_PENDING_OPERATIONS = 256
HEAVY_OPERATIONS = frozenset({"verify_all", "rehearsal", "rehearsals"})


class ReactorError(ValueError):
    """An event, board, or cursor violates the reactor contract."""


def _job_id_from_output(text: str) -> str | None:
    """The job id an agentctl start printed, from JSON or a plain line."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = None
    if isinstance(value, Mapping):
        for candidate in (value.get("job_id"), (value.get("job") or {}).get("job_id") if isinstance(value.get("job"), Mapping) else None):
            if isinstance(candidate, str) and candidate:
                return candidate
    match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", text)
    return match.group(0) if match else None


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
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
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

    encoded = (
        json.dumps(dict(event), sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    if len(encoded) > MAX_EVENT_BYTES:
        raise ReactorError("event exceeds the reactor event size bound")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def event_main(argv: list[str] | None = None) -> int:
    """Append one systemd failure event for the shared campaign spool."""

    parser = argparse.ArgumentParser(prog="sinnixd-event")
    parser.add_argument("--event-spool", type=Path, required=True)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--result", default="unknown")
    arguments = parser.parse_args(argv)
    emitted_at = _now()
    event_id = hashlib.sha256(
        f"service-failure:{arguments.unit}:{arguments.result}:{emitted_at}".encode()
    ).hexdigest()[:32]
    append_event(
        arguments.event_spool,
        {
            "schema_version": EVENT_SCHEMA_VERSION,
            "event_id": event_id,
            "kind": "service_failure",
            "unit": arguments.unit,
            "result": arguments.result,
            "emitted_at": emitted_at,
        },
    )
    return 0


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
        # Lane terminals carry the checkout id as a string; older records
        # carry the resolved object. Both identify the same checkout.
        if isinstance(checkout, str) and checkout:
            checkout = {"checkout_id": checkout}
        elif checkout is not None and not isinstance(checkout, Mapping):
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
    opened_at: str | None = None
    check_states: tuple[str, ...] = ()
    auto_merge: bool = False

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
        optional = {"opened_at", "check_states", "auto_merge"}
        if set(value) - required - optional or not required <= set(value):
            raise ReactorError("board pull request record has an invalid shape")
        receipt = value["decision_receipt"]
        if receipt is not None and not isinstance(receipt, Mapping):
            raise ReactorError("board decision receipt must be an object or null")
        opened_at = value.get("opened_at")
        if opened_at is not None and (not isinstance(opened_at, str) or not opened_at):
            raise ReactorError(
                "board pull request opened_at must be a timestamp or null"
            )
        if opened_at is not None:
            _parse_time(opened_at)
        raw_checks = value.get("check_states", [])
        if not isinstance(raw_checks, list) or any(
            not isinstance(check, str) or not check for check in raw_checks
        ):
            raise ReactorError("board pull request check_states must be strings")
        auto_merge = value.get("auto_merge", False)
        if not isinstance(auto_merge, bool):
            raise ReactorError("board pull request auto_merge must be boolean")
        result = cls(
            repo=_required_string(value, "repo"),
            pr=_required_string(value, "pr"),
            state=_required_string(value, "state"),
            bead_id=_optional_string(value, "bead_id"),
            bead_close_status=_required_string(value, "bead_close_status"),
            decision_receipt=dict(receipt) if receipt is not None else None,
            error=_optional_string(value, "error"),
            updated_at=_required_string(value, "updated_at"),
            opened_at=opened_at,
            check_states=tuple(raw_checks),
            auto_merge=auto_merge,
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
                dict(self.decision_receipt)
                if self.decision_receipt is not None
                else None
            ),
            "error": self.error,
            "updated_at": self.updated_at,
            "opened_at": self.opened_at,
            "check_states": list(self.check_states),
            "auto_merge": self.auto_merge,
        }


@dataclass
class CampaignBoard:
    """Versioned external board; maps are keyed by stable event identities."""

    updated_at: str = field(default_factory=_now)
    lanes: dict[str, LaneRecord] = field(default_factory=dict)
    prs: dict[str, PullRequestRecord] = field(default_factory=dict)
    keeper: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[dict[str, str]] = field(default_factory=list)
    judgment_queue: list[dict[str, Any]] = field(default_factory=list)
    corpus_health: dict[str, Any] = field(default_factory=dict)
    pending_operations: dict[str, dict[str, Any]] = field(default_factory=dict)

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
        raw_judgment = value.get("judgment_queue", [])
        raw_corpus_health = value.get("corpus_health", {})
        raw_pending_operations = value.get("pending_operations", {})
        if not isinstance(raw_lanes, Mapping) or not isinstance(raw_prs, Mapping):
            raise ReactorError("campaign board lanes and prs must be objects")
        if not isinstance(raw_keeper, Mapping) or not isinstance(raw_errors, list):
            raise ReactorError("campaign board keeper and errors have invalid types")
        if not isinstance(raw_judgment, list):
            raise ReactorError("campaign board judgment queue must be a list")
        if not isinstance(raw_corpus_health, Mapping):
            raise ReactorError("campaign board corpus health must be an object")
        if not isinstance(raw_pending_operations, Mapping):
            raise ReactorError("campaign board pending operations must be an object")
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
                not expected <= set(record)
                or isinstance(record["backoff_seconds"], bool)
                or not isinstance(record["backoff_seconds"], int)
            ):
                raise ReactorError("campaign board keeper record is malformed")
            _parse_time(str(record["emitted_at"]))
            _parse_time(str(record["next_eligible_at"]))
            keeper[key] = dict(record)
        errors: list[dict[str, str]] = []
        for error in raw_errors[-MAX_BOARD_ERRORS:]:
            if not isinstance(error, Mapping) or set(error) != {
                "offset",
                "message",
                "at",
            }:
                raise ReactorError("campaign board error record is malformed")
            errors.append({key: str(error[key]) for key in ("offset", "message", "at")})
        pending_operations: dict[str, dict[str, Any]] = {}
        for request_id, record in raw_pending_operations.items():
            if not isinstance(request_id, str) or not isinstance(record, Mapping):
                raise ReactorError("campaign board pending operation is malformed")
            required = {
                "request_id",
                "project",
                "operation",
                "parameters",
                "requested_at",
                "last_reason",
                "active_lanes",
            }
            if set(record) != required:
                raise ReactorError("campaign board pending operation is malformed")
            if (
                record.get("request_id") != request_id
                or not isinstance(record.get("project"), str)
                or not isinstance(record.get("operation"), str)
                or not isinstance(record.get("parameters"), Mapping)
                or not isinstance(record.get("requested_at"), str)
                or not isinstance(record.get("last_reason"), str)
                or (
                    record.get("active_lanes") is not None
                    and (
                        isinstance(record.get("active_lanes"), bool)
                        or not isinstance(record.get("active_lanes"), int)
                    )
                )
            ):
                raise ReactorError("campaign board pending operation is malformed")
            _parse_time(str(record["requested_at"]))
            pending_operations[request_id] = dict(record)
        return cls(
            updated_at=value["updated_at"],
            lanes=lanes,
            prs=prs,
            keeper=keeper,
            errors=errors,
            judgment_queue=[
                dict(item) for item in raw_judgment if isinstance(item, Mapping)
            ],
            corpus_health=dict(raw_corpus_health),
            pending_operations=pending_operations,
        )

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
            "lanes": {
                key: value.to_dict() for key, value in sorted(self.lanes.items())
            },
            "prs": {key: value.to_dict() for key, value in sorted(self.prs.items())},
            "keeper": dict(sorted(self.keeper.items())),
            "errors": self.errors[-MAX_BOARD_ERRORS:],
            "judgment_queue": self.judgment_queue[-MAX_BOARD_ERRORS:],
            "corpus_health": dict(self.corpus_health),
            "pending_operations": dict(sorted(self.pending_operations.items())),
        }

    def save(self, path: Path) -> None:
        _atomic_write(path, self.to_dict())

    def record_error(self, offset: int, message: str) -> None:
        self.errors.append({"offset": str(offset), "message": message, "at": _now()})
        self.errors = self.errors[-MAX_BOARD_ERRORS:]


class ReactionHandler(Protocol):
    def __call__(
        self, event: Mapping[str, Any], context: "ReactionContext"
    ) -> None: ...


@dataclass
class ReactionContext:
    board: CampaignBoard
    bead_closer: "BeadCloser"
    project_roots: Mapping[str, Path]


class BeadCloser(Protocol):
    def close(
        self, bead_id: str, reason: str, *, cwd: Path
    ) -> tuple[bool, str | None]: ...


class RefillDispatcher(Protocol):
    def __call__(self, project: str, bead_ids: tuple[str, ...]) -> None: ...


class ReviewDispatcher(Protocol):
    def __call__(self, project: str, workspace: str) -> None: ...


class IntegrationDispatcher(Protocol):
    def __call__(self, project: str, workspace: str, receipt_ref: str) -> None: ...


class OperationDispatcher(Protocol):
    def __call__(
        self, project: str, operation: str, parameters: Mapping[str, Any]
    ) -> None: ...


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
    if (
        not isinstance(bead_id, str)
        or not bead_id
        or not isinstance(reason, str)
        or not reason
    ):
        raise ReactorError("merge decision receipt must contain bead_id and reason")
    receipt_id = raw.get("receipt_id")
    if receipt_id is not None and (not isinstance(receipt_id, str) or not receipt_id):
        raise ReactorError("merge decision receipt_id must be a non-empty string")
    return bead_id, reason, raw


def _receipts(
    event: Mapping[str, Any],
) -> tuple[tuple[str, str, Mapping[str, Any]], ...]:
    """Read either the legacy single receipt or an authored receipt set."""
    raw = event.get("decision_receipts")
    if raw is None:
        one = _receipt(event)
        return (one,) if one is not None else ()
    if not isinstance(raw, list) or not raw:
        raise ReactorError("merge decision receipts must be a non-empty list")
    result = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ReactorError("merge decision receipt must be an object")
        one = _receipt({"decision_receipt": item})
        assert one is not None
        result.append(one)
    return tuple(result)


def _merge_reaction(event: Mapping[str, Any], context: ReactionContext) -> None:
    repo = _required_string(event, "repo")
    pr = _required_string(event, "pr")
    state = _required_string(event, "state")
    key = f"{repo}#{pr}"
    prior = context.board.prs.get(key)
    receipts = _receipts(event)
    if not receipts and prior is not None and prior.decision_receipt is not None:
        receipts = _receipts({"decision_receipt": prior.decision_receipt})
    receipt_value = event.get("decision_receipt")
    receipt = (
        dict(receipt_value)
        if isinstance(receipt_value, Mapping)
        else (
            dict(prior.decision_receipt) if prior and prior.decision_receipt else None
        )
    )
    bead_id = receipts[0][0] if receipts else (prior.bead_id if prior else None)
    if bead_id is not None and (not isinstance(bead_id, str) or not bead_id):
        raise ReactorError("merge decision receipt bead_id must be a non-empty string")
    close_status = prior.bead_close_status if prior is not None else "not-attempted"
    error = prior.error if prior is not None else None
    opened_at = _optional_string(event, "opened_at") or (
        prior.opened_at if prior is not None else None
    )
    if opened_at is not None:
        _parse_time(opened_at)
    raw_checks = event.get("check_states")
    if raw_checks is None:
        check_states = prior.check_states if prior is not None else ()
    elif isinstance(raw_checks, list) and all(
        isinstance(check, str) and check for check in raw_checks
    ):
        check_states = tuple(raw_checks)
    else:
        raise ReactorError("merge event check_states must be strings")
    raw_auto_merge = event.get("auto_merge")
    if raw_auto_merge is None:
        auto_merge = prior.auto_merge if prior is not None else False
    elif isinstance(raw_auto_merge, bool):
        auto_merge = raw_auto_merge
    else:
        raise ReactorError("merge event auto_merge must be boolean")
    if state == "MERGED" and close_status not in {"closed", "missing-receipt"}:
        if receipt is None:
            close_status = "missing-receipt"
            error = "merged PR has no decision-time receipt"
        else:
            if not receipts:
                close_status = "missing-receipt"
                error = "merged PR has no decision-time receipt"
            else:
                root_name = event.get("project")
                project_name = (
                    root_name
                    if isinstance(root_name, str) and root_name
                    else _repo_name(repo)
                )
                root = context.project_roots.get(project_name)
                if root is None:
                    close_status = "failed"
                    error = f"no configured project root for {project_name}"
                else:
                    failures = []
                    for settled_bead_id, reason, _ in receipts:
                        closed, close_error = context.bead_closer.close(
                            settled_bead_id, reason, cwd=root
                        )
                        if not closed:
                            failures.append(close_error or settled_bead_id)
                    close_status = "failed" if failures else "closed"
                    error = "; ".join(failures) if failures else None
    context.board.prs[key] = PullRequestRecord(
        repo=repo,
        pr=pr,
        state=state,
        bead_id=bead_id,
        bead_close_status=close_status,
        decision_receipt=receipt,
        error=error,
        updated_at=_now(),
        opened_at=opened_at,
        check_states=check_states,
        auto_merge=auto_merge,
    )
    context.board.updated_at = _now()


def default_reactions() -> ReactionRegistry:
    registry = ReactionRegistry()
    registry.register("attested-agent", "lane-success-to-review-ready", _lane_reaction)
    registry.register("needs-merge", "record-pending-merge", _merge_reaction)
    registry.register("merge_close", "merge-to-bead-close", _merge_reaction)
    return registry


class BeadReleaser(Protocol):
    def release(self, bead_id: str, *, cwd: Path) -> tuple[bool, str | None]: ...


class SubprocessBeadReleaser:
    """Return an interrupted lane's claimed bead to the ready frontier."""

    def __init__(self, executable: str = "bd", actor: str = "sinnix-reactor") -> None:
        self.executable = executable
        self.actor = actor

    def release(self, bead_id: str, *, cwd: Path) -> tuple[bool, str | None]:
        try:
            result = subprocess.run(
                [
                    self.executable,
                    "update",
                    bead_id,
                    "-s",
                    "open",
                    "-a",
                    "",
                    # Only the campaign's own claim is released; an operator's
                    # in_progress claim on the same bead stays theirs.
                    "--if-assignee",
                    "campaign",
                    "--actor",
                    self.actor,
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
        return False, (result.stderr or result.stdout).strip()[:300]


class BeadParker(Protocol):
    def park(self, bead_id: str, note: str, *, cwd: Path) -> tuple[bool, str | None]: ...


class SubprocessBeadParker:
    """Hand a bead back to the operator with the lane's reason attached."""

    def __init__(self, executable: str = "bd", actor: str = "sinnix-reactor") -> None:
        self.executable = executable
        self.actor = actor

    def park(self, bead_id: str, note: str, *, cwd: Path) -> tuple[bool, str | None]:
        commands = [
            [
                self.executable,
                "update",
                bead_id,
                "-s",
                "open",
                "-a",
                "",
                "--if-assignee",
                "campaign",
                "--append-notes",
                note,
                "--actor",
                self.actor,
            ],
            [self.executable, "label", "add", bead_id, "needs:operator", "--actor", self.actor],
        ]
        for argv in commands:
            try:
                result = subprocess.run(
                    argv, cwd=cwd, capture_output=True, text=True, timeout=30, check=False
                )
            except (OSError, subprocess.SubprocessError) as error:
                return False, str(error)
            if result.returncode != 0:
                return False, (result.stderr or result.stdout).strip()[:300]
        return True, None


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
        if (
            not isinstance(value, Mapping)
            or value.get("schema_version") != CURSOR_SCHEMA_VERSION
        ):
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


class _ActiveLaneCount(int):
    degraded_records: int

    def __new__(cls, value: int, degraded_records: int = 0) -> "_ActiveLaneCount":
        instance = int.__new__(cls, value)
        instance.degraded_records = degraded_records
        return instance


def _active_lane_count(path: Path | None, project: str | None = None) -> int | None:
    if path is None or not path.is_dir():
        return None
    count = 0
    degraded = 0
    for record_path in path.glob("*.json"):
        try:
            record = json.loads(record_path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            degraded += 1
            continue
        if not isinstance(record, Mapping):
            degraded += 1
            continue
        spec = record.get("spec")
        state = record.get("state")
        if (
            isinstance(spec, Mapping)
            and spec.get("kind") == "attested-agent"
            and (project is None or spec.get("project_id") == project)
            and isinstance(state, Mapping)
            and not state.get("terminal", False)
        ):
            count += 1
    return _ActiveLaneCount(count, degraded)


def _judgment_reason(bead: Mapping[str, Any], snapshot: Any) -> str | None:
    metadata = bead.get("metadata", {})
    metadata = metadata if isinstance(metadata, Mapping) else {}
    if snapshot.dimensions.conflict_keys and any(
        key.startswith("schema:") for key in snapshot.dimensions.conflict_keys
    ):
        return "touches durable schema or migration"
    for marker in (
        "operator_ruling",
        "operator_ruling_marker",
        "requires_operator_ruling",
        "judgment_required",
    ):
        if metadata.get(marker):
            return f"operator ruling marker: {marker}"
    return None


@dataclass
class CampaignReactor:
    event_spool: Path
    board_path: Path
    state_dir: Path
    project_roots: Mapping[str, Path] = field(default_factory=dict)
    # Projects the reactor may DISPATCH into. Board upkeep and event
    # consumption stay estate-wide; launching work is a campaign decision,
    # and an unscoped refill once launched lanes into every registered
    # project at once (2026-09-01).
    refill_projects: tuple[str, ...] = ()
    jobs_state_dir: Path | None = None
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    min_active_lanes: int = 3
    keeper_backoff_seconds: int = DEFAULT_KEEPER_BACKOFF_SECONDS
    max_keeper_backoff_seconds: int = MAX_KEEPER_BACKOFF_SECONDS
    pr_age_threshold_seconds: int = DEFAULT_PR_AGE_THRESHOLD_SECONDS
    refill_width_target: int | None = None
    refill_spacing_seconds: int = DEFAULT_REFILL_SPACING_SECONDS
    verify_all_failure_threshold: int = DEFAULT_VERIFY_ALL_FAILURE_THRESHOLD
    refill_dispatcher: RefillDispatcher | None = None
    review_dispatcher: ReviewDispatcher | None = None
    operation_dispatcher: OperationDispatcher | None = None
    lane_gate_threshold: int = DEFAULT_LANE_GATE_THRESHOLD
    retry_dispatcher: Callable[[str], None] | None = None
    dispose_dispatcher: Callable[[str], None] | None = None
    integration_dispatcher: IntegrationDispatcher | None = None
    review_fix_dispatcher: IntegrationDispatcher | None = None
    harvest_dispatcher: IntegrationDispatcher | None = None
    verify_dispatcher: Callable[[str, str], str | None] | None = None
    _closed_beads_cache: dict[str, tuple[float, tuple[str, ...]]] = field(default_factory=dict, init=False, repr=False)
    integrator_backend: str = "codex"
    # Workers default to luna, so the integrator is a sibling rather than the
    # same model judging its own family's output.
    integrator_model: str = "gpt-5.6-terra"
    integrator_effort: str = "high"
    verify_timeout_seconds: int = 2_400
    agentctl_executable: str = "agentctl"
    bead_closer: BeadCloser = field(default_factory=SubprocessBeadCloser)
    bead_releaser: BeadReleaser = field(default_factory=SubprocessBeadReleaser)
    bead_parker: BeadParker = field(default_factory=SubprocessBeadParker)
    registry: ReactionRegistry = field(default_factory=default_reactions)

    def __post_init__(self) -> None:
        if self.interval_seconds < 1 or self.min_active_lanes < 1:
            raise ReactorError("reactor intervals and lane targets must be positive")
        if self.keeper_backoff_seconds < 1 or self.max_keeper_backoff_seconds < 1:
            raise ReactorError("keeper backoff values must be positive")
        if self.pr_age_threshold_seconds < 1:
            raise ReactorError("PR age threshold must be positive")
        if self.refill_width_target is not None and self.refill_width_target < 1:
            raise ReactorError("refill width target must be positive")
        if self.refill_spacing_seconds < 1:
            raise ReactorError("refill spacing must be positive")
        if self.lane_gate_threshold < 0:
            raise ReactorError("lane gate threshold must not be negative")
        if self.verify_all_failure_threshold < 1:
            raise ReactorError("verify_all failure threshold must be positive")
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
        if (
            self._cursor.device != stat.st_dev
            or self._cursor.inode != stat.st_ino
            or stat.st_size < self._cursor.offset
        ):
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
                    events.append(
                        (
                            offset,
                            {
                                "kind": "__invalid__",
                                "error": "event line exceeds size bound",
                            },
                        )
                    )
                    continue
                try:
                    events.append((offset, _validate_event(json.loads(line))))
                except (
                    ReactorError,
                    UnicodeDecodeError,
                    json.JSONDecodeError,
                ) as error:
                    events.append(
                        (offset, {"kind": "__invalid__", "error": str(error)})
                    )
                self._cursor.offset = handle.tell()
        return events

    def _pending_keeper_actions(self) -> list[tuple[str, str]]:
        actions: list[tuple[str, str]] = []
        for request_id, request in sorted(self._board.pending_operations.items()):
            reason = str(request["last_reason"])
            actions.append(
                (
                    f"operation:{request_id}",
                    f"defer {request['project']}:{request['operation']} ({reason})",
                )
            )
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
        needs_merge: list[str] = []
        now = datetime.now(UTC)
        for key, pr in sorted(self._board.prs.items()):
            if pr.state != "OPEN" or pr.opened_at is None:
                continue
            if (
                now - _parse_time(pr.opened_at)
            ).total_seconds() < self.pr_age_threshold_seconds:
                continue
            checks = ",".join(pr.check_states) or "none"
            merge_state = "armed" if pr.auto_merge else "unarmed"
            needs_merge.append(f"{key} checks={checks} auto-merge={merge_state}")
        if needs_merge:
            actions.append(
                ("needs-merge", "needs-merge " + "; ".join(needs_merge[:12]))
            )
        merge_pending = sorted(
            key for key, pr in self._board.prs.items() if pr.state == "NEEDS-MERGE"
        )
        if merge_pending:
            actions.append(("needs-merge", "merge " + ",".join(merge_pending[:12])))
        active = _active_lane_count(self.jobs_state_dir)
        if active is not None and active.degraded_records:
            self._board.record_error(
                -1, f"job records degraded: {active.degraded_records} unreadable"
            )
        if active is not None and self._board.lanes and active < self.min_active_lanes:
            actions.append(
                ("lanes-low", f"active lanes {active} < {self.min_active_lanes}")
            )
            # The queue replenishes itself: an under-filled fleet refills on
            # the keeper tick, not only on bead closes — most lane exits
            # (slices, rejections, timeouts) close no bead, and waiting for
            # one starved the pool at whatever the last close left behind.
            for project in self._refill_targets():
                self._dispatch_refill(project)
        return actions

    @staticmethod
    def _operation_request(event: Mapping[str, Any]) -> dict[str, Any] | None:
        kind = event.get("kind")
        requested = kind == "operation-request" or (
            kind in {"declared-operation", "operation"}
            and event.get("phase", event.get("transition")) in {"requested", "request"}
        )
        if not requested:
            return None
        request_id = _required_string(event, "request_id")
        project = _required_string(event, "project")
        operation = _required_string(event, "operation")
        parameters = event.get("parameters", {})
        if not isinstance(parameters, Mapping):
            raise ReactorError("operation request parameters must be an object")
        if operation not in HEAVY_OPERATIONS:
            return None
        requested_at = event.get("requested_at", event.get("emitted_at", _now()))
        if not isinstance(requested_at, str) or not requested_at:
            raise ReactorError("operation request requested_at must be a timestamp")
        _parse_time(requested_at)
        return {
            "request_id": request_id,
            "project": project,
            "operation": operation,
            "parameters": dict(parameters),
            "requested_at": requested_at,
            "last_reason": "awaiting lane gate evaluation",
            "active_lanes": None,
        }

    def _record_operation_request(self, event: Mapping[str, Any]) -> None:
        request = self._operation_request(event)
        if request is None:
            return
        request_id = str(request["request_id"])
        prior = self._board.pending_operations.get(request_id)
        if prior is not None:
            immutable = ("project", "operation", "parameters")
            if any(prior[field] != request[field] for field in immutable):
                raise ReactorError(f"operation request {request_id} changed")
            return
        if len(self._board.pending_operations) >= MAX_PENDING_OPERATIONS:
            raise ReactorError("campaign board pending operation limit exceeded")
        self._board.pending_operations[request_id] = request

    def _operation_gate_reason(
        self, request: Mapping[str, Any]
    ) -> tuple[str, int | None]:
        active = _active_lane_count(self.jobs_state_dir)
        if active is None:
            return "active lane count unavailable", None
        if active > self.lane_gate_threshold:
            return (
                f"active lanes {active} > gate threshold {self.lane_gate_threshold}",
                active,
            )
        return "lane gate clear", active

    def _dispatch_operation(self, request: Mapping[str, Any]) -> None:
        project = str(request["project"])
        operation = str(request["operation"])
        parameters = request["parameters"]
        if self.operation_dispatcher is not None:
            self.operation_dispatcher(project, operation, parameters)
            return
        subprocess.run(
            [
                self.agentctl_executable,
                "job",
                "start",
                project,
                operation,
                "--parameters-json",
                json.dumps(parameters, sort_keys=True, separators=(",", ":")),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def _dispatch_pending_operations(self) -> None:
        now = datetime.now(UTC)
        for request_id, request in sorted(self._board.pending_operations.items()):
            key = f"operation:{request_id}"
            prior = self._board.keeper.get(key)
            if prior is not None and now < _parse_time(str(prior["next_eligible_at"])):
                continue
            reason, active = self._operation_gate_reason(request)
            if reason != "lane gate clear":
                request["last_reason"] = reason
                request["active_lanes"] = active
                continue
            try:
                self._dispatch_operation(request)
            except (OSError, subprocess.SubprocessError) as error:
                request["last_reason"] = f"dispatch failed: {error}"
                request["active_lanes"] = active
                self._board.record_error(-1, f"operation {request_id}: {error}")
                continue
            del self._board.pending_operations[request_id]
            emitted_at = datetime.now(UTC)
            self._board.keeper[key] = {
                "emitted_at": emitted_at.isoformat(),
                "backoff_seconds": 0,
                "next_eligible_at": emitted_at.isoformat(),
            }

    def _emit_keeper(self) -> None:
        actions = self._pending_keeper_actions()
        active_keys = {key for key, _ in actions}
        # Only pending-action entries are pruned here. Prefixed entries are
        # durable records of work already dispatched; deleting one re-dispatches
        # it on the next tick.
        now = datetime.now(UTC)
        for key in list(self._board.keeper):
            if key.startswith(_DURABLE_KEEPER_PREFIXES):
                if key.startswith("refill:"):
                    continue
                emitted = self._board.keeper[key].get("emitted_at")
                try:
                    age = (now - _parse_time(str(emitted))).total_seconds()
                except (TypeError, ValueError):
                    continue
                if age > DURABLE_KEEPER_MAX_AGE_SECONDS:
                    del self._board.keeper[key]
                continue
            if key not in active_keys:
                del self._board.keeper[key]
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
            event_id = hashlib.sha256(f"{key}:{action}".encode()).hexdigest()[:32]
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
                "next_eligible_at": (
                    emitted_at + timedelta(seconds=next_backoff)
                ).isoformat(),
            }

    def _job_record(self, job_id: str) -> Mapping[str, Any] | None:
        if self.jobs_state_dir is None:
            return None
        try:
            value = json.loads((self.jobs_state_dir / f"{job_id}.json").read_text())
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, Mapping) else None

    def _workspace_for(self, record: LaneRecord) -> str:
        """The directory a lane was provisioned into, whatever the event carried.

        A lane terminal names its checkout by id, so the durable job record is
        the only place the path is recorded.
        """
        checkout = record.checkout or {}
        path = checkout.get("path")
        if not isinstance(path, str) or not path:
            if self.jobs_state_dir is None:
                return ""
            try:
                stored = json.loads(
                    (self.jobs_state_dir / f"{record.job_id}.json").read_text()
                )
            except (OSError, json.JSONDecodeError):
                return ""
            spec = stored.get("spec") if isinstance(stored, Mapping) else None
            for source in (stored, spec):
                value = source.get("checkout") if isinstance(source, Mapping) else None
                if isinstance(value, Mapping) and isinstance(value.get("path"), str):
                    path = value["path"]
                    break
        if not isinstance(path, str) or not path:
            return ""
        return PurePosixPath(path).name

    def _publish(self, project: str, workspace: str, receipt: str) -> None:
        """Publish a lane whose scan is clean, using the text the lane wrote."""
        worktree = Path("/realm/worktrees") / workspace
        parameters: dict[str, Any] = {
            "authorize": True,
            "receipt_ref": receipt.rsplit("/", 1)[-1],
        }
        title = worktree / ".lane/title"
        body = worktree / ".lane/body.md"
        if not title.is_file() or not body.is_file():
            # A lane that wrote no publication text still has a bead and a
            # receipt; the PR text is the bead's title and the lane's own
            # classification, and hosted review reads the diff.
            if not self._synthesize_lane_text(project, worktree, receipt):
                self._board.record_error(-1, f"publish {workspace}: no .lane text and no bead")
                return
        parameters["title_file"] = str(title)
        parameters["body_file"] = str(body)
        # Delivery requires a successful DECLARED verification at the exact
        # HEAD. A lane runs devtools inside its own session, which leaves a
        # local receipt but no job, so publication is refused however green the
        # lane was. Running it here as an operation is what makes the evidence
        # addressable.
        verified = subprocess.run(
            [
                self.agentctl_executable,
                "job",
                "start",
                project,
                "verify_quick",
                "--workspace",
                workspace,
            ],
            capture_output=True,
            text=True,
            timeout=self.verify_timeout_seconds,
        )
        if verified.returncode != 0:
            self._board.record_error(
                -1, f"publish {workspace}: declared verification refused"
            )
            return
        try:
            subprocess.run(
                [
                    self.agentctl_executable,
                    "job",
                    "start",
                    project,
                    "harvest",
                    "--workspace",
                    workspace,
                    "--parameters-json",
                    json.dumps(parameters, sort_keys=True),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as error:
            self._board.record_error(-1, f"publish {workspace}: {error}")
            return

    def _synthesize_lane_text(self, project: str, worktree: Path, receipt: str) -> bool:
        """Write .lane/title and .lane/body.md from the bead and receipt."""
        payload = self._receipt_payload(receipt) or {}
        bead = payload.get("bead_id")
        root = self.project_roots.get(project)
        if not isinstance(bead, str) or not bead or root is None:
            return False
        try:
            record = SubprocessBdReader(root).show(bead)
        except (OSError, subprocess.SubprocessError, ReactorError, ValueError):
            return False
        title = str(record.get("title") or "").strip()
        if not title:
            return False
        trailer = payload.get("lane_trailer")
        classification = (
            str(trailer.get("LANE-CLASSIFICATION") or "").strip()
            if isinstance(trailer, Mapping)
            else ""
        )
        body = f"Lane for {bead}: {title}\n"
        if classification:
            body += f"\n{classification}\n"
        body += f"\nPublication text synthesized from the bead and receipt; the lane wrote none.\n"
        try:
            lane_dir = worktree / ".lane"
            lane_dir.mkdir(exist_ok=True)
            (lane_dir / "title").write_text(title[:72] + "\n", encoding="utf-8")
            (lane_dir / "body.md").write_text(body, encoding="utf-8")
        except OSError:
            return False
        return True

    @staticmethod
    def _workspace_name(checkout_id: str) -> str | None:
        """Map a checkout id back to the workspace name the verbs take.

        Events carry the checkout id; `job start --workspace` and the harvest
        operation address a workspace by name.
        """
        index = Path.home() / ".local/state/sinnixd/workspaces/index.json"
        try:
            records = json.loads(index.read_text()).get("workspaces", [])
        except (OSError, json.JSONDecodeError, AttributeError):
            return None
        for record in records:
            path = record.get("path")
            name = record.get("name")
            if not isinstance(path, str) or not isinstance(name, str):
                continue
            derived = "worktree-" + hashlib.sha256(path.encode()).hexdigest()[:16]
            if derived == checkout_id:
                return name
        return None

    def _integration_prompt(
        self, root: Path, event: Mapping[str, Any], workspace: str
    ) -> str:
        contract = (
            root / "dots/_ai/skills/orchestrate/references/integrator-contract.md"
        )
        try:
            body = contract.read_text()
        except OSError:
            body = ""
        packet = event.get("packet")
        summary = (
            json.dumps(packet, indent=1, sort_keys=True)[:20_000]
            if isinstance(packet, Mapping)
            else ""
        )
        receipt = str(event.get("receipt_ref") or event.get("packet_id") or "")
        return (
            "# Integration packet\n\n"
            f"project: {event.get('project')}\n"
            f"workspace: {workspace}\n"
            f"worktree: /realm/worktrees/{workspace}\n"
            f"receipt_ref: {receipt.rsplit('/', 1)[-1]}\n\n"
            "## Review receipt\n\n"
            f"```json\n{summary}\n```\n\n"
            f"## Operating rules\n\n{body}\n"
        )

    def _launch_rebase(self, project: str, workspace: str, checkout_id: str, head: str, *, reason: str) -> None:
        """One integrator rebases the lane onto master and re-verifies."""
        refusal = (
            "rebasing onto origin/master conflicts"
            if reason == "conflict"
            else "its branch predates master's verification harness, so affected selection refuses"
        )
        prompt = (
            f"You are an integrator in /realm/worktrees/{workspace}. Publication of this "
            f"lane was refused: {refusal}. Fetch origin, rebase "
            "the branch onto origin/master, resolve every conflict preserving the lane's "
            "intent and master's, run the project's quick gate (devtools verify --quick) "
            "and affected verification (devtools verify), fix what they surface, commit, and "
            "stop. Do not publish; the harvest runs again on your commit. Report the "
            "machine trailer (LANE-BRANCH/COMMIT/QUICK/CLASSIFICATION).\n"
        )
        self._launch_agent(project, workspace, checkout_id, prompt, label="rebase", name=f"rebase-{workspace}-{head[:12]}")

    def _launch_agent(self, project: str, workspace: str, checkout_id: str, prompt: str, *, label: str, name: str) -> None:
        try:
            if self.integration_dispatcher is not None:
                self.integration_dispatcher(project, workspace, label)
                return
            prompt_path = self.state_dir / f"{name}.md"
            prompt_path.write_text(prompt, encoding="utf-8")
            subprocess.run(
                [
                    self.agentctl_executable,
                    "agent",
                    "launch",
                    "--project",
                    project,
                    "--checkout",
                    checkout_id,
                    "--prompt-file",
                    str(prompt_path),
                    "--backend",
                    self.integrator_backend,
                    "--model",
                    self.integrator_model,
                    "--effort",
                    self.integrator_effort,
                    "--coordinator-label",
                    label,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as error:
            self._board.record_error(-1, f"{label} {workspace}: {error}")

    def _park_empty_lane(self, event: Mapping[str, Any]) -> None:
        """A lane with nothing to publish hands its bead back with the reason.

        The claim would otherwise hold the bead forever; releasing it plain
        would relaunch the same blocked packet every refill. The bead goes
        back to open under needs:operator with the lane's classification.
        """
        harvest_job = event.get("job_id")
        record = self._job_record(str(harvest_job)) if isinstance(harvest_job, str) else None
        spec = record.get("spec") if isinstance(record, Mapping) else None
        checkout = spec.get("checkout") if isinstance(spec, Mapping) else None
        checkout_id = checkout.get("checkout_id") if isinstance(checkout, Mapping) else None
        project = event.get("project")
        root = self.project_roots.get(str(project)) if isinstance(project, str) else None
        if not isinstance(checkout_id, str) or root is None:
            return
        key = f"park:{checkout_id}:{str(event.get('head') or '')[:12]}"
        if key in self._board.keeper:
            return
        trailer = event.get("lane_trailer")
        classification = (
            trailer.get("LANE-CLASSIFICATION") if isinstance(trailer, Mapping) else None
        )
        note = f"lane had nothing to publish: {classification or 'no classification'}"
        for bead_id in self._campaign_beads_for_checkout(checkout_id):
            parked, detail = self.bead_parker.park(bead_id, note, cwd=root)
            if not parked:
                self._board.record_error(-1, f"park {bead_id}: {detail}")
        self._board.keeper[key] = {
            "emitted_at": _now(),
            "backoff_seconds": 0,
            "next_eligible_at": _now(),
        }

    def _campaign_beads_for_checkout(self, checkout_id: str) -> list[str]:
        """Beads of the newest campaign lane launched into a checkout."""
        if self.jobs_state_dir is None:
            return []
        best: tuple[str, list[str]] | None = None
        for path in self.jobs_state_dir.glob("*.json"):
            try:
                record = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            spec = record.get("spec") if isinstance(record, Mapping) else None
            if not isinstance(spec, Mapping) or spec.get("kind") != "attested-agent":
                continue
            checkout = spec.get("checkout")
            if not isinstance(checkout, Mapping) or checkout.get("checkout_id") != checkout_id:
                continue
            contract = spec.get("contract")
            parameters = contract.get("parameters") if isinstance(contract, Mapping) else None
            campaign = parameters.get("campaign") if isinstance(parameters, Mapping) else None
            bead_ids = campaign.get("bead_ids") if isinstance(campaign, Mapping) else None
            if not isinstance(bead_ids, list):
                continue
            created = str(record.get("created_at") or "")
            if best is None or created > best[0]:
                best = (created, [b for b in bead_ids if isinstance(b, str) and b])
        return best[1] if best else []

    def _spool(self, event: Mapping[str, Any]) -> None:
        """Append one reactor-originated event to the spool the operator tails."""
        try:
            with self.event_spool.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {"emitted_at": _now(), "schema_version": 1, **dict(event)},
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
        except OSError as error:
            self._board.record_error(-1, f"spool: {error}")

    def _reconcile_claims(self, project: str, root: Path, reader: Any) -> None:
        """Release campaign claims whose lane died while the reactor was not watching.

        A claim is released from the lane's terminal event; a reactor outage
        during a wave leaves claims parked. Each refill checks every campaign
        claim against the newest lane launched for it: cancelled, failed, or
        timed-out lanes release; running lanes and succeeded lanes awaiting
        publication keep theirs.
        """
        try:
            rows = reader.list()
        except Exception as error:  # noqa: BLE001 - one bad listing skips one reconcile
            self._board.record_error(-1, f"reconcile claims {project}: {error}")
            return
        claimed = [
            str(row["id"])
            for row in rows
            if isinstance(row, Mapping)
            and row.get("status") == "in_progress"
            and row.get("assignee") == "campaign"
            and isinstance(row.get("id"), str)
        ]
        if not claimed or self.jobs_state_dir is None:
            return
        newest: dict[str, tuple[str, str]] = {}
        for path in self.jobs_state_dir.glob("*.json"):
            try:
                record = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            spec = record.get("spec") if isinstance(record, Mapping) else None
            if not isinstance(spec, Mapping) or spec.get("kind") != "attested-agent":
                continue
            contract = spec.get("contract")
            parameters = contract.get("parameters") if isinstance(contract, Mapping) else None
            campaign = parameters.get("campaign") if isinstance(parameters, Mapping) else None
            bead_ids = campaign.get("bead_ids") if isinstance(campaign, Mapping) else None
            state = record.get("state") if isinstance(record, Mapping) else None
            phase = str(state.get("phase")) if isinstance(state, Mapping) else ""
            created = str(record.get("created_at") or "")
            for bead_id in bead_ids if isinstance(bead_ids, list) else []:
                if isinstance(bead_id, str) and (bead_id not in newest or created > newest[bead_id][0]):
                    newest[bead_id] = (created, phase)
        for bead_id in claimed:
            phase = newest.get(bead_id, ("", ""))[1]
            if phase in {"cancelled", "failed", "timeout", "launch-failed"}:
                released, detail = self.bead_releaser.release(bead_id, cwd=root)
                if not released:
                    self._board.record_error(-1, f"reconcile release {bead_id}: {detail}")

    def _release_beads(self, lane: LaneRecord) -> None:
        """An interrupted lane's claim goes back to the frontier.

        The claim exists so a succeeded lane is not relaunched while its
        result is integrated; a lane that never reached a result must not
        keep its bead parked.
        """
        record = self._job_record(lane.job_id)
        spec = record.get("spec") if isinstance(record, Mapping) else None
        contract = spec.get("contract") if isinstance(spec, Mapping) else None
        parameters = contract.get("parameters") if isinstance(contract, Mapping) else None
        campaign = parameters.get("campaign") if isinstance(parameters, Mapping) else None
        bead_ids = campaign.get("bead_ids") if isinstance(campaign, Mapping) else None
        root = self.project_roots.get(lane.project)
        if not isinstance(bead_ids, list) or root is None:
            return
        for bead_id in bead_ids:
            if not isinstance(bead_id, str) or not bead_id:
                continue
            released, detail = self.bead_releaser.release(bead_id, cwd=root)
            if not released:
                self._board.record_error(-1, f"release {bead_id}: {detail}")

    def _checkout_owned(self, checkout_id: str) -> bool:
        """Whether a running attested agent already works in this checkout.

        Two agents in one worktree edit under each other; every launch into a
        worktree defers to the agent that holds it and waits for its terminal
        event instead.
        """
        if self.jobs_state_dir is None:
            return False
        for path in self.jobs_state_dir.glob("*.json"):
            try:
                other = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            other_spec = other.get("spec") if isinstance(other, Mapping) else None
            other_state = other.get("state") if isinstance(other, Mapping) else None
            other_checkout = (
                other_spec.get("checkout") if isinstance(other_spec, Mapping) else None
            )
            if (
                isinstance(other_state, Mapping)
                and not other_state.get("terminal")
                and isinstance(other_spec, Mapping)
                and other_spec.get("kind") == "attested-agent"
                and isinstance(other_checkout, Mapping)
                and other_checkout.get("checkout_id") == checkout_id
            ):
                return True
        return False

    @classmethod
    def _receipt_workspace(cls, receipt: str) -> str | None:
        """The workspace a harvest receipt was published from."""
        return cls._receipt_field(receipt, "workspace_id")

    @classmethod
    def _receipt_field(cls, receipt: str, key: str) -> str | None:
        payload = cls._receipt_payload(receipt)
        value = payload.get(key) if payload is not None else None
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _receipt_payload(receipt: str) -> Mapping[str, Any] | None:
        """The harvest receipt a review-required event names.

        The event carries the packet id only; the receipt file holds what
        judgment reads (scan flags, lane trailer, verification evidence).
        """
        packet_root = Path.home() / ".local/state/sinnixd/harvest-packets"
        name = receipt.rsplit("/", 1)[-1]
        if not re.fullmatch(r"harvest-[0-9a-f]{32}", name):
            return None
        try:
            payload = json.loads((packet_root / f"{name}.json").read_text())
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, Mapping) else None

    def _advance_lanes(self, project: str) -> None:
        """Advance every lane of the project one step from its facts.

        No dispatch records: an action in flight shows up as a holder or a
        running operation on the next tick, and an action that already ran
        at this head shows up as an integrator job bound to it.
        """
        from .lane_facts import advance, collect, latest_sweep_pulls

        root = self.project_roots.get(project)
        if root is None or self.jobs_state_dir is None:
            return
        state_root = self.jobs_state_dir.parent
        try:
            lanes = collect(
                project,
                state_root=state_root,
                receipt_pulls=latest_sweep_pulls(state_root),
                closed_beads=self._closed_beads(project, root),
            )
        except (OSError, ValueError) as error:
            self._board.record_error(-1, f"advance {project}: {error}")
            return
        launched = 0
        for facts in lanes:
            action = advance(facts)
            if action.kind in {"verify", "harvest", "publish", "integrate", "rebase", "review-fix"}:
                # Smooth bursts: the rest of the backlog advances next tick.
                if launched >= ADVANCE_DISPATCHES_PER_TICK:
                    continue
                launched += 1
            self._dispatch_action(project, facts, action)

    def _closed_beads(self, project: str, root: Path) -> tuple[str, ...]:
        """Closed bead ids, read at most once a minute per project."""
        cached = self._closed_beads_cache.get(project)
        now = time.monotonic()
        if cached is not None and now - cached[0] < 60:
            return cached[1]
        try:
            rows = SubprocessBdReader(root).list()
        except (OSError, subprocess.SubprocessError, ReactorError, ValueError, AttributeError):
            return cached[1] if cached is not None else ()
        closed = tuple(
            str(row.get("id"))
            for row in rows
            if isinstance(row, Mapping) and row.get("status") == "closed" and row.get("id")
        )
        self._closed_beads_cache[project] = (now, closed)
        return closed

    def _dispatch_action(self, project: str, facts: Any, action: Any) -> None:
        workspace = facts.name
        checkout_id = facts.checkout_id
        try:
            if action.kind == "verify":
                if self.verify_dispatcher is not None:
                    self.verify_dispatcher(project, workspace)
                else:
                    subprocess.run(
                        [self.agentctl_executable, "job", "start", project, "verify_affected", "--workspace", workspace],
                        check=True, capture_output=True, text=True, timeout=60,
                    )
            elif action.kind == "harvest":
                verify_job = facts.verify_job[0] if facts.verify_job else ""
                if self.harvest_dispatcher is not None:
                    self.harvest_dispatcher(project, workspace, verify_job)
                else:
                    parameters = json.dumps({"affected_job": verify_job}, sort_keys=True) if verify_job else "{}"
                    subprocess.run(
                        [self.agentctl_executable, "job", "start", project, "harvest", "--workspace", workspace,
                         "--parameters-json", parameters],
                        check=True, capture_output=True, text=True, timeout=60,
                    )
            elif action.kind == "publish":
                receipt = facts.receipt.packet_id if facts.receipt else ""
                if receipt:
                    self._publish(project, workspace, receipt)
            elif action.kind == "integrate":
                packet = self._receipt_payload(facts.receipt.packet_id) if facts.receipt else None
                root = self.project_roots[project]
                event = {"project": project, "packet": packet, "receipt_ref": facts.receipt.packet_id if facts.receipt else ""}
                self._launch_agent(
                    project, workspace, checkout_id, self._integration_prompt(root, event, workspace),
                    label="integrator", name=f"integrate-{workspace}-{facts.head[:12]}",
                )
            elif action.kind == "rebase":
                self._launch_rebase(
                    project, workspace, checkout_id, facts.head,
                    reason="conflict" if facts.pull is not None else "evidence",
                )
            elif action.kind == "review-fix":
                repo = self._repo_slug(project)
                pull = facts.pull
                if repo and pull is not None:
                    self._launch_agent(
                        project, workspace, checkout_id,
                        self._review_fix_prompt(repo, str(pull.number), workspace, {"findings": pull.findings}),
                        label="review-fix", name=f"review-fix-{pull.number}-{facts.head[:12]}",
                    )
            elif action.kind == "park":
                self._record_judgment(project, facts, action.reason)
        except (OSError, subprocess.SubprocessError, KeyError) as error:
            self._board.record_error(-1, f"{action.kind} {workspace}: {error}")

    def _record_judgment(self, project: str, facts: Any, reason: str) -> None:
        key = f"judged:{facts.name}:{facts.head[:12]}"
        if key in self._board.keeper:
            return
        self._board.keeper[key] = {
            "emitted_at": _now(),
            "backoff_seconds": 0,
            "next_eligible_at": _now(),
            "reason": reason,
            "receipt": facts.receipt.packet_id if facts.receipt else None,
        }
        self._spool(
            {"kind": "judgment", "project": project, "workspace": facts.name,
             "receipt": facts.receipt.packet_id if facts.receipt else None, "reason": reason}
        )

    def _repo_slug(self, project: str) -> str:
        root = self.project_roots.get(project)
        if root is None:
            return ""
        try:
            url = subprocess.run(
                ["git", "-C", str(root), "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=10, check=False,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
        match = re.search(r"github\.com[:/]([^/]+/[^/.]+)", url)
        return match.group(1) if match else ""

    @staticmethod
    def _review_fix_prompt(
        repo: str, pr: str, workspace: str, event: Mapping[str, Any]
    ) -> str:
        return (
            f"You are a review-fix lane in /realm/worktrees/{workspace} "
            f"(open PR #{pr} on {repo}). The hosted reviewer left "
            f"{event.get('findings')} inline finding(s) on the PR. Read them with: "
            f"gh api repos/{repo}/pulls/{pr}/comments (the open ones are the "
            "top-level comments by chatgpt-codex-connector[bot] from its latest "
            "review round, newer than its last +1 reaction; earlier rounds were "
            "superseded). For each: confirm against the code and fix with a focused "
            "test, or refute with concrete evidence. Post a threaded reply on every "
            f"open finding (gh api repos/{repo}/pulls/{pr}/comments/<comment_id>/replies "
            "-f body='...'), disposition style: \"Fixed in <sha> - one line.\" or "
            "\"Refuted: <evidence>.\" with \"[review-fix lane]\" appended. Verify with "
            "the project's devtools (devtools test <selection>; devtools verify "
            "--quick); rebase onto origin/master; push the branch. Then request "
            f"re-review by commenting exactly \"@codex review\" on the PR "
            f"(gh pr comment {pr} --repo {repo} --body \"@codex review\"). Update "
            ".lane/body.md's disposition table (uncommitted). Report per-finding "
            "dispositions with the machine trailer "
            "(LANE-BRANCH/COMMIT/QUICK/CLASSIFICATION).\n"
        )

    def _dispatch_retry(self, record: LaneRecord) -> None:
        """Re-dispatch an interrupted lane once, from its preserved prompt.

        One auto-retry per ORIGINAL lane, only for interruptions (pressure,
        timeout), and never into an occupied worktree: replaying a backlog
        of cancelled events once dispatched a retry per event and piled
        twelve jobs into one checkout (2026-09-01).
        """
        key = f"retry:{record.job_id}"
        if key in self._board.keeper:
            return
        stored = self._job_record(record.job_id)
        if stored is not None:
            spec = stored.get("spec") if isinstance(stored, Mapping) else None
            contract = spec.get("contract") if isinstance(spec, Mapping) else None
            if isinstance(contract, Mapping) and contract.get("retry_of"):
                return  # already a retry: one auto-attempt per chain
            state = stored.get("state") if isinstance(stored, Mapping) else None
            cancellation = (
                state.get("cancellation") if isinstance(state, Mapping) else None
            )
            reason = (
                str(cancellation.get("reason", ""))
                if isinstance(cancellation, Mapping)
                else ""
            )
            if record.phase == "cancelled" and not reason.startswith(
                "pressure-preemption"
            ):
                # An explicit cancel is a decision, not an interruption.
                return
        checkout_id = (record.checkout or {}).get("checkout_id")
        if isinstance(checkout_id, str) and self._checkout_owned(checkout_id):
            return  # worktree already owned; no duplicate agent
        self._board.keeper[key] = {
            "emitted_at": _now(),
            "backoff_seconds": 0,
            "next_eligible_at": _now(),
        }
        try:
            if self.retry_dispatcher is not None:
                self.retry_dispatcher(record.job_id)
            else:
                subprocess.run(
                    [self.agentctl_executable, "job", "retry", record.job_id],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
        except (OSError, subprocess.SubprocessError) as error:
            self._board.record_error(-1, f"retry {record.job_id}: {error}")

    def _dispatch_dispose(self, project: str, bead_id: str) -> None:
        """Dispose the packet workspace of a closed bead.

        Packet launch names workspaces packet-<bead-id>; disposal safety
        (clean tree, published head) is enforced by the workspace owner, so
        the reactor only asks, it never forces.
        """
        workspace = f"packet-{bead_id}"
        key = f"dispose:{workspace}"
        if key in self._board.keeper:
            return
        self._board.keeper[key] = {
            "emitted_at": _now(),
            "backoff_seconds": 0,
            "next_eligible_at": _now(),
        }
        try:
            if self.dispose_dispatcher is not None:
                self.dispose_dispatcher(workspace)
            else:
                listing = subprocess.run(
                    [self.agentctl_executable, "--plain", "workspace", "list"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                target = None
                for line in listing.stdout.splitlines():
                    parts = line.split()
                    if parts and parts[0] == workspace:
                        target = parts[-1]
                        break
                if target is None:
                    return
                subprocess.run(
                    [
                        self.agentctl_executable,
                        "workspace",
                        "dispose",
                        target,
                        "--acknowledge-published",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
        except (OSError, subprocess.SubprocessError) as error:
            self._board.record_error(-1, f"dispose {workspace}: {error}")

    def _refill_targets(self) -> tuple[str, ...]:
        if self.refill_projects:
            return tuple(
                name for name in self.refill_projects if name in self.project_roots
            )
        return tuple(self.project_roots)

    def _corpus_pending(self, project: str) -> bool:
        """Whether a complete-corpus run for the project is queued or running."""
        if self.jobs_state_dir is None or not self.jobs_state_dir.is_dir():
            return False
        for path in self.jobs_state_dir.glob("*.json"):
            try:
                value = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            spec = value.get("spec") if isinstance(value, Mapping) else None
            state = value.get("state") if isinstance(value, Mapping) else None
            if (
                isinstance(spec, Mapping)
                and isinstance(state, Mapping)
                and spec.get("kind") == "declared-operation"
                and spec.get("operation") == "verify_all"
                and spec.get("project_id") == project
                and not state.get("terminal")
            ):
                return True
        return False

    def _dispatch_refill(self, project: str) -> None:
        if project not in self._refill_targets():
            return
        root = self.project_roots.get(project)
        if root is None:
            return
        if self._corpus_pending(project):
            # The corpus run is the master boundary's measurement; lanes
            # launched beside it swap the host and turn its failures into
            # load noise (76 of 626 "failures" on 2026-09-02 passed alone).
            # Running lanes finish; new ones wait for the quiet window.
            return
        target = self.refill_width_target or self.min_active_lanes
        active = _active_lane_count(self.jobs_state_dir, project)
        if active is not None and active.degraded_records:
            self._board.record_error(
                -1, f"job records degraded: {active.degraded_records} unreadable"
            )
        refill_key = f"refill:{project}"
        prior = self._board.keeper.get(refill_key)
        if prior is not None and datetime.now(UTC) < _parse_time(
            str(prior["next_eligible_at"])
        ):
            return
        if active is not None:
            target = max(0, target - active)
        if not target:
            return
        try:
            reader = SubprocessBdReader(root)
            config = PacketConfig.load(root)
            # Parked under a judgment reason that no longer exists; the
            # entries would otherwise sit on the board forever.
            self._board.judgment_queue[:] = [
                item
                for item in self._board.judgment_queue
                if item.get("reason") != "conflict metadata is incomplete"
            ]
            self._reconcile_claims(project, root, reader)
            candidates: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
            for row in sorted(reader.ready(), key=frontier_order):
                bead_id = row.get("id")
                if not isinstance(bead_id, str) or not bead_id:
                    continue
                if row.get("issue_type") in {"epic", "milestone", "decision"}:
                    # Containers coordinate work and decisions belong to the
                    # operator; a lane needs an executable leaf.
                    continue
                labels = row.get("labels")
                if isinstance(labels, list) and {
                    "needs:operator",
                    "needs:switch",
                    "horizon:vision",
                }.intersection(str(item) for item in labels):
                    continue
                try:
                    snapshot = compile_launch_snapshot(
                        bead_id,
                        project_root=root,
                        project_id=project,
                        reader=reader,
                        config=config,
                    )
                except Exception as error:
                    # One bead that cannot compile is one bead out of the
                    # pass, not a refill that aborts (parity with campaign
                    # run's uncompilable skip; an oversized packet killed
                    # every polylogue refill on 2026-09-01).
                    self._board.record_error(-1, f"refill skip {bead_id}: {error}")
                    continue
                reason = _judgment_reason(row, snapshot)
                if reason:
                    record = {
                        "project": project,
                        "group": snapshot.group,
                        "bead_ids": list(snapshot.bead_ids),
                        "reason": reason,
                        "queued_at": _now(),
                    }
                    if not any(
                        item.get("group") == snapshot.group
                        for item in self._board.judgment_queue
                    ):
                        self._board.judgment_queue.append(record)
                    continue
                candidates.append(
                    (bead_id, snapshot.bead_ids, snapshot.dimensions.conflict_keys)
                )
            selected: list[str] = []
            used: set[str] = set()
            for bead_id, _group, keys in candidates:
                if used.intersection(keys):
                    continue
                selected.append(bead_id)
                used.update(keys)
                if len(selected) >= target:
                    break
            if not selected:
                return
            if self.refill_dispatcher is not None:
                self.refill_dispatcher(project, tuple(selected))
            else:
                command = [
                    self.agentctl_executable,
                    "campaign",
                    "run",
                    "--project",
                    project,
                ]
                for bead_id in selected:
                    command.extend(("--bead", bead_id))
                # A wave provisions one worktree per bead (graph copy, venv
                # sync); on a loaded host that is minutes, not seconds.
                subprocess.run(
                    command, check=True, capture_output=True, text=True, timeout=900
                )
            emitted_at = datetime.now(UTC)
            previous = int(prior["backoff_seconds"]) if prior is not None else 0
            backoff = min(
                max(previous * 2, self.refill_spacing_seconds),
                MAX_REFILL_BACKOFF_SECONDS,
            )
            self._board.keeper[refill_key] = {
                "emitted_at": emitted_at.isoformat(),
                "backoff_seconds": backoff,
                "next_eligible_at": (
                    emitted_at + timedelta(seconds=backoff)
                ).isoformat(),
            }
            self._board.keeper.pop("lanes-low", None)
        except (OSError, subprocess.SubprocessError, ReactorError, ValueError) as error:
            self._board.record_error(-1, f"refill {project}: {error}")
            # A failed wave backs off like a launched one; retrying every
            # tick turned one bad packet into a refill attempt per minute.
            emitted_at = datetime.now(UTC)
            previous = int(prior["backoff_seconds"]) if prior is not None else 0
            backoff = min(
                max(previous * 2, self.refill_spacing_seconds),
                MAX_REFILL_BACKOFF_SECONDS,
            )
            self._board.keeper[refill_key] = {
                "emitted_at": emitted_at.isoformat(),
                "backoff_seconds": backoff,
                "next_eligible_at": (
                    emitted_at + timedelta(seconds=backoff)
                ).isoformat(),
            }

    def _verify_all_records(self) -> list[dict[str, Any]]:
        """Read terminal verify_all records in execution order."""
        if self.jobs_state_dir is None or not self.jobs_state_dir.is_dir():
            self._verify_all_degraded_records = 0
            return []
        records: list[dict[str, Any]] = []
        self._verify_all_degraded_records = 0
        for path in self.jobs_state_dir.glob("*.json"):
            try:
                value = json.loads(path.read_text())
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                self._verify_all_degraded_records += 1
                continue
            if not isinstance(value, Mapping):
                self._verify_all_degraded_records += 1
                continue
            spec = value.get("spec")
            state = value.get("state")
            if not isinstance(spec, Mapping) or not isinstance(state, Mapping):
                self._verify_all_degraded_records += 1
                continue
            if (
                spec.get("kind") != "declared-operation"
                or spec.get("project_id") != "polylogue"
                or spec.get("operation") != "verify_all"
                or not state.get("terminal")
            ):
                continue
            job_id = value.get("job_id")
            created_at = value.get("created_at")
            phase = state.get("phase")
            if not all(
                isinstance(item, str) and item for item in (job_id, created_at, phase)
            ):
                self._verify_all_degraded_records += 1
                continue
            records.append(
                {
                    "job_id": job_id,
                    "created_at": created_at,
                    "phase": phase,
                    "state": dict(state),
                }
            )
        records.sort(key=lambda item: (str(item["created_at"]), str(item["job_id"])))
        return records

    @staticmethod
    def _corpus_failure(record: Mapping[str, Any]) -> dict[str, Any] | None:
        if record.get("phase") == "succeeded":
            return None
        state = record.get("state")
        failure: dict[str, Any] = {
            "job_id": record["job_id"],
            "created_at": record["created_at"],
            "phase": record["phase"],
        }
        if isinstance(state, Mapping):
            cancellation = state.get("cancellation")
            if isinstance(cancellation, Mapping):
                failure["cancellation"] = dict(cancellation)
            error = state.get("error")
            if isinstance(error, Mapping):
                failure["error"] = dict(error)
        return failure

    def _check_verify_all_health(self) -> None:
        records = self._verify_all_records()
        failures: list[dict[str, Any]] = []
        for record in reversed(records):
            failure = self._corpus_failure(record)
            if failure is None:
                break
            failures.append(failure)
        failures.reverse()
        latest = records[-1] if records else None
        prior = self._board.corpus_health
        if not failures:
            self._board.corpus_health = {
                "operation": "verify_all",
                "threshold": self.verify_all_failure_threshold,
                "consecutive_failures": 0,
                "status": "healthy",
                "latest_job_id": latest.get("job_id") if latest else None,
                "latest_phase": latest.get("phase") if latest else None,
                "failures": [],
                "alert_event_id": None,
                "degraded_records": self._verify_all_degraded_records,
                "updated_at": _now(),
            }
            return
        alerting = len(failures) >= self.verify_all_failure_threshold
        alert_event_id = prior.get("alert_event_id") if alerting else None
        if alerting and prior.get("status") != "alerting":
            alert_event_id = hashlib.sha256(
                json.dumps(failures, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()[:32]
            append_event(
                self.event_spool,
                {
                    "schema_version": EVENT_SCHEMA_VERSION,
                    "event_id": alert_event_id,
                    "kind": "corpus-health-alert",
                    "project": "polylogue",
                    "operation": "verify_all",
                    "phase": "alerting",
                    "threshold": self.verify_all_failure_threshold,
                    "consecutive_failures": len(failures),
                    "failures": failures[-MAX_CORPUS_FAILURES:],
                    "emitted_at": _now(),
                },
            )
        self._board.corpus_health = {
            "operation": "verify_all",
            "threshold": self.verify_all_failure_threshold,
            "consecutive_failures": len(failures),
            "status": "alerting" if alerting else "degraded",
            "latest_job_id": latest["job_id"] if latest else None,
            "latest_phase": latest["phase"] if latest else None,
            "failures": failures[-MAX_CORPUS_FAILURES:],
            "alert_event_id": alert_event_id,
            "degraded_records": self._verify_all_degraded_records,
            "updated_at": _now(),
        }

    def run_once(self) -> int:
        processed = 0
        context = ReactionContext(self._board, self.bead_closer, self.project_roots)
        for offset, event in self._available_events():
            if event.get("kind") == "__invalid__":
                self._board.record_error(
                    offset, str(event.get("error", "invalid event"))
                )
            else:
                self.registry.dispatch(event, context)
                self._record_operation_request(event)
                if event.get("kind") == "attested-agent":
                    job_id = event.get("job_id")
                    lane = (
                        self._board.lanes.get(job_id)
                        if isinstance(job_id, str)
                        else None
                    )
                    if lane is not None and lane.phase == "succeeded":
                        # A real completion proves dispatch works again;
                        # collapse any accumulated refill backoff.
                        self._board.keeper.pop(f"refill:{lane.project}", None)
                    if lane is not None and lane.phase in {"cancelled", "timeout"}:
                        self._dispatch_retry(lane)
                    if lane is not None and lane.phase in {
                        "cancelled",
                        "timeout",
                        "failed",
                    }:
                        self._release_beads(lane)
                if (
                    event.get("kind") == "harvest"
                    and event.get("outcome") == "HARVEST_EMPTY"
                ):
                    self._park_empty_lane(event)
                pr = self._board.prs.get(f"{event.get('repo')}#{event.get('pr')}")
                closed = pr is not None and pr.bead_close_status == "closed"
                if event.get("kind") in {"bead_close", "merge_close"} and (
                    event.get("bead_closed") is True
                    or event.get("kind") == "bead_close"
                    or closed
                ):
                    project = event.get("project") or _repo_name(
                        str(event.get("repo", ""))
                    )
                    if isinstance(project, str) and project:
                        self._dispatch_refill(project)
                        receipt_value = event.get("decision_receipt")
                        closed_bead = (
                            receipt_value.get("bead_id")
                            if isinstance(receipt_value, Mapping)
                            else (pr.bead_id if pr is not None else None)
                        )
                        if isinstance(closed_bead, str) and closed_bead:
                            self._dispatch_dispose(project, closed_bead)
            self._board.updated_at = _now()
            self._board.save(self.board_path)
            self._cursor.save(self.cursor_path)
            processed += 1
        for project in self._refill_targets():
            self._advance_lanes(project)
        if self._board.keeper:
            self._board.updated_at = _now()
            self._board.save(self.board_path)
        self._dispatch_pending_operations()
        self._emit_keeper()
        self._check_verify_all_health()
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
    result.add_argument(
        "--event-spool", type=Path, default=Path("/realm/state/agentctl/events.jsonl")
    )
    result.add_argument(
        "--board", type=Path, default=Path("/realm/tmp/work/campaign-board.json")
    )
    result.add_argument(
        "--state-dir", type=Path, default=Path("/realm/state/sinnixd/reactor")
    )
    result.add_argument("--jobs-state-dir", type=Path)
    result.add_argument(
        "--project-root", type=_project_root, action="append", default=[]
    )
    result.add_argument("--refill-project", action="append", default=[])
    result.add_argument(
        "--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS
    )
    result.add_argument("--min-active-lanes", type=int, default=3)
    result.add_argument(
        "--lane-gate-threshold", type=int, default=DEFAULT_LANE_GATE_THRESHOLD
    )
    result.add_argument("--refill-width-target", type=int)
    result.add_argument(
        "--refill-spacing-seconds", type=int, default=DEFAULT_REFILL_SPACING_SECONDS
    )
    result.add_argument(
        "--verify-all-failure-threshold",
        type=int,
        default=DEFAULT_VERIFY_ALL_FAILURE_THRESHOLD,
    )
    result.add_argument(
        "--keeper-backoff-seconds", type=int, default=DEFAULT_KEEPER_BACKOFF_SECONDS
    )
    result.add_argument(
        "--max-keeper-backoff-seconds", type=int, default=MAX_KEEPER_BACKOFF_SECONDS
    )
    result.add_argument(
        "--pr-age-threshold-seconds",
        type=int,
        default=DEFAULT_PR_AGE_THRESHOLD_SECONDS,
    )
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
        refill_projects=tuple(arguments.refill_project),
        jobs_state_dir=arguments.jobs_state_dir,
        interval_seconds=arguments.interval_seconds,
        min_active_lanes=arguments.min_active_lanes,
        lane_gate_threshold=arguments.lane_gate_threshold,
        refill_width_target=arguments.refill_width_target,
        refill_spacing_seconds=arguments.refill_spacing_seconds,
        verify_all_failure_threshold=arguments.verify_all_failure_threshold,
        keeper_backoff_seconds=arguments.keeper_backoff_seconds,
        max_keeper_backoff_seconds=arguments.max_keeper_backoff_seconds,
        pr_age_threshold_seconds=arguments.pr_age_threshold_seconds,
        bead_closer=SubprocessBeadCloser(arguments.bd),
    )
    if arguments.once:
        reactor.run_once()
    else:
        reactor.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
