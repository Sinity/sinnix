from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.projects import ProjectError, ProjectService


def git(path: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(path), *arguments], check=True, capture_output=True)


def project_service(tmp_path: Path) -> tuple[ProjectService, Path, Path]:
    project = tmp_path / "project"
    linked = tmp_path / "linked"
    project.mkdir()
    git(project, "init", "--quiet")
    git(project, "config", "user.name", "Fixture")
    git(project, "config", "user.email", "fixture@example.invalid")
    (project / "README.md").write_text("fixture\n")
    git(project, "add", "README.md")
    git(project, "commit", "--quiet", "-m", "initial fixture")
    git(project, "worktree", "add", "--quiet", "-b", "fixture-linked", str(linked))
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={
            "fixture": ProjectConfig(
                project_id="fixture", path=project, observer_read=True
            )
        },
    )
    return ProjectService(config, Principal.for_name("observer")), project, linked


def test_project_checkouts_are_git_derived_and_explicit(tmp_path: Path) -> None:
    projects, project, linked = project_service(tmp_path)

    rows = projects.checkouts("fixture")["checkouts"]

    assert len(rows) == 2
    assert rows[0]["checkout_id"] == "default"
    assert rows[0]["path"] == str(project)
    assert rows[0]["head"] == git_stdout(project, "rev-parse", "HEAD")
    assert rows[0]["branch"] == "master"
    assert rows[0]["upstream"] is None
    assert len(rows[0]["dirty_sha256"]) == 64
    assert rows[0]["lifecycle"] == "configured-root"
    assert rows[1]["checkout_id"].startswith("worktree-")
    assert rows[1]["path"] == str(linked)
    assert rows[1]["branch"] == "fixture-linked"
    assert rows[1]["lifecycle"] == "linked-worktree"
    assert projects.checkout("fixture", rows[1]["checkout_id"])["checkout"] == rows[1]


def test_project_mutation_requires_an_explicit_checkout_when_ambiguous(
    tmp_path: Path,
) -> None:
    projects, _project, linked = project_service(tmp_path)
    operator = ProjectService(projects.config, Principal.for_name("operator"))
    linked_checkout = operator.checkouts("fixture")["checkouts"][1]["checkout_id"]

    with pytest.raises(ProjectError, match="checkout_id is required"):
        operator.write("fixture", "operator.txt", "not selected")

    operator.write("fixture", "operator.txt", "selected", linked_checkout)

    assert (linked / "operator.txt").read_text() == "selected"


def git_stdout(path: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()
