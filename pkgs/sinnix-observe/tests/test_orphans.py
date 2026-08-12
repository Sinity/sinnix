from __future__ import annotations

import json
from pathlib import Path

from sinnix_observe.sources.orphans import classify_jobs


def _job(job_id: str, pid: int, start: str, cgroup: str) -> dict:
    return {
        "job_id": job_id,
        "schema_version": 3,
        "created_at": "2026-08-07T00:00:00Z",
        "worktree": "/realm/worktrees/fixture",
        "launcher": {
            "pid": pid,
            "proc_start": start,
            "scope_unit": cgroup.rsplit("/", 1)[-1],
            "cgroup": cgroup,
        },
    }


def _proc(proc_root: Path, pid: int, start: str, cgroup: str) -> None:
    directory = proc_root / str(pid)
    directory.mkdir(parents=True)
    directory.joinpath("stat").write_text(" ".join(["0"] * 21 + [start]))
    directory.joinpath("cgroup").write_text(f"0::{cgroup}\n")


def test_classification_distinguishes_attestation_and_cold_workload_class(
    tmp_path: Path, monkeypatch
) -> None:
    proc_root = tmp_path / "proc"
    cgroup_root = tmp_path / "cgroups"
    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps(
            {
                "surfaces": {
                    "cold": {
                        "unit": "cold.scope",
                        "workload": {"class": "sacrificial"},
                    },
                    "protected": {
                        "unit": "protected.scope",
                        "workload": {"class": "protected"},
                    },
                }
            }
        )
    )
    monkeypatch.setenv("SINNIX_RUNTIME_INVENTORY_FILE", str(inventory))
    live_cgroup = "/user.slice/live.scope"
    cold_cgroup = "/user.slice/cold.scope"
    protected_cgroup = "/user.slice/protected.scope"
    _proc(proc_root, 101, "111", live_cgroup)
    for cgroup, pids, swap in (
        (live_cgroup, "101 303", 0),
        (cold_cgroup, "202 303", 65536),
        (protected_cgroup, "404 405", 65536),
    ):
        path = cgroup_root / cgroup.lstrip("/")
        path.mkdir(parents=True)
        path.joinpath("cgroup.procs").write_text(pids)
        path.joinpath("memory.swap.current").write_text(str(swap))
        path.joinpath("io.stat").write_text("8:0 rbytes=0 wbytes=0\n")
    rows = classify_jobs(
        [
            _job("live", 101, "111", live_cgroup),
            _job("cold", 202, "999", cold_cgroup),
            _job("protected", 404, "999", protected_cgroup),
            _job("reused", 101, "999", live_cgroup),
        ],
        {
            "cgroup_peaks": [
                {
                    "cgroup": cold_cgroup,
                    "samples": 2,
                    "max_cpu_pct": 0.1,
                    "max_rw_bps": 0.0,
                }
            ]
        },
        proc_root=proc_root,
        cgroup_root=cgroup_root,
        now=1786060800,
    )
    by_id = {row["job_id"]: row for row in rows}
    assert by_id["live"]["attestation"] == "valid"
    assert by_id["live"]["orphaned"] is False
    assert by_id["cold"]["attestation"] == "dead_launcher"
    assert by_id["cold"]["orphaned"] is True
    assert by_id["cold"]["coldness"]["candidate"] is True
    assert by_id["cold"]["proposed_action"] == "notify"
    assert by_id["protected"]["workload"]["class"] == "protected"
    assert by_id["reused"]["attestation"] == "pid_reuse"
