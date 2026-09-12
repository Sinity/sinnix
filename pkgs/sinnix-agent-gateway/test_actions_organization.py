from __future__ import annotations

from pathlib import Path

import anyio
from mcp.types import CallToolResult
from sinnix_agent_gateway.app import create_server
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.files import FileError


def config(tmp_path: Path) -> GatewayConfig:
    project = tmp_path / "project"
    project.mkdir()
    return GatewayConfig(
        state_dir=tmp_path / "state",
        projects={"fixture": ProjectConfig(project_id="fixture", path=project)},
        approved_manifest_hash="approved-fixture-hash",
    )


def call(server, name: str, arguments: dict):
    return anyio.run(server.call_tool, name, arguments)


def structured(result) -> dict:
    if isinstance(result, CallToolResult):
        assert result.structured_content is not None
        return result.structured_content
    return result


def plan(
    server, source: Path, destination: Path, *, mkdirs: list[Path] | None = None
) -> dict:
    result = structured(
        call(
            server,
            "files.plan",
            {
                "moves": [
                    {
                        "source": {"path": str(source)},
                        "destination": {"path": str(destination)},
                    }
                ],
                "mkdirs": [{"path": str(path)} for path in (mkdirs or [])],
            },
        )
    )
    assert result["result"]["outcome"] == "ok", result
    return result["data"]


def apply(server, plan_data: dict, key: str = "apply-1") -> dict:
    return structured(
        call(
            server,
            "files.changeset",
            {
                "plan_ref": plan_data["plan_artifact"]["ref"],
                "plan_digest": plan_data["plan_digest"],
                "idempotency_key": key,
            },
        )
    )


def test_plan_applies_explicit_move_after_planned_mkdir_and_replays(
    tmp_path: Path,
) -> None:
    server = create_server(config(tmp_path), "operator")
    source = tmp_path / "source.txt"
    destination_parent = tmp_path / "archive"
    destination = destination_parent / "source.txt"
    source.write_text("source\n")

    planned = plan(server, source, destination, mkdirs=[destination_parent])
    assert planned["ready"] is True
    assert planned["moves"][0]["identity"]["sha256"]
    assert planned["moves"][0]["same_filesystem"] is True

    first = apply(server, planned)
    assert first["result"]["outcome"] == "ok", first
    assert first["data"]["state"] == "applied"
    assert source.exists() is False and destination.read_text() == "source\n"

    replay = apply(server, planned)
    assert replay["result"]["result_id"] == first["result"]["result_id"]
    assert destination.read_text() == "source\n"


def test_changeset_refuses_changed_source_before_any_mutation(tmp_path: Path) -> None:
    server = create_server(config(tmp_path), "operator")
    source, destination = tmp_path / "source.txt", tmp_path / "destination.txt"
    source.write_text("before")
    planned = plan(server, source, destination)
    source.write_text("changed")

    result = apply(server, planned)
    assert result["result"]["outcome"] == "error"
    assert result["error"]["code"] == "precondition_failed"
    assert source.read_text() == "changed"
    assert destination.exists() is False


def test_plan_reports_collision_without_mutating(tmp_path: Path) -> None:
    server = create_server(config(tmp_path), "operator")
    source, destination = tmp_path / "source.txt", tmp_path / "destination.txt"
    source.write_text("source")
    destination.write_text("destination")

    planned = plan(server, source, destination)
    assert planned["ready"] is False
    assert planned["moves"][0]["refusal"] == "destination already exists"
    result = apply(server, planned)
    assert result["result"]["outcome"] == "error"
    assert result["error"]["code"] == "precondition_failed"
    assert source.read_text() == "source" and destination.read_text() == "destination"


def test_changeset_reports_partial_failure_with_compensation_hint(
    tmp_path: Path, monkeypatch
) -> None:
    server = create_server(config(tmp_path), "operator")
    runtime = server._sinnix_revision_publisher.runtime
    source_one, source_two = tmp_path / "one.txt", tmp_path / "two.txt"
    destination_one, destination_two = (
        tmp_path / "one-new.txt",
        tmp_path / "two-new.txt",
    )
    source_one.write_text("one")
    source_two.write_text("two")
    result = structured(
        call(
            server,
            "files.plan",
            {
                "moves": [
                    {
                        "source": {"path": str(source_one)},
                        "destination": {"path": str(destination_one)},
                    },
                    {
                        "source": {"path": str(source_two)},
                        "destination": {"path": str(destination_two)},
                    },
                ]
            },
        )
    )
    planned = result["data"]
    original_write = runtime.files.write
    calls = 0

    def fail_second_move(operation, *args, **kwargs):
        nonlocal calls
        if operation == "move":
            calls += 1
            if calls == 2:
                raise FileError("synthetic transfer failure")
        return original_write(operation, *args, **kwargs)

    monkeypatch.setattr(runtime.files, "write", fail_second_move)
    applied = apply(server, planned, "partial-1")
    assert applied["result"]["outcome"] == "ok", applied
    assert applied["data"]["state"] == "partial"
    first, second = applied["data"]["entries"]
    assert first["state"] == "applied" and first["compensation_hint"]
    assert second["state"] == "failed"
    assert destination_one.read_text() == "one"
    assert source_two.read_text() == "two"


def test_directory_move_is_same_filesystem_rename_with_tree_identity(
    tmp_path: Path,
) -> None:
    server = create_server(config(tmp_path), "operator")
    source, destination = tmp_path / "source-dir", tmp_path / "destination-dir"
    (source / "nested").mkdir(parents=True)
    (source / "nested" / "note.txt").write_text("note")
    (source / "link").symlink_to("nested/note.txt")

    planned = plan(server, source, destination)
    move = planned["moves"][0]
    assert planned["ready"] is True
    assert move["identity"]["tree_entries"] == 3
    assert move["identity"]["tree_sha256"]
    applied = apply(server, planned, "directory-1")
    assert applied["data"]["state"] == "applied"
    assert source.exists() is False
    assert (destination / "nested" / "note.txt").read_text() == "note"
    assert (destination / "link").is_symlink()


def test_references_uses_bounded_existing_text_search(tmp_path: Path) -> None:
    server = create_server(config(tmp_path), "operator")
    root = tmp_path / "refs"
    root.mkdir()
    note = root / "note.txt"
    note.write_text("path=/realm/data/old.txt\n")

    result = structured(
        call(
            server,
            "files.references",
            {"roots": [{"path": str(root)}], "old_paths": ["/realm/data/old.txt"]},
        )
    )
    assert result["result"]["outcome"] == "ok", result
    hit = result["data"]["hits"][0]
    assert hit["path"] == str(note) and hit["line_number"] == 1
