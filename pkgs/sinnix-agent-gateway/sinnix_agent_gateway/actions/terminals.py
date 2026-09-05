"""Kitty terminal actions: natural locators in, canonical terminal refs and
bounded text out; send, run, wait, focus and open through the kitty owner."""

from __future__ import annotations

import re
import shlex
import time
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from ..action import (
    OBSERVER_OPERATOR,
    OPERATOR_ONLY,
    Action,
    Example,
    MutationControls,
    RequestControls,
)
from ..contracts import VerbFamily
from ..locators import TerminalLocator, terminal_ref
from ..results import ProtocolError
from ..schemas import GatewayModel
from ..terminals import TerminalDiagnosticError, TerminalError

if TYPE_CHECKING:
    from ..runtime import Runtime


def _owner_call(callback):
    try:
        return callback()
    except TerminalDiagnosticError as exc:
        raise ProtocolError(
            "unavailable",
            "terminal owner failed",
            details=dict(exc.response),
            diagnostic_refs=[
                f"sinnix://artifacts/{exc.response['diagnostic_artifact_id']}"
            ],
        ) from exc
    except TerminalError as exc:
        raise ProtocolError("owner_failed", str(exc)) from exc


class Process(GatewayModel):
    pid: int | None = None
    cmdline: list[str] = Field(default_factory=list)
    cwd: str | None = None


class Terminal(GatewayModel):
    ref: str
    kitty_id: int
    os_window_id: int | None = None
    tab_id: int | None = None
    title: str = ""
    tab_title: str | None = None
    cwd: str | None = None
    pid: int | None = Field(default=None, description="Shell pid.")
    focused: bool = False
    is_active: bool = Field(default=False, description="Active window of its tab.")
    at_prompt: bool | None = None
    cmdline: list[str] = Field(default_factory=list)
    foreground_processes: list[Process] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)
    affordances: list[str] = Field(default_factory=list)


_KNOWN = {
    "id",
    "os_window_id",
    "tab_id",
    "title",
    "tab_title",
    "cwd",
    "pid",
    "focused",
    "is_focused",
    "is_active",
    "at_prompt",
    "cmdline",
    "foreground_processes",
}


def _terminal(window: dict[str, Any]) -> Terminal:
    return Terminal(
        ref=terminal_ref(int(window["id"])),
        kitty_id=int(window["id"]),
        os_window_id=window.get("os_window_id"),
        tab_id=window.get("tab_id"),
        title=str(window.get("title", "") or ""),
        tab_title=window.get("tab_title"),
        cwd=window.get("cwd"),
        pid=window.get("pid"),
        focused=bool(window.get("focused")),
        is_active=bool(window.get("is_active")),
        at_prompt=window.get("at_prompt"),
        cmdline=[str(part) for part in window.get("cmdline", []) or []],
        foreground_processes=[
            Process(
                pid=proc.get("pid"),
                cmdline=[str(part) for part in proc.get("cmdline", []) or []],
                cwd=proc.get("cwd"),
            )
            for proc in window.get("foreground_processes", []) or []
            if isinstance(proc, dict)
        ],
        extra={key: value for key, value in window.items() if key not in _KNOWN},
        affordances=[
            "terminals.screen",
            "terminals.send",
            "terminals.run",
            "terminals.focus",
        ],
    )


def _windows(runtime: Runtime) -> list[dict[str, Any]]:
    listing = _owner_call(lambda: runtime.terminals.read("list"))["result"]
    return TerminalLocator.windows(listing)


def _resolve(runtime: Runtime, locator: TerminalLocator) -> tuple[dict[str, Any], str]:
    return _owner_call(lambda: locator.resolve(runtime))


def _refresh(runtime: Runtime, kitty_id: int) -> Terminal | None:
    return next(
        (_terminal(w) for w in _windows(runtime) if w.get("id") == kitty_id), None
    )


class ListInput(RequestControls):
    pass


class TerminalListing(GatewayModel):
    terminals: list[Terminal]
    focused_ref: str | None = None
    affordances: list[str] = Field(default_factory=list)


def _list(runtime: Runtime, inp: ListInput) -> TerminalListing:
    terminals = [_terminal(w) for w in _windows(runtime)]
    return TerminalListing(
        terminals=terminals,
        focused_ref=next((t.ref for t in terminals if t.focused), None),
        affordances=[
            "terminals.get",
            "terminals.screen",
            "terminals.send",
            "terminals.open",
        ],
    )


class GetInput(RequestControls):
    target: TerminalLocator


def _get(runtime: Runtime, inp: GetInput) -> Terminal:
    window, _ = _resolve(runtime, inp.target)
    return _terminal(window)


Extent = Literal[
    "screen", "all", "selection", "last_cmd_output", "last_non_empty_output"
]


def _capture(runtime: Runtime, kitty_id: int, extent: str, ansi: bool) -> str:
    result = _owner_call(
        lambda: runtime.terminals.read(
            "capture", {"match": f"id:{kitty_id}", "extent": extent, "ansi": ansi}
        )
    )["result"]
    return result if isinstance(result, str) else str(result)


class TerminalText(GatewayModel):
    ref: str
    kitty_id: int
    extent: Extent
    text: str
    lines: int
    total_lines: int | None = Field(default=None, description="Before tail truncation.")
    truncated: bool = False
    affordances: list[str] = Field(default_factory=list)


class ScreenInput(RequestControls):
    target: TerminalLocator
    ansi: bool = Field(default=False, description="Keep ANSI styling escapes.")


def _screen(runtime: Runtime, inp: ScreenInput) -> TerminalText:
    window, ref = _resolve(runtime, inp.target)
    text = _capture(runtime, int(window["id"]), "screen", inp.ansi)
    return TerminalText(
        ref=ref,
        kitty_id=int(window["id"]),
        extent="screen",
        text=text,
        lines=len(text.splitlines()),
        affordances=["terminals.scrollback", "terminals.send", "terminals.wait"],
    )


class ScrollbackInput(RequestControls):
    target: TerminalLocator
    source: Literal["screen", "history", "last_command"] = Field(
        default="history",
        description="history = screen plus scrollback; last_command = output of the last shell command.",
    )
    lines: int = Field(
        default=500, ge=1, le=100_000, description="Last N lines returned."
    )
    ansi: bool = False


def _scrollback(runtime: Runtime, inp: ScrollbackInput) -> TerminalText:
    window, ref = _resolve(runtime, inp.target)
    extent = {"screen": "screen", "history": "all", "last_command": "last_cmd_output"}[
        inp.source
    ]
    text = _capture(runtime, int(window["id"]), extent, inp.ansi)
    all_lines = text.splitlines()
    tail = all_lines[-inp.lines :]
    return TerminalText(
        ref=ref,
        kitty_id=int(window["id"]),
        extent=extent,
        text="\n".join(tail),
        lines=len(tail),
        total_lines=len(all_lines),
        truncated=len(all_lines) > len(tail),
        affordances=["terminals.screen", "terminals.send", "terminals.wait"],
    )


class ProcessesInput(RequestControls):
    target: TerminalLocator


class TerminalProcesses(GatewayModel):
    ref: str
    kitty_id: int
    shell_pid: int | None
    cwd: str | None
    at_prompt: bool | None
    processes: list[Process]


def _processes(runtime: Runtime, inp: ProcessesInput) -> TerminalProcesses:
    window, ref = _resolve(runtime, inp.target)
    terminal = _terminal(window)
    return TerminalProcesses(
        ref=ref,
        kitty_id=terminal.kitty_id,
        shell_pid=terminal.pid,
        cwd=terminal.cwd,
        at_prompt=terminal.at_prompt,
        processes=terminal.foreground_processes,
    )


# ----------------------------------------------------------------------- send


class TextInput(GatewayModel):
    kind: Literal["text"] = "text"
    text: str = Field(min_length=1, max_length=64_000)
    enter: bool = Field(default=False, description="Press Enter after the text.")
    bracketed_paste: bool = False


class KeysInput(GatewayModel):
    kind: Literal["keys"] = "keys"
    keys: list[str] = Field(
        min_length=1,
        max_length=16,
        description="kitty key names, e.g. ctrl+c, enter, escape, tab.",
    )


class SendInput(MutationControls):
    target: TerminalLocator
    input: TextInput | KeysInput = Field(discriminator="kind")


class SendResult(GatewayModel):
    ref: str
    kitty_id: int
    kind: Literal["text", "keys"]
    sent: str | list[str]
    terminal: Terminal | None
    affordances: list[str] = Field(default_factory=list)


def _send(runtime: Runtime, inp: SendInput) -> SendResult:
    window, ref = _resolve(runtime, inp.target)
    kitty_id = int(window["id"])
    match = f"id:{kitty_id}"
    if isinstance(inp.input, TextInput):
        _owner_call(
            lambda: runtime.terminals.action(
                "send",
                {
                    "match": match,
                    "text": inp.input.text,
                    "enter": inp.input.enter,
                    "bracketed_paste": inp.input.bracketed_paste,
                },
            )
        )
        sent: str | list[str] = inp.input.text
    else:
        _owner_call(
            lambda: runtime.terminals.action(
                "key", {"match": match, "keys": inp.input.keys}
            )
        )
        sent = inp.input.keys
    return SendResult(
        ref=ref,
        kitty_id=kitty_id,
        kind=inp.input.kind,
        sent=sent,
        terminal=_refresh(runtime, kitty_id),
        affordances=["terminals.wait", "terminals.screen", "terminals.scrollback"],
    )


# ------------------------------------------------------------------------ run


_RC_MARKER = "__SINNIX_RC:"


class RunInput(MutationControls):
    target: TerminalLocator
    command: str | list[str] = Field(
        description="A shell command line, or an argv list that is shell-quoted for you."
    )
    wait: bool = Field(
        default=True, description="Wait until the shell is back at a prompt."
    )
    timeout_seconds: int = Field(default=60, ge=1, le=3_600)
    capture_exit_status: bool = Field(
        default=False,
        description="Append an exit-status marker to the command line so the status is reported; the marker is visible in the terminal.",
    )


class RunResult(GatewayModel):
    ref: str
    kitty_id: int
    command: str
    completed: bool = Field(
        description="The shell returned to a prompt within the timeout."
    )
    exit_status: int | None = Field(
        default=None, description="Only with capture_exit_status."
    )
    output: str | None = Field(
        default=None, description="Last command output per kitty shell integration."
    )
    cwd: str | None = None
    duration_seconds: float | None = None
    terminal: Terminal | None
    affordances: list[str] = Field(default_factory=list)


def _run(runtime: Runtime, inp: RunInput) -> RunResult:
    window, ref = _resolve(runtime, inp.target)
    kitty_id = int(window["id"])
    command = inp.command if isinstance(inp.command, str) else shlex.join(inp.command)
    if not command.strip():
        raise ProtocolError("invalid_request", "command is empty")
    line = command
    if inp.capture_exit_status:
        line = f"{command}; printf '\\n{_RC_MARKER}%s__\\n' \"$?\""
    started = time.monotonic()
    _owner_call(
        lambda: runtime.terminals.action(
            "run", {"match": f"id:{kitty_id}", "command": line}
        )
    )
    completed = False
    output: str | None = None
    exit_status: int | None = None
    terminal: Terminal | None = None
    if inp.wait:
        time.sleep(0.2)
        while True:
            terminal = _refresh(runtime, kitty_id)
            if terminal is None:
                raise ProtocolError(
                    "not_found", "terminal disappeared while running the command"
                )
            if terminal.at_prompt:
                completed = True
                break
            if time.monotonic() - started >= inp.timeout_seconds:
                break
            time.sleep(0.3)
        output = _capture(runtime, kitty_id, "last_cmd_output", False)
        if inp.capture_exit_status:
            found = re.findall(re.escape(_RC_MARKER) + r"(\d+)__", output)
            if found:
                exit_status = int(found[-1])
                output = re.sub(
                    r"\n?" + re.escape(_RC_MARKER) + r"\d+__\n?", "", output
                )
    else:
        terminal = _refresh(runtime, kitty_id)
    return RunResult(
        ref=ref,
        kitty_id=kitty_id,
        command=command,
        completed=completed,
        exit_status=exit_status,
        output=output,
        cwd=terminal.cwd if terminal else None,
        duration_seconds=round(time.monotonic() - started, 3) if inp.wait else None,
        terminal=terminal,
        affordances=["terminals.scrollback", "terminals.wait", "terminals.send"],
    )


# ----------------------------------------------------------------------- wait


class PromptCondition(GatewayModel):
    kind: Literal["prompt"] = "prompt"


class RegexCondition(GatewayModel):
    kind: Literal["regex"] = "regex"
    pattern: str = Field(
        min_length=1, max_length=2_048, description="Extended regex (grep -E)."
    )
    extent: Extent = "all"


class ProcessExitCondition(GatewayModel):
    kind: Literal["process_exit"] = "process_exit"
    pid: int | None = Field(
        default=None,
        description="Defaults to any foreground process besides the shell.",
    )


class TitleCondition(GatewayModel):
    kind: Literal["title"] = "title"
    contains: str = Field(min_length=1, max_length=512)


WaitCondition = PromptCondition | RegexCondition | ProcessExitCondition | TitleCondition


class WaitInput(RequestControls):
    target: TerminalLocator
    condition: WaitCondition = Field(discriminator="kind")
    timeout_seconds: int = Field(default=30, ge=1, le=3_600)


class WaitResult(GatewayModel):
    ref: str
    kitty_id: int
    condition: str
    satisfied: bool
    waited_seconds: float
    matched_text: str | None = None
    terminal: Terminal | None
    affordances: list[str] = Field(default_factory=list)


def _wait(runtime: Runtime, inp: WaitInput) -> WaitResult:
    window, ref = _resolve(runtime, inp.target)
    kitty_id = int(window["id"])
    started = time.monotonic()
    condition = inp.condition
    matched: str | None = None
    satisfied = False
    if isinstance(condition, RegexCondition):
        try:
            result = _owner_call(
                lambda: runtime.terminals.invoke(
                    [
                        "await",
                        "--match",
                        f"id:{kitty_id}",
                        "--pattern",
                        condition.pattern,
                        "--timeout-sec",
                        str(inp.timeout_seconds),
                        "--extent",
                        condition.extent,
                    ],
                    mutating=False,
                    timeout=inp.timeout_seconds + 10,
                )
            )
            matched = (result if isinstance(result, str) else str(result)).rstrip("\n")
            satisfied = True
        except ProtocolError as exc:
            if exc.code != "unavailable" or exc.details.get("exit_status") != 124:
                raise
    else:
        shell_pid = window.get("pid")
        while True:
            terminal = _refresh(runtime, kitty_id)
            if terminal is None:
                raise ProtocolError("not_found", "terminal disappeared while waiting")
            if isinstance(condition, PromptCondition):
                satisfied = bool(terminal.at_prompt)
            elif isinstance(condition, TitleCondition):
                satisfied = condition.contains.casefold() in terminal.title.casefold()
                matched = terminal.title if satisfied else None
            else:
                pids = {
                    proc.pid
                    for proc in terminal.foreground_processes
                    if proc.pid != shell_pid
                }
                satisfied = condition.pid not in pids if condition.pid else not pids
            if satisfied or time.monotonic() - started >= inp.timeout_seconds:
                break
            time.sleep(0.3)
    return WaitResult(
        ref=ref,
        kitty_id=kitty_id,
        condition=condition.kind,
        satisfied=satisfied,
        waited_seconds=round(time.monotonic() - started, 3),
        matched_text=matched,
        terminal=_refresh(runtime, kitty_id),
        affordances=["terminals.screen", "terminals.scrollback", "terminals.send"],
    )


# ---------------------------------------------------------------- focus / open


class FocusInput(MutationControls):
    target: TerminalLocator


class FocusResult(GatewayModel):
    ref: str
    kitty_id: int
    terminal: Terminal | None
    affordances: list[str] = Field(default_factory=list)


def _focus(runtime: Runtime, inp: FocusInput) -> FocusResult:
    window, ref = _resolve(runtime, inp.target)
    kitty_id = int(window["id"])
    _owner_call(lambda: runtime.terminals.action("focus", {"match": f"id:{kitty_id}"}))
    return FocusResult(
        ref=ref,
        kitty_id=kitty_id,
        terminal=_refresh(runtime, kitty_id),
        affordances=["terminals.send", "terminals.screen"],
    )


class OpenInput(MutationControls):
    cwd: str | None = Field(default=None, min_length=1, max_length=4_096)
    command: str | list[str] | None = Field(
        default=None,
        description="Command to run in the new window; the window stays open afterwards.",
    )
    title: str | None = Field(default=None, min_length=1, max_length=256)
    placement: Literal["os_window", "window", "tab"] = Field(
        default="os_window",
        description="New OS window, a split in the active tab, or a new tab.",
    )


class OpenResult(GatewayModel):
    ref: str
    kitty_id: int
    terminal: Terminal | None
    affordances: list[str] = Field(default_factory=list)


def _open(runtime: Runtime, inp: OpenInput) -> OpenResult:
    arguments = ["launch", "--type", inp.placement.replace("_", "-")]
    if inp.cwd:
        arguments.extend(["--cwd", inp.cwd])
    if inp.title:
        arguments.extend(["--title", inp.title])
    if inp.command:
        command = (
            inp.command if isinstance(inp.command, str) else shlex.join(inp.command)
        )
        arguments.extend(["--command", command])
    raw = _owner_call(lambda: runtime.terminals.invoke(arguments, mutating=True))
    kitty_id = raw.get("id") if isinstance(raw, dict) else None
    if not isinstance(kitty_id, int):
        raise ProtocolError(
            "owner_failed",
            "kitty did not report the new window id",
            details={"result": raw},
        )
    terminal = None
    deadline = time.monotonic() + 5
    while terminal is None and time.monotonic() < deadline:
        terminal = _refresh(runtime, kitty_id)
        if terminal is None:
            time.sleep(0.2)
    return OpenResult(
        ref=terminal_ref(kitty_id),
        kitty_id=kitty_id,
        terminal=terminal,
        affordances=[
            "terminals.send",
            "terminals.run",
            "terminals.screen",
            "terminals.focus",
        ],
    )


_READ = {
    "owner": "terminals",
    "principals": OBSERVER_OPERATOR,
    "resource_kinds": ("terminal",),
}
_WRITE = {
    "owner": "terminals",
    "principals": OPERATOR_ONLY,
    "resource_kinds": ("terminal",),
}
_TARGET = {"target": {"title_contains": "Codex"}}

ACTIONS: tuple[Action, ...] = (
    Action(
        name="terminals.list",
        family=VerbFamily.CATALOG,
        summary="Every kitty window with its ref, title, cwd, shell pid, focus and foreground processes.",
        Input=ListInput,
        Output=TerminalListing,
        handler=_list,
        affordances=(
            "terminals.get",
            "terminals.screen",
            "terminals.send",
            "terminals.open",
        ),
        aliases=("kitty windows", "terminal inventory", "shells"),
        examples=(Example(title="List terminals", input={}),),
        **_READ,
    ),
    Action(
        name="terminals.get",
        family=VerbFamily.GET,
        summary="Resolve one terminal by ref, kitty id, title, cwd, pid or focus.",
        Input=GetInput,
        Output=Terminal,
        handler=_get,
        affordances=("terminals.screen", "terminals.send", "terminals.run"),
        aliases=("find terminal", "which terminal", "focused terminal"),
        examples=(
            Example(title="The focused terminal", input={"target": {"focused": True}}),
        ),
        **_READ,
    ),
    Action(
        name="terminals.screen",
        family=VerbFamily.QUERY,
        summary="The visible screen text of one terminal.",
        Input=ScreenInput,
        Output=TerminalText,
        handler=_screen,
        affordances=("terminals.scrollback", "terminals.send", "terminals.wait"),
        aliases=("what does the terminal show", "terminal contents", "screen text"),
        examples=(Example(title="Screen of a titled terminal", input=_TARGET),),
        **_READ,
    ),
    Action(
        name="terminals.scrollback",
        family=VerbFamily.QUERY,
        summary="The last N lines of a terminal's history, screen, or last command output.",
        Input=ScrollbackInput,
        Output=TerminalText,
        handler=_scrollback,
        affordances=("terminals.screen", "terminals.send", "terminals.wait"),
        aliases=("history", "last output", "scroll back", "command output"),
        examples=(
            Example(title="Last 200 lines of history", input={**_TARGET, "lines": 200}),
            Example(
                title="Output of the last command",
                input={**_TARGET, "source": "last_command"},
            ),
        ),
        **_READ,
    ),
    Action(
        name="terminals.processes",
        family=VerbFamily.QUERY,
        summary="Foreground processes of one terminal and whether its shell is at a prompt.",
        Input=ProcessesInput,
        Output=TerminalProcesses,
        handler=_processes,
        affordances=("terminals.wait", "terminals.send"),
        aliases=("what is running", "is it busy", "terminal processes"),
        examples=(Example(title="Processes in a terminal", input=_TARGET),),
        **_READ,
    ),
    Action(
        name="terminals.send",
        family=VerbFamily.OPERATE,
        summary="Send text (optionally with Enter or bracketed paste) or key presses to one terminal.",
        Input=SendInput,
        Output=SendResult,
        handler=_send,
        affordances=("terminals.wait", "terminals.screen", "terminals.scrollback"),
        aliases=("type into terminal", "press keys", "ctrl+c", "send text"),
        examples=(
            Example(
                title="Send a line",
                input={
                    **_TARGET,
                    "input": {"kind": "text", "text": "status", "enter": True},
                    "idempotency_key": "send-1",
                },
            ),
            Example(
                title="Interrupt",
                input={
                    **_TARGET,
                    "input": {"kind": "keys", "keys": ["ctrl+c"]},
                    "idempotency_key": "send-2",
                },
            ),
        ),
        **_WRITE,
    ),
    Action(
        name="terminals.run",
        family=VerbFamily.RUN,
        summary="Run a command line in one terminal and, by default, wait for the prompt to return; reports last-command output, cwd and duration.",
        Input=RunInput,
        Output=RunResult,
        handler=_run,
        affordances=("terminals.scrollback", "terminals.wait", "terminals.send"),
        aliases=("execute in terminal", "run command", "shell command in kitty"),
        documentation="Completion and output rely on kitty shell integration (at_prompt, last_cmd_output). exit_status is reported only with capture_exit_status, which appends a visible marker to the command line.",
        examples=(
            Example(
                title="Run and wait",
                input={
                    **_TARGET,
                    "command": ["git", "status"],
                    "idempotency_key": "run-1",
                },
            ),
            Example(
                title="Run with exit status",
                input={
                    **_TARGET,
                    "command": "make test",
                    "capture_exit_status": True,
                    "timeout_seconds": 600,
                    "idempotency_key": "run-2",
                },
            ),
        ),
        **_WRITE,
    ),
    Action(
        name="terminals.wait",
        family=VerbFamily.WAIT,
        summary="Wait until a terminal is at its prompt, shows a regex, finishes a process, or changes title.",
        Input=WaitInput,
        Output=WaitResult,
        handler=_wait,
        affordances=("terminals.screen", "terminals.scrollback", "terminals.send"),
        aliases=("wait for prompt", "wait for output", "wait until done"),
        examples=(
            Example(
                title="Wait for the prompt",
                input={**_TARGET, "condition": {"kind": "prompt"}},
            ),
            Example(
                title="Wait for a pattern",
                input={
                    **_TARGET,
                    "condition": {"kind": "regex", "pattern": "done|completed"},
                    "timeout_seconds": 120,
                },
            ),
        ),
        **_READ,
    ),
    Action(
        name="terminals.focus",
        family=VerbFamily.OPERATE,
        summary="Focus one kitty window.",
        Input=FocusInput,
        Output=FocusResult,
        handler=_focus,
        affordances=("terminals.send", "terminals.screen"),
        aliases=("switch to terminal", "bring terminal to front"),
        examples=(
            Example(
                title="Focus by title", input={**_TARGET, "idempotency_key": "focus-1"}
            ),
        ),
        **_WRITE,
    ),
    Action(
        name="terminals.open",
        family=VerbFamily.OPERATE,
        summary="Open a new kitty window (OS window, split or tab) with an optional cwd and command; returns its ref.",
        Input=OpenInput,
        Output=OpenResult,
        handler=_open,
        affordances=(
            "terminals.send",
            "terminals.run",
            "terminals.screen",
            "terminals.focus",
        ),
        aliases=("new terminal", "open kitty", "spawn shell"),
        examples=(
            Example(
                title="New window in a project",
                input={"cwd": "/realm/project/sinnix", "idempotency_key": "open-1"},
            ),
            Example(
                title="Run a command in a new tab",
                input={
                    "placement": "tab",
                    "command": ["htop"],
                    "idempotency_key": "open-2",
                },
            ),
        ),
        **_WRITE,
    ),
)
