"""The / page: the three-second read -- a verdict, a row of tiles, then detail."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Any

from .probes import HEAVY_CLASSES, collect_scopes
from .shell import (
    ACTION_SCRIPT,
    badge,
    card,
    dot,
    duration_human,
    empty,
    esc,
    kv_table,
    meter,
    page,
    parse_iso,
    row,
    tile,
)
from .work import live_work_card, running_ledger


def psi_avg10(pressure: dict[str, Any], key: str) -> float | None:
    block = pressure.get(key)
    if not isinstance(block, dict):
        return None
    window = block.get("some")
    if not isinstance(window, dict):
        return None
    try:
        return float(window.get("avg10"))
    except (TypeError, ValueError):
        return None


def memory_figures(pressure: dict[str, Any]) -> tuple[float, float] | None:
    """(used GiB, total GiB) parsed from `free -h`'s Mem line."""
    free = pressure.get("free_h")
    if not isinstance(free, str):
        return None
    for line in free.splitlines():
        if not line.startswith("Mem:"):
            continue
        fields = line.split()
        if len(fields) < 3:
            return None

        def gib(text: str) -> float | None:
            try:
                if text.endswith("Gi"):
                    return float(text[:-2])
                if text.endswith("Mi"):
                    return float(text[:-2]) / 1024
                if text.endswith("Ti"):
                    return float(text[:-2]) * 1024
            except ValueError:
                return None
            return None

        total, used = gib(fields[1]), gib(fields[2])
        if total is None or used is None:
            return None
        return used, total
    return None


def failed_units(state: dict[str, Any]) -> list[dict[str, Any]]:
    units = state.get("systemd_units")
    if not isinstance(units, list):
        return []
    return [
        entry
        for entry in units
        if isinstance(entry, dict) and entry.get("active_state") == "failed"
    ]


def worst_mount(state: dict[str, Any]) -> tuple[str, float] | None:
    storage = state.get("storage")
    mounts = storage.get("mounts") if isinstance(storage, dict) else None
    if not isinstance(mounts, list):
        return None
    interesting = {
        "/",
        "/persist",
        "/realm",
        "/outer-realm",
        "/neo-outer-realm",
        "/nix",
    }
    worst: tuple[str, float] | None = None
    for entry in mounts:
        if not isinstance(entry, dict) or entry.get("target") not in interesting:
            continue
        target = str(entry["target"])
        try:
            stat = os.statvfs(target)
        except OSError:
            continue
        total = stat.f_blocks * stat.f_frsize
        if not total:
            continue
        used = (total - stat.f_bavail * stat.f_frsize) / total
        if worst is None or used > worst[1]:
            worst = (target, used)
    return worst


def verdict(
    state: dict[str, Any],
    scopes: list[dict[str, Any]],
    memory: tuple[float, float] | None,
    failed: list[dict[str, Any]],
    mount: tuple[str, float] | None,
    sources: dict[str, Any],
) -> tuple[str, str, str]:
    """One sentence the operator can read in three seconds, plus a tone."""
    problems: list[str] = []
    tone = "ok"
    if failed:
        tone = "bad"
        names = ", ".join(str(entry.get("unit")) for entry in failed[:3])
        problems.append(
            f"{len(failed)} unit{'s' if len(failed) != 1 else ''} failed ({names})"
        )
    degraded = [
        name
        for name, value in sources.items()
        if isinstance(value, dict) and value.get("status") == "unavailable"
    ]
    if degraded:
        tone = "bad" if tone == "bad" else "warn"
        problems.append(
            f"{len(degraded)} source{'s' if len(degraded) != 1 else ''} unavailable"
        )
    if mount and mount[1] > 0.9:
        tone = "bad"
        problems.append(f"{mount[0]} is {mount[1] * 100:.0f}% full")
    if memory and memory[0] / memory[1] > 0.9:
        tone = "bad" if tone == "bad" else "warn"
        problems.append("memory is nearly exhausted")

    heavy = [entry for entry in scopes if entry.get("class") in HEAVY_CLASSES]
    agents = [
        entry
        for entry in scopes
        if entry.get("job_id") or entry.get("class") == "agent"
    ]
    in_flight = running_ledger(state)
    activity: list[str] = []
    if in_flight:
        named = ", ".join(
            sorted(
                {
                    f"{entry.get('project') or '?'} {entry.get('name') or entry.get('command') or ''}".strip()
                    for entry in in_flight
                }
            )
        )
        activity.append(f"running {named}")
    if heavy:
        names = ", ".join(
            sorted({str(entry.get("project") or entry.get("class")) for entry in heavy})
        )
        activity.append(
            f"{len(heavy)} scope{'s' if len(heavy) != 1 else ''} in the build slices ({names})"
        )
    if agents:
        activity.append(f"{len(agents)} agent session{'s' if len(agents) != 1 else ''}")
    if not activity:
        activity.append("nothing heavy is running")

    if problems:
        sentence = "Needs attention: " + "; ".join(problems) + "."
    else:
        sentence = "The system is healthy."
    detail = ", ".join(activity).capitalize() + "."
    if memory:
        detail += f" Memory {memory[0]:.1f} of {memory[1]:.1f} GiB."
    return tone, sentence, detail


def pressure_card(state: dict[str, Any]) -> str:
    pressure = state.get("live_pressure")
    if not isinstance(pressure, dict):
        return card("Pressure", empty("no live_pressure in the snapshot"))
    rows = []
    for label, key in (("cpu", "cpu"), ("io", "io"), ("memory", "memory")):
        value = psi_avg10(pressure, key)
        if value is None:
            rows.append((f"{label} psi", "—"))
            continue
        tone = "bad" if value > 40 else "warn" if value > 10 else "ok"
        rows.append(
            (
                f"{label} psi",
                f'{dot(tone)}{value:.2f} <span class="sub">avg10 some</span>',
            )
        )
    memory = memory_figures(pressure)
    if memory:
        used, total = memory
        rows.insert(
            0,
            (
                "memory",
                f"{used:.1f} / {total:.1f} GiB"
                + meter(int(used * 1024), int(total * 1024)),
            ),
        )
    return card(
        "Pressure",
        kv_table(rows),
        "PSI avg10 is the share of the last ten seconds something was stalled",
    )


def storage_card(state: dict[str, Any]) -> str:
    storage = state.get("storage")
    mounts = storage.get("mounts") if isinstance(storage, dict) else None
    if not isinstance(mounts, list) or not mounts:
        return card("Storage", empty("no storage mounts in the snapshot"))
    interesting = {
        "/",
        "/persist",
        "/realm",
        "/outer-realm",
        "/neo-outer-realm",
        "/nix",
    }
    # Several of these are subvolumes of one filesystem and report identical
    # figures; showing the same bar four times is noise, so collapse them onto
    # one row that names every mount point sharing the numbers.
    seen: dict[tuple[int, int], dict[str, Any]] = {}
    for entry in mounts:
        if not isinstance(entry, dict) or entry.get("target") not in interesting:
            continue
        target = str(entry["target"])
        try:
            stat = os.statvfs(target)
        except OSError:
            continue
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        if not total:
            continue
        key = (total, free)
        if key in seen:
            seen[key]["targets"].append(target)
            continue
        seen[key] = {
            "targets": [target],
            "total": total,
            "used": total - free,
            "fstype": entry.get("fstype"),
        }
    blocks = ""
    for figures in sorted(
        seen.values(), key=lambda item: item["used"] / item["total"], reverse=True
    ):
        names = " ".join(f"<code>{esc(name)}</code>" for name in figures["targets"])
        blocks += row(
            names + meter(figures["used"], figures["total"]),
            [
                f"{figures['used'] / 1e12:.2f} T of {figures['total'] / 1e12:.2f} T",
                f"{figures['used'] / figures['total'] * 100:.0f}% used",
                esc(figures["fstype"]),
            ],
        )
    return card("Storage", blocks or empty("nothing to show"))


def sources_card(snapshot: dict[str, Any]) -> str:
    sources = snapshot.get("sources")
    if not isinstance(sources, dict):
        return card("Sources", empty("no source health in the snapshot"))
    blocks = ""
    for name, value in sorted(sources.items()):
        if not isinstance(value, dict):
            continue
        status = str(value.get("status", "unknown"))
        tone = {"healthy": "ok", "unavailable": "bad", "disabled": "muted"}.get(
            status, "warn"
        )
        note = value.get("degradation") or value.get("freshness") or ""
        blocks += row(
            f"<code>{esc(name)}</code>",
            [badge(status, tone), esc(note)],
            tone="bad" if tone == "bad" else "",
        )
    return card(
        "Source health",
        blocks or empty("nothing to show"),
        "where the state above came from, and whether it is current",
    )


def failed_card(state: dict[str, Any]) -> str:
    units = state.get("systemd_units")
    if not isinstance(units, list):
        return card("Units", empty("no systemd_units in the snapshot"))
    unhealthy = [
        entry
        for entry in units
        if isinstance(entry, dict)
        and entry.get("active_state") in {"failed", "activating"}
    ]
    if not unhealthy:
        return card(
            "Units",
            f"<p>{badge('all observed units healthy', 'ok')}</p>",
            f"{len(units)} observed",
        )
    blocks = ""
    for entry in unhealthy:
        active = str(entry.get("active_state"))
        tone = "bad" if active == "failed" else "warn"
        blocks += row(
            f"<code>{esc(entry.get('unit'))}</code>",
            [
                badge(active, tone),
                esc(entry.get("sub_state")),
                esc(entry.get("result") or ""),
            ],
            '<a class="act" href="/services/">manage →</a>'
            if active == "failed"
            else "",
            tone,
        )
    return card(
        "Units needing attention",
        blocks,
        f"{len(unhealthy)} of {len(units)} observed units",
        wide=len(unhealthy) > 3,
    )


def links_card(manifest: dict[str, Any]) -> str:
    items = ""
    for frontend in manifest.get("frontends", []):
        if not isinstance(frontend, dict):
            continue
        port = frontend.get("port")
        label = frontend.get("label", frontend.get("name"))
        items += (
            f'<li><a data-port="{esc(port)}" href="http://127.0.0.1:{esc(port)}/">{esc(label)}</a>'
            f'<div class="sub">port {esc(port)} → {esc(frontend.get("upstream"))}</div></li>'
        )
    for link in manifest.get("links", []):
        if not isinstance(link, dict):
            continue
        href = link.get("href", "#")
        items += (
            f'<li><a href="{esc(href)}">{esc(link.get("label", href))}</a>'
            f'<div class="sub">{esc(link.get("note") or "")}</div></li>'
        )
    return card(
        "Elsewhere",
        f'<ul class="links">{items}</ul>' if items else empty("nothing published"),
        "web UIs republished on the tailnet, and the reducer's raw documents",
    )


def reports_card(reports_dir: Path, now: dt.datetime) -> str:
    try:
        entries = [
            entry
            for entry in reports_dir.iterdir()
            if entry.is_file()
            and entry.suffix == ".html"
            and entry.name != "index.html"
        ]
    except OSError as error:
        return card("Reports", f'<p class="sub">{esc(error)}</p>')
    entries.sort(key=lambda entry: entry.stat().st_mtime, reverse=True)
    items = ""
    for entry in entries[:8]:
        age = duration_human(now.timestamp() - entry.stat().st_mtime)
        items += (
            f'<li><a href="/reports/{esc(entry.name)}">{esc(entry.stem)}</a>'
            f'<div class="sub">{esc(age)} ago</div></li>'
        )
    return card(
        "Recent reports",
        f'<ul class="links">{items}</ul>'
        if items
        else empty("no reports generated yet"),
        f'<a href="/reports/">all {len(entries)} reports →</a>',
    )


def render_dashboard(
    manifest: dict[str, Any],
    snapshot: dict[str, Any] | None,
    snapshot_error: str | None,
    inventory: dict[str, Any] | None,
    generated: str,
) -> str:
    host = str(manifest.get("host", "sinnix"))
    now = dt.datetime.now(dt.timezone.utc)
    reports = Path(manifest.get("reportsDir", "/nonexistent"))
    scopes = collect_scopes(inventory)

    if snapshot is None:
        body = (
            '<div class="verdict bad"><p>The system snapshot is unavailable, so '
            "this page cannot say whether anything is wrong.</p>"
            f'<p class="sub">{esc(snapshot_error)}</p></div>'
        )
        body += live_work_card(scopes, {}, now)
        body += links_card(manifest)
        body += reports_card(reports, now)
        return page("hub", host, ["degraded"], "/", body, tail=ACTION_SCRIPT)

    state = snapshot.get("state")
    state = state if isinstance(state, dict) else {}
    sources = (
        snapshot.get("sources") if isinstance(snapshot.get("sources"), dict) else {}
    )
    pressure = (
        state.get("live_pressure")
        if isinstance(state.get("live_pressure"), dict)
        else {}
    )
    memory = memory_figures(pressure)
    failed = failed_units(state)
    mount = worst_mount(state)

    tone, sentence, detail = verdict(state, scopes, memory, failed, mount, sources)
    body = f'<div class="verdict {tone}"><p>{esc(sentence)}</p><p class="sub">{esc(detail)}</p></div>'

    heavy = [entry for entry in scopes if entry.get("class") in HEAVY_CLASSES]
    in_flight = running_ledger(state)
    cpu = psi_avg10(pressure, "cpu")
    tiles = [
        tile(str(len(failed)), "failed units", "bad" if failed else "ok", "/services/"),
        tile(
            str(len(in_flight)),
            "commands in flight",
            "info" if in_flight else "",
            "/work/#running",
        ),
        tile(str(len(heavy)), "heavy scopes", "warn" if heavy else "", "/work/"),
    ]
    if memory:
        share = memory[0] / memory[1]
        tiles.append(
            tile(
                f"{memory[0]:.0f}<span class='l'> / {memory[1]:.0f} GiB</span>",
                "memory",
                "bad" if share > 0.9 else "warn" if share > 0.75 else "",
            )
        )
    if cpu is not None:
        tiles.append(
            tile(
                f"{cpu:.1f}",
                "cpu psi avg10",
                "bad" if cpu > 40 else "warn" if cpu > 10 else "",
            )
        )
    if mount:
        tiles.append(
            tile(
                f"{mount[1] * 100:.0f}%",
                f"{mount[0]} used",
                "bad" if mount[1] > 0.9 else "warn" if mount[1] > 0.8 else "",
            )
        )
    body += f'<div class="tiles">{"".join(tiles)}</div>'

    if failed:
        body += failed_card(state)
    body += pressure_card(state)
    body += storage_card(state)
    body += sources_card(snapshot)
    body += links_card(manifest)
    body += reports_card(reports, now)
    if not failed:
        body += failed_card(state)

    chips = [
        f"rendered {generated[11:19]}",
        f"seq {snapshot.get('sequence')}",
    ]
    observed = parse_iso(snapshot.get("observed_at"))
    if observed is not None:
        chips.append(f"observed {duration_human((now - observed).total_seconds())} ago")
    return page("hub", host, chips, "/", body, tail=ACTION_SCRIPT)
