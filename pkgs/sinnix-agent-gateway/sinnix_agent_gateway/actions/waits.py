"""Bounded waits on owner facts and the normalized event stream.

``wait.for`` polls one owner until a condition holds or the deadline passes;
it never starts work. ``events.tail`` reads the normalized event stream with
an opaque, scope-bound cursor.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import anyio
from pydantic import Field

from ..action import ALL_PRINCIPALS, Action, Example, RequestControls
from ..capabilities import Capability
from ..contexts import source_revision
from ..contracts import VerbFamily
from ..locators import (
    BeadLocator,
    FileLocator,
    JobLocator,
    ProjectLocator,
    project_ref,
)
from ..results import ProtocolError
from ..schemas import GatewayModel
from .jobs import JobView, _job_view

if TYPE_CHECKING:
    from ..runtime import Runtime


# ------------------------------------------------------------ conditions


class JobTerminal(GatewayModel):
    kind: Literal["job_terminal"] = "job_terminal"
    target: JobLocator


class BeadStatus(GatewayModel):
    kind: Literal["bead_status"] = "bead_status"
    bead: BeadLocator
    status: str = Field(
        min_length=1, max_length=64, description="e.g. open, in_progress, closed"
    )


class BeadRevision(GatewayModel):
    kind: Literal["bead_revision"] = "bead_revision"
    bead: BeadLocator
    revision: str = Field(
        min_length=1, max_length=256, description="task_revision to wait for."
    )


class UnitState(GatewayModel):
    kind: Literal["unit_state"] = "unit_state"
    unit: str = Field(
        min_length=1,
        max_length=256,
        description="systemd unit name, e.g. pueued.service",
    )
    manager: Literal["system", "user"] = "system"
    state: str = Field(
        min_length=1,
        max_length=32,
        description="active, inactive, failed, activating, ...",
    )


class FileHash(GatewayModel):
    kind: Literal["file_hash"] = "file_hash"
    target: FileLocator
    sha256: str = Field(pattern="^[0-9a-f]{64}$")


class FileExists(GatewayModel):
    kind: Literal["file_exists"] = "file_exists"
    target: FileLocator
    exists: bool = Field(
        default=True, description="False waits for the path to disappear."
    )


class CaptureFreshness(GatewayModel):
    kind: Literal["capture_freshness"] = "capture_freshness"
    lane: str = Field(min_length=1, max_length=128, description="Capture lane name.")
    max_age_seconds: float = Field(gt=0, le=86_400)


class ReceiptAppearance(GatewayModel):
    kind: Literal["receipt_appearance"] = "receipt_appearance"
    receipt_id: str = Field(min_length=1, max_length=256)


class TerminalOutput(GatewayModel):
    kind: Literal["terminal_output"] = "terminal_output"
    match: str = Field(
        min_length=1,
        max_length=512,
        description="kitty window match, e.g. id:3 or title:build",
    )
    pattern: str = Field(
        min_length=1, max_length=512, description="Regex searched in the captured text."
    )
    extent: Literal["last_cmd_output", "screen", "all"] = "screen"


Condition = (
    JobTerminal
    | BeadStatus
    | BeadRevision
    | UnitState
    | FileHash
    | FileExists
    | CaptureFreshness
    | ReceiptAppearance
    | TerminalOutput
)


class WaitInput(RequestControls):
    condition: Condition = Field(discriminator="kind")
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    poll_seconds: float = Field(default=0.25, ge=0.01, le=5)


class WaitResult(GatewayModel):
    kind: str
    ref: str = Field(description="Canonical ref of the waited resource.")
    outcome: Literal["satisfied", "timeout", "cancelled"]
    timed_out: bool
    polls: int = 0
    evidence: dict[str, Any] = Field(default_factory=dict)
    source_revision: str | None = None
    continuation: str | None = Field(
        default=None,
        description="Stable token for the unsatisfied state; None once satisfied.",
    )
    job: JobView | None = Field(default=None, description="Set for job_terminal.")
    affordances: list[str] = Field(default_factory=list)


def _legacy_target(
    runtime: Runtime, condition: Condition
) -> tuple[str, dict[str, Any]]:
    """``(ref, expected)`` for the conditions the runtime's wait resolver knows."""
    if isinstance(condition, JobTerminal):
        return condition.target.resolve()[1], {}
    if isinstance(condition, (BeadStatus, BeadRevision)):
        _, _, ref = condition.bead.resolve(runtime)
        if isinstance(condition, BeadStatus):
            return ref, {"status": condition.status}
        return ref, {"revision": condition.revision}
    if isinstance(condition, UnitState):
        return (
            f"sinnix://machine/units/{condition.manager}/{condition.unit}",
            {"state": condition.state},
        )
    if isinstance(condition, FileHash):
        return condition.target.resolve()[1], {"sha256": condition.sha256}
    if isinstance(condition, CaptureFreshness):
        return f"sinnix://captures/{condition.lane}", {
            "max_age_seconds": condition.max_age_seconds
        }
    assert isinstance(condition, ReceiptAppearance)
    return f"sinnix://receipts/{condition.receipt_id}", {}


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def _probe(
    runtime: Runtime, condition: FileExists | TerminalOutput
) -> tuple[bool, dict[str, Any], str]:
    if isinstance(condition, FileExists):
        runtime.principal.require(Capability.FILE_READ)
        path, _ = condition.target.resolve()
        present = Path(path).exists()
        return (
            present == condition.exists,
            {"path": path, "exists": present},
            source_revision({"path": path, "exists": present}),
        )
    capture = runtime.terminals.read(
        "capture", {"match": condition.match, "extent": condition.extent}
    )
    text = "\n".join(_strings(capture))
    found = re.search(condition.pattern, text)
    evidence = {
        "matched": found is not None,
        "excerpt": text[max(0, found.start() - 200) : found.end() + 200]
        if found
        else text[-800:],
    }
    return found is not None, evidence, source_revision(text)


async def _poll(runtime: Runtime, inp: WaitInput, ref: str) -> WaitResult:
    """A local bounded poll for conditions the runtime's resolver does not cover."""
    condition = inp.condition
    assert isinstance(condition, (FileExists, TerminalOutput))
    deadline = time.monotonic() + inp.timeout_seconds
    polls = 0
    while True:
        satisfied, evidence, revision = await anyio.to_thread.run_sync(
            lambda: _probe(runtime, condition), abandon_on_cancel=True
        )
        if satisfied:
            return WaitResult(
                kind=condition.kind,
                ref=ref,
                outcome="satisfied",
                timed_out=False,
                polls=polls,
                evidence=evidence,
                source_revision=revision,
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return WaitResult(
                kind=condition.kind,
                ref=ref,
                outcome="timeout",
                timed_out=True,
                polls=polls,
                evidence=evidence,
                source_revision=revision,
                continuation=source_revision({"ref": ref, "revision": revision}),
                affordances=["wait.for"],
            )
        await anyio.sleep(min(inp.poll_seconds, remaining))
        polls += 1


async def _wait_for(runtime: Runtime, inp: WaitInput) -> WaitResult:
    condition = inp.condition
    if isinstance(condition, FileExists):
        return await _poll(runtime, inp, condition.target.resolve()[1])
    if isinstance(condition, TerminalOutput):
        return await _poll(runtime, inp, f"sinnix://terminals/{condition.match}")
    ref, expected = _legacy_target(runtime, condition)
    raw = await runtime.v2_wait_async(
        ref, inp.timeout_seconds, condition.kind, expected, inp.poll_seconds
    )
    if isinstance(condition, JobTerminal) and "outcome" not in raw:
        view = _job_view(raw)
        timed_out = bool(raw.get("timed_out"))
        return WaitResult(
            kind=condition.kind,
            ref=ref,
            outcome="timeout" if timed_out else "satisfied",
            timed_out=timed_out,
            evidence=view.state.model_dump(),
            source_revision=source_revision(view.state.model_dump()),
            continuation=source_revision({"ref": ref, "state": view.state.model_dump()})
            if timed_out
            else None,
            job=view,
            affordances=["jobs.get", "jobs.logs"]
            if not timed_out
            else ["wait.for", "jobs.cancel"],
        )
    outcome = str(raw.get("outcome") or "satisfied")
    if outcome not in {"satisfied", "timeout", "cancelled"}:
        raise ProtocolError("owner_failed", f"wait owner reported outcome {outcome!r}")
    evidence = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}
    job = None
    if isinstance(condition, JobTerminal) and "job_id" in raw:
        job = _job_view(raw)
    return WaitResult(
        kind=condition.kind,
        ref=str(raw.get("ref") or ref),
        outcome=outcome,  # type: ignore[arg-type]
        timed_out=outcome == "timeout",
        polls=int(raw.get("polls") or 0),
        evidence=evidence,
        source_revision=raw.get("source_revision"),
        continuation=raw.get("continuation"),
        job=job,
        affordances=["wait.for"] if outcome != "satisfied" else [],
    )


# ---------------------------------------------------------------- events


class EventsInput(RequestControls):
    limit: int = Field(default=100, ge=1, le=1_000)
    cursor: str | None = Field(
        default=None,
        min_length=1,
        max_length=4_096,
        description="next_cursor from the previous page.",
    )
    projects: list[ProjectLocator] | None = Field(
        default=None,
        max_length=16,
        description="Scope; defaults to every configured project.",
    )


class EventPage(GatewayModel):
    event_schema: str | None = None
    principal: str
    events: list[dict[str, Any]]
    sources: dict[str, Any] = Field(default_factory=dict)
    next_cursor: str
    truncated: bool
    project_refs: list[str] = Field(default_factory=list)
    affordances: list[str] = Field(default_factory=list)


def _events(runtime: Runtime, inp: EventsInput) -> EventPage:
    runtime.principal.require(Capability.AUDIT_READ)
    project_ids = (
        sorted({locator.resolve(runtime) for locator in inp.projects})
        if inp.projects
        else None
    )
    page = runtime.v2_events(inp.limit, inp.cursor, project_ids)
    return EventPage(
        event_schema=page.get("schema"),
        principal=str(page.get("principal") or runtime.principal.name),
        events=[dict(row) for row in page.get("events") or []],
        sources=dict(page.get("sources") or {}),
        next_cursor=str(page["next_cursor"]),
        truncated=bool(page.get("truncated")),
        project_refs=[
            project_ref(p) for p in (project_ids or sorted(runtime.config.projects))
        ],
        affordances=["events.tail"],
    )


ACTIONS: tuple[Action, ...] = (
    Action(
        name="wait.for",
        family=VerbFamily.WAIT,
        owner="waits",
        summary="Poll one owner fact until it holds or the bounded timeout passes; never starts work.",
        Input=WaitInput,
        Output=WaitResult,
        handler=_wait_for,
        principals=ALL_PRINCIPALS,
        resource_kinds=(
            "job",
            "bead",
            "machine_unit",
            "host_file",
            "capture_lane",
            "receipt",
            "terminal",
        ),
        affordances=("jobs.get", "jobs.logs", "jobs.cancel", "events.tail"),
        aliases=("wait until", "block until", "poll", "watch for"),
        documentation="Conditions: job_terminal, bead_status, bead_revision, unit_state, file_hash, file_exists, capture_freshness, receipt_appearance, terminal_output. A timeout returns the current evidence and a continuation token.",
        examples=(
            Example(
                title="Wait for a job",
                input={
                    "condition": {"kind": "job_terminal", "target": {"job_id": 41}},
                    "timeout_seconds": 120,
                },
            ),
            Example(
                title="Wait for a bead to close",
                input={
                    "condition": {
                        "kind": "bead_status",
                        "bead": {"id": "sinnix-abc1"},
                        "status": "closed",
                    }
                },
            ),
            Example(
                title="Wait for a file to appear",
                input={
                    "condition": {
                        "kind": "file_exists",
                        "target": {"path": "/realm/tmp/work/out.png"},
                    }
                },
            ),
            Example(
                title="Wait for a unit to be active",
                input={
                    "condition": {
                        "kind": "unit_state",
                        "unit": "pueued.service",
                        "manager": "user",
                        "state": "active",
                    }
                },
            ),
        ),
    ),
    Action(
        name="events.tail",
        family=VerbFamily.EVENTS,
        owner="events",
        summary="Read normalized gateway, git, beads, job and runtime events with a resumable cursor.",
        Input=EventsInput,
        Output=EventPage,
        handler=_events,
        principals=ALL_PRINCIPALS,
        resource_kinds=("receipt", "project", "job"),
        affordances=("wait.for", "jobs.get", "events.tail"),
        aliases=("what happened", "recent activity", "audit log", "changes since"),
        documentation="Pass next_cursor back to continue; a cursor from another principal or project scope fails stale_cursor.",
        examples=(
            Example(title="Latest events", input={"limit": 50}),
            Example(
                title="One project",
                input={"projects": [{"project": "sinnix"}], "limit": 100},
            ),
        ),
    ),
)
