from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import sinnixd.harvest as harvest
from sinnixd.review import route_review


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )


def _repository(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "polylogue"
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(remote)], check=True)
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    _run_git(root, "config", "user.name", "Fixture")
    _run_git(root, "config", "user.email", "fixture@example.test")
    (root / "polylogue").mkdir()
    (root / "polylogue" / "module.py").write_text("def original():\n    return 1\n")
    _run_git(root, "add", ".")
    assert _run_git(root, "commit", "--quiet", "-m", "base").returncode == 0
    _run_git(root, "branch", "-M", "master")
    _run_git(root, "remote", "add", "origin", str(remote))
    assert _run_git(root, "push", "--quiet", "-u", "origin", "master").returncode == 0
    _run_git(root, "switch", "-c", "feature/fixture")
    (root / "polylogue" / "module.py").write_text(
        "def original():\n    return 2\n\n\ndef added():\n    return 3\n"
    )
    _run_git(root, "add", ".")
    assert _run_git(root, "commit", "--quiet", "-m", "lane").returncode == 0
    return root, remote


def _context(
    root: Path, state: Path, job_id: str = "harvest-job"
) -> harvest.HarvestContext:
    return harvest.HarvestContext(
        worktree=root,
        project_id="polylogue",
        workspace_id="worktree-1",
        job_id=job_id,
        state_root=state,
        spool=state / "events.jsonl",
    )


def test_compile_packet_halts_before_publication_and_spools_review_evidence(
    tmp_path: Path,
) -> None:
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state)

    result = harvest.compile_packet(context)

    assert result["outcome"] == harvest.HARVEST_OK
    assert result["phase"] == "review-required"
    packet = result["packet"]
    assert packet["branch"] == "feature/fixture"
    assert "1 file changed" in packet["diffstat"]
    assert packet["full_diff_ref"].startswith("sinnix://jobs/")
    assert (state / "harvest-packets" / f"{packet['packet_id']}.diff").is_file()
    event = json.loads((state / "events.jsonl").read_text())
    assert event["kind"] == "harvest"
    assert event["transition"] == "review-required"


def test_authorize_requires_receipt_and_runs_publish_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state, "authorize-job")
    packet = harvest.compile_packet(context)["receipt_ref"]
    monkeypatch.setattr(harvest, "LOCK_PATH", tmp_path / "harvest.lock")

    def run(argv, **kwargs):
        if argv[:2] == ["devtools", "verify"] and len(argv) == 2:
            return subprocess.CompletedProcess(
                argv, 0, "affected verification passed", ""
            )
        if argv[:3] == ["devtools", "verify", "--quick"]:
            return subprocess.CompletedProcess(argv, 0, "quick gate passed", "")
        if argv[0] == "gh":
            if argv[1] == "pr" and argv[2] == "create":
                return subprocess.CompletedProcess(
                    argv, 0, "https://github.test/pull/42\n", ""
                )
            if argv[1] == "pr" and argv[2] == "merge":
                return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.run(argv, **kwargs)

    result = harvest.authorize(
        context,
        receipt_ref=packet,
        title="fix: publish the harvested lane branch",
        body="Reviewed packet.",
        run=run,
        watch=False,
    )

    assert result == {
        "outcome": harvest.HARVEST_OK,
        "phase": "published",
        "pr": "42",
        "pr_url": "https://github.test/pull/42",
        "merge_state": "ARMED",
        "bead_id": None,
        "affected_tests": "passed",
    }
    assert any(
        row["transition"] == "review-required"
        for row in map(json.loads, (state / "events.jsonl").read_text().splitlines())
    )
    assert any(
        row.get("phase") == "published"
        for row in map(json.loads, (state / "events.jsonl").read_text().splitlines())
    )


def test_authorize_watcher_closes_bead_from_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state, "watch-job")
    receipt = harvest.compile_packet(
        context, bead_id="sinnix-c960", close_reason="landed by harvest"
    )["receipt_ref"]
    monkeypatch.setattr(harvest, "LOCK_PATH", tmp_path / "harvest.lock")
    closed: list[list[str]] = []

    def run(argv, **kwargs):
        if argv[:2] == ["devtools", "verify"] and len(argv) == 2:
            return subprocess.CompletedProcess(
                argv, 0, "affected verification passed", ""
            )
        if argv[:3] == ["devtools", "verify", "--quick"]:
            return subprocess.CompletedProcess(argv, 0, "quick gate passed", "")
        if argv[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(
                argv, 0, "https://github.test/pull/42\n", ""
            )
        if argv[:3] == ["gh", "pr", "merge"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(argv, 0, "MERGED\n", "")
        if argv[:2] == ["bd", "close"]:
            closed.append(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.run(argv, **kwargs)

    result = harvest.authorize(
        context,
        receipt_ref=receipt,
        title="fix: publish the harvested lane branch",
        body="Reviewed packet.",
        run=run,
        watch=True,
        watch_attempts=1,
        watch_delay=0,
    )

    assert result["merge_state"] == "MERGED"
    assert closed == [
        [
            "bd",
            "close",
            "sinnix-c960",
            "--force",
            "--actor",
            "claude-overseer",
            "--reason",
            "landed by harvest",
        ]
    ]
    events = [
        json.loads(row) for row in (state / "events.jsonl").read_text().splitlines()
    ]
    assert any(
        event.get("kind") == "merge_close" and event["bead_closed"] for event in events
    )


def test_gate_red_is_typed_and_never_pushes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state, "gate-job")
    receipt = harvest.compile_packet(context)["receipt_ref"]
    monkeypatch.setattr(harvest, "LOCK_PATH", tmp_path / "harvest.lock")
    pushed = False

    def run(argv, **kwargs):
        nonlocal pushed
        if argv[:2] == ["devtools", "verify"] and len(argv) == 2:
            return subprocess.CompletedProcess(
                argv, 0, "affected verification passed", ""
            )
        if argv[:3] == ["devtools", "verify", "--quick"]:
            return subprocess.CompletedProcess(argv, 1, "gate failed", "")
        if argv[:2] == ["git", "push"]:
            pushed = True
        return subprocess.run(argv, **kwargs)

    result = harvest.authorize(
        context,
        receipt_ref=receipt,
        title="fix: publish the harvested lane branch",
        body="Reviewed packet.",
        run=run,
        watch=False,
    )

    assert result["outcome"] == harvest.GATE_RED
    assert pushed is False


def test_redflags_flags_removed_production_lines_and_assertions() -> None:
    status, flags = harvest._redflags(
        "diff --git a/polylogue/module.py b/polylogue/module.py\n"
        "-def removed():\n"
        "+def retained():\n"
        "diff --git a/tests/test_module.py b/tests/test_module.py\n"
        "-    assert old\n"
        "+    assert new\n"
    )

    assert status == 1
    assert "FLAG: production lines removed (polylogue/)" in flags
    assert "FLAG: test assertions removed" in flags


def test_publication_title_must_be_a_squashable_conventional_subject() -> None:
    """The title lands verbatim as the squash subject on the protected branch.

    Anti-vacuity: dropping the shape or length check makes this red, since a
    mangled caller expansion and a 73-character subject both pass otherwise.
    """
    harvest._require_publication_title("fix(daemon): stop dropping the lane trailer")

    for rejected in (
        "",
        "   ",
        "fix: OPEN]",
        "fix: short",
        "add a thing",
        "fix: " + "x" * 80,
    ):
        with pytest.raises(harvest.HarvestError):
            harvest._require_publication_title(rejected)


def test_affected_tests_separates_refusal_from_failure() -> None:
    """A missing testmon graph is not a red test run, and must not read as one.

    Anti-vacuity: collapsing the two makes an unavailable selection block
    publication; dropping the check makes a real failure publish.
    """
    context = harvest.HarvestContext(
        worktree=Path("/realm/worktrees/fixture"),
        project_id="polylogue",
        workspace_id="worktree-abc",
        job_id="job-1",
        state_root=Path("/realm/state/fixture"),
    )

    def run_with(returncode: int, stdout: str):
        def run(argv, **kwargs):
            return subprocess.CompletedProcess(argv, returncode, stdout, "")

        return run

    assert harvest._affected_tests(context, run_with(0, "ok"))[0] == "passed"
    assert (
        harvest._affected_tests(context, run_with(1, "failed 3 tests"))[0] == "failed"
    )
    refusal = "testmon graph is incompatible; refusing to run selected verification"
    assert harvest._affected_tests(context, run_with(2, refusal))[0] == "unavailable"


def test_silent_refusal_is_unavailable_not_red(tmp_path: Path) -> None:
    """The real refusal prints nothing, so only the receipt can name it.

    ``devtools verify`` without a compatible testmon graph exits 2 and writes
    to neither stream. Reading the prose is therefore not enough, and treating
    the silence as a failure blocks publication for a lane whose tests are
    fine.

    Anti-vacuity: drop the receipt read and this returns "failed"; drop the
    tier or diagnosis checks and a genuinely red run reports "unavailable".
    """
    run_dir = tmp_path / ".cache/verify/runs/20260828T034732Z-affected"
    run_dir.mkdir(parents=True)
    receipt = {
        "run_id": "20260828T034732Z-affected",
        "tier": "affected",
        "status": "failed",
        "exit_code": 2,
        "diagnosis": "native_testmon_graph_unavailable",
        "testmon_selection": {
            "selection_mode": "affected",
            "state_status": "absent",
            "state_reason": "native environment 'polylogue-6c675d4d' is absent",
        },
        "pytest_aggregate": {"selection_mode": "none"},
    }
    (run_dir / "run.json").write_text(json.dumps(receipt))

    context = harvest.HarvestContext(
        worktree=tmp_path,
        project_id="polylogue",
        workspace_id="worktree-abc",
        job_id="job-1",
        state_root=tmp_path / "state",
    )

    def run_silent(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 2, "", "")

    verdict, output = harvest._affected_tests(context, run_silent)
    assert verdict == "unavailable"
    assert "native_testmon_graph_unavailable" in output
    assert "polylogue-6c675d4d" in output

    red = dict(receipt)
    red.pop("diagnosis")
    red["testmon_selection"] = {"selection_mode": "affected", "state_status": "present"}
    red["pytest_aggregate"] = {"selection_mode": "affected", "outcomes": {"failed": 3}}
    (run_dir / "run.json").write_text(json.dumps(red))
    verdict, output = harvest._affected_tests(context, run_silent)
    assert verdict == "failed"
    assert output.strip(), "a silent failure must still explain itself"


def test_redflags_catches_a_new_module_that_no_test_touches() -> None:
    """New production code passes every other gate: nothing removed, nothing to select.

    Anti-vacuity: dropping the new-module check makes the first case clean,
    and ignoring touched test files makes the second case flag spuriously.
    """
    untested = (
        "diff --git a/polylogue/insights/widget_materializer.py "
        "b/polylogue/insights/widget_materializer.py\n"
        "new file mode 100644\n"
        "+def materialize():\n"
        "diff --git a/tests/unit/daemon/test_stages.py b/tests/unit/daemon/test_stages.py\n"
        '+        "widget",\n'
    )
    status, flags = harvest._redflags(untested)
    assert status == 1
    assert any("widget_materializer.py" in f for f in flags)

    tested = untested + (
        "diff --git a/tests/unit/insights/test_widget_materializer.py "
        "b/tests/unit/insights/test_widget_materializer.py\n"
        "new file mode 100644\n"
        "+def test_materialize():\n"
    )
    _, flags = harvest._redflags(tested)
    assert not any("without a test" in f for f in flags)


def test_a_failed_run_is_not_test_evidence(tmp_path: Path) -> None:
    """Tests having run is not the same as tests having passed.

    Anti-vacuity: without the status check a lane whose gate failed still reads
    as `tests-run` and qualifies to publish mechanically.
    """
    runs = tmp_path / ".cache/verify/runs"
    (runs / "a").mkdir(parents=True)
    (runs / "a" / "run.json").write_text(
        json.dumps(
            {
                "argv": ["devtools", "verify", "--quick"],
                "status": "failed",
                "git_head": "abc",
                "final_git_head": "abc",
                "pytest_aggregate": {"selected_union_count": 3},
            }
        )
    )

    assert harvest._verification_evidence(tmp_path, "abc")["state"] == "static-only"

    (runs / "a" / "run.json").write_text(
        json.dumps(
            {
                "argv": ["devtools", "verify", "--quick"],
                "status": "success",
                "git_head": "abc",
                "final_git_head": "abc",
                "pytest_aggregate": {"selected_union_count": 3},
            }
        )
    )
    assert harvest._verification_evidence(tmp_path, "abc")["state"] == "tests-run"
def test_review_route_auto_publishes_only_clean_docs_and_tests() -> None:
    result = route_review(
        changed_paths=("docs/review.md", "tests/test_review.py"),
        scanner_output="diff lines: 4\n",
    )

    assert result.route == "auto-publish"
    assert result.reviewer_model is None


def test_review_route_dispatches_cross_family_for_ordinary_production() -> None:
    result = route_review(
        changed_paths=("polylogue/module.py",),
        scanner_output="diff lines: 4\n",
        implementation_backend="codex",
    )

    assert result.route == "review-lane"
    assert (result.reviewer_backend, result.reviewer_model) == (
        "claude",
        "claude-opus-5",
    )


def test_review_route_escalates_uncleared_and_risky_flags() -> None:
    result = route_review(
        changed_paths=("polylogue/module.py",),
        scanner_output=(
            "FLAG: production lines removed (polylogue/)\n"
            "EXPLAIN: production lines removed\n"
        ),
    )
    assert result.route == "coordinator"
    assert result.unresolved

    risky = route_review(
        changed_paths=("polylogue/module.py",),
        scanner_output=(
            "FLAG: durable migration touched\n"
            "  VERDICT: migration metadata is present\n"
        ),
    )
    assert risky.route == "coordinator"


def _parsed(**overrides: object) -> object:
    """The argparse defaults that matter: title and body are "", not None."""
    import argparse

    values = {
        "title": "",
        "title_file": None,
        "body": "",
        "body_file": None,
        "close_reason": None,
        "close_reason_file": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_publication_text_falls_back_to_the_lane_artifacts(tmp_path: Path) -> None:
    """The real call site, with the real argparse defaults.

    --title and --body default to the empty string, so an `is None` guard never
    fires and the publication dies with 'harvest publication title is empty'
    after the gate has already run.
    """
    root, _remote = _repository(tmp_path)
    lane = root / ".lane"
    lane.mkdir()
    (lane / "title").write_text("fix(storage): restore the sidecar blob owner\n")
    (lane / "body.md").write_text("## Summary\n\nRestores the owner.\n")
    (lane / "close-reason.md").write_text("Merged: owner restored.\n")
    context = _context(root, tmp_path / "state")

    title, body, close_reason = harvest._resolve_publication_text(_parsed(), context)

    assert title == "fix(storage): restore the sidecar blob owner"
    assert body == "## Summary\n\nRestores the owner."
    assert close_reason == "Merged: owner restored."


def test_an_explicit_title_still_wins_over_the_lane_artifact(tmp_path: Path) -> None:
    root, _remote = _repository(tmp_path)
    lane = root / ".lane"
    lane.mkdir()
    (lane / "title").write_text("fix(storage): the lane's own subject\n")
    context = _context(root, tmp_path / "state")

    title, _body, _reason = harvest._resolve_publication_text(
        _parsed(title="fix(storage): the caller's subject"), context
    )

    assert title == "fix(storage): the caller's subject"


def test_lane_artifacts_supply_the_publication_title_and_body(tmp_path: Path) -> None:
    """The worker contract has the lane write these; harvest must read them.

    Without this, every coordinator has to point --title-file at a path the
    contract already fixed, and forgetting to fails the publication with
    'harvest publication title is empty' after the gate has already run.
    """
    root, _remote = _repository(tmp_path)
    lane = root / ".lane"
    lane.mkdir()
    (lane / "title").write_text("fix(storage): restore the sidecar blob owner\n")
    (lane / "body.md").write_text("## Summary\n\nRestores the owner.\n")
    (lane / "close-reason.md").write_text("Merged: owner restored.\n")
    context = _context(root, tmp_path / "state")

    assert (
        harvest._lane_artifact(context, "title")
        == "fix(storage): restore the sidecar blob owner"
    )
    assert harvest._lane_artifact(context, "body.md") == "## Summary\n\nRestores the owner."
    assert harvest._lane_artifact(context, "close-reason.md") == "Merged: owner restored."


def test_absent_or_blank_lane_artifacts_read_as_absent(tmp_path: Path) -> None:
    """A missing or whitespace-only file must not become an empty title."""
    root, _remote = _repository(tmp_path)
    context = _context(root, tmp_path / "state")

    assert harvest._lane_artifact(context, "title") is None

    lane = root / ".lane"
    lane.mkdir()
    (lane / "title").write_text("   \n")
    assert harvest._lane_artifact(context, "title") is None


def test_publication_adopts_the_open_pull_request_it_already_pushed(
    tmp_path: Path,
) -> None:
    """A publication that failed after `gh pr create` must be re-runnable.

    Without adoption the lane is stuck: the branch has an open pull request, so
    creation fails forever and nothing merges it.
    """
    root, _remote = _repository(tmp_path)
    context = _context(root, tmp_path / "state")
    calls: list[list[str]] = []

    def run(argv, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(list(argv))
        if argv[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(
                argv, 0, "https://github.com/o/r/pull/4387 OPEN", ""
            )
        return subprocess.CompletedProcess(argv, 0, "", "")

    url = harvest._adopt_open_pull_request(
        context, run, title="fix(x): subject", body="## Summary\n"
    )

    assert url == "https://github.com/o/r/pull/4387"
    assert ["gh", "pr", "edit", url, "--title", "fix(x): subject", "--body", "## Summary\n"] in calls


def test_publication_does_not_adopt_a_closed_pull_request(tmp_path: Path) -> None:
    root, _remote = _repository(tmp_path)
    context = _context(root, tmp_path / "state")

    def run(argv, **kwargs):  # type: ignore[no-untyped-def]
        if argv[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(
                argv, 0, "https://github.com/o/r/pull/4387 MERGED", ""
            )
        raise AssertionError("a merged pull request must not be edited")

    assert (
        harvest._adopt_open_pull_request(
            context, run, title="fix(x): subject", body="b"
        )
        is None
    )
