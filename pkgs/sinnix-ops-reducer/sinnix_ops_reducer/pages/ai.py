"""The /ai/ page: local AI backends, their activation semantics, and GPU admission."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .probes import gpu_summary, monotonic_now_us, show_units, unit_states
from .services import lifecycle_controls, unit_status
from .shell import (
    ACTION_SCRIPT,
    as_int,
    badge,
    card,
    duration_human,
    empty,
    esc,
    log_card,
    page,
    row,
    tile,
)

# --------------------------------------------------------------------------
# GPU admission (gpu-inference key): who is resident, how much VRAM they
# measurably hold, who evicted whom, and the live exclusivity mesh.
#
# Everything below reads systemd and nvidia-smi directly. It never restates
# a Nix source's *declared* exclusiveResource/Conflicts= as if wiring made
# it true -- ai-control.nix and each backend's own module own that wiring;
# this only reports what the running host currently does.
# --------------------------------------------------------------------------

GPU_ADMISSION_KEY = "gpu-inference"
GPU_STATE_PROPERTIES = (
    "ActiveState",
    "LoadState",
    "ControlGroup",
    "ActiveEnterTimestampMonotonic",
    "Conflicts",
)
# Bounded lookback and event cap: eviction history reads real journal
# entries, but a query with no ceiling on either axis is a query that can
# make this render slow (or unbounded) on a host with noisy backends.
GPU_EVICTION_SINCE = "2 days ago"
GPU_EVICTION_MAX_EVENTS = 500
GPU_EVICTION_ROWS = 10
# A systemd Conflicts= transaction runs the evicted unit's stop job and the
# evicting unit's start job together; on this host they have landed within
# the same second every time observed. 5s leaves headroom without widening
# the window enough to start pairing unrelated restarts.
GPU_EVICTION_WINDOW_US = 5_000_000


def gpu_compute_apps() -> tuple[list[dict[str, Any]] | None, str | None]:
    """Real per-process VRAM via `nvidia-smi --query-compute-apps`.

    Returns (None, reason) when it cannot be measured -- no nvidia-smi, no
    GPU, a permissions failure -- so callers can render "not measured"
    instead of a confident zero. An empty list (not None) means nvidia-smi
    ran fine and reported no compute processes at all.
    """
    nvidia = shutil.which("nvidia-smi")
    if not nvidia:
        return None, "nvidia-smi not on PATH"
    try:
        result = subprocess.run(
            [
                nvidia,
                "--query-compute-apps=pid,process_name,used_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, str(error)
    if result.returncode != 0:
        return None, (result.stderr or "nvidia-smi exited non-zero").strip()[:200] or "nvidia-smi failed"
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        pid = as_int(parts[0])
        if pid is None:
            continue
        rows.append({"pid": pid, "name": parts[1], "used_mib": as_int(parts[2])})
    return rows, None


def process_cgroup_path(pid: int) -> str | None:
    try:
        text = Path(f"/proc/{pid}/cgroup").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        _, _, path = line.partition("::")
        if path:
            return path
    return None


def vram_by_unit(
    processes: list[dict[str, Any]], unit_cgroups: dict[str, str]
) -> dict[str, int]:
    """Sum measured VRAM per unit, matching each GPU process's own cgroup
    against the candidate units' cgroups by prefix.

    This works identically for a native systemd service (the process sits
    directly in the unit's cgroup) and for a podman container placed under a
    systemd-owned cgroup parent (the process sits in a nested libpod scope
    beneath it) -- prefix matching covers both without special-casing either.
    """
    totals: dict[str, int] = {}
    for proc in processes:
        cgroup = process_cgroup_path(proc["pid"])
        if not cgroup or proc.get("used_mib") is None:
            continue
        for unit, prefix in unit_cgroups.items():
            if prefix and (cgroup == prefix or cgroup.startswith(prefix.rstrip("/") + "/")):
                totals[unit] = totals.get(unit, 0) + proc["used_mib"]
                break
    return totals


def gpu_admission_states(units: list[tuple[str, str]]) -> dict[str, dict[str, str]]:
    states: dict[str, dict[str, str]] = {}
    for manager in {manager for manager, _ in units}:
        states.update(
            show_units(manager, [unit for owner, unit in units if owner == manager], GPU_STATE_PROPERTIES)
        )
    return states


def gpu_lifecycle_events(units: list[str]) -> tuple[list[dict[str, Any]], str | None]:
    """Every start/stop job completion for the given units, straight from
    the journal, within a fixed lookback window and a hard event cap."""
    if not units:
        return [], None
    journalctl = shutil.which("journalctl")
    if not journalctl:
        return [], "journalctl not on PATH"
    arguments = [journalctl, "-o", "json", "--since", GPU_EVICTION_SINCE, "--no-pager"]
    for unit in units:
        arguments += ["-u", unit]
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, timeout=25, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return [], str(error)
    if result.returncode != 0:
        return [], (result.stderr or "journalctl exited non-zero").strip()[:200]
    events: list[dict[str, Any]] = []
    for line in result.stdout.splitlines()[-GPU_EVICTION_MAX_EVENTS:]:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("JOB_RESULT") != "done" or entry.get("JOB_TYPE") not in {"start", "stop"}:
            continue
        unit = entry.get("UNIT")
        timestamp = as_int(entry.get("__REALTIME_TIMESTAMP"))
        if not unit or timestamp is None:
            continue
        events.append({"unit": str(unit), "type": entry["JOB_TYPE"], "ts": timestamp})
    events.sort(key=lambda event: event["ts"])
    return events, None


def eviction_history(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair each start-job completion with a stop-job completion of a
    *different* unit landing within the correlation window.

    Systemd does not log "stopped because of Conflicts=" as a distinct fact
    -- both jobs are just part of the same transaction -- so this is a timing
    inference, not a field read straight off a log line. Captioned as such on
    the page; see GPU_EVICTION_WINDOW_US for why the window is narrow enough
    that a coincidental unrelated stop is unlikely to be misread as one.
    """
    starts = [event for event in events if event["type"] == "start"]
    stops = [event for event in events if event["type"] == "stop"]
    pairs: list[dict[str, Any]] = []
    for start in starts:
        for stop in stops:
            if stop["unit"] == start["unit"]:
                continue
            if abs(stop["ts"] - start["ts"]) <= GPU_EVICTION_WINDOW_US:
                pairs.append(
                    {
                        "started": start["unit"],
                        "stopped": stop["unit"],
                        "ts": max(start["ts"], stop["ts"]),
                    }
                )
    seen: set[tuple[str, str, int]] = set()
    deduped: list[dict[str, Any]] = []
    for entry in sorted(pairs, key=lambda item: item["ts"], reverse=True):
        key = (entry["started"], entry["stopped"], entry["ts"] // 1_000_000)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped[:GPU_EVICTION_ROWS]


def gpu_admission_card(services: list[dict[str, Any]], now: dt.datetime) -> str:
    members = [
        service
        for service in services
        if service.get("registered") and service.get("exclusiveResource") == GPU_ADMISSION_KEY
    ]
    if not members:
        return card(
            "GPU admission (gpu-inference)",
            empty(
                "no registered backend currently declares the gpu-inference "
                "admission key -- nothing to report"
            ),
        )

    unit_by_name = {str(service["name"]): str(service["unit"]) for service in members}
    units = sorted(set(unit_by_name.values()))
    unit_owner_pairs = [(str(service.get("manager") or "system"), str(service["unit"])) for service in members]
    states = gpu_admission_states(unit_owner_pairs)
    processes, proc_error = gpu_compute_apps()
    unit_cgroups = {unit: str(states.get(unit, {}).get("ControlGroup") or "") for unit in units}
    vram = vram_by_unit(processes, unit_cgroups) if processes is not None else {}
    monotonic = monotonic_now_us()

    resident_blocks = ""
    resident_count = 0
    for service in sorted(members, key=lambda item: str(item["name"])):
        unit = str(service["unit"])
        info = states.get(unit, {})
        installed = info.get("LoadState") not in {"not-found", "", None}
        active = info.get("ActiveState") == "active"
        meta: list[str] = []
        tone = ""
        if not installed:
            meta.append("not installed on this host")
        elif active:
            resident_count += 1
            measured = vram.get(unit)
            if processes is None:
                meta.append(badge("VRAM not measured", "warn"))
                meta.append(esc(proc_error or "nvidia-smi unavailable"))
                tone = "warn"
            elif measured is not None:
                meta.append(badge(f"{measured} MiB measured", "info"))
            else:
                meta.append(badge("resident, VRAM not attributable", "warn"))
                meta.append("no nvidia-smi compute process matched this unit's cgroup")
                tone = "warn"
            started = as_int(info.get("ActiveEnterTimestampMonotonic"))
            if monotonic is not None and started:
                meta.append(f"resident {esc(duration_human((monotonic - started) / 1_000_000))}")
            meta.append(
                "idle-out: not a live countdown — systemd-socket-proxyd tears the "
                "backend down synchronously with its own 30s idle detection, so "
                "there is no running timer to read"
                if service.get("activationMode") == "socket-proxy"
                else "idle-out: none — container, stopped only by conflict or the operator"
            )
        headline = f"<strong>{esc(service['name'])}</strong> <code>{esc(unit)}</code>"
        status_badge = (
            badge("not installed", "muted")
            if not installed
            else badge("resident", "ok") if active else badge("idle/stopped", "muted")
        )
        resident_blocks += row(headline, [status_badge, *meta], tone=tone)

    conflict_blocks = ""
    for service in sorted(members, key=lambda item: str(item["name"])):
        unit = str(service["unit"])
        conflicts = (states.get(unit, {}).get("Conflicts") or "").split()
        gpu_conflicts = sorted((set(conflicts) & set(units)) - {unit})
        conflict_blocks += row(
            f"<code>{esc(unit)}</code>",
            [
                " ".join(f"<code>{esc(other)}</code>" for other in gpu_conflicts)
                if gpu_conflicts
                else badge("no live Conflicts= against another gpu-inference member", "bad")
            ],
        )

    events, journal_error = gpu_lifecycle_events(units)
    evictions = eviction_history(events)
    name_by_unit = {unit: name for name, unit in unit_by_name.items()}
    eviction_blocks = ""
    for entry in evictions:
        age = duration_human(now.timestamp() - entry["ts"] / 1_000_000)
        eviction_blocks += row(
            f"<strong>{esc(name_by_unit.get(entry['started'], entry['started']))}</strong> started, "
            f"evicting <strong>{esc(name_by_unit.get(entry['stopped'], entry['stopped']))}</strong>",
            [esc(age) + " ago", badge("inferred from job timing", "muted")],
        )
    if not evictions:
        eviction_blocks = empty(
            f"journalctl error: {journal_error}" if journal_error
            else f"no evictions in the last lookback window ({GPU_EVICTION_SINCE})"
        )

    body = (
        '<div class="tiles">'
        + tile(str(resident_count), "resident now", "info" if resident_count else "ok")
        + tile(str(len(members)), "admission members")
        + (tile("live", "vram source", "ok") if processes is not None else tile("unmeasured", "vram source", "warn"))
        + "</div>"
    )
    body += f'<div class="group"><h3>resident state</h3>{resident_blocks}</div>'
    body += (
        '<div class="group"><h3>mutual exclusivity (live Conflicts=)</h3>'
        f"{conflict_blocks}</div>"
    )
    body += (
        f'<div class="group"><h3>recent evictions (last {GPU_EVICTION_ROWS}, '
        f"{esc(GPU_EVICTION_SINCE)})</h3>{eviction_blocks}</div>"
    )
    return card(
        "GPU admission (gpu-inference)",
        body,
        "Every backend sharing the gpu-inference key evicts every other on "
        "start. VRAM is measured per process from nvidia-smi and attributed "
        "by matching each process's own cgroup to the owning unit's — never "
        "restated from a nominal model size. Exclusivity below is systemd's "
        "live Conflicts=, not the Nix source.",
        wide=True,
        anchor="gpu-admission",
    )


# --------------------------------------------------------------------------
# AI control panel
# --------------------------------------------------------------------------


def resolve_ai_services(
    manifest: dict[str, Any], inventory: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Turn the manifest's AI service *names* into live surface metadata.

    The manifest carries names only. Units, endpoints, idle timeouts, the
    gpu-inference admission key, and the restartable flag all come from
    /etc/sinnix/runtime-inventory.json -- the same attested document the
    ops-reducer's action API resolves targets against. Reading one source for
    both means the panel can never offer a button the API would refuse for a
    reason the panel does not know about.
    """
    surfaces = {}
    if isinstance(inventory, dict) and isinstance(inventory.get("surfaces"), dict):
        surfaces = inventory["surfaces"]
    resolved: list[dict[str, Any]] = []
    for name in manifest.get("aiServices", []):
        if not isinstance(name, str):
            continue
        surface = surfaces.get(name)
        if not isinstance(surface, dict):
            resolved.append({"name": name, "registered": False})
            continue
        activation = (
            surface.get("activation") if isinstance(surface.get("activation"), dict) else {}
        )
        observe = surface.get("observe") if isinstance(surface.get("observe"), dict) else {}
        resolved.append(
            {
                "name": name,
                "registered": True,
                "unit": surface.get("unit"),
                "manager": surface.get("manager", "system"),
                "restartable": bool(observe.get("restartable")),
                "activationMode": activation.get("mode"),
                "publicEndpoint": activation.get("publicEndpoint"),
                "idleTimeout": activation.get("idleTimeout"),
                "exclusiveResource": activation.get("exclusiveResource"),
            }
        )
    return resolved



def render_ai(
    manifest: dict[str, Any],
    inventory: dict[str, Any] | None,
    generated: str,
) -> str:
    host = str(manifest.get("host", "sinnix"))
    now = dt.datetime.now(dt.timezone.utc)
    services = resolve_ai_services(manifest, inventory)
    states = unit_states(
        [(str(s.get("manager", "system")), str(s["unit"])) for s in services if s.get("unit")]
    )

    blocks = ""
    running = 0
    for service in sorted(services, key=lambda item: str(item.get("name"))):
        if not service.get("registered"):
            blocks += row(
                f"<strong>{esc(service.get('name'))}</strong>",
                [
                    badge("not registered", "muted"),
                    "no runtime surface on this host — the module is not enabled",
                ],
            )
            continue
        unit = str(service.get("unit", ""))
        info = states.get(unit, {})
        socket_activated = service.get("activationMode") == "socket-proxy"
        status, tone = unit_status(info, socket_activated)
        installed = info.get("LoadState") not in {"not-found", "", None}
        active = info.get("ActiveState") == "active"
        running += 1 if active else 0

        meta = [status]
        if service.get("publicEndpoint"):
            meta.append(f"<code>{esc(service['publicEndpoint'])}</code>")
        if service.get("idleTimeout"):
            meta.append(f"idle exit {esc(service['idleTimeout'])}")
        if service.get("exclusiveResource"):
            meta.append(f"admission key <code>{esc(service['exclusiveResource'])}</code>")
        blocks += row(
            f"<strong>{esc(service.get('name'))}</strong>",
            meta,
            lifecycle_controls(unit, bool(service.get("restartable")), installed, active),
            "bad" if tone == "bad" else "",
        )

    gpu = gpu_summary()
    body = (
        '<div class="tiles">'
        + tile(str(running), "backends up", "info" if running else "ok")
        + tile(str(len([s for s in services if s.get("registered")])), "registered")
        + (
            tile(esc(gpu.split(",")[0].strip()), "gpu memory used", "info")
            if gpu
            else tile("—", "gpu", "muted")
        )
        + (tile(esc(gpu.split(",")[2].strip()), "gpu utilisation") if gpu and len(gpu.split(",")) > 2 else "")
        + "</div>"
    )
    body += (
        '<section class="card wide"><h2>Local AI backends</h2>'
        "<p class=\"sub\">These sit behind <code>systemd-socket-proxyd</code> and "
        "exit after their idle timeout, so <em>idle</em> is the resting state, not "
        "a fault: connecting to the public endpoint starts one with no privileged "
        "action at all. Ollama and KoboldCpp hold the same "
        "<code>gpu-inference</code> admission key and conflict by design.</p>"
        f"{blocks}</section>"
    )
    body += gpu_admission_card(services, now)
    body += log_card()
    if inventory is None:
        body += card(
            "Runtime inventory unavailable",
            '<p class="sub">The action API will refuse every unit target until '
            "<code>/etc/sinnix/runtime-inventory.json</code> is readable.</p>",
            wide=True,
        )
    return page(
        "ai",
        host,
        [f"rendered {generated[11:19]}"],
        "/ai/",
        body,
        tail=ACTION_SCRIPT,
    )

