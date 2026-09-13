"""Per-module smoke tests: imports + one happy-path call per module."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3

import pytest
from sinnix_lib.process import Result
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
    assert util.float_or_zero("1.5") == 1.5
    assert util.float_or_zero(None) == 0.0
    assert util.words("a b  c") == ["a", "b", "c"]
    assert util.words(None) == []
    assert util.parse_counts('{"a": 1}') == {"a": 1}
    assert util.parse_counts(None) == {}
    assert util.normalize_timestamp(None) is None
    assert util.normalize_timestamp("2026-01-01T00:00:00Z") == "2026-01-01T00:00:00Z"
    assert util.normalize_timestamp("1767225600") == "2026-01-01T00:00:00Z"
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
    validated = Result(("noctalia",), 0, "Config is valid", "")
    monkeypatch.setattr(systemd, "run", lambda *_args, **_kwargs: validated)
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


def test_runtime_inventory_missing_is_explicitly_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("SINNIX_RUNTIME_INVENTORY_FILE", "/does/not/exist")
    inventory = runtime_inventory.load_inventory()
    assert inventory == {
        "available": False,
        "reason": "runtime inventory missing",
    }
    assert runtime_inventory.observed_slices() == []
    assert runtime_inventory.resource_class_for_unit("sshd.service") is None


def test_runtime_inventory_malformed_is_explicitly_unavailable(
    monkeypatch, tmp_path
) -> None:
    inventory_path = tmp_path / "runtime-inventory.json"
    inventory_path.write_text("{")
    monkeypatch.setenv("SINNIX_RUNTIME_INVENTORY_FILE", str(inventory_path))
    assert runtime_inventory.load_inventory() == {
        "available": False,
        "reason": "runtime inventory malformed",
    }


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


def test_polylogue_archive_inventory_reports_all_tier_states(
    tmp_path, monkeypatch
) -> None:
    root = tmp_path / "archive"
    root.mkdir()
    (root / "index.db").touch()
    (tmp_path / "source-target.db").touch()
    (root / "source.db").symlink_to(tmp_path / "source-target.db")
    (root / "ops.db").symlink_to(tmp_path / "missing.db")
    inventory = tmp_path / "runtime-inventory.json"
    inventory.write_text(json.dumps({"polylogue": {"archiveRoot": str(root)}}))
    monkeypatch.setenv("SINNIX_RUNTIME_INVENTORY_FILE", str(inventory))

    states = {row["name"]: row["state"] for row in polylogue.polylogue_tiers()["tiers"]}
    assert list(states) == [
        "index.db",
        "source.db",
        "embeddings.db",
        "ops.db",
        "audit.db",
        "user.db",
    ]
    assert states["index.db"] == "active"
    assert states["source.db"] == "compatibility"
    assert states["ops.db"] == "stale_compatibility"
    assert states["embeddings.db"] == "missing"


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
    assert report["agent_gateway"]["schema"] == "sinnix-observe-agentctl-v2"
    assert report["schema"] == "sinnix-observe-v1"
    assert report["live_pressure"] == {"offline": True}
    assert isinstance(report["workload_rows"], list)
    assert "gaps_summary" in report


def test_agent_gateway_reads_the_bounded_agentctl_projection(monkeypatch) -> None:
    monkeypatch.setattr(
        agent_gateway,
        "_snapshot",
        lambda limit: {
            "schema": "sinnix.agentctl.job-snapshot.v1",
            "groups": {"agent": {"running": 1}},
            "jobs": [
                {
                    "job_id": 7,
                    "label": "sinnix:worker:run",
                    "project": "sinnix",
                    "kind": "attested-agent",
                    "phase": "running",
                    "group": "agent",
                }
            ],
            "omitted": {"total": 1, "active": 0, "terminal": 1},
            "coverage": {"active": {"total": 1, "returned": 1}},
        },
    )
    out = agent_gateway.collect_agent_gateway()
    assert out["schema"] == "sinnix-observe-agentctl-v2"
    assert out["available"] is True
    assert out["groups"]["agent"]["running"] == 1
    assert out["jobs"][0]["job_id"] == 7
    assert out["omitted"]["terminal"] == 1


def test_agent_gateway_keeps_owner_failure_visible(monkeypatch) -> None:
    monkeypatch.setattr(
        agent_gateway,
        "_snapshot",
        lambda _limit: (_ for _ in ()).throw(RuntimeError("socket unavailable")),
    )
    out = agent_gateway.collect_agent_gateway()
    assert out["available"] is False
    assert out["jobs"] == []
    assert out["error"] == "socket unavailable"


def test_human_render_reports_owner_queue_omissions() -> None:
    rendered = render.render_human(
        {
            "generated_at": "2026-09-12T00:00:00Z",
            "window": {"since": "10 min ago"},
            "agent_gateway": {
                "available": True,
                "jobs": [
                    {
                        "job_id": 7,
                        "label": "sinnix:worker",
                        "phase": "running",
                        "group": "agent",
                    }
                ],
                "omitted": {"total": 50},
                "error": None,
            },
        }
    )
    assert "jobs=1 omitted=50" in rendered
    assert "7 sinnix:worker running group=agent" in rendered


def test_gateway_rows_use_agentctl_snapshot_fields() -> None:
    rows = joins.build_gateway_rows(
        {
            "jobs": [
                {
                    "job_id": 7,
                    "label": "sinnix:worker:run",
                    "project": "sinnix",
                    "kind": "attested-agent",
                    "phase": "running",
                    "group": "agent",
                }
            ],
            "available": True,
        },
        {},
    )
    assert rows[0]["source"] == "agentctl"
    assert rows[0]["project"] == "sinnix"
    assert rows[0]["metrics"]["group"] == "agent"


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

    from sinnix_observe.sources import sqlite_util

    db = tmp_path / "real.db"
    with sqlite3.connect(db) as conn:
        conn.execute("create table t (a integer)")
        conn.execute("insert into t values (7)")

    sqlite_util.clear_sqlite_errors()
    rows = sqlite_util.sqlite_rows(db, "select a from t")

    assert rows == [{"a": 7}]
    assert sqlite_util.sqlite_errors() == []


def test_gateway_failure_surfaces_as_a_gap_category() -> None:
    rows = joins.build_gateway_rows(
        {
            "jobs": [{"job_id": "j", "phase": "running"}],
            "available": False,
        },
        {},
    )
    assert rows[0]["gaps"] == ["agentctl.unavailable"]


def test_report_header_stamps_one_utc_grammar_through_the_shared_helper(
    monkeypatch,
) -> None:
    """``generated_at`` and the epoch-derived row stamps share one grammar.

    The report is read as one document -- the header's stamp is compared
    against the row stamps ``normalize_timestamp`` mints from epoch seconds --
    so both are ``%Y-%m-%dT%H:%M:%SZ``, and the header's comes from the
    estate's helper rather than a local copy.
    """
    args = argparse.Namespace(since="10 min ago", duration="10 min")
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
        cli._report_header(args)["generated_at"],
    )
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", util.normalize_timestamp("1767225600")
    )

    monkeypatch.setattr(cli, "utc_ts", lambda: "SENTINEL-UTC-TS")
    assert cli._report_header(args)["generated_at"] == "SENTINEL-UTC-TS"


def test_below_live_path_returns_the_report_dict(monkeypatch) -> None:
    """The live path must not lose the report to the subprocess result.
    Mutation: assigning `run(...)` to `result` fails this with TypeError."""
    from sinnix_observe.sources import below as below_module

    class Dump:
        ok = True
        stdout = "2026-09-06 00:00:00\tname\t/sys/fs/cgroup/x.slice\t1\t2\t3\t4\t5\n"

    monkeypatch.delenv("SINNIX_OBSERVE_BELOW_CGROUP_TSV", raising=False)
    monkeypatch.delenv("SINNIX_OBSERVE_BELOW_PROCESS_TSV", raising=False)
    monkeypatch.setattr(below_module, "run", lambda *a, **k: Dump())
    out = below_module.collect_below("10 min ago", "10 min", 10, offline=False)
    assert out["available"] is True
    assert out["cgroup_peaks"][0]["cgroup"] == "/sys/fs/cgroup/x.slice"


def test_current_profile_never_fans_out_expensive_collectors(monkeypatch):
    for name in (
        "collect_below",
        "collect_config_drift",
        "collect_chrome_io",
        "collect_storage",
        "collect_blocked_tasks",
        "collect_systemd_units",
        "collect_resource_slices",
        "collect_sinex_xtask",
        "collect_polylogue_live_attempts",
        "collect_agent_gateway",
    ):
        monkeypatch.setattr(
            cli, name, lambda *a, **k: pytest.fail("expensive background collector")
        )
    monkeypatch.setattr(cli, "collect_pressure", lambda _: {"memory": 5})
    monkeypatch.setattr(
        cli,
        "collect_current_units",
        lambda _: (_ for _ in ()).throw(RuntimeError("manager down")),
    )
    monkeypatch.setattr(cli, "collect_runtime_inventory", lambda _: {"surfaces": {}})
    report = cli.collect_report(
        cli.parse_args(["--format", "json", "--section", "current"])
    )
    assert report["live_pressure"] == {"memory": 5}
    assert report["sections"]["live_pressure"]["available"] is True
    assert report["sections"]["systemd_units"]["available"] is False
    assert report["runtime_inventory"] == {"surfaces": {}}
