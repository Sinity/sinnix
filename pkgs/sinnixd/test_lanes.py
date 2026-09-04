"""Lanes: worktree + agent + PR, with wt, gh and bd replaced by recorders."""

from __future__ import annotations

import fcntl
import json
import threading
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeBd, FakePueue, bead, read_launch
from sinnixd import lanes, launch
from sinnixd.config import Config
from sinnixd.lanes import LaneError
from sinnixd.packets import PacketError
from sinnixd.projects import load_project_adapter
from sinnixd.worktrunk import Worktree, WorktrunkError


def tree(
    branch: str,
    path: Path,
    *,
    state: str = "ahead",
    dirty: bool = False,
    head: str = "abc123",
) -> Worktree:
    return Worktree(
        branch=branch, path=path, head=head, main=False, dirty=dirty, state=state
    )


def merged_pr(
    number: int, branch: str, bead_id: str, *, head: str = "abc123"
) -> dict[str, Any]:
    """A merged PR whose publication marker binds the lane it came from."""
    payload = json.dumps({"bead": bead_id, "branch": branch, "head": head})
    return {
        "number": number,
        "state": "MERGED",
        "headRefName": branch,
        "headRefOid": head,
        "title": "fix: First task",
        "body": f"<!-- sinnixd:lane-publication {payload} -->",
    }


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
    state: dict[str, Any] = {
        "calls": [],
        "prs": {},
        "pr_views": {},
        "merged_heads": set(),
        # PRs newer than every lane's, which a bounded listing returns instead.
        "newer_prs": [],
    }

    def run(argv: Any, *, cwd: Path, timeout: float = 60) -> str:
        argv = list(argv)
        state["calls"].append(argv)
        if argv[:3] == ["gh", "pr", "list"]:
            if "--head" in argv:
                pull = state["prs"].get(argv[argv.index("--head") + 1])
                return json.dumps([pull] if pull is not None else [])
            # gh lists the newest first and truncates at --limit.
            newest = list(state["newer_prs"]) + list(state["prs"].values())
            return json.dumps(newest[: int(argv[argv.index("--limit") + 1])])
        if argv[:3] == ["gh", "pr", "view"]:
            pull = state["prs"].get(argv[3])
            if pull is None:
                raise LaneError("no pull requests found for branch")
            views = state["pr_views"].get(argv[3])
            if views:
                pull = views.pop(0)
            return json.dumps(pull)
        if argv[:3] == ["gh", "pr", "create"]:
            head = argv[argv.index("--head") + 1]
            state["prs"][head] = {
                "number": 100 + len(state["prs"]),
                "url": f"https://example.test/pr/{head}",
                "state": "OPEN",
                "headRefName": head,
                "headRefOid": "abc123",
                "autoMergeRequest": None,
                "reviews": [
                    {
                        "author": {"login": "chatgpt-codex-connector"},
                        "state": "APPROVED",
                        "commit": {"oid": "abc123"},
                    }
                ],
                "comments": [],
                "reactionGroups": [],
                "title": argv[argv.index("--title") + 1],
                "body": argv[argv.index("--body") + 1],
            }
            return ""
        if argv[:3] == ["gh", "pr", "merge"]:
            for pull in state["prs"].values():
                if str(pull["number"]) == argv[3]:
                    pull["autoMergeRequest"] = {"enabledAt": "now"}
            return ""
        if argv[:3] == ["gh", "pr", "comment"]:
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
    assert argv[:2] == ["env", str(config.agent_runner)]
    assert "systemd-run" not in argv, (
        "a scope started by the agent's own command lives outside the task's, "
        "where cancelling the task cannot reach it"
    )
    assert written["scope_properties"] == ["MemoryMax=10G"]
    assert written["pool"] == lanes.AGENT_GROUP
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


def test_lane_start_resolves_model_alias_and_refuses_unknown_before_mutation(
    fake_pueue: FakePueue,
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
) -> None:
    project = load_project_adapter(project_root)

    started = lanes.lane_start(config, project, "fx-1", model="luna")
    launch = read_launch(config, fake_pueue.task(started["job"]["job_id"]))
    assert launch["argv"][launch["argv"].index("--model") + 1] == "gpt-5.6-luna"

    fake_pueue.added.clear()
    fake_wt["created"].clear()
    with pytest.raises(PacketError, match=r"unknown model alias 'moon'.*luna"):
        lanes.lane_start(config, project, "fx-2", model="moon")
    assert fake_pueue.added == []
    assert fake_wt["created"] == []


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
    monkeypatch: pytest.MonkeyPatch,
    project_root: Path,
    branch: str,
    *,
    dirty: str = "",
    events: list[str] | None = None,
    git_calls: list[tuple[str, ...]] | None = None,
    remote_head: str = "",
    push_error: str | None = None,
) -> Path:
    worktree = project_root.parent / "worktrees" / "lane"
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: elsewhere\n")
    (worktree / "marker").write_text("")
    (worktree / ".agentctl").mkdir()
    (worktree / ".agentctl" / "project.toml").write_text(
        (project_root / ".agentctl" / "project.toml").read_text()
    )

    def git(path: Path, *arguments: str, timeout: float = 60) -> str:
        if git_calls is not None:
            git_calls.append(arguments)
        if arguments[0] == "status":
            return dirty
        if arguments[0] == "symbolic-ref":
            return branch
        if arguments[0] == "rev-parse":
            if arguments[1:] == ("HEAD",):
                return "abc123"
            return str(project_root / ".git")
        if arguments[0] == "ls-remote":
            return f"{remote_head}\trefs/heads/{branch}\n" if remote_head else ""
        if arguments[0] == "push":
            if events is not None:
                events.append("push")
            if push_error is not None:
                raise LaneError(push_error)
            return ""
        raise AssertionError(arguments)

    monkeypatch.setattr(lanes, "_git", git)
    return worktree


def test_lane_publish_uses_a_new_operation_from_the_lane_descriptor(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = _git_worktree(monkeypatch, project_root, "feature/packet/fx-1")
    descriptor = worktree / ".agentctl" / "project.toml"
    descriptor_text = descriptor.read_text().replace(
        '[operations.verify_quick]\ndescription = "Fixture quick verification"\n'
        'exec = ["fixture-verify-quick"]\npool = "pytest"\nresult = "exit"\n'
        "timeout_seconds = 120\n",
        "",
    )
    descriptor.write_text(
        descriptor_text
        + "\n[operations.verify_quick]\n"
        + 'description = "Lane-only quick verification"\n'
        + 'exec = ["lane-verify-quick"]\n'
        + 'pool = "pytest"\n'
        + 'result = "exit"\n'
        + "timeout_seconds = 120\n"
    )
    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))

    published = lanes.lane_publish(config, worktree)

    assert published["verification"]["phase"] == "succeeded"
    assert fake_pueue.added[0]["label"] == "fixture:verify_quick"
    launch_input = read_launch(config, fake_pueue.task(1))
    assert launch_input["argv"][-1] == "lane-verify-quick"


def test_lane_publish_runs_the_declared_verification_sequence_and_dependencies(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = _git_worktree(monkeypatch, project_root, "feature/packet/fx-1")
    descriptor = worktree / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        .replace(
            'verification_operations = ["verify_quick"]',
            'verification_operations = ["verify_quick", "verify"]',
        )
        .replace(
            'exec = ["fixture-verify"]\npool = "pytest"',
            'exec = ["fixture-verify"]\npool = "pytest"\ndependencies = ["check"]',
        )
    )

    def succeed(task_id: int, *, timeout_seconds: float) -> dict[str, Any]:
        fake_pueue.succeed(task_id)
        return launch.job_view(fake_pueue.task(task_id))

    monkeypatch.setattr(launch, "wait", succeed)
    published = lanes.lane_publish(config, worktree)

    assert [item["label"] for item in fake_pueue.added] == [
        "fixture:verify_quick",
        "fixture:check",
        "fixture:verify",
    ]
    assert fake_pueue.added[2]["after"] == (2,)
    assert [item["name"] for item in published["verification"]["operations"]] == [
        "verify_quick",
        "verify",
    ]
    assert [item["job_id"] for item in published["verification"]["operations"]] == [
        1,
        3,
    ]


def test_lane_publish_rejects_a_checkout_that_spoofs_project_identity(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = _git_worktree(monkeypatch, project_root, "feature/packet/fx-1")
    descriptor = worktree / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace('id = "fixture"', 'id = "other"')
    )

    with pytest.raises(LaneError, match="does not match registered project fixture"):
        lanes.lane_publish(config, worktree)

    assert fake_pueue.added == []


def test_lane_publish_rejects_a_worktree_outside_registered_repositories(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = _git_worktree(monkeypatch, project_root, "feature/packet/fx-1")
    monkeypatch.setattr(
        lanes, "_project_root_of", lambda path: project_root.parent / "other"
    )

    with pytest.raises(LaneError, match="is not a configured project"):
        lanes.lane_publish(config, worktree)

    assert fake_pueue.added == []


def test_lane_publish_pushes_opens_the_pr_under_the_bead_subject_and_arms_auto_merge(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    worktree = _git_worktree(
        monkeypatch, project_root, "feature/packet/fx-1", events=events
    )

    def finish_verification(fake: FakePueue) -> None:
        assert events == []
        fake.succeed(1)

    fake_pueue.finish_when_waited(1, finish_verification)

    published = lanes.lane_publish(config, worktree)

    assert fake_pueue.added[0]["label"] == "fixture:verify_quick"
    assert fake_pueue.added[0]["command"][0] == "sinnixd-queue-run"
    assert fake_pueue.added[0]["group"] == "pytest"
    assert fake_pueue.added[0]["working_directory"] == worktree
    assert fake_pueue.waited == [1]
    assert events == ["push"]
    launch_input = read_launch(config, fake_pueue.task(1))
    assert launch_input["pool"] == "pytest"
    assert published["verification"]["job_id"] == 1
    assert published["verification"]["phase"] == "succeeded"
    create = next(
        call for call in fake_commands["calls"] if call[:3] == ["gh", "pr", "create"]
    )
    assert create[create.index("--title") + 1] == "fix: First task"
    assert create[create.index("--base") + 1] == "master"
    assert create[create.index("--head") + 1] == "feature/packet/fx-1"
    assert create[create.index("--body") + 1].endswith(
        "<!-- sinnixd:lane-publication "
        '{"bead":"fx-1","branch":"feature/packet/fx-1",'
        '"head":"abc123"} -->\n'
    )
    assert ["gh", "pr", "merge", "100", "--auto", "--squash"] in fake_commands["calls"]
    assert published["pr"] == 100 and published["created"] is True
    assert published["bead"] == "fx-1"


def test_lane_publish_does_not_treat_empty_review_decision_as_codex_verdict(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing the exact-head review gate would arm auto-merge here."""
    worktree = _git_worktree(monkeypatch, project_root, "feature/packet/fx-1")
    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))
    pending_pr = {
        "number": 100,
        "url": "u",
        "state": "OPEN",
        "headRefName": "feature/packet/fx-1",
        "headRefOid": "abc123",
        "autoMergeRequest": None,
        "reviewDecision": "",
        "statusCheckRollup": [],
        "reviews": [],
        "comments": [],
        "reactionGroups": [],
    }
    fake_commands["pr_views"]["feature/packet/fx-1"] = [pending_pr, pending_pr]
    clock = iter((0.0, 0.0, 0.0, 0.0, 2.0))
    monkeypatch.setattr(lanes, "CODEX_REVIEW_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(lanes.time, "monotonic", lambda: next(clock, 2.0))
    monkeypatch.setattr(lanes.time, "sleep", lambda _: None)

    published = lanes.lane_publish(config, worktree)

    assert published["auto_merge"] is False
    assert published["review"]["status"] == "timeout"
    assert "rerun lane publish" in published["next_action"]
    assert [
        "gh",
        "pr",
        "comment",
        "100",
        "--body",
        "@codex review",
    ] in fake_commands["calls"]
    assert not any(call[:3] == ["gh", "pr", "merge"] for call in fake_commands["calls"])


def test_lane_publish_leaves_exact_head_codex_findings_actionable(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing COMMENTED to clean would incorrectly arm auto-merge."""
    worktree = _git_worktree(monkeypatch, project_root, "feature/packet/fx-1")
    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))
    findings_pr = {
        "number": 100,
        "url": "u",
        "state": "OPEN",
        "headRefName": "feature/packet/fx-1",
        "headRefOid": "abc123",
        "autoMergeRequest": None,
        "reviewDecision": "",
        "statusCheckRollup": [],
        "reviews": [
            {
                "author": {"login": "chatgpt-codex-connector"},
                "state": "COMMENTED",
                "commit": {"oid": "abc123"},
                "body": "automated review suggestions",
            }
        ],
        "comments": [],
        "reactionGroups": [],
    }
    fake_commands["pr_views"]["feature/packet/fx-1"] = [findings_pr, findings_pr]

    published = lanes.lane_publish(config, worktree)

    assert published["auto_merge"] is False
    assert published["review"]["status"] == "findings"
    assert published["review"]["round"] == 1
    assert published["review"]["max_rounds"] == 2
    assert "fix Codex findings" in published["next_action"]
    assert not any(call[:3] == ["gh", "pr", "merge"] for call in fake_commands["calls"])


def test_lane_publish_counts_answered_codex_rounds_across_corrected_heads(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Counting only exact-head reviews would report round 1 after every push."""
    worktree = _git_worktree(monkeypatch, project_root, "feature/packet/fx-1")
    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))
    corrected_pr = {
        "number": 100,
        "url": "u",
        "state": "OPEN",
        "headRefName": "feature/packet/fx-1",
        "headRefOid": "abc123",
        "autoMergeRequest": None,
        "reviewDecision": "",
        "statusCheckRollup": [],
        "reviews": [
            {
                "author": {"login": "chatgpt-codex-connector"},
                "state": "COMMENTED",
                "commit": {"oid": "def456"},
            },
            {
                "author": {"login": "chatgpt-codex-connector"},
                "state": "COMMENTED",
                "commit": {"oid": "abc123"},
            },
        ],
        "comments": [],
        "reactionGroups": [],
    }
    fake_commands["pr_views"]["feature/packet/fx-1"] = [corrected_pr, corrected_pr]

    published = lanes.lane_publish(config, worktree)

    assert published["auto_merge"] is False
    assert published["review"]["status"] == "findings"
    assert published["review"]["round"] == 2
    assert published["review"]["head"] == "abc123"
    assert "exhausted" in published["next_action"]
    assert not any(call[:3] == ["gh", "pr", "merge"] for call in fake_commands["calls"])


def test_lane_publish_does_not_count_a_clean_earlier_codex_head_as_a_round(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Counting every earlier review would exhaust the rounds after one finding."""
    worktree = _git_worktree(monkeypatch, project_root, "feature/packet/fx-1")
    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))
    findings_after_clean_pr = {
        "number": 100,
        "url": "u",
        "state": "OPEN",
        "headRefName": "feature/packet/fx-1",
        "headRefOid": "abc123",
        "autoMergeRequest": None,
        "reviewDecision": "",
        "statusCheckRollup": [],
        "reviews": [
            {
                "author": {"login": "chatgpt-codex-connector"},
                "state": "COMMENTED",
                "commit": {"oid": "def456"},
            },
            {
                "author": {"login": "chatgpt-codex-connector"},
                "state": "COMMENTED",
                "commit": {"oid": "abc123"},
            },
        ],
        "comments": [
            {
                "author": {"login": "chatgpt-codex-connector"},
                "body": (
                    "Reviewed commit: " + chr(96) + "def456" + chr(96) + "\n"
                    "I didn't find any major issues."
                ),
            }
        ],
        "reactionGroups": [],
    }
    fake_commands["pr_views"]["feature/packet/fx-1"] = [
        findings_after_clean_pr,
        findings_after_clean_pr,
    ]

    published = lanes.lane_publish(config, worktree)

    assert published["review"]["status"] == "findings"
    assert published["review"]["round"] == 1
    assert "fix Codex findings" in published["next_action"]


def test_lane_publish_accepts_a_clean_exact_head_codex_reaction(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = _git_worktree(monkeypatch, project_root, "feature/packet/fx-1")
    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))
    clean_pr = {
        "number": 100,
        "url": "u",
        "state": "OPEN",
        "headRefName": "feature/packet/fx-1",
        "headRefOid": "abc123",
        "autoMergeRequest": None,
        "reviewDecision": "",
        "statusCheckRollup": [],
        "reviews": [
            {
                "author": {"login": "chatgpt-codex-connector[bot]"},
                "state": "COMMENTED",
                "commit": {"oid": "abc123"},
            }
        ],
        "comments": [
            {
                "author": {"login": "chatgpt-codex-connector[bot]"},
                "body": (
                    "<!-- codex-pull-request-review-summary -->\n"
                    "Reviewed commit: " + chr(96) + "abc123" + chr(96)
                ),
            }
        ],
        "reactionGroups": [{"content": "THUMBS_UP", "users": {"totalCount": 1}}],
    }
    fake_commands["pr_views"]["feature/packet/fx-1"] = [clean_pr, clean_pr]

    published = lanes.lane_publish(config, worktree)

    assert published["auto_merge"] is True
    assert published["review"]["status"] == "clean"
    assert [
        "gh",
        "pr",
        "merge",
        "100",
        "--auto",
        "--squash",
    ] in fake_commands["calls"]


def test_lane_publish_reuses_an_open_pr_and_reads_the_lane_body(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
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
    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))

    published = lanes.lane_publish(config, worktree)

    assert not any(
        call[:3] == ["gh", "pr", "create"] for call in fake_commands["calls"]
    )
    assert not any(call[:3] == ["gh", "pr", "merge"] for call in fake_commands["calls"])
    assert published["pr"] == 7 and published["created"] is False


def test_lane_publish_reports_reviewable_pr_when_auto_merge_is_unavailable(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = _git_worktree(monkeypatch, project_root, "feature/packet/fx-1")
    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))

    original_run = fake_commands["calls"]
    run = lanes._run

    def fail_auto_merge(argv: Any, *, cwd: Path, timeout: float = 60) -> str:
        if list(argv)[:3] == ["gh", "pr", "merge"]:
            original_run.append(list(argv))
            raise LaneError("protected branch rules are not configured")
        return run(argv, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(lanes, "_run", fail_auto_merge)

    published = lanes.lane_publish(config, worktree)

    assert published["pr"] == 100
    assert published["auto_merge"] is False
    assert published["next_action"] == "gh pr merge 100 --squash"
    assert ["gh", "pr", "merge", "100", "--auto", "--squash"] in original_run


def test_lane_publish_recognizes_github_unconfigured_branch_rules_error() -> None:
    assert lanes._auto_merge_unavailable(
        LaneError("GraphQL: Pull request Protected branch rules not configured")
    )


def test_lane_publish_uses_the_observed_remote_head_as_a_force_push_lease(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remote_head = "1" * 40
    git_calls: list[tuple[str, ...]] = []
    worktree = _git_worktree(
        monkeypatch,
        project_root,
        "feature/packet/fx-2",
        remote_head=remote_head,
        git_calls=git_calls,
    )
    fake_commands["prs"]["feature/packet/fx-2"] = {
        "number": 7,
        "url": "u",
        "state": "OPEN",
        "headRefName": "feature/packet/fx-2",
        "autoMergeRequest": {"enabledAt": "x"},
    }
    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))

    lanes.lane_publish(config, worktree)

    push = next(call for call in git_calls if call[0] == "push")
    assert "--force-with-lease=refs/heads/feature/packet/fx-2:" + remote_head in push


def test_lane_publish_refuses_when_the_remote_head_lease_is_rejected(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remote_head = "2" * 40
    worktree = _git_worktree(
        monkeypatch,
        project_root,
        "feature/packet/fx-2",
        remote_head=remote_head,
        push_error="remote ref has changed",
    )
    fake_commands["prs"]["feature/packet/fx-2"] = {
        "number": 7,
        "url": "u",
        "state": "OPEN",
        "headRefName": "feature/packet/fx-2",
        "autoMergeRequest": {"enabledAt": "x"},
    }
    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))

    with pytest.raises(LaneError, match="remote ref has changed"):
        lanes.lane_publish(config, worktree)

    assert not any(
        call[:3] == ["gh", "pr", "create"] for call in fake_commands["calls"]
    )
    assert not any(call[:3] == ["gh", "pr", "merge"] for call in fake_commands["calls"])


def test_lane_publish_refuses_a_dirty_worktree_but_ignores_lane_artifacts(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
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
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = _git_worktree(monkeypatch, project_root, "wip/anything")
    with pytest.raises(LaneError, match="--bead or --title"):
        lanes.lane_publish(config, worktree)

    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))
    published = lanes.lane_publish(config, worktree, title="chore: hand-written")
    create = next(
        call for call in fake_commands["calls"] if call[:3] == ["gh", "pr", "create"]
    )
    assert create[create.index("--title") + 1] == "chore: hand-written"
    assert published["bead"] is None


def test_lane_publish_blocks_publication_when_quick_verification_fails(
    fake_commands: dict[str, Any],
    fake_pueue: FakePueue,
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed pueue receipt must leave push and GitHub publication untouched."""
    events: list[str] = []
    worktree = _git_worktree(
        monkeypatch, project_root, "feature/packet/fx-1", events=events
    )
    fake_pueue.finish_when_waited(1, lambda fake: fake.fail(1, exit_code=1))

    with pytest.raises(LaneError, match="quick verification task 1 did not succeed"):
        lanes.lane_publish(config, worktree)

    assert fake_pueue.added[0]["label"] == "fixture:verify_quick"
    assert fake_pueue.waited == [1]
    assert events == []
    assert fake_commands["calls"] == []


def test_lane_sync_closes_and_removes_merged_lanes_and_reports_the_rest(
    fake_pueue: FakePueue,
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
        "feature/packet/fx-1": merged_pr(1, "feature/packet/fx-1", "fx-1"),
        "feature/packet/fx-2": {
            "number": 2,
            "state": "MERGED",
            "headRefName": "feature/packet/fx-2",
            "headRefOid": "abc123",
            "title": "feat: Second task",
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
        "merged (PR #1)",
    ] in fake_commands["calls"]
    remaining = {row["branch"]: row for row in synced["remaining"]}
    assert remaining["feature/packet/fx-2"]["reason"].startswith("merged but")
    assert remaining["feature/packet/fx-3"]["pr_state"] == "OPEN"


def test_lane_sync_does_not_reuse_a_historical_merged_pr_for_a_new_branch_head(
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    """A branch-name match is informational when the PR merged an older head."""
    project = load_project_adapter(project_root)
    fake_wt["trees"] = [tree("feature/packet/fx-1", tmp_path / "a")]
    fake_commands["prs"] = {
        "feature/packet/fx-1": {
            "number": 9,
            "state": "MERGED",
            "headRefName": "feature/packet/fx-1",
            "headRefOid": "historical-head",
        }
    }

    synced = lanes.lane_sync(config, project)

    assert synced["closed"] == []
    assert synced["removed"] == []
    assert fake_wt["removed"] == []
    remaining = synced["remaining"]
    assert len(remaining) == 1
    assert remaining[0]["branch"] == "feature/packet/fx-1"
    assert remaining[0]["reason"] == "merged PR does not match the current branch head"


def test_lane_sync_does_not_close_a_bead_for_another_beads_merged_pr(
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    """A reused branch can have another bead's exact merged head."""
    project = load_project_adapter(project_root)
    fake_wt["trees"] = [tree("feature/packet/fx-1", tmp_path / "a", state="integrated")]
    fake_commands["prs"] = {
        "feature/packet/fx-1": {
            "number": 4670,
            "state": "MERGED",
            "headRefName": "feature/packet/fx-1",
            "headRefOid": "abc123",
            "title": "fix: Second task",
            "body": (
                "<!-- sinnixd:lane-publication "
                '{"bead":"fx-2","branch":"feature/packet/fx-1",'
                '"head":"abc123"} -->'
            ),
        }
    }

    synced = lanes.lane_sync(config, project)

    assert synced["closed"] == []
    assert synced["removed"] == []
    assert fake_wt["removed"] == []
    assert synced["remaining"][0]["reason"] == (
        "merged PR does not bind the current bead"
    )


def test_lane_sync_removes_a_clean_worktree_for_the_current_merged_pr_head(
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    project = load_project_adapter(project_root)
    fake_wt["trees"] = [tree("feature/packet/fx-1", tmp_path / "a")]
    fake_commands["prs"] = {
        "feature/packet/fx-1": {
            "number": 9,
            "state": "MERGED",
            "headRefName": "feature/packet/fx-1",
            "headRefOid": "abc123",
            "title": "fix: First task",
        }
    }

    synced = lanes.lane_sync(config, project)

    assert synced["closed"] == ["fx-1"]
    assert synced["removed"] == ["feature/packet/fx-1"]


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
    fake_pueue: FakePueue,
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
    fake_commands["prs"] = {
        "feature/packet/fx-1": merged_pr(1, "feature/packet/fx-1", "fx-1"),
        "feature/packet/fx-2": merged_pr(2, "feature/packet/fx-2", "fx-2"),
    }

    synced = lanes.lane_sync(config, project)

    assert synced["removed"] == ["feature/packet/fx-2"]
    assert synced["closed"] == ["fx-2"]
    locked = next(row for row in synced["remaining"] if row["branch"].endswith("fx-1"))
    assert "locked" in locked["reason"]


def test_lane_sync_leaves_a_lane_alone_while_its_agent_job_runs(
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    """Complete merge evidence does not license cleanup under a running agent."""
    project = load_project_adapter(project_root)
    fake_wt["trees"] = [tree("feature/packet/fx-1", tmp_path / "a")]
    fake_commands["prs"] = {
        "feature/packet/fx-1": merged_pr(9, "feature/packet/fx-1", "fx-1")
    }
    task_id = fake_pueue.add(
        group="agent",
        label="fixture:lane:fx-1",
        command=["agent"],
        working_directory=tmp_path / "a",
    )

    synced = lanes.lane_sync(config, project)

    assert synced["closed"] == []
    assert synced["removed"] == []
    assert fake_wt["removed"] == []
    assert not [call for call in fake_commands["calls"] if call[:2] == ["bd", "close"]]
    assert synced["remaining"][0]["reason"] == (
        f"job {task_id} (fixture:lane:fx-1) is running"
    )

    fake_pueue.succeed(task_id)
    finished = lanes.lane_sync(config, project)

    assert finished["closed"] == ["fx-1"]
    assert finished["removed"] == ["feature/packet/fx-1"]


def test_lane_sync_leaves_an_active_empty_branch_alone(
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    """A branch an agent has not committed to yet reads as integrated: no content
    of its own is missing from master."""
    project = load_project_adapter(project_root)
    fake_wt["trees"] = [tree("feature/packet/fx-1", tmp_path / "a", state="integrated")]
    task_id = fake_pueue.add(
        group="agent",
        label="fixture:lane:fx-1",
        command=["agent"],
        working_directory=tmp_path / "a",
    )

    synced = lanes.lane_sync(config, project)

    assert synced["closed"] == []
    assert synced["removed"] == []
    assert fake_wt["removed"] == []
    assert not [call for call in fake_commands["calls"] if call[:2] == ["bd", "close"]]
    assert synced["remaining"][0]["reason"] == (
        f"job {task_id} (fixture:lane:fx-1) is running"
    )


def test_lane_sync_leaves_a_worktree_owned_by_an_unlabelled_task_alone(
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    project = load_project_adapter(project_root)
    lane_path = tmp_path / "a"
    fake_wt["trees"] = [tree("feature/packet/fx-1", lane_path, state="integrated")]
    task_id = fake_pueue.add(
        group="agent",
        label="",
        command=["agent"],
        working_directory=lane_path,
    )

    synced = lanes.lane_sync(config, project)

    assert synced["closed"] == []
    assert synced["removed"] == []
    assert fake_wt["removed"] == []
    assert synced["remaining"][0]["reason"] == f"job {task_id} () is running"


def test_lane_sync_leaves_an_active_lane_whose_base_merged_under_an_old_pr(
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    """The lane's base commit is contained in an earlier round's merge commit, so
    every merge test the branch itself can answer says landed."""
    project = load_project_adapter(project_root)
    fake_wt["trees"] = [
        tree(
            "feature/packet/fx-1",
            tmp_path / "a",
            state="integrated",
            head="base-commit",
        )
    ]
    fake_commands["prs"] = {
        "feature/packet/fx-1": {
            "number": 9,
            "state": "MERGED",
            "headRefName": "feature/packet/fx-1",
            "headRefOid": "earlier-head",
            "mergeCommit": {"oid": "merge-commit"},
            "title": "fix: First task",
        }
    }
    task_id = fake_pueue.add(
        group="agent",
        label="fixture:rebase:fx-1",
        command=["agent"],
        working_directory=tmp_path / "a",
    )

    synced = lanes.lane_sync(config, project)

    assert synced["closed"] == []
    assert synced["removed"] == []
    assert fake_wt["removed"] == []
    assert synced["remaining"][0]["reason"] == (
        f"job {task_id} (fixture:rebase:fx-1) is running"
    )

    fake_pueue.succeed(task_id)
    finished = lanes.lane_sync(config, project)

    assert finished["removed"] == ["feature/packet/fx-1"]


def test_lane_sync_keeps_an_integrated_branch_that_no_merged_pr_published(
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    """wt's integrated verdict alone is not a publication: no PR merged this bead."""
    project = load_project_adapter(project_root)
    fake_wt["trees"] = [tree("feature/packet/fx-1", tmp_path / "a", state="integrated")]

    synced = lanes.lane_sync(config, project)

    assert synced["closed"] == []
    assert synced["removed"] == []
    assert fake_wt["removed"] == []
    assert not [call for call in fake_commands["calls"] if call[:2] == ["bd", "close"]]
    assert synced["remaining"][0]["reason"] == (
        "branch integrated but no merged PR publishes this bead"
    )


def test_lane_sync_closes_a_merged_lane_its_publication_marker_binds(
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    project = load_project_adapter(project_root)
    fake_wt["trees"] = [tree("feature/packet/fx-1", tmp_path / "a", state="integrated")]
    fake_commands["prs"] = {
        "feature/packet/fx-1": merged_pr(9, "feature/packet/fx-1", "fx-1")
    }
    fake_pueue.succeed(
        fake_pueue.add(
            group="agent",
            label="fixture:lane:fx-1",
            command=["agent"],
            working_directory=tmp_path / "a",
        )
    )

    synced = lanes.lane_sync(config, project)

    assert synced["closed"] == ["fx-1"]
    assert synced["removed"] == ["feature/packet/fx-1"]
    assert synced["remaining"] == []


def test_lane_sync_refuses_when_the_queue_cannot_say_which_lanes_are_active(
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    project = load_project_adapter(project_root)
    fake_wt["trees"] = [tree("feature/packet/fx-1", tmp_path / "a", state="integrated")]
    fake_commands["prs"] = {
        "feature/packet/fx-1": merged_pr(9, "feature/packet/fx-1", "fx-1")
    }
    fake_pueue.fail_tasks = True

    with pytest.raises(LaneError, match="pueue"):
        lanes.lane_sync(config, project)

    assert fake_wt["removed"] == []


def test_lane_sync_resolves_a_merged_pr_older_than_the_listing_window(
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    """A lane whose PR merged before 300 newer ones is still a published lane."""
    project = load_project_adapter(project_root)
    fake_wt["trees"] = [tree("feature/packet/fx-1", tmp_path / "a", state="integrated")]
    fake_commands["prs"] = {
        "feature/packet/fx-1": merged_pr(9, "feature/packet/fx-1", "fx-1")
    }
    fake_commands["newer_prs"] = [
        {
            "number": 1000 + index,
            "state": "MERGED",
            "headRefName": f"feature/packet/other-{index}",
            "headRefOid": "other-head",
            "title": "fix: Another task",
        }
        for index in range(300)
    ]

    synced = lanes.lane_sync(config, project)

    assert synced["closed"] == ["fx-1"]
    assert synced["removed"] == ["feature/packet/fx-1"]
    assert [
        call
        for call in fake_commands["calls"]
        if call[:3] == ["gh", "pr", "list"]
        and "--head" in call
        and call[call.index("--head") + 1] == "feature/packet/fx-1"
    ]


def test_lane_sync_leaves_a_lane_started_after_its_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    """The sweep's rows are a snapshot: the lane they describe can be removed and
    started again, with a new agent, before the sweep reaches it."""
    project = load_project_adapter(project_root)
    fake_wt["trees"] = [tree("feature/packet/fx-1", tmp_path / "a", state="integrated")]
    fake_commands["prs"] = {
        "feature/packet/fx-1": merged_pr(9, "feature/packet/fx-1", "fx-1")
    }
    listing = lanes.worktrunk.worktrunk_list

    def worktrunk_list(root: Path, *, full: bool = False) -> tuple[Worktree, ...]:
        snapshot = listing(root, full=full)
        if not fake_pueue.added:
            fake_wt["trees"] = []
            lanes.lane_start(config, project, "fx-1")
        return snapshot

    monkeypatch.setattr(lanes.worktrunk, "worktrunk_list", worktrunk_list)

    synced = lanes.lane_sync(config, project)

    started = fake_wt["created"][0]
    assert started["path"].is_dir()
    assert [item.branch for item in fake_wt["trees"]] == ["feature/packet/fx-1"]
    assert fake_wt["removed"] == []
    assert synced["closed"] == []
    assert synced["removed"] == []
    assert synced["remaining"][0]["reason"] == (
        f"job {fake_pueue.added[0]['task_id']} (fixture:lane:fx-1) is running"
    )


def test_lane_sync_waits_for_a_lane_start_that_holds_the_lane_lock(
    monkeypatch: pytest.MonkeyPatch,
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    """A start creates the worktree before it queues the agent. A sweep that read
    the queue in that window would find the lane unowned and remove it."""
    project = load_project_adapter(project_root)
    branch = "feature/packet/fx-1"
    created = threading.Event()
    queue_the_agent = threading.Event()
    creating = lanes.worktrunk.worktrunk_create

    def worktrunk_create(
        root: Path, name: str, *, path: Path, base: str | None = None
    ) -> Worktree:
        worktree = creating(root, name, path=path, base=base)
        created.set()
        queue_the_agent.wait(10)
        return worktree

    monkeypatch.setattr(lanes.worktrunk, "worktrunk_create", worktrunk_create)
    starting = threading.Thread(target=lanes.lane_start, args=(config, project, "fx-1"))
    starting.start()
    try:
        assert created.wait(10)
        # What the sweep sees: this lane's worktree, a merged PR that binds it,
        # and an agent that is not in the queue yet.
        fake_wt["trees"] = [tree(branch, tmp_path / "a", state="integrated")]
        fake_commands["prs"] = {branch: merged_pr(9, branch, "fx-1")}
        synced: list[dict[str, Any]] = []
        sweeping = threading.Thread(
            target=lambda: synced.append(lanes.lane_sync(config, project))
        )
        sweeping.start()
        sweeping.join(0.5)
        assert fake_wt["removed"] == [], "swept a lane a start still held"
    finally:
        queue_the_agent.set()
    starting.join(10)
    sweeping.join(10)

    assert not sweeping.is_alive()
    assert fake_wt["removed"] == []
    assert synced[0]["removed"] == []
    assert synced[0]["remaining"][0]["reason"] == (
        f"job {fake_pueue.added[0]['task_id']} (fixture:lane:fx-1) is running"
    )


def test_lane_sync_reports_a_lane_another_operation_holds(
    monkeypatch: pytest.MonkeyPatch,
    fake_pueue: FakePueue,
    fake_commands: dict[str, Any],
    fake_wt: dict[str, Any],
    fake_bd: FakeBd,
    config: Config,
    project_root: Path,
    tmp_path: Path,
) -> None:
    """A lane the sweep cannot take is reported; waiting for it is not forever."""
    project = load_project_adapter(project_root)
    branch = "feature/packet/fx-1"
    fake_wt["trees"] = [tree(branch, tmp_path / "a", state="integrated")]
    fake_commands["prs"] = {branch: merged_pr(9, branch, "fx-1")}
    monkeypatch.setattr(lanes, "LANE_LOCK_WAIT_SECONDS", 0.2)
    held = lanes.lane_lock_path(config, project, branch)
    held.parent.mkdir(parents=True, exist_ok=True)

    with held.open("a") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        synced = lanes.lane_sync(config, project)

    assert fake_wt["removed"] == []
    assert synced["closed"] == []
    assert synced["removed"] == []
    assert synced["remaining"][0]["reason"] == (
        f"another lane operation holds {branch}"
    )
