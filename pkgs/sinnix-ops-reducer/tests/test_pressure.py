"""The /pressure/ observation layer: regimes, the swap lane, and the hog table.

Every assertion here is a claim the 2026-08-18 incident clustering makes about
this machine, not a restatement of the code. The four that carry the design:

  1. **The regime boundaries are the measured ones.** 75% swap, PSI full 20/50,
     2 GiB available, IO full 40 -- each came out of an episode inventory, and
     a page that classifies differently sends the operator to the wrong action.
  2. **The swap lane fires on a PAIR.** Swap saturated *while nothing is
     stalling* is the ten-minute warning; swap saturated *while everything
     stalls* is the freeze itself. Collapsing them loses the only lead time
     this machine gets.
  3. **Ordering counts swapped pages.** `bd list` was measured at 8.19 GiB
     resident and 19.38 GiB swapped. Rank on RSS and it disappears.
  4. **A button exists only where the bounded action API admits the target.**
     Scope stop where the launcher's name shape matches, park where the runtime
     inventory carries the unit, and nowhere else -- the page states the gap
     instead of growing a private path to it.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from sinnix_ops_reducer import health, pressure, server
from sinnix_ops_reducer.actions import process_admitted_slices
from sinnix_ops_reducer.pages.pressure import (
    hog_row,
    hogs_card,
    parkable_units,
    render_pressure,
    scheduled_card,
)

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


# --------------------------------------------------------------------------
# regimes
# --------------------------------------------------------------------------


def test_regime_boundaries_are_the_measured_thresholds() -> None:
    """Mutation: move any threshold (75 -> 90, 20 -> 50, 2048 -> 1024, 40 -> 60)
    and the matching pair below stops straddling it."""
    assert pressure.classify(swap_at(74.9)).name == "CALM"
    assert pressure.classify(swap_at(75.0)).name == "SWAP-CRITICAL"

    assert pressure.classify(sample_with(memory_psi_full=19.9)).name == "CALM"
    stalling = pressure.classify(sample_with(memory_psi_full=20.0))
    assert stalling.name == "SWAP-CRITICAL" and stalling.cluster == "C1"

    assert pressure.classify(sample_with(mem_avail_mb=2048)).name == "CALM"
    spike = pressure.classify(sample_with(mem_avail_mb=2047))
    assert spike.name == "SPIKE" and spike.cluster == "C2"

    assert pressure.classify(sample_with(io_psi_full=39.9)).name == "CALM"
    saturated = pressure.classify(sample_with(io_psi_full=40.0))
    assert saturated.name == "IO-SATURATED" and saturated.cluster == "C5"


def test_the_freeze_regime_outranks_the_disks_and_the_spike() -> None:
    """The 2026-08-14 shape: swap pegged, everything stalled, and the disks
    saturated as a consequence. Reporting IO there points the operator at a
    backup that is a symptom.

    Mutation: check the IO or the mem_avail branch first and this reads
    IO-SATURATED / SPIKE.
    """
    both = pressure.classify(
        swap_at(99.0, memory_psi_full=80.0, io_psi_full=95.0, mem_avail_mb=900)
    )
    assert both.name == "SWAP-CRITICAL"
    assert "freeze itself" in both.detail

    # And the spike shape must NOT be dressed up as a freeze: PSI is what
    # separates them, and during a spike PSI is ~3.
    burst = pressure.classify(swap_at(60.0, memory_psi_full=3.0, mem_avail_mb=993))
    assert burst.name == "SPIKE"
    assert "two minutes" in burst.detail


def test_unreadable_pressure_is_not_reported_as_calm() -> None:
    """A page that says CALM because it could not read /proc is worse than one
    that says nothing. Mutation: returning the CALM regime for an empty sample."""
    regime = pressure.classify(pressure.Sample())
    assert regime.name == "UNKNOWN"
    assert "does not know" in regime.detail


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
    assert "/pressure/" in body

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
    assert stored[pressure.SWAP_LANE_KEY] == {"status": "pre-freeze"}
    assert len(lane["recorder"].notifications) == 1


def test_the_reducers_own_sweep_reads_the_machine_when_nothing_is_injected(
    tmp_path: Path,
) -> None:
    """The wiring, end to end: `server.run_sweep` is what the reducer loop
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
# the hog table
# --------------------------------------------------------------------------


def write_process(
    proc: Path, pid: int, name: str, rss_kb: int, swap_kb: int, cgroup: str, argv: str
) -> None:
    directory = proc / str(pid)
    directory.mkdir(parents=True)
    (directory / "status").write_text(
        f"Name:\t{name}\nState:\tS (sleeping)\nVmRSS:\t{rss_kb} kB\n"
        f"VmSwap:\t{swap_kb} kB\nThreads:\t1\n"
    )
    (directory / "cgroup").write_text(f"0::{cgroup}\n")
    (directory / "cmdline").write_bytes(argv.replace(" ", "\0").encode() + b"\0")
    (directory / "stat").write_text(
        f"{pid} ({name}) S 1 1 0 0 -1 0 0 0 0 0 0 0 0 0 20 0 1 0 987654 0 0\n"
    )


@pytest.fixture
def fake_proc(tmp_path: Path) -> Path:
    proc = tmp_path / "proc"
    proc.mkdir()
    agent_scope = (
        "/user.slice/user-1000.slice/user@1000.service/agent.slice/"
        "sinnix-agent-bd-1786988205604048771-1061646.scope"
    )
    # The measured C3 shape: modest resident set, enormous swap.
    write_process(
        proc, 101, "bd", 8_388_608, 20_316_160, agent_scope, "bd list --limit 500"
    )
    # Bigger resident set, no swap at all -- what an RSS-ordered table calls
    # the worst offender.
    write_process(
        proc,
        102,
        "chrome",
        12_582_912,
        0,
        "/user.slice/user-1000.slice/user@1000.service/app.slice/app-chrome.scope",
        "/run/current-system/sw/bin/chrome --type=renderer",
    )
    write_process(
        proc,
        103,
        "rustc",
        6_291_456,
        1_048_576,
        "/user.slice/user-1000.slice/user@1000.service/build.slice/"
        "sinnix-build-cargo-1786988205604048771-9.scope",
        "rustc --edition 2021 src/main.rs",
    )
    # A tool invocation placed inside a build: cheap to re-run in isolation,
    # but killing it costs the build, so the slice must win.
    write_process(
        proc,
        104,
        "git",
        2_097_152,
        0,
        "/user.slice/user-1000.slice/user@1000.service/nix-build.slice/"
        "sinnix-nix-build-nix-1786988205604048771-11.scope",
        "git fetch --all",
    )
    # A kernel thread: no VmRSS at all, and it must not appear.
    kernel = proc / "9"
    kernel.mkdir()
    (kernel / "status").write_text(
        "Name:\tkworker/0:1\nState:\tI (idle)\nThreads:\t1\n"
    )
    return proc


def test_ranking_counts_swapped_pages_not_just_resident_ones(fake_proc: Path) -> None:
    """`bd list` at 8.2 G resident and 19.4 G swapped outranks a 12 G Chrome
    renderer, because what it is holding is 27 G of anonymous memory.

    Mutation: sort on rss alone and chrome leads, which is exactly the view
    that hid this class of hog for months.
    """
    rows = pressure.scan_processes(limit=4, proc=fake_proc)
    assert [row.comm for row in rows] == ["bd", "chrome", "rustc", "git"]
    assert rows[0].swap_kb > rows[0].rss_kb
    assert rows[0].footprint_kb > rows[1].footprint_kb
    assert all(row.comm != "kworker/0:1" for row in rows)
    # The PID-reuse pin a process-level action would need is carried, not
    # invented later.
    assert rows[0].start_ticks == 987654


def test_cheapness_says_what_a_kill_costs_not_how_big_it_is(fake_proc: Path) -> None:
    """Mutation: classify on size, or drop the slice precedence, and the
    `git fetch` inside nix-build.slice becomes a free kill that in fact
    destroys a build."""
    rows = {row.comm: row for row in pressure.scan_processes(limit=4, proc=fake_proc)}
    assert rows["bd"].cheapness == pressure.CHEAPNESS_RERUNNABLE
    assert rows["rustc"].cheapness == pressure.CHEAPNESS_EXPENSIVE
    assert rows["chrome"].cheapness == pressure.CHEAPNESS_SESSION
    assert rows["git"].cheapness == pressure.CHEAPNESS_EXPENSIVE
    assert rows["bd"].unit.endswith(".scope")
    assert rows["bd"].slice_unit == "agent.slice"
    # Version-suffixed interpreters and prefix-named model servers are the two
    # shapes an exact-name set silently misses; both are C2 victims on the
    # measured record.
    assert (
        pressure.classify_cheapness({"python3.14"}, "system.slice")
        == pressure.CHEAPNESS_EXPENSIVE
    )
    assert (
        pressure.classify_cheapness({"sherpa-onnx-vad"}, "system.slice")
        == pressure.CHEAPNESS_EXPENSIVE
    )
    # And an agent session stays unclassified on purpose: which lane is
    # expendable is the operator's judgment, not a lookup.
    assert (
        pressure.classify_cheapness({"claude"}, "agent.slice")
        == pressure.CHEAPNESS_UNKNOWN
    )


def test_scopes_resolve_to_lanes_a_person_can_choose_between() -> None:
    """ "Which lane is expendable" is unanswerable about
    `sinnix-agent-1785530197414290568-596681.scope`.

    Mutation: print the unit name instead of resolving it and every assertion
    below reads back the raw scope.
    """
    assert (
        pressure.lane_of("sinnix-agent-bd-1786988205604048771-1061646.scope")
        == "agent · bd"
    )
    # The live scope's own checkout wins where the reducer has it: two agent
    # lanes differ by where they are working, not by the binary they ran.
    assert (
        pressure.lane_of(
            "sinnix-build-cargo-178698820560404877-9.scope",
            scopes_by_unit={
                "sinnix-build-cargo-178698820560404877-9.scope": {
                    "command": "xtask test",
                    "project": "sinex",
                }
            },
        )
        == "build · sinex"
    )
    assert (
        pressure.lane_of(
            "sinnix-agent-job-abc.scope",
            jobs_by_id={
                "abc": {
                    "backend": "claude",
                    "model": "opus",
                    "worktree": "/realm/worktrees/agent-7",
                }
            },
        )
        == "claude opus in agent-7"
    )
    assert pressure.lane_of("polylogued.service") == "polylogued.service"


# --------------------------------------------------------------------------
# actions: only where the bounded API admits the target
# --------------------------------------------------------------------------

INVENTORY: dict[str, Any] = {
    "schema": "sinnix-runtime-inventory-v1",
    "commandClasses": {name: {} for name in ("agent", "build", "nix-build")},
    "surfaces": {
        "borgbackup-job-realm": {
            "unit": "borgbackup-job-realm.service",
            "manager": "system",
            "kind": "service",
            "resourceClass": "backup-maintenance",
            "observe": {"enable": True, "restartable": False},
        },
        "activitywatch": {
            "unit": "activitywatch.service",
            "manager": "user",
            "kind": "service",
            "resourceClass": "background-maintenance",
            "observe": {"enable": True, "restartable": True},
        },
    },
}


def test_park_is_offered_exactly_where_the_action_api_resolves_the_unit() -> None:
    """`park` resolves its target through the runtime inventory, and
    sinnix-pressure-park's parkable set is the backup-maintenance system
    services. The nixpkgs-generated scrub timers are in neither, and an idle
    unit has no cgroup to freeze at all.

    Mutations, each caught here:
      * offer park for every scheduled row -> the scrub button 403s;
      * offer it for none -> the highest-value existing capability stays hidden;
      * ignore the live state -> the idle borg job gets a button whose receipt
        says "accepted" having frozen nothing.
    """
    parkable = parkable_units(INVENTORY)
    assert parkable == {"borgbackup-job-realm.service"}
    running = pressure.ScheduledRun(
        timer="borgbackup-job-realm.timer",
        unit="borgbackup-job-realm.service",
        next_seconds=540.0,
        last_seconds=1200.0,
        last_duration_seconds=4210.0,
        active=True,
    )
    scrub = pressure.ScheduledRun(
        timer="btrfs-scrub-realm.timer",
        unit="btrfs-scrub-realm.service",
        next_seconds=86400.0,
        last_seconds=None,
    )
    html = scheduled_card([running, scrub], parkable)
    assert "act('park','unit','borgbackup-job-realm.service'" in html
    assert "running now" in html
    assert "btrfs-scrub-realm.service" in html
    assert "act('park','unit','btrfs-scrub-realm.service'" not in html
    assert "no park verb" in html
    # The historical duration is the reason the strip is worth reading.
    assert "took 1h 10m" in html

    idle = scheduled_card([replace(running, active=False)], parkable)
    assert "act('park','unit'" not in idle
    assert "park freezes a running cgroup" in idle


def test_the_hog_table_offers_scope_stop_and_names_the_verb_it_lacks(
    fake_proc: Path,
) -> None:
    """A scope button may exist only where the action API's own name-shape
    admission accepts the unit; a per-process stop button may exist only on
    a re-runnable row whose live cgroup the action API would actually admit
    (sinnix-mble).

    Mutation: emit a stop button for any row with a unit and the app-scope
    Chrome row gets one the API answers 403 to; drop the missing-verb prose and
    the page silently implies the whole-scope stop is the only granularity;
    offer the process button on a row outside the admitted cgroups and it
    answers 403 too.
    """
    rows = {row.comm: row for row in pressure.scan_processes(limit=4, proc=fake_proc)}
    admitted = process_admitted_slices(INVENTORY)
    # agent.slice and build.slice are admitted unconditionally, with no
    # "slices" key in INVENTORY at all -- proving the base set does not
    # depend on the inventory carrying it.
    assert admitted == {"agent.slice", "build.slice"}

    cheap = hog_row(rows["bd"], {}, {}, admitted)
    assert "act('stop','scope','sinnix-agent-bd-" in cheap
    assert "stop the whole scope" in cheap
    # bd is re-runnable AND in agent.slice, which is admitted: it gets the
    # process button, carrying exactly the pid/start_ticks this row observed.
    assert (
        f"act('stop','process',{{pid: {rows['bd'].pid}, "
        f"start_ticks: {rows['bd'].start_ticks}}},this)" in cheap
    )
    assert "act('stop','scope'" not in hog_row(rows["chrome"], {}, {}, admitted)
    # rustc is classified EXPENSIVE (build.slice precedence over the command
    # name), not RERUNNABLE, so it never gets a process-stop button even
    # though build.slice is admitted.
    assert "act('stop','process'" not in hog_row(rows["rustc"], {}, {}, admitted)
    # A re-runnable command outside every admitted slice (a bare `git`
    # running as some system.slice service, say) gets no button -- and the
    # row says why, rather than silently withholding it.
    outside_admission = replace(rows["bd"], slice_unit="system.slice", unit="")
    assert outside_admission.cheapness == pressure.CHEAPNESS_RERUNNABLE
    outside_row = hog_row(outside_admission, {}, {}, admitted)
    assert "act('stop','process'" not in outside_row
    assert "no process-stop button" in outside_row

    html = render_pressure(
        {"host": "fixture"},
        None,
        INVENTORY,
        "2026-08-18T12:00:00+02:00",
        reading=swap_at(80.0, memory_psi_full=2.0),
        processes=list(rows.values()),
        runs=[],
    )
    assert "Per-process stop" in html
    assert "slices are not registered surfaces" in html
    # The full render wires the same admission the direct hog_row call used
    # above -- the bd row's process button is live end to end, not only when
    # a test hand-supplies the admitted set.
    assert (
        f"act('stop','process',{{pid: {rows['bd'].pid}, "
        f"start_ticks: {rows['bd'].start_ticks}}},this)" in html
    )


def test_process_admission_widens_with_a_sacrificial_slice_marker() -> None:
    """A slice outside agent.slice/build.slice is admitted only if the live
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
    assert admitted == {"agent.slice", "build.slice", "background.slice"}
    assert "gpu-runtime.slice" not in admitted


def test_session_processes_are_summed_rather_than_given_rows(fake_proc: Path) -> None:
    """C4, made structural. On a calm live host eight of the top ten processes
    by footprint were Chrome renderers; a table that spends its rows on them
    has none left for the hog an operator can do something about.

    Mutation: render session processes as ordinary rows and the aggregate line
    disappears while the individual renderer reappears — which is the naive
    top-consumers view the evidence rejects.
    """
    rows = pressure.scan_processes(limit=4, proc=fake_proc)
    html = hogs_card(rows, {}, {})
    assert "1 session processes" in html
    assert "collapsed on purpose" in html
    # The actionable rows survive, including the one an RSS ranking would have
    # pushed below Chrome.
    assert "bd list --limit 500" in html
    assert "rustc --edition" in html
    assert "--type=renderer" not in html


def test_the_page_leads_with_swap_and_buries_available_memory() -> None:
    """The whole point of the layout: the number that moves first is first, and
    the number that lies during a freeze is last.

    Mutation: put the availability card ahead of the headroom card (the
    conventional layout) and this ordering assertion fails.
    """
    html = render_pressure(
        {"host": "fixture"},
        None,
        INVENTORY,
        "2026-08-18T12:00:00+02:00",
        reading=swap_at(90.0, memory_psi_full=4.0, mem_avail_mb=12852),
        processes=[],
        runs=[],
    )
    assert html.index("Swap headroom") < html.index("Memory stall")
    assert html.index("Memory stall") < html.index("Available memory")
    assert "SWAP-CRITICAL" in html
    # Availability is present and explicitly demoted, rather than removed: the
    # finding is that it must be read after the other two, not that it is
    # useless.
    assert "12,852 MiB" in html
    assert "de-emphasised, and that is the finding" in html


def test_scheduled_selection_is_soonest_first_and_only_the_heavy_timers() -> None:
    """Mutation: filter by runtime-inventory resource class instead of unit
    name and the scrub timers -- 16.7 TiB over seven days, and in no sinnix
    surface -- vanish from the strip."""
    now_us = 1_787_052_000_000_000
    runs = pressure.select_scheduled(
        [
            {
                "unit": "sinnix-config-drift.timer",
                "activates": "sinnix-config-drift.service",
                "next": now_us + 60_000_000,
                "last": now_us - 60_000_000,
            },
            {
                "unit": "btrfs-scrub-realm.timer",
                "activates": "btrfs-scrub-realm.service",
                "next": now_us + 3_600_000_000,
                "last": 0,
            },
            {
                "unit": "borgbackup-job-realm.timer",
                "activates": "borgbackup-job-realm.service",
                "next": now_us + 600_000_000,
                "last": now_us - 1_200_000_000,
            },
        ],
        now_us,
    )
    assert [run.unit for run in runs] == [
        "borgbackup-job-realm.service",
        "btrfs-scrub-realm.service",
    ]
    assert runs[0].next_seconds == 600.0
    assert runs[0].last_seconds == 1200.0
    assert runs[1].last_seconds is None


def test_run_facts_read_systemds_own_timestamps_and_live_state() -> None:
    """Mutations: subtract the wrong pair (ActiveEnter/ActiveExit, both 0 for a
    finished oneshot) and every duration disappears; drop `Id` from the
    property list and `show_units` keys nothing at all, so the whole join comes
    back empty."""
    facts = pressure.unit_run_facts(
        ["borgbackup-job-realm.service", "btrbk.service"],
        show=lambda units, user, properties: {
            "borgbackup-job-realm.service": {
                "Id": "borgbackup-job-realm.service",
                "ActiveState": "inactive",
                "InactiveExitTimestampMonotonic": "333488126540",
                "InactiveEnterTimestampMonotonic": "337488126540",
            },
            "btrbk.service": {
                "Id": "btrbk.service",
                "ActiveState": "active",
                "InactiveExitTimestampMonotonic": "333488126540",
                "InactiveEnterTimestampMonotonic": "0",
            },
        },
    )
    assert facts["borgbackup-job-realm.service"] == {
        "last_duration_seconds": 4000.0,
        "active": False,
    }
    # Still running: there is no completed duration yet, and it is the one that
    # can actually be parked.
    assert facts["btrbk.service"] == {"last_duration_seconds": None, "active": True}
