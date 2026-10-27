"""Capture lanes and normalised activity events."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from ..action import (
    Action,
    Example,
    RequestControls,
)
from ..captures import CaptureLane
from ..catalog import search_rows
from ..contracts import VerbFamily
from ..results import ProtocolError
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime


def _owner_error(exc: ValueError) -> ProtocolError:
    message = str(exc)
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
    next_actions: list[str] = Field(default_factory=list)


def _captures(runtime: Runtime, inp: CapturesInput) -> CapturesResult:
    op = inp.request
    try:
        if isinstance(op, LanesOp):
            return CapturesResult(
                operation="lanes",
                **runtime.captures.lanes_visible(),
                next_actions=["captures.query", "activity.query"],
            )
        if isinstance(op, LaneOp):
            return CapturesResult(
                operation="lane",
                lane=runtime.captures.lane(op.name),
                next_actions=["captures.query", "activity.query"],
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
    return CapturesResult(operation="query", **payload, next_actions=["activity.query"])


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
    next_actions: list[str] = Field(default_factory=list)


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


# The capture writer's high-water sidecar line (sinnix_capture.writer.HW_FORMAT):
# a 20-digit end offset, a space, a 32-wide running maximum ts, a newline.
_HW_WIDTH = 20 + 1 + 32 + 1


def _range_start(path: Path, since: float) -> int:
    """Offset past every record the high-water sidecar proves is before ``since``.

    Checkpoint ``i`` holds the end offset of the ``i``-th appended batch and the
    largest ts of every record up to it; both only grow, so the last checkpoint
    whose high water is below ``since`` bounds a prefix no in-window record can
    be in. A file without a usable sidecar is read from its start.
    """
    sidecar = path.with_name(path.name + ".hw")
    try:
        with sidecar.open("rb") as handle:
            count = handle.seek(0, 2) // _HW_WIDTH
            lo, hi, start = 0, count, 0
            while lo < hi:
                mid = (lo + hi) // 2
                handle.seek(mid * _HW_WIDTH)
                offset, high = handle.read(_HW_WIDTH).split()
                if float(high) < since:
                    start, lo = int(offset), mid + 1
                else:
                    hi = mid
    except (OSError, ValueError):
        return 0
    return start if start <= path.stat().st_size else 0


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
    until = inp.until if inp.until is not None else time.time()
    since = inp.since if inp.since is not None else until - 3_600
    if since > until:
        raise ProtocolError("invalid_request", "since must not be after until")
    available = runtime.captures._available_lanes()
    visible = sorted(available)
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
                start = _range_start(path, since)
                with path.open("rb") as handle:
                    handle.seek(start)
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
        next_actions=["captures.query", "mcp.tools", "mcp.call"],
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
        resource_kinds=("capture_lane",),
        next_actions=("activity.query", "captures.query"),
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
        summary="Normalised activity events (clipboard, notifications, media, windows...) from the capture lanes, newest first.",
        Input=ActivityInput,
        Output=Activity,
        handler=_activity,
        resource_kinds=("capture_lane",),
        next_actions=("captures.query", "mcp.tools", "mcp.call"),
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
)
