from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from sinnix_agent_gateway.gateway_codegen import (
    DOCS_PATH,
    FIXTURE_PATH,
    REFERENCE_PATH,
    SKILL_PATH,
    check_artifacts,
    catalog_payload,
    render_fixtures,
    render_reference,
    render_skill,
    update_docs,
)


candidate_root = Path(__file__).resolve().parents[2]
ROOT = candidate_root if (candidate_root / DOCS_PATH).exists() else None
FIXTURE_FILE = (ROOT / FIXTURE_PATH) if ROOT is not None else Path(__file__).parent / "fixtures" / FIXTURE_PATH.name


def test_generated_artifacts_are_current_and_deterministic() -> None:
    if ROOT is not None:
        assert check_artifacts(ROOT) == []
    assert render_reference() == render_reference()
    assert render_skill() == render_skill()
    assert render_skill().startswith(
        "---\nname: agent-gateway\ndescription: Use when invoking, inspecting, or documenting "
    )
    assert render_fixtures() == render_fixtures()
    assert json.loads(FIXTURE_FILE.read_text())["action_catalog_hash"] == catalog_payload()["action_catalog_hash"]


def test_every_generated_example_validates_against_the_live_action_schema() -> None:
    fixtures = json.loads(FIXTURE_FILE.read_text())
    actions = {row["name"]: row for row in catalog_payload()["actions"]}
    for fixture in fixtures["examples"]:
        schema = actions[fixture["action"]]["input_schema"]
        errors = list(Draft202012Validator(schema).iter_errors(fixture["input"]))
        assert errors == [], (fixture["action"], errors)


def test_corrupting_an_action_name_or_field_fails_generation_check(tmp_path: Path) -> None:
    artifacts = {
        REFERENCE_PATH: render_reference(),
        SKILL_PATH: render_skill(),
        FIXTURE_PATH: json.dumps(render_fixtures(), indent=2, sort_keys=True) + "\n",
        DOCS_PATH: update_docs(""),
    }
    for path, content in artifacts.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    reference = tmp_path / REFERENCE_PATH
    reference.write_text(reference.read_text().replace("`gateway.status`", "`gateway.corrupt`", 1))
    assert check_artifacts(tmp_path)

    reference.write_text(render_reference().replace("Catalog SHA-256", "Corrupt field"))
    assert check_artifacts(tmp_path)
