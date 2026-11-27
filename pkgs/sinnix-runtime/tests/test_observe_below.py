"""The recorded-history CLI contract and failure evidence stay visible."""

from __future__ import annotations

import pytest

from sinnix_lib.process import Result
from sinnix_runtime.observe import cli, render
from sinnix_runtime.observe.sources import below


@pytest.fixture(autouse=True)
def live_sources(monkeypatch):
    monkeypatch.delenv("SINNIX_OBSERVE_BELOW_CGROUP_TSV", raising=False)
    monkeypatch.delenv("SINNIX_OBSERVE_BELOW_PROCESS_TSV", raising=False)


def test_dump_fields_are_individual_arguments_and_preserve_measurements(monkeypatch):
    # Model below's documented variadic --fields contract: each token names
    # one field, and the selected order determines the emitted TSV columns.
    values = {
        "datetime": "2026-01-01 12:00:00",
        "name": "worker.service",
        "full_path": "/system.slice/worker.service",
        "cpu.usage_pct": "2",
        "mem.total": "4096",
        "io.rwbytes_per_sec": "1024",
        "pressure.io_full_pct": "3",
        "pressure.memory_full_pct": "4",
        "pid": "42",
        "comm": "worker",
        "state": "SLEEPING",
        "cgroup": "/system.slice/worker.service",
        "mem.rss_bytes": "2048",
        "cmdline": "worker --fixture",
    }
    calls = []

    def dump(argv, *, timeout):
        calls.append(argv[2])
        fields = argv[argv.index("-f") + 1 : argv.index("-O")]
        if not fields or any(field not in values for field in fields):
            return Result(tuple(argv), 2, "", "invalid field")
        return Result(tuple(argv), 0, "\t".join(values[f] for f in fields) + "\n", "")

    monkeypatch.setattr(below, "run", dump)
    result = below.collect_below("1 min ago", "1 min", 5, offline=False)

    assert calls == ["cgroup", "process"]
    assert result["available"] is True
    assert result.get("errors", {}) == {}
    assert result["cgroup_peaks"][0] == {
        "cgroup": "/system.slice/worker.service",
        "max_cpu_pct": 2,
        "max_rss_bytes": 4096,
        "max_rw_bps": 1024,
        "max_io_full_pct": 3,
        "max_memory_full_pct": 4,
        "samples": 1,
    }
    process = result["process_peaks"][0]
    assert (process["pid"], process["max_rw_bps"], process["max_rss_bytes"]) == (
        42, 1024, 2048
    )
    assert process["cmdline"] == "worker --fixture"


@pytest.mark.parametrize(
    ("returncode", "stderr", "error", "reason"),
    [
        (2, "invalid field\n", None, "invalid field"),
        (-1, "", "timed out after 10s", "timed out after 10s"),
    ],
)
def test_failed_dump_retains_partial_history_and_reaches_reports(
    monkeypatch, returncode, stderr, error, reason
):
    def dump(argv, **kwargs):
        if argv[2] == "cgroup":
            return Result(tuple(argv), returncode, "", stderr, error=error)
        return Result(
            tuple(argv), 0,
            "2026-01-01 12:00:00\t42\tworker\tSLEEPING\t/worker\t8\t16\t1\tworker\n",
            "",
        )

    monkeypatch.setattr(below, "run", dump)
    result = below.collect_below("1 min ago", "1 min", 5, offline=False)
    assert result["available"] is True
    assert result["process_peaks"][0]["pid"] == 42
    assert result["gaps"] == ["below.history.cgroup.failed"]
    assert result["errors"] == {
        "cgroup": {"returncode": returncode, "reason": reason}
    }
    assert cli._sources({}, {}, below=result)["below"]["errors"] == result["errors"]
    report = {"generated_at": "fixture", "window": {"since": "fixture"}, "below": result}
    assert f"cgroup dump failed: exit={returncode} {reason}" in render.render_human(report)


def test_successful_empty_history_is_distinct_from_command_failure(monkeypatch):
    monkeypatch.setattr(
        below, "run", lambda argv, **kwargs: Result(tuple(argv), 0, "", "")
    )
    result = below.collect_below("1 min ago", "1 min", 5, offline=False)
    assert result["available"] is False
    assert result["gaps"] == ["below.history.no_samples"]
    assert result.get("errors", {}) == {}
