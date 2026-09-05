"""Calendar timers reconcile from the descriptors alone."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from agentctl import schedule
from agentctl.config import Config


@pytest.fixture
def fake_systemd(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"units": set(), "calls": []}

    def run(argv: Any, *, check: bool = True) -> str:
        argv = list(argv)
        state["calls"].append(argv)
        if argv[:3] == ["systemctl", "--user", "list-units"]:
            return "".join(
                f"{unit}.timer loaded active waiting x\n"
                for unit in sorted(state["units"])
            )
        if argv[:3] == ["systemctl", "--user", "stop"]:
            for item in argv[3:]:
                if item.endswith(".timer"):
                    state["units"].discard(item[: -len(".timer")])
                elif item.endswith(".service"):
                    # A transient timer's service is not loaded while idle;
                    # systemctl exits non-zero and apply must not fail on it.
                    assert not check, "stopping the service must tolerate 'not loaded'"
            return ""
        if argv[0] == "systemd-run":
            unit = next(item for item in argv if item.startswith("--unit=")).split(
                "=", 1
            )[1]
            state["units"].add(unit)
            return ""
        raise AssertionError(argv)

    monkeypatch.setattr(schedule, "_run", run)
    return state


def test_apply_starts_declared_timers_that_fire_agentctl_and_stops_retired_ones(
    fake_systemd: dict[str, Any], config: Config, project_root: Path
) -> None:
    """Breaks if a timer stops running `job fire`, or a retired one survives."""
    fake_systemd["units"].add("agentctl-schedule-000000000000000000000000")

    applied = schedule.apply(config)

    expected = schedule.unit_for("fixture", "nightly", "*-*-* 03:17:00")
    assert applied["started"] == [expected]
    assert applied["stopped"] == ["agentctl-schedule-000000000000000000000000"]
    start = next(call for call in fake_systemd["calls"] if call[0] == "systemd-run")
    assert "--on-calendar=*-*-* 03:17:00" in start
    assert "--timer-property=Persistent=true" in start
    assert start[start.index("--") + 1 :] == [
        "/fixture/agentctl",
        "job",
        "fire",
        "fixture",
        "nightly",
    ]


def test_apply_is_idempotent(fake_systemd: dict[str, Any], config: Config) -> None:
    schedule.apply(config)
    again = schedule.apply(config)
    assert again["started"] == [] and again["stopped"] == []


def test_a_changed_expression_is_a_new_unit() -> None:
    assert schedule.unit_for("p", "op", "hourly") != schedule.unit_for(
        "p", "op", "daily"
    )


def test_sub_hourly_timers_do_not_catch_up() -> None:
    assert schedule.timer_persistent("*-*-* 03:17:00")
    assert schedule.timer_persistent("hourly")
    assert not schedule.timer_persistent("*:0/5")
