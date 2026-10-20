"""Original evidence stays readable without the retired filing workflow."""

import hashlib
import json
import tracemalloc
from types import SimpleNamespace

import pytest
from agentctl import evidence
from agentctl.config import Config
from agentctl.job_queries import JobError


def test_list_ignores_malformed_or_other_project_records(config: Config) -> None:
    directory = config.state_dir / "native-evidence"
    directory.mkdir(parents=True)
    (directory / "bad.json").write_text("not json")
    (directory / "other.json").write_text(
        json.dumps({"schema_version": 1, "kind": "native_evidence", "project": "other"})
    )

    listed = evidence.list_records(config, "fixture")
    assert listed["records"] == []
    assert listed["coverage"] == "partial"


def test_list_cursor_crosses_other_projects_and_retrieves_later_record(
    config: Config,
) -> None:
    directory = config.state_dir / "native-evidence"
    directory.mkdir(parents=True)
    for index in range(1, evidence.MAX_RECORDS + 3):
        evidence_id = f"{index:032x}"
        (directory / f"{evidence_id}.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "kind": "native_evidence",
                    "evidence_id": evidence_id,
                    "project": "other",
                    "recorded_at": "fixture",
                    "payload": "x" * 2_000,
                }
            )
        )
    target_id = f"{evidence.MAX_RECORDS + 3:032x}"
    target = {
        "schema_version": 1,
        "kind": "native_evidence",
        "evidence_id": target_id,
        "project": "fixture",
        "recorded_at": "fixture",
        "identity": "complete",
    }
    (directory / f"{target_id}.json").write_text(json.dumps(target))

    page = evidence.list_records(config, "fixture", limit=2)
    pages = [page]
    while pages[-1]["next_cursor"] is not None:
        pages.append(
            evidence.list_records(
                config, "fixture", cursor=pages[-1]["next_cursor"], limit=2
            )
        )

    assert all(len(item["records"]) <= 2 for item in pages)
    assert pages[0]["records"] == []
    assert any(
        row["evidence_id"] == target_id for item in pages for row in item["records"]
    )
    assert evidence.get_record(config, "fixture", target_id) == target


def test_list_selects_a_page_from_a_large_directory_with_bounded_memory(
    config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    count = 50_000
    observed = 0
    closed = False

    class SyntheticEntries:
        def __iter__(self):
            nonlocal observed
            for index in range(count, 0, -1):
                observed += 1
                yield SimpleNamespace(name=f"{index:032x}.json")

        def close(self) -> None:
            nonlocal closed
            closed = True

    monkeypatch.setattr(evidence.os, "scandir", lambda directory: SyntheticEntries())
    monkeypatch.setattr(evidence.job_queries, "read_bounded", lambda path, limit: None)
    tracemalloc.start()
    try:
        page = evidence.list_records(config, "fixture")
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert observed == count
    assert closed
    assert page["next_cursor"] == f"{evidence.MAX_RECORDS:032x}.json"
    assert page["coverage"] == "partial"
    assert len(page["gaps"]) == evidence.MAX_RECORDS + 1
    assert peak < 1_500_000


@pytest.mark.parametrize("damage", [None, "bytes", "sha256", "evidence_id", "project"])
def test_original_artifact_identity_and_scope_are_checked(config, damage):
    evidence_id = "a" * 32
    directory = config.state_dir / "native-evidence"
    directory.mkdir(parents=True)
    original = {
        "evidence_id": evidence_id,
        "project": "fixture",
        "raw": "x" * 300_000,
        "unknown_field": {"exact": 9223372036854775807},
    }
    raw = json.dumps(original).encode()
    artifact = directory / f"{evidence_id}.artifact.json"
    artifact.write_bytes(raw)
    pointer = {
        "schema_version": 2,
        "kind": "native_evidence_reference",
        "evidence_id": evidence_id,
        "project": "fixture",
        "artifact": artifact.name,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    if damage == "bytes":
        pointer[damage] += 1
    elif damage is not None:
        pointer[damage] = "wrong"
    (directory / f"{evidence_id}.json").write_text(json.dumps(pointer))
    if damage:
        with pytest.raises(JobError):
            evidence.get_record(config, "fixture", evidence_id)
    else:
        assert evidence.get_record(config, "fixture", evidence_id) == original
    assert artifact.read_bytes() == raw
