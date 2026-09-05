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

    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    value, errors = results.load_result(bad, kind="worker")
    assert value is None and errors[0].endswith(")") and "not JSON" in errors[0]
    value, errors = results.load_result(tmp_path / "missing.json", kind="worker")
    assert value is None and "missing.json" in errors[0]


def test_write_schema_round_trips_the_embedded_document(tmp_path: Path) -> None:
    written = results.write_schema(tmp_path / "x" / "worker.schema.json", "worker")
    assert json.loads(written.read_text()) == results.WORKER_SCHEMA


@pytest.mark.skipif(
    not SCHEMA_DIR.is_dir(), reason="agent schemas are outside this checkout"
)
@pytest.mark.parametrize("kind", ["worker", "judge"])
def test_embedded_schemas_match_the_agent_schema_files(kind: str) -> None:
    """Breaks if either copy of a schema is edited without the other."""
    on_disk = json.loads((SCHEMA_DIR / f"{kind}.schema.json").read_text())
    assert on_disk == results.SCHEMAS[kind]


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
