"""Prompt compilation: the bead group, the model policy, the subject, the budget."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentctl.packets import (
    MAX_PROMPT_BYTES,
    MAX_SUBJECT_LENGTH,
    PacketConfig,
    PacketError,
    bead_digest,
    bead_subject,
    compile_launch_snapshot,
    rebase_prompt,
    resolve_group,
    validate_members,
)
from conftest import FakeBd, bead


def reader() -> FakeBd:
    return FakeBd(
        beads={
            "fx-lead": bead(
                "fx-lead",
                "Lead bead",
                description="Touch polylogue/storage/schema.py",
                metadata={
                    "dispatch_group": "fx-lead",
                    "affected_paths": "core/x.py;other/y.py",
                    "verification_commands": ["devtools test core"],
                    "effort": "high",
                },
            ),
            "fx-member": bead(
                "fx-member", "Member bead", metadata={"dispatch_group": "fx-lead"}
            ),
            "fx-closed": bead(
                "fx-closed",
                "Closed member",
                status="closed",
                metadata={"dispatch_group": "fx-lead"},
            ),
            "fx-solo": bead("fx-solo", "Solo bead", issue_type="bug"),
        }
    )


def test_group_resolution_follows_dispatch_group_and_skips_closed_members() -> None:
    """A closed member's spec must not be reissued as an instruction."""
    leader, members = resolve_group("fx-member", reader())
    assert leader == "fx-lead"
    assert members == ("fx-lead", "fx-member")


def test_a_closed_leader_is_never_a_member() -> None:
    """Breaks if the leader is added to the group regardless of its status."""
    closed_lead = reader()
    closed_lead.beads["fx-lead"]["status"] = "closed"
    leader, members = resolve_group("fx-member", closed_lead)
    assert leader == "fx-lead"
    assert members == ("fx-member",)
    leader, members = resolve_group("fx-lead", closed_lead)
    assert members == ("fx-member",)
    closed_lead.beads["fx-member"]["status"] = "deferred"
    with pytest.raises(PacketError, match="no open members"):
        resolve_group("fx-lead", closed_lead)


def test_member_validation_names_every_refusal() -> None:
    """Breaks if a missing, closed, claimed, blocked or duplicated member slips into a run."""
    beads = reader()
    beads.beads["fx-claimed"] = bead("fx-claimed", "Claimed", status="in_progress") | {
        "assignee": "agent-x"
    }
    beads.beads["fx-blocked"] = bead("fx-blocked", "Blocked") | {
        "dependencies": [
            {"id": "fx-solo", "status": "open", "dependency_type": "blocks"}
        ]
    }
    beads.beads["fx-internal"] = bead("fx-internal", "Internally blocked") | {
        "dependencies": [
            {"id": "fx-lead", "status": "open", "dependency_type": "blocks"}
        ]
    }
    codes = {
        (refusal.code, refusal.bead)
        for refusal in validate_members(
            beads,
            [
                ["fx-lead", "fx-internal", "fx-missing", "fx-closed"],
                ["fx-claimed", "fx-blocked", "fx-lead", "fx-member"],
            ],
            claimed={"fx-member"},
        )
    }
    assert codes == {
        ("missing", "fx-missing"),
        ("status", "fx-closed"),
        ("claimed", "fx-claimed"),
        ("blocked", "fx-blocked"),
        ("duplicate", "fx-lead"),
        ("in_run", "fx-member"),
    }
    assert validate_members(beads, [["fx-lead", "fx-internal"]], claimed=set()) == []


def test_write_scopes_must_be_disjoint_across_workers() -> None:
    beads = reader()
    beads.beads["fx-lead"]["metadata"]["write_scope"] = ["core/", "docs/*.md"]
    beads.beads["fx-solo"]["metadata"]["write_scope"] = "core/x.py;other/"
    beads.beads["fx-member"]["metadata"]["write_scope"] = ["docs/atlas.md"]
    refusals = validate_members(
        beads, [["fx-lead"], ["fx-solo"], ["fx-member"]], claimed=set()
    )
    assert {(item.code, item.bead) for item in refusals} == {("write_scope", "fx-lead")}
    assert any("core/x.py" in item.detail for item in refusals)
    assert any("docs/atlas.md" in item.detail for item in refusals)
    # The same scopes inside one worker are fine.
    assert (
        validate_members(beads, [["fx-lead", "fx-solo", "fx-member"]], claimed=set())
        == []
    )


def test_snapshot_carries_beads_dimensions_branch_atlas_and_the_contract(
    project_root: Path,
) -> None:
    config = PacketConfig.load(project_root)

    snapshot = compile_launch_snapshot(
        "fx-lead", project_id="fixture", reader=reader(), config=config
    )

    assert snapshot.leader_id == "fx-lead"
    assert snapshot.bead_ids == ("fx-lead", "fx-member")
    assert snapshot.branch == "feature/packet/fx-lead"
    assert snapshot.dimensions.backend == "codex"
    assert snapshot.dimensions.model == "fixture-model"
    assert snapshot.dimensions.effort == "high"
    assert snapshot.dimensions.affected_paths == ("core/x.py", "other/y.py")
    assert snapshot.dimensions.verification_commands == ("devtools test core",)
    # No sheet matches the affected top-level tokens, so every sheet is offered.
    assert snapshot.atlas_refs == ("atlas/core.md",)
    assert snapshot.worker_contract_path == "contract.md"
    payload = json.loads(snapshot.prompt.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert payload["bead_ids"] == ["fx-lead", "fx-member"]
    assert "Commit by path, push, never merge." in snapshot.prompt


def test_snapshot_projects_rich_relationship_records_without_changing_dispatched_beads(
    project_root: Path,
) -> None:
    config = PacketConfig.load(project_root)
    rich = reader()
    rich.beads["fx-parent"] = bead("fx-parent", "Parent", issue_type="epic")
    rich.beads["fx-dependency"] = bead(
        "fx-dependency", "Dependency", issue_type="bug", status="in_progress"
    )
    rich.beads["fx-lead"].update(
        {
            "comments": [{"body": "Keep this context", "author": "operator"}],
            "parent": "fx-parent",
            "dependencies": [
                {
                    **rich.beads["fx-dependency"],
                    "dependency_type": "blocks",
                    "dependencies": [
                        {**rich.beads["fx-parent"], "dependency_type": "relates-to"}
                    ],
                }
            ],
        }
    )

    snapshot = compile_launch_snapshot(
        "fx-lead", project_id="fixture", reader=rich, config=config
    )

    dispatched = next(item for item in snapshot.beads if item["id"] == "fx-lead")
    assert dispatched["description"] == "Touch polylogue/storage/schema.py"
    assert dispatched["comments"] == [
        {"body": "Keep this context", "author": "operator"}
    ]
    assert dispatched["parent"] == {
        "id": "fx-parent",
        "status": "open",
        "issue_type": "epic",
        "title": "Parent",
    }
    assert dispatched["dependencies"] == [
        {
            "id": "fx-dependency",
            "status": "in_progress",
            "issue_type": "bug",
            "title": "Dependency",
            "dependency_type": "blocks",
        }
    ]
    assert len(snapshot.prompt.encode()) < MAX_PROMPT_BYTES


def test_explicit_backend_model_effort_override_the_policy(project_root: Path) -> None:
    config = PacketConfig.load(project_root)

    snapshot = compile_launch_snapshot(
        "fx-solo",
        project_id="fixture",
        reader=reader(),
        config=config,
        backend="claude",
        model="claude-opus-5",
        effort="medium",
    )

    assert (
        snapshot.dimensions.backend,
        snapshot.dimensions.model,
        snapshot.dimensions.effort,
    ) == ("claude", "claude-opus-5", "medium")


def test_codex_model_alias_resolves_before_dispatch(project_root: Path) -> None:
    config = PacketConfig.load(project_root)

    snapshot = compile_launch_snapshot(
        "fx-solo",
        project_id="fixture",
        reader=reader(),
        config=config,
        model="luna",
    )

    assert snapshot.dimensions.backend == "codex"
    assert snapshot.dimensions.model == "gpt-5.6-luna"


def test_unknown_model_alias_is_rejected_with_valid_choices(project_root: Path) -> None:
    config = PacketConfig.load(project_root)

    with pytest.raises(PacketError, match=r"unknown model alias 'moon'.*luna"):
        compile_launch_snapshot(
            "fx-solo",
            project_id="fixture",
            reader=reader(),
            config=config,
            model="moon",
        )


def test_model_backend_mismatch_is_rejected_before_dispatch(project_root: Path) -> None:
    config = PacketConfig.load(project_root)

    with pytest.raises(PacketError, match="incompatible"):
        compile_launch_snapshot(
            "fx-solo",
            project_id="fixture",
            reader=reader(),
            config=config,
            backend="claude",
            model="luna",
        )


def test_a_prompt_over_budget_embeds_digests_instead_of_bodies(
    project_root: Path,
) -> None:
    """Breaks if a large bead body is dropped silently or the digest cannot be verified."""
    config = PacketConfig.load(project_root)
    big = reader()
    big.beads["fx-solo"]["description"] = "x" * MAX_PROMPT_BYTES

    snapshot = compile_launch_snapshot(
        "fx-solo", project_id="fixture", reader=big, config=config
    )

    assert len(snapshot.prompt.encode()) <= MAX_PROMPT_BYTES
    payload = json.loads(snapshot.prompt.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert payload["bead_bodies"] == "digest"
    (entry,) = payload["beads"]
    assert entry["digest"] == bead_digest(big.beads["fx-solo"])
    assert entry["excerpt"] == "x" * 600 and entry["truncated"]
    assert "bd show <id> --json" in snapshot.prompt


def test_a_prompt_over_budget_even_as_digests_is_refused(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = PacketConfig.load(project_root)
    monkeypatch.setattr("agentctl.packets.MAX_PROMPT_BYTES", 500)

    with pytest.raises(PacketError, match="over the"):
        compile_launch_snapshot(
            "fx-solo", project_id="fixture", reader=reader(), config=config
        )


def test_explicit_members_and_branch_carry_the_batch_facts(project_root: Path) -> None:
    config = PacketConfig.load(project_root)

    snapshot = compile_launch_snapshot(
        "fx-lead",
        project_id="fixture",
        reader=reader(),
        config=config,
        member_ids=["fx-solo", "fx-lead"],
        branch="batch/run-1/fx-lead",
        batch={"run_id": "run-1", "worker_id": "fx-lead"},
    )

    assert snapshot.bead_ids == ("fx-lead", "fx-solo")
    assert snapshot.branch == "batch/run-1/fx-lead"
    assert snapshot.to_dict()["batch"] == {"run_id": "run-1", "worker_id": "fx-lead"}
    with pytest.raises(PacketError, match="not among the members"):
        compile_launch_snapshot(
            "fx-lead",
            project_id="fixture",
            reader=reader(),
            config=config,
            member_ids=["fx-solo"],
        )


def test_subject_is_type_prefixed_and_bounded() -> None:
    assert bead_subject(bead("a", "Archive reads refuse drift", issue_type="bug")) == (
        "fix: Archive reads refuse drift"
    )
    assert (
        bead_subject(bead("a", "Add lane sync", issue_type="feature"))
        == "feat: Add lane sync"
    )
    assert (
        bead_subject(bead("a", "Migrate  the\nthing", issue_type="task"))
        == "chore: Migrate the thing"
    )
    assert (
        bead_subject(bead("a", "feat(cli): already conventional"))
        == "feat(cli): already conventional"
    )
    long = bead_subject(bead("a", "word " * 40, issue_type="bug"))
    assert len(long) <= MAX_SUBJECT_LENGTH


def test_rebase_prompt_names_the_worktree_branch_and_base(project_root: Path) -> None:
    config = PacketConfig.load(project_root)

    prompt = rebase_prompt(
        config=config,
        bead=bead("fx-solo", "Solo bead"),
        branch="feature/packet/fx-solo",
        base="origin/master",
        worktree=Path("/realm/worktrees/fixture-feature-packet-fx-solo"),
    )

    assert "feature/packet/fx-solo" in prompt
    assert "origin/master" in prompt
    assert "Do not push" in prompt
    assert "Commit by path" in prompt
    with_packet = rebase_prompt(
        config=config,
        bead=bead("fx-solo", "Solo bead"),
        branch="feature/packet/fx-solo",
        base="origin/master",
        worktree=Path("/w"),
        packet="# Dispatch packet\n\noriginal",
    )
    assert "## Original dispatch packet" in with_packet and "original" in with_packet


def test_a_missing_worker_contract_is_a_typed_refusal(project_root: Path) -> None:
    config = PacketConfig.load(project_root)
    config.template_path.unlink()

    with pytest.raises(PacketError, match="worker-contract template"):
        compile_launch_snapshot(
            "fx-solo", project_id="fixture", reader=reader(), config=config
        )
