"""The worker result and judge verdict contracts, and their embedded schemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from agentctl import results

SHA = "a" * 40
SCHEMA_DIR = (
    Path(__file__).resolve().parents[2] / "dots" / "claude" / "agents" / "schemas"
)


def worker_result(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "candidate_sha": SHA,
        "beads": [
            {
                "id": "fx-1",
                "criteria": [
                    {
                        "text": "tests pass",
                        "status": "satisfied",
                        "evidence": "pytest -q",
                    }
                ],
            }
        ],
        "unresolved": [],
        "verification": [{"command": "pytest -q", "receipt": "3 passed"}],
    }
    document.update(overrides)
    return document


def test_a_conforming_worker_result_has_no_errors() -> None:
    assert results.validate_worker_result(worker_result()) == []


def test_versioned_result_carries_explicit_provenance_and_stable_evidence() -> None:
    result = worker_result(
        schema_version=2,
        planned_model="gpt-5.6",
        execution="queued",
        parent_session_ref="parent-1",
        child_session_ref="child-1",
        attempt=1,
        model_segments=[
            {
                "attempt": 1,
                "actual_executor_model": "gpt-5.6",
                "actual_executor_observed_by": "runner",
                "measured_usage": None,
            }
        ],
        measured_usage={"input_tokens": 12, "output_tokens": 8},
        beads=[
            {
                "id": "fx-1",
                "bead_revision": "sha256:fixture",
                "acceptance_digest": "sha256:acceptance",
                "criteria": [
                    {
                        "ac_id": "fx-1/ac-1",
                        "text": "tests pass",
                        "status": "satisfied",
                        "evidence": "pytest -q",
                    }
                ],
            }
        ],
        verification=[
            {
                "command": "pytest -q",
                "receipt": "3 passed",
                "tested_sha": SHA,
                "status": "passed",
                "coverage": {
                    "ac_ids": ["fx-1/ac-1"],
                    "scope": "pkgs/agentctl/test_results.py",
                },
            }
        ],
    )
    assert results.validate_worker_result(result) == []
    # A historical result remains valid, but its absent provenance is unknown.
    assert results.validate_worker_result(worker_result()) == []


def test_versioned_result_rejects_missing_stable_evidence() -> None:
    errors = results.validate_worker_result(worker_result(schema_version=2))
    assert any("missing execution" in error for error in errors)
    assert any("missing bead_revision" in error for error in errors)
    assert any("missing ac_id" in error for error in errors)
    assert any("missing tested_sha" in error for error in errors)


def test_versioned_result_requires_attribution_and_unique_acceptance_ids() -> None:
    result = worker_result(
        schema_version=2,
        execution="native",
        attempt=1,
        model_segments=[],
        measured_usage=None,
        actual_executor_model="gpt-5.6",
        beads=[
            {
                "id": "fx-1",
                "bead_revision": "rev",
                "criteria": [
                    {
                        "ac_id": "ac-1",
                        "text": "one",
                        "status": "satisfied",
                        "evidence": "e",
                    },
                    {
                        "ac_id": "ac-1",
                        "text": "two",
                        "status": "satisfied",
                        "evidence": "e",
                    },
                ],
            }
        ],
        verification=[
            {
                "command": "x",
                "receipt": "ok",
                "tested_sha": SHA,
                "status": "passed",
                "coverage": {"ac_ids": ["ac-1"], "scope": "one"},
            }
        ],
    )
    errors = results.validate_worker_result(result)
    assert any(
        "actual_executor_model missing actual_executor_observed_by" in error
        for error in errors
    )
    assert any("duplicate ac_id ac-1" in error for error in errors)


def test_versioned_result_rejects_duplicate_bead_rows() -> None:
    result = worker_result(
        schema_version=2,
        execution="native",
        attempt=1,
        model_segments=[],
        measured_usage=None,
        beads=[
            {
                "id": "fx-1",
                "bead_revision": "rev",
                "acceptance_digest": "digest",
                "criteria": [
                    {
                        "ac_id": "one",
                        "text": "one",
                        "status": "satisfied",
                        "evidence": "e",
                    }
                ],
            },
            {
                "id": "fx-1",
                "bead_revision": "rev",
                "acceptance_digest": "digest",
                "criteria": [
                    {
                        "ac_id": "two",
                        "text": "two",
                        "status": "satisfied",
                        "evidence": "e",
                    }
                ],
            },
        ],
        verification=[
            {
                "command": "x",
                "receipt": "ok",
                "tested_sha": SHA,
                "status": "passed",
                "coverage": {"ac_ids": ["one"], "scope": "unit"},
            }
        ],
    )
    assert any("duplicate bead id fx-1" in error for error in results.validate_worker_result(result))


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"candidate_sha": "abc"}, "candidate_sha: does not match"),
        ({"candidate_sha": SHA.upper()}, "candidate_sha: does not match"),
        ({"beads": []}, "beads: fewer than 1"),
        ({"extra": 1}, "unexpected extra"),
        ({"unresolved": [""]}, "unresolved[0]: shorter"),
        ({"verification": [{"command": "x"}]}, "verification[0]: missing receipt"),
        (
            {
                "beads": [
                    {
                        "id": "fx",
                        "criteria": [{"text": "t", "status": "done", "evidence": ""}],
                    }
                ]
            },
            "status: must be one of",
        ),
        ({"beads": [{"id": "fx", "criteria": "none"}]}, "criteria: expected array"),
    ],
)
def test_worker_result_violations_are_named(
    overrides: dict[str, Any], fragment: str
) -> None:
    errors = results.validate_worker_result(worker_result(**overrides))
    assert any(fragment in error for error in errors), errors


def test_a_pattern_must_match_the_whole_string() -> None:
    schema = {"type": "string", "pattern": "[0-9a-f]{40}"}
    assert results.validate(schema, "a" * 40) == []
    assert results.validate(schema, "x" + "a" * 40) == [
        "$: does not match [0-9a-f]{40}"
    ]
    assert results.validate(schema, "a" * 40 + "\n") != []


def test_a_non_object_is_one_error() -> None:
    assert results.validate_worker_result([]) == ["$: expected object, got list"]
    assert results.validate_worker_result(None) == ["$: expected object, got NoneType"]


def test_judge_verdict_validation() -> None:
    verdict = {
        "verdict": "pass",
        "confidence": 0.9,
        "evidence": ["diff read"],
        "refutation_attempted": True,
        "unsupported": [],
    }
    assert results.validate_judge_verdict(verdict) == []
    assert results.validate_judge_verdict({**verdict, "confidence": 2}) == [
        "$.confidence: above 1"
    ]
    assert results.validate_judge_verdict({**verdict, "evidence": []}) == [
        "$.evidence: fewer than 1 items"
    ]
    assert results.validate_judge_verdict(
        {**verdict, "refutation_attempted": "yes"}
    ) == ["$.refutation_attempted: expected boolean, got str"]
    assert results.validate_judge_verdict({**verdict, "verdict": "maybe"})
    # A boolean is not a number.
    assert results.validate_judge_verdict({**verdict, "confidence": True})


def test_load_result_reads_a_file_or_the_claude_envelope(tmp_path: Path) -> None:
    plain = tmp_path / "plain.json"
    plain.write_text(json.dumps(worker_result()))
    value, errors = results.load_result(plain, kind="worker")
    assert errors == [] and value["candidate_sha"] == SHA

    wrapped = tmp_path / "wrapped.json"
    wrapped.write_text(
        json.dumps({"type": "result", "structured_output": worker_result()})
    )
    value, errors = results.load_result(wrapped, kind="worker")
    assert errors == [] and value["candidate_sha"] == SHA

    incomplete_v2 = tmp_path / "incomplete-v2.json"
    incomplete_v2.write_text(json.dumps(worker_result(schema_version=2)))
    value, errors = results.load_result(incomplete_v2, kind="worker")
    assert value["schema_version"] == 2
    assert any("missing execution" in error for error in errors)

    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    value, errors = results.load_result(bad, kind="worker")
    assert value is None and errors[0].endswith(")") and "not JSON" in errors[0]
    value, errors = results.load_result(tmp_path / "missing.json", kind="worker")
    assert value is None and "missing.json" in errors[0]


def test_write_schema_round_trips_the_embedded_document(tmp_path: Path) -> None:
    written = results.write_schema(tmp_path / "x" / "worker.schema.json", "worker")
    assert json.loads(written.read_text()) == results.WORKER_SCHEMA


def test_codex_schema_requires_nullable_transport_placeholders(tmp_path: Path) -> None:
    written = results.write_schema(tmp_path / "x" / "worker.schema.json", "worker", codex_strict=True)
    schema = json.loads(written.read_text())
    assert set(schema["required"]) == set(schema["properties"])
    segment = schema["properties"]["model_segments"]["items"]
    assert set(segment["required"]) == set(segment["properties"])
    assert set(segment["properties"]["actual_executor_model"]["type"]) == {"string", "null"}


def test_load_result_drops_codex_only_null_placeholders(tmp_path: Path) -> None:
    value = worker_result(
        schema_version=2,
        planned_model="gpt-5.6",
        execution="queued",
        parent_session_ref=None,
        child_session_ref=None,
        attempt=1,
        actual_executor_model=None,
        actual_executor_observed_by=None,
        model_segments=[
            {
                "attempt": 1,
                "planned_model": "gpt-5.6",
                "actual_executor_model": None,
                "actual_executor_observed_by": None,
                "measured_usage": None,
            }
        ],
        measured_usage=None,
        beads=[
            {
                "id": "fx-1",
                "bead_revision": "sha256:fixture",
                "acceptance_digest": "sha256:acceptance",
                "criteria": [
                    {
                        "ac_id": "fx-1/ac-1",
                        "text": "tests pass",
                        "status": "satisfied",
                        "evidence": "pytest -q",
                    }
                ],
            }
        ],
        verification=[
            {
                "command": "pytest -q",
                "receipt": "3 passed",
                "tested_sha": SHA,
                "status": "passed",
                "coverage": {"ac_ids": ["fx-1/ac-1"], "scope": "fixture"},
            }
        ],
    )
    path = tmp_path / "codex.json"
    path.write_text(json.dumps(value))
    loaded, errors = results.load_result(path, kind="worker")
    assert errors == []
    assert loaded is not None and "actual_executor_model" not in loaded
    assert loaded["measured_usage"] is None


@pytest.mark.skipif(
    not SCHEMA_DIR.is_dir(), reason="agent schemas are outside this checkout"
)
@pytest.mark.parametrize("kind", ["worker", "judge"])
def test_embedded_schemas_match_the_agent_schema_files(kind: str) -> None:
    """Breaks if either copy of a schema is edited without the other, or a
    `$schema` key returns: `claude --json-schema` rejects it."""
    on_disk = json.loads((SCHEMA_DIR / f"{kind}.schema.json").read_text())
    assert on_disk == results.SCHEMAS[kind]
    assert "$schema" not in on_disk


def test_no_embedded_schema_carries_a_dollar_schema_key() -> None:
    assert all("$schema" not in schema for schema in results.SCHEMAS.values())


def test_satisfied_beads_needs_every_criterion_across_every_result() -> None:
    first = worker_result()
    second = worker_result(
        beads=[
            {
                "id": "fx-1",
                "criteria": [
                    {"text": "docs", "status": "unsatisfied", "evidence": "none"}
                ],
            },
            {
                "id": "fx-2",
                "criteria": [
                    {"text": "old", "status": "superseded", "evidence": "replaced"}
                ],
            },
            {"id": "fx-3", "criteria": []},
        ]
    )
    assert results.satisfied_beads([first]) == {"fx-1": True}
    assert results.satisfied_beads([first, second]) == {
        "fx-1": False,
        "fx-2": True,
        "fx-3": False,
    }
