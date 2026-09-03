from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import sinnixd.harvest as harvest


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


def _verified_job(root: Path, state: Path, context: harvest.HarvestContext) -> str:
    """Plant a succeeded verify_affected job for the workspace at its current HEAD."""
    job_id = "0f7d4d0e-2f6a-4b1e-9c0a-3d1e5a6b7c8d"
    (state / "jobs").mkdir(parents=True, exist_ok=True)
    (state / "jobs" / f"{job_id}.json").write_text(
        json.dumps(
            {
                "spec": {
                    "operation": "verify_affected",
                    "checkout": {
                        "checkout_id": context.workspace_id,
                        "head": harvest._git(subprocess.run, root, "rev-parse", "HEAD"),
                    },
                },
                "state": {"phase": "succeeded", "terminal": True},
                "artifacts": {},
            }
        )
    )
    return job_id


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
    assert packet["verification"] == {"state": "absent"}
    assert (state / "harvest-packets" / f"{packet['packet_id']}.diff").is_file()
    event = json.loads((state / "events.jsonl").read_text())
    assert event["kind"] == "harvest"
    assert event["transition"] == "review-required"


def test_failing_oracle_returns_gate_red_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state)
    published = False

    def publish_sentinel(*_args, **_kwargs):
        nonlocal published
        published = True
        pytest.fail("failing oracle reached publication")

    monkeypatch.setattr(harvest, "authorize", publish_sentinel)

    result = harvest.compile_packet(
        context, oracle_command="printf 'clone mismatch\\n' >&2; exit 7"
    )

    assert result["outcome"] == harvest.GATE_RED
    assert result["oracle"]["exit_code"] == 7
    assert result["oracle"]["stderr"] == "clone mismatch\n"
    assert published is False


def test_authorize_rejects_a_changed_oracle_command_in_receipt(
    tmp_path: Path,
) -> None:
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state)
    compiled = harvest.compile_packet(context, oracle_command="printf 'stable\\n'")
    packet_id = compiled["packet"]["packet_id"]
    receipt_path = state / "harvest-packets" / f"{packet_id}.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["oracle"]["command"] = "printf 'changed\\n'"
    receipt_path.write_text(json.dumps(receipt))

    with pytest.raises(harvest.HarvestError, match="oracle receipt is invalid"):
        harvest.authorize(
            context,
            receipt_ref=compiled["receipt_ref"],
            title="fix: publish the harvested lane branch",
            body="Reviewed packet.",
        )


def test_authorize_rejects_a_receipt_without_the_oracle_digest(
    tmp_path: Path,
) -> None:
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state)
    compiled = harvest.compile_packet(context, oracle_command="printf 'stable\\n'")
    packet_id = compiled["packet"]["packet_id"]
    receipt_path = state / "harvest-packets" / f"{packet_id}.json"
    receipt = json.loads(receipt_path.read_text())
    del receipt["oracle"]["command_sha256"]
    receipt_path.write_text(json.dumps(receipt))

    with pytest.raises(harvest.HarvestError, match="oracle receipt is invalid"):
        harvest.authorize(
            context,
            receipt_ref=compiled["receipt_ref"],
            title="fix: publish the harvested lane branch",
            body="Reviewed packet.",
        )


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

    verified = _verified_job(root, state, context)
    result = harvest.authorize(
        context,
        receipt_ref=packet,
        title="fix: publish the harvested lane branch",
        body="Reviewed packet.",
        run=run,
        affected_job=verified,
    )

    assert result == {
        "outcome": harvest.HARVEST_OK,
        "phase": "published",
        "pr": "42",
        "pr_url": "https://github.test/pull/42",
        "merge_state": "AUTO-MERGE-ARMED",
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
            affected_job=_verified_job(root, state, context),
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


def test_authorize_arms_auto_merge_after_pr_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state, "handoff-job")
    receipt = harvest.compile_packet(
        context, bead_id="sinnix-handoff", close_reason="merged by reactor"
    )["receipt_ref"]
    monkeypatch.setattr(harvest, "LOCK_PATH", tmp_path / "harvest.lock")
    merged: list[list[str]] = []

    def run(argv, **kwargs):
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
            merged.append(list(argv))
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.run(argv, **kwargs)

    result = harvest.authorize(
        context,
        affected_job=_verified_job(root, state, context),
        receipt_ref=receipt,
        title="fix: publish the harvested lane branch",
        body="Reviewed packet.",
        run=run,
    )

    assert result["merge_state"] == "AUTO-MERGE-ARMED"
    assert merged == [
        ["gh", "pr", "merge", "--squash", "--auto", "https://github.test/pull/43"]
    ]


def test_authorize_records_refused_auto_merge_and_leaves_pr_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auto-merge disabled on the repository must not fall back to a direct merge."""
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state, "refused-job")
    receipt = harvest.compile_packet(
        context, bead_id="sinnix-refused", close_reason="merged by reactor"
    )["receipt_ref"]
    monkeypatch.setattr(harvest, "LOCK_PATH", tmp_path / "harvest.lock")

    def run(argv, **kwargs):
        if argv[:2] == ["devtools", "verify"] and len(argv) == 2:
            return subprocess.CompletedProcess(
                argv, 0, "affected verification passed", ""
            )
        if argv[:3] == ["devtools", "verify", "--quick"]:
            return subprocess.CompletedProcess(argv, 0, "quick gate passed", "")
        if argv[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(
                argv, 0, "https://github.test/pull/44\n", ""
            )
        if argv[:3] == ["gh", "pr", "merge"]:
            return subprocess.CompletedProcess(
                argv, 1, "", "auto-merge is not enabled for this repository"
            )
        return subprocess.run(argv, **kwargs)

    result = harvest.authorize(
        context,
        affected_job=_verified_job(root, state, context),
        receipt_ref=receipt,
        title="fix: publish the harvested lane branch",
        body="Reviewed packet.",
        run=run,
    )

    assert result["merge_state"] == "AUTO-MERGE-REFUSED"
    assert any(
        row.get("kind") == "needs-merge"
        and row.get("merge_error") == "auto-merge is not enabled for this repository"
        for row in map(json.loads, (state / "events.jsonl").read_text().splitlines())
    )
    events = [
        json.loads(row) for row in (state / "events.jsonl").read_text().splitlines()
    ]
    handoff = next(event for event in events if event["kind"] == "needs-merge")
    assert handoff["pr"] == "44"
    packet_id = receipt.rsplit("/", 1)[-1]
    assert handoff["decision_receipt"] == {
        "receipt_id": json.loads(
            (state / "harvest-packets" / f"{packet_id}.json").read_text()
        )["packet_id"],
        "bead_id": "sinnix-refused",
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
        affected_job=_verified_job(root, state, context),
        receipt_ref=receipt,
        title="fix: publish the harvested lane branch",
        body="Reviewed packet.",
        run=run,
    )

    assert result["outcome"] == harvest.GATE_RED
    assert pushed is False


def test_unavailable_affected_tests_are_typed_and_spooled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refused affected selection reaches the reactor with typed context."""
    root, _remote = _repository(tmp_path)
    state = tmp_path / "state"
    context = _context(root, state, "unavailable-job")
    receipt = harvest.compile_packet(context)["receipt_ref"]
    monkeypatch.setattr(
        harvest,
        "_load_receipt",
        lambda _context, _receipt_ref: {
            "head": harvest._git(subprocess.run, root, "rev-parse", "HEAD"),
            "worktree_unstaged_sha256": harvest._digest(
                harvest._git(subprocess.run, root, "diff", "HEAD")
            ),
            "worktree_staged_sha256": harvest._digest(
                harvest._git(subprocess.run, root, "diff", "--cached")
            ),
        },
    )

    result = harvest.authorize(
        context,
        receipt_ref=receipt,
        title="fix(harvest): report unavailable test selection",
        body="Reviewed packet.",
    )
    assert result["outcome"] == harvest.NO_TEST_EVIDENCE

    events = [
        json.loads(row) for row in (state / "events.jsonl").read_text().splitlines()
    ]
    assert events[-1]["outcome"] == harvest.NO_TEST_EVIDENCE
    assert events[-1]["detail"] == "no affected verification job for this head"


def test_redflags_flags_vanished_definitions_and_net_assertion_loss() -> None:
    status, flags = harvest._redflags(
        "diff --git a/polylogue/module.py b/polylogue/module.py\n"
        "-def removed():\n"
        "-def renamed():\n"
        "+def renamed_to():\n"
        "+def renamed():\n"
        "diff --git a/tests/test_module.py b/tests/test_module.py\n"
        "-    assert old\n"
        "-    assert older\n"
        "+    assert new\n"
    )

    assert status == 1
    assert "FLAG: production definitions removed: removed" in flags
    assert "FLAG: test assertions removed: 1 net" in flags


def test_redflags_ignores_edits_that_keep_definitions_and_assertions() -> None:
    """Anti-vacuity: the previous scanner flagged every removed line holding
    ``self.`` or ``()``, which parked ordinary edits for a reader."""
    status, flags = harvest._redflags(
        "diff --git a/polylogue/module.py b/polylogue/module.py\n"
        "-    value = self.compute()\n"
        "+    value = self.compute(strict=True)\n"
        "-def moved():\n"
        "diff --git a/polylogue/other.py b/polylogue/other.py\n"
        "+def moved():\n"
        "diff --git a/tests/test_module.py b/tests/test_module.py\n"
        "-    assert old\n"
        "+    assert new\n"
        "+    assert newer\n"
    )

    assert status == 0
    assert not [flag for flag in flags if flag.startswith("FLAG:")]


def test_redflags_flags_a_deleted_production_file() -> None:
    status, flags = harvest._redflags(
        "diff --git a/polylogue/gone.py b/polylogue/gone.py\n"
        "deleted file mode 100644\n"
        "-VALUE = 1\n"
        "diff --git a/tests/test_gone.py b/tests/test_gone.py\n"
        "deleted file mode 100644\n"
    )

    assert status == 1
    assert "FLAG: production file deleted: polylogue/gone.py" in flags


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


def _parsed(**overrides: object) -> object:
    """The argparse defaults of the publication-text flags."""
    import argparse

    values = {
        "title_file": None,
        "body_file": None,
        "close_reason_file": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_publication_text_falls_back_to_the_lane_artifacts(tmp_path: Path) -> None:
    """Publication text comes from the lane's own artifacts when no file is named."""
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
                    # The campaign launcher names the bead through the wave
                    # parameters, not through a bead binding.
                    "contract": {
                        "parameters": {"campaign": {"group": "polylogue-zzz1"}}
                    },
                },
                "state": {"phase": "succeeded"},
            }
        )
    )
    # A newer review-fix lane on the same checkout carries no bead; it must
    # not displace the lane that does (PR #4507 published with no bead).
    (jobs_root / "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb.json").write_text(
        json.dumps(
            {
                "job_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "created_at": "2026-08-30T11:00:00+00:00",
                "spec": {
                    "kind": "attested-agent",
                    "checkout": {"checkout_id": "worktree-1"},
                    "contract": {"coordinator_label": "review-fix"},
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
    result = harvest.publish(
        context, close=True, affected_job=_verified_job(root, state, context)
    )
    assert result["outcome"] == harvest.HARVEST_OK
    assert captured.get("lane_job_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa") == (
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    )
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


def test_publication_text_from_files_matches_the_minted_binding(tmp_path: Path) -> None:
    """Anti-vacuity: reading the file raw keeps its trailing newline, and every
    mechanical publish then fails as "text differs from the reviewed receipt"."""
    import argparse
    from types import SimpleNamespace

    lane = tmp_path / ".lane"
    lane.mkdir()
    (lane / "title").write_text("fix: bound text\n")
    (lane / "body.md").write_text("Body.\n\n")
    context = SimpleNamespace(worktree=tmp_path)
    minted = harvest._digest(harvest._lane_artifact(context, "title") or "")
    parsed = argparse.Namespace(
        title="", title_file=lane / "title", body="", body_file=lane / "body.md"
    )
    title = harvest._read_text(parsed.title_file, "t").strip()
    assert harvest._digest(title) == minted
    assert harvest._digest(
        harvest._read_text(parsed.body_file, "b").strip()
    ) == harvest._digest(harvest._lane_artifact(context, "body.md") or "")


def test_redflags_polarity_needs_a_removed_success_assertion() -> None:
    """Anti-vacuity: an added ``pytest.raises`` alone parked
    packet-polylogue-aex0-publication (2026-09-02 01:12Z)."""
    _, added_only = harvest._redflags(
        "diff --git a/tests/test_module.py b/tests/test_module.py\n"
        "+    with pytest.raises(ValueError):\n"
        "+        act()\n"
    )
    assert "FLAG: assertion polarity change" not in added_only

    _, flipped = harvest._redflags(
        "diff --git a/tests/test_module.py b/tests/test_module.py\n"
        "-    assert result.exit_code == 0\n"
        "+    with pytest.raises(ValueError):\n"
        "+        act()\n"
    )
    assert "FLAG: assertion polarity change" in flipped


def test_redflags_gate_flag_names_gates_not_every_verify_module() -> None:
    """Anti-vacuity: the `verify` prefix matched verify_runs.py (receipt
    bookkeeping) and parked packet-polylogue-a74ru for a reader."""
    _, bookkeeping = harvest._redflags(
        'diff --git a/devtools/verify_runs.py b/devtools/verify_runs.py\n+    row["agentctl"] = 1\n'
    )
    assert not any(flag.startswith("FLAG: verification gate") for flag in bookkeeping)

    _, gate = harvest._redflags(
        "diff --git a/devtools/verify.py b/devtools/verify.py\n+    pass\n"
    )
    assert "FLAG: verification gate or baseline edited" in gate


def test_redflags_catches_private_evidence_references() -> None:
    """Anti-vacuity: #4529 published rawlog dates and note categories in
    docs/ before a reader noticed."""
    status, flags = harvest._redflags(
        "diff --git a/docs/queue.md b/docs/queue.md\n"
        "+| Q01 | ... | Operator rawlog, 2026-07-07, planning note |\n"
    )
    assert status == 1
    assert "FLAG: private evidence reference in tracked text" in flags


def test_authorization_binds_the_head(tmp_path: Path) -> None:
    from sinnixd.harvest import HarvestContext, _authorization

    context = HarvestContext(
        worktree=tmp_path,
        project_id="polylogue",
        workspace_id="worktree-x",
        job_id="job-1",
        state_root=tmp_path / "state",
    )
    assert _authorization(context, "a" * 40) is None
    (tmp_path / ".lane").mkdir()
    (tmp_path / ".lane" / "authorization.json").write_text(
        json.dumps({"head": "a" * 40, "reason": "reviewed by hand"})
    )
    assert _authorization(context, "a" * 40) == {
        "head": "a" * 40,
        "reason": "reviewed by hand",
        "at": "",
        "by": "operator",
    }
    assert _authorization(context, "b" * 40) is None


def test_redflags_catches_ignored_paths_committed() -> None:
    """Anti-vacuity: a lane force-added .lane/ after master untracked it
    (2026-09-02); no prose rule stopped it."""
    status, flags = harvest._redflags(
        "diff --git a/.lane/title b/.lane/title\n+fix: thing\n",
        ignored_paths=(".lane/title",),
    )
    assert status == 1
    assert "FLAG: ignored paths committed: .lane/title" in flags
