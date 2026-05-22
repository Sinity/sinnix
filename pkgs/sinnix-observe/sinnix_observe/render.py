"""Human-readable rendering of the report dict."""

from __future__ import annotations

from typing import Any

from .util import normalize_timestamp


def render_human(report: dict[str, Any]) -> str:
    lines: list[str] = []

    def section(title: str) -> None:
        lines.append("")
        lines.append(f"== {title} ==")

    section("live pressure")
    lines.append(report["generated_at"])
    pressure = report.get("live_pressure", {})
    for key in ("cpu", "memory", "io"):
        raw = pressure.get(key, {}).get("raw", "")
        prefix = f"{key:<6}"
        for idx, raw_line in enumerate(raw.splitlines() or [""]):
            lines.append(f"{prefix if idx == 0 else '':<7}{raw_line}")
    if pressure.get("free_h"):
        lines.append(pressure["free_h"].rstrip())

    section("blocked tasks")
    blocked = report.get("blocked_tasks", [])
    if not blocked:
        lines.append("none")
    else:
        lines.append(
            f"{'STAT':<6} {'PID':<8} {'PPID':<8} {'SEC':<8} {'CPU':<6} {'RSS_KB':<9} {'WCHAN':<24} COMMAND"
        )
        for task in blocked[:20]:
            lines.append(
                f"{task.get('stat', ''):<6} {task.get('pid', '')!s:<8} {task.get('ppid', '')!s:<8} "
                f"{task.get('elapsed_secs', '')!s:<8} {task.get('cpu_pct', '')!s:<6} {task.get('rss_kb', '')!s:<9} "
                f"{task.get('wchan', ''):<24} {task.get('cmdline', '')}"
            )

    section("storage pressure")
    storage = report.get("storage", {})
    ft = storage.get("fstrim_timer", {})
    fs = storage.get("fstrim_service", {})
    lines.append(
        f"fstrim.timer active={ft.get('ActiveState')} sub={ft.get('SubState')} next={ft.get('NextElapseUSecRealtime')}"
    )
    lines.append(
        f"fstrim.service active={fs.get('ActiveState')} sub={fs.get('SubState')} result={fs.get('Result')}"
    )
    lines.append("mount map:")
    for mount in storage.get("mounts", []):
        if mount.get("unresolved"):
            lines.append(f"  {mount.get('path'):<42} unresolved")
        else:
            lines.append(
                f"  {mount.get('path'):<42} {mount.get('target')} {mount.get('source')} {mount.get('fstype')} {mount.get('options')}"
            )
    if storage.get("discard_queues"):
        lines.append("discard queues:")
        for queue in storage["discard_queues"]:
            lines.append(
                f"  {queue.get('device'):<8} discard_max={queue.get('discard_max_bytes')} "
                f"granularity={queue.get('discard_granularity')} scheduler={queue.get('scheduler')} "
                f"wbt={queue.get('wbt_lat_usec')}"
            )
    if storage.get("iostat_xz"):
        lines.append("iostat 1s sample:")
        lines.extend(
            "  " + line for line in storage["iostat_xz"].rstrip().splitlines()[:40]
        )

    section("managed workload units")
    for unit in report.get("systemd_units", []):
        policy = unit.get("policy", {})
        lines.append(
            f"{unit.get('unit'):<34} active={unit.get('active_state')}/{unit.get('sub_state')} "
            f"pid={unit.get('main_pid')} class={unit.get('resource_class')} "
            f"cgroup={unit.get('control_group')} high={policy.get('memory_high')} "
            f"max={policy.get('memory_max')} io_weight={policy.get('io_weight')}"
        )

    section("resource slices")
    for unit in report.get("resource_slices", []):
        policy = unit.get("policy", {})
        lines.append(
            f"{unit.get('manager')}/{unit.get('unit'):<24} active={unit.get('active_state')}/{unit.get('sub_state')} "
            f"high={policy.get('memory_high')} max={policy.get('memory_max')} "
            f"io_weight={policy.get('io_weight')}"
        )

    section("chrome I/O attribution")
    chrome = report.get("chrome_io", {})
    lines.append(chrome.get("counter_scope", "unavailable"))
    if not chrome.get("available"):
        lines.append("none")
    else:
        for profile in chrome.get("profiles", []):
            mount = profile.get("mount", {})
            lines.append(
                f"profile {profile.get('path')} real={profile.get('realpath')} "
                f"mount={mount.get('source')} target={mount.get('target')}"
            )
            for cache in profile.get("cache_paths", [])[:16]:
                cache_mount = cache.get("mount", {})
                lines.append(
                    f"  cache {cache.get('path')} bytes={cache.get('du_bytes')} "
                    f"mount={cache_mount.get('source')}"
                )
        lines.append("cgroups:")
        for row in chrome.get("by_cgroup", [])[:12]:
            lines.append(
                f"  procs={row.get('processes')} rss_MiB={row.get('rss_kb', 0) / 1024:.1f} "
                f"read_MiB={row.get('read_bytes', 0) / 1048576:.1f} "
                f"write_MiB={row.get('write_bytes', 0) / 1048576:.1f} {row.get('cgroup')}"
            )
        lines.append("top live processes:")
        for proc in chrome.get("processes", [])[:12]:
            io = proc.get("io") or {}
            lines.append(
                f"  pid={proc.get('pid')} rss_MiB={(proc.get('rss_kb') or 0) / 1024:.1f} "
                f"read_MiB={io.get('read_bytes', 0) / 1048576:.1f} "
                f"write_MiB={io.get('write_bytes', 0) / 1048576:.1f} "
                f"cg={proc.get('cgroup')} {proc.get('comm')}"
            )
        if chrome.get("below_process_peaks"):
            lines.append("recent below Chrome peaks:")
            for row in chrome["below_process_peaks"][:8]:
                lines.append(
                    f"  rw_Bps={row.get('max_rw_bps'):.0f} rss_MiB={row.get('max_rss_bytes', 0) / 1048576:.1f} "
                    f"pid={row.get('pid')} {row.get('comm')} {row.get('cgroup')}"
                )

    section("workload rows")
    rows = report.get("workload_rows", [])
    if not rows:
        lines.append("none")
    else:
        lines.append(
            f"{'source':<18} {'project':<10} {'class':<22} {'status':<18} {'name'}"
        )
        for row in rows[:60]:
            gap_count = len(row.get("gaps", []))
            lines.append(
                f"{row.get('source', ''):<18} {str(row.get('project') or ''):<10} "
                f"{str(row.get('resource_class') or ''):<22} {str(row.get('status') or ''):<18} "
                f"{row.get('name') or row.get('workload_id')} gaps={gap_count}"
            )

    section("sinex xtask history")
    sinex = report.get("sinex_xtask_history", {})
    lines.append(f"db={sinex.get('db')} available={sinex.get('available')}")
    for row in sinex.get("rows", [])[:10]:
        lines.append(
            f"  {row.get('id')} {row.get('command')} {row.get('status')} "
            f"{row.get('started_at')} secs={row.get('duration_secs')} "
            f"rss_mb={row.get('process_memory_usage_max_mb')}"
        )

    section("polylogue live ingest")
    poly = report.get("polylogue_live_attempts", {})
    lines.append(f"db={poly.get('db')} available={poly.get('available')}")
    for row in poly.get("rows", [])[:10]:
        lines.append(
            f"  {normalize_timestamp(row.get('started_at'))} {row.get('attempt_id')} "
            f"{row.get('status')} {row.get('phase')} "
            f"files={row.get('succeeded_file_count')}/{row.get('needed_file_count')} "
            f"payload_read={row.get('source_payload_read_bytes')}"
        )

    section("below recent history")
    below = report.get("below", {})
    lines.append(f"window: begin={below.get('begin')} duration={below.get('duration')}")
    lines.append("cgroup peaks:")
    for row in below.get("cgroup_peaks", [])[:12]:
        lines.append(
            f"  rw_Bps={row.get('max_rw_bps'):.0f} io_full={row.get('max_io_full_pct'):.2f} "
            f"rss_MiB={row.get('max_rss_bytes', 0) / 1048576:.1f} cpu={row.get('max_cpu_pct'):.1f} "
            f"{row.get('cgroup')}"
        )
    lines.append("process I/O peaks:")
    for row in below.get("process_peaks", [])[:12]:
        lines.append(
            f"  rw_Bps={row.get('max_rw_bps'):.0f} rss_MiB={row.get('max_rss_bytes', 0) / 1048576:.1f} "
            f"cpu={row.get('max_cpu_pct'):.1f} pid={row.get('pid')} {row.get('comm')} {row.get('cmdline')}"
        )

    section("gaps")
    gaps = report.get("gaps_summary", {})
    if not gaps:
        lines.append("none")
    else:
        for gap, count in sorted(gaps.items()):
            lines.append(f"{gap}: {count}")

    section("below hint")
    lines.append(f"interactive replay: below replay -t '{report['window']['since']}'")
    return "\n".join(lines) + "\n"
