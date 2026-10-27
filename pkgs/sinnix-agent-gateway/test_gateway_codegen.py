from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sinnix_agent_gateway import actions as action_set
from sinnix_agent_gateway.action import Action
from sinnix_agent_gateway.gateway_codegen import (
    SKILL_PATH,
    check_artifacts,
    render_reference,
    render_skill,
)

candidate_root = Path(__file__).resolve().parents[2]
ROOT = candidate_root if (candidate_root / SKILL_PATH).exists() else None


def test_generated_artifacts_are_current_and_deterministic() -> None:
    if ROOT is not None:
        assert check_artifacts(ROOT) == []
    assert render_reference() == render_reference()
    assert render_skill() == render_skill()
    assert render_skill().startswith("---\nname: agent-gateway\ndescription: ")


def test_corrupting_an_action_name_or_field_fails_generation_check(
    tmp_path: Path,
) -> None:
    artifacts = {SKILL_PATH: render_skill()}
    for path, content in artifacts.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    assert check_artifacts(tmp_path) == []
    skill = tmp_path / SKILL_PATH
    skill.write_text(
        skill.read_text().replace("`gateway.status`", "`gateway.corrupt`", 1)
    )
    assert check_artifacts(tmp_path)


def test_catalog_hash_includes_examples_and_affordances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action = action_set.BY_NAME["gateway.status"]
    rows = list(action_set.ALL_ACTIONS)
    rows[rows.index(action)] = replace(
        action, next_actions=("gateway.catalog", "gateway.status"), examples=()
    )

    action_set.catalog_hash.cache_clear()
    baseline = action_set.catalog_hash()
    monkeypatch.setattr(action_set, "ALL_ACTIONS", tuple(rows))
    # A changed action set belongs to a new process, with an empty cache.
    action_set.catalog_hash.cache_clear()
    try:
        assert action_set.catalog_hash() != baseline
    finally:
        action_set.catalog_hash.cache_clear()


def test_catalog_digest_reuses_startup_result(monkeypatch: pytest.MonkeyPatch) -> None:
    action_set.catalog_hash.cache_clear()
    expected = action_set.catalog_hash()

    def unexpected(_self):
        raise AssertionError("warm catalog requests must not rebuild catalog rows")

    monkeypatch.setattr(Action, "catalog_row", unexpected)
    try:
        assert action_set.catalog_hash() == expected
        assert action_set.catalog_hash() == expected
    finally:
        action_set.catalog_hash.cache_clear()


def test_orientation_shared_with_generated_surfaces():
    from sinnix_agent_gateway.orientation import ORIENTATION

    assert ORIENTATION in render_skill()
    if ROOT is not None:
        assert ORIENTATION in (ROOT / "docs/agent-gateway.md").read_text()
