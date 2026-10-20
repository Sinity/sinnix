"""Descriptor loading: the fields agentctl reads, and the ones it refuses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentctl.config import Config, ConfigError, load_config, resolve_project
from agentctl.projects import (
    ProjectCatalog,
    ProjectConfigError,
    ProjectEnvironmentError,
    load_project_adapter,
)
from conftest import write_project


@pytest.mark.parametrize(
    "setting",
    [
        "Delegate=yes",
        "IOReadBandwidthMax=relative 20M",
        "IOWriteBandwidthMax=/realm 0",
        "IOReadBandwidthMax=/realm 20M\nUser=root",
    ],
)
def test_operation_refuses_nonlimiting_or_malformed_unit_properties(
    project_root: Path, setting: str
) -> None:
    descriptor = project_root / ".agentctl/project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'exec = ["fixture-verify"]',
            'exec = ["fixture-verify"]\nunit_properties=' + json.dumps([setting]),
        )
    )
    with pytest.raises(ProjectConfigError, match="unit_properties"):
        load_project_adapter(project_root)


def test_the_fixture_descriptor_loads_every_declared_field(project_root: Path) -> None:
    project = load_project_adapter(project_root)

    assert project.project_id == "fixture"
    assert project.environment.command == ("env",)
    assert project.workspace is not None
    assert project.workspace.default_base == "origin/master"
    assert project.workspace.retain_artifacts == ()
    nightly = project.operation("nightly")
    assert nightly.checkout == "default"
    assert nightly.pool == "bulk"
    verify = project.operation("verify")
    assert (verify.result, verify.timeout_seconds) == ("json", 120)
    # A descriptor that declares no scratch tier gets none.
    assert [operation.scratch for operation in project.operations] == ["none"] * 4
    assert [operation.name for operation in project.operations] == [
        "check",
        "nightly",
        "verify",
        "verify_quick",
    ]


def test_workspace_artifacts_must_be_relative(tmp_path: Path) -> None:
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            "[workspace]",
            '[workspace]\nretain_artifacts = [".cache/verify/*.json"]',
        )
    )
    assert load_project_adapter(root).workspace.retain_artifacts == (
        ".cache/verify/*.json",
    )

    descriptor.write_text(
        descriptor.read_text().replace(".cache/verify/*.json", "../escape")
    )
    with pytest.raises(ProjectConfigError, match="retain_artifacts must be relative"):
        load_project_adapter(root)


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


def test_unknown_operation_fields_warn_and_load(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        + '[operations.check.parameters.apply]\ntype = "bool"\nflag = "--apply"\n'
    )
    load_project_adapter(root)
    err = capsys.readouterr().err
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
        (
            '[operations.bad]\ndescription = "x"\nexec = ["x"]\narguments = "maybe"\n',
            "arguments is invalid",
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
    assert config.jobs_dir == Path("/s/jobs")
    assert resolve_project(config, "fixture").root == project_root
    assert resolve_project(config, str(project_root)).root == project_root
    nested = project_root / "nested"
    nested.mkdir()
    monkeypatch.chdir(nested)
    assert resolve_project(config, None).root == project_root


def test_an_absent_config_file_yields_the_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENTCTL_CONFIG", str(tmp_path / "missing.json"))
    config = load_config()
    assert isinstance(config, Config)
    assert config.project_roots == ()
    assert config.event_spool == Path("/realm/state/agentctl/events.jsonl")


def test_config_adds_agentctl_projects_from_private_runtime_catalog(
    tmp_path: Path, project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_root = write_project(tmp_path / "private-project")
    descriptor = private_root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace('id = "fixture"', 'id = "private_fixture"', 1)
    )
    catalog = tmp_path / "private-projects.json"
    catalog.write_text(
        json.dumps(
            {
                "projects": {
                    "private_fixture": {
                        "path": str(private_root),
                        "agentctl": True,
                    },
                    "task-only": {
                        "path": str(tmp_path / "task-only"),
                        "agentctl": False,
                    },
                },
                "links": {"/home/fixture/.local/share/private": "/realm/state/private"},
            }
        )
    )
    location = tmp_path / "agentctl.json"
    location.write_text(
        json.dumps(
            {
                "project_roots": [str(project_root)],
                "private_project_catalog": str(catalog),
            }
        )
    )
    monkeypatch.setenv("AGENTCTL_CONFIG", str(location))

    config = load_config()

    assert config.project_roots == (project_root, private_root)
    assert config.catalog(tolerant=False).get("private_fixture").root == private_root


def test_config_rejects_duplicate_private_project_roots(
    tmp_path: Path, project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = tmp_path / "private-projects.json"
    catalog.write_text(
        json.dumps(
            {"projects": {"duplicate": {"path": str(project_root), "agentctl": True}}}
        )
    )
    location = tmp_path / "agentctl.json"
    location.write_text(
        json.dumps(
            {
                "project_roots": [str(project_root)],
                "private_project_catalog": str(catalog),
            }
        )
    )
    monkeypatch.setenv("AGENTCTL_CONFIG", str(location))

    with pytest.raises(ConfigError, match="must be unique"):
        load_config()


# ----------------------------------------------- checkout and admission keys


def test_an_operation_checkout_is_any_or_default(tmp_path: Path) -> None:
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    base = descriptor.read_text()
    descriptor.write_text(
        base
        + '\n[operations.corpus]\ndescription = "Corpus"\nexec = ["c"]\n'
        + 'checkout = "candidate"\n'
    )
    with pytest.raises(ProjectConfigError, match="checkout is invalid"):
        load_project_adapter(root)


def test_an_operation_may_declare_its_admission_envelope(tmp_path: Path) -> None:
    """The measured side already exists on every sizing receipt; without this
    key there is no declared number to compare it against, and a workload can
    only mirror a pool ceiling by hand. Breaks if `admission` stops being
    parsed: the declaration is dropped with a warning and the catalog says
    nothing about what the operation expects."""
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    base = descriptor.read_text()
    descriptor.write_text(
        base
        + '\n[operations.corpus]\ndescription = "Corpus"\nexec = ["c"]\n'
        + "admission = { memory_mib = 12288 }\n"
    )

    operation = load_project_adapter(root).operation("corpus")

    assert operation.admission is not None
    assert operation.admission.memory_mib == 12288
    assert operation.catalog_row()["admission"] == {"memory_mib": 12288}


@pytest.mark.parametrize(
    "value",
    ["0", "-1", "65537", '"12288"', "12288.5", "true"],
)
def test_an_unusable_admission_envelope_is_refused(tmp_path: Path, value: str) -> None:
    """Breaks if the bound is dropped: a typo becomes a declaration nothing
    can satisfy, and the number a receipt compares against is nonsense."""
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        + '\n[operations.corpus]\ndescription = "Corpus"\nexec = ["c"]\n'
        + f"admission = {{ memory_mib = {value} }}\n"
    )
    with pytest.raises(ProjectConfigError, match="admission.memory_mib"):
        load_project_adapter(root)


def test_every_existing_declaration_keeps_working_without_the_new_keys(
    project_root: Path,
) -> None:
    """The fixture descriptor declares neither key. Breaks if either becomes
    required, or if the default stops being today's behaviour."""
    project = load_project_adapter(project_root)

    assert project.operation("check").checkout == "any"
    assert project.operation("check").admission is None
    assert project.operation("nightly").checkout == "default"
    assert project.operation("check").catalog_row()["admission"] is None


def test_nix_develop_cache_inputs_route_jobs_through_the_cached_realization(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: drop the cache_inputs branch in command_for and the job
    argv falls back to the declared `nix develop` command."""
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'kind = "plain"\ncommand = ["env"]',
            'kind = "nix-develop"\ncommand = ["nix", "develop", "--command"]\n'
            'cache_inputs = ["flake.nix", "flake.lock", "nix"]',
        )
    )

    project = load_project_adapter(root)

    assert project.environment.command_for(("pytest", "-q")) == (
        "agentctl-devenv",
        "--input=flake.nix",
        "--input=flake.lock",
        "--input=nix",
        "--",
        "pytest",
        "-q",
    )
    assert project.environment.catalog_row()["cache_inputs"] == [
        "flake.nix",
        "flake.lock",
        "nix",
    ]


@pytest.mark.parametrize(
    ("replacement", "match"),
    [
        (
            'kind = "plain"\ncommand = ["env"]\ncache_inputs = ["flake.nix"]',
            "only to kind",
        ),
        (
            'kind = "nix-develop"\ncommand = ["env"]\ncache_inputs = ["../flake.nix"]',
            "repository-relative",
        ),
    ],
)
def test_cache_inputs_are_validated(
    tmp_path: Path, replacement: str, match: str
) -> None:
    root = write_project(tmp_path / "p")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace('kind = "plain"\ncommand = ["env"]', replacement)
    )
    with pytest.raises(ProjectConfigError, match=match):
        load_project_adapter(root)


@pytest.mark.parametrize("value", [[], {"FIXTURE_ROOT": 42}])
def test_host_environment_rejects_malformed_values(
    tmp_path: Path, value: object
) -> None:
    import json

    location = tmp_path / "agentctl.json"
    location.write_text(json.dumps({"inherited_environment": value}))
    with pytest.raises(ConfigError, match="inherited_environment"):
        load_config(location)


def test_host_environment_is_loaded_without_requiring_a_caller_value(
    tmp_path: Path,
) -> None:
    import json

    location = tmp_path / "agentctl.json"
    location.write_text(
        json.dumps({"inherited_environment": {"FIXTURE_ROOT": "/current"}})
    )
    assert load_config(location).inherited_environment == {"FIXTURE_ROOT": "/current"}


def test_retired_reviewer_policy_cannot_disable_native_operations(project_root, capsys):
    descriptor = project_root / ".agentctl/project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            "[workspace]\n",
            "[workspace]\nreview = [123]\nverify = false\npublish = 42\nagent_memory_max = false\n",
        )
    )
    project = load_project_adapter(project_root)
    assert project.operation("check").command == ("true",)
    assert "ignores unknown fields" in capsys.readouterr().err


def test_retired_packet_table_is_an_explicit_unknown_table(project_root):
    descriptor = project_root / ".agentctl/project.toml"
    descriptor.write_text(descriptor.read_text() + "\n[packets]\nreview = false\n")
    with pytest.raises(ProjectConfigError, match="unknown tables: packets"):
        load_project_adapter(project_root)
