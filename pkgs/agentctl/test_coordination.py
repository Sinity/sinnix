"""Announced operations, discretionary deferral and build-output expiry."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from agentctl import build_output, cli, job_queries, launch
from agentctl.config import Config
from agentctl.projects import ProjectConfigError, load_project_adapter
from conftest import FakePueue, read_launch


def announced(project_root: Path):
    descriptor = project_root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'exec = ["fixture-nightly"]', 'exec = ["fixture-nightly"]\nannounce = true'
        )
    )
    return load_project_adapter(project_root)


def test_announce_must_be_a_boolean(project_root: Path) -> None:
    descriptor = project_root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'exec = ["fixture-nightly"]', 'exec = ["fixture-nightly"]\nannounce = "yes"'
        )
    )
    with pytest.raises(ProjectConfigError, match="announce"):
        load_project_adapter(project_root)


def test_second_caller_of_an_announced_operation_is_told_who_holds_it(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Breaks if a second activation request no longer names the first one's
    session, start time and commit, or if an unannounced job is listed."""
    subprocess.run(["git", "init", "-q", str(project_root)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(project_root),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "fixture",
        ],
        check=True,
    )
    head = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    project = announced(project_root)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "first-session-id")
    first = launch.start_operation(config, project, project.operation("nightly"))
    launch.start_operation(config, project, project.operation("check"))
    assert read_launch(config, fake_pueue.task(first["task_id"]))["revision"] == {
        "commit": head,
        "dirty": False,
    }

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "second-session-id")
    location = config.state_dir / "agentctl.json"
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(
        json.dumps(
            {
                "project_roots": [str(project_root)],
                "state_dir": str(config.state_dir),
                "event_spool": str(config.event_spool),
            }
        )
    )
    monkeypatch.setenv("AGENTCTL_CONFIG", str(location))
    assert cli.main(["job", "start", "fixture", "nightly"]) == 0

    captured = capsys.readouterr()
    assert "another activation holds the queue: fixture:nightly #1 is running" in (
        captured.err
    )
    assert "claude session first-se" in captured.err
    assert f"commit {head[:9]}" in captured.err
    ahead = json.loads(captured.out)["announced_ahead"]
    assert [row["task_id"] for row in ahead] == [first["task_id"]]
    rows = job_queries.snapshot_jobs(10, config)["jobs"]
    by_task = {row["task_id"]: row for row in rows}
    assert by_task[1]["announce"] is True and by_task[1]["revision"]["commit"] == head
    assert "announce" not in by_task[2]


def quota_check(tmp_path: Path, verdict: dict[str, object]) -> tuple[str, ...]:
    script = tmp_path / "quota-check"
    script.write_text(f"import json\nprint(json.dumps({verdict!r}))\n")
    return (sys.executable, str(script))


def test_only_a_job_marked_discretionary_is_held_until_the_reset(
    fake_pueue: FakePueue, config: Config, project_root: Path, tmp_path: Path
) -> None:
    """Breaks if an ordinary job is ever delayed, or a discretionary one starts
    while the check reports the subscription above its threshold."""
    reset = datetime.now(UTC) + timedelta(hours=5)
    config = replace(
        config,
        quota_check=quota_check(
            tmp_path,
            {
                "ok": False,
                "reason": "Claude weekly usage 91% is above 85%",
                "resets_at": reset.isoformat(timespec="seconds"),
            },
        ),
    )
    project = load_project_adapter(project_root)

    ordinary = launch.start_operation(config, project, project.operation("check"))
    held = launch.start_operation(
        config, project, project.operation("check"), discretionary=True
    )

    assert fake_pueue.added[0]["delay_seconds"] is None
    assert ordinary["phase"] == "running" and "deferred" not in ordinary
    delay = fake_pueue.added[1]["delay_seconds"]
    assert 5 * 3600 - 60 < delay <= 5 * 3600 + 60
    assert held["phase"] == "stashed"
    assert held["deferred"]["reason"] == "Claude weekly usage 91% is above 85%"
    row = {r["task_id"]: r for r in job_queries.snapshot_jobs(10, config)["jobs"]}[
        held["task_id"]
    ]
    assert row["deferred"]["until"] == held["deferred"]["until"]


@pytest.mark.parametrize(
    "verdict",
    [
        {"ok": True, "reason": "Claude weekly usage 40%"},
        {"ok": False, "reason": "above", "resets_at": None},
        {"ok": None, "reason": "usage could not be read"},
    ],
)
def test_discretionary_job_starts_when_the_check_does_not_say_wait(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    tmp_path: Path,
    verdict: dict[str, object],
) -> None:
    config = replace(config, quota_check=quota_check(tmp_path, verdict))
    project = load_project_adapter(project_root)

    started = launch.start_operation(
        config, project, project.operation("check"), discretionary=True
    )

    assert fake_pueue.added[0]["delay_seconds"] is None
    assert started["phase"] == "running"


# ---------------------------------------------------------------- build output


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def worktrees(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_pueue: FakePueue):
    """Three checkouts with ignored build output: one old, one fresh, one exempt."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("SINNIX_CARGO_CACHE_ROOT", str(tmp_path / "cargo"))
    root = tmp_path / "trees"
    old = time.time() - 40 * 86400
    for name in ("old", "fresh", "campaign-a"):
        tree = root / name
        tree.mkdir(parents=True)
        git(tree, "init", "-q", "-b", "master")
        (tree / ".gitignore").write_text("target/\nnode_modules/\n")
        (tree / "source.txt").write_text("source")
        (tree / "build").mkdir()
        (tree / "build" / "tracked.txt").write_text("a tracked directory named build")
        git(tree, "add", ".")
        git(
            tree,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "fixture",
        )
        (tree / "target").mkdir()
        (tree / "target" / "artifact").write_bytes(b"x" * 8192)
        if name != "fresh":
            for path in [tree, *tree.rglob("*")]:
                os.utime(path, (old, old))
    return root


def cache_entry(tmp_path: Path, checkout: Path, age_days: float) -> Path:
    import hashlib

    key = hashlib.sha256(str(checkout.resolve()).encode()).hexdigest()[:32]
    entry = tmp_path / "cargo" / str(os.getuid()) / key
    (entry / "target" / "debug" / "deps").mkdir(parents=True)
    (entry / "target" / "debug" / ".cargo-lock").write_text("")
    (entry / "target" / "debug" / "deps" / "libfixture.rlib").write_bytes(b"y" * 8192)
    (entry / "checkout").write_bytes(os.fsencode(checkout.resolve()) + b"\n")
    stamp = time.time() - age_days * 86400
    for path in [entry, *entry.rglob("*")]:
        os.utime(path, (stamp, stamp))
    return entry


def test_report_sizes_output_and_does_not_examine_exempt_checkouts(
    config: Config, worktrees: Path, tmp_path: Path
) -> None:
    config = replace(config, build_output_exempt=("campaign-*",))
    cache_entry(tmp_path, worktrees / "old", 40)

    listing = build_output.report(config, roots=[worktrees])

    rows = {row["name"]: row for row in listing["worktrees"]}
    assert rows["campaign-a"] == {
        "path": str(worktrees / "campaign-a"),
        "name": "campaign-a",
        "exempt": True,
    }
    assert [item["kind"] for item in rows["old"]["outputs"]] == [
        "in-tree",
        "cargo-cache",
    ]
    assert rows["old"]["bytes"] >= 16384
    assert rows["old"]["idle_days"] >= 39 and rows["fresh"]["idle_days"] < 1
    # A tracked directory with an output-like name is source, not output.
    assert all(
        Path(item["path"]).name != "build"
        for row in rows.values()
        for item in row.get("outputs", [])
    )


def test_expiry_is_a_dry_run_until_applied_and_removes_only_output(
    config: Config, worktrees: Path, tmp_path: Path
) -> None:
    """Breaks if a dry run deletes, if sources or the checkout are removed, or
    if a fresh or exempt checkout loses its build output."""
    config = replace(config, build_output_exempt=("campaign-*",))
    entry = cache_entry(tmp_path, worktrees / "old", 40)

    planned = build_output.expire(config, idle_days=30, roots=[worktrees])

    assert planned["applied"] is False
    assert {Path(item["path"]).name for item in planned["removed"]} == {"target"}
    assert (worktrees / "old" / "target" / "artifact").exists() and entry.exists()

    applied = build_output.expire(config, idle_days=30, apply=True, roots=[worktrees])

    assert applied["bytes"] >= 16384
    assert not (worktrees / "old" / "target").exists() and not entry.exists()
    assert (worktrees / "old" / "source.txt").read_text() == "source"
    assert (worktrees / "old" / "build" / "tracked.txt").exists()
    assert git(worktrees / "old", "status", "--porcelain") == ""
    assert (worktrees / "fresh" / "target" / "artifact").exists()
    assert (worktrees / "campaign-a" / "target" / "artifact").exists()
    reasons = {item["name"]: item["reason"] for item in applied["kept"]}
    assert reasons["campaign-a"] == "exempt by configuration"
    assert "under the 30-day limit" in reasons["fresh"]


def test_a_checkout_with_an_unfinished_job_or_a_process_keeps_its_output(
    config: Config, worktrees: Path, fake_pueue: FakePueue, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    launch.start_operation(
        config, project, project.operation("check"), workspace=worktrees / "old"
    )
    sleeper = subprocess.Popen(["sleep", "30"], cwd=worktrees / "campaign-a")
    try:
        applied = build_output.expire(
            config, idle_days=30, apply=True, roots=[worktrees]
        )
    finally:
        sleeper.kill()
        sleeper.wait()

    reasons = {item["name"]: item["reason"] for item in applied["kept"]}
    assert "job #1 fixture:check running" in reasons["old"]
    assert "process(es) work here" in reasons["campaign-a"]
    assert applied["removed"] == []
    assert (worktrees / "old" / "target" / "artifact").exists()
    assert (worktrees / "campaign-a" / "target" / "artifact").exists()
