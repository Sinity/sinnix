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

    expected = schedule.unit_for(
        "fixture", "nightly", "*-*-* 03:17:00", "/fixture/agentctl"
    )
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


def test_incomplete_catalog_defers_retirement_until_recovery(
    fake_systemd: dict[str, Any], config: Config, project_root: Path, tmp_path: Path
) -> None:
    """A malformed descriptor must not erase timers while discovery is partial."""
    from dataclasses import replace

    unavailable_root = tmp_path / "temporarily-unavailable"
    descriptor = unavailable_root / ".agentctl" / "project.toml"
    descriptor.parent.mkdir(parents=True)
    descriptor.write_text("not valid TOML = [")
    previous = "agentctl-schedule-111111111111111111111111"
    fake_systemd["units"].add(previous)
    partial_config = replace(config, project_roots=(project_root, unavailable_root))

    partial = schedule.apply(partial_config)

    assert partial["status"] == "incomplete"
    assert partial["unavailable"]
    assert partial["stopped"] == []
    assert previous in fake_systemd["units"]
    assert partial["started"] == [
        schedule.unit_for(
            "fixture",
            "nightly",
            "*-*-* 03:17:00",
            config.agentctl_executable,
        )
    ]

    (unavailable_root / "marker").write_text("")
    (unavailable_root / "contract.md").write_text("# Recovered\n")
    (unavailable_root / "atlas").mkdir()
    (unavailable_root / "atlas" / "core.md").write_text("# Recovered\n")
    recovered = project_root.joinpath(".agentctl", "project.toml").read_text()
    recovered = recovered.replace('id = "fixture"', 'id = "recovered"').replace(
        'display_name = "Fixture"', 'display_name = "Recovered"'
    )
    recovered = "\n".join(
        line for line in recovered.splitlines() if line != 'schedule = "*-*-* 03:17:00"'
    )
    descriptor.write_text(recovered)

    reconciled = schedule.apply(partial_config)

    assert reconciled["status"] == "complete"
    assert reconciled["unavailable"] == []
    assert reconciled["stopped"] == [previous]
    assert previous not in fake_systemd["units"]


def test_custom_config_is_forwarded_and_a_path_change_replaces_the_timer(
    fake_systemd: dict[str, Any], config: Config
) -> None:
    from dataclasses import replace

    first_config = replace(config, config_path=Path("/realm/state/agentctl/first.json"))
    first = schedule.apply(first_config)
    start = next(call for call in fake_systemd["calls"] if call[0] == "systemd-run")
    assert start[start.index("--") + 1 :] == [
        "/fixture/agentctl",
        "--config",
        "/realm/state/agentctl/first.json",
        "job",
        "fire",
        "fixture",
        "nightly",
    ]
    assert schedule.apply(first_config)["started"] == []

    second_config = replace(
        config, config_path=Path("/realm/state/agentctl/second.json")
    )
    second = schedule.apply(second_config)
    assert second["stopped"] == first["started"]
    assert second["started"] == [
        schedule.unit_for(
            "fixture",
            "nightly",
            "*-*-* 03:17:00",
            "/fixture/agentctl",
            "/realm/state/agentctl/second.json",
        )
    ]


def test_a_changed_expression_or_executable_is_a_new_unit() -> None:
    assert schedule.unit_for("p", "op", "hourly", "/a") != schedule.unit_for(
        "p", "op", "daily", "/a"
    )
    assert schedule.unit_for("p", "op", "hourly", "/a") != schedule.unit_for(
        "p", "op", "hourly", "/b"
    )


def test_a_rebuilt_agentctl_replaces_the_timer_that_execs_the_old_path(
    fake_systemd: dict[str, Any], config: Config
) -> None:
    """A timer keeps exec'ing the store path it was started with; after a
    rebuild that path is garbage, so the timer is a new unit."""
    from dataclasses import replace

    first = schedule.apply(config)
    rebuilt = replace(
        config, agentctl_executable="/nix/store/new-agentctl/bin/agentctl"
    )

    second = schedule.apply(rebuilt)

    assert second["stopped"] == first["started"]
    assert second["started"] == [
        schedule.unit_for(
            "fixture", "nightly", "*-*-* 03:17:00", rebuilt.agentctl_executable
        )
    ]
    start = [call for call in fake_systemd["calls"] if call[0] == "systemd-run"][-1]
    assert start[start.index("--") + 1] == rebuilt.agentctl_executable


def test_sub_hourly_timers_do_not_catch_up() -> None:
    assert schedule.timer_persistent("*-*-* 03:17:00")
    assert schedule.timer_persistent("hourly")
    assert not schedule.timer_persistent("*:0/5")
