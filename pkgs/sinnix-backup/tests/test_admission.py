"""Resource admission and requeue use the live owner's typed status."""
import json
import subprocess
from types import SimpleNamespace

import pytest

from sinnix_backup import admission as a


@pytest.mark.parametrize("index,available,ready", [
    ("idle", 8192, True),
    ("inactive", 8192, True),
    ("idle", 8191, False),
    ("rebuilding", 32000, False),
    ("unknown", 32000, False),
])
def test_admission(index, available, ready):
    assert (a.admission_reason(index, available, 8192) is None) == ready


def test_start_and_yield_thresholds():
    assert a.yield_reason("idle", 4096, 0) is None
    assert a.yield_reason("unknown", 4096, 0) is None
    assert a.yield_reason("rebuilding", 32000, 16000)
    assert a.yield_reason("idle", 1500, 500)
    assert a.yield_reason("idle", 800, 16000)
    assert a.yield_reason("idle", 3000, 100) is None


@pytest.mark.parametrize("rebuilding,installed,exit_code,expected", [
    ("writing", "unusable", 5, "rebuilding"),
    ("no", "current", 0, "idle"),
    ("no", "current", 5, "idle"),
    ("no", "unusable", 5, "unknown"),
])
def test_live_index_probe(monkeypatch, rebuilding, installed, exit_code, expected):
    monkeypatch.setattr(a, "properties", lambda *_: {"ActiveState": "active"})

    def command(argv):
        if "systemctl" in argv:
            return subprocess.CompletedProcess(argv, 0, "active\n", "")
        assert argv[:4] == ["runuser", "-u", "operator", "--"]
        assert "--deadline" in argv
        return subprocess.CompletedProcess(argv, exit_code, json.dumps({
            "value": {"index": {
                "rebuilding": {"state": rebuilding},
                "installed": {"state": installed},
            }}
        }), "")
    monkeypatch.setattr(a, "command", command)
    assert a.IndexProbe("operator", 1000, "/polylogue").state() == expected


def test_invalid_status_fails_closed(monkeypatch):
    monkeypatch.setattr(a, "properties", lambda *_: {"ActiveState": "active"})
    monkeypatch.setattr(a, "command", lambda argv: subprocess.CompletedProcess(
        argv, 0, "active\n" if "systemctl" in argv else "{}", ""))
    assert a.IndexProbe("operator", 1000, "/polylogue").state() == "unknown"


def test_absent_user_manager(monkeypatch):
    monkeypatch.setattr(a, "properties", lambda *_: {"ActiveState": "inactive"})
    assert a.IndexProbe("operator", 1000, "/polylogue").state() == "inactive"


def test_wait_until_eligible(monkeypatch):
    states = iter(["rebuilding", "idle", "idle"])
    available = iter([12000, 4000, 9000])
    monkeypatch.setattr(a, "memory_mib", lambda: (next(available), 100))
    monkeypatch.setattr(a.time, "sleep", lambda _: None)
    assert a.wait_for_admission(SimpleNamespace(state=lambda: next(states)), 8192, once=False) == 0


def test_only_running_drains_are_requeued(monkeypatch):
    states = {"realm": {"SubState": "start", "MainPID": "42"},
              "genome": {"SubState": "start-pre", "MainPID": "0"},
              "persist": {"SubState": "dead", "MainPID": "0"}}
    monkeypatch.setattr(a, "properties", lambda unit, *_: states[unit])
    monkeypatch.setattr(a, "memory_mib", lambda: (12000, 100))
    calls = []
    def command(argv):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")
    monkeypatch.setattr(a, "command", command)
    assert a.yield_drains(SimpleNamespace(state=lambda: "rebuilding"), list(states)) == 0
    assert calls == [["systemctl", "--no-block", "restart", "realm"]]
    calls.clear()
    assert a.yield_drains(SimpleNamespace(state=lambda: "idle"), list(states)) == 0
    assert calls == []


def test_memory_probe(tmp_path):
    path = tmp_path / "meminfo"
    path.write_text("MemTotal: 32768000 kB\nMemAvailable: 8388608 kB\nSwapFree: 524288 kB\n")
    assert a.memory_mib(path) == (8192, 512)
