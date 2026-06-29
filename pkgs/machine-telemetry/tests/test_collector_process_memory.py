from __future__ import annotations

import importlib.util
from pathlib import Path


def _collector():
    path = Path(__file__).resolve().parents[1] / "collector.py"
    spec = importlib.util.spec_from_file_location("machine_telemetry_collector", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_systemd_unescape_fragment_decodes_hex_escapes() -> None:
    collector = _collector()

    assert (
        collector.systemd_unescape_fragment("wayland-wm@hyprland\\x2duwsm.desktop.service")
        == "wayland-wm@hyprland-uwsm.desktop.service"
    )


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
