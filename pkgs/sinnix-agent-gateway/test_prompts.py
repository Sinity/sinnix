from __future__ import annotations

import json
import pytest

from sinnix_agent_gateway.prompts import PromptGenerator, PROMPT_SPECS


def test_generated_prompts_use_canonical_refs_and_principal_filtered_catalog() -> None:
    catalog = lambda principal: {"revision": "catalog-rev", "actions": [{"name": "beads.query", "verb": "query", "effect": "read", "route": "beads.query", "resource_kinds": ["bead"]}, {"name": "beads.change", "verb": "change", "effect": "change", "route": "beads.write", "resource_kinds": ["bead"]}]}  # noqa: E731
    generator = PromptGenerator(principal="observer", catalog=catalog)

    assert {row["name"] for row in generator.list()} == {spec.name for spec in PROMPT_SPECS}
    messages = generator.generate("work-bead", {"ref": "sinnix://projects/p/beads/b"})
    body = json.loads(messages[0]["content"]["text"])
    assert body["target_ref"] == "sinnix://projects/p/beads/b"
    assert body["context_ref"] == body["target_ref"]
    assert body["action_catalog_revision"] == "catalog-rev"
    assert "does not grant mutation authority" in " ".join(body["instructions"])


def test_prompt_rejects_noncanonical_or_unknown_inputs() -> None:
    generator = PromptGenerator(principal="observer", catalog=lambda _principal: {"actions": []})
    try:
        generator.generate("orient-project", {"ref": "/tmp/project"})
    except ValueError as exc:
        assert "canonical" in str(exc)
    else:
        raise AssertionError("noncanonical prompt target was accepted")


def test_prompt_registry_visibility_intent_kind_and_bounds_are_enforced() -> None:
    generator = PromptGenerator(principal="observer", catalog=lambda _principal: {"actions": []})
    with pytest.raises(ValueError, match="resource kind"):
        generator.generate("orient-project", {"ref": "sinnix://jobs/job-1"})
    with pytest.raises(ValueError, match="visible"):
        generator.generate("orient-project", {"ref": "sinnix://browser/agent-workspace"})
    with pytest.raises(ValueError, match="job_ref"):
        generator.generate("work-bead", {"ref": "sinnix://projects/p/beads/b", "job_ref": "sinnix://projects/p"})
    with pytest.raises(ValueError, match="input bound"):
        generator.generate("orient-project", {"ref": "sinnix://projects/" + "x" * 2_100})
