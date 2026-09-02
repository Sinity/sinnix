"""Model-free campaign reactor.

Every lane decision is computed fresh each tick by ``lane_facts.collect`` and
``advance``; the reactor dispatches the action they name.  The only state it
keeps between ticks is a small file of markers (refill backoff, parked and
judged lanes) and a rotating error log.
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
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from .campaign import frontier_order
from .packets import PacketConfig, SubprocessBdReader, compile_launch_snapshot

BOARD_SCHEMA_VERSION = 2
EVENT_SCHEMA_VERSION = 1
DEFAULT_INTERVAL_SECONDS = 10
MAX_BOARD_ERRORS = 100
MAX_BOARD_MARKERS = 2_000
MAX_EVENT_BYTES = 1_000_000
ADVANCE_DISPATCHES_PER_TICK = 3
# A marker older than this names a head, receipt, or PR round that no longer
# exists; keeping it only hides the live entries.
MARKER_MAX_AGE_SECONDS = 3 * 24 * 60 * 60
DEFAULT_REFILL_SPACING_SECONDS = 300
MAX_REFILL_BACKOFF_SECONDS = 3600


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


@dataclass
class CampaignBoard:
    """The reactor's own small state: dispatch markers and recent errors.

    Markers are idempotence keys for work already done at a head (a parked
    bead, a recorded judgment, a refill's backoff); deleting one re-dispatches
    it. Errors are a rotating log the status view reads.
    """

    updated_at: str = field(default_factory=_now)
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
        updated_at = value.get("updated_at")
        if not isinstance(updated_at, str):
            raise ReactorError("campaign board updated_at is invalid")
        _parse_time(updated_at)
        raw_keeper = value.get("keeper", {})
        raw_errors = value.get("errors", [])
        if not isinstance(raw_keeper, Mapping) or not isinstance(raw_errors, list):
            raise ReactorError("campaign board keeper and errors have invalid types")
        keeper: dict[str, dict[str, Any]] = {}
        for key, record in raw_keeper.items():
            if not isinstance(key, str) or not isinstance(record, Mapping):
                raise ReactorError("campaign board marker is malformed")
            _parse_time(str(record.get("emitted_at")))
            keeper[key] = dict(record)
        errors: list[dict[str, str]] = []
        for error_record in raw_errors[-MAX_BOARD_ERRORS:]:
            if not isinstance(error_record, Mapping) or set(error_record) != {
                "offset",
                "message",
                "at",
            }:
                raise ReactorError("campaign board error record is malformed")
            errors.append(
                {key: str(error_record[key]) for key in ("offset", "message", "at")}
            )
        return cls(updated_at=updated_at, keeper=keeper, errors=errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": BOARD_SCHEMA_VERSION,
            "updated_at": self.updated_at,
            "keeper": dict(sorted(self.keeper.items())),
            "errors": self.errors[-MAX_BOARD_ERRORS:],
        }

    def save(self, path: Path) -> None:
        _atomic_write(path, self.to_dict())

    def record_error(self, offset: int, message: str) -> None:
        self.errors.append({"offset": str(offset), "message": message, "at": _now()})
        self.errors = self.errors[-MAX_BOARD_ERRORS:]

    def expire_markers(self, now: datetime) -> None:
        """Drop markers whose head, receipt, or PR round is long gone."""
        for key in list(self.keeper):
            if key.startswith("refill:"):
                continue
            try:
                age = (now - _parse_time(str(self.keeper[key].get("emitted_at")))).total_seconds()
            except (TypeError, ReactorError):
                continue
            if age > MARKER_MAX_AGE_SECONDS:
                del self.keeper[key]
        if len(self.keeper) > MAX_BOARD_MARKERS:
            oldest = sorted(
                self.keeper, key=lambda key: str(self.keeper[key].get("emitted_at"))
            )
            for key in oldest[: len(self.keeper) - MAX_BOARD_MARKERS]:
                del self.keeper[key]


class RefillDispatcher(Protocol):
    def __call__(self, project: str, bead_ids: tuple[str, ...]) -> None: ...


class IntegrationDispatcher(Protocol):
    def __call__(self, project: str, workspace: str, receipt_ref: str) -> None: ...


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


def _harvest_outcome(record: Mapping[str, Any]) -> Mapping[str, Any]:
    """The result payload a terminal harvest job wrote, or an empty mapping."""
    artifacts = record.get("artifacts")
    path = artifacts.get("result") if isinstance(artifacts, Mapping) else None
    if not isinstance(path, str):
        return {}
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(value, Mapping) and isinstance(value.get("value"), Mapping):
        value = value["value"]
    return value if isinstance(value, Mapping) else {}


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
    refill_width_target: int | None = None
    refill_spacing_seconds: int = DEFAULT_REFILL_SPACING_SECONDS
    refill_dispatcher: RefillDispatcher | None = None
    retry_dispatcher: Callable[[str], None] | None = None
    integration_dispatcher: IntegrationDispatcher | None = None
    review_fix_dispatcher: IntegrationDispatcher | None = None
    harvest_dispatcher: IntegrationDispatcher | None = None
    verify_dispatcher: Callable[[str, str], str | None] | None = None
    integrator_backend: str = "codex"
    # Workers default to luna, so the integrator is a sibling rather than the
    # same model judging its own family's output.
    integrator_model: str = "gpt-5.6-terra"
    integrator_effort: str = "high"
    agentctl_executable: str = "agentctl"
    bead_releaser: BeadReleaser = field(default_factory=SubprocessBeadReleaser)
    bead_parker: BeadParker = field(default_factory=SubprocessBeadParker)

    def __post_init__(self) -> None:
        if self.interval_seconds < 1 or self.min_active_lanes < 1:
            raise ReactorError("reactor intervals and lane targets must be positive")
        if self.refill_width_target is not None and self.refill_width_target < 1:
            raise ReactorError("refill width target must be positive")
        if self.refill_spacing_seconds < 1:
            raise ReactorError("refill spacing must be positive")
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._board = CampaignBoard.load(self.board_path)

    def _job_record(self, job_id: str) -> Mapping[str, Any] | None:
        if self.jobs_state_dir is None:
            return None
        try:
            value = json.loads((self.jobs_state_dir / f"{job_id}.json").read_text())
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, Mapping) else None

    def _publish(self, project: str, workspace: str, receipt: str, affected_job: str = "") -> None:
        """Publish a lane whose scan is clean, using the text the lane wrote."""
        worktree = Path("/realm/worktrees") / workspace
        parameters: dict[str, Any] = {
            "authorize": True,
            "receipt_ref": receipt.rsplit("/", 1)[-1],
        }
        if affected_job:
            parameters["affected_job"] = affected_job
        title = worktree / ".lane/title"
        body = worktree / ".lane/body.md"
        if not title.is_file() or not body.is_file():
            # The worker contract requires the lane to write its own
            # publication text; a lane that skipped it is parked, not
            # published under text nobody wrote.
            self._board.record_error(-1, f"publish {workspace}: no .lane publication text")
            return
        parameters["title_file"] = str(title)
        parameters["body_file"] = str(body)
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
            f"receipt_ref: {receipt.rsplit('/', 1)[-1]}\n"
            f"affected_job: {event.get('affected_job') or ''}\n\n"
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

    def _park_empty_lanes(self, project: str) -> None:
        """A lane with nothing to publish hands its bead back with the reason.

        The claim would otherwise hold the bead forever; releasing it plain
        would relaunch the same blocked packet every refill. The bead goes
        back to open under needs:operator with the lane's classification.
        """
        root = self.project_roots.get(project)
        if root is None or self.jobs_state_dir is None:
            return
        for path in sorted(self.jobs_state_dir.glob("*.json")):
            try:
                record = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            spec = record.get("spec") if isinstance(record, Mapping) else None
            state = record.get("state") if isinstance(record, Mapping) else None
            if (
                not isinstance(spec, Mapping)
                or spec.get("operation") != "harvest"
                or spec.get("project_id") != project
                or not isinstance(state, Mapping)
                or not state.get("terminal")
            ):
                continue
            outcome = _harvest_outcome(record)
            if outcome.get("outcome") != "HARVEST_EMPTY":
                continue
            checkout = spec.get("checkout")
            checkout_id = (
                checkout.get("checkout_id") if isinstance(checkout, Mapping) else None
            )
            if not isinstance(checkout_id, str):
                continue
            key = f"park:{checkout_id}:{str(outcome.get('head') or '')[:12]}"
            if key in self._board.keeper:
                continue
            trailer = outcome.get("lane_trailer")
            classification = (
                trailer.get("LANE-CLASSIFICATION") if isinstance(trailer, Mapping) else None
            )
            note = f"lane had nothing to publish: {classification or 'no classification'}"
            for bead_id in self._campaign_beads_for_checkout(checkout_id):
                parked, detail = self.bead_parker.park(bead_id, note, cwd=root)
                if not parked:
                    self._board.record_error(-1, f"park {bead_id}: {detail}")
            self._board.keeper[key] = {"emitted_at": _now()}

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
        """Closed bead ids; the facts module owns the cache and refresh."""
        from .lane_facts import closed_bead_ids

        closed = closed_bead_ids(root)
        if not closed:
            self._board.record_error(-1, f"closed beads {project}: bd answered nothing")
        return closed

    def _dispatch_action(self, project: str, facts: Any, action: Any) -> None:
        workspace = facts.name
        checkout_id = facts.checkout_id
        if action.kind in {"verify", "harvest", "publish", "integrate", "rebase", "review-fix", "retry"}:
            self._spool({"kind": "dispatch", "project": project, "workspace": workspace,
                         "head": facts.head[:12], "action": action.kind, "reason": action.reason})
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
                    verified = facts.verify_job[0] if facts.verify_job and facts.verify_job[1] == "succeeded" else ""
                    self._publish(project, workspace, receipt, verified)
            elif action.kind == "integrate":
                packet = self._receipt_payload(facts.receipt.packet_id) if facts.receipt else None
                root = self.project_roots[project]
                verified = facts.verify_job[0] if facts.verify_job and facts.verify_job[1] == "succeeded" else ""
                event = {"project": project, "packet": packet, "receipt_ref": facts.receipt.packet_id if facts.receipt else "", "affected_job": verified}
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
            elif action.kind == "retry":
                self._dispatch_retry(facts)
            elif action.kind == "park":
                self._record_judgment(project, facts, action.reason)
        except (OSError, subprocess.SubprocessError, KeyError) as error:
            self._board.record_error(-1, f"{action.kind} {workspace}: {error}")

    def _dispatch_retry(self, facts: Any) -> None:
        """Re-dispatch an interrupted lane once, from its own job record.

        One auto-retry per lane job: the retry keeps the checkout, so a second
        attempt at the same dead job would pile agents into one worktree.
        """
        job_id = facts.lane_job
        if not job_id:
            return
        key = f"retry:{job_id}"
        if key in self._board.keeper:
            return
        self._board.keeper[key] = {"emitted_at": _now()}
        if self.retry_dispatcher is not None:
            self.retry_dispatcher(job_id)
            return
        subprocess.run(
            [self.agentctl_executable, "job", "retry", job_id],
            check=True, capture_output=True, text=True, timeout=60,
        )

    def _record_judgment(self, project: str, facts: Any, reason: str) -> None:
        key = f"judged:{facts.name}:{facts.head[:12]}"
        if key in self._board.keeper:
            return
        self._board.keeper[key] = {
            "emitted_at": _now(),
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
                    # The operator decides this one; a lane must not.
                    self._board.record_error(-1, f"refill judgment {bead_id}: {reason}")
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

    def run_once(self) -> int:
        """Advance, park, and refill every campaign project once."""
        for project in self._refill_targets():
            self._advance_lanes(project)
            self._park_empty_lanes(project)
            self._dispatch_refill(project)
        self._board.expire_markers(datetime.now(UTC))
        self._board.updated_at = _now()
        self._board.save(self.board_path)
        return len(self._refill_targets())

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
    result.add_argument("--refill-width-target", type=int)
    result.add_argument(
        "--refill-spacing-seconds", type=int, default=DEFAULT_REFILL_SPACING_SECONDS
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
        refill_width_target=arguments.refill_width_target,
        refill_spacing_seconds=arguments.refill_spacing_seconds,
        bead_releaser=SubprocessBeadReleaser(arguments.bd),
        bead_parker=SubprocessBeadParker(arguments.bd),
    )
    if arguments.once:
        reactor.run_once()
    else:
        reactor.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
