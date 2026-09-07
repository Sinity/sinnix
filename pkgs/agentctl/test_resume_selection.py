"""Worker resume selection is current state with an immutable launch history."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentctl import batch, gitcmd, manifest, start, worktrunk
from agentctl.config import Config
from agentctl.projects import load_project_adapter
from conftest import FakePueue, read_launch
from test_batch import FakeGit, FakeWorktrunk, Harness, beads, verdict


@pytest.fixture
def selection_harness(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Harness:
    project = load_project_adapter(project_root)
    git = FakeGit()
    wt = FakeWorktrunk()
    fake_pueue.groups["fixture-land"] = 1

    def create(
        root: Path, branch: str, *, path: Path, base: str | None = None
    ) -> worktrunk.Worktree:
        tree = wt.create(root, branch, path=path, base=base)
        git.checkouts[str(path)] = branch
        return tree

    monkeypatch.setattr(gitcmd, "git", git)
    monkeypatch.setattr(worktrunk, "worktrunk_find", wt.find)
    monkeypatch.setattr(worktrunk, "worktrunk_list", wt.list)
    monkeypatch.setattr(worktrunk, "worktrunk_create", create)
    monkeypatch.setattr(worktrunk, "worktrunk_remove", wt.remove)
    return Harness(
        config=config,
        project=project,
        pueue=fake_pueue,
        beads=beads(),
        git=git,
        wt=wt,
        verdict=verdict(),
    )


def _resume(
    harness: Harness, run: dict[str, object], **selection: str
) -> dict[str, object]:
    worker = run["workers"][0]  # type: ignore[index]
    harness.pueue.fail(worker["task_id"], exit_code=1)  # type: ignore[index]
    return batch.resume(
        harness.config,
        harness.project,
        run["run_id"],  # type: ignore[arg-type]
        "fx-solo",
        **selection,
    )


def test_resume_updates_the_current_selection_and_retains_each_launch(
    selection_harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = selection_harness.start("fx-solo", model="luna")
    monkeypatch.setattr(start, "SubprocessBeads", lambda root: selection_harness.beads)

    terra = _resume(selection_harness, run, model="terra", effort="high")
    terra_worker = terra["workers"][0]
    selection_harness.pueue.fail(terra_worker["task_id"], exit_code=1)
    final = batch.resume(
        selection_harness.config, selection_harness.project, run["run_id"], "fx-solo"
    )
    worker = final["workers"][0]

    assert (worker["backend"], worker["model"], worker["effort"]) == (
        "codex",
        "gpt-5.6-terra",
        "high",
    )
    for queued in (terra, final):
        argv = read_launch(
            selection_harness.config,
            selection_harness.pueue.task(queued["job"]["job_id"]),
        )["argv"]
        assert argv[argv.index("--model") + 1] == "gpt-5.6-terra"
        assert argv[argv.index("--reasoning-effort") + 1] == "high"
    assert [
        (
            attempt["task_reference"],
            attempt["backend"],
            attempt["model"],
            attempt["effort"],
        )
        for attempt in worker["attempts"]
    ] == [
        (run["workers"][0]["task_reference"], "codex", "gpt-5.6-luna", "low"),
        (terra["job"]["reference"], "codex", "gpt-5.6-terra", "high"),
        (final["job"]["reference"], "codex", "gpt-5.6-terra", "high"),
    ]
    assert worker["attempts"][-1]["prompt_path"] == worker["prompt_path"]
    assert worker["attempts"][-1]["result_path"] == worker["result_path"]


def test_resume_of_a_legacy_manifest_does_not_invent_historical_selection(
    selection_harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = selection_harness.start("fx-solo", model="luna")
    monkeypatch.setattr(start, "SubprocessBeads", lambda root: selection_harness.beads)
    worker = run["workers"][0]
    selection_harness.pueue.fail(worker["task_id"], exit_code=1)

    path = manifest.manifest_path(selection_harness.config, run["run_id"])
    document = json.loads(path.read_text())
    document["workers"][0].pop("attempts")
    path.write_text(json.dumps(document))

    resumed = batch.resume(
        selection_harness.config, selection_harness.project, run["run_id"], "fx-solo"
    )
    latest = resumed["workers"][0]

    assert latest["attempts"] == [
        {
            "task_id": resumed["job"]["job_id"],
            "task_reference": resumed["job"]["reference"],
            "prompt_path": latest["prompt_path"],
            "result_path": latest["result_path"],
            "backend": "codex",
            "model": "gpt-5.6-luna",
            "effort": "low",
        }
    ]
