"""Capture lanes, normalised activity events, coding sessions, memory and timeline."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from ..action import ALL_PRINCIPALS, OBSERVER_OPERATOR, Action, Example, RequestControls
from ..capabilities import Capability, PolicyError
from ..captures import CaptureLane
from ..catalog import search_rows
from ..contracts import VerbFamily
from ..memory import MemoryError
from ..results import ProtocolError
from ..schemas import GatewayModel
from ..sessions import SessionError
from ..timeline import TimelineError

if TYPE_CHECKING:
    from ..runtime import Runtime

Provider = Literal["claude-code", "codex"]
MemorySource = Literal["claude-code", "codex", "polylogue", "sinex", "lynchpin"]


def _owner_error(exc: ValueError) -> ProtocolError:
    message = str(exc)
    if isinstance(exc, PolicyError):
        return ProtocolError("policy_denied", message)
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


# ---------------------------------------------------------------- sessions


class SessionsListOp(GatewayModel):
    operation: Literal["list"] = "list"
    provider: Provider
    limit: int = Field(default=100, ge=1, le=500)


class SessionsReadOp(GatewayModel):
    operation: Literal["read"] = "read"
    reference: str = Field(
        min_length=1,
        max_length=8_192,
        description="provider:relative/path.jsonl from a list or search row.",
    )
    offset: int = Field(default=0, ge=0)
    max_bytes: int = Field(default=64_000, ge=1, le=262_144)


class SessionsSearchOp(GatewayModel):
    operation: Literal["search"] = "search"
    provider: Provider
    query: str = Field(min_length=1, max_length=1_000)
    max_results: int = Field(default=100, ge=1, le=500)


class SessionsInput(RequestControls):
    request: SessionsListOp | SessionsReadOp | SessionsSearchOp = Field(
        discriminator="operation"
    )


class SessionsResult(GatewayModel):
    operation: Literal["list", "read", "search"]
    provider: str
    sessions: list[dict[str, Any]] | None = None
    matches: list[dict[str, Any]] | None = None
    reference: str | None = None
    offset: int | None = None
    bytes: int | None = None
    content: str | None = None
    scanned_bytes: int | None = None
    truncated: bool
    affordances: list[str] = Field(default_factory=list)


def _sessions(runtime: Runtime, inp: SessionsInput) -> SessionsResult:
    op = inp.request
    try:
        if isinstance(op, SessionsListOp):
            payload = runtime.sessions.list(op.provider, op.limit)
        elif isinstance(op, SessionsReadOp):
            payload = runtime.sessions.read(op.reference, op.offset, op.max_bytes)
        else:
            payload = runtime.sessions.search(op.provider, op.query, op.max_results)
    except (SessionError, PolicyError) as exc:
        raise _owner_error(exc) from exc
    return SessionsResult(
        operation=op.operation,
        **payload,
        affordances=["sessions.query", "memory.query", "timeline.query"],
    )


# ------------------------------------------------------------------ memory


class MemorySearchOp(GatewayModel):
    operation: Literal["search"] = "search"
    query: str = Field(min_length=1, max_length=1_000)
    providers: list[MemorySource] | None = Field(default=None, min_length=1)
    limit: int = Field(default=100, ge=1, le=500)


class MemoryGetOp(GatewayModel):
    operation: Literal["get"] = "get"
    reference: str = Field(min_length=1, max_length=8_192)
    offset: int = Field(default=0, ge=0)
    max_bytes: int = Field(default=64_000, ge=1, le=262_144)


class MemoryInput(RequestControls):
    request: MemorySearchOp | MemoryGetOp = Field(discriminator="operation")


class MemoryResult(GatewayModel):
    operation: Literal["search", "get"]
    query: str | None = None
    sources: list[dict[str, Any]] | None = None
    matches: list[dict[str, Any]] | None = None
    source: str | None = None
    authority: str | None = None
    availability: str | None = None
    object_reference: str | None = None
    offset: int | None = None
    bytes: int | None = None
    content: str | None = None
    truncated: bool
    affordances: list[str] = Field(default_factory=list)


def _memory(runtime: Runtime, inp: MemoryInput) -> MemoryResult:
    op = inp.request
    try:
        if isinstance(op, MemorySearchOp):
            payload = runtime.memory.search(
                op.query, list(op.providers) if op.providers else None, op.limit
            )
        else:
            payload = runtime.memory.get(op.reference, op.offset, op.max_bytes)
    except (MemoryError, PolicyError) as exc:
        raise _owner_error(exc) from exc
    return MemoryResult(
        operation=op.operation,
        **payload,
        affordances=["memory.query", "sessions.query"],
    )


# ---------------------------------------------------------------- timeline


class TimelineInput(RequestControls):
    start: str | None = Field(
        default=None, max_length=64, description="RFC 3339 with timezone."
    )
    end: str | None = Field(default=None, max_length=64)
    query: str | None = Field(default=None, min_length=1, max_length=1_000)
    providers: list[MemorySource] | None = Field(default=None, min_length=1)
    limit: int = Field(default=100, ge=1, le=500)


class TimelineResult(GatewayModel):
    available: bool = True
    reason: str | None = None
    time_basis: str | None = None
    start: str | None = None
    end: str | None = None
    query: str | None = None
    sources: list[dict[str, Any]] | None = None
    entries: list[dict[str, Any]] | None = None
    truncated: bool = False
    affordances: list[str] = Field(default_factory=list)


def _timeline(runtime: Runtime, inp: TimelineInput) -> TimelineResult:
    try:
        payload = runtime.timeline.query(
            inp.start,
            inp.end,
            inp.query,
            list(inp.providers) if inp.providers else None,
            inp.limit,
        )
    except (TimelineError, PolicyError) as exc:
        raise _owner_error(exc) from exc
    return TimelineResult(
        **payload, affordances=["sessions.query", "memory.query", "activity.query"]
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
        owner="sessions",
        summary="List, read or search local coding-session JSONL files per provider.",
        Input=SessionsInput,
        Output=SessionsResult,
        handler=_sessions,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("session",),
        affordances=("sessions.query", "memory.query", "timeline.query"),
        aliases=("claude sessions", "codex sessions", "transcript", "session log"),
        examples=(
            Example(
                title="Recent Claude Code sessions",
                input={
                    "request": {
                        "operation": "list",
                        "provider": "claude-code",
                        "limit": 20,
                    }
                },
            ),
            Example(
                title="Search",
                input={
                    "request": {
                        "operation": "search",
                        "provider": "codex",
                        "query": "gateway",
                    }
                },
            ),
        ),
    ),
    Action(
        name="memory.query",
        family=VerbFamily.QUERY,
        owner="memory",
        summary="Search session-derived memory across providers or fetch one object by reference, with source provenance.",
        Input=MemoryInput,
        Output=MemoryResult,
        handler=_memory,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("session",),
        affordances=("memory.query", "sessions.query"),
        aliases=("remember", "recall", "what did we decide", "semantic search"),
        examples=(
            Example(
                title="Search all sources",
                input={"request": {"operation": "search", "query": "screenshot probe"}},
            ),
        ),
    ),
    Action(
        name="timeline.query",
        family=VerbFamily.QUERY,
        owner="timeline",
        summary="Session evidence ordered by file mtime within an RFC 3339 window, per provider, without claiming unavailable upstreams.",
        Input=TimelineInput,
        Output=TimelineResult,
        handler=_timeline,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("session",),
        affordances=("sessions.query", "memory.query", "activity.query"),
        aliases=("history", "when did", "sessions between", "chronology"),
        examples=(
            Example(
                title="Yesterday's sessions",
                input={"start": "2026-09-04T00:00:00Z", "end": "2026-09-05T00:00:00Z"},
            ),
        ),
    ),
)
