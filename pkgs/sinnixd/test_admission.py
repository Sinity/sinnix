from __future__ import annotations

import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from sinnixd.jobs import (
    MEMORY_FULL_BLOCK_THRESHOLD,
    MEMORY_FULL_PREEMPT_THRESHOLD,
    AdmissionConflictError,
    GenericJobs,
    GenericJobSpec,
    GenericJobStore,
    SystemdJobTimeout,
    UserSystemdJobs,
)
from sinnixd.projects import (
    ConflictPolicy,
    ProjectAdapter,
    ProjectEnvironment,
    ProjectOperation,
    load_project_adapter,
)


@dataclass
class FakeSystemd:
    started: list[dict[str, object]] = field(default_factory=list)
    stopped: list[str] = field(default_factory=list)
    unit_properties: dict[str, dict[str, str]] = field(default_factory=dict)
    properties: dict[str, str] = field(
        default_factory=lambda: {
            "LoadState": "loaded",
            "ActiveState": "active",
            "Result": "success",
            "ExecMainStatus": "0",
            "MemoryPeak": "0",
        }
    )

    def start(self, **kwargs: object) -> None:
        self.started.append(dict(kwargs))

    def show(self, unit: str, *, timeout_seconds: float = 0.25) -> dict[str, str]:
        assert unit.startswith("sinnixd-job-")
        return dict(self.unit_properties.get(unit, self.properties))

    def stop(self, unit: str) -> None:
        self.stopped.append(unit)
        previous = self.unit_properties.get(unit, self.properties)
        stopped = {
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "signal",
            "ExecMainStatus": "15",
            "InvocationID": previous.get("InvocationID", "fixture"),
        }
        if unit in self.unit_properties:
            self.unit_properties[unit] = stopped
        else:
            self.properties = stopped


def project(root: Path, operations: tuple[ProjectOperation, ...]) -> ProjectAdapter:
    root.mkdir()
    (root / "tracked").write_text("fixture\n")
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "tracked"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--quiet",
            "-m",
            "fixture",
        ],
        check=True,
    )
    return ProjectAdapter(
        project_id="fixture",
        display_name="Fixture",
        root=root,
        descriptor=root / "project.toml",
        digest="sha256:" + "0" * 64,
        environment=ProjectEnvironment("fixture", ("env",), (), ()),
        workspace=None,
        conflicts=ConflictPolicy((), (), {}),
        operations=operations,
    )


def operation(name: str, **kwargs: object) -> ProjectOperation:
    defaults = {"pool": "normal", "result": "exit", "cache": "none"}
    defaults.update(kwargs)
    return ProjectOperation(name=name, description=name, command=(name,), **defaults)


def jobs(tmp_path: Path, systemd: FakeSystemd, pressure: float = 0.0) -> GenericJobs:
    return GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: {
            "memory_full_avg10": pressure,
            "memory_full_avg60": pressure,
        },
    )


def agent_spec(keys: tuple[str, ...]) -> GenericJobSpec:
    return GenericJobSpec(
        kind="attested-agent",
        command=("agent",),
        working_directory="/fixture",
        environment={"PATH": "/bin"},
        project_id="fixture",
        principal="agent-control",
        checkout={
            "project_id": "fixture",
            "project_path": "/fixture",
            "checkout_id": "checkout",
            "path": "/fixture",
            "git_common_dir": "/fixture/.git",
            "head": "0" * 40,
        },
        contract={"parameters": {"campaign": {"group": "lane"}}},
        result_kind="last-message",
        pool="agent",
        exclusive_keys=keys,
    )


def test_packet_admission_refuses_overlap_but_allows_disjoint_lane(
    tmp_path: Path,
) -> None:
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd)
    subject.start(agent_spec(("module:polylogue.cost",)))

    subject.start(
        agent_spec(("table:jobs",)),
        reject_conflicts=True,
    )
    with pytest.raises(AdmissionConflictError, match="module:polylogue.cost") as error:
        subject.start(
            agent_spec(("module:polylogue.cost", "table:jobs")),
            reject_conflicts=True,
        )

    assert tuple(error.value.conflicts) == ("module:polylogue.cost", "table:jobs")
    assert all(len(job_ids) == 1 for job_ids in error.value.conflicts.values())


def test_admission_claims_are_durable_and_ledger_explains_queue(
    tmp_path: Path,
) -> None:
    adapter = project(
        tmp_path / "project",
        (
            operation("hold", exclusive_keys=("fixture:store",)),
            operation("wait", exclusive_keys=("fixture:store",)),
        ),
    )
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd)

    holder = subject.start_declared(
        project=adapter,
        operation=adapter.operation("hold"),
        correlation_id="holder",
        parameters={},
    )
    queued = subject.start_declared(
        project=adapter,
        operation=adapter.operation("wait"),
        correlation_id="queued",
        parameters={},
    )

    persisted = subject._admission_state()
    assert persisted["claims"][holder["job_id"]] == {
        "job_id": holder["job_id"],
        "pool": "normal",
        "estimate_memory_bytes": 1024 * 1024 * 1024,
        "exclusive_keys": ["fixture:store"],
        "created_at": persisted["claims"][holder["job_id"]]["created_at"],
        "project_id": "fixture",
        "operation": "hold",
    }
    ledger = subject.admission_ledger()
    assert ledger["claims"][holder["job_id"]]["exclusive_keys"] == ["fixture:store"]
    assert ledger["queue"][0]["job_id"] == queued["job_id"]
    assert ledger["queue"][0]["blocked_by"] == ["exclusive-key"]
    assert (
        ledger["queue"][0]["arithmetic"]["pool_memory"]["after_bytes"]
        == 2 * 1024 * 1024 * 1024
    )


def test_descriptor_loads_typed_admission_controls(tmp_path: Path) -> None:
    root = tmp_path / "descriptor"
    root.mkdir()
    (root / "marker").touch()
    descriptor = root / ".agentctl"
    descriptor.mkdir()
    (descriptor / "project.toml").write_text("""
schema = 1
[project]
id = "fixture"
display_name = "Fixture"
root_markers = ["marker"]
[environment]
kind = "fixture"
command = ["env"]
[operations.prepare]
description = "prepare"
exec = ["prepare"]
pool = "interactive"
result = "exit"
cache = "none"
scratch = "tmpfs"
[operations.check]
description = "check"
exec = ["check"]
pool = "bulk"
result = "pytest"
cache = "tree+environment"
dependencies = ["prepare"]
exclusive_keys = ["fixture:store"]
estimate_memory_bytes = 1048576
scratch = "nvme"
""")
    check = load_project_adapter(root).operation("check")
    assert check.dependencies == ("prepare",)
    assert check.exclusive_keys == ("fixture:store",)
    assert check.estimate_memory_bytes == 1_048_576 and check.scratch == "nvme"


def test_mixed_workload_injects_light_workers_and_queues_bulk(tmp_path: Path) -> None:
    adapter = project(
        tmp_path / "project",
        (
            operation(
                "heavy", pool="bulk", estimate_memory_bytes=12 * 1024 * 1024 * 1024
            ),
            operation(
                "light", pool="interactive", estimate_memory_bytes=64 * 1024 * 1024
            ),
        ),
    )
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd)

    first = subject.start_declared(
        project=adapter,
        operation=adapter.operation("heavy"),
        correlation_id="one",
        parameters={},
    )
    second = subject.start_declared(
        project=adapter,
        operation=adapter.operation("heavy"),
        correlation_id="two",
        principal="agent-control",
        parameters={},
    )
    light_a = subject.start_declared(
        project=adapter,
        operation=adapter.operation("light"),
        correlation_id="three",
        parameters={},
    )
    light_b = subject.start_declared(
        project=adapter,
        operation=adapter.operation("light"),
        correlation_id="four",
        principal="agent-control",
        parameters={},
    )

    assert [entry["command"] for entry in systemd.started] == [
        ("env", "heavy"),
        ("env", "light"),
        ("env", "light"),
    ]
    assert subject.get(second["job_id"])["state"]["phase"] == "queued"
    assert light_a["state"]["phase"] == light_b["state"]["phase"] == "submitted"
    assert first["state"]["phase"] == "submitted"


def test_lone_job_larger_than_pool_budget_is_not_permanently_starved(
    tmp_path: Path,
) -> None:
    adapter = project(
        tmp_path / "project",
        (
            operation(
                "oversized", pool="bulk", estimate_memory_bytes=24 * 1024 * 1024 * 1024
            ),
        ),
    )
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd)

    started = subject.start_declared(
        project=adapter,
        operation=adapter.operation("oversized"),
        correlation_id="oversized",
        parameters={},
    )

    assert started["state"]["phase"] == "submitted"
    assert started["state"]["admitted_at"]
    assert (
        started["state"]["admission"]["estimate_memory_bytes"]
        == 24 * 1024 * 1024 * 1024
    )
    assert [entry["command"] for entry in systemd.started] == [("env", "oversized")]


def test_swap_exhaustion_queues_even_a_small_agent_job(tmp_path: Path) -> None:
    systemd = FakeSystemd()
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: {
            "memory_full_avg10": 0.0,
            "io_full_avg10": 0.0,
            "memory_total_bytes": 32 * 1024 * 1024 * 1024,
            "memory_available_bytes": 2 * 1024 * 1024 * 1024,
            "swap_total_bytes": 20 * 1024 * 1024 * 1024,
            "swap_free_bytes": 0,
            "managed_memory_bytes": 0,
        },
    )

    queued = subject.start(agent_spec(("table:jobs",)))

    assert queued["state"]["phase"] == "queued"
    assert "host-pressure" in queued["state"]["admission"]["blocked_by"]
    assert queued["state"]["admission"]["host"]["swap_free_bytes"] == 0
    assert systemd.started == []


def test_cold_swap_with_plentiful_ram_does_not_block_admission(
    tmp_path: Path,
) -> None:
    """Nearly-full swap alone is occupancy, not danger: with high available
    RAM and zero stall pressure the job admits (2026-08-31 wedge: free
    fraction 0.145 held the whole queue at zero running jobs). Anti-vacuity:
    restoring the unconditional swap gate turns this red."""
    systemd = FakeSystemd()
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: {
            "memory_full_avg10": 0.0,
            "io_full_avg10": 0.0,
            "memory_total_bytes": 32 * 1024 * 1024 * 1024,
            "memory_available_bytes": 9 * 1024 * 1024 * 1024,
            "swap_total_bytes": 20 * 1024 * 1024 * 1024,
            "swap_free_bytes": 1 * 1024 * 1024 * 1024,
            "managed_memory_bytes": 0,
        },
    )

    started = subject.start(agent_spec(("table:jobs",)))

    assert started["state"]["phase"] != "queued"
    assert systemd.started != []


def test_memory_psi_noise_does_not_block_admission(tmp_path: Path) -> None:
    """0.39% full PSI is 39 ms of whole-system stall in the ten-second window."""
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd, pressure=0.39)

    started = subject.start(agent_spec(("table:jobs",)))

    assert started["state"]["phase"] == "submitted"
    assert len(systemd.started) == 1


def test_memory_psi_block_requires_two_avg10_probes(tmp_path: Path) -> None:
    probes = iter(
        (
            {"memory_full_avg10": MEMORY_FULL_BLOCK_THRESHOLD},
            {"memory_full_avg10": 0.0},
            {"memory_full_avg10": MEMORY_FULL_BLOCK_THRESHOLD},
            {"memory_full_avg10": MEMORY_FULL_BLOCK_THRESHOLD},
        )
    )
    systemd = FakeSystemd()
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: next(probes),
    )

    first = subject.start(agent_spec(("table:first",)))
    second = subject.start(agent_spec(("table:second",)))

    assert first["state"]["phase"] == "submitted"
    assert second["state"]["phase"] == "queued"


def test_memory_psi_avg60_blocks_on_the_first_probe(tmp_path: Path) -> None:
    pressure = {
        "memory_full_avg10": 0.0,
        "memory_full_avg60": MEMORY_FULL_BLOCK_THRESHOLD,
    }
    systemd = FakeSystemd()
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: pressure,
    )

    queued = subject.start(agent_spec(("table:jobs",)))

    assert queued["state"]["phase"] == "queued"
    assert systemd.started == []


def test_io_pressure_never_blocks_admission(tmp_path: Path) -> None:
    """Host IO PSI cannot attribute stalls to managed work on this host
    (ambient io full sits above any usable threshold), so admission ignores
    it. Red if anyone reintroduces an IO gate."""
    adapter = project(
        tmp_path / "project",
        (operation("first"), operation("second")),
    )
    systemd = FakeSystemd()
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: {
            "memory_full_avg10": 0.0,
            "io_full_avg10": 55.0,
        },
    )

    first = subject.start_declared(
        project=adapter,
        operation=adapter.operation("first"),
        correlation_id="first",
        parameters={},
    )
    second = subject.start_declared(
        project=adapter,
        operation=adapter.operation("second"),
        correlation_id="second",
        parameters={},
    )

    assert first["state"]["phase"] == "submitted"
    assert second["state"]["phase"] == "submitted"
    assert len(systemd.started) == 2


def test_host_budget_accounts_for_active_jobs_across_pools(tmp_path: Path) -> None:
    adapter = project(
        tmp_path / "project",
        (
            operation(
                "bulk", pool="bulk", estimate_memory_bytes=18 * 1024 * 1024 * 1024
            ),
        ),
    )
    systemd = FakeSystemd()
    pressure = {
        "memory_full_avg10": 0.0,
        "io_full_avg10": 0.0,
        "memory_total_bytes": 32 * 1024 * 1024 * 1024,
        # Real headroom decides: 24 GiB free minus the 2.56 GiB reserve leaves
        # 21.4 GiB; the just-launched bulk job (18 GiB, not yet in the kernel's
        # figure) plus a 12 GiB candidate does not fit.
        "memory_available_bytes": 24 * 1024 * 1024 * 1024,
        "swap_total_bytes": 20 * 1024 * 1024 * 1024,
        "swap_free_bytes": 20 * 1024 * 1024 * 1024,
        "managed_memory_bytes": 0,
    }
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: pressure,
    )
    subject.start_declared(
        project=adapter,
        operation=adapter.operation("bulk"),
        correlation_id="bulk",
        parameters={},
    )
    candidate = agent_spec(("table:jobs",))
    candidate = GenericJobSpec(
        **{
            **candidate.__dict__,
            "estimate_memory_bytes": 12 * 1024 * 1024 * 1024,
        }
    )

    queued = subject.start(candidate)

    assert queued["state"]["phase"] == "queued"
    assert queued["state"]["admission"]["blocked_by"] == ["host-memory"]
    assert (
        queued["state"]["admission"]["host"]["occupied_memory_bytes"]
        == 18 * 1024 * 1024 * 1024
    )
    assert len(systemd.started) == 1


def test_unchanged_admission_block_does_not_rewrite_job_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = project(
        tmp_path / "project",
        (operation("heavy", pool="bulk", estimate_memory_bytes=1024),),
    )
    pressure = {
        "memory_full_avg10": MEMORY_FULL_BLOCK_THRESHOLD,
        "memory_full_avg60": MEMORY_FULL_BLOCK_THRESHOLD,
    }
    subject = GenericJobs(
        FakeSystemd(),
        GenericJobStore(tmp_path / "state"),
        pressure_probe=lambda: pressure,
    )
    queued = subject.start_declared(
        project=adapter,
        operation=adapter.operation("heavy"),
        correlation_id="queued",
        parameters={},
    )
    assert queued["state"]["admission"]["blocked_by"] == ["host-pressure"]
    writes: list[object] = []
    monkeypatch.setattr(subject.store, "save", writes.append)
    pressure["memory_full_avg10"] = 2.0

    subject._admit_locked()

    assert writes == []


def test_scheduler_admits_queued_work_after_pressure_clears(tmp_path: Path) -> None:
    adapter = project(
        tmp_path / "project",
        (operation("heavy", pool="bulk", estimate_memory_bytes=1024),),
    )
    pressure = {
        "memory_full_avg10": MEMORY_FULL_BLOCK_THRESHOLD,
        "memory_full_avg60": MEMORY_FULL_BLOCK_THRESHOLD,
    }
    admitted = threading.Event()
    systemd = FakeSystemd()
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        pressure_probe=lambda: pressure,
        before_admission_start=lambda _job_id: admitted.set(),
        admission_retry_seconds=0.001,
    )
    queued = subject.start_declared(
        project=adapter,
        operation=adapter.operation("heavy"),
        correlation_id="queued",
        parameters={},
    )
    assert queued["state"]["phase"] == "queued"
    stop_event = threading.Event()
    scheduler = threading.Thread(
        target=subject.run_admission_scheduler, args=(stop_event,)
    )
    scheduler.start()
    try:
        pressure["memory_full_avg10"] = 0.0
        pressure["memory_full_avg60"] = 0.0
        assert admitted.wait(1)
    finally:
        stop_event.set()
        scheduler.join(1)

    assert not scheduler.is_alive()
    assert len(systemd.started) == 1


def test_sustained_pressure_preempts_largest_managed_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pressure = {
        "memory_full_avg10": 0.0,
        "io_full_avg10": 0.0,
        "memory_total_bytes": 32 * 1024**3,
        "memory_available_bytes": 24 * 1024**3,
        "swap_total_bytes": 20 * 1024**3,
        "swap_free_bytes": 20 * 1024**3,
        "managed_memory_bytes": 0,
    }
    clock = [0.0]
    monkeypatch.setattr("sinnixd.jobs.time.monotonic", lambda: clock[0])
    systemd = FakeSystemd()
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        pressure_probe=lambda: pressure,
    )
    first = subject.start(agent_spec(("table:first",)))
    second = subject.start(agent_spec(("table:second",)))
    interactive = subject.start_foreground(
        command=("terminal",), working_directory="/fixture", environment={}
    )
    base = {
        "LoadState": "loaded",
        "ActiveState": "active",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    systemd.unit_properties[first["unit"]] = {
        **base,
        "InvocationID": "first",
        "MemoryCurrent": str(1024**3),
        "MemorySwapCurrent": "0",
        "MemoryPeak": str(2 * 1024**3),
    }
    systemd.unit_properties[second["unit"]] = {
        **base,
        "InvocationID": "second",
        "MemoryCurrent": str(5 * 1024**3),
        "MemorySwapCurrent": str(1024**3),
        "MemoryPeak": str(6 * 1024**3),
    }
    systemd.unit_properties[interactive["unit"]] = {
        **base,
        "InvocationID": "interactive",
        "MemoryCurrent": str(8 * 1024**3),
        "MemorySwapCurrent": "0",
        "MemoryPeak": str(8 * 1024**3),
    }

    pressure.update(
        memory_full_avg10=MEMORY_FULL_PREEMPT_THRESHOLD,
        memory_available_bytes=4 * 1024**3,
        swap_free_bytes=4 * 1024**3,
        managed_memory_bytes=7 * 1024**3,
    )
    assert subject._relieve_active_pressure(pressure) is None
    clock[0] = 2.1
    assert subject._relieve_active_pressure(pressure) == second["job_id"]

    assert systemd.stopped == [second["unit"]]
    preempted = subject.get(second["job_id"])
    assert preempted["state"]["phase"] == "cancelled"
    assert preempted["state"]["preemption"]["reason"] == ["memory-stall"]
    assert (
        preempted["state"]["cancellation"]["reason"]
        == "pressure-preemption:memory-stall"
    )
    assert preempted["state"]["pre_stop_systemd"]["MemoryPeak"] == str(6 * 1024**3)
    assert interactive["unit"] not in systemd.stopped


def test_transient_pressure_does_not_preempt_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pressure = {"memory_full_avg10": 0.0}
    clock = [0.0]
    monkeypatch.setattr("sinnixd.jobs.time.monotonic", lambda: clock[0])
    systemd = FakeSystemd()
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        pressure_probe=lambda: pressure,
    )
    subject.start(agent_spec(("table:first",)))

    pressure["memory_full_avg10"] = MEMORY_FULL_PREEMPT_THRESHOLD
    assert subject._relieve_active_pressure(pressure) is None
    clock[0] = 1.0
    pressure["memory_full_avg10"] = 0.0
    assert subject._relieve_active_pressure(pressure) is None

    assert systemd.stopped == []


def test_oom_kill_is_terminal_even_when_log_mentions_backend_capacity(
    tmp_path: Path,
) -> None:
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd)
    started = subject.start(agent_spec(("table:first",)))
    subject.store.load(started["job_id"]).log_path.write_text("capacity exceeded\n")
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "failed",
        "Result": "oom-kill",
        "ExecMainStatus": "9",
        "MemoryPeak": str(14 * 1024**3),
    }

    observed = subject.get(started["job_id"])

    assert observed["state"]["phase"] == "failed"
    assert observed["state"]["terminal"] is True
    assert "capacity" not in observed["state"]


def test_wait_does_not_drive_admission_on_each_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = project(
        tmp_path / "project",
        (operation("heavy", pool="bulk", estimate_memory_bytes=1024),),
    )
    probes = 0

    def pressure_probe() -> dict[str, float]:
        nonlocal probes
        probes += 1
        return {
            "memory_full_avg10": MEMORY_FULL_BLOCK_THRESHOLD,
            "memory_full_avg60": MEMORY_FULL_BLOCK_THRESHOLD,
        }

    subject = GenericJobs(
        FakeSystemd(),
        GenericJobStore(tmp_path / "state"),
        pressure_probe=pressure_probe,
        wait_poll_seconds=0.1,
    )
    queued = subject.start_declared(
        project=adapter,
        operation=adapter.operation("heavy"),
        correlation_id="queued",
        parameters={},
    )
    clock = [0.0]
    monkeypatch.setattr("sinnixd.jobs.time.monotonic", lambda: clock[0])
    monkeypatch.setattr(
        "sinnixd.jobs.TerminalEvents.wait_terminal",
        lambda self, job_ids, seconds: (
            clock.__setitem__(0, clock[0] + seconds),
            False,
        )[1],
    )
    probes = 0

    waited = subject.wait(queued["job_id"], timeout_seconds=1)

    assert waited["wait_timed_out"]
    assert probes == 1


def test_failed_launch_peak_does_not_replace_declared_memory_estimate(
    tmp_path: Path,
) -> None:
    adapter = project(
        tmp_path / "project",
        (
            operation(
                "heavy", pool="bulk", estimate_memory_bytes=12 * 1024 * 1024 * 1024
            ),
        ),
    )
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd)
    started = subject.start_declared(
        project=adapter,
        operation=adapter.operation("heavy"),
        correlation_id="failed",
        parameters={},
    )
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "exit-code",
        "ExecMainStatus": "1",
        "MemoryPeak": str(128 * 1024 * 1024),
    }
    subject.get(started["job_id"])

    repeated = subject.start_declared(
        project=adapter,
        operation=adapter.operation("heavy"),
        correlation_id="retry",
        parameters={},
    )

    assert (
        repeated["state"]["admission"]["estimate_memory_bytes"]
        == 12 * 1024 * 1024 * 1024
    )


def test_small_successful_peak_does_not_erase_declared_estimate(
    tmp_path: Path,
) -> None:
    adapter = project(
        tmp_path / "project",
        (
            operation(
                "heavy", pool="bulk", estimate_memory_bytes=12 * 1024 * 1024 * 1024
            ),
        ),
    )
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd)
    started = subject.start_declared(
        project=adapter,
        operation=adapter.operation("heavy"),
        correlation_id="first",
        parameters={},
    )
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
        "MemoryPeak": str(32 * 1024 * 1024),
    }
    subject.get(started["job_id"])

    repeated = subject.start_declared(
        project=adapter,
        operation=adapter.operation("heavy"),
        correlation_id="second",
        parameters={},
    )

    assert (
        repeated["state"]["admission"]["estimate_memory_bytes"]
        == 12 * 1024 * 1024 * 1024
    )


def test_observed_peak_does_not_change_later_estimates(tmp_path: Path) -> None:
    """Estimates are declared-or-default only. A completed run's peak must
    not alter later admissions: learned high-water estimates serialized a
    campaign to one lane and wedged the queue (2026-08-29/09-01)."""
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd)
    started = subject.start(agent_spec(("table:first",)))
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
        "MemoryPeak": str(9 * 1024 * 1024 * 1024),
    }
    subject.get(started["job_id"])

    from sinnixd.jobs import POOL_POLICIES

    repeated = subject.start(agent_spec(("table:second",)))
    claimed = repeated["state"]["admission"]["estimate_memory_bytes"]
    assert claimed == POOL_POLICIES["agent"]["default_estimate"]
    assert "estimates" not in subject._admission_state()


def test_cache_and_coalescing_are_principal_isolated(tmp_path: Path) -> None:
    adapter = project(
        tmp_path / "project", (operation("check", cache="tree+environment"),)
    )
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd)

    operator_first = subject.start_declared(
        project=adapter,
        operation=adapter.operation("check"),
        correlation_id="operator-first",
        principal="operator",
        parameters={},
    )
    operator_duplicate = subject.start_declared(
        project=adapter,
        operation=adapter.operation("check"),
        correlation_id="operator-duplicate",
        principal="operator",
        parameters={},
    )
    agent_first = subject.start_declared(
        project=adapter,
        operation=adapter.operation("check"),
        correlation_id="agent-first",
        principal="agent-control",
        parameters={},
    )
    agent_duplicate = subject.start_declared(
        project=adapter,
        operation=adapter.operation("check"),
        correlation_id="agent-duplicate",
        principal="agent-control",
        parameters={},
    )

    assert operator_duplicate["job_id"] == operator_first["job_id"]
    assert operator_duplicate["coalesced"]
    assert agent_duplicate["job_id"] == agent_first["job_id"]
    assert agent_duplicate["coalesced"]
    assert agent_first["job_id"] != operator_first["job_id"]
    assert len(systemd.started) == 2

    operator_record = subject.store.load(operator_first["job_id"])
    agent_record = subject.store.load(agent_first["job_id"])
    assert operator_record.spec.principal == "operator"
    assert agent_record.spec.principal == "agent-control"
    assert operator_record.spec.cache_key != agent_record.spec.cache_key

    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    assert subject.get(operator_first["job_id"])["state"]["phase"] == "succeeded"
    assert subject.get(agent_first["job_id"])["state"]["phase"] == "succeeded"

    operator_cached = subject.start_declared(
        project=adapter,
        operation=adapter.operation("check"),
        correlation_id="operator-cached",
        principal="operator",
        parameters={},
    )
    agent_cached = subject.start_declared(
        project=adapter,
        operation=adapter.operation("check"),
        correlation_id="agent-cached",
        principal="agent-control",
        parameters={},
    )
    assert (
        operator_cached["job_id"] == operator_first["job_id"]
        and operator_cached["reused"]
    )
    assert agent_cached["job_id"] == agent_first["job_id"] and agent_cached["reused"]

    (adapter.root / "tracked").write_text("changed\n")
    uncached = subject.start_declared(
        project=adapter,
        operation=adapter.operation("check"),
        correlation_id="operator-uncached",
        principal="operator",
        parameters={},
    )
    assert uncached["job_id"] != operator_first["job_id"] and len(systemd.started) == 3


def test_dependencies_exclusive_keys_defaults_and_pressure_gate(
    tmp_path: Path,
) -> None:
    adapter = project(
        tmp_path / "project",
        (
            operation("prepare", estimate_memory_bytes=64 * 1024 * 1024),
            operation(
                "check",
                dependencies=("prepare",),
                cache="none",
                exclusive_keys=("fixture:store",),
            ),
            operation("other", exclusive_keys=("fixture:store",)),
            operation(
                "heavy", pool="bulk", estimate_memory_bytes=12 * 1024 * 1024 * 1024
            ),
            operation("interactive", pool="interactive"),
        ),
    )
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd, pressure=MEMORY_FULL_BLOCK_THRESHOLD)

    heavy = subject.start_declared(
        project=adapter,
        operation=adapter.operation("heavy"),
        correlation_id="heavy",
        parameters={},
    )
    interactive = subject.start_declared(
        project=adapter,
        operation=adapter.operation("interactive"),
        correlation_id="interactive",
        parameters={},
    )
    assert heavy["state"]["phase"] == "queued"
    assert interactive["state"]["phase"] == "submitted"
    assert not systemd.stopped

    subject.pressure_probe = lambda: {"memory_full_avg10": 0.0}
    primary = subject.start_declared(
        project=adapter,
        operation=adapter.operation("check"),
        correlation_id="check",
        parameters={},
    )
    prepare_id = primary["state"]["dependencies"][0]
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
        "MemoryPeak": str(777 * 1024 * 1024),
    }
    subject.get(prepare_id)
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "active",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    primary_state = subject.get(primary["job_id"])
    competing = subject.start_declared(
        project=adapter,
        operation=adapter.operation("other"),
        correlation_id="other",
        parameters={},
    )
    assert primary_state["state"]["phase"] in {"submitted", "running"}
    assert subject.get(competing["job_id"])["state"]["phase"] == "queued"
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
        "MemoryPeak": str(2 * 1024 * 1024 * 1024),
    }
    subject.get(primary["job_id"])
    repeated = subject.start_declared(
        project=adapter,
        operation=adapter.operation("check"),
        correlation_id="again",
        parameters={},
    )
    assert repeated["state"]["admission"]["estimate_memory_bytes"] == 1024 * 1024 * 1024


@pytest.mark.parametrize("scratch", ("tmpfs", "nvme"))
def test_owned_scratch_is_injected_cleaned_on_terminal_and_recovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scratch: str
) -> None:
    monkeypatch.setenv("SINNIXD_TMPFS_SCRATCH_ROOT", str(tmp_path / "tmpfs"))
    monkeypatch.setenv("SINNIXD_NVME_SCRATCH_ROOT", str(tmp_path / "nvme"))
    adapter = project(tmp_path / "project", (operation("scratch", scratch=scratch),))
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd)
    started = subject.start_declared(
        project=adapter,
        operation=adapter.operation("scratch"),
        correlation_id="one",
        parameters={},
    )
    record = subject.store.load(started["job_id"])
    assert record.scratch_path is not None and record.scratch_path.exists()
    command, environment = subject.store.declared_launch(record.job_id)
    assert command[:2] == ("env", f"TMPDIR={record.scratch_path}")
    assert "TMPDIR" not in environment
    assert "TMPDIR" not in systemd.started[0]["environment"]
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "failed",
        "ExecMainStatus": "1",
    }
    subject.get(started["job_id"])
    assert not record.scratch_path.exists()
    succeeded = subject.start_declared(
        project=adapter,
        operation=adapter.operation("scratch"),
        correlation_id="two",
        parameters={},
    )
    success_record = subject.store.load(succeeded["job_id"])
    assert (
        success_record.scratch_path is not None and success_record.scratch_path.exists()
    )
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    subject.get(succeeded["job_id"])
    assert not success_record.scratch_path.exists()
    cancelled = subject.start_declared(
        project=adapter,
        operation=adapter.operation("scratch"),
        correlation_id="three",
        parameters={},
    )
    cancel_record = subject.store.load(cancelled["job_id"])
    assert (
        cancel_record.scratch_path is not None and cancel_record.scratch_path.exists()
    )
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "active",
        "Result": "success",
        "ExecMainStatus": "0",
        "InvocationID": "fixture",
    }
    subject.cancel(cancelled["job_id"], reason="test-cancel")
    assert not cancel_record.scratch_path.exists()
    recovered = subject.store.create(
        GenericJobSpec(
            kind="foreground-command",
            command=("fixture",),
            working_directory=str(tmp_path),
            environment={},
            scratch=scratch,
        )
    )
    assert recovered.scratch_path is not None and recovered.scratch_path.exists()
    subject.store.save(
        subject._with_state(recovered, {"phase": "failed", "terminal": True})
    )
    GenericJobs(systemd, subject.store)
    assert not recovered.scratch_path.exists()

    protected = subject.store.create(
        GenericJobSpec(
            kind="foreground-command",
            command=("fixture",),
            working_directory=str(tmp_path),
            environment={},
            scratch=scratch,
        )
    )
    assert protected.scratch_path is not None
    nested = protected.scratch_path / "pytest-fixture" / "cache"
    nested.mkdir(parents=True)
    (nested / "payload").write_text("fixture")
    nested.chmod(0o500)
    nested.parent.chmod(0o500)
    subject.store.save(
        subject._with_state(protected, {"phase": "timed_out", "terminal": True})
    )
    GenericJobs(systemd, subject.store)
    assert not protected.scratch_path.exists()


def test_queued_job_recreates_aged_scratch_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SINNIXD_NVME_SCRATCH_ROOT", str(tmp_path / "nvme"))
    adapter = project(
        tmp_path / "project",
        (
            operation(
                "heavy",
                pool="bulk",
                estimate_memory_bytes=12 * 1024 * 1024 * 1024,
                scratch="nvme",
            ),
        ),
    )
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd)
    first = subject.start_declared(
        project=adapter,
        operation=adapter.operation("heavy"),
        correlation_id="one",
        parameters={},
    )
    queued = subject.start_declared(
        project=adapter,
        operation=adapter.operation("heavy"),
        correlation_id="two",
        principal="agent-control",
        parameters={},
    )
    queued_record = subject.store.load(queued["job_id"])
    assert queued["state"]["phase"] == "queued"
    assert queued_record.scratch_path is not None
    queued_record.scratch_path.rmdir()

    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
        "MemoryPeak": str(12 * 1024 * 1024 * 1024),
    }
    subject.get(first["job_id"])
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "active",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    launched = subject.get(queued["job_id"])

    assert launched["state"]["phase"] in {"submitted", "running"}
    assert queued_record.scratch_path.is_dir()
    command, environment = subject.store.declared_launch(queued_record.job_id)
    assert command[:2] == ("env", f"TMPDIR={queued_record.scratch_path}")
    assert "TMPDIR" not in environment
    assert "TMPDIR" not in systemd.started[-1]["environment"]


def test_exit_json_pytest_and_agent_result_parsers_are_contract_specific(
    tmp_path: Path,
) -> None:
    systemd = FakeSystemd(
        properties={
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "success",
            "ExecMainStatus": "0",
        }
    )
    subject = jobs(tmp_path, systemd)
    exit_job = subject.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    assert subject.result(exit_job["job_id"])["value"] == {
        "code": 0,
        "result": "success",
    }
    for kind in ("json", "pytest", "last-message"):
        started = subject.start(
            GenericJobSpec(
                kind="foreground-command",
                command=("fixture",),
                working_directory=str(tmp_path),
                environment={},
                result_kind=kind,
            )
        )
        record = subject.store.load(started["job_id"])
        assert record.result_path is not None
        record.result_path.write_bytes(
            b'{"receipt":"ok"}' if kind != "last-message" else b"agent result"
        )
        result = subject.result(started["job_id"])
        assert result["kind"] == kind
        if kind == "last-message":
            assert result["content"] == "agent result"
        else:
            assert result["value"] == {"receipt": "ok"}


def _lone_managed_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[GenericJobs, FakeSystemd, dict[str, object], dict[str, object], list[float]]:
    """One managed job, active, holding 6 GiB. Nothing else is contending."""
    pressure = {
        "memory_full_avg10": 0.0,
        "io_full_avg10": 0.0,
        "memory_total_bytes": 32 * 1024**3,
        "memory_available_bytes": 24 * 1024**3,
        "swap_total_bytes": 20 * 1024**3,
        "swap_free_bytes": 20 * 1024**3,
        "managed_memory_bytes": 0,
    }
    clock = [0.0]
    monkeypatch.setattr("sinnixd.jobs.time.monotonic", lambda: clock[0])
    systemd = FakeSystemd()
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        pressure_probe=lambda: pressure,
    )
    only = subject.start(agent_spec(("table:only",)))
    systemd.unit_properties[only["unit"]] = {
        "LoadState": "loaded",
        "ActiveState": "active",
        "Result": "success",
        "ExecMainStatus": "0",
        "InvocationID": "only",
        "MemoryCurrent": str(6 * 1024**3),
        "MemorySwapCurrent": "0",
        "MemoryPeak": str(6 * 1024**3),
    }
    return subject, systemd, only, pressure, clock


def test_sustained_io_stall_does_not_preempt_the_only_managed_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lone job's IO stall is its own work, not contention to shed.

    Cancelling it cannot relieve pressure it is itself producing; it only
    destroys the work. Observed on the polylogue harvest operation, whose quick
    gate drove io_full_avg10 to 22.2 and was then preempted as the largest --
    and only -- managed job, so no lane could publish.
    """
    subject, systemd, only, pressure, clock = _lone_managed_job(tmp_path, monkeypatch)

    pressure.update(io_full_avg10=22.2, managed_memory_bytes=6 * 1024**3)
    assert subject._relieve_active_pressure(pressure) is None
    clock[0] = 2.1
    assert subject._relieve_active_pressure(pressure) is None

    assert systemd.stopped == []
    assert subject.get(only["job_id"])["state"].get("phase") != "cancelled"


def test_swap_exhaustion_still_preempts_the_only_managed_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Host endangerment is the exception: a lone job is still a valid victim."""
    subject, systemd, only, pressure, clock = _lone_managed_job(tmp_path, monkeypatch)

    pressure.update(
        memory_full_avg10=MEMORY_FULL_PREEMPT_THRESHOLD,
        io_full_avg10=22.2,
        memory_available_bytes=1024**3,
        swap_free_bytes=1024**3,
        managed_memory_bytes=6 * 1024**3,
    )
    assert subject._relieve_active_pressure(pressure) is None
    clock[0] = 2.1
    assert subject._relieve_active_pressure(pressure) == only["job_id"]

    assert systemd.stopped == [only["unit"]]
    preempted = subject.get(only["job_id"])
    assert preempted["state"]["phase"] == "cancelled"
    assert "swap-exhaustion" in preempted["state"]["preemption"]["reason"]


def test_io_stall_never_preempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """IO stalls never cost work. Host IO PSI cannot attribute the stall to
    the managed plane (2026-09-01: four lane kills while user-slice IO
    measured megabytes against 41MB/s of device writes), and an IO-slow host
    is degraded, not endangered. Red if io-stall preemption returns."""
    pressure = {
        "memory_full_avg10": 0.0,
        "io_full_avg10": 0.0,
        "memory_total_bytes": 32 * 1024**3,
        "memory_available_bytes": 24 * 1024**3,
        "swap_total_bytes": 20 * 1024**3,
        "swap_free_bytes": 20 * 1024**3,
        "managed_memory_bytes": 0,
    }
    clock = [0.0]
    monkeypatch.setattr("sinnixd.jobs.time.monotonic", lambda: clock[0])
    systemd = FakeSystemd()
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        pressure_probe=lambda: pressure,
    )
    base = {
        "LoadState": "loaded",
        "ActiveState": "active",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    first = subject.start(agent_spec(("table:first",)))
    second = subject.start(agent_spec(("table:second",)))
    systemd.unit_properties[first["unit"]] = {
        **base,
        "InvocationID": "first",
        "MemoryCurrent": str(1024**3),
        "MemorySwapCurrent": "0",
        "MemoryPeak": str(1024**3),
    }
    systemd.unit_properties[second["unit"]] = {
        **base,
        "InvocationID": "second",
        "MemoryCurrent": str(5 * 1024**3),
        "MemorySwapCurrent": "0",
        "MemoryPeak": str(5 * 1024**3),
    }

    pressure.update(io_full_avg10=80.0, managed_memory_bytes=6 * 1024**3)
    for tick in (0.0, 10.0, 30.0, 60.0, 600.0):
        clock[0] = tick
        assert subject._relieve_active_pressure(pressure) is None
    assert systemd.stopped == []
    assert second["state"]["phase"] != "cancelled"


def test_memory_stall_keeps_the_short_grace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Memory endangers the host; it must not wait out the IO window."""
    pressure = {
        "memory_full_avg10": 0.0,
        "io_full_avg10": 0.0,
        "memory_total_bytes": 32 * 1024**3,
        "memory_available_bytes": 24 * 1024**3,
        "swap_total_bytes": 20 * 1024**3,
        "swap_free_bytes": 20 * 1024**3,
        "managed_memory_bytes": 0,
    }
    clock = [0.0]
    monkeypatch.setattr("sinnixd.jobs.time.monotonic", lambda: clock[0])
    systemd = FakeSystemd()
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        pressure_probe=lambda: pressure,
    )
    base = {
        "LoadState": "loaded",
        "ActiveState": "active",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    first = subject.start(agent_spec(("table:first",)))
    second = subject.start(agent_spec(("table:second",)))
    systemd.unit_properties[first["unit"]] = {
        **base,
        "InvocationID": "first",
        "MemoryCurrent": str(1024**3),
        "MemorySwapCurrent": "0",
        "MemoryPeak": str(1024**3),
    }
    systemd.unit_properties[second["unit"]] = {
        **base,
        "InvocationID": "second",
        "MemoryCurrent": str(5 * 1024**3),
        "MemorySwapCurrent": "0",
        "MemoryPeak": str(5 * 1024**3),
    }

    pressure.update(
        memory_full_avg10=MEMORY_FULL_PREEMPT_THRESHOLD,
        managed_memory_bytes=6 * 1024**3,
    )
    assert subject._relieve_active_pressure(pressure) is None
    clock[0] = 2.1
    assert subject._relieve_active_pressure(pressure) == second["job_id"]


def test_lane_and_harvest_fit_the_host_budget_together(tmp_path: Path) -> None:
    """A lane's peak reservation must leave room for the harvest that publishes it.

    Sized from the 2026-08-28 wave: a 31 GiB host with ~15 GiB available, a lane
    holding a 7 GiB reservation, and a 4.7 GiB harvest. A 25% reserve capped at
    8 GiB queues the harvest behind the lane, which is what stalls publication.
    Admission charges the just-launched lane its estimate until its footprint
    reaches the kernel's available figure; the reserve is 8% of the host.
    """
    gib = 1024 * 1024 * 1024
    adapter = project(
        tmp_path / "project",
        (
            operation(
                "harvest", pool="normal", estimate_memory_bytes=4700 * 1024 * 1024
            ),
        ),
    )
    systemd = FakeSystemd()
    pressure = {
        "memory_full_avg10": 0.0,
        "io_full_avg10": 0.0,
        "memory_total_bytes": 31 * gib,
        "memory_available_bytes": 15 * gib,
        "swap_total_bytes": 20 * gib,
        "swap_free_bytes": 20 * gib,
        "managed_memory_bytes": 3 * gib,
    }
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: pressure,
    )
    lane = GenericJobSpec(
        **{**agent_spec(("table:jobs",)).__dict__, "estimate_memory_bytes": 7 * gib}
    )
    running = subject.start(lane)
    assert running["state"]["phase"] == "submitted"

    harvest = subject.start_declared(
        project=adapter,
        operation=adapter.operation("harvest"),
        correlation_id="harvest",
        parameters={},
    )

    assert harvest["state"]["phase"] == "submitted"
    assert len(systemd.started) == 2


def test_superseding_operation_cancels_its_own_queued_jobs(tmp_path: Path) -> None:
    gib = 1024 * 1024 * 1024
    adapter = project(
        tmp_path / "project",
        (
            operation(
                "prebuild",
                pool="bulk",
                estimate_memory_bytes=24 * gib,
                supersede="queued",
            ),
        ),
    )
    systemd = FakeSystemd()
    pressure = {
        "memory_full_avg10": 0.0,
        "io_full_avg10": 0.0,
        "memory_total_bytes": 31 * gib,
        "memory_available_bytes": 8 * gib,
        "swap_total_bytes": 20 * gib,
        "swap_free_bytes": 20 * gib,
        "managed_memory_bytes": 0,
    }
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: pressure,
    )

    def start(correlation_id: str) -> dict[str, object]:
        return subject.start_declared(
            project=adapter,
            operation=adapter.operation("prebuild"),
            correlation_id=correlation_id,
            parameters={},
        )

    def move_tree(marker: str) -> None:
        (adapter.root / "tracked").write_text(marker + "\n")
        subprocess.run(["git", "-C", str(adapter.root), "add", "tracked"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(adapter.root),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.test",
                "commit",
                "--quiet",
                "-m",
                marker,
            ],
            check=True,
        )

    first = start("first")
    assert first["state"]["phase"] == "queued"

    move_tree("input moved")
    second = start("second")

    assert second["state"]["phase"] == "queued"
    assert second["job_id"] != first["job_id"]
    replaced = subject.get(str(first["job_id"]))
    assert replaced["state"]["phase"] == "cancelled"
    assert replaced["state"]["superseded"] is True


def test_terminal_observation_is_idempotent_and_records_no_estimate(
    tmp_path: Path,
) -> None:
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd)
    started = subject.start(agent_spec(("table:jobs",)))
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
        "MemoryPeak": str(6 * 1024**3),
    }

    first = subject.get(started["job_id"])
    repeated = subject.get(started["job_id"])

    assert first["state"]["phase"] == "succeeded"
    assert repeated["state"]["phase"] == "succeeded"
    assert "estimates" not in subject._admission_state()


def test_scheduler_survives_a_failing_pressure_sweep(tmp_path: Path) -> None:
    """A raising pressure sweep must not end the thread that owns the active set.

    A preemption whose ``systemctl stop`` times out raises out of the sweep;
    the thread that dies is the only one holding the active set, which orphans
    every running unit and wedges all later admission.

    Anti-vacuity: remove the try/except around the pressure sweep in
    ``run_admission_scheduler`` and the thread dies on the first raise, so the
    queued job is never admitted and ``scheduler.is_alive()`` is false.
    """
    failures = []
    armed = threading.Event()
    adapter = project(
        tmp_path / "project",
        (operation("light", pool="bulk", estimate_memory_bytes=1024),),
    )

    pressure = {"memory_full_avg60": MEMORY_FULL_BLOCK_THRESHOLD}

    def probe() -> dict[str, float]:
        if armed.is_set() and len(failures) < 3:
            failures.append("raised")
            raise SystemdJobTimeout("systemd command timed out")
        return dict(pressure)

    admitted = threading.Event()
    subject = GenericJobs(
        FakeSystemd(),
        GenericJobStore(tmp_path / "state"),
        pressure_probe=probe,
        before_admission_start=lambda _job_id: admitted.set(),
        admission_retry_seconds=0.001,
    )
    queued = subject.start_declared(
        project=adapter,
        operation=adapter.operation("light"),
        correlation_id="queued",
        parameters={},
    )
    assert queued["state"]["phase"] == "queued"

    armed.set()
    stop_event = threading.Event()
    scheduler = threading.Thread(
        target=subject.run_admission_scheduler, args=(stop_event,)
    )
    scheduler.start()
    try:
        # The sweep raises three times before the probe answers; the loop must
        # still be alive to admit the queued job once pressure clears.
        pressure["memory_full_avg60"] = 0.0
        assert admitted.wait(5)
    finally:
        stop_event.set()
        scheduler.join(2)

    assert not scheduler.is_alive()
    assert len(failures) == 3


def test_stop_does_not_wait_for_the_unit_to_finish_shutting_down() -> None:
    """Cancellation requests a stop; it never blocks on the unit's own shutdown.

    Anti-vacuity: drop ``--no-block`` and the assertion fails. A blocking stop
    runs until the agent unit exits, far past the shared command budget, and
    every cancellation then raises ``SystemdJobTimeout``.
    """
    recorded: list[Sequence[str]] = []

    class Recorder(UserSystemdJobs):
        @staticmethod
        def _run(args: Sequence[str], *, timeout_seconds: float = 0.0) -> str:
            recorded.append(list(args))
            return ""

    Recorder().stop("sinnixd-job-fixture.service")
    assert recorded == [
        ["systemctl", "--user", "--no-block", "stop", "sinnixd-job-fixture.service"]
    ]


def test_memory_blocked_head_of_line_reserves_its_claim(tmp_path: Path) -> None:
    """Younger small jobs cannot slip past a memory-blocked older job forever."""
    gib = 1024 * 1024 * 1024
    adapter = project(
        tmp_path / "project",
        (
            operation("seed", pool="bulk", estimate_memory_bytes=10 * gib),
            operation("large", pool="normal", estimate_memory_bytes=7 * gib),
            operation("small", pool="normal", estimate_memory_bytes=3 * gib),
        ),
    )
    systemd = FakeSystemd()
    pressure = {
        "memory_full_avg10": 0.0,
        "io_full_avg10": 0.0,
        "memory_total_bytes": 16 * gib,
        "memory_available_bytes": 16 * gib,
        "swap_total_bytes": 20 * gib,
        "swap_free_bytes": 20 * gib,
        "managed_memory_bytes": 0,
    }
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: pressure,
    )
    subject.start_declared(
        project=adapter,
        operation=adapter.operation("seed"),
        correlation_id="seed",
        parameters={},
    )
    blocked = subject.start_declared(
        project=adapter,
        operation=adapter.operation("large"),
        correlation_id="large",
        parameters={},
    )
    assert blocked["state"]["admission"]["blocked_by"] == ["host-memory"]
    younger = subject.start_declared(
        project=adapter,
        operation=adapter.operation("small"),
        correlation_id="small",
        parameters={},
    )
    # 10 (seed) + 3 (small) fits the raw budget, but the blocked 7GiB head
    # reserves its claim: the younger job queues instead of starving it.
    assert younger["state"]["phase"] == "queued"
    assert "host-memory" in younger["state"]["admission"]["blocked_by"]


def test_cancel_records_a_typed_reason(tmp_path: Path) -> None:
    gib = 1024 * 1024 * 1024
    adapter = project(
        tmp_path / "project",
        (operation("op", pool="bulk", estimate_memory_bytes=14 * gib),),
    )
    pressure = {
        "memory_full_avg10": 0.0,
        "io_full_avg10": 0.0,
        "memory_total_bytes": 32 * gib,
        "memory_available_bytes": 8 * gib,
        "swap_total_bytes": 8 * gib,
        "swap_free_bytes": 8 * gib,
        "managed_memory_bytes": 0,
    }
    subject = GenericJobs(
        FakeSystemd(),
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: pressure,
    )
    started = subject.start_declared(
        project=adapter,
        operation=adapter.operation("op"),
        correlation_id="why",
        parameters={},
    )
    assert started["state"]["phase"] == "queued"
    subject.cancel(started["job_id"], reason="pressure-preemption:memory-stall")
    record = subject.store.load(started["job_id"])
    assert record.state["cancellation"]["reason"] == "pressure-preemption:memory-stall"


def test_agent_fleet_admits_on_default_claims(tmp_path: Path) -> None:
    """Undeclared agent lanes claim the small pool default (lanes are
    API-bound; verification bursts are short and rarely coincide), so a real
    fleet admits on a host with ~12G available. Anti-vacuity: lanes that
    DECLARE a large estimate stop at the host budget."""

    def build(tmp: Path) -> GenericJobs:
        return GenericJobs(
            FakeSystemd(),
            GenericJobStore(tmp / "state"),
            wait_poll_seconds=0.001,
            pressure_probe=lambda: {
                "memory_full_avg10": 0.0,
                "io_full_avg10": 0.0,
                "memory_total_bytes": 32 * 1024**3,
                "memory_available_bytes": 12 * 1024**3,
                "swap_total_bytes": 20 * 1024**3,
                "swap_free_bytes": 10 * 1024**3,
                "managed_memory_bytes": 0,
            },
        )

    subject = build(tmp_path / "default")
    started = [
        subject.start(agent_spec((f"table:fleet-{index}",))) for index in range(10)
    ]
    running = [item for item in started if item["state"]["phase"] != "queued"]
    assert len(running) >= 8

    declared = build(tmp_path / "declared")
    heavy_started = []
    for index in range(10):
        spec = agent_spec((f"table:heavy-{index}",))
        spec = GenericJobSpec(**{**spec.__dict__, "estimate_memory_bytes": 4 * 1024**3})
        heavy_started.append(declared.start(spec))
    heavy_running = [
        item for item in heavy_started if item["state"]["phase"] != "queued"
    ]
    assert len(heavy_running) <= 3
