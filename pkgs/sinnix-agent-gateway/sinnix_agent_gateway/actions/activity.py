"""Capture lanes, normalised activity events, coding sessions, memory and timeline."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from .. import generated_polylogue_inputs as session_owner
from ..action import (
    ALL_PRINCIPALS,
    OBSERVER_OPERATOR,
    Action,
    ActionResult,
    Example,
    RequestControls,
)
from ..capabilities import Capability, PolicyError
from ..captures import CaptureLane
from ..catalog import search_rows
from ..contracts import VerbFamily
from ..results import ProtocolError
from ..schemas import GatewayModel
from .products import OwnerProduct, owner_product

if TYPE_CHECKING:
    from ..runtime import Runtime


def _owner_error(exc: ValueError) -> ProtocolError:
    message = str(exc)
    if isinstance(exc, PolicyError):
        return ProtocolError("policy_denied", message)
    if "cursor" in message and ("stale" in message or "malformed" in message):
        return ProtocolError("stale_cursor", message)
    if "source changed" in message:
        return ProtocolError("source_changed", message)
    if "unavailable" in message or "not declared" in message:
        return ProtocolError(
            "not_found" if "not declared" in message else "unavailable", message
        )
    if "does not identify" in message or "unknown" in message:
        return ProtocolError("not_found", message)
    return ProtocolError("invalid_request", message)


# ---------------------------------------------------------------- captures


class LanesOp(GatewayModel):
    operation: Literal["lanes"] = "lanes"


class LaneOp(GatewayModel):
    operation: Literal["lane"] = "lane"
    name: str = Field(min_length=1, max_length=128)


class DeltaOp(GatewayModel):
    operation: Literal["query"] = "query"
    lanes: list[str] | None = Field(
        default=None,
        max_length=64,
        description="Lane names; omitted means every visible lane.",
    )
    since: float = Field(
        default=0.0,
        ge=0,
        description="Unix seconds; counts records at or after this time.",
    )
    limit: int = Field(default=100, ge=1, le=1_000)


class CapturesInput(RequestControls):
    request: LanesOp | LaneOp | DeltaOp = Field(
        default_factory=LanesOp, discriminator="operation"
    )


class CapturesResult(GatewayModel):
    operation: Literal["lanes", "lane", "query"]
    lanes: list[dict[str, Any]] | None = None
    total_declared_lanes: int | None = None
    lane: dict[str, Any] | None = None
    records: list[dict[str, Any]] | None = Field(
        default=None,
        description="Per-lane deltas: lane, records_since, newest_ts, gap_records.",
    )
    lanes_queried: list[str] | None = None
    truncated: bool = False
    available: bool = True
    failure_class: str | None = None
    reason: str | None = None
    command: list[str] | None = None
    unavailable_lanes: list[str] | None = None
    affordances: list[str] = Field(default_factory=list)


def _captures(runtime: Runtime, inp: CapturesInput) -> CapturesResult:
    op = inp.request
    try:
        if isinstance(op, LanesOp):
            return CapturesResult(
                operation="lanes",
                **runtime.captures.lanes_visible(),
                affordances=["captures.query", "activity.query"],
            )
        if isinstance(op, LaneOp):
            return CapturesResult(
                operation="lane",
                lane=runtime.captures.lane(op.name),
                affordances=["captures.query", "activity.query"],
            )
        payload = runtime.captures.query(op.lanes, op.since, op.limit)
    except ValueError as exc:
        raise _owner_error(exc) from exc
    if payload.get("available") is False:
        return CapturesResult(
            operation="query",
            available=False,
            failure_class=payload.get("failure_class"),
            reason=payload.get("reason"),
            command=payload.get("command"),
            unavailable_lanes=payload.get("lanes"),
        )
    return CapturesResult(operation="query", **payload, affordances=["activity.query"])


# ---------------------------------------------------------------- activity


class ActivityEvent(GatewayModel):
    at: str
    ts: float
    lane: str
    lane_ref: str
    seq: int
    kind: str
    application: str | None = None
    terminal: str | None = None
    project: str | None = None
    text: str | None = None
    payload: dict[str, Any]


class ActivityInput(RequestControls):
    since: float | None = Field(
        default=None, ge=0, description="Unix seconds; default one hour ago."
    )
    until: float | None = Field(default=None, ge=0)
    kinds: list[str] = Field(
        default_factory=list,
        max_length=32,
        description="Lane names or payload event names, e.g. clipboard, notifications, heartbeat.",
    )
    project: str | None = Field(default=None, max_length=256)
    terminal: str | None = Field(
        default=None,
        max_length=256,
        description="Substring of the source window title.",
    )
    application: str | None = Field(
        default=None,
        max_length=256,
        description="Substring of the window class, app name or player.",
    )
    text: str | None = Field(
        default=None,
        max_length=512,
        description="Terms matched against the event text.",
    )
    limit: int = Field(default=200, ge=1, le=2_000)
    max_bytes_per_lane: int = Field(default=8_388_608, ge=65_536, le=134_217_728)


class LaneCoverage(GatewayModel):
    lane: str
    lane_ref: str
    available: bool
    reason: str | None = None
    files_read: int = 0
    events_seen: int = 0
    truncated: bool = False


class Activity(GatewayModel):
    since: float
    until: float
    events: list[ActivityEvent]
    returned: int
    truncated: bool
    lanes_contributed: list[str]
    lanes_unavailable: list[str]
    coverage: list[LaneCoverage]
    affordances: list[str] = Field(default_factory=list)


def _normalise(lane: str, envelope: dict[str, Any]) -> ActivityEvent | None:
    ts = envelope.get("ts")
    seq = envelope.get("seq")
    payload = envelope.get("payload")
    if (
        not isinstance(ts, (int, float))
        or not isinstance(seq, int)
        or not isinstance(payload, dict)
    ):
        return None
    window = (
        payload.get("source_window")
        if isinstance(payload.get("source_window"), dict)
        else {}
    )
    application = (
        window.get("class")
        or payload.get("app_name")
        or payload.get("player")
        or payload.get("application")
        or payload.get("window")
    )
    terminal = (
        window.get("title")
        if window.get("class") in {"kitty", "Alacritty", "foot", "wezterm"}
        else payload.get("terminal")
    )
    text = (
        payload.get("text")
        or " ".join(
            str(part) for part in (payload.get("summary"), payload.get("body")) if part
        )
        or " - ".join(
            str(part) for part in (payload.get("artist"), payload.get("title")) if part
        )
        or payload.get("message")
    )
    kind = str(payload.get("event") or payload.get("category") or lane)
    return ActivityEvent(
        at=datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        ts=float(ts),
        lane=lane,
        lane_ref=f"sinnix://captures/{lane}",
        seq=seq,
        kind=kind,
        application=str(application) if application else None,
        terminal=str(terminal) if terminal else None,
        project=str(payload.get("project")) if payload.get("project") else None,
        text=str(text)[:2_000] if text else None,
        payload=payload,
    )


def _lane_files(lane: CaptureLane, since: float, until: float) -> list[Path]:
    assert lane.native_lane is not None
    days = set()
    day = int(since // 86_400)
    while day <= int(until // 86_400):
        days.add(time.strftime("%Y%m%d", time.gmtime(day * 86_400)))
        day += 1
    return sorted(
        (
            path
            for path in lane.path.glob(f"{lane.native_lane}-*.jsonl")
            if path.name[len(lane.native_lane) + 1 : -6] in days
        ),
        reverse=True,
    )


def _activity(runtime: Runtime, inp: ActivityInput) -> Activity:
    runtime.principal.require(Capability.CAPTURE_READ)
    until = inp.until if inp.until is not None else time.time()
    since = inp.since if inp.since is not None else until - 3_600
    if since > until:
        raise ProtocolError("invalid_request", "since must not be after until")
    available = runtime.captures._available_lanes()
    visible = runtime.principal.filter_lanes(None, sorted(available))
    wanted_kinds = set(inp.kinds)
    lanes = [
        name
        for name in visible
        if not wanted_kinds
        or name in wanted_kinds
        or available[name].native_contract == "sinnix-capture-v1-sidecar"
    ]
    events: list[ActivityEvent] = []
    coverage: list[LaneCoverage] = []
    for name in lanes:
        lane = available[name]
        ref = f"sinnix://captures/{name}"
        if lane.native_contract != "sinnix-capture-v1-sidecar":
            coverage.append(
                LaneCoverage(
                    lane=name,
                    lane_ref=ref,
                    available=False,
                    reason="lane has no sinnix-capture-v1 envelope files",
                )
            )
            continue
        files = _lane_files(lane, since, until)
        seen = 0
        budget = inp.max_bytes_per_lane
        truncated = False
        for path in files:
            try:
                with path.open("rb") as handle:
                    data = handle.read(budget + 1)
            except OSError:
                continue
            if len(data) > budget:
                truncated = True
                data = data[: data.rfind(b"\n") if b"\n" in data else 0]
            budget -= len(data)
            for raw in data.splitlines():
                try:
                    envelope = json.loads(raw)
                except ValueError:
                    continue
                event = (
                    _normalise(name, envelope) if isinstance(envelope, dict) else None
                )
                if event is None or not since <= event.ts <= until:
                    continue
                seen += 1
                if (
                    wanted_kinds
                    and event.kind not in wanted_kinds
                    and name not in wanted_kinds
                ):
                    continue
                if inp.project and event.project != inp.project:
                    continue
                if (
                    inp.terminal
                    and inp.terminal.casefold() not in (event.terminal or "").casefold()
                ):
                    continue
                if (
                    inp.application
                    and inp.application.casefold()
                    not in (event.application or "").casefold()
                ):
                    continue
                events.append(event)
            if budget <= 0:
                truncated = True
                break
        coverage.append(
            LaneCoverage(
                lane=name,
                lane_ref=ref,
                available=True,
                files_read=len(files),
                events_seen=seen,
                truncated=truncated,
            )
        )
    if inp.text:
        rows = search_rows(
            [event.model_dump() for event in events],
            inp.text,
            ("text", "application", "terminal", "kind"),
        )
        selected = {(row["ts"], row["seq"], row["lane"]) for row in rows}
        events = [
            event for event in events if (event.ts, event.seq, event.lane) in selected
        ]
    events.sort(key=lambda event: (event.ts, event.seq), reverse=True)
    page = events[: inp.limit]
    return Activity(
        since=since,
        until=until,
        events=page,
        returned=len(page),
        truncated=len(events) > inp.limit or any(row.truncated for row in coverage),
        lanes_contributed=[
            row.lane for row in coverage if row.available and row.events_seen
        ],
        lanes_unavailable=[row.lane for row in coverage if not row.available],
        coverage=coverage,
        affordances=["captures.query", "sessions.query", "timeline.query"],
    )


# Session parsing, scan cursors and cross-source ordering are Polylogue products.


class SessionsInput(RequestControls):
    request: (
        session_owner.SessionList
        | session_owner.SessionSearch
        | session_owner.SessionRead
        | session_owner.RawList
        | session_owner.RawSearch
        | session_owner.RawRead
    ) = Field(discriminator="operation")


class SessionsResult(GatewayModel):
    operation: str
    owner_product: OwnerProduct
    affordances: list[str] = Field(
        default_factory=lambda: ["sessions.read", "sessions.search", "timeline.query"]
    )


async def _sessions(runtime: Runtime, inp: SessionsInput) -> ActionResult:
    runtime.principal.require(Capability.SESSION_READ)
    product = await owner_product(
        runtime,
        "polylogue",
        "query",
        {
            "projection": "session-operations",
            "session_operation": inp.request.model_dump(mode="json"),
        },
        deadline_at=inp.deadline_at,
    )
    return ActionResult(
        SessionsResult(operation=inp.request.operation, owner_product=product)
    )


class MemoryInput(RequestControls):
    request: session_owner.RawMemorySearch | session_owner.RawRead = Field(
        discriminator="operation"
    )


async def _memory(runtime: Runtime, inp: MemoryInput) -> ActionResult:
    return await _sessions(runtime, inp)


class TimelineInput(RequestControls, session_owner.SessionTimeline):
    pass


async def _timeline(runtime: Runtime, inp: TimelineInput) -> ActionResult:
    runtime.principal.require(Capability.SESSION_READ)
    product = await owner_product(
        runtime,
        "polylogue",
        "query",
        {
            "projection": "session-operations",
            "session_operation": inp.model_dump(
                mode="json", exclude=set(RequestControls.model_fields)
            ),
        },
        deadline_at=inp.deadline_at,
    )
    return ActionResult(SessionsResult(operation=inp.operation, owner_product=product))


_SESSION_EXAMPLES: dict[str, Example] = {
    "timeline.query": Example(
        title="Indexed session events in a time window",
        input={
            "origin": "codex-session",
            "since": "2026-09-01T00:00:00Z",
            "until": "2026-09-02T00:00:00Z",
            "limit": 50,
        },
    ),
    "sessions.list": Example(
        title="Recent indexed project sessions",
        input={"repo": "sinnix", "sort": "date", "limit": 20},
    ),
    "sessions.search": Example(
        title="Find sessions discussing pagination",
        input={"expression": "pagination", "repo": "sinnix", "limit": 20},
    ),
    "sessions.read": Example(
        title="Read an indexed session message page",
        input={"ref": "session:example-session", "offset": 0, "limit": 25},
    ),
    "sessions.raw.list": Example(
        title="List original Codex session sources",
        input={"origin": "codex-session", "limit": 20},
    ),
    "sessions.raw.search": Example(
        title="Search original Claude Code transcripts",
        input={
            "origin": "claude-code-session",
            "query": "pagination",
            "limit": 20,
            "scan_bytes": 1048576,
        },
    ),
    "sessions.raw.read": Example(
        title="Read a bounded original transcript page",
        input={
            "reference": "codex:2026/09/01/example-session.jsonl",
            "offset": 0,
            "max_bytes": 16000,
        },
    ),
    "sessions.raw.timeline": Example(
        title="Original sources modified in a time window",
        input={
            "origins": ["claude-code-session", "codex-session"],
            "since": "2026-09-01T00:00:00Z",
            "until": "2026-09-02T00:00:00Z",
            "limit": 20,
        },
    ),
    "memory.raw.get": Example(
        title="Read one original memory source",
        input={
            "reference": "claude-code:example-project/example-session.jsonl",
            "offset": 0,
            "max_bytes": 16000,
        },
    ),
    "memory.raw.search": Example(
        title="Find pagination notes across original sources",
        input={
            "query": "pagination",
            "origins": ["claude-code-session", "codex-session"],
            "limit": 20,
        },
    ),
    "sessions.resume": Example(
        title="Resume work in a checkout",
        input={
            "repo_path": "/realm/project/sinnix",
            "recent_files": ["README.md"],
            "related_limit": 3,
        },
    ),
}


def _session_action(name: str, model: type, summary: str) -> Action:
    """Bind one declared owner model to one discoverable action."""
    from pydantic import create_model

    selector = {
        "timeline.query": "sessions.timeline",
        "sessions.resume": "context.resume",
    }.get(name, name)
    Input = create_model(
        name.replace(".", "_") + "Input",
        __base__=(RequestControls, model),
        operation=(Literal[selector], selector),
    )
    return Action(
        name=name,
        family=VerbFamily.QUERY,
        owner="polylogue",
        summary=summary,
        Input=Input,
        Output=SessionsResult,
        handler=_timeline,
        principals=OBSERVER_OPERATOR,
        resource_kinds=(),
        affordances=("sessions.read", "sessions.search", "timeline.query"),
        examples=(_SESSION_EXAMPLES[name],),
        documentation="Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.",
    )


ACTIONS: tuple[Action, ...] = (
    Action(
        name="captures.query",
        family=VerbFamily.QUERY,
        owner="captures",
        summary="List runtime-declared capture lanes, describe one, or read per-lane record deltas since a time.",
        Input=CapturesInput,
        Output=CapturesResult,
        handler=_captures,
        principals=ALL_PRINCIPALS,
        resource_kinds=("capture_lane",),
        affordances=("activity.query", "captures.query"),
        aliases=("capture lanes", "lane health", "records since", "sidecar index"),
        examples=(
            Example(title="Visible lanes", input={}),
            Example(
                title="Deltas for two lanes",
                input={
                    "request": {
                        "operation": "query",
                        "lanes": ["clipboard", "mpris"],
                        "since": 1_700_000_000,
                    }
                },
            ),
        ),
    ),
    Action(
        name="activity.query",
        family=VerbFamily.QUERY,
        owner="captures",
        summary="Normalised activity events (clipboard, notifications, media, windows...) from the capture lanes this principal may read, newest first.",
        Input=ActivityInput,
        Output=Activity,
        handler=_activity,
        principals=ALL_PRINCIPALS,
        resource_kinds=("capture_lane",),
        affordances=("captures.query", "sessions.query", "timeline.query"),
        aliases=(
            "what was I doing",
            "recent activity",
            "clipboard history",
            "notifications",
            "now playing",
        ),
        documentation="Reads sinnix-capture-v1 envelope files under each lane path within the time window; coverage lists which lanes contributed and which have no envelope files.",
        examples=(
            Example(
                title="Last hour of clipboard and notifications",
                input={"kinds": ["clipboard", "notifications"], "limit": 50},
            ),
        ),
    ),
    Action(
        name="sessions.query",
        family=VerbFamily.QUERY,
        owner="polylogue",
        summary="Read indexed session pages or explicit original-source fallback through Polylogue.",
        Input=SessionsInput,
        Output=SessionsResult,
        handler=_sessions,
        principals=OBSERVER_OPERATOR,
        resource_kinds=(),
        affordances=("sessions.read", "sessions.search", "timeline.query"),
        examples=(
            Example(
                title="Project sessions",
                input={"request": {"operation": "sessions.list", "repo": "sinnix"}},
            ),
        ),
    ),
    Action(
        name="memory.query",
        family=VerbFamily.QUERY,
        owner="polylogue",
        summary="Search original session sources or read one source object with explicit coverage.",
        Input=MemoryInput,
        Output=SessionsResult,
        handler=_memory,
        principals=OBSERVER_OPERATOR,
        resource_kinds=(),
        affordances=("memory.raw.search", "sessions.raw.read"),
        examples=(
            Example(
                title="Search original sources",
                input={
                    "request": {
                        "operation": "memory.raw.search",
                        "query": "screenshot probe",
                    }
                },
            ),
        ),
    ),
    _session_action(
        "timeline.query",
        session_owner.SessionTimeline,
        "Read the indexed session event timeline from Polylogue.",
    ),
    _session_action(
        "sessions.list",
        session_owner.SessionList,
        "Page indexed session summaries with native archive filters.",
    ),
    _session_action(
        "sessions.search",
        session_owner.SessionSearch,
        "Search indexed sessions with native archive ranking and pagination.",
    ),
    _session_action(
        "sessions.read",
        session_owner.SessionRead,
        "Read a page of messages from one canonical session reference.",
    ),
    _session_action(
        "sessions.raw.list",
        session_owner.RawList,
        "List original session files through the archive owner's explicit fallback.",
    ),
    _session_action(
        "sessions.raw.search",
        session_owner.RawSearch,
        "Search original session transcripts with source-bound continuations.",
    ),
    _session_action(
        "sessions.raw.read",
        session_owner.RawRead,
        "Read an original session transcript byte page.",
    ),
    _session_action(
        "sessions.raw.timeline",
        session_owner.RawTimeline,
        "Read original session evidence ordered by file modification time.",
    ),
    _session_action(
        "memory.raw.get",
        session_owner.RawRead,
        "Read one original memory source object by native reference.",
    ),
    _session_action(
        "memory.raw.search",
        session_owner.RawMemorySearch,
        "Search across original session sources with independent coverage.",
    ),
    _session_action(
        "sessions.resume",
        session_owner.ResumeContext,
        "Read the archive owner's resume context for a session or checkout.",
    ),
)
