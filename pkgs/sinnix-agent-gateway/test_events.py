from __future__ import annotations

from pathlib import Path
import json

import pytest

from sinnix_agent_gateway.audit import AuditService
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.events import MAX_EVENT_PROJECTS, EventCursorError, NormalizedEventService


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
        cursor_key=b"e" * 32,
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
        events.read(limit=2, project_ids=["fixture"], cursor=events.cursor.encode({"audit_sequence": 0, "runtime_offset": 0, "owner_revisions": {}, "job_revision": None}, ["other"]))


def test_event_cursor_secret_is_private_principal_bound_and_bounded(tmp_path: Path) -> None:
    events, _projects, _beads, _audit = service(tmp_path)
    cursor = events.read(limit=2)["next_cursor"]
    other = NormalizedEventService(
        principal="operator",
        cursor_key=b"e" * 32,
        projects=events.projects,  # type: ignore[arg-type]
        beads=events.beads,  # type: ignore[arg-type]
        audit=events.audit,
        transitions_path=events.transitions_path,
    )
    with pytest.raises(EventCursorError, match="authentication|scope"):
        other.read(limit=2, cursor=cursor)
    rotated = NormalizedEventService(
        principal="observer",
        cursor_key=b"r" * 32,
        projects=events.projects,  # type: ignore[arg-type]
        beads=events.beads,  # type: ignore[arg-type]
        audit=events.audit,
        transitions_path=events.transitions_path,
    )
    with pytest.raises(EventCursorError, match="authentication"):
        rotated.read(limit=2, cursor=cursor)
    with pytest.raises(EventCursorError, match="too large"):
        events.read(limit=2, cursor="x" * 4_097)


def test_event_scope_bound_matches_cursor_capacity(tmp_path: Path) -> None:
    project_ids = [f"project-{index:02d}" for index in range(MAX_EVENT_PROJECTS + 1)]
    projects = FakeProjects(tmp_path / "project")
    projects.config.projects = {
        project_id: ProjectConfig(project_id, tmp_path / project_id)
        for project_id in project_ids
    }
    beads = FakeBeads()
    config = GatewayConfig(state_dir=tmp_path / "state", projects=projects.config.projects)
    audit = AuditService(config, Principal.for_name("observer"))
    events = NormalizedEventService(
        principal="observer",
        cursor_key=b"e" * 32,
        projects=projects,  # type: ignore[arg-type]
        beads=beads,  # type: ignore[arg-type]
        audit=audit,
        transitions_path=tmp_path / "missing.jsonl",
    )

    page = events.read(limit=1_000, project_ids=project_ids[:MAX_EVENT_PROJECTS])
    assert len(page["next_cursor"].encode()) <= 4_096
    events.read(
        limit=1_000,
        project_ids=project_ids[:MAX_EVENT_PROJECTS],
        cursor=page["next_cursor"],
    )
    with pytest.raises(ValueError, match="1-16 projects"):
        events.read(limit=1_000, project_ids=project_ids)


def test_event_cursor_state_and_runtime_continuation_preserve_rows(tmp_path: Path) -> None:
    events, _projects, _beads, _audit = service(tmp_path)
    events.transitions_path.write_text("".join(f'{{"schema":"sinnix-health-transition-v1","event_id":"row-{i}","data":"{i}"}}\n' for i in range(4)))
    seen: list[str] = []
    cursor = None
    for _ in range(8):
        page = events.read(limit=1, cursor=cursor)
        seen.extend(row["event_id"] for row in page["events"] if row["event_id"].startswith("row-"))
        cursor = page["next_cursor"]
        assert len(cursor.encode()) <= 4_096
        if not page["truncated"]:
            break
    assert seen == ["row-0", "row-1", "row-2", "row-3"]
    assert len(seen) == len(set(seen))


def test_event_cursor_state_is_bounded_independently_of_job_population(tmp_path: Path) -> None:
    events, _projects, _beads, _audit = service(tmp_path)
    jobs = [{"job_id": f"job-{index}", "state": {"phase": "running"}} for index in range(10_000)]
    events.jobs = lambda _limit, _cursor: {"jobs": jobs, "snapshot": {"ordering": "created_at_desc_job_id_desc", "ceiling": ["", ""]}}

    response = events.read(limit=1_000)
    assert len(response["next_cursor"].encode()) <= 4_096
    job_events = [row for row in response["events"] if row["kind"] == "job_state"]
    assert len(job_events) == 1
    assert job_events[0]["data"]["truncated"] is True


def test_oversized_runtime_row_is_compacted_without_advancing_past_next_row(tmp_path: Path) -> None:
    events, _projects, _beads, _audit = service(tmp_path)
    events.transitions_path.write_text(
        json.dumps({"schema": "sinnix-health-transition-v1", "event_id": "huge", "data": "x" * 1_100_000}) + "\n"
        + json.dumps({"schema": "sinnix-health-transition-v1", "event_id": "after"}) + "\n"
    )
    cursor = None
    runtime = None
    first = None
    for _ in range(10):
        first = events.read(limit=1, cursor=cursor)
        cursor = first["next_cursor"]
        runtime = next((row for row in first["events"] if row["data"].get("truncated") is True), None)
        if runtime is not None:
            break
    assert runtime is not None
    assert runtime["data"]["truncated"] is True
    second = events.read(limit=1, cursor=cursor)
    assert [row["event_id"] for row in second["events"] if row["event_id"] == "after"] == ["after"]
