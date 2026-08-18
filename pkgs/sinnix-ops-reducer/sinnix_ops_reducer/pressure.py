"""What the machine's pressure actually is, measured the way the incidents were.

Every threshold and every column here comes from the 2026-08-18 clustering of
this host's own telemetry, and each exists because the obvious alternative was
measured and found to lie:

  * **Swap headroom is the early warning.** Across 29 freeze onsets, ten
    minutes before the machine froze the median swap was 90% consumed while
    available memory still read ~12.8 GiB. Every "used memory" or "available
    memory" gauge is blind to that, so swap headroom is the primary number and
    `mem_avail` is shown last, de-emphasised.
  * **`memory_psi_full` is the honest "is anything stalled".** 84% of the
    earlyoom kills since 2026-07-13 happened below PSI 10 -- the machine was
    working fine and the emergency responder killed the largest process anyway.
  * **A process table ordered by RSS lies.** `bd list` was measured at 8.19 GiB
    resident and 19.38 GiB swapped; anything ranking by RSS alone puts it below
    processes a tenth its size. Rows rank on RSS + swap, and swap is its own
    column.
  * **The cheapest kill is not the biggest process.** A runaway `rg` costs
    nothing to stop (the agent re-runs it, usually better scoped); a 40-minute
    pytest or a model server costs the whole job. That distinction is a column,
    because it is the one that turns the table into a decision.

The regimes are the measured clusters, not severity levels: they call for
different actions and some of them call for none at all.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from sinnix_lib.systemd import show_units

# --------------------------------------------------------------------------
# thresholds -- every one of them measured, none of them tuned by feel
# --------------------------------------------------------------------------

# Swap consumed. The median onset was preceded by 90% ten minutes out; 75% is
# the earliest line the record supports, and the point of the lane is lead time.
SWAP_PRE_FREEZE_PERCENT = 75.0
# memory PSI full: the share of the last ten seconds during which EVERY task
# was stalled. 20 is "degraded" in the incident inventory, 50 is "frozen".
MEMORY_STALL_PSI = 20.0
MEMORY_FROZEN_PSI = 50.0
# io PSI full at or above this is the IO-STALL class: disks saturated, memory
# untouched. Backups and scrubs, and they are scheduled rather than surprising.
IO_SATURATED_PSI = 40.0
# Available memory under this, with nothing stalling, is the spike shape: a
# single job allocating fast, page cache already surrendered, earlyoom's
# trigger zone. ~2 minutes from calm to kill, which is why it has no button.
SPIKE_MEM_AVAIL_MB = 2048

PROC = Path("/proc")

CHEAPNESS_RERUNNABLE = "re-runnable"
CHEAPNESS_EXPENSIVE = "expensive"
CHEAPNESS_SESSION = "session"
CHEAPNESS_UNKNOWN = "unclassified"

# Short-lived tool invocations an agent (or a person) issues and can issue
# again. Killing one costs a re-run, and the re-run is usually better scoped.
RERUNNABLE_COMMANDS = frozenset(
    {
        "ag",
        "ausearch",
        "awk",
        "bd",
        "cat",
        "diff",
        "du",
        "fd",
        "find",
        "grep",
        "git",
        "jq",
        "journalctl",
        "ls",
        "rg",
        "ripgrep",
        "sed",
        "sort",
        "systemctl",
        "tree",
        "ugrep",
        "wc",
        # The shell an agent harness spawns to run one of the above; measured
        # at 8.24 GiB resident and 15.87 GiB swapped as a Claude shell snapshot.
        "bash",
        "sh",
        "zsh",
    }
)

# Work whose loss is the point: a kill here throws away minutes to hours, or a
# resident model, or a pipeline stage that has to start over.
EXPENSIVE_COMMANDS = frozenset(
    {
        "cargo",
        "cc1",
        "cc1plus",
        "clang",
        "clang++",
        "comfyui",
        "ffmpeg",
        "g++",
        "gcc",
        "gradle",
        "java",
        "koboldcpp",
        "ld",
        "lld",
        "llama-server",
        "mypy",
        "nix",
        "nix-build",
        "nix-daemon",
        "ollama",
        "pytest",
        "python",
        "python3",
        "rustc",
        "sinexd",
        "tsc",
        "uv",
        "whisper",
        "yt-dlp",
    }
)

# The graphical session. Chrome renderers dominate any naive "top consumers"
# list and are never a cause: 26 of them were killed in six minutes on
# 2026-08-16 to free 1.7 GiB, after the job that actually filled memory had
# already died. Naming them as session work is how the table refuses to point
# the operator at a symptom.
SESSION_COMMANDS = frozenset(
    {
        "Hyprland",
        "Xwayland",
        "chrome",
        "chromium",
        "firefox",
        "kitten",
        "kitty",
        "noctalia-shell",
        "pipewire",
        "quickshell",
        "wireplumber",
        "xdg-desktop-portal",
    }
)

# Model servers and pipeline binaries whose real names carry a variant suffix
# (`sherpa-onnx-vad-with-offline-asr`, `llama-server-cuda`), and which /proc's
# `comm` truncates to fifteen characters anyway. Matched by prefix for exactly
# that reason: an exact-name set silently misses a resident 12.9 GiB model
# server, which is the most expensive thing on this machine to kill.
EXPENSIVE_PREFIXES = (
    "comfy",
    "kokoro",
    "llama-",
    "ollama",
    "sherpa-onnx",
    "vllm",
    "whisper",
)

# Slices whose whole purpose is to hold work that is expensive to lose and
# sacrificial to throttle. A tool invocation inside a build is part of the
# build, so the slice wins over the command name.
BUILD_SLICES = frozenset({"build.slice", "nix-build.slice"})

# Units whose runs are the scheduled IO pressure: predictable, so the page
# predicts rather than alarms.
SCHEDULED_UNIT_MARKERS = (
    "borgbackup",
    "borg-",
    "btrbk",
    "btrfs-scrub",
    "sqlite-backup",
)

SWAP_LANE_KEY = "pressure:swap-headroom"
SWAP_LANE_TYPE = "swap_headroom"
SWAP_LANE_UNIT = "swap headroom"


# --------------------------------------------------------------------------
# the sample
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Sample:
    """One reading of the four numbers that decide, and nothing else."""

    swap_used_mb: int | None = None
    swap_total_mb: int | None = None
    mem_avail_mb: int | None = None
    mem_total_mb: int | None = None
    memory_psi_full: float | None = None
    memory_psi_some: float | None = None
    io_psi_full: float | None = None
    cpu_psi_some: float | None = None

    @property
    def swap_percent(self) -> float | None:
        if not self.swap_total_mb or self.swap_used_mb is None:
            return None
        return self.swap_used_mb / self.swap_total_mb * 100.0

    @property
    def readable(self) -> bool:
        return any(
            value is not None
            for value in (
                self.swap_percent,
                self.memory_psi_full,
                self.io_psi_full,
                self.mem_avail_mb,
            )
        )


def read_psi(path: Path) -> dict[str, float]:
    """`some`/`full` avg10 out of one /proc/pressure file.

    A kernel without PSI, or a container without the file, yields an empty
    dict rather than zeros: "not measured" and "measured at zero" are opposite
    claims and only one of them is safe to act on.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    found: dict[str, float] = {}
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        for field in fields[1:]:
            key, separator, value = field.partition("=")
            if not separator or key != "avg10":
                continue
            try:
                found[fields[0]] = float(value)
            except ValueError:
                pass
    return found


def read_meminfo(path: Path) -> dict[str, int]:
    """/proc/meminfo as MiB, for the handful of keys this module reads."""
    wanted = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}
    found: dict[str, int] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    for line in text.splitlines():
        key, separator, rest = line.partition(":")
        if not separator or key not in wanted:
            continue
        fields = rest.split()
        if not fields:
            continue
        try:
            found[key] = int(fields[0]) // 1024
        except ValueError:
            continue
    return found


def sample(proc: Path = PROC) -> Sample:
    memory = read_psi(proc / "pressure" / "memory")
    io = read_psi(proc / "pressure" / "io")
    cpu = read_psi(proc / "pressure" / "cpu")
    meminfo = read_meminfo(proc / "meminfo")
    swap_total = meminfo.get("SwapTotal")
    swap_free = meminfo.get("SwapFree")
    return Sample(
        swap_used_mb=(
            swap_total - swap_free
            if swap_total is not None and swap_free is not None
            else None
        ),
        swap_total_mb=swap_total,
        mem_avail_mb=meminfo.get("MemAvailable"),
        mem_total_mb=meminfo.get("MemTotal"),
        memory_psi_full=memory.get("full"),
        memory_psi_some=memory.get("some"),
        io_psi_full=io.get("full"),
        cpu_psi_some=cpu.get("some"),
    )


# --------------------------------------------------------------------------
# the regime
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Regime:
    name: str
    cluster: str
    tone: str
    headline: str
    detail: str


def classify(reading: Sample) -> Regime:
    """Which measured cluster the machine is in right now.

    Order is severity of the *response*, not of the number: swap saturation is
    checked first because it is the one state where ten minutes of warning
    exist and a decision is worth making, and it co-occurs with IO saturation
    often enough that reporting the disks would bury it.
    """
    if not reading.readable:
        return Regime(
            "UNKNOWN",
            "",
            "muted",
            "Pressure could not be read",
            "Neither /proc/pressure nor /proc/meminfo answered, so this page is "
            "not saying the machine is fine — it is saying it does not know.",
        )
    swap = reading.swap_percent
    memory_full = reading.memory_psi_full
    io_full = reading.io_psi_full
    available = reading.mem_avail_mb

    if (swap is not None and swap >= SWAP_PRE_FREEZE_PERCENT) or (
        memory_full is not None and memory_full >= MEMORY_STALL_PSI
    ):
        frozen = memory_full is not None and memory_full >= MEMORY_FROZEN_PSI
        stalling = memory_full is not None and memory_full >= MEMORY_STALL_PSI
        if frozen:
            detail = (
                f"Every task is stalled ({memory_full:.0f}% of the last ten "
                "seconds). This is the freeze itself, not the warning before "
                "it; the machine will survive it and stay unusable for as long "
                "as the load stays."
            )
        elif stalling:
            detail = (
                f"Tasks are already stalling on memory ({memory_full:.0f}% "
                "full PSI). Refaults, not exhaustion — earlyoom will stay "
                "silent through this because available memory looks fine."
            )
        else:
            detail = (
                "Nothing is stalling yet. On the measured record this state "
                "runs about ten minutes ahead of a multi-hour freeze, and the "
                "decision it needs — which agent lane is expendable — is not "
                "one the machine can make."
            )
        return Regime(
            "SWAP-CRITICAL",
            "C1",
            "bad",
            "Swap headroom is nearly gone",
            detail,
        )

    if available is not None and available < SPIKE_MEM_AVAIL_MB:
        return Regime(
            "SPIKE",
            "C2",
            "warn",
            "One job is allocating fast",
            f"{available} MiB available with nothing stalling: page cache has "
            "already been surrendered and swap is taking the rest, which is "
            "what a tiered swap posture is for. It is also earlyoom's trigger "
            "zone — measured lead time from calm to kill is about two minutes, "
            "so no button on this page is fast enough to matter.",
        )

    if io_full is not None and io_full >= IO_SATURATED_PSI:
        return Regime(
            "IO-SATURATED",
            "C5",
            "warn",
            "The disks are saturated and memory is fine",
            f"IO full PSI {io_full:.0f}% with memory untouched. This is a "
            "backup, a scrub or a database dump — scheduled work, listed "
            "below, and parkable with a deadline rather than a surprise.",
        )

    return Regime(
        "CALM",
        "",
        "ok",
        "Nothing is under pressure",
        "Swap has headroom, nothing is stalling on memory, and the disks are "
        "keeping up.",
    )


# --------------------------------------------------------------------------
# the swap-headroom health lane
# --------------------------------------------------------------------------


def swap_lane_status(reading: Sample) -> tuple[str, str] | None:
    """(status, evidence) for the swap-headroom lane, or None if unmeasurable.

    Three states, because swap headroom being gone has two very different
    meanings and calling either of them healthy would be a lie:

      * `pre-freeze` -- swap at or past 75% while memory PSI full is still
        below 20. This is the pair the whole lane exists for: the warning has
        arrived and the machine still works, so a decision is possible.
      * `stalled` -- swap saturated AND tasks already stalling. The warning is
        late; this is the freeze.
      * `healthy` -- swap has headroom.
    """
    percent = reading.swap_percent
    if percent is None:
        return None
    evidence = (
        f"swap_percent={percent:.1f};"
        f"swap_used_mb={reading.swap_used_mb};"
        f"swap_total_mb={reading.swap_total_mb};"
        f"memory_psi_full={'null' if reading.memory_psi_full is None else reading.memory_psi_full};"
        f"mem_avail_mb={'null' if reading.mem_avail_mb is None else reading.mem_avail_mb};"
        f"pre_freeze_percent={SWAP_PRE_FREEZE_PERCENT};"
        f"stall_psi={MEMORY_STALL_PSI}"
    )
    if percent < SWAP_PRE_FREEZE_PERCENT:
        return "healthy", evidence
    if (
        reading.memory_psi_full is not None
        and reading.memory_psi_full >= MEMORY_STALL_PSI
    ):
        return "stalled", evidence
    return "pre-freeze", evidence


def sweep_swap_headroom(reading: Sample, emitter: Any) -> None:
    """The lane, on the health sweep's own tick and through its own emitter.

    Deliberately not a second mechanism: it shares the confirm-2 debounce, the
    `sinnix-health-transition-v1` ledger, the dedup state file, and the
    notification rules with every other lane. A machine with no swap
    configured registers the key without judging it, so the sweep's prune does
    not treat the lane as one it no longer emits.
    """
    verdict = swap_lane_status(reading)
    if verdict is None:
        emitter.observe(SWAP_LANE_KEY)
        return
    status, evidence = verdict
    emitter.emit(SWAP_LANE_KEY, SWAP_LANE_TYPE, SWAP_LANE_UNIT, status, evidence)


# --------------------------------------------------------------------------
# the process table
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Process:
    pid: int
    comm: str
    command: str
    rss_kb: int
    swap_kb: int
    unit: str
    slice_unit: str
    start_ticks: int
    cheapness: str

    @property
    def footprint_kb(self) -> int:
        return self.rss_kb + self.swap_kb


VERSION_SUFFIX = re.compile(r"[-_.0-9]+$")


def classify_cheapness(names: Iterable[str], slice_unit: str) -> str:
    """What a kill would cost, from process identity plus where it is placed.

    Placement outranks the command name in exactly one direction: a `git` or a
    `python` inside a build slice is part of a build, and killing it throws
    away the build rather than costing a re-run.

    Names are compared with their version tail stripped as well as whole, or
    `python3.14` -- the interpreter every heavy tool on this host actually runs
    as -- would fall through to unclassified.
    """
    candidates: set[str] = set()
    for name in names:
        if not name:
            continue
        candidates.add(name)
        stripped = VERSION_SUFFIX.sub("", name)
        if stripped:
            candidates.add(stripped)
    if candidates & EXPENSIVE_COMMANDS:
        return CHEAPNESS_EXPENSIVE
    if any(name.startswith(EXPENSIVE_PREFIXES) for name in candidates):
        return CHEAPNESS_EXPENSIVE
    if slice_unit in BUILD_SLICES:
        return CHEAPNESS_EXPENSIVE
    if candidates & SESSION_COMMANDS:
        return CHEAPNESS_SESSION
    if candidates & RERUNNABLE_COMMANDS:
        return CHEAPNESS_RERUNNABLE
    return CHEAPNESS_UNKNOWN


def parse_cgroup(text: str) -> tuple[str, str]:
    """(owning unit, owning slice) out of a cgroup v2 membership line."""
    parts = [part for part in text.strip().split("\n") if part][:1]
    if not parts:
        return "", ""
    path = parts[0].rpartition(":")[2]
    unit = ""
    slice_unit = ""
    for segment in path.split("/"):
        if segment.endswith((".scope", ".service")):
            unit = segment
        elif segment.endswith(".slice"):
            slice_unit = segment
    return unit, slice_unit


def _memory_fields(text: str) -> tuple[str, int, int] | None:
    name = ""
    rss = None
    swap = 0
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        if key == "Name":
            name = value.strip()
        elif key == "VmRSS":
            rss = int(value.split()[0])
        elif key == "VmSwap":
            swap = int(value.split()[0])
        elif key == "Threads":
            break
    # No VmRSS at all means a kernel thread: no address space, nothing to rank.
    return (name, rss, swap) if rss is not None else None


def _command_of(raw: bytes) -> tuple[str, str]:
    """(argv0 basename, readable command line) from /proc/<pid>/cmdline."""
    parts = [part for part in raw.decode("utf-8", "replace").split("\0") if part]
    if not parts:
        return "", ""
    base = os.path.basename(parts[0])
    text = " ".join([base, *parts[1:]])
    return base, text if len(text) <= 88 else text[:85] + "…"


def scan_processes(limit: int = 12, proc: Path = PROC) -> list[Process]:
    """The `limit` largest anonymous footprints, ranked on RSS + swap.

    Two phases on purpose, and this is the whole reason the page can be
    rendered on request rather than off a cached tick: every process is read
    once for its memory fields (~19 ms for ~870 processes on this host), and
    only the survivors pay for cgroup, cmdline and start-time reads.
    """
    coarse: list[tuple[int, str, int, int]] = []
    try:
        entries = os.listdir(proc)
    except OSError:
        return []
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            fields = _memory_fields(
                (proc / entry / "status").read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            continue
        if fields is None:
            continue
        name, rss, swap = fields
        coarse.append((int(entry), name, rss, swap))
    coarse.sort(key=lambda item: item[2] + item[3], reverse=True)

    found: list[Process] = []
    for pid, name, rss, swap in coarse[:limit]:
        directory = proc / str(pid)
        try:
            unit, slice_unit = parse_cgroup(
                (directory / "cgroup").read_text(encoding="utf-8")
            )
        except OSError:
            unit, slice_unit = "", ""
        try:
            base, command = _command_of((directory / "cmdline").read_bytes())
        except OSError:
            base, command = "", ""
        found.append(
            Process(
                pid=pid,
                comm=name,
                command=command or name,
                rss_kb=rss,
                swap_kb=swap,
                unit=unit,
                slice_unit=slice_unit,
                # The PID-reuse pin: a process-level action (which the action
                # API does not have yet) has to name both, and reporting it
                # here is what makes the row quotable into one.
                start_ticks=_start_ticks(directory),
                cheapness=classify_cheapness({name, base}, slice_unit),
            )
        )
    return found


def _start_ticks(directory: Path) -> int:
    try:
        text = (directory / "stat").read_text(encoding="utf-8")
    except OSError:
        return 0
    # comm sits in parentheses and may contain spaces: split after it.
    tail = text.rpartition(")")[2].split()
    try:
        return int(tail[19])
    except (IndexError, ValueError):
        return 0


# --------------------------------------------------------------------------
# scheduled pressure
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ScheduledRun:
    timer: str
    unit: str
    next_seconds: float | None
    last_seconds: float | None
    last_duration_seconds: float | None = None
    active: bool = False


def select_scheduled(
    entries: Sequence[dict[str, Any]], now_us: int, limit: int = 8
) -> list[ScheduledRun]:
    """The backup/scrub/dump timers, soonest first.

    Filtered by unit name rather than by resource class because the class only
    covers what the runtime inventory declares, and the btrfs scrub timers --
    16.72 TiB over seven days on one drive, the second-largest IO source
    measured -- are generated by nixpkgs and are in no sinnix surface at all.
    Leaving them out because they have no button would hide exactly the run
    the operator most wants warning of.
    """
    found: list[ScheduledRun] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        timer = str(entry.get("unit") or "")
        unit = str(entry.get("activates") or "")
        if not any(marker in timer for marker in SCHEDULED_UNIT_MARKERS):
            continue
        next_us = entry.get("next")
        last_us = entry.get("last")
        found.append(
            ScheduledRun(
                timer=timer,
                unit=unit,
                next_seconds=(
                    (int(next_us) - now_us) / 1e6 if isinstance(next_us, int) else None
                ),
                last_seconds=(
                    (now_us - int(last_us)) / 1e6
                    if isinstance(last_us, int) and last_us > 0
                    else None
                ),
            )
        )
    found.sort(
        key=lambda run: (
            run.next_seconds is None,
            run.next_seconds if run.next_seconds is not None else 0.0,
        )
    )
    return found[:limit]


def list_timers() -> list[dict[str, Any]]:
    """systemd's own timer table. Read on request; it is one call and the
    manager already holds the answer."""
    try:
        result = subprocess.run(
            [
                "systemctl",
                "--system",
                "list-timers",
                "--all",
                "-o",
                "json",
                "--no-pager",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    try:
        value = json.loads(result.stdout or "[]")
    except ValueError:
        return []
    return [entry for entry in value if isinstance(entry, dict)]


# `Id` is not decoration: show_units keys its result by it, so a property list
# without it parses into nothing at all.
RUN_PROPERTIES = (
    "Id",
    "ActiveState",
    "InactiveExitTimestampMonotonic",
    "InactiveEnterTimestampMonotonic",
)


def unit_run_facts(
    units: Sequence[str],
    show: Callable[..., dict[str, dict[str, str]]] | None = None,
) -> dict[str, dict[str, Any]]:
    """How long each unit's last run took, and whether it is running now.

    Both matter to the strip and for opposite reasons. The historical duration
    is why the strip is worth reading -- a timer firing in nine minutes means
    something different if its last run took four seconds than if it took five
    hours. The live state decides whether `park` is offered at all: park
    freezes the unit's cgroup, and an inactive unit has none, so the action
    would succeed while freezing nothing.
    """
    if not units:
        return {}
    prober = show or show_units
    states = prober(list(units), user=False, properties=RUN_PROPERTIES)
    found: dict[str, dict[str, Any]] = {}
    for unit, properties in states.items():
        duration: float | None = None
        try:
            start = int(properties.get("InactiveExitTimestampMonotonic", "0"))
            end = int(properties.get("InactiveEnterTimestampMonotonic", "0"))
        except (TypeError, ValueError):
            start, end = 0, 0
        if start > 0 and end > start:
            duration = (end - start) / 1e6
        found[unit] = {
            "last_duration_seconds": duration,
            "active": properties.get("ActiveState") in {"active", "activating"},
        }
    return found


SCOPE_IDENTITY = re.compile(
    r"^sinnix-(?P<klass>agent|build|background|gpu-runtime|nix-build|system)"
    r"-(?P<identity>[A-Za-z0-9_.-]{1,40})-\d+-\d+\.scope$"
)
AGENT_JOB_SCOPE = re.compile(r"^sinnix-agent-job-(?P<job>.+)\.scope$")


def lane_of(
    unit: str,
    jobs_by_id: dict[str, dict[str, Any]] | None = None,
    scopes_by_unit: dict[str, dict[str, Any]] | None = None,
) -> str:
    """A scope unit resolved to the lane a human recognises.

    The launcher encodes the command's own name in the unit
    (`sinnix-<class>-<identity>-<epoch_ns>-<pid>.scope`) and the gateway
    carries a full job manifest, so the digits never have to be shown: an
    operator being asked which lane is expendable cannot answer about
    `sinnix-agent-1785530197414290568-596681.scope`.
    """
    if not unit:
        return ""
    job_match = AGENT_JOB_SCOPE.match(unit)
    if job_match:
        job = (jobs_by_id or {}).get(job_match.group("job"))
        if isinstance(job, dict):
            worktree = str(job.get("worktree") or "")
            where = Path(worktree).name if worktree else ""
            named = " ".join(
                part
                for part in (
                    str(job.get("backend") or "agent"),
                    str(job.get("model") or ""),
                )
                if part
            )
            return f"{named} in {where}" if where else named
        return f"gateway job {job_match.group('job')}"
    scope_match = SCOPE_IDENTITY.match(unit)
    if scope_match:
        klass = scope_match.group("klass")
        placed = (scopes_by_unit or {}).get(unit)
        if isinstance(placed, dict):
            # The checkout the scope was launched in is what distinguishes two
            # agent lanes from each other; the command is already the row's own
            # headline, so repeating it here would cost a column and say
            # nothing.
            if placed.get("project"):
                return f"{klass} · {placed['project']}"
            if placed.get("command"):
                return f"{klass} · {placed['command']}"
        return f"{klass} · {scope_match.group('identity')}"
    return unit
