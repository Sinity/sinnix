from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import sinnixd.cli as cli_module
from sinnixd.packets import (
    PacketConfig,
    checkout_id_from_workspace_response,
    compile_launch_snapshot,
    resolve_group,
)


def bead(bead_id: str, *, group: str | None = None, intent: str = "ship it") -> dict:
    metadata = {
        "model_policy": "provider-neutral-calibrated-v2",
        "effort": "medium",
        "verification_commands": ["devtools test tests/unit"],
        "conflict_keys": "area:parser;area:storage",
        "affected_paths": "sources/parser.py;storage/write.py",
        "packet_intent": intent,
    }
    if group is not None:
        metadata["dispatch_group"] = group
    return {
        "id": bead_id,
        "title": f"Title {bead_id}",
        "description": f"Description {bead_id}",
        "metadata": metadata,
    }


class FixtureBd:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = {row["id"]: row for row in rows}

    def show(self, bead_id: str) -> dict:
        return self.rows[bead_id]

    def list(self) -> list[dict]:
        return list(self.rows.values())


def project_fixture(tmp_path: Path) -> tuple[Path, PacketConfig]:
    root = tmp_path / "project"
    (root / ".agentctl").mkdir(parents=True)
    (root / "docs" / "atlas").mkdir(parents=True)
    (root / "dots" / "_ai" / "skills" / "orchestrate" / "references").mkdir(
        parents=True
    )
    (root / "docs" / "atlas" / "storage.md").write_text("storage")
    template = (
        root
        / "dots"
        / "_ai"
        / "skills"
        / "orchestrate"
        / "references"
        / "worker-contract.md"
    )
    template.write_text("contract residue")
    (root / ".agentctl" / "project.toml").write_text(
        """
schema = 1
[project]
id = "fixture"
display_name = "Fixture"
root_markers = [".agentctl"]
[packets]
template = "dots/_ai/skills/orchestrate/references/worker-contract.md"
atlas_dir = "docs/atlas"
"""
    )
    return root, PacketConfig.load(root)


def test_snapshot_compiles_fixture_bead_json_and_group() -> None:
    rows = [bead("leader"), bead("member", group="leader", intent="adapt it")]
    root = Path("/does/not/matter")
    config = PacketConfig(
        template_path=Path(__file__),
        atlas_dir=Path("/does/not/matter"),
    )
    snapshot = compile_launch_snapshot(
        "member",
        project_root=root,
        project_id="fixture",
        reader=FixtureBd(rows),
        config=config,
    )

    assert snapshot.leader_id == "leader"
    assert snapshot.bead_ids == ("leader", "member")
    assert snapshot.dimensions.backend == "codex"
    assert snapshot.dimensions.model == "gpt-5.6-luna"
    assert snapshot.dimensions.conflict_keys == ("area:parser", "area:storage")
    assert "Description leader" in snapshot.prompt
    assert "Description member" in snapshot.prompt


def test_resolve_group_queries_members_that_point_at_leader() -> None:
    reader = FixtureBd([bead("leader"), bead("member", group="leader")])

    assert resolve_group("leader", reader) == ("leader", ("leader", "member"))
    assert resolve_group("member", reader) == ("leader", ("leader", "member"))


def test_plan_does_not_call_runtime_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _config = project_fixture(tmp_path)
    reader = FixtureBd([bead("leader")])
    monkeypatch.setattr(cli_module, "resolve_project_root", lambda _project: root)
    monkeypatch.setattr(
        cli_module, "project_id_from_descriptor", lambda _root: "fixture"
    )
    monkeypatch.setattr(cli_module, "SubprocessBdReader", lambda _root: reader)
    monkeypatch.setattr(
        cli_module, "call", lambda *_args: pytest.fail("--plan called runtime")
    )
    monkeypatch.setattr(
        sys, "argv", ["agentctl", "packet", "launch", "leader", "--plan"]
    )

    assert cli_module.main() == 0
    assert "PREDICTED DURATION" in capsys.readouterr().out
    assert not list((root / ".agentctl").glob("*.json"))


def test_checkout_resolution_uses_checkout_id_not_workspace_id() -> None:
    response = {
        "ok": True,
        "payload": {
            "value": {"workspace_id": "workspace-1", "checkout_id": "worktree-abc"}
        },
    }

    assert checkout_id_from_workspace_response(response) == "worktree-abc"


def test_launch_creates_then_dispatches_with_dimensions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _config = project_fixture(tmp_path)
    reader = FixtureBd([bead("leader")])
    calls = []

    def fake_call(_socket: Path, request: object) -> dict:
        calls.append(request)
        if request.operation == "workspace.create":
            return {
                "ok": True,
                "payload": {
                    "value": {
                        "workspace_id": "workspace-1",
                        "checkout_id": "worktree-abc",
                        "notes": [
                            {
                                "kind": "packet-dead-collision-recovered",
                                "workspace_id": "workspace-old",
                            }
                        ],
                    }
                },
            }
        return {"ok": True, "payload": {"value": {"job_id": "job-1"}}}

    monkeypatch.setattr(cli_module, "resolve_project_root", lambda _project: root)
    monkeypatch.setattr(
        cli_module, "project_id_from_descriptor", lambda _root: "fixture"
    )
    monkeypatch.setattr(cli_module, "SubprocessBdReader", lambda _root: reader)
    monkeypatch.setattr(cli_module, "call", fake_call)
    monkeypatch.setattr(sys, "argv", ["agentctl", "packet", "launch", "leader"])

    assert cli_module.main() == 0
    assert [request.operation for request in calls] == [
        "workspace.create",
        "job.agent.start",
    ]
    assert calls[1].arguments["checkout_id"] == "worktree-abc"
    assert calls[1].arguments["parameters"]["template_version"] == "v2"
    assert calls[1].arguments["parameters"]["dimensions"]["conflict_keys"] == [
        "area:parser",
        "area:storage",
    ]
    assert calls[0].arguments["recover_dead"] is True
    assert calls[1].arguments["parameters"]["packet_notes"][0]["kind"] == (
        "packet-dead-collision-recovered"
    )
    assert json.loads(capsys.readouterr().out)["payload"]["value"]["notes"] == [
        {
            "kind": "packet-dead-collision-recovered",
            "workspace_id": "workspace-old",
        }
    ]
