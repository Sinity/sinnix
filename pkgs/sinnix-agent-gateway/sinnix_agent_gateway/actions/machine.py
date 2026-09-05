"""Machine actions: sinnix-observe sections, systemd units, ops-reducer operations."""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field
from sinnix_mcp.execution import ExecutionProfile, ExecutionResult, OwnerRoute

from ..action import (
    ALL_PRINCIPALS,
    OPERATOR_ONLY,
    Action,
    Example,
    MutationControls,
    RequestControls,
)
from ..capabilities import Capability
from ..contracts import VerbFamily
from ..locators import UNIT_REF_PREFIX, UnitLocator, UnitScope
from ..machine_actions import MachineActionError
from ..results import ProtocolError
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime

SectionOperation = Literal[
    "overview",
    "pressure",
    "runtime_inventory",
    "gateway",
    "browser",
    "storage",
    "ingestion",
    "units",
    "workloads",
    "slices",
    "blocked_tasks",
    "actions",
]


class _Op(GatewayModel):
    def parameters(self) -> dict[str, Any]:
        return self.model_dump(exclude={"action"})


class InterruptOp(_Op):
    action: Literal["interrupt"] = "interrupt"


class FreezeOp(_Op):
    action: Literal["freeze"] = "freeze"


class ThawOp(_Op):
    action: Literal["thaw"] = "thaw"


class ResetPolicyOp(_Op):
    action: Literal["reset_policy"] = "reset_policy"


class SetPolicyOp(_Op):
    action: Literal["set_policy"] = "set_policy"
    property: Literal[
        "MemoryHigh", "MemoryMax", "MemoryLow", "CPUWeight", "IOWeight", "Nice"
    ]
    value: str = Field(min_length=1, max_length=64)


class ParkOp(_Op):
    action: Literal["park"] = "park"
    deadline_seconds: int = Field(ge=1, le=86_400)


class RebuildOverrideOp(_Op):
    action: Literal["rebuild_override"] = "rebuild_override"
    name: Literal["max_jobs", "cores", "eval_cache"]
    value: str = Field(min_length=1, max_length=32)


class RestartOp(_Op):
    action: Literal["restart"] = "restart"


class StartOp(_Op):
    action: Literal["start"] = "start"


class StopOp(_Op):
    action: Literal["stop"] = "stop"


MachineRequest = (
    InterruptOp
    | FreezeOp
    | ThawOp
    | ResetPolicyOp
    | SetPolicyOp
    | ParkOp
    | RebuildOverrideOp
    | RestartOp
    | StartOp
    | StopOp
)


def _run(
    runtime: Runtime, argv: list[str], route: str, timeout: float = 20
) -> ExecutionResult:
    return runtime.observe.execution.run(
        argv,
        ExecutionProfile(
            route=OwnerRoute(route),
            timeout_seconds=timeout,
            max_stdout_bytes=max(runtime.config.max_result_bytes * 8, 1_048_576),
        ),
    )


def _failed(result: ExecutionResult, what: str) -> ProtocolError:
    return ProtocolError(
        "unavailable",
        f"{what} failed: {result.stderr_excerpt() or result.failure_class or 'non-zero exit'}",
        details={"command": list(result.command), "exit_status": result.exit_status},
    )


# ---------------------------------------------------------------- machine.query


class QueryInput(RequestControls):
    operation: SectionOperation = Field(
        description="One sinnix-observe section, or actions for the ops-reducer revision."
    )
    cursor: int = Field(
        default=0,
        ge=0,
        description="Row cursor for units/workloads/slices/blocked_tasks.",
    )
    limit: int = Field(default=100, ge=1, le=500)


class MachineSection(GatewayModel):
    available: bool
    operation: str | None = None
    source: dict[str, Any] | None = None
    sections: dict[str, Any] | None = None
    rows: list[dict[str, Any]] | None = None
    total: int | None = None
    cursor: int | None = None
    next_cursor: int | None = None
    truncated: bool = False
    artifact: dict[str, Any] | None = None
    failure_class: str | None = None
    reason: str | None = None
    command: list[str] | None = None
    owner: str | None = None
    schema_name: str | None = Field(default=None, description="Owner report schema.")
    observed_at: str | None = None
    revision: int | None = None
    degradation: Any | None = None
    sources: dict[str, Any] | None = None


def _ops_revision(runtime: Runtime) -> dict[str, Any]:
    try:
        return runtime.machine_actions.snapshot()
    except MachineActionError as exc:
        return {
            "available": False,
            "operation": "actions",
            "owner": "ops-reducer",
            "failure_class": "owner_unavailable",
            "reason": str(exc),
        }


def _section(payload: dict[str, Any]) -> MachineSection:
    renamed = {
        ("schema_name" if key == "schema" else key): value
        for key, value in payload.items()
    }
    return MachineSection.model_validate(renamed)


def _query(runtime: Runtime, inp: QueryInput) -> MachineSection:
    if inp.operation == "actions":
        if inp.cursor:
            raise ProtocolError(
                "invalid_request", "machine actions snapshot does not support a cursor"
            )
        return _section(_ops_revision(runtime))
    try:
        payload = runtime.observe.machine_query(inp.operation, inp.cursor, inp.limit)
    except ValueError as exc:
        raise ProtocolError("invalid_request", str(exc)) from exc
    return _section(payload)


# ------------------------------------------------------------- machine.snapshot


class SnapshotSection(GatewayModel):
    available: bool
    source: str
    data: Any | None = None
    reason: str | None = None
    failure_class: str | None = None


class MachineSnapshot(GatewayModel):
    generated_at: str | None = None
    load: SnapshotSection
    pressure: SnapshotSection
    memory: SnapshotSection
    gpu: SnapshotSection
    disks: SnapshotSection
    units: SnapshotSection = Field(
        description="Units that are failed or in transition."
    )
    slices: SnapshotSection
    blocked_tasks: SnapshotSection
    network: SnapshotSection
    incidents: SnapshotSection
    ops_revision: SnapshotSection
    affordances: list[str] = Field(default_factory=list)


class SnapshotInput(RequestControls):
    unit_limit: int = Field(default=50, ge=1, le=200)
    incident_limit: int = Field(default=20, ge=1, le=200)


def _observe_section(
    runtime: Runtime, operation: str, key: str | None = None, limit: int = 500
) -> SnapshotSection:
    try:
        payload = runtime.observe.machine_query(operation, 0, limit)
    except ValueError as exc:
        return SnapshotSection(
            available=False, source="sinnix-observe", reason=str(exc)
        )
    if not payload.get("available"):
        return SnapshotSection(
            available=False,
            source="sinnix-observe",
            reason=payload.get("reason"),
            failure_class=payload.get("failure_class"),
        )
    if payload.get("truncated"):
        return SnapshotSection(
            available=True,
            source="sinnix-observe",
            data={"truncated": True, "artifact": payload.get("artifact")},
        )
    data = payload.get("rows") if "rows" in payload else payload.get("sections", {})
    if key is not None and isinstance(data, dict):
        data = data.get(key)
    return SnapshotSection(available=True, source="sinnix-observe", data=data)


def _proc_file(path: str) -> SnapshotSection:
    try:
        text = Path(path).read_text()
    except OSError as exc:
        return SnapshotSection(available=False, source=path, reason=str(exc))
    if path.endswith("loadavg"):
        one, five, fifteen, running, _last = text.split()
        return SnapshotSection(
            available=True,
            source=path,
            data={
                "1m": float(one),
                "5m": float(five),
                "15m": float(fifteen),
                "runnable": running.split("/")[0],
                "threads": running.split("/")[1],
            },
        )
    fields: dict[str, int] = {}
    for line in text.splitlines():
        name, _, rest = line.partition(":")
        if name in {
            "MemTotal",
            "MemAvailable",
            "MemFree",
            "SwapTotal",
            "SwapFree",
            "Cached",
            "Dirty",
            "Shmem",
        }:
            fields[name] = int(rest.split()[0]) * 1024
    return SnapshotSection(available=True, source=path, data={"bytes": fields})


def _incidents(runtime: Runtime, limit: int) -> SnapshotSection:
    path = runtime.config.runtime_transitions
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        return SnapshotSection(available=False, source=str(path), reason=str(exc))
    rows = []
    for line in lines[-limit:]:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return SnapshotSection(available=True, source=str(path), data=rows)


def _snapshot(runtime: Runtime, inp: SnapshotInput) -> MachineSnapshot:
    runtime.principal.require(Capability.MACHINE_READ)
    pressure = _observe_section(runtime, "pressure", "live_pressure")
    units = _observe_section(runtime, "units")
    if units.available and isinstance(units.data, list):
        notable = [
            row
            for row in units.data
            if isinstance(row, dict)
            and (
                row.get("active") not in {"active", "inactive"}
                or row.get("sub") == "failed"
                or row.get("load") not in {"loaded", None}
            )
        ]
        units = SnapshotSection(
            available=True,
            source="sinnix-observe",
            data={"total": len(units.data), "notable": notable[: inp.unit_limit]},
        )
    ops = _ops_revision(runtime)
    ops_section = SnapshotSection(
        available=bool(ops.get("available")),
        source="ops-reducer",
        data={k: ops.get(k) for k in ("revision", "observed_at", "degradation")}
        if ops.get("available")
        else None,
        reason=ops.get("reason"),
        failure_class=ops.get("failure_class"),
    )
    return MachineSnapshot(
        generated_at=(pressure.data or {}).get("generated_at")
        if isinstance(pressure.data, dict)
        else None,
        load=_proc_file("/proc/loadavg"),
        pressure=pressure,
        memory=_proc_file("/proc/meminfo"),
        gpu=SnapshotSection(
            available=False, source="none", reason="no owner exposes a GPU section"
        ),
        disks=_observe_section(runtime, "storage", "storage"),
        units=units,
        slices=_observe_section(runtime, "slices", limit=200),
        blocked_tasks=_observe_section(runtime, "blocked_tasks", limit=100),
        network=SnapshotSection(
            available=False, source="none", reason="no owner exposes a network section"
        ),
        incidents=_incidents(runtime, inp.incident_limit),
        ops_revision=ops_section,
        affordances=[
            "machine.query",
            "machine.units.list",
            "processes.list",
            "machine.operate",
        ],
    )


# ----------------------------------------------------------------- units.list


class UnitRow(GatewayModel):
    ref: str
    unit: str
    scope: UnitScope
    load: str | None = None
    active: str | None = None
    sub: str | None = None
    description: str | None = None


class UnitsListInput(RequestControls):
    scope: UnitScope = "user"
    pattern: str | None = Field(
        default=None,
        max_length=256,
        description="Glob on the unit name, e.g. sinnix-*.service",
    )
    state: Literal[
        "any", "active", "inactive", "failed", "activating", "deactivating"
    ] = "any"
    include_inactive: bool = Field(
        default=True, description="Pass --all so loaded-but-inactive units appear."
    )
    limit: int = Field(default=200, ge=1, le=2_000)
    offset: int = Field(default=0, ge=0)


class UnitsListing(GatewayModel):
    scope: UnitScope
    units: list[UnitRow]
    total: int
    offset: int
    next_offset: int | None = None
    truncated: bool


def _scope_flag(scope: UnitScope) -> list[str]:
    return ["--user"] if scope == "user" else ["--system"]


def _units_list(runtime: Runtime, inp: UnitsListInput) -> UnitsListing:
    runtime.principal.require(Capability.MACHINE_READ)
    argv = [
        runtime.config.systemctl_command,
        *_scope_flag(inp.scope),
        "list-units",
        "--output=json",
        "--no-pager",
        "--plain",
    ]
    if inp.include_inactive:
        argv.append("--all")
    if inp.state != "any":
        argv.append(f"--state={inp.state}")
    if inp.pattern:
        argv.append(inp.pattern)
    result = _run(runtime, argv, "machine-units")
    if result.failure_class is not None:
        raise _failed(result, "systemctl list-units")
    try:
        rows = result.decode_json()
    except ValueError as exc:
        raise ProtocolError(
            "owner_failed", "systemctl returned malformed JSON"
        ) from exc
    if not isinstance(rows, list):
        raise ProtocolError("owner_failed", "systemctl returned malformed JSON")
    units = [
        UnitRow(
            ref=f"{UNIT_REF_PREFIX}{inp.scope}/{row['unit']}",
            unit=row["unit"],
            scope=inp.scope,
            load=row.get("load"),
            active=row.get("active"),
            sub=row.get("sub"),
            description=row.get("description"),
        )
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("unit"), str)
        and (inp.pattern is None or fnmatch.fnmatch(row["unit"], inp.pattern))
    ]
    page = units[inp.offset : inp.offset + inp.limit]
    truncated = inp.offset + inp.limit < len(units)
    return UnitsListing(
        scope=inp.scope,
        units=page,
        total=len(units),
        offset=inp.offset,
        next_offset=inp.offset + inp.limit if truncated else None,
        truncated=truncated,
    )


# ------------------------------------------------------------------ units.get

DEFAULT_PROPERTIES = (
    "Id",
    "Description",
    "LoadState",
    "ActiveState",
    "SubState",
    "UnitFileState",
    "FragmentPath",
    "MainPID",
    "ExecMainStartTimestamp",
    "ActiveEnterTimestamp",
    "InactiveEnterTimestamp",
    "NRestarts",
    "Result",
    "ControlGroup",
    "MemoryCurrent",
    "MemoryPeak",
    "CPUUsageNSec",
    "TasksCurrent",
    "InvocationID",
    "Slice",
    "Type",
    "Restart",
    "TriggeredBy",
    "Triggers",
    "NextElapseUSecRealtime",
)


class UnitGetInput(RequestControls):
    target: UnitLocator
    properties: list[str] = Field(
        default_factory=list,
        max_length=200,
        description="systemctl show properties; empty means a standard set.",
    )


class UnitDetail(GatewayModel):
    ref: str
    unit: str
    scope: UnitScope
    load: str | None
    active: str | None
    sub: str | None
    main_pid: int | None = None
    process_ref: str | None = None
    control_group: str | None = None
    properties: dict[str, str]
    affordances: list[str] = Field(default_factory=list)


def _unit_show(
    runtime: Runtime, unit: str, scope: UnitScope, properties: tuple[str, ...]
) -> dict[str, str]:
    argv = [
        runtime.config.systemctl_command,
        *_scope_flag(scope),
        "show",
        "--no-pager",
        unit,
    ]
    for name in properties:
        argv += ["-p", name]
    result = _run(runtime, argv, "machine-units")
    if result.failure_class is not None:
        raise _failed(result, "systemctl show")
    shown = {}
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            shown[key] = value
    return shown


def _units_get(runtime: Runtime, inp: UnitGetInput) -> UnitDetail:
    runtime.principal.require(Capability.MACHINE_READ)
    unit, scope, ref = inp.target.resolve()
    wanted = tuple(
        dict.fromkeys(
            (
                "LoadState",
                "ActiveState",
                "SubState",
                "MainPID",
                "ControlGroup",
                *(inp.properties or DEFAULT_PROPERTIES),
            )
        )
    )
    shown = _unit_show(runtime, unit, scope, wanted)
    if shown.get("LoadState") in {None, "not-found"}:
        raise ProtocolError(
            "not_found",
            f"unit {unit} is not known to the {scope} manager",
            details={"ref": ref},
        )
    main_pid = (
        int(shown["MainPID"])
        if shown.get("MainPID", "0").isdigit() and shown["MainPID"] != "0"
        else None
    )
    process_ref = None
    if main_pid:
        from ..locators import proc_row
        from ..locators import process_ref as make_ref

        row = proc_row(main_pid)
        process_ref = make_ref(main_pid, row["start_ticks"]) if row else None
    return UnitDetail(
        ref=ref,
        unit=unit,
        scope=scope,
        load=shown.get("LoadState"),
        active=shown.get("ActiveState"),
        sub=shown.get("SubState"),
        main_pid=main_pid,
        process_ref=process_ref,
        control_group=shown.get("ControlGroup") or None,
        properties=shown,
        affordances=["machine.units.logs", "machine.units.operate", "processes.list"],
    )


# ----------------------------------------------------------------- units.logs


class UnitLogsInput(RequestControls):
    target: UnitLocator
    lines: int = Field(default=100, ge=1, le=2_000)
    since: str | None = Field(
        default=None,
        max_length=64,
        description="journalctl --since expression, e.g. '-1h' or an RFC 3339 time.",
    )
    until: str | None = Field(default=None, max_length=64)
    priority: (
        Literal["emerg", "alert", "crit", "err", "warning", "notice", "info", "debug"]
        | None
    ) = Field(
        default=None, description="Highest priority level to include (journalctl -p)."
    )
    grep: str | None = Field(
        default=None, max_length=512, description="Case-insensitive regex on MESSAGE."
    )
    max_bytes: int = Field(default=64_000, ge=1, le=1_048_576)


class LogEntry(GatewayModel):
    at: str | None = Field(default=None, description="UTC ISO timestamp.")
    realtime_usec: int | None = None
    priority: int | None = None
    pid: int | None = None
    identifier: str | None = None
    message: str
    cursor: str | None = None


class UnitLogs(GatewayModel):
    ref: str
    unit: str
    scope: UnitScope
    entries: list[LogEntry]
    returned: int
    truncated: bool
    affordances: list[str] = Field(default_factory=list)


def _units_logs(runtime: Runtime, inp: UnitLogsInput) -> UnitLogs:
    runtime.principal.require(Capability.MACHINE_READ)
    unit, scope, ref = inp.target.resolve()
    argv = [
        runtime.config.journalctl_command,
        *(["--user"] if scope == "user" else []),
        "-o",
        "json",
        "--no-pager",
        "-u",
        unit,
        "-n",
        str(inp.lines),
    ]
    if inp.since:
        argv += ["--since", inp.since]
    if inp.until:
        argv += ["--until", inp.until]
    if inp.priority:
        argv += ["-p", inp.priority]
    if inp.grep:
        argv += ["--case-sensitive=false", "-g", inp.grep]
    result = _run(runtime, argv, "machine-journal", timeout=30)
    if result.failure_class is not None:
        raise _failed(result, "journalctl")
    from datetime import datetime, timezone

    max_bytes = min(inp.max_bytes, runtime.config.max_result_bytes)
    entries: list[LogEntry] = []
    used = 0
    truncated = False
    for raw in result.stdout.splitlines():
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        message = row.get("MESSAGE")
        if isinstance(message, list):
            message = bytes(message).decode("utf-8", "replace")
        usec = row.get("__REALTIME_TIMESTAMP")
        usec = (
            int(usec) if isinstance(usec, (str, int)) and str(usec).isdigit() else None
        )
        entry = LogEntry(
            at=datetime.fromtimestamp(usec / 1e6, tz=timezone.utc).isoformat()
            if usec
            else None,
            realtime_usec=usec,
            priority=int(row["PRIORITY"])
            if str(row.get("PRIORITY", "")).isdigit()
            else None,
            pid=int(row["_PID"]) if str(row.get("_PID", "")).isdigit() else None,
            identifier=row.get("SYSLOG_IDENTIFIER") or row.get("_COMM"),
            message=str(message if message is not None else "")[:8_000],
            cursor=row.get("__CURSOR"),
        )
        used += len(entry.message) + 64
        if used > max_bytes:
            truncated = True
            break
        entries.append(entry)
    return UnitLogs(
        ref=ref,
        unit=unit,
        scope=scope,
        entries=entries,
        returned=len(entries),
        truncated=truncated or result.output_exceeded,
        affordances=["machine.units.get", "machine.units.operate"],
    )


# -------------------------------------------------------------- machine.operate


class OperateInput(MutationControls):
    target: str = Field(
        min_length=1,
        max_length=2_048,
        pattern=r"^sinnix://(?:jobs|machine/units|processes)/",
        description="Canonical job, unit or process ref.",
    )
    request: MachineRequest = Field(
        discriminator="action", description="The reducer action and its parameters."
    )
    expected_revision: int | None = Field(
        default=None,
        ge=0,
        description="Revision from machine.query operation=actions; also accepted as preconditions.expected_revision.",
    )


class OperateResult(GatewayModel):
    ref: str
    action: str
    owner_receipt: dict[str, Any]
    affordances: list[str] = Field(default_factory=list)


def _operate_via_reducer(
    runtime: Runtime,
    inp: MutationControls,
    *,
    target: str,
    action: str,
    parameters: dict[str, Any],
    expected_revision: int | None,
) -> OperateResult:
    if not inp.reason:
        raise ProtocolError("invalid_request", "machine operation requires reason")
    preconditions = dict(inp.preconditions or {})
    if expected_revision is not None:
        if (
            "expected_revision" in preconditions
            and preconditions["expected_revision"] != expected_revision
        ):
            raise ProtocolError(
                "invalid_request",
                "expected_revision disagrees with preconditions.expected_revision",
            )
        preconditions["expected_revision"] = expected_revision
    try:
        payload = runtime.v2_operate(
            reference=target,
            action=action,
            parameters=parameters,
            reason=inp.reason,
            idempotency_key=inp.idempotency_key,
            preconditions=preconditions,
        )
    except MachineActionError as exc:
        message = str(exc)
        code = (
            "conflict"
            if "stale" in message or "revision" in message
            else "unavailable"
            if "unavailable" in message
            else "owner_failed"
        )
        raise ProtocolError(code, message) from exc
    return OperateResult(**payload, affordances=["machine.query", "audit.receipt"])


def _operate(runtime: Runtime, inp: OperateInput) -> OperateResult:
    return _operate_via_reducer(
        runtime,
        inp,
        target=inp.target,
        action=inp.request.action,
        parameters=inp.request.parameters(),
        expected_revision=inp.expected_revision,
    )


class UnitOperateInput(MutationControls):
    target: UnitLocator
    action: Literal["start", "stop", "restart"]
    expected_revision: int | None = Field(default=None, ge=0)


def _units_operate(runtime: Runtime, inp: UnitOperateInput) -> OperateResult:
    _unit, _scope, ref = inp.target.resolve()
    return _operate_via_reducer(
        runtime,
        inp,
        target=ref,
        action=inp.action,
        parameters={},
        expected_revision=inp.expected_revision,
    )


ACTIONS: tuple[Action, ...] = (
    Action(
        name="machine.snapshot",
        family=VerbFamily.STATUS,
        owner="machine",
        summary="One bounded overview: load, PSI pressure, memory/swap, disks, notable units, slices, blocked tasks, incidents, ops revision.",
        Input=SnapshotInput,
        Output=MachineSnapshot,
        handler=_snapshot,
        principals=ALL_PRINCIPALS,
        resource_kinds=("machine_unit",),
        affordances=(
            "machine.query",
            "machine.units.list",
            "processes.list",
            "machine.operate",
        ),
        aliases=("overview", "health", "how is the machine", "system status", "top"),
        documentation="Each section carries its own availability and source; GPU and network report unavailable because no owner exposes them.",
        examples=(Example(title="Machine overview", input={}),),
    ),
    Action(
        name="machine.query",
        family=VerbFamily.QUERY,
        owner="machine",
        summary="Read one sinnix-observe section with cursor paging, or the ops-reducer revision (operation=actions).",
        Input=QueryInput,
        Output=MachineSection,
        handler=_query,
        principals=ALL_PRINCIPALS,
        resource_kinds=("machine_unit", "process"),
        affordances=(
            "machine.operate",
            "machine.units.get",
            "processes.get",
            "artifacts.read",
        ),
        aliases=("observe", "pressure", "storage", "workloads", "slices", "revision"),
        examples=(
            Example(
                title="Units page",
                input={"operation": "units", "cursor": 0, "limit": 50},
            ),
            Example(title="Ops revision", input={"operation": "actions"}),
        ),
    ),
    Action(
        name="machine.units.list",
        family=VerbFamily.QUERY,
        owner="machine",
        summary="List systemd units of one manager with load/active/sub state and a canonical ref each.",
        Input=UnitsListInput,
        Output=UnitsListing,
        handler=_units_list,
        principals=ALL_PRINCIPALS,
        resource_kinds=("machine_unit",),
        affordances=(
            "machine.units.get",
            "machine.units.logs",
            "machine.units.operate",
        ),
        aliases=("systemctl list-units", "services", "timers", "failed units"),
        examples=(
            Example(
                title="Failed user units", input={"scope": "user", "state": "failed"}
            ),
        ),
    ),
    Action(
        name="machine.units.get",
        family=VerbFamily.GET,
        owner="machine",
        summary="Describe one unit via systemctl show: states, main pid, cgroup, restarts, timestamps.",
        Input=UnitGetInput,
        Output=UnitDetail,
        handler=_units_get,
        principals=ALL_PRINCIPALS,
        resource_kinds=("machine_unit",),
        affordances=("machine.units.logs", "machine.units.operate", "processes.get"),
        aliases=("systemctl status", "unit status", "service status", "is it running"),
        examples=(
            Example(
                title="Describe polylogued",
                input={"target": {"name": "polylogued", "scope": "user"}},
            ),
        ),
    ),
    Action(
        name="machine.units.logs",
        family=VerbFamily.QUERY,
        owner="machine",
        summary="Journal entries for one unit (journalctl -o json), bounded by line count and bytes.",
        Input=UnitLogsInput,
        Output=UnitLogs,
        handler=_units_logs,
        principals=ALL_PRINCIPALS,
        resource_kinds=("machine_unit",),
        affordances=("machine.units.get", "machine.units.operate"),
        aliases=("journalctl", "logs", "journal", "why did it fail"),
        examples=(
            Example(
                title="Last 50 lines",
                input={"target": {"name": "polylogued"}, "lines": 50, "since": "-1h"},
            ),
        ),
    ),
    Action(
        name="machine.operate",
        family=VerbFamily.OPERATE,
        owner="ops-reducer",
        summary="Submit one revision-checked ops-reducer action against a canonical job, unit or process ref.",
        Input=OperateInput,
        Output=OperateResult,
        handler=_operate,
        principals=OPERATOR_ONLY,
        resource_kinds=("job", "machine_unit", "process"),
        affordances=("machine.query", "machine.units.get", "audit.receipt"),
        aliases=(
            "restart service",
            "freeze",
            "thaw",
            "park",
            "set policy",
            "interrupt job",
        ),
        supports_precondition=True,
        receipt_policy="owner",
        documentation="expected_revision must match machine.query operation=actions; the reducer receipt is verified against the submitted action and target.",
        examples=(
            Example(
                title="Restart a unit",
                input={
                    "target": "sinnix://machine/units/user/example.service",
                    "request": {"action": "restart"},
                    "reason": "apply the approved restart",
                    "expected_revision": 42,
                    "idempotency_key": "restart-example",
                },
            ),
            Example(
                title="Cap a unit's memory",
                input={
                    "target": "sinnix://machine/units/user/example.service",
                    "request": {
                        "action": "set_policy",
                        "property": "MemoryHigh",
                        "value": "4G",
                    },
                    "reason": "bound the runaway",
                    "expected_revision": 42,
                    "idempotency_key": "policy-example",
                },
            ),
        ),
    ),
    Action(
        name="machine.units.operate",
        family=VerbFamily.OPERATE,
        owner="ops-reducer",
        summary="Start, stop or restart one unit through the ops reducer (reload and wait are not reducer actions).",
        Input=UnitOperateInput,
        Output=OperateResult,
        handler=_units_operate,
        principals=OPERATOR_ONLY,
        resource_kinds=("machine_unit",),
        affordances=("machine.units.get", "machine.units.logs", "audit.receipt"),
        aliases=("systemctl restart", "systemctl start", "systemctl stop", "bounce"),
        supports_precondition=True,
        receipt_policy="owner",
        examples=(
            Example(
                title="Restart by name",
                input={
                    "target": {"name": "example", "scope": "user"},
                    "action": "restart",
                    "reason": "apply config",
                    "expected_revision": 42,
                    "idempotency_key": "restart-example-2",
                },
            ),
        ),
    ),
)
