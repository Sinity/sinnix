"""Batches: start once, land exactly, close only from the acceptance record."""

from __future__ import annotations

import fcntl
import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest
from agentctl import batch, github, launch, worktrunk
from agentctl.batch import BatchError, BatchRefusal
from agentctl.config import Config
from agentctl.projects import ProjectAdapter, load_project_adapter
from agentctl.pueue import PueueError
from agentctl.worktrunk import Worktree, WorktrunkError
from conftest import FakeBd, FakePueue, bead, read_launch

BASE = "b" * 40
SHA = "c" * 40
MOVED = "d" * 40
MOVED_AGAIN = "e" * 40


@dataclass
class FakeBeads(FakeBd):
    """FakeBd plus the four writes a batch makes; a claim held by another actor refuses."""

    claims: list[tuple[str, str]] = field(default_factory=list)
    released: list[tuple[str, str]] = field(default_factory=list)
    closed: list[tuple[str, str, str]] = field(default_factory=list)
    comments: list[tuple[str, str]] = field(default_factory=list)
    refuse_close: set[str] = field(default_factory=set)

    def claim(self, bead_id: str, *, actor: str) -> None:
        record = self.beads[bead_id]
        holder = record.get("assignee")
        if holder and holder != actor:
            raise BatchError(f"bd update {bead_id}: already claimed by {holder}")
        record["assignee"] = actor
        record["status"] = "in_progress"
        self.claims.append((bead_id, actor))

    def unclaim(self, bead_id: str, *, actor: str) -> None:
        record = self.beads[bead_id]
        if record.get("assignee") == actor:
            record["assignee"] = None
            record["status"] = "open"
        self.released.append((bead_id, actor))

    def close(self, bead_id: str, *, reason: str, actor: str) -> None:
        if bead_id in self.refuse_close:
            raise BatchError(f"bd close {bead_id}: refused")
        self.beads[bead_id]["status"] = "closed"
        self.closed.append((bead_id, reason, actor))

    def comment(self, bead_id: str, text: str, *, actor: str) -> None:
        self.comments.append((bead_id, text))


def beads() -> FakeBeads:
    return FakeBeads(
        beads={
            "fx-lead": bead("fx-lead", "Lead", metadata={"dispatch_group": "fx-lead"}),
            "fx-member": bead(
                "fx-member", "Member", metadata={"dispatch_group": "fx-lead"}
            ),
            "fx-solo": bead("fx-solo", "Solo", issue_type="bug"),
            "fx-other": bead("fx-other", "Other"),
        }
    )


@dataclass
class FakeGit:
    heads: dict[str, str] = field(default_factory=dict)
    merges: list[str] = field(default_factory=list)
    pushes: list[tuple[str, ...]] = field(default_factory=list)
    conflict_on: set[str] = field(default_factory=set)
    remote_bases: list[str] = field(default_factory=lambda: [BASE])
    push_rejects: int = 0
    push_rejection: str = "! [rejected] master -> master (stale info)"
    resets: list[str] = field(default_factory=list)
    # Commits that do not descend from the base commit.
    off_base: set[str] = field(default_factory=set)
    ancestry: list[tuple[str, str]] = field(default_factory=list)

    def __call__(self, path: Path, *arguments: str, timeout: float = 60) -> str:
        verb = arguments[0]
        if verb == "fetch":
            return ""
        if verb == "rev-parse":
            if arguments[1] == "HEAD":
                return self.heads.get(str(path), SHA)
            if arguments[-1].startswith("refs/remotes/origin/"):
                return (
                    self.remote_bases.pop(0)
                    if len(self.remote_bases) > 1
                    else self.remote_bases[0]
                )
            return BASE
        if verb == "merge" and arguments[1] == "--abort":
            raise BatchError("git merge: no merge to abort")
        if verb == "merge":
            branch = arguments[-1]
            self.merges.append(branch)
            if branch in self.conflict_on:
                self.conflict_on.discard(branch)
                raise BatchError("git merge: CONFLICT (content)")
            return ""
        if verb == "reset":
            self.resets.append(arguments[-1])
            return ""
        if verb == "diff":
            return "a.py\nb.py"
        if verb == "status":
            return ""
        if verb == "merge-base":
            if arguments[1] == "--is-ancestor":
                ancestor, descendant = arguments[2], arguments[3]
                self.ancestry.append((ancestor, descendant))
                if descendant in self.off_base:
                    raise BatchError("merge-base: not an ancestor")
            return ""
        if verb == "push":
            if self.push_rejects:
                self.push_rejects -= 1
                raise BatchError(f"git push: {self.push_rejection}")
            self.pushes.append(arguments)
            return ""
        raise AssertionError(arguments)


@dataclass
class FakeWorktrunk:
    trees: dict[str, Worktree] = field(default_factory=dict)
    removed: list[str] = field(default_factory=list)
    refuse_remove: set[str] = field(default_factory=set)
    fail_create: set[str] = field(default_factory=set)

    def find(self, root: Path, branch: str) -> Worktree | None:
        return self.trees.get(branch)

    def create(
        self, root: Path, branch: str, *, path: Path, base: str | None = None
    ) -> Worktree:
        if branch in self.fail_create:
            raise WorktrunkError(f"wt refused {branch}")
        path.mkdir(parents=True, exist_ok=True)
        tree = Worktree(
            branch=branch,
            path=path,
            head=base or "",
            main=False,
            dirty=False,
            state="ahead",
        )
        self.trees[branch] = tree
        return tree

    def remove(self, root: Path, branch: str, *, force: bool = False) -> None:
        if branch in self.refuse_remove:
            raise WorktrunkError(f"{branch} is locked")
        self.trees.pop(branch, None)
        self.removed.append(branch)


@dataclass
class Harness:
    config: Config
    project: ProjectAdapter
    pueue: FakePueue
    beads: FakeBeads
    git: FakeGit
    wt: FakeWorktrunk
    verdict: dict[str, Any]
    waited: list[int] = field(default_factory=list)

    def start(self, *seeds: str, **kwargs: Any) -> dict[str, Any]:
        return batch.start(
            self.config, self.project, list(seeds), reader=self.beads, **kwargs
        )

    def land(self, run_id: str) -> dict[str, Any]:
        return batch.land(
            self.config, self.project, run_id, beads=self.beads, sleep=lambda _s: None
        )

    def file_result(
        self, run: dict[str, Any], worker_id: str, **overrides: Any
    ) -> dict[str, Any]:
        worker = next(item for item in run["workers"] if item["id"] == worker_id)
        document = worker_result(worker["beads"], **overrides)
        path = Path(worker["worktree"]) / ".lane" / "prompt.result.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(document))
        return batch.result(self.config, run["run_id"], worker_id, path)


def worker_result(
    bead_ids: list[str], *, unsatisfied: set[str] = frozenset(), sha: str = SHA
) -> dict[str, Any]:
    return {
        "candidate_sha": sha,
        "beads": [
            {
                "id": bead_id,
                "criteria": [
                    {
                        "text": "done",
                        "status": "unsatisfied"
                        if bead_id in unsatisfied
                        else "satisfied",
                        "evidence": "pytest -q: 3 passed",
                    }
                ],
            }
            for bead_id in bead_ids
        ],
        "unresolved": [],
        "verification": [{"command": "pytest -q", "receipt": "3 passed"}],
    }


def verdict(**overrides: Any) -> dict[str, Any]:
    return {
        "verdict": "pass",
        "confidence": 0.9,
        "evidence": ["diff read"],
        "refutation_attempted": True,
        "unsupported": [],
        **overrides,
    }


@pytest.fixture
def harness(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Harness:
    project = load_project_adapter(project_root)
    git = FakeGit()
    wt = FakeWorktrunk()
    fake_pueue.groups["fixture-land"] = 1
    monkeypatch.setattr(batch, "_git", git)
    monkeypatch.setattr(worktrunk, "worktrunk_find", wt.find)
    monkeypatch.setattr(worktrunk, "worktrunk_create", wt.create)
    monkeypatch.setattr(worktrunk, "worktrunk_remove", wt.remove)
    built = Harness(
        config=config,
        project=project,
        pueue=fake_pueue,
        beads=beads(),
        git=git,
        wt=wt,
        verdict=verdict(),
    )

    def wait(job_id: int, *, timeout_seconds: float) -> dict[str, Any]:
        """Every waited task succeeds; a review task also leaves its verdict."""
        built.waited.append(job_id)
        task = fake_pueue.task(job_id)
        assert task is not None
        if ":review:" in task.label:
            (Path(task.path) / ".lane" / "review.result.json").write_text(
                json.dumps(built.verdict)
            )
        fake_pueue.succeed(job_id)
        return launch.job_view(fake_pueue.task(job_id))

    monkeypatch.setattr(launch, "wait", wait)
    return built


def labels(fake: FakePueue) -> list[str]:
    return [entry["label"] for entry in fake.added]


# ---------------------------------------------------------------- start


def test_start_claims_creates_worktrees_and_queues_workers_then_the_landing(
    harness: Harness,
) -> None:
    """Breaks if a worker runs unclaimed, off its base, or without the landing behind it."""
    run = harness.start("fx-lead", "fx-solo")

    assert run["prepared"] and run["base_commit"] == BASE
    assert [worker["beads"] for worker in run["workers"]] == [
        ["fx-lead", "fx-member"],
        ["fx-solo"],
    ]
    assert {item[0] for item in harness.beads.claims} == {
        "fx-lead",
        "fx-member",
        "fx-solo",
    }
    assert all(
        actor == f"agentctl-batch-{run['run_id']}"
        for _bead, actor in harness.beads.claims
    )
    assert harness.beads.beads["fx-lead"]["status"] == "in_progress"
    lead = run["workers"][0]
    assert lead["branch"] == f"batch/{run['run_id']}/fx-lead"
    assert Path(lead["worktree"]).name == f"fixture-batch-{run['run_id']}-fx-lead"
    assert harness.wt.trees[lead["branch"]].head == BASE
    prompt = (Path(lead["worktree"]) / ".lane" / "prompt.md").read_text()
    payload = json.loads(prompt.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert payload["batch"]["run_id"] == run["run_id"] and payload["batch"][
        "result_path"
    ].endswith("prompt.result.json")
    assert json.loads(
        (Path(lead["worktree"]) / ".lane" / "worker.schema.json").read_text()
    )["required"]
    assert labels(harness.pueue) == [
        f"fixture:worker:{run['run_id']}:fx-lead",
        f"fixture:worker:{run['run_id']}:fx-solo",
        f"fixture:land:{run['run_id']}",
    ]
    worker_task = harness.pueue.task(lead["task_id"])
    assert worker_task is not None and worker_task.group == "agent"
    argv = read_launch(harness.config, worker_task)["argv"]
    assert argv[:3] == ["env", "bash", "-c"]
    assert "--output-schema" in argv and argv[3].endswith(
        f"batch result {run['run_id']} fx-lead {lead['worktree']}/.lane/prompt.result.json"
    )
    landing = harness.pueue.task(run["landing"]["task_id"])
    assert landing is not None
    assert landing.group == "fixture-land"
    assert landing.dependencies == (
        run["workers"][0]["task_id"],
        run["workers"][1]["task_id"],
    )
    assert landing.status == "Running"
    assert read_launch(harness.config, landing)["argv"][-3:] == [
        "batch",
        "land",
        run["run_id"],
    ]
    manifest = json.loads(
        batch.manifest_path(harness.config, run["run_id"]).read_text()
    )
    assert manifest["workers"][0]["task_id"] == lead["task_id"]
    assert manifest["workers"][0]["claimed_beads"] == ["fx-lead", "fx-member"]
    assert launch.get_job(lead["task_id"], harness.config)["binding"] == {
        "beads": ["fx-lead", "fx-member"],
        "run_id": run["run_id"],
        "worker": "fx-lead",
    }


def test_start_is_idempotent_for_the_same_members(harness: Harness) -> None:
    first = harness.start("fx-lead")
    again = harness.start("fx-member")
    assert (
        again["run_id"] == first["run_id"]
        and again["existing"]
        and not again["resumed"]
    )
    assert len(harness.pueue.added) == 2
    assert len(harness.beads.claims) == 2


def test_start_completes_a_run_left_half_prepared(harness: Harness) -> None:
    """Breaks if recovery launches a second task graph for the same manifest."""
    run = harness.start("fx-solo")
    manifest_path = batch.manifest_path(harness.config, run["run_id"])
    document = json.loads(manifest_path.read_text())
    document["prepared"] = False
    document["landing"]["task_id"] = None
    manifest_path.write_text(json.dumps(document))

    resumed = harness.start("fx-solo")
    assert (
        resumed["run_id"] == run["run_id"]
        and resumed["resumed"]
        and resumed["prepared"]
    )
    assert resumed["workers"][0]["task_id"] == run["workers"][0]["task_id"]
    assert labels(harness.pueue) == [
        f"fixture:worker:{run['run_id']}:fx-solo",
        f"fixture:land:{run['run_id']}",
        f"fixture:land:{run['run_id']}",
    ]
    assert len(harness.beads.claims) == 1


def test_a_failed_start_releases_its_claims_and_removes_its_manifest(
    harness: Harness,
) -> None:
    harness.pueue.fail_add = True
    with pytest.raises(PueueError):
        harness.start("fx-lead")
    assert {item[0] for item in harness.beads.released} == {"fx-lead", "fx-member"}
    assert harness.beads.beads["fx-lead"]["status"] == "open"
    assert batch.list_runs(harness.config) == []
    assert harness.wt.trees == {} and len(harness.wt.removed) == 1
    assert [path.name for path in batch.runs_dir(harness.config).iterdir()] == [
        "fixture.lock"
    ]


def test_two_starts_on_the_same_member_are_refused_by_the_claim(
    harness: Harness,
) -> None:
    first = harness.start("fx-solo")
    with pytest.raises(BatchRefusal, match="already in another run") as refused:
        harness.start("fx-solo", "fx-other")
    assert refused.value.to_dict()["refusals"][0]["code"] == "in_run"
    assert batch.list_runs(harness.config)[0].run_id == first["run_id"]

    # A claim taken outside agentctl between validation and preparation.
    harness.beads.beads["fx-other"]["assignee"] = "someone-else"
    harness.beads.beads["fx-other"]["status"] = "in_progress"
    with pytest.raises(BatchRefusal, match="claimed by someone-else"):
        harness.start("fx-other")
    harness.beads.beads["fx-other"]["status"] = "open"
    original = harness.beads.claim

    def race(bead_id: str, *, actor: str) -> None:
        harness.beads.beads[bead_id]["assignee"] = "racer"
        original(bead_id, actor=actor)

    harness.beads.claim = race  # type: ignore[method-assign]
    with pytest.raises(BatchError, match="already claimed by racer"):
        harness.start("fx-other")
    assert len(batch.list_runs(harness.config)) == 1
    assert not any(
        str(record.get("assignee") or "").startswith("agentctl-batch-")
        for bead_id, record in harness.beads.beads.items()
        if bead_id != "fx-solo"
    )


def test_a_claim_failing_mid_worker_releases_the_beads_already_claimed(
    harness: Harness,
) -> None:
    original = harness.beads.claim

    def second_claim_races(bead_id: str, *, actor: str) -> None:
        if bead_id == "fx-member":
            harness.beads.beads[bead_id]["assignee"] = "racer"
        original(bead_id, actor=actor)

    harness.beads.claim = second_claim_races  # type: ignore[method-assign]
    with pytest.raises(BatchError, match="already claimed by racer"):
        harness.start("fx-lead")

    assert [item[0] for item in harness.beads.released] == ["fx-lead"]
    assert harness.beads.beads["fx-lead"]["assignee"] is None
    assert harness.beads.beads["fx-lead"]["status"] == "open"
    assert harness.beads.beads["fx-member"]["assignee"] == "racer"
    assert batch.list_runs(harness.config) == []


def test_start_takes_the_project_lock_around_worktree_creation(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two starts cannot race `wt`: creation happens under runs/<project>.lock."""
    held: set[str] = set()
    seen: list[set[str]] = []
    real_flock = fcntl.flock

    def flock(handle: Any, operation: int) -> None:
        path = os.readlink(f"/proc/self/fd/{handle.fileno()}")
        if operation == fcntl.LOCK_EX:
            held.add(path)
        else:
            held.discard(path)
        real_flock(handle, operation)

    create = harness.wt.create

    def observed_create(root: Path, branch: str, **kwargs: Any) -> Worktree:
        seen.append(set(held))
        return create(root, branch, **kwargs)

    monkeypatch.setattr(batch.fcntl, "flock", flock)
    monkeypatch.setattr(worktrunk, "worktrunk_create", observed_create)

    harness.start("fx-solo")

    lock = str(batch.project_lock_path(harness.config, "fixture"))
    assert lock.endswith("/runs/fixture.lock")
    assert seen and all(lock in locks for locks in seen)
    assert lock not in held


def test_a_closed_leader_is_excluded_and_a_blocked_member_refused(
    harness: Harness,
) -> None:
    harness.beads.beads["fx-lead"]["status"] = "closed"
    run = harness.start("fx-member")
    assert run["workers"][0]["beads"] == ["fx-member"]
    assert run["workers"][0]["id"] == "fx-member"

    harness.beads.beads["fx-solo"]["dependencies"] = [
        {"id": "fx-other", "status": "open", "dependency_type": "blocks"}
    ]
    with pytest.raises(BatchRefusal, match="blocked by fx-other"):
        harness.start("fx-solo")
    assert harness.beads.beads["fx-solo"].get("assignee") is None


def test_explicit_workers_and_external_harness_stash_the_landing(
    harness: Harness,
) -> None:
    run = harness.start(
        workers=[["fx-solo", "fx-other"], ["fx-lead"]], harness="external"
    )
    assert [w["beads"] for w in run["workers"]] == [
        ["fx-solo", "fx-other"],
        ["fx-lead"],
    ]
    assert all(w["task_id"] is None for w in run["workers"])
    assert labels(harness.pueue) == [f"fixture:land:{run['run_id']}"]
    landing = harness.pueue.task(run["landing"]["task_id"])
    assert (
        landing is not None
        and landing.status == "Stashed"
        and landing.dependencies == ()
    )
    assert (Path(run["workers"][1]["worktree"]) / ".lane" / "prompt.md").is_file()

    with pytest.raises(BatchRefusal, match="filed no valid result"):
        harness.land(run["run_id"])
    filed = harness.file_result(run, "fx-solo")
    assert not filed["landing_released"]
    filed = harness.file_result(run, "fx-lead")
    assert filed["landing_released"] and harness.pueue.enqueued == [landing.task_id]
    assert harness.pueue.task(landing.task_id).status == "Queued"


# ---------------------------------------------------------------- result / resume


def test_result_validates_and_binds_to_the_worktree_head(harness: Harness) -> None:
    run = harness.start("fx-solo")
    worker = run["workers"][0]
    bad = Path(worker["worktree"]) / "bad.json"
    bad.write_text(json.dumps({"candidate_sha": "x"}))
    with pytest.raises(BatchRefusal, match="invalid_result"):
        batch.result(harness.config, run["run_id"], "fx-solo", bad)
    with pytest.raises(BatchRefusal, match="candidate_mismatch"):
        harness.file_result(run, "fx-solo", sha=MOVED)
    with pytest.raises(BatchRefusal, match="foreign_beads"):
        path = Path(worker["worktree"]) / "foreign.json"
        path.write_text(json.dumps(worker_result(["fx-other"])))
        batch.result(harness.config, run["run_id"], "fx-solo", path)
    filed = harness.file_result(run, "fx-solo")
    assert filed["result"]["candidate_sha"] == SHA
    assert (
        batch.load(harness.config, run["run_id"]).workers[0]["result"]["beads"][0]["id"]
        == "fx-solo"
    )


def test_resume_requeues_the_worker_and_a_landing_behind_it(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = harness.start("fx-lead", "fx-solo")
    monkeypatch.setattr(batch, "SubprocessBeads", lambda root: harness.beads)
    lead_task = run["workers"][0]["task_id"]
    with pytest.raises(BatchRefusal, match="worker_active"):
        batch.resume(harness.config, harness.project, run["run_id"], "fx-lead")
    harness.pueue.fail(lead_task, exit_code=1)
    harness.pueue.succeed(run["workers"][1]["task_id"])
    harness.pueue.dependency_fail(run["landing"]["task_id"])

    resumed = batch.resume(
        harness.config, harness.project, run["run_id"], "fx-lead", effort="high"
    )

    worker = resumed["workers"][0]
    assert worker["task_id"] == resumed["job"]["job_id"] and worker["task_ids"] == [
        lead_task,
        worker["task_id"],
    ]
    assert resumed["job"]["label"] == f"fixture:worker:{run['run_id']}:fx-lead".replace(
        "worker", "resume"
    )
    prompt = (Path(worker["worktree"]) / ".lane" / "prompt.md").read_text()
    assert (
        prompt.startswith("# Resume packet") and "## Original dispatch packet" in prompt
    )
    argv = read_launch(harness.config, harness.pueue.task(worker["task_id"]))["argv"]
    assert argv[argv.index("--reasoning-effort") + 1] == "high"
    assert read_launch(harness.config, harness.pueue.task(worker["task_id"]))[
        "binding"
    ] == {
        "beads": ["fx-lead", "fx-member"],
        "run_id": run["run_id"],
        "worker": "fx-lead",
    }
    assert harness.pueue.removed == [run["landing"]["task_id"]]
    landing = harness.pueue.task(resumed["landing"]["task_id"])
    assert landing is not None and landing.dependencies == (
        worker["task_id"],
        run["workers"][1]["task_id"],
    )


# ---------------------------------------------------------------- land


def prepared_run(
    harness: Harness, *seeds: str, unsatisfied: set[str] = frozenset()
) -> dict[str, Any]:
    run = harness.start(*seeds)
    for worker in run["workers"]:
        harness.pueue.succeed(worker["task_id"])
        harness.file_result(run, worker["id"], unsatisfied=unsatisfied)
    return batch.load(harness.config, run["run_id"]).to_dict()


def test_land_refuses_until_every_worker_succeeded_with_a_result(
    harness: Harness,
) -> None:
    run = harness.start("fx-lead", "fx-solo")
    with pytest.raises(BatchRefusal, match="worker_not_done"):
        harness.land(run["run_id"])
    harness.pueue.fail(run["workers"][0]["task_id"], exit_code=1)
    with pytest.raises(BatchRefusal, match="worker_failed"):
        harness.land(run["run_id"])
    harness.pueue.succeed(run["workers"][0]["task_id"])
    harness.pueue.succeed(run["workers"][1]["task_id"])
    with pytest.raises(BatchRefusal, match="worker_result_missing"):
        harness.land(run["run_id"])
    assert batch.load(harness.config, run["run_id"]).landing["failure"] is None
    assert harness.git.merges == []


def test_land_integrates_verifies_reviews_publishes_and_closes_satisfied_members(
    harness: Harness,
) -> None:
    """Breaks if a member closes without every criterion satisfied, or the push skips its lease."""
    run = prepared_run(harness, "fx-lead", "fx-solo", unsatisfied={"fx-member"})
    run_id = run["run_id"]

    landed = harness.land(run_id)

    integration = f"batch/{run_id}/integration"
    assert harness.wt.trees.get(integration) is None
    assert harness.git.merges == [f"batch/{run_id}/fx-lead", f"batch/{run_id}/fx-solo"]
    verify = landed["landing"]["verify_run"]
    assert verify["operation"] == "check" and verify["candidate_sha"] == SHA
    verify_task = harness.pueue.task(verify["job_id"])
    assert verify_task.label == "fixture:check"
    assert verify_task.path.endswith(f"fixture-batch-{run_id}-integration")
    review = landed["landing"]["review_verdict"]
    assert review["verdict"] == "pass" and review["candidate_sha"] == SHA
    review_task = harness.pueue.task(review["job_id"])
    assert review_task.label == f"fixture:review:{run_id}"
    assert read_launch(harness.config, review_task)["argv"][-1].endswith(
        "judge.schema.json"
    )
    assert read_launch(harness.config, review_task)["binding"] == {
        "beads": ["fx-lead", "fx-member", "fx-solo"],
        "run_id": run_id,
        "worker": None,
    }
    assert harness.git.pushes == [
        (
            "push",
            f"--force-with-lease=refs/heads/master:{BASE}",
            "origin",
            f"{SHA}:refs/heads/master",
        )
    ]
    acceptance = landed["acceptance"]
    assert (
        acceptance["candidate_sha"] == SHA
        and acceptance["published"]["policy"] == "master"
    )
    assert {bead: state["state"] for bead, state in acceptance["members"].items()} == {
        "fx-lead": "closed",
        "fx-member": "open",
        "fx-solo": "closed",
    }
    assert [(item[0], item[1]) for item in harness.beads.closed] == [
        ("fx-lead", f"batch {run_id} {SHA}"),
        ("fx-solo", f"batch {run_id} {SHA}"),
    ]
    assert (
        harness.beads.comments[0][0] == "fx-member"
        and "without satisfying" in harness.beads.comments[0][1]
    )
    assert sorted(harness.wt.removed) == sorted(
        [f"batch/{run_id}/fx-solo", integration]
    )
    assert acceptance["residual"] == [
        f"batch/{run_id}/fx-lead: worktree kept; fx-member still open"
    ]
    assert acceptance["advisory"] == []
    with pytest.raises(BatchRefusal, match="already_accepted"):
        harness.land(run_id)


def test_a_failed_close_keeps_that_worker_worktree_and_removes_the_rest(
    harness: Harness,
) -> None:
    run = prepared_run(harness, "fx-lead", "fx-solo")
    run_id = run["run_id"]
    harness.beads.refuse_close = {"fx-solo"}

    landed = harness.land(run_id)

    members = landed["acceptance"]["members"]
    assert members["fx-solo"]["state"] == "open"
    assert "close failed" in members["fx-solo"]["evidence"]
    assert members["fx-lead"]["state"] == "closed"
    assert sorted(harness.wt.removed) == sorted(
        [f"batch/{run_id}/fx-lead", f"batch/{run_id}/integration"]
    )
    assert f"batch/{run_id}/fx-solo" in harness.wt.trees
    assert landed["acceptance"]["residual"] == [
        f"batch/{run_id}/fx-solo: worktree kept; fx-solo still open"
    ]


def test_cleanup_failure_is_a_residual_and_never_undoes_a_close(
    harness: Harness,
) -> None:
    run = prepared_run(harness, "fx-solo")
    harness.wt.refuse_remove = {f"batch/{run['run_id']}/fx-solo"}
    harness.beads.refuse_close = set()

    landed = harness.land(run["run_id"])

    assert landed["acceptance"]["members"]["fx-solo"]["state"] == "closed"
    assert landed["acceptance"]["residual"] == [
        f"batch/{run['run_id']}/fx-solo: batch/{run['run_id']}/fx-solo is locked"
    ]
    assert harness.beads.beads["fx-solo"]["status"] == "closed"


def test_a_conflict_runs_one_integration_agent_and_requires_every_branch_merged(
    harness: Harness,
) -> None:
    run = prepared_run(harness, "fx-lead", "fx-solo")
    harness.git.conflict_on = {f"batch/{run['run_id']}/fx-solo"}

    landed = harness.land(run["run_id"])

    integrate = [label for label in labels(harness.pueue) if ":integrate:" in label]
    assert integrate == [f"fixture:integrate:{run['run_id']}"]
    task = next(t for t in harness.pueue.tasks().values() if t.label == integrate[0])
    prompt = (Path(task.path) / ".lane" / "integrate.md").read_text()
    assert "- a.py" in prompt and f"batch/{run['run_id']}/fx-solo" in prompt
    assert landed["acceptance"]["candidate_sha"] == SHA


def test_a_rejected_review_records_the_failure_and_closes_nothing(
    harness: Harness,
) -> None:
    run = prepared_run(harness, "fx-solo")
    harness.verdict = verdict(
        verdict="fail", evidence=["tests mirror the implementation"]
    )

    with pytest.raises(BatchRefusal, match="review_rejected"):
        harness.land(run["run_id"])

    stored = batch.load(harness.config, run["run_id"])
    assert stored.acceptance is None
    assert stored.landing["failure"]["code"] == "review_rejected"
    assert stored.landing["verify_run"]["phase"] == "succeeded"
    assert harness.beads.closed == [] and harness.git.pushes == []
    assert harness.beads.beads["fx-solo"]["status"] == "in_progress"


def test_an_invalid_verdict_is_a_refusal(harness: Harness) -> None:
    run = prepared_run(harness, "fx-solo")
    harness.verdict = {"verdict": "pass"}
    with pytest.raises(BatchRefusal, match="review_invalid"):
        harness.land(run["run_id"])


def test_target_moved_once_refreshes_and_twice_stops(harness: Harness) -> None:
    """Breaks if a moved master is published over, or refreshed without end."""
    run = prepared_run(harness, "fx-solo")
    harness.git.remote_bases = [MOVED, MOVED, MOVED]

    landed = harness.land(run["run_id"])

    assert landed["landing"]["refreshes"] == 1
    assert harness.git.resets == [MOVED]
    assert harness.git.merges == [f"batch/{run['run_id']}/fx-solo"] * 2
    assert len([label for label in labels(harness.pueue) if ":review:" in label]) == 2
    assert harness.git.pushes[-1][1] == f"--force-with-lease=refs/heads/master:{MOVED}"
    assert landed["acceptance"]["published"]["base_commit"] == MOVED

    second = prepared_run(harness, "fx-other")
    harness.git.remote_bases = [MOVED, MOVED, MOVED_AGAIN, MOVED_AGAIN]
    with pytest.raises(BatchRefusal, match="target_moved_twice"):
        harness.land(second["run_id"])
    stored = batch.load(harness.config, second["run_id"])
    assert stored.landing["failure"]["code"] == "target_moved_twice"
    assert stored.landing["refreshes"] == 1 and stored.acceptance is None
    assert harness.beads.beads["fx-other"]["status"] == "in_progress"


@pytest.mark.parametrize(
    "rejection",
    [
        "! [rejected] master -> master (stale info)",
        "! [rejected] master -> master (fetch first)",
    ],
)
def test_a_push_lease_rejection_counts_as_target_movement(
    harness: Harness, rejection: str
) -> None:
    run = prepared_run(harness, "fx-solo")
    harness.git.remote_bases = [BASE, MOVED, MOVED]
    harness.git.push_rejects = 1
    harness.git.push_rejection = rejection
    landed = harness.land(run["run_id"])
    assert (
        landed["landing"]["refreshes"] == 1
        and landed["acceptance"]["published"]["base_commit"] == MOVED
    )


def test_a_push_rejected_for_any_other_reason_is_a_publish_refusal(
    harness: Harness,
) -> None:
    """A protected branch or a hook rejects the same push again; no refresh."""
    run = prepared_run(harness, "fx-solo")
    harness.git.push_rejects = 1
    harness.git.push_rejection = (
        "! [remote rejected] master -> master (protected branch hook declined)"
    )
    with pytest.raises(BatchRefusal, match="publish_rejected") as refused:
        harness.land(run["run_id"])
    assert "protected branch hook declined" in refused.value.detail
    stored = batch.load(harness.config, run["run_id"])
    assert stored.landing["refreshes"] == 0
    assert stored.landing["failure"]["code"] == "publish_rejected"
    assert stored.acceptance is None and harness.beads.closed == []


def test_a_registered_integration_branch_without_a_directory_is_recreated(
    harness: Harness, tmp_path: Path
) -> None:
    run = prepared_run(harness, "fx-solo")
    integration = f"batch/{run['run_id']}/integration"
    harness.wt.trees[integration] = Worktree(
        branch=integration,
        path=tmp_path / "gone",
        head=BASE,
        main=False,
        dirty=False,
        state="ahead",
    )

    landed = harness.land(run["run_id"])

    assert landed["acceptance"]["candidate_sha"] == SHA
    assert harness.wt.removed[0] == integration
    assert harness.git.resets == []

    second = prepared_run(harness, "fx-other")
    stale = f"batch/{second['run_id']}/integration"
    harness.wt.trees[stale] = Worktree(
        branch=stale, path=None, head=BASE, main=False, dirty=False, state="ahead"
    )
    harness.wt.refuse_remove = {stale}
    with pytest.raises(BatchRefusal, match="integration_worktree_missing"):
        harness.land(second["run_id"])


def test_pr_policy_pushes_the_branch_waits_for_required_checks_and_merges_the_head(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    descriptor = harness.project.descriptor
    descriptor.write_text(
        descriptor.read_text()
        .replace('publish = "master"', 'publish = "pr"')
        .replace('candidate = "check"', 'candidate = "hosted:verify"')
    )
    harness.project = load_project_adapter(harness.project.root)
    calls: list[tuple[str, Any]] = []
    rollups = iter(["pending", "ready"])

    def pull(root: Path, number: int) -> dict[str, Any]:
        calls.append(("pull", number))
        return {
            "number": number,
            "state": "OPEN",
            "headRefOid": SHA,
            "statusCheckRollup": [],
        }

    monkeypatch.setattr(
        github,
        "push_branch",
        lambda root, branch, *, sha, lease, timeout=0: calls.append(
            ("push", branch, sha, lease)
        ),
    )
    monkeypatch.setattr(github, "remote_head", lambda root, branch: None)
    monkeypatch.setattr(github, "pull_request", pull)
    monkeypatch.setattr(github, "pull_request_for_branch", lambda root, branch: None)
    monkeypatch.setattr(
        github,
        "create_pull_request",
        lambda root, **kw: calls.append(("create", kw["head"], kw["base"])) or 41,
    )
    monkeypatch.setattr(
        github, "required_checks", lambda root, base: ("lint", "verify")
    )
    monkeypatch.setattr(
        github,
        "hosted_check_state",
        lambda pull, name: "success" if name == "verify" else "missing",
    )
    monkeypatch.setattr(github, "check_rollup", lambda pull, required=(): next(rollups))
    monkeypatch.setattr(
        github,
        "merge_pr",
        lambda root, number, sha: calls.append(("merge", number, sha)),
    )
    advisory = [
        {
            "kind": "review",
            "author": "reviewer",
            "state": "CHANGES_REQUESTED",
            "head_sha": SHA,
            "url": "https://github.com/o/r/pull/41#pullrequestreview-1",
        }
    ]
    monkeypatch.setattr(
        github,
        "pull_request_advisory",
        lambda root, number: calls.append(("advisory", number)) or advisory,
    )
    run = prepared_run(harness, "fx-solo")

    landed = harness.land(run["run_id"])

    branch = f"batch/{run['run_id']}/integration"
    assert ("push", branch, SHA, None) in calls
    assert ("create", branch, "master") in calls
    assert calls.count(("create", branch, "master")) == 1
    assert landed["landing"]["pr_number"] == 41
    assert landed["landing"]["verify_run"] == {
        "kind": "hosted",
        "check": "verify",
        "pr": 41,
        "candidate_sha": SHA,
        "phase": "succeeded",
    }
    assert calls[-2:] == [("merge", 41, SHA), ("advisory", 41)]
    assert landed["acceptance"]["published"] == {
        "policy": "pr",
        "pr": 41,
        "candidate_sha": SHA,
        "base_commit": BASE,
    }
    # Advisory only: a CHANGES_REQUESTED review is recorded, never a gate.
    assert landed["acceptance"]["advisory"] == advisory
    assert landed["acceptance"]["members"]["fx-solo"]["state"] == "closed"
    assert harness.git.pushes == []


# ---------------------------------------------------------------- status / manifest


def test_status_and_list_join_the_manifest_with_pueue(harness: Harness) -> None:
    run = harness.start("fx-lead")
    document = batch.status(harness.config, run["run_id"])
    assert document["stage"] == "working"
    assert document["workers"][0]["stage"] == "running"
    assert (
        document["workers"][0]["task"]["label"]
        == f"fixture:worker:{run['run_id']}:fx-lead"
    )
    assert document["landing"]["task"]["phase"] == "running"
    assert [item.run_id for item in batch.list_runs(harness.config, "fixture")] == [
        run["run_id"]
    ]
    assert batch.list_runs(harness.config, "other") == []


def test_manifest_is_written_once_and_updated_under_the_lock(harness: Harness) -> None:
    run = batch.Run.from_dict(
        {
            **harness.start("fx-solo"),
        }
    )
    with pytest.raises(BatchRefusal, match="already has a manifest"):
        batch.create(harness.config, run)

    def bump(document: dict[str, Any]) -> None:
        document["landing"]["refreshes"] = 3

    updated = batch.update(harness.config, run.run_id, bump)
    assert updated.landing["refreshes"] == 3
    assert batch.load(harness.config, run.run_id).landing["refreshes"] == 3
    with pytest.raises(BatchRefusal, match="unknown_run"):
        batch.load(harness.config, "nope")


def test_a_result_must_name_a_commit_that_descends_from_the_run_base(
    harness: Harness,
) -> None:
    """Breaks if a worker may file work landing cannot merge onto the base: the
    base itself (nothing committed) or a commit from an unrelated history."""
    run = harness.start("fx-solo")
    worker = run["workers"][0]

    filed = harness.file_result(run, "fx-solo")
    assert filed["result"]["candidate_sha"] == SHA
    assert (BASE, SHA) in harness.git.ancestry

    harness.git.heads[worker["worktree"]] = BASE
    with pytest.raises(BatchRefusal, match="empty_candidate"):
        harness.file_result(run, "fx-solo", sha=BASE)

    harness.git.heads[worker["worktree"]] = MOVED
    harness.git.off_base.add(MOVED)
    with pytest.raises(BatchRefusal, match="candidate_off_base"):
        harness.file_result(run, "fx-solo", sha=MOVED)


def test_resume_replaces_a_queued_landing_so_it_waits_on_the_current_workers(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = harness.start("fx-lead", "fx-solo")
    monkeypatch.setattr(batch, "SubprocessBeads", lambda root: harness.beads)
    harness.pueue.fail(run["workers"][0]["task_id"], exit_code=1)
    harness.pueue.fail(run["workers"][1]["task_id"], exit_code=1)
    queued = harness.pueue.task(run["landing"]["task_id"])
    harness.pueue._tasks[queued.task_id] = replace(queued, status="Queued")
    first = batch.resume(harness.config, harness.project, run["run_id"], "fx-lead")
    queued = harness.pueue.task(first["landing"]["task_id"])
    harness.pueue._tasks[queued.task_id] = replace(queued, status="Queued")
    second = batch.resume(harness.config, harness.project, run["run_id"], "fx-solo")
    landing = harness.pueue.task(second["landing"]["task_id"])
    assert sorted(landing.dependencies) == sorted(
        worker["task_id"] for worker in second["workers"]
    )
