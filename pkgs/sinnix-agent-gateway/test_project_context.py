from __future__ import annotations

import subprocess
from pathlib import Path

from sinnix_agent_gateway.beads import BeadsError
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.project_context import ProjectContextService
from sinnix_agent_gateway.projects import ProjectService


class FakeBeads:
    def __init__(self, result: dict[str, object] | Exception):
        self.result = result
        self.calls = []

    def query(
        self, *, project_ids: list[str], view: str, limit: int
    ) -> dict[str, object]:
        self.calls.append((project_ids, view, limit))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def project_service(tmp_path: Path, principal_name: str) -> ProjectService:
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init"], cwd=project, check=True, stdout=subprocess.DEVNULL)
    (project / "tracked.txt").write_text("initial\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=project, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Gateway Fixture",
            "-c",
            "user.email=gateway@example.invalid",
            "commit",
            "-m",
            "initial gateway fixture",
        ],
        cwd=project,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    (project / "tracked.txt").write_text("changed\n")
    (project / "untracked.txt").write_text("untracked\n")
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={
            "fixture": ProjectConfig(
                project_id="fixture", path=project, observer_read=True
            )
        },
    )
    return ProjectService(config, Principal.for_name(principal_name))


def test_project_summary_reports_structured_git_state(tmp_path: Path) -> None:
    projects = project_service(tmp_path, "observer")
    index = projects.config.projects["fixture"].path / ".git" / "index"
    before_index = index.read_bytes()

    result = projects.summary("fixture")

    assert result["project_id"] == "fixture"
    assert result["branch"]["head"] in {"master", "main"}
    assert result["changes"] == {
        "staged": 0,
        "unstaged": 1,
        "untracked": 1,
        "conflicted": 0,
    }
    assert result["latest_commit"]["subject"] == "initial gateway fixture"
    assert index.read_bytes() == before_index


def test_commit_range_uses_immutable_two_commit_relation(tmp_path: Path) -> None:
    projects = project_service(tmp_path, "operator")
    project = projects.config.projects["fixture"].path
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, check=True, capture_output=True, text=True
    ).stdout.strip()
    (project / "tracked.txt").write_text("committed change\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=project, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Gateway Fixture", "-c", "user.email=gateway@example.invalid", "commit", "-m", "second gateway fixture"],
        cwd=project, check=True, stdout=subprocess.DEVNULL,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, check=True, capture_output=True, text=True
    ).stdout.strip()

    result = projects.commit_range("fixture", "default", base, head)

    assert result["base_revision"] == base
    assert result["head_revision"] == head
    assert result["range"] == f"{base}..{head}"
    assert result["relation"] == "base_is_ancestor"
    assert result["merge_base"] == base
    assert "committed change" in result["diff"]
    assert result["truncated"] is False


def test_project_context_uses_native_ready_task_owner(tmp_path: Path) -> None:
    projects = project_service(tmp_path, "observer")
    beads = FakeBeads({"project_id": "fixture", "operation": "ready", "result": []})
    context = ProjectContextService(Principal.for_name("observer"), projects, beads)  # type: ignore[arg-type]

    result = context.context("fixture")

    assert result["tasks"]["availability"] == "available"
    assert beads.calls == [(["fixture"], "ready", 20)]
    assert "query:beads.query" in result["next_routes"]


def test_project_context_reports_unavailable_task_owner_without_hiding_git(
    tmp_path: Path,
) -> None:
    projects = project_service(tmp_path, "observer")
    context = ProjectContextService(
        Principal.for_name("observer"),
        projects,
        FakeBeads(BeadsError("no beads project found")),  # type: ignore[arg-type]
    )

    result = context.context("fixture")

    assert result["project"]["latest_commit"] is not None
    assert result["tasks"] == {
        "availability": "unavailable",
        "reason": "no beads project found",
        "next_route": "query:beads.query",
    }


def test_project_context_does_not_expose_ready_tasks_to_agent_control(
    tmp_path: Path,
) -> None:
    projects = project_service(tmp_path, "agent-control")
    beads = FakeBeads({"unexpected": True})
    context = ProjectContextService(Principal.for_name("agent-control"), projects, beads)  # type: ignore[arg-type]

    result = context.context("fixture")

    assert result["tasks"] == {
        "availability": "unavailable",
        "reason": "assigned Beads context requires a bound job reference",
    }
    assert beads.calls == []
