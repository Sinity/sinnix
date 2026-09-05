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
    assert project.workspace.verification_operations == ("verify_quick",)
    nightly = project.operation("nightly")
    assert nightly.schedule == "*-*-* 03:17:00"
    assert nightly.checkout == "default"
    assert nightly.pool == "bulk"
    verify = project.operation("verify")
    assert (verify.result, verify.timeout_seconds) == ("json", 120)
    assert verify.dependencies == ()
    assert [operation.name for operation in project.operations] == [
        "check",
        "nightly",
        "verify",
        "verify_quick",
    ]


def test_retired_tables_are_ignored_but_retired_operation_fields_refuse(
    tmp_path: Path,
) -> None:
    """Inert tables must not take a project out of service; an operation
    field agentctl cannot honour must, loudly."""
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        + '\n[conflicts]\nexact_files = ["x"]\n\n[owner_adapters.a]\nnamespace = "a"\n'
    )
    assert load_project_adapter(root).project_id == "fixture"

    descriptor.write_text(
        descriptor.read_text()
        + '\n[operations.check.parameters.apply]\ntype = "bool"\nflag = "--apply"\n'
    )
    with pytest.raises(ProjectConfigError, match="unknown fields: parameters"):
        load_project_adapter(root)


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
        descriptor.read_text()
        .replace(
            'verification_operations = ["verify_quick"]',
            'verification_operations = ["verify_quick", "check"]',
        )
        .replace(
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
    assert project.environment.values()["FIXTURE_TOKEN"] == "t"


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
