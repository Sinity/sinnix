from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path

SCRIPT = Path(__file__).parents[3] / "scripts" / "sinnix-file-catalog"


def invoke(catalog: Path, command: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), "--catalog", str(catalog), command, *args],
        text=True,
        capture_output=True,
        check=False,
    )


def observation(path: Path, **extra: object) -> dict[str, object]:
    return {
        "current_path": str(path),
        "title": "Sample recording",
        "description": "A useful sample",
        "tags": ["audio"],
        "inspections": [
            {"method": "manual", "scope": "metadata", "basis": "operator note"}
        ],
        **extra,
    }


def import_rows(
    catalog: Path, rows: list[dict[str, object]]
) -> subprocess.CompletedProcess[str]:
    source = catalog.with_name("observations.json")
    source.write_text(json.dumps(rows), encoding="utf-8")
    return invoke(catalog, "import", str(source))


def assets(catalog: Path) -> list[dict[str, object]]:
    return json.loads(catalog.read_text(encoding="utf-8"))["assets"]


def test_import_is_idempotent_and_merges_evidence(tmp_path: Path) -> None:
    payload = tmp_path / "recording.txt"
    payload.write_text("sample", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    assert import_rows(catalog, [observation(payload)]).returncode == 0
    first = assets(catalog)[0]
    assert (
        import_rows(
            catalog,
            [
                observation(
                    payload,
                    tags=["new"],
                    inspections=[
                        {"method": "tool", "scope": "content", "basis": "report"}
                    ],
                )
            ],
        ).returncode
        == 0
    )
    second = assets(catalog)[0]
    assert second["id"] == first["id"]
    assert second["tags"] == ["audio", "new"]
    assert len(second["inspections"]) == 2


def test_relocate_preserves_id_and_history_after_external_rename(
    tmp_path: Path,
) -> None:
    old = tmp_path / "old.txt"
    new = tmp_path / "new.txt"
    old.write_text("sample", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    assert import_rows(catalog, [observation(old)]).returncode == 0
    asset = assets(catalog)[0]
    old.rename(new)
    result = invoke(catalog, "relocate", str(asset["id"]), str(new))
    assert result.returncode == 0, result.stderr
    updated = assets(catalog)[0]
    assert updated["id"] == asset["id"]
    assert updated["previous_paths"] == [str(old)]


def test_replacement_and_duplicate_path_are_refused_without_write(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "recording.txt"
    payload.write_text("sample", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    assert import_rows(catalog, [observation(payload)]).returncode == 0
    before = catalog.read_bytes()
    payload.write_text("replacement", encoding="utf-8")
    assert import_rows(catalog, [observation(payload)]).returncode != 0
    assert catalog.read_bytes() == before
    other = tmp_path / "other.txt"
    other.write_text("other", encoding="utf-8")
    assert (
        import_rows(catalog, [observation(other), observation(other)]).returncode != 0
    )


def test_empty_inspection_is_rejected_atomically(tmp_path: Path) -> None:
    payload = tmp_path / "recording.txt"
    payload.write_text("sample", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    assert import_rows(catalog, [observation(payload)]).returncode == 0
    before = catalog.read_bytes()
    row = observation(payload, inspections=[])
    assert import_rows(catalog, [row]).returncode != 0
    assert catalog.read_bytes() == before


def test_dangling_relation_is_rejected_with_valid_inspection(tmp_path: Path) -> None:
    payload = tmp_path / "recording.txt"
    payload.write_text("sample", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    row = observation(
        payload,
        relations=[
            {"type": "derived", "target_id": str(uuid.uuid4()), "basis": "note"}
        ],
    )
    assert import_rows(catalog, [row]).returncode != 0
    assert not catalog.exists()


def test_search_and_show_work_when_payload_is_missing(tmp_path: Path) -> None:
    payload = tmp_path / "recording.txt"
    payload.write_text("sample", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    assert import_rows(catalog, [observation(payload)]).returncode == 0
    asset_id = assets(catalog)[0]["id"]
    payload.unlink()
    assert invoke(catalog, "search", "sample").returncode == 0
    assert invoke(catalog, "show", str(asset_id)).returncode == 0
    assert invoke(catalog, "validate").returncode != 0


def test_collection_identity_allows_membership_changes(tmp_path: Path) -> None:
    directory = tmp_path / "collection"
    directory.mkdir()
    catalog = tmp_path / "catalog.json"
    assert (
        import_rows(catalog, [observation(directory, kind="collection")]).returncode
        == 0
    )
    (directory / "member").write_text("new", encoding="utf-8")
    assert (
        import_rows(catalog, [observation(directory, kind="collection")]).returncode
        == 0
    )


def test_description_history_and_unknown_fields_survive_updates(tmp_path: Path) -> None:
    payload = tmp_path / "recording.txt"
    payload.write_text("sample", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    assert (
        import_rows(
            catalog, [observation(payload, identity={"attribution": "scanner"})]
        ).returncode
        != 0
    )
    # A supplied partial identity is intentionally invalid; import once with
    # the normal stat identity, then add an attributed field to the catalog.
    assert import_rows(catalog, [observation(payload)]).returncode == 0
    data = json.loads(catalog.read_text(encoding="utf-8"))
    data["assets"][0]["identity"]["attribution"] = "scanner"
    data["assets"][0]["custom_annotation"] = {"reviewer": "A"}
    data["assets"][0]["previous_paths"] = [str(tmp_path / "earlier.txt")]
    catalog.write_text(json.dumps(data), encoding="utf-8")
    assert (
        import_rows(
            catalog,
            [
                observation(
                    payload, title="Revised title", description="Revised description"
                )
            ],
        ).returncode
        == 0
    )
    asset = assets(catalog)[0]
    assert asset["identity"]["attribution"] == "scanner"
    assert asset["custom_annotation"] == {"reviewer": "A"}
    assert asset["previous_paths"] == [str(tmp_path / "earlier.txt")]
    assert asset["inspections"][0]["title"] == "Sample recording"
    assert asset["inspections"][0]["description"] == "A useful sample"


def test_missing_identity_and_wrong_kind_are_rejected(tmp_path: Path) -> None:
    payload = tmp_path / "recording.txt"
    payload.write_text("sample", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    assert (
        import_rows(catalog, [observation(payload, kind="collection")]).returncode != 0
    )
    data = {
        "schema_version": 1,
        "updated_at": "2026-01-01T00:00:00Z",
        "assets": [{**observation(payload), "id": str(uuid.uuid4()), "identity": None}],
    }
    catalog.write_text(json.dumps(data), encoding="utf-8")
    assert invoke(catalog, "validate").returncode != 0


def test_relative_paths_and_malformed_lists_are_rejected(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.json"
    row = observation(tmp_path / "recording.txt", current_path="relative.txt")
    assert import_rows(catalog, [row]).returncode != 0
    payload = tmp_path / "recording.txt"
    payload.write_text("sample", encoding="utf-8")
    bad = observation(payload, tags=[3])
    assert import_rows(catalog, [bad]).returncode != 0


def test_relocate_repairs_after_unrelated_payload_is_also_renamed(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    assert (
        import_rows(catalog, [observation(first), observation(second)]).returncode == 0
    )
    row = {a["current_path"]: a for a in assets(catalog)}
    first_new, second_new = tmp_path / "first-new", tmp_path / "second-new"
    first.rename(first_new)
    second.rename(second_new)
    result = invoke(catalog, "relocate", str(row[str(first)]["id"]), str(first_new))
    assert result.returncode == 0, result.stderr
