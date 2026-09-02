from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import sinnixd.cli as cli_module
from sinnixd.packets import (
    PacketConfig,
    PacketError,
    checkout_id_from_workspace_response,
    compile_launch_snapshot,
    extract_references,
    infer_conflict_keys,
    plan_table,
    resolve_group,
)


def bead(
    bead_id: str,
    *,
    group: str | None = None,
    intent: str = "ship it",
    oracle_command: str | None = None,
) -> dict:
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
    if oracle_command is not None:
        metadata["oracle_command"] = oracle_command
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
    (root / ".agentctl" / "project.toml").write_text("""
schema = 1
[project]
id = "fixture"
display_name = "Fixture"
root_markers = [".agentctl"]
[packets]
template = "dots/_ai/skills/orchestrate/references/worker-contract.md"
atlas_dir = "docs/atlas"
""")
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


def test_snapshot_carries_one_packet_oracle_command() -> None:
    config = PacketConfig(
        template_path=Path(__file__), atlas_dir=Path("/does/not/matter")
    )
    snapshot = compile_launch_snapshot(
        "leader",
        project_root=Path("/does/not/matter"),
        project_id="fixture",
        reader=FixtureBd([bead("leader", oracle_command="git status --short")]),
        config=config,
    )

    assert snapshot.dimensions.oracle_command == "git status --short"
    assert snapshot.to_dict()["dimensions"]["oracle_command"] == "git status --short"


def test_snapshot_rejects_conflicting_packet_oracle_commands() -> None:
    config = PacketConfig(
        template_path=Path(__file__), atlas_dir=Path("/does/not/matter")
    )
    reader = FixtureBd(
        [
            bead("leader", oracle_command="git status --short"),
            bead("child", group="leader", oracle_command="git diff --quiet"),
        ]
    )

    with pytest.raises(PacketError, match="one oracle_command"):
        compile_launch_snapshot(
            "leader",
            project_root=Path("/does/not/matter"),
            project_id="fixture",
            reader=reader,
            config=config,
        )


def test_reference_extraction_accepts_repo_references_and_rejects_noise() -> None:
    references = extract_references("""
        Change polylogue/cost/allocator.py and migrations/042_add_users.sql.
        The package is `polylogue.cost`; use table `users` and 'audit_log'.
        Ignore https://example.test/noise.py, /tmp/no.py, ../escape.py,
        and ordinary and/or prose.
        """)

    assert references.paths == (
        "migrations/042_add_users.sql",
        "polylogue/cost/allocator.py",
    )
    assert references.modules == ("polylogue.cost",)
    assert references.migrations == ("042",)
    assert references.tables == ("audit_log", "users")
    assert infer_conflict_keys(references) == (
        "file:polylogue/cost/allocator.py",
        "module:polylogue.cost",
        "schema:042",
        "table:audit_log",
        "table:users",
    )


def test_module_inference_rejects_address_and_host_tokens() -> None:
    """Email parts, URL hosts, and bare hostnames never become module keys
    (sinnix-8l2p). Anti-vacuity: the broad dotted-token regex emitted
    module:gmail.com and module:ezo.dev for this exact text."""
    references = extract_references("""
        Contact ezo.dev@gmail.com about the module polylogue.sources.dispatch,
        see https://api.github.com/repos for details; host gmail.com serves it.
        """)

    assert references.modules == ("polylogue.sources.dispatch",)
    keys = infer_conflict_keys(references)
    assert keys == ("module:polylogue.sources.dispatch",)


def test_snapshot_unions_inferred_keys_and_explicit_keys_win_source_label(
    tmp_path: Path,
) -> None:
    root, _config = project_fixture(tmp_path)
    row = bead("leader")
    row["description"] = (
        "Edit polylogue/cost/allocator.py, migrations/007_add_runs.sql, "
        "and table `runs`."
    )
    row["design"] = "The module is `polylogue.cost`; use table `runs`."
    row["metadata"]["conflict_keys"] = "module:polylogue.cost;table:runs;declared:lock"
    snapshot = compile_launch_snapshot(
        "leader",
        project_root=root,
        project_id="fixture",
        reader=FixtureBd([row]),
        config=_config,
    )

    assert snapshot.dimensions.conflict_keys == (
        "declared:lock",
        "file:polylogue/cost/allocator.py",
        "module:polylogue.cost",
        "schema:007",
        "table:runs",
    )
    assert snapshot.dimensions.inferred_conflict_keys == (
        "file:polylogue/cost/allocator.py",
        "schema:007",
    )
    rendered = plan_table(snapshot, _config)
    assert "schema:007 (inferred)" in rendered
    assert "file:polylogue/cost/allocator.py (inferred)" in rendered
    assert "module:polylogue.cost (inferred)" not in rendered
    assert snapshot.dimensions.to_dict()["inferred_conflict_keys"] == [
        "file:polylogue/cost/allocator.py",
        "schema:007",
    ]


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
    monkeypatch.setattr(
        sys,
        "argv",
        ["agentctl", "packet", "launch", "leader", "--coordinator-label", "wave-a"],
    )

    assert cli_module.main() == 0
    assert [request.operation for request in calls] == [
        "workspace.create",
        "job.agent.start",
    ]
    assert calls[1].arguments["checkout_id"] == "worktree-abc"
    assert calls[1].arguments["coordinator_label"] == "wave-a"
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

    assert calls[1].arguments["exclusive_keys"] == [
        "area:parser",
        "area:storage",
    ]
    assert calls[1].arguments["reject_conflicts"] is True
    assert calls[1].arguments["dimensions"]["conflict_keys"] == (
        "area:parser;area:storage"
    )


def test_launch_agent_failure_disposes_created_workspace_and_labels_step(
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
                    }
                },
            }
        if request.operation == "job.agent.start":
            return {
                "ok": False,
                "error": {
                    "code": "OWNER_UNAVAILABLE",
                    "message": "sinnixd is unavailable",
                },
            }
        assert request.operation == "workspace.dispose"
        return {"ok": True, "payload": {"value": {"disposed": True}}}

    monkeypatch.setattr(cli_module, "resolve_project_root", lambda _project: root)
    monkeypatch.setattr(
        cli_module, "project_id_from_descriptor", lambda _root: "fixture"
    )
    monkeypatch.setattr(cli_module, "SubprocessBdReader", lambda _root: reader)
    monkeypatch.setattr(cli_module, "call", fake_call)
    monkeypatch.setattr(sys, "argv", ["agentctl", "packet", "launch", "leader"])

    assert cli_module.main() == 1
    assert [request.operation for request in calls] == [
        "workspace.create",
        "job.agent.start",
        "workspace.dispose",
    ]
    response = json.loads(capsys.readouterr().out)
    assert response["error"] == {
        "code": "OWNER_UNAVAILABLE",
        "message": (
            "packet launch step job.agent.start failed (completed rollback): "
            "sinnixd is unavailable"
        ),
    }


def test_launch_workspace_lookup_failure_disposes_created_workspace(
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
                "payload": {"value": {"workspace_id": "workspace-1"}},
            }
        if request.operation == "workspace.get":
            return {
                "ok": False,
                "error": {"code": "OWNER_UNAVAILABLE", "message": "lookup lost"},
            }
        assert request.operation == "workspace.dispose"
        return {"ok": True}

    monkeypatch.setattr(cli_module, "resolve_project_root", lambda _project: root)
    monkeypatch.setattr(
        cli_module, "project_id_from_descriptor", lambda _root: "fixture"
    )
    monkeypatch.setattr(cli_module, "SubprocessBdReader", lambda _root: reader)
    monkeypatch.setattr(cli_module, "call", fake_call)
    monkeypatch.setattr(sys, "argv", ["agentctl", "packet", "launch", "leader"])

    assert cli_module.main() == 1
    assert [request.operation for request in calls] == [
        "workspace.create",
        "workspace.get",
        "workspace.dispose",
    ]
    response = json.loads(capsys.readouterr().out)
    assert response["error"]["code"] == "OWNER_UNAVAILABLE"
    assert response["error"]["message"].startswith(
        "packet launch step workspace.get failed (completed rollback):"
    )
