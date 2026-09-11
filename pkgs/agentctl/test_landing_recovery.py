"""Landing and cleanup preserve a live batch's inputs and recovery work."""

import json
import threading
from dataclasses import replace
from pathlib import Path

import pytest
from agentctl import batch, launch, manifest, prompts
from agentctl import start as start_module
from agentctl.batch import BatchError, BatchRefusal
from conftest import read_launch
from test_batch import BASE, MOVED, SHA, Harness, labels, prepared_run, verdict
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


def failed_publication(harness: Harness) -> dict:
    run = prepared_run(harness, "fx-solo")
    harness.git.push_rejects = 1
    harness.git.push_rejection = "permission denied"
    with pytest.raises(BatchError, match="permission denied"):
        harness.land(run["run_id"])
    return manifest.load(harness.config, run["run_id"]).to_dict()


def test_transient_publication_retry_reuses_the_exact_candidate(
    harness: Harness,
) -> None:
    """A lost publication attempt must not queue a second check or reviewer."""
    run = failed_publication(harness)
    merges = list(harness.git.merges)
    landed = harness.land(run["run_id"])
    assert landed["acceptance"]["candidate_sha"] == run["landing"]["candidate_sha"]
    assert landed["acceptance"]["verify_run"] == run["landing"]["verify_run"]
    assert landed["acceptance"]["review_verdict"] == run["landing"]["review_verdict"]
    assert harness.git.merges == merges and harness.git.resets == []
    assert labels(harness.pueue).count("fixture:check") == 1
    assert labels(harness.pueue).count(f"fixture:review:{run['run_id']}") == 1


@pytest.mark.parametrize(
    "changed", ["base", "descriptor", "template", "result", "bead"]
)
def test_changed_landing_inputs_invalidate_reuse(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    """The same Git head cannot authorize evidence from a different contract."""
    run = failed_publication(harness)
    if changed == "base":
        harness.git.remote_bases = [MOVED]
    elif changed == "descriptor":
        harness.project = replace(harness.project, digest="new-descriptor")
    elif changed == "template":
        original = prompts.landing_template
        monkeypatch.setattr(
            prompts,
            "landing_template",
            lambda name: original(name) + "\nUpdated review rule.\n",
        )
    elif changed == "result":
        manifest.update(
            harness.config,
            run["run_id"],
            lambda doc: doc["workers"][0]["result"]["unresolved"].append(
                "Live rehearsal remains open"
            ),
        )
    else:
        harness.beads.beads["fx-solo"]["acceptance_criteria"] = "changed criterion"
    harness.land(run["run_id"])
    assert labels(harness.pueue).count("fixture:check") == 2
    assert labels(harness.pueue).count(f"fixture:review:{run['run_id']}") == 2


def test_failed_review_retries_only_review(harness: Harness) -> None:
    run = prepared_run(harness, "fx-solo")
    harness.verdict = verdict(verdict="unsupported")
    with pytest.raises(BatchRefusal, match="review_rejected"):
        harness.land(run["run_id"])
    harness.verdict = verdict()
    harness.land(run["run_id"])
    assert labels(harness.pueue).count("fixture:check") == 1
    assert labels(harness.pueue).count(f"fixture:review:{run['run_id']}") == 2
    assert harness.git.resets == []


def test_manual_integration_commit_requires_keep_and_new_evidence(
    harness: Harness,
) -> None:
    run = failed_publication(harness)
    path = run["landing"]["integration_worktree"]
    manual = "a" * 40
    harness.git.parents[manual] = (SHA,)
    harness.git.heads[path] = manual
    with pytest.raises(BatchRefusal, match="integration_incomplete"):
        harness.land(run["run_id"])
    assert harness.git.heads[path] == manual and harness.git.resets == []
    landed = harness.land(run["run_id"], keep_integration=True)
    assert landed["acceptance"]["candidate_sha"] == manual
    assert labels(harness.pueue).count("fixture:check") == 2


def test_bulk_cleanup_refuses_unreadable_manifest_authority(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A transient read failure cannot turn a live run into permission to delete."""
    run = prepared_run(harness, "fx-solo")
    target = manifest.manifest_path(harness.config, run["run_id"])
    original = Path.read_text

    def read(path: Path, *args, **kwargs):
        if path == target:
            raise PermissionError("manifest temporarily unreadable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    with pytest.raises(BatchRefusal, match="manifest"):
        launch.clean_terminal(harness.config)
    assert harness.pueue.task(run["workers"][0]["task_id"]) is not None


def test_failed_verification_is_retried_on_the_same_candidate(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = prepared_run(harness, "fx-solo")
    original = launch.wait

    def fail(job_id, **kwargs):
        harness.pueue.fail(job_id, exit_code=1)
        return launch.job_view(harness.pueue.task(job_id))

    monkeypatch.setattr(launch, "wait", fail)
    with pytest.raises(BatchRefusal, match="verify_failed"):
        harness.land(run["run_id"])
    monkeypatch.setattr(launch, "wait", original)
    harness.land(run["run_id"])
    assert labels(harness.pueue).count("fixture:check") == 2
    assert labels(harness.pueue).count(f"fixture:review:{run['run_id']}") == 1
    assert harness.git.resets == []


def test_large_review_evidence_is_exact_and_locally_readable(harness: Harness) -> None:
    run = prepared_run(harness, "fx-solo", unsatisfied={"fx-solo"})
    harness.wt.leave_paths = {f"batch/{run['run_id']}/integration"}
    harness.beads.beads["fx-solo"]["design"] = (
        "Publish code now; live rehearsal follows and keeps this bead open."
    )
    evidence = "tests/test_fixture.py::test_delivery: passed; " * 600

    def evidence_result(doc):
        result = doc["workers"][0]["result"]
        result["beads"][0]["criteria"][0]["evidence"] = evidence
        result["unresolved"] = ["Run live rehearsal after publication"]

    manifest.update(harness.config, run["run_id"], evidence_result)
    landed = harness.land(run["run_id"])
    task = next(t for t in harness.pueue.tasks().values() if ":review:" in t.label)
    path = Path(task.path)
    prompt = (path / ".agentctl/review.md").read_text()
    blocks = [
        json.loads(block.split("\n```", 1)[0])
        for block in prompt.split("```json\n")[1:]
    ]
    members, worker_results, verification = blocks
    assert members[0]["beads"][0]["design"] == harness.beads.beads["fx-solo"]["design"]
    entry = worker_results[0]
    assert entry["inline_omitted"] is True
    exact = json.loads(Path(entry["source"]).read_text())[entry["index"]]
    assert exact["beads"][0]["criteria"][0]["evidence"] == evidence
    assert exact["unresolved"] == ["Run live rehearsal after publication"]
    assert Path(entry["source"]).parent == path / ".agentctl"
    assert verification[0]["candidate_sha"] == landed["acceptance"]["candidate_sha"]
    assert landed["acceptance"]["beads"]["fx-solo"]["state"] == "open"
    assert len(prompt) < 10_000


def test_generic_check_keeps_explicit_test_selection_separate(harness: Harness) -> None:
    metadata = harness.beads.beads["fx-solo"]["metadata"]
    metadata["affected_paths"] = ["storage internals and deleted paths"]
    commands = ["devtools test tests/unit/storage/test_fixture.py -k roundtrip"]
    metadata["verification_commands"] = commands
    run = harness.start("fx-solo")
    worker = run["workers"][0]
    prompt = Path(worker["prompt_path"]).read_text()
    snapshot = json.loads(prompt.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert (
        snapshot["batch"]["focused_verification"]
        == f"/fixture/agentctl job start fixture verify_quick --workspace {worker['worktree']} --wait"
    )
    assert snapshot["dimensions"]["verification_commands"] == commands


def test_a_worker_changed_after_filing_is_not_merged(harness: Harness) -> None:
    run = failed_publication(harness)
    branch = run["workers"][0]["branch"]
    harness.git.branches[branch] = MOVED
    merges = list(harness.git.merges)
    with pytest.raises(BatchRefusal, match="candidate_mismatch"):
        harness.land(run["run_id"])
    assert harness.git.merges == merges and harness.git.resets == []


@pytest.mark.parametrize("failure", ["directory_unreadable", "incomplete_json"])
def test_bulk_cleanup_requires_a_complete_run_inventory(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    run = prepared_run(harness, "fx-solo")
    if failure == "incomplete_json":
        manifest.manifest_path(harness.config, run["run_id"]).write_text('{"run_id":')
    else:
        original = Path.iterdir

        def inventory(path: Path):
            if path == manifest.runs_dir(harness.config):
                raise PermissionError("run directory temporarily unreadable")
            return original(path)

        monkeypatch.setattr(Path, "iterdir", inventory)
    with pytest.raises(BatchRefusal, match="manifest"):
        launch.clean_terminal(harness.config)
    assert harness.pueue.removed == []


# ------------------------------------------- a queue that lost its own state


def test_the_last_result_requeues_a_landing_the_queue_lost(harness: Harness) -> None:
    """mzw2: a landing id pueue reassigned to a stranger is not a landing task.

    pueued's state was reset under a live external run: the manifest named
    landing task 1 and the next task the daemon queued took that id, so an
    id-resolved status reported a stage that nothing was waiting for.
    """
    run = harness.start(workers=[["fx-solo"]], harness="external")
    stranded = run["landing"]["task_id"]
    harness.pueue.reset_state()
    unrelated = launch.start_operation(
        harness.config, harness.project, harness.project.operation("check")
    )
    assert unrelated["job_id"] == stranded

    filed = harness.file_result(run, "fx-solo")

    assert filed["landing_vanished"] == stranded
    assert not filed["landing_released"]
    queued = filed["landing_requeued"]
    task = harness.pueue.task(queued)
    assert task.label == f"fixture:land:{run['run_id']}"
    # Every result is in, so the replacement is released, not stashed again.
    assert task.status != "Stashed" and task.dependencies == ()
    assert read_launch(harness.config, task)["argv"][-3:] == [
        "batch",
        "land",
        run["run_id"],
    ]
    stored = manifest.load(harness.config, run["run_id"])
    assert stored.landing["task_id"] == queued
    assert stored.landing["task_reference"] == launch.launch_reference(task)


def test_concurrent_results_replace_a_lost_landing_once(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mzw2: recovery locks its queue snapshot through the manifest relink.

    Both workers preserve the same pre-recovery task snapshot behind this
    barrier. Without the recovery lock they both see the missing landing and
    enqueue one, leaving the first task orphaned; with it, the second sees the
    replacement and releases it after reloading the first result.
    """
    run = harness.start(workers=[["fx-lead"], ["fx-solo"]], harness="external")
    lost = run["landing"]["task_id"]
    harness.pueue.reset_state()
    original_tasks = harness.pueue.tasks
    snapshots = threading.Barrier(2)

    def concurrent_snapshots():
        snapshot = original_tasks()
        try:
            # A recovery lock holds the second caller outside this function;
            # timing out then lets the first proceed. Without that lock both
            # callers return their identical stale snapshots together.
            snapshots.wait(timeout=0.2)
        except threading.BrokenBarrierError:
            pass
        return snapshot

    monkeypatch.setattr(start_module.pueue, "tasks", concurrent_snapshots)
    ready = threading.Barrier(2)
    filed: list[dict[str, object]] = []
    errors: list[BaseException] = []

    def file(worker_id: str) -> None:
        try:
            ready.wait(timeout=2)
            filed.append(harness.file_result(run, worker_id))
        except BaseException as error:  # surface failures from both threads
            errors.append(error)

    threads = [
        threading.Thread(target=file, args=(worker["id"],)) for worker in run["workers"]
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert not any(thread.is_alive() for thread in threads)
    assert not errors
    replacement = [
        task
        for task in harness.pueue.tasks().values()
        if task.label.endswith(f":{run['run_id']}")
    ]
    assert len(replacement) == 1
    task = replacement[0]
    assert task.status != "Stashed"
    stored = manifest.load(harness.config, run["run_id"])
    assert stored.landing["task_id"] == task.task_id
    assert all(worker.get("result") for worker in stored.workers)
    assert any(entry["landing_vanished"] == lost for entry in filed)


def test_a_requeued_landing_waits_for_the_workers_still_running(
    harness: Harness,
) -> None:
    """Breaks if recovery lands a run while a worker is still writing to it."""
    run = harness.start("fx-lead", "fx-solo")
    lead, solo = run["workers"]
    harness.pueue.succeed(lead["task_id"])
    stranded = run["landing"]["task_id"]
    harness.pueue.remove([stranded])

    filed = harness.file_result(run, "fx-lead")

    assert filed["landing_vanished"] == stranded
    task = harness.pueue.task(filed["landing_requeued"])
    # The finished worker is answered by its result; the running one is not.
    assert task.dependencies == (solo["task_id"],)


def test_a_landing_the_queue_refuses_to_requeue_names_the_command(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Filing the result is the verb's work; a failed recovery is reported."""
    run = harness.start(workers=[["fx-solo"]], harness="external")
    stranded = run["landing"]["task_id"]
    harness.pueue.reset_state()
    harness.pueue.fail_add = True

    filed = harness.file_result(run, "fx-solo")

    assert filed["landing_vanished"] == stranded
    assert filed["landing_requeued"] is None
    assert "fixture pueue add failed" in filed["landing_requeue_error"]
    assert manifest.load(harness.config, run["run_id"]).workers[0]["result"]


def test_a_result_stays_recorded_when_the_queue_is_temporarily_unreadable(
    harness: Harness,
) -> None:
    """A queue outage cannot undo the durable evidence this verb just filed."""
    run = harness.start(workers=[["fx-solo"]], harness="external")
    harness.pueue.fail_tasks = True

    filed = harness.file_result(run, "fx-solo")

    assert filed["landing_vanished"] is None
    assert filed["landing_requeued"] is None
    assert filed["landing_released"] is False
    assert "fixture pueue status failed" in filed["landing_requeue_error"]
    assert manifest.load(harness.config, run["run_id"]).workers[0]["result"]


def test_a_result_filed_normally_reports_no_lost_landing(harness: Harness) -> None:
    """Anti-vacuity: the recovery path must not fire on a healthy run."""
    run = harness.start(workers=[["fx-solo"]], harness="external")
    filed = harness.file_result(run, "fx-solo")
    assert filed["landing_vanished"] is None
    assert filed["landing_requeued"] is None
    assert filed["landing_released"]
    assert len([label for label in labels(harness.pueue) if ":land:" in label]) == 1


def test_a_queued_landing_manually_stashed_by_the_operator_is_preserved(
    harness: Harness,
) -> None:
    run = harness.start("fx-solo")
    landing_id = run["landing"]["task_id"]
    landing = harness.pueue.task(landing_id)
    assert landing is not None
    harness.pueue._tasks[landing_id] = replace(landing, status="Stashed")
    harness.pueue.succeed(run["workers"][0]["task_id"])

    filed = harness.file_result(run, "fx-solo")

    assert filed["landing_released"] is False
    assert harness.pueue.task(landing_id).status == "Stashed"
    assert manifest.load(harness.config, run["run_id"]).landing[
        "waiting_for_results"
    ] is False


def test_repeated_result_does_not_release_an_operator_restash_after_ours(
    harness: Harness,
) -> None:
    run = harness.start(workers=[["fx-solo"]], harness="external")
    landing_id = run["landing"]["task_id"]

    first = harness.file_result(run, "fx-solo")
    assert first["landing_released"] is True
    landing = harness.pueue.task(landing_id)
    assert landing is not None
    harness.pueue._tasks[landing_id] = replace(landing, status="Stashed")

    repeated = harness.file_result(run, "fx-solo")

    assert repeated["landing_released"] is False
    assert harness.pueue.task(landing_id).status == "Stashed"
    assert manifest.load(harness.config, run["run_id"]).landing[
        "waiting_for_results"
    ] is False


def test_a_queue_reset_does_not_strand_workers_that_filed_results(
    harness: Harness,
) -> None:
    """A landing refuses on the results, not on the queue's memory of a task."""
    run = prepared_run(harness, "fx-solo")
    harness.pueue.reset_state()

    landed = harness.land(run["run_id"])

    assert landed["acceptance"]["candidate_sha"] == SHA
    assert harness.beads.closed[0][0] == "fx-solo"


def test_a_worker_with_no_result_and_no_task_still_refuses_to_land(
    harness: Harness,
) -> None:
    """Anti-vacuity: losing the task is not evidence that the worker finished."""
    run = harness.start("fx-solo")
    harness.pueue.reset_state()
    with pytest.raises(BatchRefusal, match="gone from pueue"):
        harness.land(run["run_id"])


def test_batch_queue_waits_for_the_worker_that_has_not_filed(
    harness: Harness,
) -> None:
    """mzw2 review: a landing that can run at once refuses `worker_not_done`.

    `batch queue` replaces a landing the queue lost, which is exactly when a
    worker may still owe its result; the replacement waits for it instead of
    ending as a failed task nobody is waiting on.
    """
    run = harness.start("fx-lead", "fx-solo")
    lead, solo = run["workers"]
    harness.pueue.succeed(lead["task_id"])
    harness.pueue.remove([run["landing"]["task_id"]])

    queued = batch.queue(harness.config, harness.project, run["run_id"])

    task = harness.pueue.task(queued["landing_task_id"])
    assert task.status == "Stashed" and task.dependencies == (solo["task_id"],)
    harness.file_result(run, "fx-lead")
    assert harness.pueue.task(task.task_id).status == "Stashed"

    harness.pueue.succeed(solo["task_id"])
    harness.file_result(run, "fx-solo")

    # The last result is what the landing was waiting for, whatever harness
    # the run uses: nothing else would ever release it.
    assert harness.pueue.task(task.task_id).status != "Stashed"
