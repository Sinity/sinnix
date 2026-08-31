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


def test_cancelled_harvest_restores_rebased_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancellation after rebase leaves the managed checkout unchanged."""
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state, "cancel-job")
    receipt = harvest.compile_packet(context)["receipt_ref"]

    assert _run_git(root, "switch", "master").returncode == 0
    (root / "polylogue" / "base.py").write_text("BASE = 2\n")
    _run_git(root, "add", ".")
    assert _run_git(root, "commit", "--quiet", "-m", "advance base").returncode == 0
    assert _run_git(root, "push", "--quiet", "origin", "master").returncode == 0
    assert _run_git(root, "switch", "feature/fixture").returncode == 0
    original_head = _run_git(root, "rev-parse", "HEAD").stdout.strip()
    monkeypatch.setattr(harvest, "LOCK_PATH", tmp_path / "harvest.lock")

    def run(argv, **kwargs):
        if argv[:2] == ["devtools", "verify"] and len(argv) == 2:
            return subprocess.CompletedProcess(
                argv, 0, "affected verification passed", ""
            )
        if argv[:3] == ["devtools", "verify", "--quick"]:
            raise KeyboardInterrupt
        return subprocess.run(argv, **kwargs)

    with pytest.raises(KeyboardInterrupt):
        harvest.authorize(
            context,
            receipt_ref=receipt,
            title="fix: restore cancelled harvest workspaces",
            body="Reviewed packet.",
            run=run,
        )

    assert _run_git(root, "rev-parse", "HEAD").stdout.strip() == original_head
    assert (
        _run_git(root, "branch", "--show-current").stdout.strip() == "feature/fixture"
    )
    assert _run_git(root, "status", "--porcelain", "--untracked-files=all").stdout == ""
    assert not (root / ".git" / "rebase-merge").exists()


def test_authorize_returns_after_pr_creation_and_emits_merge_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state, "handoff-job")
    receipt = harvest.compile_packet(
        context, bead_id="sinnix-handoff", close_reason="merged by reactor"
    )["receipt_ref"]
    monkeypatch.setattr(harvest, "LOCK_PATH", tmp_path / "harvest.lock")
    viewed = False

    def run(argv, **kwargs):
        nonlocal viewed
        if argv[:2] == ["devtools", "verify"] and len(argv) == 2:
            return subprocess.CompletedProcess(
                argv, 0, "affected verification passed", ""
            )
        if argv[:3] == ["devtools", "verify", "--quick"]:
            return subprocess.CompletedProcess(argv, 0, "quick gate passed", "")
        if argv[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(
                argv, 0, "https://github.test/pull/43\n", ""
            )
        if argv[:3] == ["gh", "pr", "merge"]:
            return subprocess.CompletedProcess(argv, 1, "", "auto-merge unavailable")
        if argv[:3] == ["gh", "pr", "view"]:
            viewed = True
        return subprocess.run(argv, **kwargs)

    result = harvest.authorize(
        context,
        receipt_ref=receipt,
        title="fix: publish the harvested lane branch",
        body="Reviewed packet.",
        run=run,
    )

    assert result["merge_state"] == "NEEDS-MERGE"
    assert viewed is False
    events = [
        json.loads(row) for row in (state / "events.jsonl").read_text().splitlines()
    ]
    handoff = next(event for event in events if event["kind"] == "needs-merge")
    assert handoff["pr"] == "43"
    packet_id = receipt.rsplit("/", 1)[-1]
    assert handoff["decision_receipt"] == {
        "receipt_id": json.loads(
            (state / "harvest-packets" / f"{packet_id}.json").read_text()
        )["packet_id"],
        "bead_id": "sinnix-handoff",
        "reason": "merged by reactor",
    }


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


def test_redflags_flags_paths_outside_declared_write_scope() -> None:
    diff = (
        "diff --git a/pkgs/sinnixd/sinnixd/harvest.py "
        "b/pkgs/sinnixd/sinnixd/harvest.py\n"
        "+scope-aware scanner\n"
        "diff --git a/README.md b/README.md\n"
        "+unrelated change\n"
    )

    status, flags = harvest._redflags(
        diff,
        write_scope=["pkgs/sinnixd/"],
        changed_paths=["pkgs/sinnixd/sinnixd/harvest.py", "README.md"],
    )

    assert status == 1
    assert "FLAG: changed paths outside declared write scope: README.md" in flags

    status, flags = harvest._redflags(
        diff,
        write_scope=["pkgs/sinnixd/"],
        changed_paths=["pkgs/sinnixd/sinnixd/harvest.py"],
    )
    assert status == 0
    assert not any("outside declared write scope" in flag for flag in flags)


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


def test_redflags_catches_a_behaviour_change_with_no_test_in_the_diff() -> None:
    """A modified production module with no test anywhere is invisible to every gate.

    The lane's own green is a static run that selects nothing, so nothing
    observes the change it just made, and the existing new-module check only
    covers files added in this diff.

    Anti-vacuity: drop the check and the first case reports no flag; count any
    touched test file and the second case flags spuriously.
    """
    untested = (
        "diff --git a/polylogue/mcp/server_cutover.py b/polylogue/mcp/server_cutover.py\n"
        '+            if view == "messages":\n'
    )
    status, flags = harvest._redflags(untested)
    assert status == 1
    assert any("no test in the diff" in f for f in flags)
    assert any("server_cutover.py" in f for f in flags)

    tested = untested + (
        "diff --git a/tests/unit/mcp/test_read_messages_view.py "
        "b/tests/unit/mcp/test_read_messages_view.py\n"
        "new file mode 100644\n"
        "+def test_read_serves_the_messages_view():\n"
    )
    _, flags = harvest._redflags(tested)
    assert not any("no test in the diff" in f for f in flags)


def test_a_docs_only_change_is_not_flagged_for_missing_tests() -> None:
    """The flag is about production behaviour, not every file in a repo."""
    _, flags = harvest._redflags(
        "diff --git a/docs/architecture.md b/docs/architecture.md\n+A sentence.\n"
    )

    assert not any("no test in the diff" in f for f in flags)


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
    assert (
        harvest._lane_artifact(context, "body.md")
        == "## Summary\n\nRestores the owner."
    )
    assert (
        harvest._lane_artifact(context, "close-reason.md") == "Merged: owner restored."
    )


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
    assert [
        "gh",
        "pr",
        "edit",
        url,
        "--title",
        "fix(x): subject",
        "--body",
        "## Summary\n",
    ] in calls


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


def test_a_lane_with_nothing_to_publish_reports_its_close_reason(
    tmp_path: Path,
) -> None:
    """A bead already satisfied on master leaves the lane with no diff.

    Compiling a review packet for it would send an empty branch to publication,
    where `gh pr create` fails with no commits between the branches.
    """
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    _run_git(root, "reset", "--hard", "--quiet", "origin/master")
    context = _context(root, state)

    result = harvest.compile_packet(
        context,
        bead_id="polylogue-teyyg",
        close_reason="Already satisfied on master.",
    )

    assert result["outcome"] == harvest.HARVEST_EMPTY
    assert result["phase"] == "nothing-to-publish"
    assert result["bead_id"] == "polylogue-teyyg"
    assert result["close_reason"] == "Already satisfied on master."
    assert "receipt_ref" not in result


def test_repo_slug_parses_github_and_labels_local_remotes(tmp_path: Path) -> None:
    root, _remote = _repository(tmp_path)
    assert harvest._repo_slug(subprocess.run, root).startswith("local/")
    _run_git(root, "remote", "set-url", "origin", "git@github.com:Example/repo.git")
    assert harvest._repo_slug(subprocess.run, root) == "Example/repo"
    _run_git(root, "remote", "set-url", "origin", "https://github.com/Example/other")
    assert harvest._repo_slug(subprocess.run, root) == "Example/other"


def test_publish_derives_identity_and_authorizes_in_one_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One invocation mints the receipt and publishes it; nothing is restated."""
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state, job_id="publish-job")
    lane_dir = root / ".lane"
    lane_dir.mkdir()
    (lane_dir / "title").write_text("fix: publish the harvested lane branch\n")
    (lane_dir / "body.md").write_text("Reviewed packet.\n")
    (lane_dir / "close-reason.md").write_text("Delivered and verified.\n")
    jobs_root = state / "jobs"
    jobs_root.mkdir(parents=True)
    (jobs_root / "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa.json").write_text(
        json.dumps(
            {
                "job_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "created_at": "2026-08-30T10:00:00+00:00",
                "spec": {
                    "kind": "attested-agent",
                    "checkout": {"checkout_id": "worktree-1"},
                    "contract": {"bead_binding": {"bead_id": "polylogue-zzz1"}},
                },
                "state": {"phase": "succeeded"},
            }
        )
    )
    captured: dict[str, object] = {}

    def fake_authorize(ctx, **kwargs):
        captured.update(kwargs)
        return {"outcome": harvest.HARVEST_OK, "phase": "published"}

    monkeypatch.setattr(harvest, "authorize", fake_authorize)
    result = harvest.publish(context, close=True)
    assert result["outcome"] == harvest.HARVEST_OK
    assert captured["lane_job_id"] if "lane_job_id" in captured else True
    assert captured["bead_id"] == "polylogue-zzz1"
    assert captured["title"] == "fix: publish the harvested lane branch"
    assert captured["close_reason"] == "Delivered and verified."
    receipt_ref = captured["receipt_ref"]
    assert isinstance(receipt_ref, str) and receipt_ref.startswith("harvest-")


def test_publish_without_close_reason_artifact_refuses_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state)
    (root / ".lane").mkdir()
    (root / ".lane" / "title").write_text("fix: publish the harvested lane branch\n")
    (root / ".lane" / "body.md").write_text("Reviewed.\n")
    monkeypatch.setattr(
        harvest, "authorize", lambda ctx, **k: {"outcome": harvest.HARVEST_OK}
    )
    with pytest.raises(harvest.HarvestError, match="close-reason"):
        harvest.publish(context, close=True)


def test_unavailable_affected_verification_reaches_the_spool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity: dropping the spool append makes this red."""
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state)
    monkeypatch.setattr(
        harvest, "_affected_tests", lambda ctx, run: ("unavailable", "no graph")
    )
    monkeypatch.setattr(
        harvest,
        "_load_receipt",
        lambda ctx, ref: {
            "head": harvest._git(subprocess.run, root, "rev-parse", "HEAD"),
            "worktree_unstaged_sha256": harvest._digest(
                harvest._git(subprocess.run, root, "diff", "HEAD")
            ),
            "worktree_staged_sha256": harvest._digest(
                harvest._git(subprocess.run, root, "diff", "--cached")
            ),
        },
    )

    def stop_before_lock(path, timeout=900):
        raise harvest.HarvestError("stop before repository lock")

    monkeypatch.setattr(harvest, "_lock", stop_before_lock)
    with pytest.raises(harvest.HarvestError, match="stop before repository lock"):
        harvest.authorize(
            context,
            receipt_ref="harvest-" + "0" * 32,
            title="fix: publish the harvested lane branch",
            body="Reviewed.",
        )
    events = [
        json.loads(row) for row in (state / "events.jsonl").read_text().splitlines()
    ]
    assert any(event["kind"] == "verification-unavailable" for event in events)


def test_reminting_binds_the_currently_edited_publication_text(
    tmp_path: Path,
) -> None:
    """A re-mint after coordinator edits binds the edited text, and the
    receipt carries its digests (sinnix-3ynh AC1). Anti-vacuity: restoring
    stale artifacts over the edits would bind the stale digests instead."""
    root, _remote = _repository(tmp_path)
    lane_dir = root / ".lane"
    lane_dir.mkdir()
    (lane_dir / "title").write_text("fix: original reviewed subject")
    (lane_dir / "body.md").write_text("Original body.")
    state = tmp_path / "state"
    context = _context(root, state)
    first = harvest.compile_packet(context)
    first_receipt = json.loads(
        (state / "harvest-packets" / f"{first['packet']['packet_id']}.json").read_text()
    )

    (lane_dir / "title").write_text("fix: corrected subject after review")
    (lane_dir / "body.md").write_text("Corrected body.")
    second = harvest.compile_packet(context)
    second_receipt = json.loads(
        (
            state / "harvest-packets" / f"{second['packet']['packet_id']}.json"
        ).read_text()
    )

    import hashlib

    def digest(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    assert first_receipt["publication_text"]["title_sha256"] == digest(
        "fix: original reviewed subject"
    )
    assert second_receipt["publication_text"]["title_sha256"] == digest(
        "fix: corrected subject after review"
    )
    assert second_receipt["publication_text"]["body_sha256"] == digest(
        "Corrected body."
    )


def test_authorize_refuses_text_that_drifted_from_the_reviewed_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """.lane/ files are untracked, so HEAD equality alone would publish text
    nobody reviewed (sinnix-3ynh AC2). Anti-vacuity: omitting the text
    digests from the receipt lets the drifted body publish."""
    root, _remote = _repository(tmp_path)
    lane_dir = root / ".lane"
    lane_dir.mkdir()
    (lane_dir / "title").write_text("fix: publish the harvested lane branch")
    (lane_dir / "body.md").write_text("Reviewed body.")
    state = tmp_path / "state"
    context = _context(root, state, "drift-job")
    receipt_ref = harvest.compile_packet(context)["receipt_ref"]
    monkeypatch.setattr(harvest, "LOCK_PATH", tmp_path / "harvest.lock")

    with pytest.raises(harvest.HarvestError, match="differs from the reviewed"):
        harvest.authorize(
            context,
            receipt_ref=receipt_ref,
            title="fix: publish the harvested lane branch",
            body="Body silently rewritten after review.",
        )
