"""Process actions over /proc (psutil when importable), signals through the ops reducer or os.kill."""

from __future__ import annotations

import os
import signal as signal_module
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

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
from ..locators import (
    ProcessLocator,
    UnitLocator,
    UnitScope,
    proc_row,
    proc_snapshot,
    process_ref,
)
from ..redaction import redact
from ..results import ProtocolError
from ..schemas import GatewayModel
from .machine import OperateResult, _operate_via_reducer

if TYPE_CHECKING:
    from ..runtime import Runtime

try:  # psutil is optional: /proc parsing below is the complete fallback.
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - depends on the environment
    psutil = None

_CLK_TCK = os.sysconf("SC_CLK_TCK")
_PAGE = os.sysconf("SC_PAGE_SIZE")
_SECRET_KEYS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "API_KEY",
    "APIKEY",
    "AUTH",
    "CREDENTIAL",
    "PRIVATE",
)


def _boot_time() -> float:
    for line in Path("/proc/stat").read_text().splitlines():
        if line.startswith("btime "):
            return float(line.split()[1])
    return 0.0


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class ProcessRow(GatewayModel):
    ref: str
    pid: int
    ppid: int
    comm: str
    state: str
    unit: str | None = None
    unit_ref: str | None = None
    cgroup: str
    user: str | None = None
    uid: int | None = None
    cmdline: str | None = None
    started_at: str | None = None


def _user(pid: int) -> tuple[int | None, str | None]:
    try:
        uid = os.stat(f"/proc/{pid}").st_uid
        import pwd

        return uid, pwd.getpwuid(uid).pw_name
    except (OSError, KeyError):
        return None, None


def _cmdline(pid: int, limit: int = 4_000) -> str | None:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return None
    return (
        redact(raw.replace(b"\0", b" ").decode("utf-8", "replace").strip())[:limit]
        or None
    )


def _unit_ref(unit: str | None, cgroup: str) -> str | None:
    if unit is None:
        return None
    scope: UnitScope = (
        "user" if "/user.slice/" in cgroup or cgroup.startswith("/user") else "system"
    )
    return f"sinnix://machine/units/{scope}/{unit}"


def _row(raw: dict[str, Any], *, boot: float, with_cmdline: bool) -> ProcessRow:
    uid, user = _user(raw["pid"])
    return ProcessRow(
        ref=process_ref(raw["pid"], raw["start_ticks"]),
        pid=raw["pid"],
        ppid=raw["ppid"],
        comm=raw["comm"],
        state=raw["state"],
        unit=raw["unit"],
        unit_ref=_unit_ref(raw["unit"], raw["cgroup"]),
        cgroup=raw["cgroup"],
        uid=uid,
        user=user,
        cmdline=_cmdline(raw["pid"]) if with_cmdline else None,
        started_at=_iso(boot + raw["start_ticks"] / _CLK_TCK) if boot else None,
    )


# ------------------------------------------------------------------------ list


class ListInput(RequestControls):
    name: str | None = Field(
        default=None,
        max_length=64,
        description="Substring of comm or cmdline (case-insensitive).",
    )
    pid: int | None = Field(default=None, ge=1)
    unit: UnitLocator | None = None
    cgroup: str | None = Field(
        default=None,
        max_length=512,
        description="Substring of the cgroup path, e.g. agent.slice.",
    )
    user: str | None = Field(default=None, max_length=64)
    with_cmdline: bool = True
    limit: int = Field(default=200, ge=1, le=5_000)
    offset: int = Field(default=0, ge=0)


class ProcessListing(GatewayModel):
    processes: list[ProcessRow]
    total: int
    offset: int
    next_offset: int | None = None
    truncated: bool
    engine: Literal["psutil", "proc"]


def _list(runtime: Runtime, inp: ListInput) -> ProcessListing:
    runtime.principal.require(Capability.MACHINE_READ)
    boot = _boot_time()
    unit = inp.unit.resolve()[0] if inp.unit else None
    rows = proc_snapshot()
    if inp.pid is not None:
        rows = [row for row in rows if row["pid"] == inp.pid]
    if unit is not None:
        rows = [row for row in rows if row["unit"] == unit]
    if inp.cgroup:
        rows = [row for row in rows if inp.cgroup in row["cgroup"]]
    typed = [
        _row(row, boot=boot, with_cmdline=inp.with_cmdline or bool(inp.name))
        for row in rows
    ]
    if inp.user:
        typed = [row for row in typed if row.user == inp.user]
    if inp.name:
        needle = inp.name.casefold()
        typed = [
            row
            for row in typed
            if needle in row.comm.casefold() or needle in (row.cmdline or "").casefold()
        ]
    if not inp.with_cmdline:
        typed = [row.model_copy(update={"cmdline": None}) for row in typed]
    page = typed[inp.offset : inp.offset + inp.limit]
    truncated = inp.offset + inp.limit < len(typed)
    return ProcessListing(
        processes=page,
        total=len(typed),
        offset=inp.offset,
        next_offset=inp.offset + inp.limit if truncated else None,
        truncated=truncated,
        engine="psutil" if psutil else "proc",
    )


# ------------------------------------------------------------------------- get


class Socket(GatewayModel):
    family: Literal["tcp", "tcp6", "udp", "udp6", "unix"]
    local: str | None = None
    remote: str | None = None
    state: str | None = None
    inode: int


class ProcessDetail(ProcessRow):
    exe: str | None = None
    cwd: str | None = None
    threads: int | None = None
    cpu_seconds: float | None = None
    cpu_percent: float | None = None
    rss_bytes: int | None = None
    vms_bytes: int | None = None
    memory_percent: float | None = None
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Secret-looking values are replaced with [REDACTED].",
    )
    env_truncated: bool = False
    parent: ProcessRow | None = None
    children: list[ProcessRow] = Field(default_factory=list)
    sockets: list[Socket] = Field(default_factory=list)
    affordances: list[str] = Field(default_factory=list)


class GetInput(RequestControls):
    target: ProcessLocator
    with_env: bool = True
    with_sockets: bool = True
    env_limit: int = Field(default=500, ge=0, le=5_000)


def _hex_addr(value: str, v6: bool) -> str:
    host, _, port = value.partition(":")
    port_number = int(port, 16)
    if v6:
        import socket
        import struct

        packed = b"".join(
            struct.pack("<I", int(host[i : i + 8], 16)) for i in range(0, 32, 8)
        )
        return f"[{socket.inet_ntop(socket.AF_INET6, packed)}]:{port_number}"
    octets = ".".join(str(int(host[i : i + 2], 16)) for i in (6, 4, 2, 0))
    return f"{octets}:{port_number}"


_TCP_STATES = {
    "01": "ESTABLISHED",
    "02": "SYN_SENT",
    "03": "SYN_RECV",
    "04": "FIN_WAIT1",
    "05": "FIN_WAIT2",
    "06": "TIME_WAIT",
    "07": "CLOSE",
    "08": "CLOSE_WAIT",
    "09": "LAST_ACK",
    "0A": "LISTEN",
    "0B": "CLOSING",
}


def _sockets(pid: int) -> list[Socket]:
    inodes: set[int] = set()
    try:
        for fd in Path(f"/proc/{pid}/fd").iterdir():
            try:
                link = os.readlink(fd)
            except OSError:
                continue
            if link.startswith("socket:["):
                inodes.add(int(link[8:-1]))
    except OSError:
        return []
    if not inodes:
        return []
    found: list[Socket] = []
    for family in ("tcp", "tcp6", "udp", "udp6"):
        try:
            lines = Path(f"/proc/{pid}/net/{family}").read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) < 10 or int(parts[9]) not in inodes:
                continue
            v6 = family.endswith("6")
            found.append(
                Socket(
                    family=family,
                    local=_hex_addr(parts[1], v6),
                    remote=_hex_addr(parts[2], v6),
                    state=_TCP_STATES.get(parts[3])
                    if family.startswith("tcp")
                    else None,
                    inode=int(parts[9]),
                )
            )
    try:
        for line in Path(f"/proc/{pid}/net/unix").read_text().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 7 and int(parts[6]) in inodes:
                found.append(
                    Socket(
                        family="unix",
                        local=parts[7] if len(parts) > 7 else None,
                        inode=int(parts[6]),
                    )
                )
    except OSError:
        pass
    return found[:200]


def _environ(pid: int, limit: int) -> tuple[dict[str, str], bool]:
    try:
        raw = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        return {}, False
    entries = [piece.decode("utf-8", "replace") for piece in raw.split(b"\0") if piece]
    env: dict[str, str] = {}
    for entry in entries[:limit]:
        key, _, value = entry.partition("=")
        if any(marker in key.upper() for marker in _SECRET_KEYS):
            value = "[REDACTED]"
        env[key] = redact(value)[:2_000]
    return env, len(entries) > limit


def _get(runtime: Runtime, inp: GetInput) -> ProcessDetail:
    runtime.principal.require(Capability.MACHINE_READ)
    raw, ref = inp.target.resolve()
    pid = raw["pid"]
    boot = _boot_time()
    base = _row(raw, boot=boot, with_cmdline=True)
    try:
        stat_fields = Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()
        statm = Path(f"/proc/{pid}/statm").read_text().split()
    except OSError as exc:
        raise ProtocolError("not_found", "process exited during inspection") from exc
    cpu_seconds = (int(stat_fields[11]) + int(stat_fields[12])) / _CLK_TCK
    threads = int(stat_fields[17])
    rss = int(statm[1]) * _PAGE
    vms = int(statm[0]) * _PAGE
    cpu_percent = memory_percent = None
    if psutil is not None:
        try:
            proc = psutil.Process(pid)
            cpu_percent = proc.cpu_percent(interval=0.1)
            memory_percent = round(proc.memory_percent(), 3)
        except Exception:  # noqa: BLE001 - psutil raises its own hierarchy
            pass

    def link(name: str) -> str | None:
        try:
            return os.readlink(f"/proc/{pid}/{name}")
        except OSError:
            return None

    parent_raw = proc_row(raw["ppid"]) if raw["ppid"] > 0 else None
    children = [
        _row(row, boot=boot, with_cmdline=False)
        for row in proc_snapshot()
        if row["ppid"] == pid
    ][:100]
    env, env_truncated = _environ(pid, inp.env_limit) if inp.with_env else ({}, False)
    return ProcessDetail(
        **base.model_dump(),
        exe=link("exe"),
        cwd=link("cwd"),
        threads=threads,
        cpu_seconds=cpu_seconds,
        cpu_percent=cpu_percent,
        rss_bytes=rss,
        vms_bytes=vms,
        memory_percent=memory_percent,
        env=env,
        env_truncated=env_truncated,
        parent=_row(parent_raw, boot=boot, with_cmdline=False) if parent_raw else None,
        children=children,
        sockets=_sockets(pid) if inp.with_sockets else [],
        affordances=[
            "processes.tree",
            "processes.signal",
            "processes.wait",
            "machine.units.get",
        ],
    )


# ------------------------------------------------------------------------ tree


class TreeNode(ProcessRow):
    children: list[TreeNode] = Field(default_factory=list)


class TreeInput(RequestControls):
    root: ProcessLocator | None = Field(
        default=None,
        description="Subtree root; omitted means every process without a live parent.",
    )
    max_depth: int = Field(default=6, ge=1, le=32)
    max_nodes: int = Field(default=500, ge=1, le=5_000)
    with_cmdline: bool = False


class ProcessTree(GatewayModel):
    roots: list[TreeNode]
    nodes: int
    truncated: bool


def _tree(runtime: Runtime, inp: TreeInput) -> ProcessTree:
    runtime.principal.require(Capability.MACHINE_READ)
    boot = _boot_time()
    rows = {row["pid"]: row for row in proc_snapshot()}
    by_parent: dict[int, list[dict[str, Any]]] = {}
    for row in rows.values():
        by_parent.setdefault(row["ppid"], []).append(row)
    budget = {"nodes": 0, "truncated": False}

    def build(row: dict[str, Any], depth: int) -> TreeNode:
        budget["nodes"] += 1
        node = TreeNode(
            **_row(row, boot=boot, with_cmdline=inp.with_cmdline).model_dump()
        )
        if depth >= inp.max_depth:
            budget["truncated"] |= bool(by_parent.get(row["pid"]))
            return node
        for child in by_parent.get(row["pid"], []):
            if budget["nodes"] >= inp.max_nodes:
                budget["truncated"] = True
                break
            node.children.append(build(child, depth + 1))
        return node

    if inp.root is not None:
        raw, _ref = inp.root.resolve()
        roots = [build(rows.get(raw["pid"], raw), 1)]
    else:
        roots = [
            build(row, 1)
            for row in rows.values()
            if row["ppid"] not in rows and budget["nodes"] < inp.max_nodes
        ]
    return ProcessTree(
        roots=roots, nodes=budget["nodes"], truncated=budget["truncated"]
    )


# ---------------------------------------------------------------------- signal


class ReducerStop(GatewayModel):
    operation: Literal["stop"] = "stop"
    expected_revision: int = Field(
        ge=0, description="Revision from machine.query operation=actions."
    )


SignalName = Literal[
    "TERM", "KILL", "INT", "HUP", "USR1", "USR2", "STOP", "CONT", "QUIT"
]


class DirectSignal(GatewayModel):
    operation: Literal["signal"] = "signal"
    signal: SignalName = "TERM"


class SignalInput(MutationControls):
    target: ProcessLocator
    request: ReducerStop | DirectSignal = Field(
        discriminator="operation",
        description="stop: attested SIGTERM/SIGKILL through the ops reducer (admitted slices only). signal: direct os.kill by the operator.",
    )


class SignalResult(GatewayModel):
    ref: str
    pid: int
    operation: str
    signal: str | None = None
    delivered: bool
    owner_receipt: dict[str, Any] | None = None
    affordances: list[str] = Field(default_factory=list)


def _signal(runtime: Runtime, inp: SignalInput) -> SignalResult:
    runtime.principal.require(Capability.MACHINE_ACTION)
    raw, ref = inp.target.resolve()
    if isinstance(inp.request, ReducerStop):
        receipt: OperateResult = _operate_via_reducer(
            runtime,
            inp,
            target=ref,
            action="stop",
            parameters={},
            expected_revision=inp.request.expected_revision,
        )
        return SignalResult(
            ref=ref,
            pid=raw["pid"],
            operation="stop",
            signal="TERM",
            delivered=True,
            owner_receipt=receipt.owner_receipt,
            affordances=["processes.wait", "audit.receipt"],
        )
    if raw["pid"] in {1, os.getpid()}:
        raise ProtocolError(
            "policy_denied", "refusing to signal init or the gateway itself"
        )
    number = getattr(signal_module, f"SIG{inp.request.signal}")
    try:
        os.kill(raw["pid"], number)
    except ProcessLookupError as exc:
        raise ProtocolError("not_found", "process exited before the signal") from exc
    except PermissionError as exc:
        raise ProtocolError(
            "policy_denied", "signal is not permitted for this process"
        ) from exc
    return SignalResult(
        ref=ref,
        pid=raw["pid"],
        operation="signal",
        signal=inp.request.signal,
        delivered=True,
        affordances=["processes.wait", "processes.get"],
    )


# ------------------------------------------------------------------------ wait


class WaitInput(RequestControls):
    target: ProcessLocator
    timeout_seconds: float = Field(default=30, ge=0, le=300)
    poll_seconds: float = Field(default=0.2, ge=0.01, le=5)


class WaitResult(GatewayModel):
    ref: str
    pid: int
    exited: bool
    waited_seconds: float
    state: str | None = Field(
        default=None, description="Last observed /proc state when still alive."
    )
    affordances: list[str] = Field(default_factory=list)


def _wait(runtime: Runtime, inp: WaitInput) -> WaitResult:
    runtime.principal.require(Capability.MACHINE_READ)
    raw, ref = inp.target.resolve()
    started = time.monotonic()
    deadline = started + inp.timeout_seconds
    if inp.deadline_at is not None:
        deadline = min(deadline, started + max(0.0, inp.deadline_at - time.time()))
    state: str | None = raw["state"]
    while True:
        current = proc_row(raw["pid"])
        alive = (
            current is not None
            and current["start_ticks"] == raw["start_ticks"]
            and current["state"] != "Z"
        )
        if not alive:
            return WaitResult(
                ref=ref,
                pid=raw["pid"],
                exited=True,
                waited_seconds=round(time.monotonic() - started, 3),
                affordances=["processes.list"],
            )
        state = current["state"] if current else state
        if time.monotonic() >= deadline:
            return WaitResult(
                ref=ref,
                pid=raw["pid"],
                exited=False,
                waited_seconds=round(time.monotonic() - started, 3),
                state=state,
                affordances=["processes.get", "processes.signal"],
            )
        time.sleep(min(inp.poll_seconds, max(0.0, deadline - time.monotonic())))


ACTIONS: tuple[Action, ...] = (
    Action(
        name="processes.list",
        family=VerbFamily.QUERY,
        owner="machine",
        summary="List live processes filtered by name, pid, unit, cgroup or user, with a canonical ref each.",
        Input=ListInput,
        Output=ProcessListing,
        handler=_list,
        principals=ALL_PRINCIPALS,
        resource_kinds=("process",),
        affordances=(
            "processes.get",
            "processes.tree",
            "processes.signal",
            "machine.units.get",
        ),
        aliases=("ps", "pgrep", "what is running", "find process"),
        examples=(
            Example(title="Processes named rg", input={"name": "rg"}),
            Example(
                title="Processes of a unit", input={"unit": {"name": "polylogued"}}
            ),
        ),
    ),
    Action(
        name="processes.get",
        family=VerbFamily.GET,
        owner="machine",
        summary="Describe one process: cmdline, cwd, exe, redacted env, cgroup/unit, parent, children, sockets, cpu and memory.",
        Input=GetInput,
        Output=ProcessDetail,
        handler=_get,
        principals=ALL_PRINCIPALS,
        resource_kinds=("process",),
        affordances=(
            "processes.tree",
            "processes.signal",
            "processes.wait",
            "machine.units.get",
        ),
        aliases=(
            "process info",
            "pid details",
            "what is pid",
            "open sockets",
            "environment",
        ),
        examples=(Example(title="Inspect pid 1234", input={"target": {"pid": 1234}}),),
    ),
    Action(
        name="processes.tree",
        family=VerbFamily.QUERY,
        owner="machine",
        summary="Parent/child process tree from one root or from every top-level process, bounded by depth and node count.",
        Input=TreeInput,
        Output=ProcessTree,
        handler=_tree,
        principals=ALL_PRINCIPALS,
        resource_kinds=("process",),
        affordances=("processes.get", "processes.signal"),
        aliases=("pstree", "children", "descendants"),
        examples=(
            Example(
                title="Subtree of a unit's main process",
                input={"root": {"unit": {"name": "polylogued"}}, "max_depth": 4},
            ),
        ),
    ),
    Action(
        name="processes.signal",
        family=VerbFamily.OPERATE,
        owner="machine",
        summary="Stop a process through the ops reducer (attested, admitted slices) or send one signal directly as the operator.",
        Input=SignalInput,
        Output=SignalResult,
        handler=_signal,
        principals=OPERATOR_ONLY,
        resource_kinds=("process",),
        affordances=("processes.wait", "processes.get", "audit.receipt"),
        aliases=("kill", "pkill", "terminate", "sigterm", "sigkill"),
        supports_precondition=True,
        documentation="The reducer path is the attested one and needs expected_revision; the direct path is receipted by the gateway audit chain only.",
        examples=(
            Example(
                title="Reducer stop",
                input={
                    "target": {"pid": 4242},
                    "request": {"operation": "stop", "expected_revision": 17},
                    "reason": "runaway rg",
                    "idempotency_key": "stop-4242",
                },
            ),
            Example(
                title="Direct SIGHUP",
                input={
                    "target": {"name": "kitty"},
                    "request": {"operation": "signal", "signal": "HUP"},
                    "reason": "reload config",
                    "idempotency_key": "hup-kitty-1",
                },
            ),
        ),
    ),
    Action(
        name="processes.wait",
        family=VerbFamily.WAIT,
        owner="machine",
        summary="Wait until a process (same pid and start ticks) exits, or the bounded timeout elapses.",
        Input=WaitInput,
        Output=WaitResult,
        handler=_wait,
        principals=ALL_PRINCIPALS,
        resource_kinds=("process",),
        affordances=("processes.get", "processes.signal", "processes.list"),
        aliases=("wait for exit", "await process", "has it finished"),
        examples=(
            Example(
                title="Wait up to 10 s",
                input={"target": {"pid": 4242}, "timeout_seconds": 10},
            ),
        ),
    ),
)
