"""Per-module smoke tests: imports + one happy-path call per module."""

from __future__ import annotations

import argparse

from sinnix_observe import SCHEMA, cli, joins, render, runtime_inventory, util
from sinnix_observe.sources import (
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


def test_schema_constant() -> None:
    assert SCHEMA == "sinnix-observe-v1"


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


def test_runtime_inventory_fallback_excludes_retired_slices(monkeypatch) -> None:
    monkeypatch.setenv("SINNIX_RUNTIME_INVENTORY_FILE", "/does/not/exist")
    inventory = runtime_inventory.load_inventory()
    assert inventory["schema"] == "sinnix-runtime-inventory-v1"
    assert inventory["classes"]
    assert inventory["commandClasses"]
    assert ("system", "system-critical.slice") in runtime_inventory.observed_slices()
    assert (
        "system",
        "sinnix-maintenance.slice",
    ) not in runtime_inventory.observed_slices()
    sshd_class = runtime_inventory.resource_class_for_unit("sshd.service")
    assert sshd_class in inventory["classes"]


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
    assert (
        joins.infer_resource_class_from_cgroup("/sys/fs/cgroup/build.slice")
        == "developer-build"
    )
    assert (
        joins.infer_resource_class_from_cgroup("/sys/fs/cgroup/agent.slice")
        == "interactive-agent"
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


def test_cli_parse_args_defaults() -> None:
    args = cli.parse_args([])
    assert args.format == "human"
    assert args.offline is False
    args = cli.parse_args(["--offline", "--format", "json", "--limit", "3"])
    assert args.offline is True
    assert args.format == "json"
    assert args.limit == 3


def test_cli_collect_report_offline() -> None:
    args = argparse.Namespace(
        offline=True, limit=2, since="10 min ago", duration="10 min", format="json"
    )
    report = cli.collect_report(args)
    assert report["schema"] == "sinnix-observe-v1"
    assert report["live_pressure"] == {"offline": True}
    assert isinstance(report["workload_rows"], list)
    assert "gaps_summary" in report
