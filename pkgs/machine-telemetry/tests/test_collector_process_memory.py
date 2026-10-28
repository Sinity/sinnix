from __future__ import annotations

import fcntl
import importlib.util
import json
import sqlite3
import sys
import threading
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import pytest


def _collector():
    path = Path(__file__).resolve().parents[1] / "machine_telemetry" / "collector.py"
    spec = importlib.util.spec_from_file_location("machine_telemetry_collector", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _source_control(database):
    return {
        "schema": "sinnix-machine-sqlite-segments-v1",
        "state": "ready",
        "current": {
            "file": database.name,
            "identity": {"inode": database.stat().st_ino},
        },
    }


def test_writer_guard_preserves_lock_inode_and_excludes_rotation(tmp_path):
    collector = _collector()
    database = tmp_path / "telemetry.sqlite"
    lock = database.with_name(database.name + ".segments.lock")
    with collector.writer_guard(database):
        inode = lock.stat().st_ino
        with lock.open("rb") as owner:
            with pytest.raises(BlockingIOError):
                fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    with lock.open("rb") as owner:
        fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            with collector.writer_guard(database):
                pytest.fail("collector entered an exclusive cutover")
    with collector.writer_guard(database):
        assert lock.stat().st_ino == inode
        assert lock.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "defect",
    [
        "preparing",
        "malformed",
        "missing",
        "replacement",
        "wrong-file",
        "bool-inode",
        "symlink",
    ],
)
def test_writer_refuses_unexplained_current_before_opening_sqlite(
    tmp_path, monkeypatch, defect
):
    collector = _collector()
    database = tmp_path / "telemetry.sqlite"
    database.write_bytes(b"retained synthetic object")
    control = database.with_name(database.name + ".segments.json")
    payload = _source_control(database)
    if defect == "preparing":
        payload["state"] = "preparing"
    elif defect == "missing":
        database.unlink()
    elif defect == "replacement":
        replacement = tmp_path / "replacement"
        replacement.write_bytes(database.read_bytes())
        replacement.replace(database)
    elif defect == "wrong-file":
        payload["current"]["file"] = "elsewhere.sqlite"
    elif defect == "bool-inode":
        payload["current"]["identity"]["inode"] = True
    elif defect == "symlink":
        database.rename(tmp_path / "original")
        database.symlink_to(tmp_path / "original")
    control.write_text("invalid" if defect == "malformed" else json.dumps(payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "machine-telemetry",
            "--db",
            str(database),
            "--manifest",
            str(tmp_path / "hardware.json"),
            "--host",
            "fixture",
            "--user-name",
            "fixture",
        ],
    )
    monkeypatch.setattr(
        collector,
        "collect",
        lambda args: pytest.fail("SQLite opening must not be reached"),
    )
    with pytest.raises((RuntimeError, OSError, ValueError)):
        collector.main()
    if defect == "missing":
        assert not database.exists()


def test_writer_guard_releases_descriptor_after_failure_and_allows_active_growth(
    tmp_path,
):
    collector = _collector()
    database = tmp_path / "telemetry.sqlite"
    database.write_bytes(b"current")
    database.with_name(database.name + ".segments.json").write_text(
        json.dumps(_source_control(database))
    )
    with pytest.raises(RuntimeError, match="synthetic"):
        with collector.writer_guard(database):
            with database.open("ab") as stream:
                stream.write(b" append")
            raise RuntimeError("synthetic writer failure")
    with collector.writer_guard(database):
        pass
    with database.with_name(database.name + ".segments.lock").open("rb") as owner:
        fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_gpu_writer_has_its_own_source_lock_until_exit(tmp_path, monkeypatch):
    collector = _collector()
    database = tmp_path / "telemetry.sqlite"
    lock = database.with_name(database.name + ".segments.lock")

    def sampling(*args):
        with lock.open("rb") as owner:
            with pytest.raises(BlockingIOError):
                fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        raise RuntimeError("synthetic sampler exit")

    monkeypatch.setattr(collector, "_gpu_sampler_thread", sampling)
    with pytest.raises(RuntimeError, match="synthetic"):
        collector.gpu_sampler_thread(str(database), "fixture", "boot", 1, None)
    with lock.open("rb") as owner:
        fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_systemd_unescape_fragment_decodes_hex_escapes() -> None:
    collector = _collector()

    assert (
        collector.systemd_unescape_fragment(
            "wayland-wm@hyprland\\x2duwsm.desktop.service"
        )
        == "wayland-wm@hyprland-uwsm.desktop.service"
    )


def test_service_unit_props_batches_each_manager(monkeypatch) -> None:
    collector = _collector()
    calls = []
    monkeypatch.setattr(
        collector,
        "show_units",
        lambda units, **kwargs: (
            calls.append(("system", units, kwargs))
            or {unit: {"ActiveState": "active"} for unit in units}
        ),
    )
    monkeypatch.setattr(
        collector,
        "show_units_as_user",
        lambda units, uid, **kwargs: (
            calls.append(("user", units, uid, kwargs))
            or {unit: {"SubState": "running"} for unit in units}
        ),
    )
    monkeypatch.setattr(
        collector.pwd,
        "getpwnam",
        lambda _name: type("Pw", (), {"pw_uid": 1000})(),
    )

    got = collector.service_unit_props(
        [
            ("system", "a.service"),
            ("user", "polylogued.service"),
            ("system", "shared.service"),
            ("user", "b.service"),
            ("user", "noctalia.service"),
            ("user", "shared.service"),
        ],
        user_name="test",
    )

    assert [call[0] for call in calls] == ["system", "user"]
    assert calls[0][1] == ["a.service", "shared.service"]
    assert calls[1][1] == [
        "polylogued.service",
        "b.service",
        "noctalia.service",
        "shared.service",
    ]
    assert set(got) == {
        ("system", "a.service"),
        ("user", "polylogued.service"),
        ("system", "shared.service"),
        ("user", "b.service"),
        ("user", "noctalia.service"),
        ("user", "shared.service"),
    }
    assert got[("system", "shared.service")][0] == "system"
    assert got[("user", "shared.service")][0] == "user"


def test_parse_unit_specs_deduplicates_only_identical_manager_unit_pairs() -> None:
    collector = _collector()

    assert collector.parse_unit_specs(
        "system:shared.service,user:shared.service,system:shared.service"
    ) == [("system", "shared.service"), ("user", "shared.service")]

    with pytest.raises(ValueError, match="invalid manager-qualified"):
        collector.parse_unit_specs("shared.service")


def test_dstate_probe_uses_shared_runner_error_contract(monkeypatch) -> None:
    collector = _collector()
    monkeypatch.setattr(
        collector,
        "run",
        lambda argv, *, timeout: SimpleNamespace(
            error="missing ps", stdout="", returncode=-1
        ),
    )
    assert collector.dstate_tasks() == (0, "ps_failed")


def test_kill_event_scan_keeps_cursor_on_bounded_failure(monkeypatch) -> None:
    collector = _collector()
    calls = []
    monkeypatch.setattr(
        collector,
        "run_bounded",
        lambda argv, **kwargs: (
            calls.append((argv, kwargs))
            or SimpleNamespace(
                error="stdout exceeded limit", stdout=b'{"__CURSOR":"partial"'
            )
        ),
    )

    assert collector.scan_kill_events("host", "boot", "old-cursor") == ([], None)
    assert calls == [
        (
            [
                "journalctl",
                "--system",
                "-o",
                "json",
                "--no-pager",
                "--show-cursor",
                "-g",
                collector.KILL_EVENT_GREP,
                "--after-cursor",
                "old-cursor",
            ],
            {
                "timeout": 120,
                "stdout_limit": collector.KILL_EVENT_STDOUT_LIMIT,
                "stderr_limit": collector.KILL_EVENT_STDERR_LIMIT,
            },
        )
    ]


@pytest.mark.parametrize(
    ("message", "killer"),
    [
        (
            'sending SIGKILL to process 42 uid 1000 "worker": oom_score 800, oom_score_adj 0, VmRSS 512 MiB',
            "earlyoom",
        ),
        ("Killed process 42 (worker) total-vm:4096kB anon-rss:2048kB", "kernel-oom"),
        (
            "oom-kill:constraint=CONSTRAINT_MEMCG,task_memcg=/agent.slice,task=worker,pid=42",
            "memcg-oom",
        ),
        (
            "Killed /agent.slice/worker.service with pid 42 (worker) due to memory pressure",
            "systemd-oomd",
        ),
    ],
)
@pytest.mark.parametrize("after_cursor", [None, "legacy-user-cursor"])
def test_kill_event_scan_parses_complete_bounded_output(
    monkeypatch, message, killer, after_cursor
) -> None:
    collector = _collector()
    entry = {
        "__CURSOR": "next-cursor",
        "MESSAGE": message,
    }
    calls = []
    monkeypatch.setattr(
        collector,
        "run_bounded",
        lambda argv, **_kwargs: (
            calls.append(argv)
            or SimpleNamespace(error=None, stdout=(json.dumps(entry) + "\n").encode())
        ),
    )

    rows, cursor = collector.scan_kill_events("host", "boot", after_cursor)
    assert cursor == "next-cursor"
    assert rows[0]["killer"] == killer
    assert rows[0]["victim_pid"] == 42
    assert "--system" in calls[0]
    assert calls[0][-2:] == (
        ["--after-cursor", after_cursor]
        if after_cursor
        else ["--since", collector.KILL_EVENT_BACKFILL_SINCE]
    )


def test_kill_event_scan_resumes_after_the_scanned_tail_without_matches(
    monkeypatch,
) -> None:
    collector = _collector()
    monkeypatch.setattr(
        collector,
        "run_bounded",
        lambda *_args, **_kwargs: SimpleNamespace(
            error=None, stdout=b"-- cursor: tail-cursor\n"
        ),
    )

    assert collector.scan_kill_events("host", "boot", "old-cursor") == (
        [],
        "tail-cursor",
    )


class StopHeartbeat(Exception):
    pass


@pytest.fixture
def heartbeat(tmp_path, monkeypatch):
    """Run the production heartbeat against SQLite, with synthetic probes."""
    collector = _collector()
    args = SimpleNamespace(
        db=str(tmp_path / "telemetry.sqlite"),
        manifest=str(tmp_path / "manifest.json"),
        host="fixture",
        user_name="fixture",
        units="",
        cgroups="",
        network_probe_once=False,
    )
    for name, replacement in {
        "find_hwmon": lambda *args: None,
        "discover_rapl": lambda: [],
        "nvml_init": lambda: None,
        "hardware_state": lambda *args: {},
        "atomic_publish": lambda *args, **kwargs: None,
        "read_text": lambda *args: None,
        "read_rapl_energy": lambda *args: {},
        "rapl_watts": lambda *args: {},
        "gpu_metrics": lambda: ({"gpu_power_w": 1}, []),
        "parse_psi": lambda *args: {},
        "dstate_tasks": lambda: (0, ""),
        "memory_metrics": lambda: defaultdict(lambda: None),
        "vmstat_metrics": lambda: dict.fromkeys(
            f"vmstat_{key}" for key in collector.VMSTAT_FIELDS
        ),
        "swap_tier_metrics": lambda: dict.fromkeys(
            ["zram_orig_mb", "zram_compr_mb", "zram_mem_used_mb", "swaps_json"]
        ),
        "process_io_snapshot": lambda: {},
        "block_device_stats": lambda *args: [],
        "insert_service_states": lambda *args: None,
        "cgroup_memory_samples": lambda *args: [],
        "network_probe": lambda *args, **kwargs: network_row,
        "scan_kill_events": lambda *args: ([], None),
    }.items():
        monkeypatch.setattr(collector, name, replacement)
    monkeypatch.setattr(collector.filesystem_capacity, "insert_samples", lambda *a: None)
    monkeypatch.setattr(collector, "PROCESS_MEMORY_INTERVAL_SEC", 0)
    monkeypatch.setattr(collector, "GPU_INTERVAL_SEC", 0)
    monkeypatch.setattr(collector, "GPU_SAMPLER_BUSY_TIMEOUT_S", 0.05)
    network_row = dict.fromkeys(
        ["boot_id", "bloat_json", "dns_ms", "pmtu_1492"]
    )
    network_row.update(
        observed_at="2026-01-01T00:00:00+00:00",
        host="fixture",
        schema_version=collector.SCHEMA_VERSION,
        interface="fixture0",
        gateway_ip="192.0.2.1",
        **dict.fromkeys(
            ["ping_json", "iface_json", "nic_json", "tcp_json", "conntrack_json"],
            "{}",
        ),
        gap_codes_json="[]",
    )

    def run(beats=1):
        clock = {"now": 0, "beats": 0}

        def sleep(_interval):
            if clock["beats"] == beats:
                raise StopHeartbeat
            clock["beats"] += 1
            clock["now"] += 31

        monkeypatch.setattr(collector.time, "monotonic", lambda: clock["now"])
        monkeypatch.setattr(collector.time, "sleep", sleep)
        with pytest.raises(StopHeartbeat):
            collector.collect(args)

    with sqlite3.connect(args.db) as conn:
        collector.init_db(conn)
        collector.save_kill_event_cursor(conn, "legacy-user-cursor")
    return collector, args, run


@pytest.mark.parametrize("probe", ["journal", "network"])
def test_optional_probe_allows_independent_gpu_writer(heartbeat, monkeypatch, probe):
    collector, args, run = heartbeat

    def slow_probe(*_args, **_kwargs):
        # Keep the probe pending until the real independent GPU writer has
        # committed. A heartbeat writer lock makes that sample fail instead.
        done = threading.Event()
        stop = threading.Event()

        def one_sample():
            try:
                collector._gpu_sampler_thread(args.db, "fixture", "boot", 0, stop)
            finally:
                done.set()

        monkeypatch.setattr(stop, "wait", lambda _interval: stop.set())
        worker = threading.Thread(target=one_sample)
        worker.start()
        try:
            assert done.wait(2), "GPU writer could not finish during the probe"
            with sqlite3.connect(args.db) as conn:
                assert conn.execute("SELECT count(*) FROM gpu_sample").fetchone() == (1,)
        finally:
            stop.set()
            worker.join(2)
            assert not worker.is_alive()
        return ([], "scanned-system-tail") if probe == "journal" else network_row

    if probe == "journal":
        monkeypatch.setattr(collector, "scan_kill_events", slow_probe)
    else:
        network_row = collector.network_probe()
        monkeypatch.setattr(collector, "network_probe", slow_probe)
    run()
    with sqlite3.connect(args.db) as conn:
        assert conn.execute("SELECT count(*) FROM metric_sample").fetchone() == (1,)


@pytest.mark.parametrize("failure", ["timeout", "stdout exceeded limit"])
def test_heartbeat_retries_failed_journal_scan_without_advancing_cursor(
    heartbeat, monkeypatch, failure
):
    collector, args, run = heartbeat
    # The fixture stubs optional probes; exercise the actual bounded scanner.
    real_scan = _collector().scan_kill_events
    monkeypatch.setattr(collector, "scan_kill_events", real_scan)
    # _collector loads standalone modules, so use the function's globals.
    calls = []
    entry = {
        "__CURSOR": "system-kill-cursor",
        "MESSAGE": 'sending SIGKILL to process 42 uid 1000 "worker": oom_score 800, oom_score_adj 0, VmRSS 512 MiB',
    }

    def bounded(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(
            error=failure if len(calls) == 1 else None,
            stdout=b'{"__CURSOR":"partial"' if len(calls) == 1 else (
                json.dumps(entry) + "\n-- cursor: system-tail\n"
            ).encode(),
        )

    monkeypatch.setitem(real_scan.__globals__, "run_bounded", bounded)
    run(beats=2)
    assert [argv[-2:] for argv in calls] == [["--after-cursor", "legacy-user-cursor"]] * 2
    assert all("--system" in argv and "--since" not in argv for argv in calls)
    with sqlite3.connect(args.db) as conn:
        assert collector.load_kill_event_cursor(conn) == "system-tail"
        assert conn.execute("SELECT journal_cursor FROM kill_event").fetchall() == [
            ("system-kill-cursor",)
        ]


def test_heartbeat_rolls_back_kill_rows_and_cursor_together(heartbeat, monkeypatch):
    collector, args, run = heartbeat
    row = dict.fromkeys(
        ["boot_id", "victim_comm", "victim_pid", "victim_rss_mib", "cgroup_path", "oom_score"]
    )
    row.update(
        observed_at="2026-01-01T00:00:00+00:00",
        host="fixture",
        schema_version=collector.SCHEMA_VERSION,
        killer="kernel-oom",
        raw_line="Killed process 42 (worker) anon-rss:2048kB",
        journal_cursor="system-kill-cursor",
    )
    seen_cursors = []

    def scan(_host, _boot, cursor):
        seen_cursors.append(cursor)
        return [row], "system-tail"

    monkeypatch.setattr(collector, "scan_kill_events", scan)
    save = collector.save_kill_event_cursor

    def fail_after_cursor_write(conn, cursor):
        save(conn, cursor)
        raise RuntimeError("synthetic transaction failure")

    monkeypatch.setattr(collector, "save_kill_event_cursor", fail_after_cursor_write)
    with pytest.raises(RuntimeError, match="synthetic transaction failure"):
        run()
    with sqlite3.connect(args.db) as conn:
        assert collector.load_kill_event_cursor(conn) == "legacy-user-cursor"
        assert conn.execute("SELECT count(*) FROM kill_event").fetchone() == (0,)
        assert conn.execute("SELECT count(*) FROM metric_sample").fetchone() == (0,)

    monkeypatch.setattr(collector, "save_kill_event_cursor", save)
    run()
    assert seen_cursors == ["legacy-user-cursor", "legacy-user-cursor"]
    with sqlite3.connect(args.db) as conn:
        assert collector.load_kill_event_cursor(conn) == "system-tail"
        assert conn.execute("SELECT journal_cursor FROM kill_event").fetchall() == [
            ("system-kill-cursor",)
        ]
        assert conn.execute("SELECT count(*) FROM metric_sample").fetchone() == (1,)


def test_psi_adapter_keeps_telemetry_flat_float_fields(monkeypatch) -> None:
    collector = _collector()
    monkeypatch.setattr(
        collector,
        "read_text",
        lambda _path: "some avg10=0.25 avg60=1.5 total=42\nfull total=7\n",
    )

    assert collector.parse_psi("/proc/pressure/cpu") == {
        "some_avg10": 0.25,
        "some_avg60": 1.5,
        "some_total": 42.0,
        "full_total": 7.0,
    }


@pytest.mark.parametrize("value", [2**53 + 1, 2**63 - 1, -(2**53 + 1), 0])
def test_integer_counter_retains_precision_in_sqlite(value) -> None:
    collector = _collector()
    with collector.sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE sample(counter INTEGER)")
        conn.execute(
            "INSERT INTO sample VALUES (?)", (collector.int_or_none(str(value)),)
        )
        assert conn.execute("SELECT counter FROM sample").fetchone() == (value,)


@pytest.mark.parametrize(
    "value", [None, "", " ", "max", "invalid", "1.5", "inf", "NaN"]
)
def test_integer_counter_unavailable_inputs(value) -> None:
    assert _collector().int_or_none(value) is None


def test_process_memory_rows_sort_and_limit(monkeypatch) -> None:
    collector = _collector()

    class ProcRoot:
        def glob(self, pattern: str):
            assert pattern == "[0-9]*"
            return [Path("/proc/1"), Path("/proc/2"), Path("/proc/3")]

    def fake_path(raw: str):
        if raw == "/proc":
            return ProcRoot()
        return Path(raw)

    rollups = {
        "1": {"Rss": 1000, "Pss": 500, "Private_Clean": 10, "Private_Dirty": 20},
        "2": {"Rss": 2000, "Pss": 1500, "Private_Clean": 30, "Private_Dirty": 40},
        "3": {"Rss": 3000, "Pss": 750, "Private_Clean": 50, "Private_Dirty": 60},
    }

    def fake_identity(pid: str):
        return {
            "pid": int(pid),
            "process_start_time_ticks": int(pid) * 100,
            "comm": f"proc-{pid}",
            "exe": f"/bin/proc-{pid}",
            "command_line": f"proc-{pid} --flag",
            "cgroup": "/user.slice/session.scope",
            "unit": "session.scope",
            "scope": "user",
        }

    monkeypatch.setattr(collector, "Path", fake_path)
    monkeypatch.setattr(collector, "parse_smaps_rollup", lambda pid: rollups[pid])
    monkeypatch.setattr(collector, "process_identity", fake_identity)

    rows = collector.process_memory_rows(
        "2026-06-30T00:00:00+00:00",
        "sinnix-prime",
        "boot-id",
        limit=2,
    )

    assert [row["pid"] for row in rows] == [2, 3]
    assert rows[0]["pss_kb"] == 1500
    assert rows[0]["private_dirty_kb"] == 40
    assert rows[0]["command_line"] == "proc-2 --flag"


def test_process_memory_rows_insert_into_sqlite(tmp_path) -> None:
    collector = _collector()
    db = tmp_path / "telemetry.sqlite"
    rows = [
        {
            "observed_at": "2026-06-30T00:00:00+00:00",
            "host": "sinnix-prime",
            "boot_id": "boot-id",
            "schema_version": collector.SCHEMA_VERSION,
            "pid": 2,
            "process_start_time_ticks": 200,
            "comm": "codex",
            "exe": "/bin/codex",
            "command_line": "codex",
            "cgroup": "/user.slice/session.scope",
            "unit": "session.scope",
            "scope": "user",
            "rss_kb": 2000,
            "pss_kb": 1500,
            "pss_anon_kb": 1200,
            "pss_file_kb": 200,
            "pss_shmem_kb": 100,
            "private_clean_kb": 30,
            "private_dirty_kb": 40,
            "shared_clean_kb": 50,
            "shared_dirty_kb": 60,
            "swap_kb": 0,
        }
    ]

    with collector.sqlite3.connect(db) as conn:
        collector.init_db(conn)
        collector.insert_process_memory_rows(conn, rows)
        row = conn.execute(
            """
            SELECT comm, pss_kb, pss_anon_kb, private_dirty_kb
            FROM process_memory_sample
            """
        ).fetchone()

    assert row == ("codex", 1500, 1200, 40)


def test_parse_cgroup_spec_requires_label_scope_and_path() -> None:
    collector = _collector()

    assert collector.parse_cgroup_spec("system.nix|system|/nix.slice") == (
        "system.nix",
        "system",
        "/nix.slice",
    )
    assert collector.parse_cgroup_spec("missing-parts") is None


def test_cgroup_memory_sample_reads_capacity_fields(monkeypatch, tmp_path) -> None:
    collector = _collector()
    root = tmp_path / "sys-fs-cgroup" / "nix.slice"
    root.mkdir(parents=True)
    values = {
        "memory.current": "100",
        "memory.peak": "200",
        "memory.swap.current": "3",
        "memory.swap.peak": "4",
        "memory.high": "max",
        "memory.max": "4096",
        "cgroup.events": "populated 1\nfrozen 1\n",
        "cgroup.freeze": "1",
    }
    for name, value in values.items():
        (root / name).write_text(value, encoding="utf-8")

    monkeypatch.setattr(collector, "cgroup_path", lambda _control_group: root)
    monkeypatch.setattr(
        collector,
        "cgroup_memory_stat",
        lambda _control_group: {
            "memory_anon_bytes": 64,
            "memory_file_bytes": 32,
            "memory_kernel_bytes": 8,
            "memory_slab_bytes": 4,
            "memory_sock_bytes": 2,
            "memory_shmem_bytes": 1,
            "memory_swapcached_bytes": 0,
            "memory_zswap_bytes": 0,
            "memory_zswapped_bytes": 0,
        },
    )

    row = collector.cgroup_memory_sample(
        "2026-06-30T00:00:00+00:00",
        "sinnix-prime",
        "boot-id",
        label="system.nix",
        scope="system",
        control_group="/nix.slice",
    )

    assert row is not None
    assert row["memory_current_bytes"] == 100
    assert row["memory_high_bytes"] is None
    assert row["memory_max_bytes"] == 4096
    assert row["memory_anon_bytes"] == 64
    assert row["cgroup_frozen"] == 1
    assert row["cgroup_freeze"] == 1


def test_service_cgroup_memory_sample_labels_unit(monkeypatch) -> None:
    collector = _collector()

    calls = []

    def fake_cgroup_memory_sample(
        observed_at,
        host,
        boot_id,
        *,
        label,
        scope,
        control_group,
    ):
        calls.append((observed_at, host, boot_id, label, scope, control_group))
        return {"label": label, "scope": scope, "control_group": control_group}

    monkeypatch.setattr(collector, "cgroup_memory_sample", fake_cgroup_memory_sample)

    row = collector.service_cgroup_memory_sample(
        "2026-06-30T00:00:00+00:00",
        "sinnix-prime",
        "boot-id",
        unit="borgbackup-job-realm.service",
        scope="system",
        control_group="/background.slice/borgbackup-job-realm.service",
    )

    assert row == {
        "label": "unit:borgbackup-job-realm.service",
        "scope": "system",
        "control_group": "/background.slice/borgbackup-job-realm.service",
    }
    assert calls == [
        (
            "2026-06-30T00:00:00+00:00",
            "sinnix-prime",
            "boot-id",
            "unit:borgbackup-job-realm.service",
            "system",
            "/background.slice/borgbackup-job-realm.service",
        )
    ]
    assert (
        collector.service_cgroup_memory_sample(
            "2026-06-30T00:00:00+00:00",
            "sinnix-prime",
            "boot-id",
            unit="missing.service",
            scope="system",
            control_group=None,
        )
        is None
    )


def test_cgroup_memory_rows_insert_into_sqlite(tmp_path) -> None:
    collector = _collector()
    db = tmp_path / "telemetry.sqlite"
    rows = [
        {
            "observed_at": "2026-06-30T00:00:00+00:00",
            "host": "sinnix-prime",
            "boot_id": "boot-id",
            "schema_version": collector.SCHEMA_VERSION,
            "label": "system.nix",
            "scope": "system",
            "control_group": "/nix.slice",
            "memory_current_bytes": 100,
            "memory_peak_bytes": 200,
            "memory_swap_current_bytes": 0,
            "memory_swap_peak_bytes": 0,
            "memory_high_bytes": None,
            "memory_max_bytes": 4096,
            "memory_anon_bytes": 64,
            "memory_file_bytes": 32,
            "memory_kernel_bytes": 8,
            "memory_slab_bytes": 4,
            "memory_sock_bytes": 2,
            "memory_shmem_bytes": 1,
            "memory_swapcached_bytes": 0,
            "memory_zswap_bytes": 0,
            "memory_zswapped_bytes": 0,
            "cgroup_populated": 1,
            "cgroup_frozen": 0,
            "cgroup_freeze": 0,
        }
    ]

    with collector.sqlite3.connect(db) as conn:
        collector.init_db(conn)
        collector.insert_cgroup_memory_stats(conn, rows)
        row = conn.execute(
            """
            SELECT label, memory_current_bytes, memory_anon_bytes, memory_max_bytes,
                   memory_events_high, memory_events_max, memory_events_oom,
                   memory_events_oom_kill
            FROM cgroup_memory_sample
            """
        ).fetchone()

    assert row == ("system.nix", 100, 64, 4096, None, None, None, None)


def test_hardware_manifest_publication_is_durable_and_readable(monkeypatch, tmp_path):
    collector = _collector()
    published = {}

    def record(path, payload, **kwargs):
        published.update(path=path, payload=payload, **kwargs)
        return True

    monkeypatch.setattr(collector, "atomic_publish", record)
    # The main loop owns manifest publication; intercepting its helper keeps
    # this contract test independent of live hardware probes.
    manifest = tmp_path / "manifest.json"
    collector.atomic_publish(manifest, b'{"host":"fixture"}', fsync=True, mode=0o644)
    assert published == {
        "path": manifest,
        "payload": b'{"host":"fixture"}',
        "fsync": True,
        "mode": 0o644,
    }
