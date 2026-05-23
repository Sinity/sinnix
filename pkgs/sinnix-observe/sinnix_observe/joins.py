"""Cross-source joins: build the unified workload_rows view."""

from __future__ import annotations

from typing import Any

from .sources.xtask import infer_sinex_resource_class
from .util import normalize_timestamp
from .workload_policy import resource_class_from_cgroup


def project_for_unit(unit: str) -> str | None:
    if unit.startswith("sinex") or unit in {"nats.service", "postgresql.service"}:
        return "sinex"
    if unit.startswith("polylogue") or unit.startswith("polylogued"):
        return "polylogue"
    if unit.startswith("borg") or unit.startswith("btrbk"):
        return "backup"
    return None


def project_for_text(text: str) -> str | None:
    lower = text.lower()
    if "sinex" in lower or "xtask" in lower:
        return "sinex"
    if "polylogue" in lower or "polylogued" in lower:
        return "polylogue"
    if "borg" in lower or "btrbk" in lower:
        return "backup"
    return None


def infer_resource_class_from_cgroup(cgroup: str) -> str | None:
    return resource_class_from_cgroup(cgroup)


def match_below(name: str, cgroup: str | None, below: dict[str, Any]) -> dict[str, Any]:
    name_l = name.lower()
    matched_cgroups = []
    for row in below.get("cgroup_peaks", []):
        cg = str(row.get("cgroup") or "")
        if (cgroup and cgroup in cg) or name_l.replace(".service", "") in cg.lower():
            matched_cgroups.append(row)
    matched_processes = []
    for row in below.get("process_peaks", []):
        text = f"{row.get('comm') or ''} {row.get('cmdline') or ''} {row.get('cgroup') or ''}".lower()
        if name_l.replace(".service", "") in text or (
            name_l == "sinex" and ("sinex" in text or "xtask" in text)
        ):
            matched_processes.append(row)
        elif name_l == "polylogue" and "polylogue" in text:
            matched_processes.append(row)
    return {
        "cgroup_peaks": matched_cgroups[:3],
        "process_peaks": matched_processes[:3],
    }


def build_workload_rows(
    systemd_units: list[dict[str, Any]],
    sinex: dict[str, Any],
    polylogue: dict[str, Any],
    below: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for unit in systemd_units:
        gaps = []
        if not unit.get("control_group"):
            gaps.append("systemd.unit.lacks_control_group")
        if not unit.get("resource_class"):
            gaps.append("systemd.unit.lacks_resource_class")
        rows.append(
            {
                "workload_id": f"systemd:{unit['manager']}:{unit['unit']}",
                "source": "systemd",
                "project": project_for_unit(unit["unit"]),
                "kind": "unit",
                "name": unit["unit"],
                "unit": unit["unit"],
                "unit_scope": unit["manager"],
                "cgroup": unit.get("control_group"),
                "resource_class": unit.get("resource_class"),
                "status": f"{unit.get('active_state')}/{unit.get('sub_state')}",
                "metrics": {"policy": unit.get("policy", {})},
                "below": match_below(unit["unit"], unit.get("control_group"), below),
                "gaps": gaps,
            }
        )

    for row in sinex.get("rows", []):
        gaps = [
            "sinex.invocation.lacks_recorded_unit",
            "sinex.invocation.lacks_cgroup",
            "sinex.invocation.lacks_io_bytes",
            "sinex.invocation.lacks_psi_window",
            "sinex.invocation.lacks_declared_resource_class",
        ]
        command = " ".join(
            str(v) for v in [row.get("command"), row.get("subcommand")] if v
        )
        rows.append(
            {
                "workload_id": f"sinex.xtask:{row.get('id')}",
                "source": "sinex.xtask",
                "project": "sinex",
                "kind": "project-ledger",
                "name": command or "xtask",
                "command": command,
                "started_at": normalize_timestamp(row.get("started_at")),
                "finished_at": normalize_timestamp(row.get("finished_at")),
                "duration_secs": row.get("duration_secs"),
                "status": row.get("status"),
                "pid": row.get("pid"),
                "unit": None,
                "cgroup": None,
                "resource_class": infer_sinex_resource_class(row),
                "metrics": {
                    "rss_mb": row.get("process_memory_usage_max_mb"),
                    "cpu_avg": row.get("process_cpu_usage_avg"),
                    "process_count_max": row.get("process_count_max"),
                    "resource_sample_count": row.get("resource_sample_count"),
                    "scope_key": row.get("scope_key"),
                    "launch_mode": row.get("launch_mode"),
                    "shared_background_slice_memory_usage_max_mb": row.get(
                        "shared_background_slice_memory_usage_max_mb"
                    ),
                    "shared_nix_build_slice_memory_usage_max_mb": row.get(
                        "shared_nix_build_slice_memory_usage_max_mb"
                    ),
                },
                "below": match_below("sinex", None, below),
                "gaps": gaps,
            }
        )

    for row in polylogue.get("rows", []):
        gaps = []
        if not row.get("cgroup_path"):
            gaps.append("polylogue.live_attempt.lacks_cgroup")
        if row.get("source_payload_read_bytes") is None:
            gaps.append("polylogue.live_attempt.lacks_io_bytes")
        if row.get("cgroup_memory_current_mb") is None:
            gaps.append("polylogue.live_attempt.lacks_cgroup_memory")
        rows.append(
            {
                "workload_id": f"polylogue.live_attempt:{row.get('attempt_id')}",
                "source": "polylogue.live_attempt",
                "project": "polylogue",
                "kind": "project-ledger",
                "name": "polylogue live ingest",
                "run_id": row.get("attempt_id"),
                "started_at": normalize_timestamp(row.get("started_at")),
                "finished_at": normalize_timestamp(row.get("completed_at")),
                "duration_secs": None,
                "status": row.get("status"),
                "unit": "polylogued.service",
                "unit_source": "sinnix-inferred",
                "cgroup": row.get("cgroup_path"),
                "resource_class": "capture-runtime",
                "metrics": {
                    "phase": row.get("phase"),
                    "queued_file_count": row.get("queued_file_count"),
                    "needed_file_count": row.get("needed_file_count"),
                    "succeeded_file_count": row.get("succeeded_file_count"),
                    "failed_file_count": row.get("failed_file_count"),
                    "input_bytes": row.get("input_bytes"),
                    "source_payload_read_bytes": row.get("source_payload_read_bytes"),
                    "cursor_fingerprint_read_bytes": row.get(
                        "cursor_fingerprint_read_bytes"
                    ),
                    "parse_time_s": row.get("parse_time_s"),
                    "convergence_time_s": row.get("convergence_time_s"),
                    "current_source": row.get("current_source"),
                    "current_path": row.get("current_path"),
                    "rss_current_mb": row.get("rss_current_mb"),
                    "rss_peak_self_mb": row.get("rss_peak_self_mb"),
                    "rss_peak_children_mb": row.get("rss_peak_children_mb"),
                    "cgroup_memory_current_mb": row.get("cgroup_memory_current_mb"),
                    "cgroup_memory_peak_mb": row.get("cgroup_memory_peak_mb"),
                    "cgroup_memory_swap_current_mb": row.get(
                        "cgroup_memory_swap_current_mb"
                    ),
                    "error": row.get("error"),
                },
                "below": match_below("polylogued", row.get("cgroup_path"), below),
                "gaps": gaps,
            }
        )

    for proc in below.get("process_peaks", []):
        gaps = []
        if not proc.get("cgroup"):
            gaps.append("below.process.lacks_cgroup")
        rows.append(
            {
                "workload_id": f"below.process:{proc.get('pid')}",
                "source": "below.process",
                "project": project_for_text(
                    proc.get("cmdline") or proc.get("comm") or ""
                ),
                "kind": "below-process-peak",
                "name": proc.get("comm"),
                "pid": proc.get("pid"),
                "cgroup": proc.get("cgroup"),
                "resource_class": infer_resource_class_from_cgroup(
                    proc.get("cgroup") or ""
                ),
                "metrics": proc,
                "gaps": gaps,
            }
        )
    return rows
