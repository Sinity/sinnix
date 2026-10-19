"""The swap-headroom lane and process admission.

Claims the 2026-08-18 incident clustering makes about this machine, not
restatements of the code:

  1. **The swap lane fires on a PAIR.** Swap saturated *while nothing is
     stalling* is the ten-minute warning; swap saturated *while everything
     stalls* is the freeze itself. Collapsing them loses the only lead time
     this machine gets.
  2. **Process stop is admitted only where the action API admits it.**
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sinnix_hub_server import health, pressure, server
from sinnix_hub_server.actions import process_admitted_slices

CALM = pressure.Sample(
    swap_used_mb=2000,
    swap_total_mb=20480,
    mem_avail_mb=12000,
    mem_total_mb=32000,
    memory_psi_full=0.2,
    memory_psi_some=1.0,
    io_psi_full=1.0,
    cpu_psi_some=2.0,
)


def sample_with(**overrides: Any) -> pressure.Sample:
    fields = {
        "swap_used_mb": CALM.swap_used_mb,
        "swap_total_mb": CALM.swap_total_mb,
        "mem_avail_mb": CALM.mem_avail_mb,
        "mem_total_mb": CALM.mem_total_mb,
        "memory_psi_full": CALM.memory_psi_full,
        "memory_psi_some": CALM.memory_psi_some,
        "io_psi_full": CALM.io_psi_full,
        "cpu_psi_some": CALM.cpu_psi_some,
    }
    fields.update(overrides)
    return pressure.Sample(**fields)


def swap_at(percent: float, **overrides: Any) -> pressure.Sample:
    total = 20480
    return sample_with(
        swap_total_mb=total, swap_used_mb=int(total * percent / 100), **overrides
    )


def test_sample_parses_real_proc_shapes(tmp_path: Path) -> None:
    """The parser against the byte shapes /proc actually emits, including the
    `full` line PSI-less kernels omit.

    Mutation: reading `some` where `full` is meant (the field the dashboard's
    existing helper reads) makes memory_psi_full 12.0 and the lane blind to the
    difference between a busy machine and a frozen one.
    """
    proc = tmp_path
    (proc / "pressure").mkdir()
    (proc / "pressure" / "memory").write_text(
        "some avg10=12.00 avg60=8.00 avg300=4.00 total=1\n"
        "full avg10=78.25 avg60=60.00 avg300=30.00 total=2\n"
    )
    (proc / "pressure" / "io").write_text(
        "some avg10=41.00 avg60=1.00 avg300=1.00 total=3\n"
        "full avg10=40.50 avg60=1.00 avg300=1.00 total=4\n"
    )
    (proc / "meminfo").write_text(
        "MemTotal:       32689680 kB\n"
        "MemFree:          500000 kB\n"
        "MemAvailable:    3145728 kB\n"
        "SwapTotal:      20971520 kB\n"
        "SwapFree:        2097152 kB\n"
    )
    reading = pressure.sample(proc)
    assert reading.memory_psi_full == 78.25
    assert reading.memory_psi_some == 12.0
    assert reading.io_psi_full == 40.5
    assert reading.mem_avail_mb == 3072
    assert reading.swap_total_mb == 20480 and reading.swap_used_mb == 18432
    assert round(reading.swap_percent) == 90
    # No PSI at all (a kernel without CONFIG_PSI) is unknown, never zero.
    assert pressure.sample(tmp_path / "empty").memory_psi_full is None


# --------------------------------------------------------------------------
# the swap-headroom lane, through the sweep that actually runs it
# --------------------------------------------------------------------------


class Recorder:
    def __init__(self) -> None:
        self.notifications: list[tuple[str, str, str]] = []

    def __call__(self, urgency: str, title: str, body: str) -> None:
        self.notifications.append((urgency, title, body))


@pytest.fixture
def lane(tmp_path: Path):
    state = tmp_path / "health-state.json"
    ledger = tmp_path / "transitions.jsonl"
    recorder = Recorder()

    def sweep(reading: pressure.Sample) -> list[dict[str, Any]]:
        # The production entry point: server.run_sweep calls exactly this, and
        # the lane must ride the same emitter so it shares the debounce, the
        # ledger, the dedup state and the prune.
        health.sweep(
            {},
            health.Emitter(state, ledger, recorder),
            prober=lambda units, user: {},
            pressure_sample=reading,
        )
        return (
            [json.loads(line) for line in ledger.read_text().splitlines()]
            if ledger.exists()
            else []
        )

    return {"sweep": sweep, "recorder": recorder, "state": state}


def test_the_lane_emits_on_the_threshold_pair_and_only_there(lane) -> None:
    """swap >= 75% AND memory PSI full < 20 -- the pre-freeze state, ~10 minutes
    of lead time.

    Mutations, each of which this catches:
      * drop the PSI half of the condition -> the 82%-swap/45-PSI sweep also
        reports `pre-freeze` instead of `stalled`;
      * drop the swap half -> the 60%-swap sweep stops being healthy;
      * move the swap line to 90 -> the 76% sweep never transitions.
    """
    lane["sweep"](swap_at(60.0))
    lane["sweep"](swap_at(60.0))
    events = lane["sweep"](swap_at(60.0))
    assert [event["status"] for event in events] == ["healthy"]
    assert lane["recorder"].notifications == []

    lane["sweep"](swap_at(76.0, memory_psi_full=3.0))
    events = lane["sweep"](swap_at(76.0, memory_psi_full=3.0))
    warning = events[-1]
    assert warning["type"] == "swap_headroom"
    assert warning["status"] == "pre-freeze"
    assert warning["ok"] is False
    assert warning["schema"] == "sinnix-health-transition-v1"
    assert "swap_percent=76.0" in warning["evidence"]
    assert "memory_psi_full=3.0" in warning["evidence"]
    urgency, title, body = lane["recorder"].notifications[-1]
    assert urgency == "critical"
    assert "nothing is stalling yet" in title
    assert "ranking processes by swap" in body

    # Same saturation, but the machine is already stalling: that is the freeze,
    # not the warning, and it must not be reported as the warning.
    lane["sweep"](swap_at(82.0, memory_psi_full=45.0))
    events = lane["sweep"](swap_at(82.0, memory_psi_full=45.0))
    assert events[-1]["status"] == "stalled"


def test_the_lane_survives_the_sweeps_prune(lane) -> None:
    """The structural reason the lane lives inside health.sweep.

    `prune` drops every state key the sweep did not emit, so a lane emitted
    through a second emitter would lose its memory each tick and re-announce
    the same pre-freeze forever. Mutation: emit it from its own Emitter (or
    after prune) and the key is gone from the state file, which makes the
    repeat sweeps below notify again.
    """
    reading = swap_at(80.0, memory_psi_full=2.0)
    for _ in range(4):
        lane["sweep"](reading)
    stored = json.loads(lane["state"].read_text())
    assert stored[pressure.SWAP_LANE_KEY]["status"] == "pre-freeze"
    assert len(lane["recorder"].notifications) == 1


def test_the_hubs_own_sweep_reads_the_machine_when_nothing_is_injected(
    tmp_path: Path,
) -> None:
    """The wiring, end to end: `server.run_sweep` is what the hub server loop
    calls every 60 seconds, and it passes no sample, so the lane must read
    /proc itself.

    The *status* is whatever this host is doing and is deliberately not
    asserted; the key's presence is. Mutation: make the default sample a no-op
    (or drop the call from `health.sweep`) and the lane never appears in the
    state file on a real machine, while every injected-sample test above still
    passes.
    """
    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps({"schema": "sinnix-runtime-inventory-v1", "surfaces": {}})
    )
    state = tmp_path / "state.json"
    server.run_sweep(
        inventory,
        lambda: health.Emitter(state, tmp_path / "ledger.jsonl", Recorder()),
    )
    server.run_sweep(
        inventory,
        lambda: health.Emitter(state, tmp_path / "ledger.jsonl", Recorder()),
    )
    stored = json.loads(state.read_text())
    assert pressure.SWAP_LANE_KEY in stored
    believed = stored[pressure.SWAP_LANE_KEY]
    assert {believed.get("status"), believed.get("pending")} & {
        "healthy",
        "pre-freeze",
        "stalled",
    }


def test_a_machine_without_swap_registers_the_lane_without_judging_it(lane) -> None:
    """Mutation: emitting `healthy` for an unmeasurable sample claims headroom
    that was never observed."""
    lane["sweep"](pressure.Sample(memory_psi_full=1.0))
    events = lane["sweep"](pressure.Sample(memory_psi_full=1.0))
    assert events == []
    assert lane["recorder"].notifications == []


# --------------------------------------------------------------------------
# actions: only where the bounded API admits the target
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------


def test_process_admission_widens_with_a_sacrificial_slice_marker() -> None:
    """A slice outside agent.slice/agenttool.slice is admitted only if the live
    inventory itself marks it sacrificial (ManagedOOMMemoryPressure=kill) --
    mirroring the action API's own boundary, not a second hardcoded list.

    Mutation: derive the sacrificial set from a name list instead of the
    inventory's own marker and this stops tracking a real policy change.
    """
    inventory = {
        "schema": "sinnix-runtime-inventory-v1",
        "slices": {
            "user": {
                "background": {"ManagedOOMMemoryPressure": "kill"},
                "gpu-runtime": {},
            }
        },
    }
    admitted = process_admitted_slices(inventory)
    assert admitted == {"agent.slice", "agenttool.slice", "background.slice"}
    assert "gpu-runtime.slice" not in admitted
