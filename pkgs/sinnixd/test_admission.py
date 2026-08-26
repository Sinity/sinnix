from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from sinnixd.jobs import (
    AdmissionConflictError,
    GenericJobs,
    GenericJobSpec,
    GenericJobStore,
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
        return dict(self.properties)

    def stop(self, unit: str) -> None:
        self.stopped.append(unit)
        self.properties = {
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "signal",
            "ExecMainStatus": "15",
            "InvocationID": "fixture",
        }


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
        pressure_probe=lambda: {"memory_full_avg10": pressure},
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
        == 18 * 1024 * 1024 * 1024
    )
    assert [entry["command"] for entry in systemd.started] == [("env", "oversized")]


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


def test_dependencies_exclusive_keys_learned_peaks_and_pressure_gate(
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
    subject = jobs(tmp_path, systemd, pressure=0.5)

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
        "MemoryPeak": str(777 * 1024 * 1024),
    }
    subject.get(primary["job_id"])
    repeated = subject.start_declared(
        project=adapter,
        operation=adapter.operation("check"),
        correlation_id="again",
        parameters={},
    )
    assert repeated["state"]["admission"]["estimate_memory_bytes"] == 777 * 1024 * 1024


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
    subject.cancel(cancelled["job_id"])
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
