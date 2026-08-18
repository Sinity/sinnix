"""`sinnix-ops-reducer orient`: composition, degrade paths, and the folded
acknowledged-outages hook contract."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from sinnix_ops_reducer import orient

SNAPSHOT_HEALTHY: dict[str, Any] = {
    "schema": "sinnix-ops-v1",
    "sequence": 42,
    "observed_at": "2026-08-18T00:00:00Z",
    "sources": {
        "sinnix-observe": {"status": "healthy"},
        "ambient-intelligence": {"status": "unavailable"},
    },
    "state": {
        "systemd_units": [
            {
                "unit": "sinnix-capture-kitty-scrollback.service",
                "manager": "user",
                "active_state": "failed",
                "sub_state": "failed",
            },
            {
                "unit": "sinnix-stt.service",
                "manager": "system",
                "active_state": "active",
                "sub_state": "running",
            },
            {
                "unit": "sinnix-midflight.service",
                "manager": "system",
                "active_state": "activating",
                "sub_state": "start",
            },
        ],
        "runtime_inventory": {
            "schema": "sinnix-runtime-inventory-v1",
            "surfaces": {
                "sinex": {
                    "unit": "sinex.service",
                    "acknowledged": {
                        "down": True,
                        "reason": "repair in progress",
                        "since": "2026-07-10",
                        "ref": "sinnix-abcd",
                    },
                },
                "stt": {
                    "unit": "sinnix-stt.service",
                    "acknowledged": {
                        "down": False,
                        "reason": "",
                        "since": "",
                        "ref": "",
                    },
                },
            },
        },
    },
}

LANES_MIXED: dict[str, Any] = {
    "schema": "sinnix-health-transition-v1",
    "ledger": "/run/user/1000/sinnix/health-transitions.jsonl",
    "keys": {
        "capture:video-resolve": {"status": "stale"},
        "capture:webhistory": {"status": "healthy"},
        "service:user:sinnix-capture-kitty-scrollback.service": {"status": "failed"},
    },
}


def make_runner(stdout: str, returncode: int = 0):
    def runner(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=["bd"], returncode=returncode, stdout=stdout, stderr=""
        )

    return runner


def failing_runner(*_args: Any, **_kwargs: Any):
    raise FileNotFoundError("bd not found")


# --------------------------------------------------------------------------
# pure composition helpers
# --------------------------------------------------------------------------


def test_failed_and_attention_units_filters_active_states() -> None:
    units = orient.failed_and_attention_units(SNAPSHOT_HEALTHY["state"])
    states = {u["unit"]: u["active_state"] for u in units}
    assert states == {
        "sinnix-capture-kitty-scrollback.service": "failed",
        "sinnix-midflight.service": "activating",
    }


def test_system_verdict_reports_attention_when_units_or_sources_are_bad() -> None:
    units = orient.failed_and_attention_units(SNAPSHOT_HEALTHY["state"])
    degraded = orient.degraded_sources(SNAPSHOT_HEALTHY["sources"])
    status, summary = orient.system_verdict(units, degraded)
    assert status == "attention"
    assert "1 unit failed" in summary
    assert "ambient-intelligence" in summary


def test_system_verdict_healthy_when_nothing_is_wrong() -> None:
    status, summary = orient.system_verdict([], [])
    assert (status, summary) == ("healthy", "The system is healthy.")


def test_acknowledged_outages_extracts_only_down_true() -> None:
    inventory = SNAPSHOT_HEALTHY["state"]["runtime_inventory"]
    rows = orient.acknowledged_outages(inventory)
    assert rows == [
        {
            "surface": "sinex",
            "unit": "sinex.service",
            "reason": "repair in progress",
            "since": "2026-07-10",
            "ref": "sinnix-abcd",
        }
    ]


def test_acknowledged_outages_absent_inventory_is_empty() -> None:
    assert orient.acknowledged_outages(None) == []
    assert orient.acknowledged_outages({"surfaces": "not-a-dict"}) == []


def test_capture_freshness_counts_and_lists_non_healthy() -> None:
    freshness = orient.capture_freshness(LANES_MIXED)
    assert freshness["available"] is True
    assert freshness["total"] == 3
    assert freshness["healthy"] == 1
    assert freshness["non_healthy"] == [
        {"key": "capture:video-resolve", "status": "stale"},
        {
            "key": "service:user:sinnix-capture-kitty-scrollback.service",
            "status": "failed",
        },
    ]


def test_capture_freshness_unavailable_when_lanes_missing() -> None:
    assert orient.capture_freshness(None) == {"available": False}
    assert orient.capture_freshness({"keys": "not-a-dict"}) == {"available": False}


# --------------------------------------------------------------------------
# bd/steering subprocess composition
# --------------------------------------------------------------------------


def test_bd_ready_head_parses_and_truncates() -> None:
    items = [
        {"id": f"sinnix-{i}", "title": f"item {i}", "priority": 3} for i in range(8)
    ]
    result = orient.bd_ready_head(runner=make_runner(json.dumps(items)))
    assert result["available"] is True
    assert result["total"] == 8
    assert len(result["ready"]) == 5
    assert result["ready"][0] == {"id": "sinnix-0", "title": "item 0", "priority": 3}


def test_bd_ready_head_absent_on_nonzero_exit() -> None:
    result = orient.bd_ready_head(
        runner=make_runner("Error: no beads database found", 1)
    )
    assert result == {"available": False}


def test_bd_ready_head_absent_on_missing_binary() -> None:
    assert orient.bd_ready_head(runner=failing_runner) == {"available": False}


def test_bd_ready_head_absent_on_malformed_json() -> None:
    assert orient.bd_ready_head(runner=make_runner("not json")) == {"available": False}


def test_steering_ready_head_absent_when_workspace_missing(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-beads"
    result = orient.steering_ready_head(beads_dir=missing, runner=make_runner("[]"))
    assert result == {"available": False}


def test_steering_ready_head_present_when_workspace_exists(tmp_path: Path) -> None:
    beads_dir = tmp_path / ".beads"
    beads_dir.mkdir()
    items = [{"id": "steer-1", "title": "morning check-in", "priority": 2}]
    result = orient.steering_ready_head(
        beads_dir=beads_dir, runner=make_runner(json.dumps(items))
    )
    assert result == {"available": True, "total": 1, "ready": items}


# --------------------------------------------------------------------------
# compose(): the three cases the team asked for
# --------------------------------------------------------------------------


def test_compose_healthy_reducer_and_beads() -> None:
    def fetch(_socket: Path, route: str) -> dict[str, Any] | None:
        return {"/v1/snapshot": SNAPSHOT_HEALTHY, "/v1/health/lanes": LANES_MIXED}[
            route
        ]

    data = orient.compose(
        socket_path=Path("/nonexistent/ops.sock"),
        fetch=fetch,
        bd_head=lambda: {
            "available": True,
            "total": 1,
            "ready": [{"id": "x", "title": "y", "priority": 1}],
        },
        steering_head=lambda: {"available": False},
    )
    assert data["schema"] == orient.SCHEMA
    assert data["system"]["status"] == "attention"
    assert data["acknowledged_outages"][0]["surface"] == "sinex"
    assert data["capture_freshness"]["healthy"] == 1
    assert data["beads"]["available"] is True
    assert data["steering"] == {"available": False}


def test_compose_degraded_reducer_falls_back_to_static_inventory(
    tmp_path: Path,
) -> None:
    static_inventory = tmp_path / "runtime-inventory.json"
    static_inventory.write_text(
        json.dumps(SNAPSHOT_HEALTHY["state"]["runtime_inventory"]), encoding="utf-8"
    )

    def fetch(_socket: Path, _route: str) -> dict[str, Any] | None:
        return None  # the reducer is unreachable

    data = orient.compose(
        socket_path=Path("/nonexistent/ops.sock"),
        static_inventory_path=static_inventory,
        fetch=fetch,
        bd_head=lambda: {"available": False},
        steering_head=lambda: {"available": False},
    )
    assert data["system"]["status"] == "unavailable"
    # Acknowledged outages still resolve from the static inventory even
    # though the reducer itself could not be reached.
    assert data["acknowledged_outages"][0]["surface"] == "sinex"
    assert data["capture_freshness"] == {"available": False}


def test_compose_no_beads_workspace() -> None:
    def fetch(_socket: Path, route: str) -> dict[str, Any] | None:
        return {"/v1/snapshot": SNAPSHOT_HEALTHY, "/v1/health/lanes": LANES_MIXED}[
            route
        ]

    data = orient.compose(
        socket_path=Path("/nonexistent/ops.sock"),
        fetch=fetch,
        bd_head=lambda: {"available": False},
        steering_head=lambda: {"available": False},
    )
    assert data["beads"] == {"available": False}
    assert data["steering"] == {"available": False}
    # Human rendering must not mention beads/steering sections at all.
    text = orient.render_human(data)
    assert "Beads ready" not in text
    assert "Steering ready" not in text


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def test_render_human_healthy_system_has_no_attention_rows() -> None:
    data = {
        "generated_at": "2026-08-18T00:00:00Z",
        "system": {"status": "healthy", "summary": "The system is healthy."},
        "acknowledged_outages": [],
        "capture_freshness": {
            "available": True,
            "total": 5,
            "healthy": 5,
            "non_healthy": [],
        },
        "beads": {"available": False},
        "steering": {"available": False},
    }
    text = orient.render_human(data)
    assert "The system is healthy." in text
    assert "FAILED" not in text
    assert "Acknowledged outages" not in text
    assert "5/5 healthy" in text


def test_render_human_includes_every_populated_section() -> None:
    data = orient.compose(
        socket_path=Path("/nonexistent/ops.sock"),
        fetch=lambda _s, route: {
            "/v1/snapshot": SNAPSHOT_HEALTHY,
            "/v1/health/lanes": LANES_MIXED,
        }[route],
        bd_head=lambda: {
            "available": True,
            "total": 2,
            "ready": [{"id": "a", "title": "t", "priority": 1}],
        },
        steering_head=lambda: {
            "available": True,
            "total": 1,
            "ready": [{"id": "s", "title": "u", "priority": 1}],
        },
    )
    text = orient.render_human(data)
    assert "FAILED      sinnix-capture-kitty-scrollback.service (user)" in text
    assert "ACTIVATING  sinnix-midflight.service (system)" in text
    assert "SOURCE DOWN ambient-intelligence" in text
    assert "Acknowledged outages (1" in text
    assert "sinex (sinex.service)" in text
    assert "Capture/health lanes: 1/3 healthy" in text
    assert "Beads ready (1 of 2):" in text
    assert "Steering ready (1 of 1):" in text


def test_render_acknowledged_only_matches_hook_contract() -> None:
    acked = [
        {
            "surface": "sinex",
            "unit": "sinex.service",
            "reason": "repair in progress",
            "since": "2026-07-10",
            "ref": "sinnix-abcd",
        }
    ]
    text = orient.render_acknowledged_only(acked)
    assert text.startswith(
        "## Acknowledged outages (known-down, do not re-report as incidents)\n\n"
    )
    assert (
        "- sinex (sinex.service) — repair in progress [since 2026-07-10, ref sinnix-abcd]"
        in text
    )
    assert text.endswith("rather than raising it as new.\n")


def test_render_acknowledged_only_empty_when_nothing_acknowledged() -> None:
    assert orient.render_acknowledged_only([]) == ""


def test_acknowledged_only_report_prefers_static_file(tmp_path: Path) -> None:
    static_inventory = tmp_path / "runtime-inventory.json"
    static_inventory.write_text(
        json.dumps(SNAPSHOT_HEALTHY["state"]["runtime_inventory"]), encoding="utf-8"
    )
    calls: list[str] = []

    def fetch(_socket: Path, route: str) -> dict[str, Any] | None:
        calls.append(route)
        return None

    text = orient.acknowledged_only_report(
        socket_path=Path("/nonexistent/ops.sock"),
        static_inventory_path=static_inventory,
        fetch=fetch,
    )
    assert "sinex" in text
    assert calls == []  # the socket was never touched


def test_acknowledged_only_report_falls_back_to_socket(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.json"

    def fetch(_socket: Path, route: str) -> dict[str, Any] | None:
        assert route == "/v1/snapshot"
        return SNAPSHOT_HEALTHY

    text = orient.acknowledged_only_report(
        socket_path=Path("/nonexistent/ops.sock"),
        static_inventory_path=missing,
        fetch=fetch,
    )
    assert "sinex" in text


def test_default_static_inventory_path_honors_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SINNIX_RUNTIME_INVENTORY_FILE", "/tmp/fixture-inventory.json")
    assert orient.default_static_inventory_path() == Path("/tmp/fixture-inventory.json")


def test_default_static_inventory_path_falls_back_to_etc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SINNIX_RUNTIME_INVENTORY_FILE", raising=False)
    assert orient.default_static_inventory_path() == Path(
        "/etc/sinnix/runtime-inventory.json"
    )
