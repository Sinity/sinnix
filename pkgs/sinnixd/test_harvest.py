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
        title="Harvest lane",
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
        title="Harvest lane",
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
        if argv[:3] == ["devtools", "verify", "--quick"]:
            return subprocess.CompletedProcess(argv, 1, "gate failed", "")
        if argv[:2] == ["git", "push"]:
            pushed = True
        return subprocess.run(argv, **kwargs)

    result = harvest.authorize(
        context,
        receipt_ref=receipt,
        title="Harvest lane",
        body="Reviewed packet.",
        run=run,
        watch=False,
    )

    assert result["outcome"] == harvest.GATE_RED
    assert pushed is False


def test_redflags_preserves_the_coordinator_scanner_contract() -> None:
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
