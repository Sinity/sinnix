"""The inventory health sweep: transitions, debounce, and the notify rules.

Ported from an earlier NixOS VM check that drove a standalone bash sweep
through a fixture inventory with stub `df`/`systemctl`/`sudo` binaries on
PATH. The fixtures here are function-level instead (the unit prober and the
mount reader are injected), so every behavioural assertion the VM check made
survives, plus the ones its shape could not reach: acknowledged outages, the
notification rules, and the shared state between the OnFailure fast path and
the sweep.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sinnix_lib.atomic_json import write_json_atomic
from sinnix_ops_reducer import health, pressure

# Swap with headroom and nothing stalling: the swap lane's healthy path, held
# fixed so these tests judge the inventory sweeps alone. The lane's own
# behaviour is asserted in test_pressure.py.
CALM_PRESSURE = pressure.Sample(
    swap_used_mb=2000,
    swap_total_mb=20480,
    mem_avail_mb=12000,
    memory_psi_full=0.2,
    io_psi_full=1.0,
)

# The resting-state shapes, one fixture unit each -- the sweep derives its
# verdict from ActiveState/Type/Result/WantedBy and never from a unit list.
UNIT_FIXTURES: dict[str, dict[str, str]] = {
    # WantedBy set, down: a daemon that should be running, isn't.
    "fixture.service": {
        "ActiveState": "inactive",
        "Type": "simple",
        "Result": "success",
        "WantedBy": "multi-user.target",
    },
    # ran and exited cleanly
    "oneshot-done.service": {
        "ActiveState": "inactive",
        "Type": "oneshot",
        "Result": "success",
        "WantedBy": "",
    },
    # ran and failed
    "oneshot-failed.service": {
        "ActiveState": "inactive",
        "Type": "oneshot",
        "Result": "exit-code",
        "WantedBy": "",
    },
    # WantedBy empty: an on-demand backend idled out cleanly
    "backend-idle.service": {
        "ActiveState": "inactive",
        "Type": "exec",
        "Result": "success",
        "WantedBy": "",
    },
    # "on-demand" excuses being inactive, not crashing
    "backend-crashed.service": {
        "ActiveState": "inactive",
        "Type": "exec",
        "Result": "exit-code",
        "WantedBy": "",
    },
    # WantedBy still set, but declared socket-proxy: that declaration suffices
    "socket-proxy-declared.service": {
        "ActiveState": "inactive",
        "Type": "exec",
        "Result": "success",
        "WantedBy": "multi-user.target",
    },
    "acknowledged.service": {
        "ActiveState": "failed",
        "Type": "simple",
        "Result": "exit-code",
        "WantedBy": "multi-user.target",
    },
    "midflight.service": {
        "ActiveState": "activating",
        "Type": "oneshot",
        "Result": "success",
        "WantedBy": "",
    },
    "proxy-listening.socket": {
        "ActiveState": "active",
        "Type": "simple",
        "Result": "success",
        "WantedBy": "sockets.target",
    },
    "proxy-latched.socket": {
        "ActiveState": "failed",
        "Type": "simple",
        "Result": "trigger-limit-hit",
        "WantedBy": "sockets.target",
    },
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


class CaptureRecorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, str]] = []

    def emit(self, key: str, type_: str, unit: str, status: str, evidence: str) -> None:
        self.events.append((key, status, evidence))


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
                    "payload": {
                        "window_class": None,
                        "geometry": {},
                        "monitor": "DP-3",
                        "note": "x",
                    },
                }
            )
            + "\n"
        )
        live.open("a").write(
            json.dumps(
                {
                    "schema": "sinnix-capture-v1",
                    "seq": seq,
                    "payload": {
                        "window_class": "kitty",
                        "geometry": {"width": 1920},
                        "monitor": "DP-3",
                        "note": None,
                    },
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
                "payload": {
                    "window_class": "kitty",
                    "geometry": {"width": 1920},
                    "monitor": "DP-3",
                    "note": "present",
                },
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
            {
                "name": "fixture",
                "path": str(lanes / "stale"),
                "expectedCadenceSeconds": 60,
            },
            {
                "name": "ed-stale",
                "path": str(lanes / "stale"),
                "expectedStaleAfterSeconds": 60,
            },
            {
                "name": "ed-fresh",
                "path": str(lanes / "fresh"),
                "expectedStaleAfterSeconds": 600,
            },
            {
                "name": "payload-dead",
                "path": str(lanes / "payload-dead"),
                "requiredPayloadFields": fields,
            },
            {
                "name": "payload-live",
                "path": str(lanes / "payload-live"),
                "requiredPayloadFields": fields,
            },
            {
                "name": "probe-absent",
                "path": str(lanes / "fresh"),
                "livenessProbe": {
                    "command": f'[ -e "{marker}" ] && exit 0 || exit 1',
                    "timeoutSeconds": 5,
                },
            },
            {
                "name": "probe-unknown",
                "path": str(lanes / "fresh"),
                "livenessProbe": {"command": "exit 9", "timeoutSeconds": 5},
            },
            {
                "name": "probe-timeout",
                "path": str(lanes / "fresh"),
                "livenessProbe": {"command": "sleep 5", "timeoutSeconds": 1},
            },
            # Neither cadence nor budget, and nothing ever written: the most
            # broken a lane can be, and the state that used to raise nothing.
            {
                "name": "unbudgeted-never-wrote",
                "path": str(tmp_path / "does-not-exist"),
            },
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
            {
                "kind": "service",
                "manager": "system",
                "unit": "socket-proxy-declared.service",
                "activationMode": "socket-proxy",
            },
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
        health.sweep(
            inventory,
            health.Emitter(state, ledger, recorder),
            prober=prober,
            # The swap-headroom lane rides this same sweep; pinning its reading
            # keeps these assertions about the inventory lanes rather than
            # about whatever the build host's swap happens to be doing.
            pressure_sample=CALM_PRESSURE,
        )
        return (
            [json.loads(line) for line in ledger.read_text().splitlines()]
            if ledger.exists()
            else []
        )

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
    matches = [
        event for event in events if event["type"] == type_ and event["unit"] == unit
    ]
    return matches[-1] if matches else None


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        (79, "healthy"),
        (80, "warning"),
        (89, "warning"),
        (90, "failed"),
        (91, "failed"),
    ],
)
def test_mount_capacity_uses_inclusive_existing_thresholds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, usage: int, expected: str
) -> None:
    monkeypatch.setattr(health, "mount_usage_percent", lambda _path: usage)
    ledger = tmp_path / "events.jsonl"
    emitter = health.Emitter(
        tmp_path / "state.json", ledger, lambda *_: None, confirm_samples=1
    )

    health.sweep_mounts(
        [{"path": "/outer-realm", "warnPct": 80, "failPct": 90}], emitter
    )

    event = json.loads(ledger.read_text().splitlines()[-1])
    assert event["unit"] == "/outer-realm"
    assert event["status"] == expected
    assert "warn_percent=80;fail_percent=90" in event["evidence"]


def test_unavailable_mount_probe_is_unknown_not_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(*_args: Any, **_kwargs: Any) -> Any:
        raise FileNotFoundError("df unavailable")

    monkeypatch.setattr(health.subprocess, "run", unavailable)
    ledger = tmp_path / "events.jsonl"
    emitter = health.Emitter(
        tmp_path / "state.json", ledger, lambda *_: None, confirm_samples=1
    )

    assert health.mount_usage_percent("/outer-realm") is None
    health.sweep_mounts(
        [{"path": "/outer-realm", "warnPct": 80, "failPct": 90}], emitter
    )

    event = json.loads(ledger.read_text().splitlines()[-1])
    assert event["status"] == "unknown"
    assert event["evidence"] == (
        "usage_percent=unknown;warn_percent=80;fail_percent=90;probe=unavailable"
    )


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
    assert (
        find(events, "service_failure", "socket-proxy-declared.service")["ok"] is True
    )
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

    assert (
        find(events, "publisher_liveness", "probe-absent")["status"]
        == "publisher-absent"
    )
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
        title
        for _, title, _ in world["recorder"].notifications
        if "never produced" in title
    ]


def test_unknown_capture_freshness_is_calm_without_demoting_other_unknowns(
    tmp_path,
):
    recorder = Recorder()
    emitter = health.Emitter(
        tmp_path / "state.json", tmp_path / "ledger.jsonl", recorder
    )
    emitter.emit(
        "capture:unknown",
        "capture_stale",
        "unknown",
        "unknown",
        "path=/fixture;scan_complete=false;reason=budget",
        force_confirm=True,
    )
    emitter.emit(
        "socket:unknown",
        "socket_failure",
        "unknown.socket",
        "unknown",
        "manager=system;active_state=unknown",
        force_confirm=True,
    )

    assert [urgency for urgency, _title, _body in recorder.notifications] == [
        "normal",
        "critical",
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
    assert announced == [
        ("normal", "empty-but-declared lane has produced for the first time")
    ]


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
    assert [
        event
        for event in events
        if event["type"] == "capture_stale" and event["unit"] == "fixture"
    ] == [find(events, "capture_stale", "fixture")]


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
    bodies = {title: body for _, title, body in notifications}
    assert (
        "Look: journalctl -u fixture.service -e"
        in bodies["fixture.service stopped working"]
    )

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
    assert (
        len(
            [
                event
                for event in (
                    json.loads(line)
                    for line in world["ledger"].read_text().splitlines()
                )
                if event["unit"] == "fixture.service"
            ]
        )
        == 1
    )


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


def test_append_failure_does_not_confirm_debounce(tmp_path, monkeypatch) -> None:
    state = tmp_path / "health-state.json"
    ledger = tmp_path / "ledger.jsonl"
    emitter = health.Emitter(state, ledger, lambda *_: None)

    def boom(*_args, **_kwargs):
        raise OSError("injected append failure")

    monkeypatch.setattr(health, "append_jsonl", boom)
    with pytest.raises(OSError, match="injected append failure"):
        emitter.emit(
            "service:system:x.service",
            "service_failure",
            "x.service",
            "failed",
            "result=exit",
            force_confirm=True,
        )
    assert not state.exists() or json.loads(state.read_text()) == {}
    assert not ledger.exists()
    monkeypatch.undo()
    health.Emitter(state, ledger, lambda *_: None).emit(
        "service:system:x.service",
        "service_failure",
        "x.service",
        "failed",
        "result=exit",
        force_confirm=True,
    )
    assert json.loads(state.read_text()) == {
        "service:system:x.service": {"status": "failed"}
    }
    assert ledger.read_text()


def test_cache_publish_failure_after_append_allows_duplicate(
    tmp_path, monkeypatch
) -> None:
    state = tmp_path / "health-state.json"
    ledger = tmp_path / "ledger.jsonl"
    emitter = health.Emitter(state, ledger, lambda *_: None)
    real_write = write_json_atomic

    def fail_once(path, data, **kwargs):
        if Path(path) == state:
            raise OSError("injected cache publish failure")
        return real_write(path, data, **kwargs)

    monkeypatch.setattr("sinnix_lib.atomic_json.write_json_atomic", fail_once)
    with pytest.raises(OSError, match="injected cache publish failure"):
        emitter.emit(
            "service:system:x.service",
            "service_failure",
            "x.service",
            "failed",
            "result=exit",
            force_confirm=True,
        )
    assert ledger.exists() and ledger.read_text().strip()
    assert not state.exists() or json.loads(state.read_text() or "{}") == {}
    monkeypatch.undo()
    health.Emitter(state, ledger, lambda *_: None).emit(
        "service:system:x.service",
        "service_failure",
        "x.service",
        "failed",
        "result=exit",
        force_confirm=True,
    )
    lines = [line for line in ledger.read_text().splitlines() if line]
    assert len(lines) >= 2


def test_newest_mtime_handles_file_lane_paths(tmp_path):
    """Marker/ledger lanes point at files; os.walk alone yields nothing for
    them. Mutation: dropping the is_file branch fails this."""
    from sinnix_ops_reducer.health import newest_mtime

    lane_file = tmp_path / "persist.last-success"
    lane_file.write_text("ok\n")
    file_result = newest_mtime(lane_file)
    assert file_result.newest_mtime == lane_file.stat().st_mtime
    assert file_result.complete and file_result.reason is None
    missing = newest_mtime(tmp_path / "absent.jsonl")
    assert missing.newest_mtime is None
    assert missing.complete and missing.reason == "missing"


def test_newest_mtime_marks_populated_directory_fanout_incomplete(tmp_path):
    """Mutation: treating a 512-entry prefix as exhaustion invents no-file."""
    from sinnix_ops_reducer import health

    for index in range(512):
        child = tmp_path / f"dir-{index:03}"
        child.mkdir()
        (child / "capture.bin").write_bytes(b"x")

    result = health.newest_mtime(tmp_path)
    assert result.newest_mtime is None
    assert not result.complete
    assert result.reason == "budget"

    emitter = CaptureRecorder()
    health.sweep_captures(
        [{"name": "fanout", "path": str(tmp_path)}], emitter, now=10_000
    )
    assert emitter.events == [
        (
            "capture:fanout",
            "unknown",
            f"path={tmp_path};scan_complete=false;reason=budget;newest_age_seconds=;"
            "progress=marker-not-declared",
        )
    ]


def test_capped_flat_scan_uses_declared_append_only_directory_progress(
    tmp_path, monkeypatch
):
    """A fresh file after the prefix proves output without raising the stat cap."""
    import os

    from sinnix_ops_reducer import health

    for index in range(512):
        entry = tmp_path / f"capture-{index:03}.bin"
        entry.write_bytes(b"old")
        os.utime(entry, (1_000, 1_000))
    os.utime(tmp_path, (1_000, 1_000))
    fresh = tmp_path / "zzzz-fresh.bin"
    fresh.write_bytes(b"new")
    now = fresh.stat().st_mtime + 1
    progress = tmp_path.parent / f"{tmp_path.name}-progress"
    progress.touch()

    real_scandir = os.scandir

    class OrderedScandir:
        def __init__(self, directory):
            with real_scandir(directory) as entries:
                self._entries = sorted(entries, key=lambda entry: entry.name)

        def __enter__(self):
            return iter(self._entries)

        def __exit__(self, *_):
            return None

    monkeypatch.setattr(health.os, "scandir", OrderedScandir)
    result = health.newest_mtime(tmp_path)
    assert not result.complete and result.reason == "budget"
    assert result.newest_mtime == 1_000
    assert result.directory_mtime == tmp_path.stat().st_mtime

    emitter = CaptureRecorder()
    health.sweep_captures(
        [
            {
                "name": "flat",
                "path": str(tmp_path),
                "expectedStaleAfterSeconds": 600,
                "producerProgressPath": str(progress),
            }
        ],
        emitter,
        now=now,
    )
    key, status, evidence = emitter.events[0]
    assert key == "capture:flat" and status == "healthy"
    assert "scan_complete=false;reason=budget" in evidence
    assert "freshness_witness=producer-marker" in evidence


def test_unreadable_capture_scan_is_unknown_not_empty_or_healthy(tmp_path, monkeypatch):
    """Mutation: swallowing a read error as an empty or healthy tree fails."""
    from sinnix_ops_reducer import health

    (tmp_path / "old.bin").write_bytes(b"old")
    monkeypatch.setattr(
        health.os,
        "scandir",
        lambda _path: (_ for _ in ()).throw(PermissionError("denied")),
    )
    result = health.newest_mtime(tmp_path)
    assert result.newest_mtime is None
    assert not result.complete and result.reason == "read-error"

    emitter = CaptureRecorder()
    health.sweep_captures(
        [
            {
                "name": "unreadable",
                "path": str(tmp_path),
                "producerProgressPath": str(tmp_path / "missing-progress"),
            }
        ],
        emitter,
        now=10_000,
    )
    assert emitter.events[0][0:2] == ("capture:unreadable", "unknown")
    assert "reason=read-error" in emitter.events[0][2]


def test_persisted_progress_marker_supports_stale_verdict_after_budget(tmp_path):
    """An old marker plus no post-marker directory change proves real silence."""
    import os

    from sinnix_ops_reducer import health

    for index in range(512):
        child = tmp_path / f"dir-{index:03}"
        child.mkdir()
        (child / "capture.bin").write_bytes(b"x")
    os.utime(tmp_path, (1_000, 1_000))
    progress = tmp_path.parent / f"{tmp_path.name}-progress"
    progress.write_text("last successful producer output\n")
    os.utime(progress, (1_000, 1_000))

    emitter = CaptureRecorder()
    health.sweep_captures(
        [
            {
                "name": "stale-fanout",
                "path": str(tmp_path),
                "expectedStaleAfterSeconds": 600,
                "producerProgressPath": str(progress),
            }
        ],
        emitter,
        now=10_000,
    )
    key, status, evidence = emitter.events[0]
    assert key == "capture:stale-fanout" and status == "stale"
    assert "scan_complete=false;reason=budget" in evidence
    assert "freshness_witness=producer-marker" in evidence


def test_newest_mtime_is_bounded_and_finds_newest_partition_first(tmp_path):
    """A wide time-partitioned tree must not be walked exhaustively: the
    newest file sits under the newest subdirectory and must be found within
    the stat budget. Mutation: restoring os.walk fails the call-count bound."""
    import os

    from sinnix_ops_reducer import health

    for day in range(50):
        sub = tmp_path / f"2026-01-{day + 1:02d}"
        sub.mkdir()
        for i in range(40):
            f = sub / f"{i}.jsonl"
            f.write_text("x")
            os.utime(f, (1_000_000 + day * 100 + i,) * 2)
        os.utime(sub, (1_000_000 + day * 100,) * 2)
    newest_file = tmp_path / "2026-01-50" / "39.jsonl"
    stats: list[str] = []
    real_scandir = os.scandir

    class CountingEntry:
        def __init__(self, entry):
            self._entry = entry
            self.path = entry.path

        def stat(self, follow_symlinks=True):
            stats.append(self.path)
            return self._entry.stat(follow_symlinks=follow_symlinks)

        def is_file(self, follow_symlinks=True):
            return self._entry.is_file(follow_symlinks=follow_symlinks)

        def is_dir(self, follow_symlinks=True):
            return self._entry.is_dir(follow_symlinks=follow_symlinks)

    class CountingScandir:
        def __init__(self, directory):
            self._it = real_scandir(directory)

        def __enter__(self):
            return (CountingEntry(e) for e in self._it)

        def __exit__(self, *exc):
            self._it.close()

    health.os.scandir = CountingScandir
    try:
        result = health.newest_mtime(tmp_path, budget=200)
        assert result.newest_mtime == newest_file.stat().st_mtime
    finally:
        health.os.scandir = real_scandir
    assert not result.complete and result.reason == "budget"
    assert len(stats) <= 199  # The root directory stat uses the remaining slot.
    assert len(stats) < 2000  # 50 dirs * 40 files: an exhaustive walk stats them all
