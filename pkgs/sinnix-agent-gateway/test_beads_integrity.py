"""Owner-backed Beads metadata, revision, and mutation-certainty contracts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from sinnix_agent_gateway.beads import BeadsError
from test_beads import beads_service, commands


def test_metadata_merge_preserves_json_types_and_unrelated_keys(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)
    submitted = {
        "array": ["a", 2],
        "object": {"nested": True},
        "integer": 7,
        "float": 1.25,
        "boolean": False,
        "null": None,
        "string": "text",
        "literal_true": "true",
        "literal_null": "null",
        "literal_number": "123",
        "literal_array": "[1,2]",
    }

    beads.change(
        "fixture",
        "update",
        {"id": "fixture-1", "patch": {"metadata": {"set": submitted}}},
    )

    metadata = beads.get("fixture", "fixture-1")["fields"]["metadata"]
    assert metadata == {"unrelated": "kept", **submitted}
    update = next(command for command in commands(log) if "update" in command)
    assert "--metadata" in update and "--set-metadata" not in update
    assert json.loads(update[update.index("--metadata") + 1]) == submitted


def test_metadata_rejects_non_json_values_before_write(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)

    with pytest.raises(BeadsError, match="not JSON serializable"):
        beads.change(
            "fixture",
            "update",
            {
                "id": "fixture-1",
                "patch": {"metadata": {"set": {"bad": float("nan")}}},
            },
        )

    assert not any("update" in command for command in commands(log))


@pytest.mark.parametrize(
    ("operation", "parameters"),
    [
        ("update", {"id": "fixture-1", "patch": {"set": {"title": "changed"}}}),
        ("update", {"id": "fixture-1", "patch": {"notes": {"text": "changed"}}}),
        ("update", {"id": "fixture-1", "patch": {"set": {"acceptance": "changed"}}}),
        ("dependency.add", {"id": "fixture-1", "depends_on": "fixture-2"}),
        ("memory.remember", {"id": "fixture-1", "key": "fact", "text": "changed"}),
    ],
)
def test_owner_revision_invalidates_preview_without_status_count_changes(
    tmp_path: Path, operation: str, parameters: dict[str, object]
) -> None:
    beads, log = beads_service(tmp_path)
    preview = beads.change(
        "fixture",
        "update",
        {"id": "fixture-1", "patch": {"set": {"title": "next"}}},
        mode="preview",
    )
    beads.change("fixture", operation, parameters)

    with pytest.raises(BeadsError, match="stale"):
        beads.change(
            "fixture",
            "update",
            {"id": "fixture-1", "patch": {"set": {"title": "next"}}},
            preview_digest=preview["preview_digest"],
        )
    status = subprocess.run(
        [str(tmp_path / "bd"), "--json", "status"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(status.stdout)["summary"]["total_issues"] == 2


def test_owner_revision_tracks_successive_writes_to_one_dirty_table(
    tmp_path: Path,
) -> None:
    beads, _ = beads_service(tmp_path)

    initial = beads.task_authority_status("fixture")["revision"]
    beads.change(
        "fixture", "update", {"id": "fixture-1", "patch": {"set": {"title": "one"}}}
    )
    first = beads.task_authority_status("fixture")["revision"]
    first_dirty = subprocess.run(
        [
            str(tmp_path / "bd"),
            "--json",
            "sql",
            "SELECT table_name, staged, status FROM dolt_status ORDER BY table_name",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    beads.change(
        "fixture", "update", {"id": "fixture-1", "patch": {"set": {"title": "two"}}}
    )
    second = beads.task_authority_status("fixture")["revision"]
    second_dirty = subprocess.run(
        [
            str(tmp_path / "bd"),
            "--json",
            "sql",
            "SELECT table_name, staged, status FROM dolt_status ORDER BY table_name",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert (
        json.loads(first_dirty.stdout)
        == json.loads(second_dirty.stdout)
        == [{"table_name": "issues", "staged": False, "status": "modified"}]
    )
    assert len({initial, first, second}) == 3


def test_etag_is_independent_of_owner_projection(tmp_path: Path) -> None:
    beads, _ = beads_service(tmp_path)
    revision = beads.task_authority_status("fixture")["revision"]
    summary = beads._normalize("fixture", {"id": "fixture-1", "title": "one"}, revision)
    expanded = beads._normalize(
        "fixture",
        {"id": "fixture-1", "title": "one", "comment_count": 3, "dependencies": []},
        revision,
    )

    assert summary["etag"] == expanded["etag"]


def test_post_write_status_failure_remains_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    beads, log = beads_service(tmp_path)
    original = beads.task_authority_status
    calls = 0

    def status(project_id: str):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise BeadsError("injected post-write status failure", "deadline")
        return original(project_id)

    monkeypatch.setattr(beads, "task_authority_status", status)
    result = beads.change(
        "fixture", "update", {"id": "fixture-1", "patch": {"set": {"title": "new"}}}
    )

    assert result["mutation_state"] == "applied"
    assert result["post_write"]["status"]["status"] == "unavailable"
    assert result["post_write"]["readback"]["status"] == "available"
    assert (
        sum(
            "update" in command and "--readonly" not in command
            for command in commands(log)
        )
        == 1
    )


def test_changeset_uses_native_create_id_when_status_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    beads, log = beads_service(tmp_path)
    original = beads.task_authority_status
    calls = 0

    def status(project_id: str):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise BeadsError("injected post-write status failure", "deadline")
        return original(project_id)

    monkeypatch.setattr(beads, "task_authority_status", status)
    result = beads.changeset(
        [
            {
                "ref": "sinnix://projects/fixture",
                "operation": "create",
                "parameters": {"title": "created"},
                "bind": "created",
            },
            {
                "ref": "sinnix://projects/fixture/beads/$created",
                "operation": "comment",
                "parameters": {"text": "linked"},
            },
        ],
        mode="apply",
    )

    assert [item["outcome"] for item in result["outcomes"]] == ["applied", "applied"]
    assert result["outcomes"][0]["bound_ref"] == (
        "sinnix://projects/fixture/beads/fixture-created-1"
    )
    assert result["outcomes"][0]["post_write"]["status"]["status"] == "unavailable"
    assert sum("create" in command for command in commands(log)) == 1
    assert sum("comments" in command for command in commands(log)) == 1


def test_changeset_halts_an_applied_create_with_an_unresolved_bind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    beads, log = beads_service(tmp_path)
    original_status = beads.task_authority_status
    original_run = beads._run
    calls = 0

    def status(project_id: str):
        nonlocal calls
        calls += 1
        if calls >= 3:
            raise BeadsError("injected post-write status failure", "deadline")
        return original_status(project_id)

    def create_without_id(project, args, write, **kwargs):
        if write and "create" in args:
            original_run(project, args, write, **kwargs)
            return {"created": True}
        return original_run(project, args, write, **kwargs)

    monkeypatch.setattr(beads, "task_authority_status", status)
    monkeypatch.setattr(beads, "_run", create_without_id)
    result = beads.changeset(
        [
            {
                "ref": "sinnix://projects/fixture",
                "operation": "create",
                "parameters": {"title": "created"},
                "bind": "created",
            },
            {
                "ref": "sinnix://projects/fixture/beads/$created",
                "operation": "comment",
                "parameters": {"text": "linked"},
            },
        ],
        mode="apply",
    )

    assert [item["outcome"] for item in result["outcomes"]] == ["applied", "skipped"]
    assert result["outcomes"][0]["bind_uncertainty"]["symbol"] == "created"
    assert result["outcomes"][1]["reason"] == (
        "an earlier applied create could not bind its owner id"
    )
    assert result["partial_completion"] is True
    assert sum("create" in command for command in commands(log)) == 1
    assert not any("comments" in command for command in commands(log))


def test_native_transport_uncertainty_is_not_replayed_in_changeset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    beads, log = beads_service(tmp_path)
    original = beads._run

    def uncertain_update(project, args, write, **kwargs):
        if write and "update" in args:
            original(project, args, write, **kwargs)
            raise BeadsError("injected owner reply loss", "response_bound")
        return original(project, args, write, **kwargs)

    monkeypatch.setattr(beads, "_run", uncertain_update)
    result = beads.changeset(
        [
            {
                "ref": "sinnix://projects/fixture/beads/fixture-1",
                "operation": "update",
                "parameters": {"patch": {"set": {"title": "first"}}},
            },
            {
                "ref": "sinnix://projects/fixture/beads/fixture-1",
                "operation": "update",
                "parameters": {"patch": {"set": {"title": "second"}}},
            },
        ],
        mode="apply",
    )

    assert [item["outcome"] for item in result["outcomes"]] == [
        "indeterminate",
        "skipped",
    ]
    assert result["partial_completion"] is True
    assert (
        sum(
            "update" in command and "--readonly" not in command
            for command in commands(log)
        )
        == 1
    )
