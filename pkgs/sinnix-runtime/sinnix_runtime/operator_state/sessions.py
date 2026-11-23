"""Interactive agent sessions: what each holds in memory and whether it could
be parked.

A session left open keeps its whole process in memory inside the ceiling all
agent work shares. Parking ends such a session; its transcript stays on disk
and ``claude --resume <id>`` brings it back.

Idle is not abandoned: a coordinator waits an hour on a hosted check, a
backup or a queued job. ``judge`` therefore names every reason a session must
stay, and only a session with none is a candidate. Nothing here parks by
itself; ``sinnix sessions park`` is a dry run until ``--apply``.

``collect`` reads small files only (the harness's session registry, procfs,
cgroup counters, the tail of a transcript when it changed) so the state engine
can poll it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .claims import SESSION_VARIABLES, parse_duration

DEFAULT_IDLE = "2h"
DEFAULT_TOUCHED = "30m"
PARKED_LOG = Path("/realm/state/hub/parked-sessions.jsonl")
# One marker per session being parked, left before its process is asked to
# exit. The session's SessionEnd hook (dots/claude/hooks/sessionend-scratch.py)
# consumes it and keeps the session's scratch for the resume.
PARKING_DIR = Path("/realm/state/hub/parking")
TAIL_BYTES = 1024 * 1024
SUBAGENT_WINDOW_SECONDS = 24 * 3600
EXIT_WAIT_SECONDS = 20.0
# Codex subcommands that are not an interactive session.
CODEX_NOT_INTERACTIVE = frozenset(
    {
        "exec",
        "app-server",
        "mcp",
        "mcp-server",
        "login",
        "logout",
        "completion",
        "apply",
        "cloud",
        "sandbox",
        "debug",
    }
)
# Tools whose call means the session waits on another agent or a background task.
WAITING_TOOLS = frozenset(
    {"Agent", "Task", "SendMessage", "Monitor", "TaskOutput", "BashOutput", "Workflow"}
)
# Commands that wait on a queued job, a hosted check or another process.
WAITING_COMMAND = re.compile(
    r"agentctl\s+job\s+wait"
    r"|agentctl\s+job\s+start\b[^|;&]*--wait"
    r"|agentctl\s+events\s+tail\b[^|;&]*--follow"
    r"|\bgh\s+pr\s+checks\b"
    r"|\bgh\s+run\s+watch\b"
    r"|\bpueue\s+(wait|follow)\b"
    r"|--watch\b"
    r"|\bsleep\s+\d"
)
RULE_LINE = re.compile(r"^[─━]{20,}")
PROMPT_MARKS = ("❯", ">")
ANSI = re.compile(r"\x1b\[[0-9;:]*[A-Za-z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
SGR = re.compile(r"\x1b\[([0-9;:]*)m")

_tail_cache: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}


def claude_config_dir() -> Path:
    if root := os.environ.get("CLAUDE_CONFIG_DIR"):
        return Path(root)
    managed = Path.home() / ".config" / "claude"
    return managed if (managed / "sessions").is_dir() else Path.home() / ".claude"


# ---------------------------------------------------------------- procfs


def _stat_fields(proc: Path, pid: int) -> list[str] | None:
    """``/proc/<pid>/stat`` after the command name: state is index 0."""
    try:
        text = (proc / str(pid) / "stat").read_text()
    except OSError:
        return None
    return text.rsplit(")", 1)[-1].split()


def _argv(proc: Path, pid: int) -> list[str]:
    try:
        raw = (proc / str(pid) / "cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]


def _environ(proc: Path, pid: int) -> dict[str, str]:
    try:
        raw = (proc / str(pid) / "environ").read_bytes()
    except OSError:
        return {}
    pairs = (
        item.decode("utf-8", "replace").partition("=") for item in raw.split(b"\0")
    )
    return {name: value for name, _, value in pairs if name}


def _agent_name(argv: list[str]) -> str | None:
    name = Path(argv[0]).name if argv else ""
    return name if name in {"claude", "codex"} else None


def started_from_agent(proc: Path, pid: int, session: str | None) -> str | None:
    """The agent session this process was started from, if any.

    A session an agent launched carries that agent's session variable in the
    environment it was started with, or has an agent process as an ancestor.
    """
    environ = _environ(proc, pid)
    for harness, variable in SESSION_VARIABLES:
        value = environ.get(variable, "").strip()
        if value and value != session:
            return f"{harness} session {value[:8]}"
    seen = 0
    fields = _stat_fields(proc, pid)
    while fields and seen < 32:
        parent = int(fields[1])
        if parent <= 1:
            return None
        if name := _agent_name(_argv(proc, parent)):
            return f"{name} process {parent}"
        fields, seen = _stat_fields(proc, parent), seen + 1
    return None


def terminal_of(fields: list[str]) -> str | None:
    """The pseudo-terminal a process is attached to, from its ``tty_nr``."""
    number = int(fields[4])
    major, minor = (number >> 8) & 0xFFF, (number & 0xFF) | ((number >> 12) & 0xFFF00)
    return f"/dev/pts/{minor}" if 136 <= major <= 143 else None


def memory_of(proc: Path, cgroup_root: Path, pid: int) -> tuple[int | None, str]:
    """Resident plus swapped bytes, and where the number comes from.

    The launcher puts each session in its own scope under ``agent-cli.slice``;
    that scope's counters cover the session and the helpers it keeps (language
    servers, tool servers). Without one, the process's own counters are used.
    """
    try:
        line = (proc / str(pid) / "cgroup").read_text().strip().splitlines()[-1]
        group = cgroup_root / line.split("::", 1)[1].lstrip("/")
    except (OSError, IndexError):
        group = None
    if (
        group is not None
        and group.name.endswith(".scope")
        and "agent-cli" in str(group)
    ):
        try:
            total = int((group / "memory.current").read_text())
            try:
                total += int((group / "memory.swap.current").read_text())
            except (OSError, ValueError):
                pass
            return total, "scope"
        except (OSError, ValueError):
            pass
    try:
        status = (proc / str(pid) / "status").read_text()
    except OSError:
        return None, "unavailable"
    total = 0
    for line in status.splitlines():
        if line.startswith(("VmRSS:", "VmSwap:")):
            total += int(line.split()[1]) * 1024
    return total, "process"


# ---------------------------------------------------------------- transcripts


def _blocks(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    content = (record.get("message") or {}).get("content")
    return (
        [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []
    )


def read_tail(path: Path) -> dict[str, Any]:
    """What the end of a Claude Code transcript says about the session.

    ``open_tools``: tool calls with no result yet. ``waits``: the calls in the
    last turn that wait on a job, a hosted check or another agent.
    ``pending_agents``: background agents the harness counted at the last turn
    end.
    """
    try:
        stat = path.stat()
    except OSError:
        return {"readable": False}
    key = (stat.st_mtime_ns, stat.st_size)
    cached = _tail_cache.get(str(path))
    if cached and cached[0] == key:
        return cached[1]
    with path.open("rb") as handle:
        handle.seek(max(0, stat.st_size - TAIL_BYTES))
        lines = handle.read().split(b"\n")
    if stat.st_size > TAIL_BYTES:
        lines = lines[1:]  # the first line is cut
    calls: dict[str, tuple[str, str]] = {}
    turn: list[str] = []
    pending_agents = 0
    for line in lines:
        if not line.startswith(b"{"):
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        kind = record.get("type")
        if kind == "system" and "pendingBackgroundAgentCount" in record:
            pending_agents = int(record.get("pendingBackgroundAgentCount") or 0)
        if kind not in ("user", "assistant") or record.get("isSidechain"):
            continue
        blocks = _blocks(record)
        if kind == "user":
            results = [b for b in blocks if b.get("type") == "tool_result"]
            for block in results:
                calls.pop(str(block.get("tool_use_id")), None)
            if not results and not record.get("isMeta"):
                turn = []  # a new prompt starts a new turn
            continue
        for block in blocks:
            if block.get("type") != "tool_use":
                continue
            name = str(block.get("name") or "")
            tool_input = (
                block.get("input") if isinstance(block.get("input"), dict) else {}
            )
            command = str(tool_input.get("command") or "")
            calls[str(block.get("id"))] = (name, command)
            if name in WAITING_TOOLS or tool_input.get("run_in_background"):
                turn.append(f"{name} (another agent or a background task)")
            elif WAITING_COMMAND.search(command):
                turn.append(f"{name}: {' '.join(command.split())[:80]}")
    result = {
        "readable": True,
        "open_tools": sorted({name for name, _ in calls.values()}),
        "waits": list(dict.fromkeys(turn))[-3:],
        "pending_agents": pending_agents,
    }
    _tail_cache[str(path)] = (key, result)
    return result


def claude_transcript(config_dir: Path, cwd: str, session: str) -> Path | None:
    slug = "".join(ch if ch.isalnum() else "-" for ch in cwd)
    direct = config_dir / "projects" / slug / f"{session}.jsonl"
    if direct.is_file():
        return direct
    return next(iter((config_dir / "projects").glob(f"*/{session}.jsonl")), None)


def subagent_state(transcript: Path, now: float) -> tuple[float, list[str]]:
    """Newest subagent activity, and the subagents with a running tool call."""
    newest, working = 0.0, []
    directory = transcript.with_suffix("") / "subagents"
    try:
        entries = list(directory.glob("agent-*.jsonl"))
    except OSError:
        return newest, working
    for entry in entries:
        try:
            changed = entry.stat().st_mtime
        except OSError:
            continue
        newest = max(newest, changed)
        if now - changed <= SUBAGENT_WINDOW_SECONDS:
            tail = read_tail_any(entry)
            if tail.get("open_tools"):
                working.append(entry.stem.removeprefix("agent-")[:8])
    return newest, working


def read_tail_any(path: Path) -> dict[str, Any]:
    """``read_tail`` for a subagent transcript, whose records are sidechains."""
    try:
        stat = path.stat()
    except OSError:
        return {"readable": False}
    key = (stat.st_mtime_ns, stat.st_size)
    cached = _tail_cache.get(str(path))
    if cached and cached[0] == key:
        return cached[1]
    with path.open("rb") as handle:
        handle.seek(max(0, stat.st_size - TAIL_BYTES // 4))
        lines = handle.read().split(b"\n")
    calls: set[str] = set()
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        for block in _blocks(record):
            if block.get("type") == "tool_use":
                calls.add(str(block.get("id")))
            elif block.get("type") == "tool_result":
                calls.discard(str(block.get("tool_use_id")))
    result = {"readable": True, "open_tools": sorted(calls)}
    _tail_cache[str(path)] = (key, result)
    return result


# ---------------------------------------------------------------- collect


def _background_commands(proc: Path, pid: int) -> int:
    """Shell commands the session's Bash tool started that are still running."""
    count = 0
    try:
        children = (
            (proc / str(pid) / "task" / str(pid) / "children").read_text().split()
        )
    except OSError:
        return 0
    for child in children:
        if any("shell-snapshots" in word for word in _argv(proc, int(child))):
            count += 1
    return count


def _terminal_used(path: str | None) -> float | None:
    """When input last reached the terminal: its access time."""
    if path is None:
        return None
    try:
        return os.stat(path).st_atime
    except OSError:
        return None


def collect(
    *,
    config_dir: Path | None = None,
    proc: Path = Path("/proc"),
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    terminal_used: Callable[[str | None], float | None] = _terminal_used,
    now: float | None = None,
) -> list[dict[str, Any]]:
    """Facts about every interactive Claude Code and Codex session."""
    now = time.time() if now is None else now
    config_dir = config_dir or claude_config_dir()
    rows: list[dict[str, Any]] = []
    claude_pids: set[int] = set()
    for entry in sorted((config_dir / "sessions").glob("*.json")):
        try:
            record = json.loads(entry.read_text())
            pid, session = int(record["pid"]), str(record["sessionId"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        fields = _stat_fields(proc, pid)
        # A reused process id is another process: its start time differs.
        if fields is None or str(record.get("procStart")) != fields[19]:
            continue
        if record.get("kind") != "interactive":
            continue
        claude_pids.add(pid)
        cwd = str(record.get("cwd") or "")
        transcript = claude_transcript(config_dir, cwd, session)
        memory, memory_source = memory_of(proc, cgroup_root, pid)
        tty = terminal_of(fields)
        activity = float(record.get("statusUpdatedAt") or 0) / 1000
        tail: dict[str, Any] = {"readable": False}
        working_subagents: list[str] = []
        if transcript is not None:
            tail = read_tail(transcript)
            try:
                activity = max(activity, transcript.stat().st_mtime)
            except OSError:
                pass
            newest, working_subagents = subagent_state(transcript, now)
            activity = max(activity, newest)
        environ = _environ(proc, pid)
        rows.append(
            {
                "harness": "claude",
                "session": session,
                "pid": pid,
                "process_start": fields[19],
                "name": record.get("name"),
                "project": cwd,
                "memory_bytes": memory,
                "memory_source": memory_source,
                "last_activity_at": activity or None,
                "status": record.get("status"),
                "waiting_for": record.get("waitingFor"),
                "terminal": tty,
                "terminal_used_at": terminal_used(tty),
                "started_from": started_from_agent(proc, pid, session),
                "transcript": str(transcript) if transcript else None,
                "open_tools": tail.get("open_tools") or [],
                "waits": tail.get("waits") or [],
                "pending_agents": tail.get("pending_agents") or 0,
                "working_subagents": working_subagents,
                "background_commands": _background_commands(proc, pid),
                "kitty": {
                    "socket": environ.get("KITTY_LISTEN_ON"),
                    "window": environ.get("KITTY_WINDOW_ID"),
                },
                "resume": f"cd {_quote(cwd)} && claude --resume {session}",
            }
        )
    rows += _codex_sessions(proc, cgroup_root, terminal_used, claude_pids)
    return rows


def _quote(text: str) -> str:
    return (
        text
        if re.fullmatch(r"[\w@%+=:,./-]+", text)
        else "'" + text.replace("'", "'\\''") + "'"
    )


def _codex_sessions(
    proc: Path,
    cgroup_root: Path,
    terminal_used: Callable[[str | None], float | None],
    skip: set[int],
) -> list[dict[str, Any]]:
    rows = []
    for entry in proc.iterdir():
        if not entry.name.isdecimal() or int(entry.name) in skip:
            continue
        pid = int(entry.name)
        argv = _argv(proc, pid)
        if _agent_name(argv) != "codex" or CODEX_NOT_INTERACTIVE & set(argv[1:]):
            continue
        fields = _stat_fields(proc, pid)
        if fields is None:
            continue
        transcript = None
        try:
            for link in (entry / "fd").iterdir():
                target = os.readlink(link)
                if "/rollout-" in target and target.endswith(".jsonl"):
                    transcript = Path(target)
                    break
        except OSError:
            pass
        session = transcript.stem[-36:] if transcript else None
        try:
            cwd = os.readlink(entry / "cwd")
        except OSError:
            cwd = ""
        memory, memory_source = memory_of(proc, cgroup_root, pid)
        tty = terminal_of(fields)
        try:
            activity = transcript.stat().st_mtime if transcript else None
        except OSError:
            activity = None
        rows.append(
            {
                "harness": "codex",
                "session": session,
                "pid": pid,
                "process_start": fields[19],
                "name": None,
                "project": cwd,
                "memory_bytes": memory,
                "memory_source": memory_source,
                "last_activity_at": activity,
                "terminal": tty,
                "terminal_used_at": terminal_used(tty),
                "started_from": started_from_agent(proc, pid, session),
                "transcript": str(transcript) if transcript else None,
                "resume": f"cd {_quote(cwd)} && codex resume {session}"
                if session
                else None,
            }
        )
    return rows


# ---------------------------------------------------------------- judge


def minutes(seconds: float) -> str:
    return f"{seconds / 3600:.1f}h" if seconds >= 5400 else f"{round(seconds / 60)}m"


def judge(
    facts: list[dict[str, Any]],
    *,
    job_sessions: Mapping[str, list[str]] | None,
    now: float,
    idle_seconds: float,
    touched_seconds: float,
    calling_session: str | None = None,
) -> list[dict[str, Any]]:
    """Each session with its idle time and every reason it must stay.

    ``job_sessions`` maps a session to its unfinished jobs; None means the
    job queue could not be read, which keeps every session.
    """
    rows = []
    for fact in facts:
        keep: list[str] = []
        idle = (
            max(0.0, now - fact["last_activity_at"])
            if fact.get("last_activity_at")
            else None
        )
        session = fact.get("session")
        if fact["harness"] != "claude":
            keep.append("reported only: parking ends Claude Code sessions")
        if not session or not fact.get("transcript"):
            keep.append("no transcript, so it cannot be resumed by ID")
        if session and session == calling_session:
            keep.append("the calling session")
        if fact.get("started_from"):
            keep.append(f"started by {fact['started_from']}, not by the operator")
        if not fact.get("terminal"):
            keep.append("not attached to a terminal")
        if fact.get("status") == "busy":
            keep.append("working (status busy)")
        if fact.get("status") == "waiting":
            keep.append(
                f"waiting on the operator ({fact.get('waiting_for') or 'prompt open'})"
            )
        if fact.get("open_tools"):
            keep.append("running tool call: " + ", ".join(fact["open_tools"][:3]))
        if fact.get("background_commands"):
            keep.append(f"{fact['background_commands']} background command(s) running")
        if fact.get("pending_agents"):
            keep.append(f"{fact['pending_agents']} background agent(s) pending")
        if fact.get("working_subagents"):
            keep.append(
                "subagent with a running tool call: "
                + ", ".join(fact["working_subagents"][:3])
            )
        if fact.get("waits"):
            keep.append("last turn waits on " + "; ".join(fact["waits"]))
        if job_sessions is None:
            keep.append("the job queue could not be read")
        elif session and job_sessions.get(session):
            keep.append(
                "has unfinished job(s): " + ", ".join(job_sessions[session][:3])
            )
        used = fact.get("terminal_used_at")
        if used is not None and now - used < touched_seconds:
            keep.append(f"terminal used {minutes(now - used)} ago")
        if idle is None:
            keep.append("last activity unknown")
        elif idle < idle_seconds:
            keep.append(
                f"idle {minutes(idle)}, under the {minutes(idle_seconds)} limit"
            )
        rows.append(
            {
                **{
                    key: fact.get(key)
                    for key in (
                        "harness",
                        "session",
                        "pid",
                        "name",
                        "project",
                        "memory_bytes",
                        "memory_source",
                        "status",
                        "resume",
                    )
                },
                "last_activity_at": datetime.fromtimestamp(
                    fact["last_activity_at"], timezone.utc
                ).isoformat(timespec="seconds")
                if fact.get("last_activity_at")
                else None,
                "idle_seconds": round(idle) if idle is not None else None,
                "candidate": not keep,
                "keep_because": keep,
            }
        )
    rows.sort(key=lambda row: -(row["idle_seconds"] or 0))
    return rows


def job_sessions_of(snapshot: Mapping[str, Any]) -> dict[str, list[str]]:
    """Unfinished jobs by the session that started them."""
    found: dict[str, list[str]] = {}
    for job in snapshot.get("jobs") or []:
        caller = job.get("caller") if isinstance(job, dict) else None
        if job.get("terminal") is True or not isinstance(caller, dict):
            continue
        if session := caller.get("session"):
            found.setdefault(str(session), []).append(
                f"#{job.get('task_id')} {job.get('label')}"
            )
    return found


def session_line(row: Mapping[str, Any]) -> str:
    memory = row.get("memory_bytes")
    size = f"{memory / 2**20:.0f} MiB" if isinstance(memory, (int, float)) else "? MiB"
    idle = minutes(row["idle_seconds"]) if row.get("idle_seconds") is not None else "?"
    name = f" {row['name']}" if row.get("name") else ""
    verdict = (
        "parking candidate"
        if row["candidate"]
        else "stays: " + "; ".join(row["keep_because"])
    )
    return (
        f"{row['harness']} {str(row.get('session'))[:8]}{name} in {row.get('project')}: "
        f"{size}, idle {idle}; {verdict}"
    )


# ---------------------------------------------------------------- park


def input_line(screen: str) -> str:
    """What the session's input box holds: ``empty``, ``text`` or ``unknown``.

    ``screen`` is the terminal's text with its colour codes. Claude Code draws
    the box between two horizontal rules; its first line starts with the
    prompt mark. A hint the harness shows in an empty box is dimmed, and is
    the only text that counts as empty; anything else keeps the session.
    """
    raw = screen.splitlines()
    lines = [ANSI.sub("", line) for line in raw]
    rules = [index for index, line in enumerate(lines) if RULE_LINE.match(line.strip())]
    for top, bottom in zip(reversed(rules[:-1]), reversed(rules[1:]), strict=True):
        box = lines[top + 1 : bottom]
        if not box or not box[0].lstrip().startswith(PROMPT_MARKS):
            continue
        text = "".join([box[0].lstrip()[1:], *box[1:]]).replace("\xa0", " ").strip()
        if not text:
            return "empty"
        after_mark = re.split("[❯>]", raw[top + 1], maxsplit=1)[-1].lstrip("\xa0 ")
        style = SGR.match(after_mark)
        dimmed = style is not None and "2" in style.group(1).split(";")
        return "empty" if dimmed and len(box) == 1 else "text"
    return "unknown"


def read_screen(kitty: Mapping[str, Any]) -> str | None:
    if not kitty.get("socket") or not kitty.get("window"):
        return None
    try:
        result = subprocess.run(
            [
                "kitty",
                "@",
                "--to",
                str(kitty["socket"]),
                "get-text",
                "--match",
                f"id:{kitty['window']}",
                "--extent",
                "screen",
                "--ansi",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def end_session(
    fact: Mapping[str, Any],
    *,
    proc: Path = Path("/proc"),
    wait: float = EXIT_WAIT_SECONDS,
) -> str | None:
    """Ask the session's process to exit. None on success, else why not.

    The process is checked against its recorded start time first, and is
    never killed: one that does not exit is left running.
    """
    pid = int(fact["pid"])
    fields = _stat_fields(proc, pid)
    if fields is None or fields[19] != fact["process_start"]:
        return "the process is gone or its id was reused"
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        fields = _stat_fields(proc, pid)
        if fields is None or fields[19] != fact["process_start"] or fields[0] == "Z":
            return None
        time.sleep(0.25)
    return f"asked to exit but still running after {wait:.0f}s; left running"


def park(
    facts: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    *,
    apply: bool,
    only: str | None = None,
    screen: Callable[[Mapping[str, Any]], str | None] = read_screen,
    end: Callable[[Mapping[str, Any]], str | None] = end_session,
    log: Path | None = PARKED_LOG,
    parking: Path | None = PARKING_DIR,
) -> dict[str, Any]:
    """Park the candidates; without ``apply`` only say which would be."""
    by_pid = {fact["pid"]: fact for fact in facts}
    parked, kept = [], []
    for row in rows:
        if only and not str(row.get("session") or "").startswith(only):
            continue
        fact = by_pid[row["pid"]]
        reasons = list(row["keep_because"])
        if not reasons:
            # Read last, and only for a session nothing else keeps.
            text = screen(fact.get("kitty") or {})
            state = input_line(text) if text is not None else "unknown"
            if state == "text":
                reasons.append("unsent input in its input box")
            elif state == "unknown":
                reasons.append("its input box could not be read")
        if not reasons and apply:
            marker = None
            if parking is not None and row.get("session"):
                parking.mkdir(parents=True, exist_ok=True)
                marker = parking / str(row["session"])
                marker.touch()
            if failure := end(fact):
                reasons.append(failure)
                if marker is not None:
                    marker.unlink(missing_ok=True)
        if reasons:
            kept.append({**row, "candidate": False, "keep_because": reasons})
            continue
        entry = {
            key: row.get(key)
            for key in (
                "harness",
                "session",
                "name",
                "project",
                "memory_bytes",
                "idle_seconds",
                "resume",
            )
        }
        if apply:
            entry["parked_at"] = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            )
            if log is not None:
                log.parent.mkdir(parents=True, exist_ok=True)
                with log.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry, sort_keys=True) + "\n")
        parked.append(entry)
    return {"applied": apply, "parked": parked, "kept": kept}


def _snapshot() -> dict[str, list[str]] | None:
    from ..agent_jobs import AgentCtlClient

    try:
        return job_sessions_of(AgentCtlClient(timeout_seconds=20).snapshot())
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sinnix sessions",
        description="Interactive agent sessions with their memory and idle time; "
        "park the idle ones that can be resumed.",
    )
    parser.add_argument("--json", action="store_true")
    verbs = parser.add_subparsers(dest="verb")
    parking = verbs.add_parser(
        "park",
        help="end idle sessions that can be resumed by ID (a dry run by default)",
    )
    parking.add_argument(
        "--idle",
        required=True,
        metavar="DURATION",
        help="park sessions with no activity for this long, for example 2h",
    )
    parking.add_argument(
        "--touched",
        default=DEFAULT_TOUCHED,
        metavar="DURATION",
        help=f"keep a session whose terminal got input within this long (default {DEFAULT_TOUCHED})",
    )
    parking.add_argument(
        "--session", help="consider only the session with this ID prefix"
    )
    parking.add_argument(
        "--apply", action="store_true", help="end them (default: list them)"
    )
    listing = verbs.add_parser(
        "parked", help="sessions parked earlier, with their resume commands"
    )
    for verb in (parking, listing):
        verb.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if arguments.verb == "parked":
        try:
            entries = [
                json.loads(line) for line in PARKED_LOG.read_text().splitlines() if line
            ]
        except OSError:
            entries = []
        if arguments.json:
            print(json.dumps(entries, sort_keys=True))
        for entry in [] if arguments.json else entries:
            print(
                f"{entry.get('parked_at')} {entry.get('name') or ''}: {entry.get('resume')}"
            )
        return 0
    try:
        idle = parse_duration(arguments.idle if arguments.verb else DEFAULT_IDLE)
        touched = parse_duration(
            arguments.touched if arguments.verb else DEFAULT_TOUCHED
        )
    except ValueError as error:
        parser.error(str(error))
    now = time.time()
    facts = collect(now=now)
    calling = next(
        (os.environ[v] for _, v in SESSION_VARIABLES if os.environ.get(v)), None
    )
    rows = judge(
        facts,
        job_sessions=_snapshot(),
        now=now,
        idle_seconds=idle,
        touched_seconds=touched,
        calling_session=calling,
    )
    if arguments.verb is None:
        if arguments.json:
            print(json.dumps(rows, sort_keys=True))
        else:
            for row in rows:
                print(session_line(row))
            total = sum(row["memory_bytes"] or 0 for row in rows)
            print(f"{len(rows)} session(s), {total / 2**30:.1f} GiB")
        return 0
    result = park(facts, rows, apply=arguments.apply, only=arguments.session)
    if arguments.json:
        print(json.dumps(result, sort_keys=True))
        return 0
    verb = "parked" if result["applied"] else "would park"
    for entry in result["parked"]:
        memory = (entry.get("memory_bytes") or 0) / 2**20
        print(
            f"{verb} {entry['harness']} {str(entry['session'])[:8]} "
            f"{entry.get('name') or ''} ({memory:.0f} MiB, idle "
            f"{minutes(entry['idle_seconds'])})\n  resume: {entry['resume']}"
        )
    for row in result["kept"]:
        print(session_line(row))
    freed = sum(entry.get("memory_bytes") or 0 for entry in result["parked"])
    print(
        f"{verb} {len(result['parked'])} session(s), about {freed / 2**30:.1f} GiB"
        + ("" if result["applied"] else "; pass --apply to end them")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
