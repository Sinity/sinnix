from __future__ import annotations

import json
import sqlite3
import time
from types import SimpleNamespace

import pytest
from machine_telemetry import allocator, collector
from sinnix_lib.process import BoundedResult


def row():
    return {
        "pid": 4242,
        "process_start_time_ticks": 987,
        "unit": "noctalia.service",
        "scope": "user",
        "exe": "/package/bin/.noctalia-wrapped",
    }


def payload(**changes):
    return {
        "schema_version": 1,
        "backend": "jemalloc",
        "units": "bytes",
        "status": "available",
        "pid": 4242,
        "observed_at_unix_ms": time.time_ns() // 1_000_000,
        **dict.fromkeys(allocator.COUNTERS, 0),
        "errors": [],
        **changes,
    }


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    user = SimpleNamespace(
        pw_uid=1001, pw_gid=100, pw_dir="/home/fixture", pw_name="fixture"
    )
    binary = tmp_path / "fixture/bin/noctalia"
    binary.parent.mkdir(parents=True)
    binary.write_text("fixture")
    monkeypatch.setattr(allocator, "PROFILE_ROOT", tmp_path)
    monkeypatch.setattr(allocator.pwd, "getpwnam", lambda name: user)
    monkeypatch.setattr(allocator.os, "geteuid", lambda: 0)
    context = {
        "uid": 1001,
        "start_ticks": 987,
        "XDG_RUNTIME_DIR": "/run/user/1001",
        "WAYLAND_DISPLAY": "wayland-7",
    }
    monkeypatch.setattr(allocator, "_context", lambda pid: dict(context))
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return BoundedResult(
            tuple(argv),
            0,
            json.dumps({"barVisible": True, "allocator": payload()}).encode(),
            b"",
        )

    monkeypatch.setattr(allocator, "run_bounded", run)
    return context, calls


def test_correct_identity_runtime_and_real_zero_counters(bridge):
    context, calls = bridge
    result = json.loads(allocator.observe(row(), "fixture"))
    assert result["status"] == "available"
    assert result["reason"] is None
    assert result["allocator"]["allocated_bytes"] == 0
    assert result["allocator"]["ownership"] == {
        "schema_version": 1,
        "status": "unavailable",
        "collector_reason": "not_provided",
    }
    assert "barVisible" not in result
    argv, options = calls[0]
    assert argv[:4] == ["setpriv", "--reuid=1001", "--regid=100", "--init-groups"]
    assert argv[-2:] == ["msg", "status"]
    assert options["env"]["HOME"] == "/home/fixture"
    assert options["env"]["XDG_RUNTIME_DIR"] == "/run/user/1001"
    assert options["env"]["WAYLAND_DISPLAY"] == "wayland-7"
    assert options["timeout"] == 1.0 and options["stdout_limit"] == 16384


@pytest.mark.parametrize(
    "defect",
    [
        "wrong_pid",
        "stale",
        "bool",
        "negative",
        "missing",
        "units",
        "unknown_schema",
        "bad_json",
        "legacy",
    ],
)
def test_bad_or_old_provider_is_unavailable_not_zero(bridge, monkeypatch, defect):
    value = payload()
    if defect == "wrong_pid":
        value["pid"] = 9
    if defect == "stale":
        value["observed_at_unix_ms"] = 0
    if defect == "bool":
        value["allocated_bytes"] = False
    if defect == "negative":
        value["resident_bytes"] = -1
    if defect == "missing":
        del value["mapped_bytes"]
    if defect == "units":
        value["units"] = "KiB"
    if defect == "unknown_schema":
        value["schema_version"] = 2
    data = (
        b"not json"
        if defect == "bad_json"
        else json.dumps(
            {"allocator": value} if defect != "legacy" else {"locked": False}
        ).encode()
    )
    monkeypatch.setattr(
        allocator,
        "run_bounded",
        lambda argv, **kw: BoundedResult(tuple(argv), 0, data, b""),
    )
    result = json.loads(allocator.observe(row(), "fixture"))
    assert result["status"] == "unavailable" and result["allocator"] is None
    assert result["reason"] == "invalid_payload"


def test_provider_unavailable_preserves_nulls_and_errno(bridge, monkeypatch):
    value = payload(
        status="unavailable",
        backend="unavailable",
        **dict.fromkeys(allocator.COUNTERS),
        errors=[{"field": "backend", "code": 95, "message": "not supported"}],
    )
    monkeypatch.setattr(
        allocator,
        "run_bounded",
        lambda argv, **kw: BoundedResult(
            tuple(argv), 0, json.dumps({"allocator": value}).encode(), b""
        ),
    )
    result = json.loads(allocator.observe(row(), "fixture"))
    assert result["reason"] == "provider_unavailable"
    assert all(result["allocator"][key] is None for key in allocator.COUNTERS)
    assert result["allocator"]["errors"][0]["code"] == 95


@pytest.mark.parametrize(
    "failure", ["timeout", "limited", "failed", "changed", "runtime"]
)
def test_supervision_and_identity_failures_remain_visible(bridge, monkeypatch, failure):
    context, calls = bridge
    if failure == "changed":
        counter = iter([dict(context), {**context, "start_ticks": 988}])
        monkeypatch.setattr(allocator, "_context", lambda pid: next(counter))
    if failure == "runtime":
        context["XDG_RUNTIME_DIR"] = "/run/user/0"
    if failure in {"timeout", "limited", "failed"}:
        monkeypatch.setattr(
            allocator,
            "run_bounded",
            lambda argv, **kw: BoundedResult(
                tuple(argv),
                1,
                b"",
                b"",
                timed_out=failure == "timeout",
                limited=failure == "limited",
            ),
        )
    result = json.loads(allocator.observe(row(), "fixture"))
    assert result["status"] == "unavailable" and result["allocator"] is None
    assert result["reason"] in {
        "timeout",
        "output_limit",
        "command_failed",
        "identity_changed",
        "runtime",
    }
    if failure == "runtime":
        assert not calls


def test_one_probe_only_and_other_processes_stay_unobserved(monkeypatch):
    calls = []
    monkeypatch.setattr(
        allocator,
        "observe",
        lambda r, user: calls.append(r["pid"]) or '{"status":"unavailable"}',
    )
    rows = [{**row(), "unit": "other.service"}, row(), {**row(), "pid": 999}]
    allocator.attach(rows, "fixture")
    assert calls == [4242]
    assert rows[0]["allocator_json"] is None and rows[2]["allocator_json"] is None


def test_existing_process_schema_adds_nullable_column_without_rewriting_history(
    tmp_path,
):
    database = tmp_path / "old.sqlite"
    with sqlite3.connect(database) as conn:
        collector.init_db(conn)
        conn.execute("ALTER TABLE process_memory_sample DROP COLUMN allocator_json")
        conn.execute(
            "INSERT INTO process_memory_sample (observed_at,host,schema_version,pid,process_start_time_ticks,rss_kb,pss_kb,private_clean_kb,private_dirty_kb,shared_clean_kb,shared_dirty_kb,swap_kb) VALUES ('2026-01-01','fixture',6,7,8,1,1,0,0,0,0,0)"
        )
        before = conn.execute(
            "SELECT id,observed_at,pid,pss_kb FROM process_memory_sample"
        ).fetchall()
        collector.init_db(conn)
        collector.init_db(conn)
        assert (
            conn.execute(
                "SELECT id,observed_at,pid,pss_kb FROM process_memory_sample"
            ).fetchall()
            == before
        )
        assert conn.execute(
            "SELECT allocator_json FROM process_memory_sample"
        ).fetchone() == (None,)


def test_cold_schema_persists_zero_unavailable_and_unobserved_distinctly(bridge):
    available = allocator.observe(row(), "fixture")
    unavailable = json.dumps(
        {
            "schema_version": 1,
            "status": "unavailable",
            "reason": "timeout",
            "allocator": None,
        }
    )
    with sqlite3.connect(":memory:") as conn:
        collector.init_db(conn)
        columns = [
            entry[1]
            for entry in conn.execute("PRAGMA table_info(process_memory_sample)")
            if entry[1] != "id"
        ]
        base = dict.fromkeys(columns)
        base.update(
            observed_at="2026-01-01",
            host="fixture",
            schema_version=6,
            pid=4242,
            process_start_time_ticks=987,
            rss_kb=1,
            pss_kb=1,
            private_clean_kb=0,
            private_dirty_kb=0,
            shared_clean_kb=0,
            shared_dirty_kb=0,
            swap_kb=0,
        )
        collector.insert_process_memory_rows(
            conn,
            [
                {**base, "allocator_json": value}
                for value in (available, unavailable, None)
            ],
        )
        assert conn.execute(
            "SELECT json_extract(allocator_json, '$.status'), json_extract(allocator_json, '$.allocator.allocated_bytes') FROM process_memory_sample ORDER BY id"
        ).fetchall() == [("available", 0), ("unavailable", None), (None, None)]


def ownership(**changes):
    now = time.time_ns() // 1_000_000
    return {
        "schema_version": 1,
        "provider": "luau",
        "status": "available",
        "pid": 4242,
        "observed_at_unix_ms": now,
        "units": "bytes",
        "runtime_count": 1,
        "reported_runtime_count": 1,
        "truncated_count": 0,
        "runtimes": [
            {
                "state_token": 1,
                "runtime_id": "fixture-runtime",
                "host_generation": 2,
                "status": "available",
                "bytes": 0,
                "sampled_at_unix_ms": now,
                "age_ms": 0,
                "reason": None,
            }
        ],
        **changes,
    }


def observe_ownership(monkeypatch, value):
    monkeypatch.setattr(
        allocator,
        "run_bounded",
        lambda argv, **kw: BoundedResult(
            tuple(argv),
            0,
            json.dumps({"allocator": payload(), "ownership": value}).encode(),
            b"",
        ),
    )
    return json.loads(allocator.observe(row(), "fixture"))


def test_valid_optional_ownership_keeps_real_zero_and_ignores_unknown_fields(
    bridge, monkeypatch
):
    value = ownership()
    value["ui_secret"] = "excluded"
    value["runtimes"][0]["ui_secret"] = "excluded"
    result = observe_ownership(monkeypatch, value)
    assert result["status"] == "available"
    stored = result["allocator"]["ownership"]
    assert stored["status"] == "available" and stored["runtimes"][0]["bytes"] == 0
    assert "ui_secret" not in stored and "ui_secret" not in stored["runtimes"][0]


def test_stale_worker_bytes_remain_last_known_without_age_threshold(
    bridge, monkeypatch
):
    value = ownership(status="partial")
    value["runtimes"][0].update(
        status="stale",
        bytes=123,
        age_ms=3_600_000,
        sampled_at_unix_ms=value["observed_at_unix_ms"] - 3_600_000,
        reason="worker_in_flight",
    )
    result = observe_ownership(monkeypatch, value)
    assert result["status"] == "available"
    assert result["allocator"]["ownership"] == value


def test_unobserved_ownership_retains_nulls_and_empty_registry_is_zero(
    bridge, monkeypatch
):
    value = ownership(status="unavailable")
    value["runtimes"][0].update(
        status="unavailable",
        host_generation=None,
        bytes=None,
        sampled_at_unix_ms=None,
        age_ms=None,
        reason="not_observed",
    )
    assert observe_ownership(monkeypatch, value)["allocator"]["ownership"] == value
    empty = ownership(runtime_count=0, reported_runtime_count=0, runtimes=[])
    assert observe_ownership(monkeypatch, empty)["allocator"]["ownership"] == empty


def test_ownership_array_bound_and_truncation_counts_are_preserved(bridge, monkeypatch):
    value = ownership(
        status="partial", runtime_count=35, reported_runtime_count=32, truncated_count=3
    )
    value["runtimes"] = [
        {**value["runtimes"][0], "state_token": i + 1} for i in range(32)
    ]
    assert observe_ownership(monkeypatch, value)["allocator"]["ownership"] == value


@pytest.mark.parametrize(
    "defect",
    [
        "not_object",
        "unsupported",
        "wrong_pid",
        "old_report",
        "missing",
        "count_bool",
        "count_mismatch",
        "too_many",
        "duplicate_token",
        "long_id",
        "control_id",
        "negative_bytes",
        "counter_bool",
        "null_current",
        "non_null_unavailable",
        "bad_reason",
        "bad_generation",
        "long_reason",
        "incorrect_status",
        "noncanonical_id",
    ],
)
def test_optional_ownership_defects_preserve_sound_base_allocator(
    bridge, monkeypatch, defect
):
    value = ownership()
    runtime = value["runtimes"][0]
    if defect == "not_object":
        value = []
    elif defect == "unsupported":
        value["schema_version"] = 2
    elif defect == "wrong_pid":
        value["pid"] = 7
    elif defect == "old_report":
        value["observed_at_unix_ms"] = 0
    elif defect == "missing":
        del runtime["age_ms"]
    elif defect == "count_bool":
        value["runtime_count"] = True
    elif defect == "count_mismatch":
        value["runtime_count"] = 2
    elif defect == "too_many":
        value.update(runtime_count=33, reported_runtime_count=33)
        value["runtimes"] = [{**runtime, "state_token": i + 1} for i in range(33)]
    elif defect == "duplicate_token":
        value.update(
            runtime_count=2, reported_runtime_count=2, runtimes=[runtime, dict(runtime)]
        )
    elif defect == "long_id":
        runtime["runtime_id"] = "x" * 129
    elif defect == "control_id":
        runtime["runtime_id"] = "fixture\n"
    elif defect == "negative_bytes":
        runtime["bytes"] = -1
    elif defect == "counter_bool":
        runtime["bytes"] = True
    elif defect == "null_current":
        runtime["bytes"] = None
    elif defect == "non_null_unavailable":
        runtime.update(status="unavailable", reason="not_observed")
    elif defect == "bad_reason":
        runtime.update(status="stale", reason="unknown")
    elif defect == "bad_generation":
        runtime["host_generation"] = -1
    elif defect == "incorrect_status":
        value["status"] = "unavailable"
    elif defect == "noncanonical_id":
        runtime["runtime_id"] = "fixture runtime"
    elif defect == "long_reason":
        runtime.update(
            status="unavailable",
            bytes=None,
            sampled_at_unix_ms=None,
            age_ms=None,
            reason="x" * 1024,
        )
    result = observe_ownership(monkeypatch, value)
    assert result["status"] == "available" and result["reason"] is None
    assert result["allocator"]["allocated_bytes"] == 0
    stored = result["allocator"]["ownership"]
    assert stored == {
        "schema_version": 1,
        "status": "unavailable",
        "collector_reason": "unsupported_schema"
        if defect == "unsupported"
        else "invalid_payload",
    }


@pytest.mark.parametrize(
    "reason",
    ["runtime_id_too_long", "runtime_id_invalid", "host_absent", "worker_in_flight"],
)
def test_unavailable_runtime_reasons_and_prior_generation_survive(
    bridge, monkeypatch, reason
):
    value = ownership(status="unavailable")
    value["runtimes"][0].update(
        status="unavailable",
        bytes=None,
        sampled_at_unix_ms=None,
        age_ms=None,
        reason=reason,
    )
    if reason.startswith("runtime_id_"):
        value["runtimes"][0]["runtime_id"] = None
    assert observe_ownership(monkeypatch, value)["allocator"]["ownership"] == value


def test_truncated_unobserved_rows_are_partial_not_empty(bridge, monkeypatch):
    value = ownership(status="partial", runtime_count=2, truncated_count=1)
    value["runtimes"][0].update(
        status="unavailable",
        host_generation=None,
        bytes=None,
        sampled_at_unix_ms=None,
        age_ms=None,
        reason="not_observed",
    )
    assert observe_ownership(monkeypatch, value)["allocator"]["ownership"] == value
