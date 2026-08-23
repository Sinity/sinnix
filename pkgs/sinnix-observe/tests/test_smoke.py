"""Per-module smoke tests: imports + one happy-path call per module."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3

import pytest
from sinnix_observe import cli, joins, render, runtime_inventory, util
from sinnix_observe.sources import (
    agent_gateway,
    below,
    chrome,
    polylogue,
    pressure,
    proc,
    sqlite_util,
    storage,
    systemd,
    xtask,
)


def test_util_happy_path() -> None:
    assert util.int_or_none("12") == 12
    assert util.int_or_none("x") is None
    assert util.float_or_none("1.5") == 1.5
    assert util.float_or_zero(None) == 0.0
    assert util.words("a b  c") == ["a", "b", "c"]
    assert util.words(None) == []
    assert util.parse_counts('{"a": 1}') == {"a": 1}
    assert util.parse_counts(None) == {}
    assert util.normalize_timestamp(None) is None
    assert util.normalize_timestamp("2026-01-01T00:00:00Z") == "2026-01-01T00:00:00Z"
    assert util.utc_now().endswith("+00:00")
    assert util.split_props("A=1\nB=2") == {"A": "1", "B": "2"}


def test_proc_parsers_handle_missing(tmp_path) -> None:
    missing = tmp_path / "missing"
    assert proc.parse_proc_io(missing) == {}
    assert proc.parse_proc_status(missing) == {}
    assert proc.parse_proc_cgroup(missing) is None

    io_file = tmp_path / "io"
    io_file.write_text("rchar: 1\nwchar: 2\n")
    assert proc.parse_proc_io(io_file) == {"rchar": 1, "wchar": 2}

    status_file = tmp_path / "status"
    status_file.write_text("State:\tR\nPid:\t1\n")
    assert proc.parse_proc_status(status_file)["State"] == "R"

    cgroup_file = tmp_path / "cgroup"
    cgroup_file.write_text("0::/user.slice/test\n")
    assert proc.parse_proc_cgroup(cgroup_file) == "/user.slice/test"


def test_pressure_offline_returns_marker() -> None:
    assert pressure.collect_pressure(offline=True) == {"offline": True}
    assert pressure.collect_blocked_tasks(offline=True) == []
    parsed = pressure.parse_psi("/nonexistent/psi/path")
    assert parsed == {"raw": ""}


def test_systemd_offline_returns_empty() -> None:
    assert systemd.collect_systemd_units(offline=True) == []
    assert systemd.collect_resource_slices(offline=True) == []
    assert systemd.collect_runtime_inventory(offline=True) == {"offline": True}
    row = systemd.unit_row("x.service", "system", {"ActiveState": "active"})
    assert row["unit"] == "x.service"
    assert row["active_state"] == "active"


def test_noctalia_health_fixture(monkeypatch) -> None:
    class Result:
        returncode = 0
        stdout = "Config is valid"
        stderr = ""

    monkeypatch.setattr(systemd, "run_cmd", lambda *_args, **_kwargs: Result())
    health = systemd.collect_noctalia_health()
    assert health == {
        "status": "healthy",
        "config_warning_count": 0,
        "plugin_compatibility": "compatible",
    }
    row = systemd.unit_row(
        "noctalia.service",
        "user",
        {"ActiveState": "active", "MemorySwapCurrent": "7", "NRestarts": "2"},
    )
    assert row["policy"]["memory_swap_current"] == "7"
    assert row["policy"]["restart_count"] == "2"
    assert row["health"]["plugin_compatibility"] == "compatible"


def test_runtime_inventory_fallback_excludes_retired_slices(monkeypatch) -> None:
    monkeypatch.setenv("SINNIX_RUNTIME_INVENTORY_FILE", "/does/not/exist")
    inventory = runtime_inventory.load_inventory()
    assert inventory["schema"] == "sinnix-runtime-inventory-v1"
    assert inventory["classes"]
    assert ("system", "system-critical.slice") in runtime_inventory.observed_slices()
    assert (
        "system",
        "sinnix-maintenance.slice",
    ) not in runtime_inventory.observed_slices()
    sshd_class = runtime_inventory.resource_class_for_unit("sshd.service")
    assert sshd_class in inventory["classes"]


def test_workload_identity_prefers_registered_unit(monkeypatch, tmp_path) -> None:
    inventory_path = tmp_path / "runtime-inventory.json"
    inventory_path.write_text(
        json.dumps(
            {
                "surfaces": {
                    "shell": {
                        "unit": "shell.service",
                        "workload": {
                            "class": "interactive",
                        },
                    }
                }
            }
        )
    )
    monkeypatch.setenv("SINNIX_RUNTIME_INVENTORY_FILE", str(inventory_path))
    assert (
        runtime_inventory.workload_for_cgroup(
            "/system.slice/shell.service/process.scope"
        )["source"]
        == "unit"
    )
    assert (
        runtime_inventory.workload_for_cgroup("/user.slice/unknown.scope")["class"]
        == "unknown"
    )


def test_storage_offline_returns_marker() -> None:
    out = storage.collect_storage(offline=True)
    assert out == {"offline": True, "mounts": [], "discard_queues": []}


def test_chrome_offline_returns_marker() -> None:
    out = chrome.collect_chrome_io(offline=True, below={}, limit=10)
    assert out["offline"] is True
    assert out["available"] is False
    assert chrome.is_chrome_process("chrome", "google-chrome --foo") is True
    assert chrome.is_chrome_process("bash", "echo hi") is False


def test_sqlite_util_handles_missing(tmp_path) -> None:
    db = tmp_path / "missing.db"
    assert sqlite_util.table_exists(db, "x") is False
    assert sqlite_util.sqlite_columns(db, "x") == set()
    assert sqlite_util.sqlite_rows(db, "select 1") == []


def test_xtask_missing_db_reports_gap() -> None:
    out = xtask.collect_sinex_xtask(limit=5)
    assert "gaps" in out or out.get("available") is True
    cls = xtask.infer_sinex_resource_class({"command": "build"})
    assert cls == "developer-build"
    cls = xtask.infer_sinex_resource_class({"command": "run", "is_background": True})
    assert cls == "background-maintenance"
    cls = xtask.infer_sinex_resource_class({"command": "run"})
    assert cls is None


def test_polylogue_missing_db_reports_gap() -> None:
    out = polylogue.collect_polylogue_live_attempts(limit=5)
    assert "gaps" in out or out.get("available") is True


def test_below_offline_reports_gap() -> None:
    out = below.collect_below("10 min ago", "10 min", 10, offline=True)
    assert out["gaps"] == ["below.history.unavailable_offline"]
    assert below.parse_below_tsv("a\tb\nc\td\n") == [["a", "b"], ["c", "d"]]


def test_joins_classifiers() -> None:
    assert joins.project_for_unit("sinex-runtime.target") == "sinex"
    assert joins.project_for_unit("polylogued.service") == "polylogue"
    assert joins.project_for_unit("btrbk.service") == "backup"
    assert joins.project_for_unit("unknown.service") is None
    assert joins.project_for_text("running xtask check") == "sinex"
    assert joins.infer_resource_class_from_cgroup("/sys/fs/cgroup/build.slice") is None
    assert joins.infer_resource_class_from_cgroup("/sys/fs/cgroup/agent.slice") is None
    assert (
        joins.infer_resource_class_from_cgroup("/sys/fs/cgroup/system.slice")
        == "system"
    )
    assert (
        joins.infer_resource_class_from_cgroup("/sys/fs/cgroup/notbuild.slice") is None
    )
    assert joins.infer_resource_class_from_cgroup("/sys/fs/cgroup/app.slice") is None
    assert joins.infer_resource_class_from_cgroup("") is None
    matched = joins.match_below(
        "polylogued.service",
        "/polylogue",
        {"cgroup_peaks": [{"cgroup": "/polylogue/x"}], "process_peaks": []},
    )
    assert matched["cgroup_peaks"]


def test_joins_build_workload_rows_minimal() -> None:
    rows = joins.build_workload_rows(
        systemd_units=[
            {
                "manager": "system",
                "unit": "x.service",
                "control_group": "/x",
                "resource_class": "obs",
                "active_state": "active",
                "sub_state": "running",
                "policy": {},
            }
        ],
        sinex={"rows": []},
        polylogue={"rows": []},
        below={"process_peaks": []},
    )
    assert any(r["source"] == "systemd" for r in rows)


def test_render_human_minimal() -> None:
    report = {
        "schema": "sinnix-observe-v1",
        "generated_at": "2026-05-19T00:00:00+00:00",
        "window": {"since": "10 min ago", "duration": "10 min"},
        "live_pressure": {"cpu": {"raw": ""}, "memory": {"raw": ""}, "io": {"raw": ""}},
        "blocked_tasks": [],
        "storage": {
            "mounts": [],
            "discard_queues": [],
            "fstrim_timer": {},
            "fstrim_service": {},
        },
        "systemd_units": [],
        "resource_slices": [],
        "chrome_io": {},
        "sinex_xtask_history": {"db": None, "rows": []},
        "polylogue_live_attempts": {"db": None, "rows": []},
        "below": {"cgroup_peaks": [], "process_peaks": []},
        "workload_rows": [],
        "gaps_summary": {},
    }
    out = render.render_human(report)
    assert "live pressure" in out
    assert "below hint" in out
    # No acknowledgements declared, so the section must not appear at all --
    # an empty "acknowledged outages" heading reads as a claim that nothing
    # is known-down, which is a different statement from staying silent.
    assert "acknowledged outages" not in out


def test_render_human_surfaces_acknowledged_outages() -> None:
    report = {
        "schema": "sinnix-observe-v1",
        "generated_at": "2026-05-19T00:00:00+00:00",
        "window": {"since": "10 min ago", "duration": "10 min"},
        "live_pressure": {"cpu": {"raw": ""}, "memory": {"raw": ""}, "io": {"raw": ""}},
        "blocked_tasks": [],
        "storage": {
            "mounts": [],
            "discard_queues": [],
            "fstrim_timer": {},
            "fstrim_service": {},
        },
        "systemd_units": [],
        "resource_slices": [],
        "chrome_io": {},
        "sinex_xtask_history": {"db": None, "rows": []},
        "polylogue_live_attempts": {"db": None, "rows": []},
        "below": {"cgroup_peaks": [], "process_peaks": []},
        "workload_rows": [],
        "gaps_summary": {},
        "runtime_inventory": {
            "surfaces": {
                "polylogued": {
                    "unit": "polylogued.service",
                    "acknowledged": {
                        "down": True,
                        "reason": "storage migration blocks every start",
                        "since": "2026-08-14",
                        "ref": "sinnix-qh6s",
                    },
                },
                "ollama": {
                    "unit": "ollama.service",
                    "acknowledged": {
                        "down": False,
                        "reason": "",
                        "since": "",
                        "ref": "",
                    },
                },
            }
        },
    }
    out = render.render_human(report)
    assert "acknowledged outages" in out
    assert "sinnix-qh6s" in out
    assert "storage migration blocks every start" in out
    # A surface that is NOT acknowledged must not be listed as known-down.
    assert "ollama.service" not in out


def test_cli_parse_args_defaults() -> None:
    args = cli.parse_args([])
    assert args.format == "human"
    assert args.offline is False
    args = cli.parse_args(["--offline", "--format", "json", "--limit", "3"])
    assert args.offline is True
    assert args.format == "json"
    assert args.limit == 3


def test_cli_section_collects_only_its_requested_owner(monkeypatch) -> None:
    args = argparse.Namespace(
        offline=True,
        limit=2,
        since="10 min ago",
        duration="10 min",
        format="json",
        section="pressure",
    )
    calls = []
    monkeypatch.setattr(
        cli,
        "collect_pressure",
        lambda offline: calls.append(("pressure", offline)) or {"available": True},
    )
    monkeypatch.setattr(
        cli,
        "collect_storage",
        lambda _offline: pytest.fail("unrequested storage collector ran"),
    )

    report = cli.collect_report(args)

    assert calls == [("pressure", True)]
    assert report["live_pressure"] == {"available": True}
    assert set(report) == {"schema", "generated_at", "window", "live_pressure"}


def test_cli_section_pages_rows_at_the_owner(monkeypatch) -> None:
    args = argparse.Namespace(
        offline=True,
        limit=20,
        since="10 min ago",
        duration="10 min",
        format="json",
        section="units",
        cursor=1,
        page_limit=2,
    )
    monkeypatch.setattr(
        cli,
        "collect_systemd_units",
        lambda _offline: [{"unit": f"fixture-{index}.service"} for index in range(4)],
    )

    report = cli.collect_report(args)

    assert report["systemd_units"] == {
        "total": 4,
        "cursor": 1,
        "next_cursor": 3,
        "rows": [
            {"unit": "fixture-1.service"},
            {"unit": "fixture-2.service"},
        ],
    }


def test_cli_collect_report_offline() -> None:
    args = argparse.Namespace(
        offline=True, limit=2, since="10 min ago", duration="10 min", format="json"
    )
    report = cli.collect_report(args)
    assert report["agent_gateway"]["schema"] == "sinnix-observe-agentctl-v1"
    assert report["schema"] == "sinnix-observe-v1"
    assert report["live_pressure"] == {"offline": True}
    assert isinstance(report["workload_rows"], list)
    assert "gaps_summary" in report


def test_agent_gateway_reads_canonical_agentctl_records(
    tmp_path, monkeypatch
) -> None:
    root = tmp_path / "sinnixd"
    jobs = root / "jobs"
    jobs.mkdir(parents=True)
    job_id = "00000000-0000-4000-8000-000000000001"
    (jobs / f"{job_id}.json").write_text(
        json.dumps(
            {
                "job_id": job_id,
                "unit": f"sinnixd-job-{job_id}.service",
                "schema_version": 4,
                "created_at": "2026-08-23T10:00:00Z",
                "spec": {
                    "kind": "attested-agent",
                    "project_id": "sinnix",
                    "timeout_seconds": 60,
                    "checkout": {"path": "/realm/worktrees/fixture"},
                    "contract": {"backend": "codex", "model": "fixture", "effort": "high"},
                },
                "state": {"phase": "succeeded", "terminal": True, "systemd": {"ControlGroup": "/agent.slice/x"}},
            }
        )
    )
    polylogue = root / "index.db"
    history_db = sqlite3.connect(polylogue)
    history_db.execute(
        "create virtual table messages_fts using fts5(session_id unindexed, text)"
    )
    history_db.execute(
        "insert into messages_fts values('codex-session:session-1', ?)",
        (f"agent job {job_id}",),
    )
    history_db.commit()
    history_db.close()
    monkeypatch.setenv("SINNIXD_STATE_DIR", str(root))
    monkeypatch.setenv("SINNIX_POLYLOGUE_INDEX_DB", str(polylogue))
    out = agent_gateway.collect_agent_gateway()
    assert out["schema"] == "sinnix-observe-agentctl-v1"
    assert out["correlations"][0]["terminal"] is True
    assert out["correlations"][0]["unit"] == f"sinnixd-job-{job_id}.service"
    assert out["correlations"][0]["cgroup"] == "/agent.slice/x"
    assert out["jobs"][0]["backend"] == "codex"
    assert (
        out["correlations"][0]["polylogue"]["session_id"] == "codex-session:session-1"
    )


def test_agent_gateway_bounds_malformed_sources(tmp_path, monkeypatch) -> None:
    root = tmp_path / "sinnixd"
    (root / "jobs").mkdir(parents=True)
    (root / "jobs/broken.json").write_text("{")
    (root / "jobs/declared.json").write_text(
        json.dumps(
            {
                "job_id": "declared",
                "unit": "sinnixd-job-declared.service",
                "schema_version": 4,
                "spec": {"kind": "declared-operation"},
                "state": {"phase": "succeeded"},
            }
        )
    )
    monkeypatch.setenv("SINNIXD_STATE_DIR", str(root))
    out = agent_gateway.collect_agent_gateway()
    assert out["malformed_records"] == ["broken.json"]
    assert out["jobs"] == []


def test_gateway_rows_use_agentctl_record_fields() -> None:
    rows = joins.build_gateway_rows(
        {
            "jobs": [
                {
                    "job_id": "j",
                    "unit": "sinnixd-job-j.service",
                    "backend": "codex",
                    "model": "fixture",
                    "effort": "high",
                    "checkout": {"path": "/realm/worktrees/j"},
                    "contract": {"backend": "codex"},
                    "state": {"phase": "running", "systemd": {"ControlGroup": "/agent.slice/j"}},
                }
            ],
        },
        {},
    )
    assert rows[0]["unit"] == "sinnixd-job-j.service"
    assert rows[0]["cgroup"] == "/agent.slice/j"
    assert rows[0]["metrics"]["backend"] == "codex"


def test_sqlite_failure_is_recorded_not_swallowed(tmp_path):
    """An unreadable database must not look like an empty one.

    sqlite_rows returns [] on failure so one bad database cannot take the
    whole observation down -- which is right, and was also the entire bug:
    the empty list was the only signal, so a query that could not run and a
    table with no rows produced identical output.
    """
    from sinnix_observe.sources import sqlite_util

    sqlite_util.clear_sqlite_errors()
    missing = tmp_path / "not-a-database.db"
    missing.write_text("this is not sqlite")

    rows = sqlite_util.sqlite_rows(missing, "select 1")

    assert rows == []
    errors = sqlite_util.sqlite_errors()
    assert len(errors) == 1
    assert str(missing) in errors[0]["db"]
    assert errors[0]["error"]


def test_successful_read_records_no_error(tmp_path):
    """Anti-vacuity for the test above: the accumulator must stay empty on
    the happy path, or 'errors is empty' would mean nothing."""
    import sqlite3

    from sinnix_observe.sources import sqlite_util

    db = tmp_path / "real.db"
    with sqlite3.connect(db) as conn:
        conn.execute("create table t (a integer)")
        conn.execute("insert into t values (7)")

    sqlite_util.clear_sqlite_errors()
    rows = sqlite_util.sqlite_rows(db, "select a from t")

    assert rows == [{"a": 7}]
    assert sqlite_util.sqlite_errors() == []


def test_gateway_polylogue_probe_failure_surfaces_as_a_gap_category() -> None:
    rows = joins.build_gateway_rows(
        {
            "jobs": [{"job_id": "j", "state": {"phase": "running"}}],
            "polylogue_error": "polylogue_index_unreadable",
        },
        {},
    )
    assert rows[0]["gaps"] == ["agent_gateway.polylogue.unavailable"]
