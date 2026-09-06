"""Mutation success must survive a failure of optional history enrichment."""

from pathlib import Path

import pytest
from sinnix_agent_gateway.beads import BeadsError
from test_beads import beads_service, commands


@pytest.mark.parametrize("code", ["response_bound", "deadline"])
def test_history_failure_preserves_confirmed_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: str
) -> None:
    beads, log = beads_service(tmp_path)
    original = beads._includes

    def unavailable_history(project, project_id, target, includes, *args, **kwargs):
        if "history" in includes:
            raise BeadsError("injected history read failure", code)
        return original(project, project_id, target, includes, *args, **kwargs)

    monkeypatch.setattr(beads, "_includes", unavailable_history)
    result = beads.change(
        "fixture", "update", {"id": "fixture-1", "patch": {"set": {"title": "new"}}}
    )

    assert result["mode"] == "apply"
    assert result["after"]["id"] == "fixture-1"
    assert result["owner_history_ref"] == "sinnix://projects/fixture/beads/fixture-1/history"
    assert result["owner_history"]["status"] == "unavailable"
    assert result["owner_history"]["error"]["code"] == code
    assert sum("update" in command and "--readonly" not in command for command in commands(log)) == 1


def test_native_mutation_failure_is_not_laundered_as_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    beads, log = beads_service(tmp_path)
    original = beads._run

    def failed_mutation(project, args, write, **kwargs):
        if write and "update" in args:
            raise BeadsError("injected owner refusal before mutation", "owner_failed")
        return original(project, args, write, **kwargs)

    monkeypatch.setattr(beads, "_run", failed_mutation)
    with pytest.raises(BeadsError, match="injected owner refusal"):
        beads.change(
            "fixture", "update", {"id": "fixture-1", "patch": {"set": {"title": "new"}}}
        )
    assert not any("update" in command for command in commands(log))
