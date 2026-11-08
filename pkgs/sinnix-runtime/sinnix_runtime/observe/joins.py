"""Cross-source joins: build the unified workload_rows view."""

from __future__ import annotations

from typing import Any

from .runtime_inventory import resource_class_from_cgroup, workload_for_cgroup
from .sources.xtask import infer_sinex_resource_class
from .util import normalize_timestamp


def project_for_unit(unit: str) -> str | None:
    if unit.startswith("sinex") or unit == "postgresql.service":
        return "sinex"
    if unit.startswith("polylogue"):
        return "polylogue"
    if unit.startswith("borg") or unit.startswith("btrbk"):
        return "backup"
    return None


def project_for_text(text: str) -> str | None:
    lower = text.lower()
    if "sinex" in lower or "xtask" in lower:
        return "sinex"
    if "polylogue" in lower:
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
        command = " ".join(str(v) for v in [row.get("command"), row.get("args")] if v)
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
                    "agentctl_job": row.get("agentctl_job"),
                    "cwd": row.get("cwd"),
                    "failure": row.get("failure"),
                },
                "below": match_below("sinex", None, below),
                "gaps": gaps,
            }
        )

    if polylogue.get("available"):
        last = polylogue.get("last_pass") or {}
        rows.append(
            {
                "workload_id": f"polylogue.daemon:{polylogue.get('pid')}",
                "source": "polylogue.daemon",
                "project": "polylogue",
                "kind": "daemon-status",
                "name": "polylogue daemon",
                "pid": polylogue.get("pid"),
                "status": "busy" if polylogue.get("busy") else "idle",
                "unit": polylogue.get("unit"),
                "unit_source": "sinnix-declared",
                "cgroup": None,
                "resource_class": "capture-runtime",
                "metrics": {
                    "uptime_seconds": polylogue.get("uptime_seconds"),
                    "passes": polylogue.get("passes"),
                    "last_pass_seconds": last.get("seconds"),
                    "last_pass_inputs_changed": last.get("inputs_changed"),
                    "last_pass_bytes_read": last.get("bytes_read"),
                    "last_pass_messages_written": last.get("messages_written"),
                    "last_pass_errors": len(last.get("errors") or []),
                },
                "below": match_below("polylogue", None, below),
                "gaps": [],
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
                "workload": workload_for_cgroup(proc.get("cgroup") or ""),
                "metrics": proc,
                "gaps": gaps,
            }
        )
    return rows


def build_gateway_rows(
    gateway: dict[str, Any], below: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = []
    for job in gateway.get("jobs", []):
        if not isinstance(job, dict):
            continue
        rows.append(
            {
                "workload_id": f"agentctl:{job.get('task_id')}",
                "source": "agentctl",
                "project": job.get("project"),
                "kind": job.get("kind"),
                "name": job.get("label"),
                "run_id": job.get("task_id"),
                "status": job.get("phase"),
                "unit": None,
                "cgroup": None,
                "resource_class": None,
                "below": match_below(str(job.get("task_id")), None, below),
                "metrics": {
                    "group": job.get("group"),
                    "operation": job.get("operation"),
                    "job_id": job.get("job_id"),
                },
                "gaps": [] if gateway.get("available") else ["agentctl.unavailable"],
            }
        )
    return rows
