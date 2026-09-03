"""Lanes: worktree + agent + PR, with wt, gh and bd replaced by recorders."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeBd, FakePueue, bead, read_launch
from sinnixd import lanes
from sinnixd.config import Config
from sinnixd.lanes import LaneError
from sinnixd.projects import load_project_adapter
from sinnixd.worktrunk import Worktree, WorktrunkError


def tree(
    branch: str, path: Path, *, state: str = "ahead", dirty: bool = False
) -> Worktree:
    return Worktree(
        branch=branch, path=path, head="abc123", main=False, dirty=dirty, state=state
    )


@pytest.fixture
def fake_wt(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"trees": [], "created": [], "removed": []}

    def worktrunk_list(root: Path, *, full: bool = False) -> tuple[Worktree, ...]:
        return tuple(state["trees"])

    def worktrunk_find(root: Path, branch: str) -> Worktree | None:
        return next((item for item in state["trees"] if item.branch == branch), None)

    def worktrunk_create(
        root: Path, branch: str, *, path: Path, base: str | None = None
    ) -> Worktree:
        path.mkdir(parents=True)
        created = tree(branch, path)
        state["trees"].append(created)
        state["created"].append({"branch": branch, "path": path, "base": base})
        return created

    def worktrunk_remove(root: Path, branch: str, *, force: bool = False) -> None:
        if branch in state.get("locked", ()):
            raise WorktrunkError(f"Cannot remove {branch}, worktree is locked")
        state["removed"].append(branch)
        state["trees"] = [item for item in state["trees"] if item.branch != branch]

    monkeypatch.setattr(lanes.worktrunk, "worktrunk_list", worktrunk_list)
    monkeypatch.setattr(lanes.worktrunk, "worktrunk_find", worktrunk_find)
    monkeypatch.setattr(lanes.worktrunk, "worktrunk_create", worktrunk_create)
    monkeypatch.setattr(lanes.worktrunk, "worktrunk_remove", worktrunk_remove)
    return state


@pytest.fixture
def fake_bd(monkeypatch: pytest.MonkeyPatch) -> FakeBd:
    fake = FakeBd(
        beads={
            "fx-1": bead("fx-1", "First task", issue_type="bug"),
            "fx-2": bead("fx-2", "Second task", issue_type="feature"),
            "fx-3": bead("fx-3", "Third task"),
            "fx-epic": bead("fx-epic", "An epic", issue_type="epic"),
        }
    )
    monkeypatch.setattr(lanes, "SubprocessBdReader", lambda root: fake)
    return fake


@pytest.fixture
def fake_commands(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Records gh/git/bd invocations; answers `gh` reads from `prs`."""
    state: dict[str, Any] = {"calls": [], "prs": {}, "merged_heads": set()}

    def run(argv: Any, *, cwd: Path, timeout: float = 60) -> str:
        argv = list(argv)
        state["calls"].append(argv)
        if argv[:3] == ["gh", "pr", "list"]:
            return json.dumps(list(state["prs"].values()))
        if argv[:3] == ["gh", "pr", "view"]:
            pull = state["prs"].get(argv[3])
            if pull is None:
                raise LaneError("no pull requests found for branch")
            return json.dumps(pull)
        if argv[:3] == ["gh", "pr", "create"]:
            head = argv[argv.index("--head") + 1]
            state["prs"][head] = {
                "number": 100 + len(state["prs"]),
                "url": f"https://example.test/pr/{head}",
                "state": "OPEN",
                "headRefName": head,
                "autoMergeRequest": None,
                "title": argv[argv.index("--title") + 1],
            }
            return ""
        if argv[:3] == ["gh", "pr", "merge"]:
            for pull in state["prs"].values():
                if str(pull["number"]) == argv[3]:
                    pull["autoMergeRequest"] = {"enabledAt": "now"}
            return ""
        if argv[:2] == ["bd", "close"]:
            state.setdefault("closed", []).append(argv[2])
            return ""
        return ""

    monkeypatch.setattr(lanes, "_run", run)
    return state


def test_lane_start_creates_the_worktree_and_queues_a_bounded_agent_scope(
    fake_pueue: FakePueue,
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
) -> None:
    """Breaks if the agent leaves the job plane, loses its memory ceiling, or the
    prompt stops reaching the worktree."""
    project = load_project_adapter(project_root)

    started = lanes.lane_start(config, project, "fx-1")

    created = fake_wt["created"][0]
    assert created["branch"] == "feature/packet/fx-1"
    assert created["path"] == project.workspace.root / "fixture-feature-packet-fx-1"
    assert created["base"] == "origin/master"
    added = fake_pueue.added[0]
    assert added["group"] == "agent"
    assert added["label"] == "fixture:lane:fx-1"
    written = read_launch(config, fake_pueue.task(started["job"]["job_id"]))
    argv = written["argv"]
    assert argv[:3] == ["env", "systemd-run", "--user"]
    assert "--scope" in argv
    assert f"--slice={lanes.AGENT_SLICE}" in argv
    assert "MemoryMax=10G" in argv
    runner_index = argv.index(str(config.agent_runner))
    runner_args = argv[runner_index + 1 :]
    assert runner_args[runner_args.index("--agent") + 1] == "codex"
    assert runner_args[runner_args.index("--model") + 1] == "fixture-model"
    assert runner_args[runner_args.index("--reasoning-effort") + 1] == "low"
    prompt_path = Path(runner_args[runner_args.index("--prompt-file") + 1])
    assert prompt_path == created["path"] / ".lane" / "prompt.md"
    assert prompt_path.stat().st_mode & 0o777 == 0o600
    assert "fx-1" in prompt_path.read_text()
    assert written["environment"]["BEADS_ACTOR"] == "agent-fx-1"
    assert written["result_kind"] == "last-message"
    assert written["timeout_seconds"] == lanes.MAX_AGENT_TIMEOUT_SECONDS
    assert started["worktree"] == str(created["path"])
    assert started["job"]["kind"] == "attested-agent"


def test_lane_start_refuses_a_bead_that_already_has_a_worktree(
    fake_pueue: FakePueue,
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
) -> None:
    project = load_project_adapter(project_root)
    fake_wt["trees"].append(tree("feature/packet/fx-1", project_root.parent / "wt"))

    with pytest.raises(LaneError, match="already has a worktree"):
        lanes.lane_start(config, project, "fx-1")
    assert fake_pueue.added == []


def test_lane_start_refuses_without_an_executable_runner(
    fake_pueue: FakePueue,
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
) -> None:
    config.agent_runner.chmod(0o644)
    project = load_project_adapter(project_root)

    with pytest.raises(LaneError, match="agent runner is unavailable"):
        lanes.lane_start(config, project, "fx-1")


def test_lane_rebase_queues_into_the_existing_worktree(
    fake_pueue: FakePueue,
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    project = load_project_adapter(project_root)
    worktree = tmp_path / "worktrees" / "fixture-feature-packet-fx-2"
    worktree.mkdir(parents=True)
    fake_wt["trees"].append(tree("feature/packet/fx-2", worktree))

    rebased = lanes.lane_rebase(
        config, project, "fx-2", model="gpt-5.6-terra", effort="high"
    )

    added = fake_pueue.added[0]
    assert added["label"] == "fixture:rebase:fx-2"
    assert added["working_directory"] == worktree
    prompt = (worktree / ".lane" / "rebase-prompt.md").read_text()
    assert "origin/master" in prompt and "fx-2" in prompt
    written = read_launch(config, fake_pueue.task(rebased["job"]["job_id"]))
    assert "gpt-5.6-terra" in written["argv"] and "high" in written["argv"]


def test_lane_rebase_refuses_without_a_worktree(
    fake_pueue: FakePueue,
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
) -> None:
    project = load_project_adapter(project_root)
    with pytest.raises(LaneError, match="has no worktree"):
        lanes.lane_rebase(config, project, "fx-2")


def _git_worktree(
    monkeypatch: pytest.MonkeyPatch, project_root: Path, branch: str, *, dirty: str = ""
) -> Path:
    worktree = project_root.parent / "worktrees" / "lane"
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: elsewhere\n")

    def git(path: Path, *arguments: str, timeout: float = 60) -> str:
        if arguments[0] == "status":
            return dirty
        if arguments[0] == "symbolic-ref":
            return branch
        if arguments[0] == "rev-parse":
            return str(project_root / ".git")
        if arguments[0] == "push":
            return ""
        raise AssertionError(arguments)

    monkeypatch.setattr(lanes, "_git", git)
    return worktree


def test_lane_publish_pushes_opens_the_pr_under_the_bead_subject_and_arms_auto_merge(
    fake_commands: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = _git_worktree(monkeypatch, project_root, "feature/packet/fx-1")

    published = lanes.lane_publish(config, worktree)

    create = next(
        call for call in fake_commands["calls"] if call[:3] == ["gh", "pr", "create"]
    )
    assert create[create.index("--title") + 1] == "fix: First task"
    assert create[create.index("--base") + 1] == "master"
    assert create[create.index("--head") + 1] == "feature/packet/fx-1"
    assert ["gh", "pr", "merge", "100", "--auto", "--squash"] in fake_commands["calls"]
    assert published["pr"] == 100 and published["created"] is True
    assert published["bead"] == "fx-1"


def test_lane_publish_reuses_an_open_pr_and_reads_the_lane_body(
    fake_commands: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = _git_worktree(monkeypatch, project_root, "feature/packet/fx-2")
    (worktree / ".lane").mkdir()
    (worktree / ".lane" / "body.md").write_text("Summary written by the lane\n")
    fake_commands["prs"]["feature/packet/fx-2"] = {
        "number": 7,
        "url": "u",
        "state": "OPEN",
        "headRefName": "feature/packet/fx-2",
        "autoMergeRequest": {"enabledAt": "x"},
    }

    published = lanes.lane_publish(config, worktree)

    assert not any(
        call[:3] == ["gh", "pr", "create"] for call in fake_commands["calls"]
    )
    assert not any(call[:3] == ["gh", "pr", "merge"] for call in fake_commands["calls"])
    assert published["pr"] == 7 and published["created"] is False


def test_lane_publish_refuses_a_dirty_worktree_but_ignores_lane_artifacts(
    fake_commands: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uncommitted work would be silently absent from the PR."""
    worktree = _git_worktree(
        monkeypatch,
        project_root,
        "feature/packet/fx-1",
        dirty=" M src/a.py\n?? .lane/prompt.md\n",
    )
    with pytest.raises(LaneError, match="src/a.py"):
        lanes.lane_publish(config, worktree)
    assert fake_commands["calls"] == []


def test_lane_publish_needs_a_bead_or_a_title_for_a_foreign_branch(
    fake_commands: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = _git_worktree(monkeypatch, project_root, "wip/anything")
    with pytest.raises(LaneError, match="--bead or --title"):
        lanes.lane_publish(config, worktree)

    published = lanes.lane_publish(config, worktree, title="chore: hand-written")
    create = next(
        call for call in fake_commands["calls"] if call[:3] == ["gh", "pr", "create"]
    )
    assert create[create.index("--title") + 1] == "chore: hand-written"
    assert published["bead"] is None


def test_lane_sync_closes_and_removes_merged_lanes_and_reports_the_rest(
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    project = load_project_adapter(project_root)
    fake_wt["trees"] = [
        tree("feature/packet/fx-1", tmp_path / "a", state="integrated"),
        tree("feature/packet/fx-2", tmp_path / "b", state="ahead", dirty=True),
        tree("feature/packet/fx-3", tmp_path / "c", state="ahead"),
        Worktree(
            branch="master",
            path=project_root,
            head="m",
            main=True,
            dirty=False,
            state="main",
        ),
    ]
    fake_commands["prs"] = {
        "feature/packet/fx-2": {
            "number": 2,
            "state": "MERGED",
            "headRefName": "feature/packet/fx-2",
        },
        "feature/packet/fx-3": {
            "number": 3,
            "state": "OPEN",
            "headRefName": "feature/packet/fx-3",
        },
    }

    synced = lanes.lane_sync(config, project)

    assert synced["closed"] == ["fx-1"]
    assert synced["removed"] == ["feature/packet/fx-1"]
    assert fake_wt["removed"] == ["feature/packet/fx-1"]
    assert [
        "bd",
        "close",
        "fx-1",
        "--force",
        "--actor",
        "agentctl",
        "--reason",
        "merged (branch integrated)",
    ] in fake_commands["calls"]
    remaining = {row["branch"]: row for row in synced["remaining"]}
    assert remaining["feature/packet/fx-2"]["reason"].startswith("merged but")
    assert remaining["feature/packet/fx-3"]["pr_state"] == "OPEN"


def test_refill_starts_ready_beads_without_a_worktree_or_pr_up_to_the_limit(
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    """Epics, beads with a worktree, and beads with an open PR are never re-dispatched."""
    project = load_project_adapter(project_root)
    fake_wt["trees"] = [tree("feature/packet/fx-1", tmp_path / "a")]
    fake_commands["prs"] = {
        "feature/packet/fx-2": {
            "number": 2,
            "state": "OPEN",
            "headRefName": "feature/packet/fx-2",
        }
    }

    planned = lanes.refill(config, project, limit=5, dry_run=True)
    assert planned["candidates"] == ["fx-3"]
    assert planned["started"] == []

    done = lanes.refill(config, project, limit=1)
    assert [row["bead"] for row in done["started"]] == ["fx-3"]
    assert fake_pueue.added[0]["label"] == "fixture:lane:fx-3"


def test_lane_sync_reports_a_locked_worktree_and_continues(
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    """Anti-vacuity: a sweep that stops at the first wt refusal removes fx-2 only if fx-1 is unlocked."""
    project = load_project_adapter(project_root)
    fake_wt["trees"] = [
        tree("feature/packet/fx-1", tmp_path / "a", state="integrated"),
        tree("feature/packet/fx-2", tmp_path / "b", state="integrated"),
    ]
    fake_wt["locked"] = {"feature/packet/fx-1"}

    synced = lanes.lane_sync(config, project)

    assert synced["removed"] == ["feature/packet/fx-2"]
    assert synced["closed"] == ["fx-2"]
    locked = next(row for row in synced["remaining"] if row["branch"].endswith("fx-1"))
    assert "locked" in locked["reason"]
