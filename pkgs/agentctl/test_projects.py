"""Descriptor loading: the fields agentctl reads, and the ones it refuses."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentctl.config import Config, load_config, resolve_project
from agentctl.projects import (
    ProjectCatalog,
    ProjectConfigError,
    ProjectEnvironmentError,
    load_project_adapter,
)
from conftest import write_project


def test_the_fixture_descriptor_loads_every_declared_field(project_root: Path) -> None:
    project = load_project_adapter(project_root)

    assert project.project_id == "fixture"
    assert project.environment.command == ("env",)
    assert project.workspace is not None
    assert project.workspace.default_base == "origin/master"
    assert project.workspace.agent_memory_max == "10G"
    assert project.workspace.verify == {
        "focused": "verify_quick",
        "candidate": "check",
        "corpus": "verify",
    }
    assert project.workspace.review == "agent"
    nightly = project.operation("nightly")
    assert nightly.schedule == "*-*-* 03:17:00"
    assert nightly.checkout == "default"
    assert nightly.pool == "bulk"
    verify = project.operation("verify")
    assert (verify.result, verify.timeout_seconds) == ("json", 120)
    assert verify.dependencies == ()
    # A descriptor that declares no scratch tier gets none.
    assert [operation.scratch for operation in project.operations] == ["none"] * 4
    assert [operation.name for operation in project.operations] == [
        "check",
        "nightly",
        "verify",
        "verify_quick",
    ]


@pytest.mark.parametrize(
    ("fragment", "message"),
    [
        ('[conflicts]\nexact_files = ["x"]\n', "unknown tables: conflicts"),
        ('[owner_adapters.a]\nnamespace = "a"\n', "unknown tables: owner_adapters"),
    ],
)
def test_a_table_agentctl_does_not_read_takes_the_project_out_of_service(
    tmp_path: Path, fragment: str, message: str
) -> None:
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(descriptor.read_text() + "\n" + fragment)
    with pytest.raises(ProjectConfigError, match=message):
        load_project_adapter(root)


@pytest.mark.parametrize(
    ("table", "key"),
    [
        ("environment", 'preflight = ["true"]'),
        ("environment", "preflight_timeout_seconds = 180"),
        ("workspace", 'provider = "git-worktree"'),
        ("workspace", 'identity_check = ["git", "diff"]'),
        ("workspace", "checkpoint_untracked = true"),
        ("workspace", 'verification_operations = ["check"]'),
    ],
)
def test_unknown_or_retired_fields_warn_and_load(
    tmp_path: Path, table: str, key: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Breaks if an unknown field takes the project out of service again: a
    descriptor written for a newer agentctl would stop every landing on the
    older one until the deploy finishes."""
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(f"[{table}]\n", f"[{table}]\n{key}\n")
    )
    project = load_project_adapter(root)
    assert project.project_id == "fixture"
    name = key.split(" =", 1)[0]
    assert f"[{table}] ignores unknown fields: {name}" in capsys.readouterr().err


def test_unknown_packet_and_operation_fields_warn_and_load(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        + "[packets.extra]\nx = 1\n"
        + '[operations.check.parameters.apply]\ntype = "bool"\nflag = "--apply"\n'
    )
    load_project_adapter(root)
    err = capsys.readouterr().err
    assert "[packets] ignores unknown fields: extra" in err
    assert "operation check ignores unknown fields: parameters" in err


@pytest.mark.parametrize(
    ("fragment", "message"),
    [
        (
            '[operations.bad]\ndescription = "x"\nexec = ["x"]\npool = "Nope"\n',
            "pool is invalid",
        ),
        (
            '[operations.bad]\ndescription = "x"\nexec = ["x"]\nresult = "last-message"\n',
            "result is invalid",
        ),
        (
            '[operations.bad]\ndescription = "x"\nexec = ["x"]\ntimeout_seconds = 99999\n',
            "timeout_seconds",
        ),
        ('[operations.bad]\ndescription = "x"\nexec = []\n', "non-empty list"),
        (
            '[operations.bad]\ndescription = "x"\nexec = ["x"]\nschedule = ""\n',
            "OnCalendar",
        ),
        (
            '[operations.bad]\ndescription = "x"\nexec = ["x"]\ncheckout = "lane"\n',
            "checkout is invalid",
        ),
        (
            '[operations.bad]\ndescription = "x"\nexec = ["x"]\ncache = "bad"\n',
            "cache is invalid",
        ),
        (
            '[operations.bad]\ndescription = "x"\nexec = ["x"]\nscratch = "ssd"\n',
            "scratch is invalid",
        ),
    ],
)
def test_malformed_operations_are_typed_refusals(
    tmp_path: Path, fragment: str, message: str
) -> None:
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(descriptor.read_text() + "\n" + fragment)
    with pytest.raises(ProjectConfigError, match=message):
        load_project_adapter(root)


def test_a_declared_scratch_tier_is_carried_by_the_operation(tmp_path: Path) -> None:
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        + '\n[operations.heavy]\ndescription = "x"\nexec = ["x"]\nscratch = "nvme"\n'
    )

    project = load_project_adapter(root)

    assert project.operation("heavy").scratch == "nvme"
    assert project.operation("heavy").catalog_row()["scratch"] == "nvme"
    assert project.operation("check").scratch == "none"


def test_a_malformed_agent_ceiling_is_a_typed_refusal(tmp_path: Path) -> None:
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'agent_memory_max = "10G"', 'agent_memory_max = "lots"'
        )
    )
    with pytest.raises(ProjectConfigError, match="agent_memory_max"):
        load_project_adapter(root)


def test_verification_operations_and_dependencies_are_validated(tmp_path: Path) -> None:
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'exec = ["fixture-verify"]\npool = "pytest"',
            'exec = ["fixture-verify"]\npool = "pytest"\ndependencies = ["missing"]',
        )
    )
    with pytest.raises(ProjectConfigError, match="undeclared.*missing"):
        load_project_adapter(root)

    descriptor.write_text(
        descriptor.read_text()
        .replace('dependencies = ["missing"]', 'dependencies = ["check"]')
        .replace(
            'exec = ["true"]\npool = "normal"',
            'exec = ["true"]\npool = "normal"\ndependencies = ["verify"]',
        )
    )
    with pytest.raises(ProjectConfigError, match="cycle"):
        load_project_adapter(root)


def test_verify_profiles_and_publish_policy_are_validated(
    project_root: Path, tmp_path: Path
) -> None:
    adapter = load_project_adapter(project_root)
    assert adapter.workspace is not None
    assert adapter.workspace.verify == {
        "focused": "verify_quick",
        "candidate": "check",
        "corpus": "verify",
    }
    assert adapter.workspace.publish == "master"
    assert adapter.workspace.base_branch == "master"

    descriptor = (project_root / ".agentctl" / "project.toml").read_text()
    hosted = descriptor.replace(
        'candidate = "check"', 'candidate = "hosted:verify"'
    ).replace('publish = "master"', 'publish = "pr"')
    hosted_root = write_project(tmp_path / "hosted")
    (hosted_root / ".agentctl" / "project.toml").write_text(hosted)
    loaded = load_project_adapter(hosted_root)
    assert loaded.workspace is not None
    assert loaded.workspace.verify["candidate"] == "hosted:verify"
    assert loaded.workspace.publish == "pr"

    for broken, fragment in (
        (
            descriptor.replace('candidate = "check"', 'candidate = "nowhere"'),
            "undeclared",
        ),
        (
            descriptor.replace('publish = "master"', 'publish = "email"'),
            "workspace.publish",
        ),
        (descriptor.replace("focused = ", "nightly = "), "workspace.verify"),
    ):
        broken_root = write_project(tmp_path / "broken")
        (broken_root / ".agentctl" / "project.toml").write_text(broken)
        with pytest.raises(ProjectConfigError, match=fragment):
            load_project_adapter(broken_root)


def test_default_agent_ceiling_is_per_lane(tmp_path: Path) -> None:
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace('agent_memory_max = "10G"\n', "")
    )

    assert load_project_adapter(root).workspace.agent_memory_max == "4G"


def test_a_required_variable_missing_at_launch_fails_loudly(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor = project_root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'inherit = ["PATH"]',
            'inherit = ["PATH", "FIXTURE_TOKEN"]\nrequire = ["FIXTURE_TOKEN"]',
        )
    )
    project = load_project_adapter(project_root)
    monkeypatch.delenv("FIXTURE_TOKEN", raising=False)

    with pytest.raises(ProjectEnvironmentError, match="FIXTURE_TOKEN"):
        project.environment.values()

    monkeypatch.setenv("FIXTURE_TOKEN", "t")
    values = project.environment.values()
    assert values["FIXTURE_TOKEN"] == "t"
    assert values["GIT_OPTIONAL_LOCKS"] == "0"


def test_a_tolerant_catalog_reports_a_broken_root_without_hiding_the_others(
    tmp_path: Path, project_root: Path
) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / ".agentctl").mkdir()
    (broken / ".agentctl" / "project.toml").write_text("schema = 2\n")

    catalog = ProjectCatalog([project_root, broken], tolerant=True)

    assert [row["id"] for row in catalog.list()] == ["fixture"]
    assert str(broken) in catalog.unavailable
    with pytest.raises(KeyError, match="out of service"):
        catalog.get("broken")
    with pytest.raises(ProjectConfigError):
        ProjectCatalog([project_root, broken])


def test_config_reads_the_host_file_and_resolves_projects_by_id_or_path(
    tmp_path: Path, project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    location = tmp_path / "agentctl.json"
    location.write_text(
        '{"project_roots": ["%s"], "agent_runner": "/r/run.sh", "event_spool": "/e/events.jsonl", "state_dir": "/s", "agentctl": "/bin/agentctl"}'
        % project_root
    )
    monkeypatch.setenv("AGENTCTL_CONFIG", str(location))

    config = load_config()

    assert config.project_roots == (project_root,)
    assert config.agent_runner == Path("/r/run.sh")
    assert config.jobs_dir == Path("/s/jobs")
    assert resolve_project(config, "fixture").root == project_root
    assert resolve_project(config, str(project_root)).root == project_root
    monkeypatch.chdir(project_root / "atlas")
    assert resolve_project(config, None).root == project_root


def test_an_absent_config_file_yields_the_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENTCTL_CONFIG", str(tmp_path / "missing.json"))
    config = load_config()
    assert isinstance(config, Config)
    assert config.project_roots == ()
    assert config.event_spool == Path("/realm/state/agentctl/events.jsonl")
    assert config.worker_contract.name == "worker-contract.md"


def test_packets_review_names_the_reviewer_agent_completely(tmp_path: Path) -> None:
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    base = descriptor.read_text()
    descriptor.write_text(
        base
        + '\n[packets.review]\nbackend = "claude"\nmodel = "claude-opus-5"\neffort = "high"\n'
    )
    assert load_project_adapter(root).packets.review == {
        "backend": "claude",
        "model": "claude-opus-5",
        "effort": "high",
    }
    descriptor.write_text(base + '\n[packets.review]\nbackend = "claude"\n')
    with pytest.raises(ProjectConfigError, match=r"\[packets.review\]"):
        load_project_adapter(root)
