"""Live host probes the pages need and the reducer's snapshot does not carry.

Ported verbatim from the retired render-on-timer job: systemd unit and
scope enumeration, the launch-line reducer that turns a wrapped `sinnix-scope`
command back into the verb the operator typed, and nvidia-smi's one-line GPU
summary. These run on request now rather than on a 60s timer, so the numbers a
page prints are the numbers at the moment it was asked for.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

from .shell import as_int

# Transient scopes sinnix creates on purpose. Agent-gateway jobs carry a
# job id and are drivable through the reducer via the job_id target; plain
# sinnix-scope placements are drivable too (sinnix-pl37), via the reducer's
# scope target -- name-shape plus live-state admission, stop only.
AGENT_JOB_PREFIX = "sinnix-agent-job-"
SCOPE_PREFIX = "sinnix-"

# Command classes that mean "heavy work is happening", as opposed to an agent
# session that is mostly idle waiting on a model.
HEAVY_CLASSES = {"build", "nix-build", "heavy"}


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"{path} does not exist"
    except OSError as error:
        return None, f"{path} unreadable: {error}"
    except json.JSONDecodeError as error:
        return None, f"{path} is not valid JSON: {error}"
    if not isinstance(value, dict):
        return None, f"{path} is not a JSON object"
    return value, None


def systemctl(manager: str, *arguments: str, timeout: int = 15) -> str | None:
    binary = shutil.which("systemctl") or "systemctl"
    scope = "--user" if manager == "user" else "--system"
    try:
        result = subprocess.run(
            [binary, scope, *arguments],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout


def show_units(manager: str, units: Iterable[str], properties: Iterable[str]) -> dict[str, dict[str, str]]:
    """`systemctl show` a batch of units, keyed by unit id.

    The manager matters: asking the system manager about a user unit reports
    not-found, which would render as "not installed" and hide a service that is
    running perfectly well.
    """
    names = [unit for unit in units if unit]
    if not names:
        return {}
    output = systemctl(
        manager,
        "show",
        *(f"--property={name}" for name in ("Id", *properties)),
        *names,
    )
    if output is None:
        return {}
    states: dict[str, dict[str, str]] = {}
    current: dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            if current.get("Id"):
                states[current["Id"]] = current
            current = {}
            continue
        key, _, value = line.partition("=")
        current[key] = value
    if current.get("Id"):
        states[current["Id"]] = current
    return states


UNIT_PROPERTIES = ("ActiveState", "SubState", "UnitFileState", "LoadState")
SCOPE_PROPERTIES = (
    "Description",
    "ActiveState",
    "Slice",
    "ControlGroup",
    "MemoryCurrent",
    "MemoryHigh",
    "MemoryMax",
    "ActiveEnterTimestampMonotonic",
)


def unit_states(units: list[tuple[str, str]]) -> dict[str, dict[str, str]]:
    states: dict[str, dict[str, str]] = {}
    for manager in {manager for manager, _ in units}:
        states.update(
            show_units(
                manager,
                [unit for owner, unit in units if owner == manager],
                UNIT_PROPERTIES,
            )
        )
    return states


def monotonic_now_us() -> int | None:
    try:
        with open("/proc/uptime", encoding="utf-8") as handle:
            return int(float(handle.read().split()[0]) * 1_000_000)
    except (OSError, ValueError, IndexError):
        return None


def gpu_summary() -> str | None:
    nvidia = shutil.which("nvidia-smi")
    if not nvidia:
        return None
    try:
        result = subprocess.run(
            [
                nvidia,
                "--query-gpu=memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    line = result.stdout.strip().splitlines()
    return line[0].strip() if line else None


def command_classes(inventory: dict[str, Any] | None) -> list[str]:
    if isinstance(inventory, dict) and isinstance(inventory.get("commandClasses"), dict):
        names = [name for name in inventory["commandClasses"] if isinstance(name, str)]
        if names:
            return sorted(names, key=len, reverse=True)
    return ["nix-build", "background", "gpu-runtime", "build", "agent", "heavy"]


def scope_class(unit: str, classes: list[str]) -> str | None:
    body = unit[len(SCOPE_PREFIX) :]
    for name in classes:
        if body.startswith(f"{name}-"):
            return name
    return None


def cgroup_leader(control_group: str) -> tuple[str | None, str | None]:
    """The scope's first process, used only to *name* the workload.

    A scope's systemd Description is the `systemd-run` command line, which for
    a wrapped launch is a store path plus an env prefix -- unreadable. The
    leader's own cmdline and cwd say what is actually running and where, which
    is what turns "some scope" into "sinex is compiling".
    """
    if not control_group:
        return None, None
    procs = Path("/sys/fs/cgroup") / control_group.lstrip("/") / "cgroup.procs"
    try:
        pids = procs.read_text(encoding="utf-8").split()
    except OSError:
        return None, None
    for pid in pids[:4]:
        try:
            cwd = os.readlink(f"/proc/{pid}/cwd")
            raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        except OSError:
            continue
        parts = [part for part in raw.decode("utf-8", "replace").split("\0") if part]
        if not parts:
            continue
        return " ".join(parts), cwd
    return None, None


def project_of(path: str | None) -> str | None:
    if not path:
        return None
    parts = Path(path).parts
    for anchor in ("project", "worktrees"):
        if anchor in parts:
            index = parts.index(anchor)
            if index + 1 < len(parts):
                return parts[index + 1]
    return None


# Launch wrappers that stand between `sinnix-scope` and the command the
# operator actually typed. Stripping them is what turns
# "…/coreutils/bin/env SINNIX_AGENT_SCOPED=1 … nice -n 10 ionice -c 3 -- xtask test"
# into "xtask test".
WRAPPER_BINARIES = {"env", "nice", "ionice", "setsid", "stdbuf", "chrt", "time"}


def shorten_command(command: str | None) -> str:
    """Reduce a launch line to the verb the operator recognises."""
    if not command:
        return "unnamed command"
    parts = command.split()
    while parts:
        head = parts[0]
        base = Path(head).name
        if head in {"--", "--internal-supervise"}:
            parts.pop(0)
            continue
        if "=" in head and not head.startswith("-") and "/" not in head.split("=", 1)[0]:
            parts.pop(0)
            continue
        if (
            base in {"bash", "sh", "dash", "zsh"}
            and len(parts) > 1
            # a store path's basename is hash-prefixed, so match on containment
            and "sinnix-scope" in Path(parts[1]).name
        ):
            parts = parts[2:]
            continue
        if base.startswith("sinnix-scope") or base in WRAPPER_BINARIES:
            parts.pop(0)
            # eat that wrapper's own options (`-n 10`, `-c 3 -n 7`), never the
            # target's: this only runs directly after a known wrapper.
            while (
                len(parts) > 1
                and parts[0] != "--"
                and parts[0].startswith("-")
                and len(parts[0]) == 2
            ):
                parts = parts[2:]
            continue
        if base == "nix" and parts[1:3] == ["develop", "--command"]:
            parts = parts[3:]
            continue
        break
    if not parts:
        return "unnamed command"
    parts[0] = Path(parts[0]).name
    # Long absolute paths are the reason these lines wrap to three lines on a
    # phone, and their middle is never the informative part.
    parts = [abbreviate_path(part) for part in parts]
    text = " ".join(parts)
    return text if len(text) <= 76 else text[:73] + "…"


def abbreviate_path(token: str) -> str:
    if len(token) <= 30 or token.count("/") < 2:
        return token
    tail = Path(token).parts[-2:]
    return "…/" + "/".join(tail)


def collect_scopes(inventory: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Every live sinnix-placed transient scope, named and measured."""
    classes = command_classes(inventory)
    monotonic = monotonic_now_us()
    found: list[dict[str, Any]] = []
    for manager in ("user", "system"):
        listing = systemctl(manager, "list-units", "--type=scope", "--state=active", "-o", "json", "--no-pager")
        if not listing:
            continue
        try:
            units = json.loads(listing)
        except json.JSONDecodeError:
            continue
        names = [
            entry.get("unit")
            for entry in units
            if isinstance(entry, dict)
            and isinstance(entry.get("unit"), str)
            and entry["unit"].startswith(SCOPE_PREFIX)
        ]
        for unit, info in show_units(manager, names, SCOPE_PROPERTIES).items():
            started = as_int(info.get("ActiveEnterTimestampMonotonic"))
            elapsed = (
                (monotonic - started) / 1_000_000
                if monotonic is not None and started is not None and started > 0
                else None
            )
            job_id = (
                unit[len(AGENT_JOB_PREFIX) : -len(".scope")]
                if unit.startswith(AGENT_JOB_PREFIX) and unit.endswith(".scope")
                else None
            )
            command, cwd = cgroup_leader(info.get("ControlGroup", ""))
            found.append(
                {
                    "unit": unit,
                    "manager": manager,
                    "job_id": job_id,
                    "class": None if job_id else scope_class(unit, classes),
                    "slice": info.get("Slice"),
                    "memory": as_int(info.get("MemoryCurrent")),
                    "memory_high": as_int(info.get("MemoryHigh")),
                    "memory_max": as_int(info.get("MemoryMax")),
                    "elapsed": elapsed,
                    "command": shorten_command(command),
                    "cwd": cwd,
                    "project": project_of(cwd),
                }
            )
    found.sort(key=lambda item: item.get("elapsed") or 0, reverse=True)
    return found

