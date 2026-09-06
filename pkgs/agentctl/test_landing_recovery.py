"""Landing and cleanup preserve a live batch's inputs and recovery work."""

import json
from pathlib import Path

import pytest
from agentctl import launch, manifest
from agentctl.batch import BatchRefusal
from conftest import read_launch
from test_batch import BASE, MOVED, Harness, labels, prepared_run, verdict
from test_batch import harness as harness


def test_a_base_moved_before_landing_is_verified_only_once(harness: Harness) -> None:
    """Verifying before refreshing the publication base adds a second check."""
    run = prepared_run(harness, "fx-solo")
    harness.git.remote_bases = [MOVED]

    landed = harness.land(run["run_id"])

    candidate = landed["acceptance"]["candidate_sha"]
    assert harness.git.is_ancestor(MOVED, candidate)
    assert landed["acceptance"]["published"]["base_commit"] == MOVED
    assert landed["landing"]["refreshed_base"] == MOVED
    assert landed["landing"]["refreshes"] == 0
    assert labels(harness.pueue).count("fixture:check") == 1
    assert len([label for label in labels(harness.pueue) if ":review:" in label]) == 1
    assert harness.git.resets == []


def test_keep_integration_does_not_reset_when_publication_base_moves(
    harness: Harness,
) -> None:
    """An explicit kept candidate must survive a moved target."""
    run = prepared_run(harness, "fx-solo")
    harness.verdict = verdict(verdict="fail")
    with pytest.raises(BatchRefusal, match="review_rejected"):
        harness.land(run["run_id"])
    stored = manifest.load(harness.config, run["run_id"])
    path = stored.landing["integration_worktree"]
    head = harness.git.heads[path]
    harness.verdict = verdict()
    harness.git.remote_bases = [MOVED]
    merges = list(harness.git.merges)

    with pytest.raises(BatchRefusal, match="publish_rejected"):
        harness.land(run["run_id"], keep_integration=True)

    assert harness.git.heads[path] == head
    assert harness.git.merges == merges and harness.git.resets == []
    assert manifest.load(harness.config, run["run_id"]).base_commit == BASE


@pytest.mark.parametrize("legacy", [False, True])
def test_terminal_cleanup_retains_live_worker_evidence(
    harness: Harness, legacy: bool
) -> None:
    """Deleting a completed worker's queue row prevents its batch from landing."""
    run = prepared_run(harness, "fx-solo")
    worker = run["workers"][0]
    task = harness.pueue.task(worker["task_id"])
    written = read_launch(harness.config, task)
    log = Path(written["log_path"])
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("worker complete\n")
    input_path = launch.launch_input_path(task)
    if legacy:
        written.pop("binding", None)
        input_path.write_text(json.dumps(written))

        def legacy_worker(document: dict) -> None:
            document["workers"][0].pop("task_reference", None)
            document["workers"][0]["worktree"] = None

        manifest.update(harness.config, run["run_id"], legacy_worker)
    unrelated = launch.start_operation(
        harness.config, harness.project, harness.project.operation("check")
    )
    harness.pueue.succeed(unrelated["job_id"])

    cleaned = launch.clean_terminal(harness.config)

    assert [row["job_id"] for row in cleaned] == [unrelated["job_id"]]
    assert harness.pueue.task(task.task_id) is not None
    assert input_path.is_file() and log.read_text() == "worker complete\n"


@pytest.mark.parametrize("terminal", ["acceptance", "abandoned"])
def test_terminal_runs_release_worker_jobs_for_cleanup(
    harness: Harness, terminal: str
) -> None:
    """Retention ends with the manifest's terminal state."""
    run = prepared_run(harness, "fx-solo")
    worker = run["workers"][0]
    task = harness.pueue.task(worker["task_id"])
    input_path = launch.launch_input_path(task)
    manifest.update(
        harness.config,
        run["run_id"],
        lambda document: document.update({terminal: {"at": "done"}}),
    )

    cleaned = launch.clean_terminal(harness.config)

    assert [row["job_id"] for row in cleaned] == [task.task_id]
    assert harness.pueue.task(task.task_id) is None and not input_path.exists()


def test_terminal_cleanup_retains_a_verification_in_a_live_worktree(
    harness: Harness,
) -> None:
    """A completed check can precede recording its job reference in the manifest."""
    run = prepared_run(harness, "fx-solo")
    check = launch.start_operation(
        harness.config,
        harness.project,
        harness.project.operation("check"),
        workspace=Path(run["workers"][0]["worktree"]),
    )
    harness.pueue.succeed(check["job_id"])

    assert launch.clean_terminal(harness.config) == []
    assert harness.pueue.task(check["job_id"]) is not None


def test_terminal_cleanup_retains_a_recorded_verification_job(harness: Harness) -> None:
    """A receipt can reference a check outside the integration worktree."""
    run = prepared_run(harness, "fx-solo")
    check = launch.start_operation(
        harness.config, harness.project, harness.project.operation("check")
    )
    harness.pueue.succeed(check["job_id"])
    manifest.land_update(
        harness.config, run["run_id"], verify_run={"job_id": check["job_id"]}
    )

    assert launch.clean_terminal(harness.config) == []
    assert harness.pueue.task(check["job_id"]) is not None


def test_terminal_cleanup_retains_a_legacy_landing_after_reorder(
    harness: Harness,
) -> None:
    """Legacy landing jobs have a run label but no binding or stable reference."""
    run = prepared_run(harness, "fx-solo")
    landing = harness.pueue.task(run["landing"]["task_id"])
    other = launch.start_operation(
        harness.config, harness.project, harness.project.operation("check")
    )
    harness.pueue.queue(other["job_id"])
    harness.pueue.switch(landing.task_id, other["job_id"])
    harness.pueue.succeed(other["job_id"])
    manifest.update(
        harness.config,
        run["run_id"],
        lambda document: document["landing"].pop("task_reference", None),
    )

    assert launch.clean_terminal(harness.config) == []
    assert harness.pueue.task(other["job_id"]).label == landing.label
