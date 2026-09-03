from __future__ import annotations

import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from sinnixd.jobs import (
    IO_FULL_BLOCK_THRESHOLD,
    AdmissionConflictError,
    GenericJobs,
    GenericJobSpec,
    GenericJobStore,
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
    defaults = {"pool": "normal", "result": "exit"}
    defaults.update(kwargs)
    return ProjectOperation(name=name, description=name, command=(name,), **defaults)


def jobs(tmp_path: Path, systemd: FakeSystemd, pressure: float = 0.0) -> GenericJobs:
    return GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: {"io_full_avg60": pressure},
    )


def agent_spec(keys: tuple[str, ...], *, pool: str = "agent") -> GenericJobSpec:
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
        pool=pool,
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
        "exclusive_keys": ["fixture:store"],
        "created_at": persisted["claims"][holder["job_id"]]["created_at"],
        "project_id": "fixture",
        "operation": "hold",
    }
    ledger = subject.admission_ledger()
    assert ledger["claims"][holder["job_id"]]["exclusive_keys"] == ["fixture:store"]
    assert ledger["queue"][0]["job_id"] == queued["job_id"]
    assert ledger["queue"][0]["blocked_by"] == ["exclusive-key"]
    assert ledger["queue"][0]["arithmetic"]["pool_workers"] == {
        "occupied": 1,
        "limit": 5,
    }


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
scratch = "nvme"
estimate_memory_bytes = 1048576
""")
    check = load_project_adapter(root).operation("check")
    assert check.dependencies == ("prepare",)
    assert check.exclusive_keys == ("fixture:store",)
    assert check.scratch == "nvme"


def test_a_descriptor_declaring_retired_memory_fields_still_loads(
    tmp_path: Path,
) -> None:
    """The daemon stopped reading estimate_memory_bytes.

    A descriptor written for the older daemon must keep working: that key
    is ignored, not rejected. Anti-vacuity: rejecting it takes the whole
    project out of service, which is what the previous key-set check did.
    """
    root = tmp_path / "retired"
    root.mkdir()
    (root / "marker").touch()
    (root / ".agentctl").mkdir()
    (root / ".agentctl" / "project.toml").write_text("""
schema = 1
[project]
id = "fixture"
display_name = "Fixture"
root_markers = ["marker"]
[environment]
kind = "fixture"
command = ["env"]
[operations.serve]
description = "serve"
exec = ["serve"]
pool = "bulk"
result = "exit"
estimate_memory_bytes = 12884901888
""")

    serve = load_project_adapter(root).operation("serve")

    assert not hasattr(serve, "estimate_memory_bytes")


def test_admission_counts_workers_and_never_meters_memory(tmp_path: Path) -> None:
    """Concurrency is the only bound admission applies.

    The slice hierarchy owns memory: sinnixd.slice carries MemoryHigh for the
    whole job plane. Anti-vacuity: reintroducing any byte arithmetic would
    hold the sixth normal job for a reason other than "pool-workers", and
    would put a memory term back in the ledger.
    """
    adapter = project(
        tmp_path / "project",
        tuple(operation(f"job{index}") for index in range(6)),
    )
    subject = GenericJobs(
        FakeSystemd(),
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        # A host with almost nothing free and heavy swap use: none of it
        # reaches admission any more.
        pressure_probe=lambda: {
            "memory_available_bytes": 64 * 1024 * 1024,
            "memory_full_avg10": 90.0,
            "memory_full_avg60": 90.0,
            "swap_total_bytes": 8 * 1024**3,
            "swap_free_bytes": 1024,
        },
    )

    started = [
        subject.start_declared(
            project=adapter,
            operation=adapter.operation(f"job{index}"),
            correlation_id=f"job{index}",
            parameters={},
        )
        for index in range(6)
    ]

    assert [job["state"]["phase"] for job in started[:5]] == ["submitted"] * 5
    assert started[5]["state"]["phase"] == "queued"
    assert started[5]["state"]["admission"]["blocked_by"] == ["pool-workers"]
    ledger = subject.admission_ledger()
    assert set(ledger["pools"]["normal"]) == {"workers", "holders"}
    assert set(ledger["queue"][0]["arithmetic"]) == {"pool_workers", "exclusive_keys"}


def test_mixed_workload_injects_light_workers_and_queues_bulk(tmp_path: Path) -> None:
    adapter = project(
        tmp_path / "project",
        (
            operation("heavy", pool="bulk"),
            operation("light", pool="interactive"),
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


def test_unchanged_admission_block_does_not_rewrite_job_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = project(
        tmp_path / "project",
        (operation("heavy", pool="bulk"),),
    )
    pressure = {
        "io_full_avg60": IO_FULL_BLOCK_THRESHOLD,
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

    subject._admit_locked()

    assert writes == []


def test_scheduler_admits_queued_work_after_pressure_clears(tmp_path: Path) -> None:
    adapter = project(
        tmp_path / "project",
        (operation("heavy", pool="bulk"),),
    )
    pressure = {
        "io_full_avg60": IO_FULL_BLOCK_THRESHOLD,
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
        pressure["io_full_avg60"] = 0.0
        assert admitted.wait(2)
    finally:
        stop_event.set()
        scheduler.join(1)

    assert not scheduler.is_alive()
    assert len(systemd.started) == 1


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
        (operation("heavy", pool="bulk"),),
    )
    probes = 0

    def pressure_probe() -> dict[str, float]:
        nonlocal probes
        probes += 1
        return {
            "io_full_avg60": IO_FULL_BLOCK_THRESHOLD,
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


def test_dependencies_exclusive_keys_defaults_and_pressure_gate(
    tmp_path: Path,
) -> None:
    adapter = project(
        tmp_path / "project",
        (
            operation("prepare"),
            operation(
                "check",
                dependencies=("prepare",),
                exclusive_keys=("fixture:store",),
            ),
            operation("other", exclusive_keys=("fixture:store",)),
            operation("heavy", pool="bulk"),
            operation("interactive", pool="interactive"),
        ),
    )
    systemd = FakeSystemd()
    subject = jobs(tmp_path, systemd, pressure=IO_FULL_BLOCK_THRESHOLD)

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


def test_superseding_operation_cancels_its_own_queued_jobs(tmp_path: Path) -> None:
    adapter = project(
        tmp_path / "project",
        (
            operation(
                "prebuild",
                pool="bulk",
                supersede="queued",
            ),
        ),
    )
    systemd = FakeSystemd()
    subject = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: {"io_full_avg60": IO_FULL_BLOCK_THRESHOLD},
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


def test_terminal_observation_is_idempotent(
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


def test_cancel_records_a_typed_reason(tmp_path: Path) -> None:
    adapter = project(
        tmp_path / "project",
        (operation("op", pool="bulk"),),
    )
    subject = GenericJobs(
        FakeSystemd(),
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: {"io_full_avg60": IO_FULL_BLOCK_THRESHOLD},
    )
    started = subject.start_declared(
        project=adapter,
        operation=adapter.operation("op"),
        correlation_id="why",
        parameters={},
    )
    assert started["state"]["phase"] == "queued"
    subject.cancel(started["job_id"], reason="operator-request")
    record = subject.store.load(started["job_id"])
    assert record.state["cancellation"]["reason"] == "operator-request"


def test_sustained_io_stall_blocks_new_admissions(tmp_path: Path) -> None:
    """Anti-vacuity: IO was ignored entirely; a sustained stall admitted
    more disk-bound work into a saturated disk."""
    adapter = project(tmp_path / "project", (operation("first"), operation("second")))
    subject = GenericJobs(
        FakeSystemd(),
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: {
            "memory_full_avg10": 0.0,
            "io_full_avg10": 80.0,
            "io_full_avg60": IO_FULL_BLOCK_THRESHOLD + 5,
        },
    )
    first = subject.start_declared(
        project=adapter,
        operation=adapter.operation("first"),
        correlation_id="first",
        parameters={},
    )
    assert first["state"]["phase"] == "queued"
