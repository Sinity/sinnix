from __future__ import annotations

from pathlib import Path

import pytest

from sinnix_agent_gateway.audit import AuditService
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.events import EventCursorError, NormalizedEventService


class FakeProjects:
    def __init__(self, project: Path):
        self.config = type("Config", (), {"projects": {"fixture": ProjectConfig("fixture", project)}})()
        self.revision = "git-a"

    def summary(self, project_id: str) -> dict[str, object]:
        return {"project_id": project_id, "head": self.revision}


class FakeBeads:
    def __init__(self) -> None:
        self.revision = "beads-a"

    def task_authority_status(self, project_id: str) -> dict[str, object]:
        return {"project_id": project_id, "revision": self.revision}


def service(tmp_path: Path) -> tuple[NormalizedEventService, FakeProjects, FakeBeads, AuditService]:
    projects = FakeProjects(tmp_path / "project")
    beads = FakeBeads()
    config = GatewayConfig(state_dir=tmp_path / "state", projects={"fixture": projects.config.projects["fixture"]})
    audit = AuditService(config, Principal.for_name("observer"))
    transitions = tmp_path / "transitions.jsonl"
    transitions.write_text('{"schema":"sinnix-health-transition-v1","event_id":"transition-1"}\n')
    return NormalizedEventService(
        principal="observer",
        state_dir=config.state_dir,
        projects=projects,  # type: ignore[arg-type]
        beads=beads,  # type: ignore[arg-type]
        audit=audit,
        transitions_path=transitions,
    ), projects, beads, audit


def test_events_normalize_owner_revisions_without_fabricating_exact_events(tmp_path: Path) -> None:
    events, projects, beads, audit = service(tmp_path)
    audit.append("fixture.read", "ok", {"target_refs": ["sinnix://projects/fixture"]})

    first = events.read(limit=20)
    assert {row["kind"] for row in first["events"]} >= {"gateway_receipt", "git_revision", "owner_revision", "runtime_transition"}
    assert all(row["exact"] is True for row in first["events"] if row["kind"] in {"gateway_receipt", "runtime_transition"})
    assert all(row["exact"] is False for row in first["events"] if row["kind"] in {"git_revision", "owner_revision"})
    assert all("ref" not in row for row in first["events"] if row["kind"] == "runtime_transition")

    second = events.read(limit=20, cursor=first["next_cursor"])
    assert not [row for row in second["events"] if row["kind"] in {"git_revision", "owner_revision"}]
    projects.revision = "git-b"
    beads.revision = "beads-b"
    third = events.read(limit=20, cursor=second["next_cursor"])
    assert {row["kind"] for row in third["events"]} >= {"git_revision", "owner_revision"}


def test_event_cursor_is_opaque_tamper_and_scope_bound(tmp_path: Path) -> None:
    events, _projects, _beads, _audit = service(tmp_path)
    cursor = events.read(limit=2)["next_cursor"]
    altered = cursor[:-1] + ("0" if cursor[-1] != "0" else "1")
    with pytest.raises(EventCursorError, match="authentication"):
        events.read(limit=2, cursor=altered)
    with pytest.raises(EventCursorError, match="scope"):
        events.read(limit=2, cursor=events.cursor.encode({"audit_sequence": 0}, ["other"]))
