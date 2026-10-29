"""Native Beads JSON retains types across the process adapter."""

from __future__ import annotations

from test_beads import beads_service, commands


def test_metadata_values_are_not_coerced_into_cli_strings(tmp_path):
    beads, log = beads_service(tmp_path)
    values = {
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
    payload = {
        "path": {"id": "fixture-1"},
        "body": {
            "actor": "operator",
            "expected_version": 7773497739344011640,
            "patch": {"metadata": {"set": values}},
        },
    }
    result = beads.native("fixture", "updateIssue", payload, write=True)
    assert commands(log)[-1]["payload"] == payload
    assert result["request"]["body"]["expected_version"] == 7773497739344011640


def test_authority_refuses_changed_project_identity_before_owner_call(tmp_path):
    import json
    from dataclasses import replace

    import pytest
    from sinnix_agent_gateway.beads import BeadsError, BeadsService

    beads, log = beads_service(tmp_path)
    project = beads.config.projects["fixture"]
    authority = replace(project.task_authority, project_uuid="fixture-current")
    metadata = authority.workspace / "metadata.json"
    metadata.write_text(json.dumps({"project_id": "fixture-historical"}))
    beads = BeadsService(
        replace(
            beads.config,
            projects={"fixture": replace(project, task_authority=authority)},
        )
    )
    with pytest.raises(BeadsError, match="project identity"):
        beads.task_authority_status("fixture")
    assert not log.exists()
    metadata.write_text(json.dumps({"project_id": "fixture-current"}))
    assert beads.task_authority_status("fixture")["project_uuid"] == "fixture-current"


def test_authority_refuses_redirect_to_historical_workspace(tmp_path):
    import pytest
    from sinnix_agent_gateway.beads import BeadsError

    beads, log = beads_service(tmp_path)
    project = beads.config.projects["fixture"]
    (project.path / ".beads").mkdir()
    redirect = project.path / ".beads" / "redirect"
    redirect.write_text(str(tmp_path / "historical"))
    with pytest.raises(BeadsError, match="checkout redirect"):
        beads.task_authority_status("fixture")
    assert not log.exists()
    redirect.write_text(str(project.task_authority.workspace))
    assert beads.task_authority_status("fixture")["attested"] is True


def test_current_authority_does_not_alias_a_missing_legacy_issue(tmp_path):
    import pytest
    from sinnix_agent_gateway.beads import BeadsError

    beads, _ = beads_service(tmp_path)
    with pytest.raises(BeadsError) as failure:
        beads.get("fixture", "historical-1")
    assert failure.value.code == "not_found"
    assert beads.get("fixture", "fixture-1")["id"] == "fixture-1"


def test_get_refuses_a_different_issue_returned_by_owner(tmp_path, monkeypatch):
    import pytest
    from sinnix_agent_gateway.beads import BeadsError

    beads, _ = beads_service(tmp_path)
    original = beads._run

    def wrong_identity(project, args, write, **kwargs):
        if (kwargs.get("payload") or {}).get("roots"):
            return {
                "items": [
                    {"id": "historical-1", "title": "Historical", "status": "closed"}
                ],
                "revision": "wrong-owner-position",
            }
        return original(project, args, write, **kwargs)

    monkeypatch.setattr(beads, "_run", wrong_identity)
    with pytest.raises(BeadsError, match="another issue identity"):
        beads.get("fixture", "fixture-1")
