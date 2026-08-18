#!/usr/bin/env python3
"""State classifier for launch_agent_tabs.sh's --status/--tails reporting.

Extracted 1:1 from the bash implementation (sinnix-3pjj): groups relaunch log
generations (<task>.resume-N.log, <task>.headless-N.log, <task>.phase-N.log,
<task>.review-N.log) onto their base task name, finds each task's newest log,
and classifies RUNNING/DONE/FAILED/STALE the same way the shell version did --
RUNNING requires a live process holding the log open (evidence via `fuser`,
falling back to a /proc/*/fd scan only when `fuser` itself is not on PATH),
never inferred from marker absence. A log with no writer and no exit marker
is STALE.

This module owns state classification and rendering (colors, column widths,
tail formatting) byte-for-byte matching the retired bash block; the shell
entrypoint stays a thin dispatcher that execs into this for --status/--tails
and keeps the launch-orchestration half itself.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

GEN_SUFFIXES = (".headless-", ".resume-", ".phase-", ".review-")


def strip_generation_suffixes(task_name: str) -> str:
    """Collapse a relaunch generation's log basename onto its base task name.

    Mirrors bash's `${v%.headless-*}` chain: each suffix is removed once, at
    its FIRST occurrence (shortest trailing match), in this fixed order.
    """
    for suffix in GEN_SUFFIXES:
        idx = task_name.find(suffix)
        if idx != -1:
            task_name = task_name[:idx]
    return task_name


def fmt_dur(seconds: int) -> str:
    if seconds < 0:
        seconds = 0
    if seconds >= 3600:
        return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"
    if seconds >= 60:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds}s"


_HAS_FUSER = shutil.which("fuser") is not None


def log_writer_pid(path: Path) -> str | None:
    """The pid currently holding `path` open, or None. `fuser`-based when
    available (the sole source bash consulted); only falls back to a raw
    /proc/*/fd scan when fuser itself is missing from PATH -- a `fuser` call
    that finds no writer is authoritative and does NOT fall back."""
    if _HAS_FUSER:
        try:
            proc = subprocess.run(
                ["fuser", str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if proc.returncode != 0:
            return None
        tokens = proc.stdout.split()
        return tokens[0] if tokens else None

    try:
        target = os.path.realpath(path)
    except OSError:
        return None
    try:
        pid_dirs = [e for e in os.scandir("/proc") if e.name.isdigit()]
    except OSError:
        return None
    for entry in pid_dirs:
        fd_dir = os.path.join(entry.path, "fd")
        try:
            fds = os.listdir(fd_dir)
        except OSError:
            continue
        for fd in fds:
            try:
                link = os.readlink(os.path.join(fd_dir, fd))
            except OSError:
                continue
            if link == target:
                return entry.name
    return None


def ps_etimes(pid: str) -> str | None:
    try:
        proc = subprocess.run(
            ["ps", "-o", "etimes=", "-p", pid],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except OSError:
        return None
    etimes = proc.stdout.strip()
    return etimes or None


def du_h(path: Path) -> str:
    try:
        proc = subprocess.run(
            ["du", "-h", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except OSError:
        return "?"
    fields = proc.stdout.split()
    return fields[0] if fields else "?"


class Colors:
    def __init__(self, enabled: bool):
        if enabled:
            self.grn, self.red, self.yel, self.cyn = (
                "\033[32m",
                "\033[31m",
                "\033[33m",
                "\033[36m",
            )
            self.dim, self.bld, self.off = "\033[2m", "\033[1m", "\033[0m"
        else:
            self.grn = self.red = self.yel = self.cyn = self.dim = self.bld = (
                self.off
            ) = ""

    def state(self, s: str) -> str:
        return {"RUNNING": self.cyn, "DONE": self.grn, "FAILED": self.red}.get(
            s, self.yel
        )


def color_enabled() -> bool:
    if os.environ.get("FORCE_COLOR"):
        return True
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


class Task:
    __slots__ = ("name", "log", "mtime", "state", "run", "idle", "detail")

    def __init__(self, name: str):
        self.name = name
        self.log: str | None = None
        self.mtime: int | None = None
        self.state = ""
        self.run = "-"
        self.idle = "-"
        self.detail = ""


def discover_tasks(output_dir: Path) -> dict[str, Task]:
    tasks: dict[str, Task] = {}
    newest_mtime: dict[str, int] = {}

    for log_file in sorted(glob.glob(str(output_dir / "*.log"))):
        base = Path(log_file).name[: -len(".log")]
        task_name = strip_generation_suffixes(base)
        try:
            mtime = int(os.stat(log_file).st_mtime)
        except OSError:
            mtime = 0
        if task_name not in newest_mtime or mtime > newest_mtime[task_name]:
            newest_mtime[task_name] = mtime
            t = tasks.setdefault(task_name, Task(task_name))
            t.log = log_file
            t.mtime = mtime
        else:
            tasks.setdefault(task_name, Task(task_name))

    for exit_file in sorted(glob.glob(str(output_dir / "*.exit"))):
        task_name = Path(exit_file).name[: -len(".exit")]
        tasks.setdefault(task_name, Task(task_name))

    return tasks


def classify(task: Task, output_dir: Path, now: int) -> None:
    exit_file = output_dir / f"{task.name}.exit"
    writer = log_writer_pid(Path(task.log)) if task.log else None
    if task.log and writer:
        etimes = ps_etimes(writer)
        task.run = fmt_dur(int(etimes)) if etimes else "-"
        task.idle = fmt_dur(now - (task.mtime if task.mtime is not None else now))
        task.state = "RUNNING"
        task.detail = f"log {du_h(Path(task.log))} ({Path(task.log).name})"
        return

    if exit_file.exists():
        ec = exit_file.read_text().strip()
        try:
            finished_ago = fmt_dur(now - int(exit_file.stat().st_mtime))
        except OSError:
            finished_ago = "-"
        task.idle = finished_ago
        if ec == "0":
            task.state = "DONE"
            task.detail = str(output_dir / f"{task.name}.last.md")
        else:
            task.state = "FAILED"
            task.detail = f"exit={ec} {task.log or output_dir / f'{task.name}.log'}"
        return

    task.state = "STALE"
    task.idle = fmt_dur(now - (task.mtime if task.mtime is not None else now))
    log_base = Path(task.log).name if task.log else "none"
    task.detail = f"no live process, no exit marker ({log_base})"


def render_status(tasks: dict[str, Task], output_dir: Path, c: Colors) -> int:
    all_tasks = sorted(tasks)
    if not all_tasks:
        print(f"(no task artifacts in {output_dir})")
        return 0

    print(f"{c.bld}{'TASK':<34} {'STATE':<8} {'RUN':>8} {'IDLE':>8}  DETAIL{c.off}")
    counts: dict[str, int] = {}
    for name in all_tasks:
        t = tasks[name]
        counts[t.state] = counts.get(t.state, 0) + 1
        print(
            f"{t.name:<34} {c.state(t.state)}{t.state:<8}{c.off} "
            f"{t.run:>8} {t.idle:>8}  {c.dim}{t.detail}{c.off}"
        )
    summary = "  ".join(
        f"{s.lower()} {counts[s]}"
        for s in ("RUNNING", "DONE", "FAILED", "STALE")
        if s in counts
    )
    if summary:
        summary += "  "
    print(f"{c.dim}{summary}{c.off}")
    return 0


def render_tails(
    tasks: dict[str, Task],
    output_dir: Path,
    c: Colors,
    tails_n: int,
    tails_all: bool,
    requested: list[str],
) -> int:
    all_tasks = sorted(tasks)
    tail_tasks = requested if requested else all_tasks
    shown = 0
    for name in tail_tasks:
        t = tasks.get(name)
        if t is None:
            print(f"unknown task: {name}", file=sys.stderr)
            continue
        if t.state != "RUNNING" and not tails_all:
            continue
        src = t.log
        last_md = output_dir / f"{t.name}.last.md"
        if t.state == "DONE" and last_md.exists():
            src = str(last_md)
        src_base = Path(src).name if src else "none"
        print(
            f"{c.bld}── {c.state(t.state)}{t.name} {c.off}{c.dim}"
            f"({t.state}, run {t.run}, idle {t.idle} — {src_base}){c.off}"
        )
        if src and Path(src).exists():
            with open(src, "r", errors="replace") as fh:
                lines = fh.readlines()
            tail_lines = lines[-tails_n:] if tails_n > 0 else []
            for line in tail_lines:
                print(f"  {line.rstrip(chr(10))}")
        print()
        shown += 1
    if shown == 0:
        print("(no matching tasks to tail; use --tails-all for finished ones)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", required=True, type=Path)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--tails", action="store_true")
    ap.add_argument("--tails-n", type=int, default=12)
    ap.add_argument("--tails-all", action="store_true")
    ap.add_argument("tasks", nargs="*")
    args = ap.parse_args()

    output_dir: Path = args.output_dir
    tasks = discover_tasks(output_dir)
    now = int(time.time())
    for t in tasks.values():
        classify(t, output_dir, now)

    c = Colors(color_enabled())
    if args.tails:
        return render_tails(
            tasks, output_dir, c, args.tails_n, args.tails_all, args.tasks
        )
    return render_status(tasks, output_dir, c)


if __name__ == "__main__":
    sys.exit(main())
