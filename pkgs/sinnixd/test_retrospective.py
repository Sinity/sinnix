from __future__ import annotations

import json
from pathlib import Path

import pytest

from sinnixd.retrospective import RetrospectiveError, run_retrospective, validate_proposals


def proposal() -> dict[str, object]:
    return {"title": "Make fetch locking explicit", "description": "Repeated fetch collisions were observed.", "type": "task", "priority": 2, "labels": ["orchestration"], "evidence": ["events.jsonl:event-1"]}


def test_files_only_validated_model_proposals_and_advances_cursor(tmp_path: Path) -> None:
    created: list[dict[str, object]] = []
    result = run_retrospective(
        evidence={"day": "2026-08-26", "events": ["event-1"], "harvest_logs": {}, "session_receipts": {}},
        model_call=lambda _: json.dumps({"proposals": [proposal()]}),
        task_create=created.append,
        state_path=tmp_path / "state.json",
    )
    assert result == {"day": "2026-08-26", "proposals": 1, "filed": 1}
    assert created[0]["request_id"]
    assert json.loads((tmp_path / "state.json").read_text())["filed"] == 1


def test_malformed_model_output_cannot_mutate_or_advance(tmp_path: Path) -> None:
    created: list[dict[str, object]] = []
    with pytest.raises(RetrospectiveError):
        run_retrospective(
            evidence={"day": "2026-08-26"},
            model_call=lambda _: '{"proposals":[{"title":"unsafe"}]}',
            task_create=created.append,
            state_path=tmp_path / "state.json",
        )
    assert created == []
    assert not (tmp_path / "state.json").exists()


def test_proposals_require_observable_evidence() -> None:
    value = proposal()
    value["evidence"] = []
    with pytest.raises(RetrospectiveError):
        validate_proposals({"proposals": [value]})
