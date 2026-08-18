"""The inventory health sweep: transitions, debounce, and the notify rules.

Ported from flake/tests/health-sentinel.nix, which drove the retired bash
sentinel through a fixture inventory with stub `df`/`systemctl`/`sudo` binaries
on PATH. The fixtures here are function-level instead (the unit prober and the
mount reader are injected), so every behavioural assertion the nix check made
survives, plus the ones its shape could not reach: acknowledged outages, the
notification rules, and the shared state between the OnFailure fast path and
the sweep.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sinnix_ops_reducer import health

# The resting-state shapes, one fixture unit each -- the sweep derives its
# verdict from ActiveState/Type/Result/WantedBy and never from a unit list.
UNIT_FIXTURES: dict[str, dict[str, str]] = {
    # WantedBy set, down: a daemon that should be running, isn't.
    "fixture.service": {"ActiveState": "inactive", "Type": "simple", "Result": "success", "WantedBy": "multi-user.target"},
    # ran and exited cleanly
    "oneshot-done.service": {"ActiveState": "inactive", "Type": "oneshot", "Result": "success", "WantedBy": ""},
    # ran and failed
    "oneshot-failed.service": {"ActiveState": "inactive", "Type": "oneshot", "Result": "exit-code", "WantedBy": ""},
    # WantedBy empty: an on-demand backend idled out cleanly
    "backend-idle.service": {"ActiveState": "inactive", "Type": "exec", "Result": "success", "WantedBy": ""},
    # "on-demand" excuses being inactive, not crashing
    "backend-crashed.service": {"ActiveState": "inactive", "Type": "exec", "Result": "exit-code", "WantedBy": ""},
    # WantedBy still set, but declared socket-proxy: that declaration suffices
    "socket-proxy-declared.service": {"ActiveState": "inactive", "Type": "exec", "Result": "success", "WantedBy": "multi-user.target"},
    "acknowledged.service": {"ActiveState": "failed", "Type": "simple", "Result": "exit-code", "WantedBy": "multi-user.target"},
    "midflight.service": {"ActiveState": "activating", "Type": "oneshot", "Result": "success", "WantedBy": ""},
    "proxy-listening.socket": {"ActiveState": "active", "Type": "simple", "Result": "success", "WantedBy": "sockets.target"},
    "proxy-latched.socket": {"ActiveState": "failed", "Type": "simple", "Result": "trigger-limit-hit", "WantedBy": "sockets.target"},
}


def prober(units, user: bool) -> dict[str, dict[str, str]]:
    # A user manager with no live session answers nothing at all, which must
    # read as "unknown" rather than as a silent pass or failure.
    if user:
        return {}
    return {unit: dict(UNIT_FIXTURES[unit]) for unit in units if unit in UNIT_FIXTURES}


class Recorder:
    def __init__(self) -> None:
        self.notifications: list[tuple[str, str, str]] = []

    def __call__(self, urgency: str, title: str, body: str) -> None:
        self.notifications.append((urgency, title, body))


@pytest.fixture
def world(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(health, "mount_usage_percent", lambda path: 96)
    monkeypatch.setattr(health, "reset_and_start", lambda manager, unit: True)
    recorder = Recorder()

    lanes = tmp_path / "lanes"
    (lanes / "fresh").mkdir(parents=True)
    (lanes / "fresh" / "current").write_text("x")
    (lanes / "stale").mkdir(parents=True)
    old = lanes / "stale" / "old"
    old.write_text("x")
    import os

    os.utime(old, (0, 0))
    # Exists, declared, holds nothing: "never produced" is a property of the
    # contents, not of whether the directory was created.
    (lanes / "declared-empty").mkdir(parents=True)
    (lanes / "payload-dead").mkdir(parents=True)
    (lanes / "payload-live").mkdir(parents=True)
    dead = lanes / "payload-dead" / "dead-20260813.jsonl"
    live = lanes / "payload-live" / "live-20260813.jsonl"
    for seq in range(1, 7):
        dead.open("a").write(
            json.dumps(
                {
                    "schema": "sinnix-capture-v1",
                    "seq": seq,
                    "payload": {"window_class": None, "geometry": {}, "monitor": "DP-3", "note": "x"},
                }
            )
            + "\n"
        )
        live.open("a").write(
            json.dumps(
                {
                    "schema": "sinnix-capture-v1",
                    "seq": seq,
                    "payload": {"window_class": "kitty", "geometry": {"width": 1920}, "monitor": "DP-3", "note": None},
                }
            )
            + "\n"
        )
    # `note` is populated in exactly one record: a sometimes-null field must
    # never raise an alarm.
    live.open("a").write(
        json.dumps(
            {
                "schema": "sinnix-capture-v1",
                "seq": 7,
                "payload": {"window_class": "kitty", "geometry": {"width": 1920}, "monitor": "DP-3", "note": "present"},
            }
        )
        + "\n"
    )
    # The sidecar index carries no payload; it must be skipped, not read as a
    # lane full of degenerate records.
    (lanes / "payload-live" / "live-index.jsonl").write_text(
        json.dumps({"ts": 1, "seq": 1, "file": "live-20260813.jsonl"}) + "\n"
    )

    marker = tmp_path / "probe-marker"
    fields = ["window_class", "geometry.width", "monitor", "note"]
    inventory: dict[str, Any] = {
        "captures": [
            {"name": "fixture", "path": str(lanes / "stale"), "expectedCadenceSeconds": 60},
            {"name": "ed-stale", "path": str(lanes / "stale"), "expectedStaleAfterSeconds": 60},
            {"name": "ed-fresh", "path": str(lanes / "fresh"), "expectedStaleAfterSeconds": 600},
            {"name": "payload-dead", "path": str(lanes / "payload-dead"), "requiredPayloadFields": fields},
            {"name": "payload-live", "path": str(lanes / "payload-live"), "requiredPayloadFields": fields},
            {
                "name": "probe-absent",
                "path": str(lanes / "fresh"),
                "livenessProbe": {"command": f'[ -e "{marker}" ] && exit 0 || exit 1', "timeoutSeconds": 5},
            },
            {"name": "probe-unknown", "path": str(lanes / "fresh"), "livenessProbe": {"command": "exit 9", "timeoutSeconds": 5}},
            {"name": "probe-timeout", "path": str(lanes / "fresh"), "livenessProbe": {"command": "sleep 5", "timeoutSeconds": 1}},
            # Neither cadence nor budget, and nothing ever written: the most
            # broken a lane can be, and the state that used to raise nothing.
            {"name": "unbudgeted-never-wrote", "path": str(tmp_path / "does-not-exist")},
            # A budget cannot fire on a lane with no file to age: an empty
            # declared directory is unproduced, not stale.
            {
                "name": "empty-but-declared",
                "path": str(lanes / "declared-empty"),
                "expectedStaleAfterSeconds": 60,
            },
        ],
        "mounts": [{"path": "/fixture", "warnPct": 80, "failPct": 95}],
        "observedServices": [
            {"kind": "service", "manager": "system", "unit": "fixture.service"},
            {"kind": "service", "manager": "system", "unit": "oneshot-done.service"},
            {"kind": "service", "manager": "system", "unit": "oneshot-failed.service"},
            {"kind": "service", "manager": "system", "unit": "backend-idle.service"},
            {"kind": "service", "manager": "system", "unit": "backend-crashed.service"},
            {"kind": "service", "manager": "system", "unit": "socket-proxy-declared.service", "activationMode": "socket-proxy"},
            {
                "kind": "service",
                "manager": "system",
                "unit": "acknowledged.service",
                "acknowledged": {"down": True, "ref": "sinnix-abc1"},
            },
            {"kind": "service", "manager": "system", "unit": "midflight.service"},
            {"kind": "service", "manager": "user", "unit": "usersurf.service"},
            {"kind": "socket", "manager": "system", "unit": "proxy-listening.socket"},
            {"kind": "socket", "manager": "system", "unit": "proxy-latched.socket"},
        ],
    }
    state = tmp_path / "state.json"
    ledger = tmp_path / "events.jsonl"

    def run() -> list[dict[str, Any]]:
        health.sweep(inventory, health.Emitter(state, ledger, recorder), prober=prober)
        return [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []

    return {
        "run": run,
        "inventory": inventory,
        "state": state,
        "ledger": ledger,
        "recorder": recorder,
        "lanes": lanes,
        "marker": marker,
    }


def find(events: list[dict[str, Any]], type_: str, unit: str) -> dict[str, Any] | None:
    matches = [event for event in events if event["type"] == type_ and event["unit"] == unit]
    return matches[-1] if matches else None


def test_every_lane_and_unit_shape_reaches_the_ledger(world) -> None:
    world["run"]()
    events = world["run"]()  # confirm-2: a transition needs two agreeing sweeps

    assert {event["schema"] for event in events} == {"sinnix-health-transition-v1"}
    assert all(event["confirmed_after_samples"] == 2 for event in events)

    assert find(events, "capture_stale", "fixture")["status"] == "stale"
    assert find(events, "capture_stale", "ed-stale")["status"] == "stale"
    assert find(events, "capture_stale", "ed-fresh")["status"] == "healthy"
    never = find(events, "capture_stale", "unbudgeted-never-wrote")
    assert never["status"] == "unproduced" and "reason=no-file" in never["evidence"]

    assert find(events, "mount_capacity", "/fixture")["status"] == "failed"

    assert find(events, "service_failure", "fixture.service")["ok"] is False
    assert find(events, "service_failure", "oneshot-done.service")["ok"] is True
    assert find(events, "service_failure", "oneshot-failed.service")["ok"] is False
    assert find(events, "service_failure", "backend-idle.service")["ok"] is True
    assert find(events, "service_failure", "backend-crashed.service")["ok"] is False
    assert find(events, "service_failure", "socket-proxy-declared.service")["ok"] is True
    usersurf = find(events, "service_failure", "usersurf.service")
    assert usersurf["status"] == "unknown" and usersurf["ok"] is False

    acknowledged = find(events, "service_failure", "acknowledged.service")
    assert acknowledged["status"] == "acknowledged"
    assert "acknowledged_ref=sinnix-abc1" in acknowledged["evidence"]

    # Mid-transition is not a verdict: no event either way.
    assert find(events, "service_failure", "midflight.service") is None

    assert find(events, "socket_failure", "proxy-listening.socket")["ok"] is True
    latched = find(events, "socket_failure", "proxy-latched.socket")
    assert latched["status"] == "healthy"
    assert "result=trigger-limit-hit" in latched["evidence"]
    assert "recovered=reset-failed+start" in latched["evidence"]

    degenerate = find(events, "capture_payload", "payload-dead")
    assert degenerate["status"] == "degenerate"
    # Names the specific dead fields rather than condemning the lane: `monitor`
    # is populated in both lanes and `note` in one record only.
    assert "always_empty=window_class,geometry.width" in degenerate["evidence"]
    assert find(events, "capture_payload", "payload-live")["ok"] is True

    assert find(events, "publisher_liveness", "probe-absent")["status"] == "publisher-absent"
    assert find(events, "publisher_liveness", "probe-unknown")["status"] == "unknown"
    timeout = find(events, "publisher_liveness", "probe-timeout")
    assert timeout["status"] == "unknown" and "probe_exit=124" in timeout["evidence"]


def test_silence_resolves_three_ways_not_two(world) -> None:
    """The distinction sinnix-pev0 exists for. A quiet lane is one of:

      * never produced (no file at all) -> unproduced, whether or not the
        directory itself exists;
      * produced and then stopped past its budget -> stale, the fault case;
      * quiet inside its budget -> healthy.

    Mutation: emitting "stale" from the newest-is-None branch (the pre-split
    behaviour) collapses the first onto the second and fails both unproduced
    assertions.
    """
    world["run"]()
    events = world["run"]()

    absent = find(events, "capture_stale", "unbudgeted-never-wrote")
    assert absent["status"] == "unproduced"
    assert "path_exists=false" in absent["evidence"]

    empty = find(events, "capture_stale", "empty-but-declared")
    assert empty["status"] == "unproduced"
    assert "path_exists=true" in empty["evidence"]
    # It carries a budget, and the budget is irrelevant: there is no age.
    assert "age_seconds" not in empty["evidence"]

    assert find(events, "capture_stale", "ed-stale")["status"] == "stale"
    assert find(events, "capture_stale", "ed-fresh")["status"] == "healthy"


def test_an_unproduced_lane_is_told_once_and_calmly(world) -> None:
    """A lane that never started is not an outage. Mutation: routing every
    non-healthy status to "critical" (the pre-split emit) makes both urgency
    assertions read "critical"."""
    world["run"]()
    world["run"]()

    calm = [
        (urgency, title)
        for urgency, title, _ in world["recorder"].notifications
        if "never produced" in title
    ]
    assert sorted(calm) == [
        ("normal", "empty-but-declared lane has never produced anything"),
        ("normal", "unbudgeted-never-wrote lane has never produced anything"),
    ]
    # A lane that produced and stopped stays critical: that one IS a fault.
    assert ("critical", "ed-stale lane has gone quiet") in [
        (urgency, title) for urgency, title, _ in world["recorder"].notifications
    ]

    # Told once: further sweeps in the same state say nothing more.
    world["recorder"].notifications.clear()
    world["run"]()
    world["run"]()
    assert not [
        title for _, title, _ in world["recorder"].notifications if "never produced" in title
    ]


def test_first_production_clears_unproduced_without_claiming_a_recovery(world) -> None:
    """unproduced -> healthy is a first write, not a comeback, and must not be
    announced as one. Mutation: dropping the `previous` argument from describe()
    restores "is recording again" and fails the phrasing assertion."""
    world["run"]()
    world["run"]()
    world["recorder"].notifications.clear()

    (world["lanes"] / "declared-empty" / "first").write_text("x")
    world["run"]()
    events = world["run"]()

    assert find(events, "capture_stale", "empty-but-declared")["status"] == "healthy"
    announced = [
        (urgency, title)
        for urgency, title, _ in world["recorder"].notifications
        if "empty-but-declared" in title
    ]
    assert announced == [("normal", "empty-but-declared lane has produced for the first time")]


def test_a_settled_status_is_not_re_emitted(world) -> None:
    world["run"]()
    settled = world["run"]()
    assert world["run"]() == settled
    assert world["run"]() == settled


def test_recovery_is_reported_once_the_lane_produces_again(world) -> None:
    world["run"]()
    before = world["run"]()
    (world["lanes"] / "stale" / "current").write_text("x")
    world["marker"].write_text("here")
    world["run"]()
    after = world["run"]()
    assert len(after) > len(before)
    assert find(after, "capture_stale", "fixture")["status"] == "healthy"
    assert find(after, "publisher_liveness", "probe-absent")["status"] == "healthy"


def test_one_disagreeing_sample_never_transitions(world) -> None:
    """A fault must be witnessed on CONSECUTIVE sweeps, not merely twice ever."""
    world["run"]()
    world["run"]()
    (world["lanes"] / "stale" / "current").write_text("x")
    world["run"]()  # one healthy sample, not yet believed
    import os

    os.utime(world["lanes"] / "stale" / "current", (0, 0))
    events = world["run"]()  # back to stale: the candidate is dropped
    assert find(events, "capture_stale", "fixture")["status"] == "stale"
    assert [event for event in events if event["type"] == "capture_stale" and event["unit"] == "fixture"] == [
        find(events, "capture_stale", "fixture")
    ]


def test_notification_rules(world) -> None:
    world["run"]()
    world["run"]()
    notifications = world["recorder"].notifications
    urgencies = {title: urgency for urgency, title, _ in notifications}
    # An acknowledged outage is recorded and never paged.
    assert not any("acknowledged.service" in title for title in urgencies)
    # A first-ever healthy reading is startup, not a recovery.
    assert not any("ed-fresh" in title for title in urgencies)
    assert urgencies["fixture.service stopped working"] == "critical"
    assert "Look: journalctl -u fixture.service -e" in dict(
        (title, body) for _, title, body in notifications
    )["fixture.service stopped working"]

    # A recovery is announced only because the outage was.
    world["recorder"].notifications.clear()
    (world["lanes"] / "stale" / "current").write_text("x")
    world["run"]()
    world["run"]()
    assert any(
        urgency == "normal" and "lane is recording again" in title
        for urgency, title, _ in world["recorder"].notifications
    )


def test_the_failure_fast_path_shares_the_sweeps_key(world) -> None:
    """The 2026-08-14 two-keys bug: an OnFailure event and the sweep must be
    talking about the same key, or the sweep's prune deletes the fast path's
    state and the same unit notifies forever without its recovery ever pairing.
    """
    emitter = health.Emitter(world["state"], world["ledger"], world["recorder"])
    health.emit_failure("fixture", "exit-code", world["inventory"], emitter)
    state = json.loads(world["state"].read_text())
    assert state["service:system:fixture.service"] == {"status": "failed"}
    events = [json.loads(line) for line in world["ledger"].read_text().splitlines()]
    # One event, on the first observation: an OnFailure hook fires exactly once,
    # so it must not wait for a second agreeing sample.
    assert len(events) == 1
    assert events[0]["evidence"] == "manager=system;source=onfailure;result=exit-code"

    # The sweep then agrees with it and says nothing further, and its prune
    # keeps the key rather than resetting the memory.
    world["run"]()
    assert json.loads(world["state"].read_text())["service:system:fixture.service"] == {
        "status": "failed"
    }
    assert len([event for event in
                (json.loads(line) for line in world["ledger"].read_text().splitlines())
                if event["unit"] == "fixture.service"]) == 1


def test_a_mid_transition_unit_keeps_its_previous_verdict(world) -> None:
    """Registering the key without judging it is what stops a crash-looping
    unit from re-notifying on every restart: skipping it entirely would prune
    the key, which resets a genuine "failed" memory to empty."""
    world["state"].write_text(
        json.dumps({"service:system:midflight.service": {"status": "failed"}})
    )
    world["run"]()
    world["run"]()
    state = json.loads(world["state"].read_text())
    assert state["service:system:midflight.service"] == {"status": "failed"}


def test_the_prune_drops_keys_the_sweep_no_longer_emits(world) -> None:
    world["run"]()
    world["inventory"]["captures"] = [
        lane for lane in world["inventory"]["captures"] if lane["name"] != "ed-fresh"
    ]
    world["run"]()
    assert "capture:ed-fresh" not in json.loads(world["state"].read_text())
    assert "capture:fixture" in json.loads(world["state"].read_text())


def test_evidence_fields_survive_a_round_trip() -> None:
    evidence = "manager=user;active_state=failed;result=timeout;wanted_by="
    assert health.evidence_field(evidence, "result") == "timeout"
    assert health.evidence_field(evidence, "wanted_by") == ""
    assert health.evidence_field(evidence, "absent") == ""
    title, body = health.describe("service_failure", "x.service", "failed", evidence)
    assert title == "x.service stopped working"
    assert "time limit" in body
    assert "journalctl --user -u x.service -e" in body


def test_newest_mtime_handles_file_lane_paths(tmp_path):
    """Marker/ledger lanes point at files; os.walk alone yields nothing for
    them. Mutation: dropping the is_file branch fails this."""
    from sinnix_ops_reducer.health import newest_mtime

    lane_file = tmp_path / "persist.last-success"
    lane_file.write_text("ok\n")
    assert newest_mtime(lane_file) == lane_file.stat().st_mtime
    assert newest_mtime(tmp_path / "absent.jsonl") is None
