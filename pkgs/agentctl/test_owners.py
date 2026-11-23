"""The ownership report: every entry has the owner that removes it, or is marked."""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from agentctl import owners

RUNNING = "11111111-2222-4333-8444-555555555555"
PARKED = "22222222-2222-4333-8444-555555555555"
ENDED = "33333333-2222-4333-8444-555555555555"
STOPPED = "44444444-2222-4333-8444-555555555555"


@pytest.fixture
def layout(tmp_path, monkeypatch, fake_pueue, config, scratch_roots):
    root = tmp_path / "work"
    worktrees = tmp_path / "worktree"
    cache = tmp_path / "cargo"
    for directory in (root, worktrees, cache / str(os.getuid())):
        directory.mkdir(parents=True)
    monkeypatch.setattr(owners, "TEMPORARY_ROOT", root)
    monkeypatch.setattr(owners, "PARKING", tmp_path / "parking")
    monkeypatch.setattr(owners.build_output, "worktree_roots", lambda _: [worktrees])
    monkeypatch.setenv("SINNIX_CARGO_CACHE_ROOT", str(cache))
    monkeypatch.setenv("AGENTCTL_NVME_SCRATCH_ROOT", str(root / "agentctl"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return root, worktrees, cache, fake_pueue


def rows_by_path(listing):
    return {
        row["path"]: row for rows in listing["sections"].values() for row in rows
    }


def test_job_scratch_is_owned_while_its_job_runs(layout, config):
    root, _, _, queue = layout
    running = queue.add(
        group="bulk",
        label="p:op",
        command=("agentctl-run", "/state/inputs/job-running.json"),
        working_directory=root,
    )
    finished = queue.add(
        group="bulk",
        label="p:op",
        command=("agentctl-run", "/state/inputs/job-done.json"),
        working_directory=root,
    )
    queue._tasks[finished] = replace(
        queue._tasks[finished], status="Done", result="Success"
    )
    for name in ("job-running", "job-done", "job-unknown"):
        (root / "agentctl" / name).mkdir(parents=True)
    rows = rows_by_path(owners.report(config))
    assert rows[str(root / "agentctl/job-running")]["owner"] == "job job-running"
    assert rows[str(root / "agentctl/job-done")]["owner"] is None
    assert rows[str(root / "agentctl/job-unknown")]["owner"] is None
    assert running in queue._tasks


def test_session_trees_name_their_session_and_loose_names_are_unowned(
    layout, config, monkeypatch
):
    root, _, _, _ = layout
    base = root / f"claude-{os.getuid()}"
    for session in (RUNNING, PARKED, ENDED, STOPPED):
        (base / "-realm-project-x" / session).mkdir(parents=True)
    (base / "session-tmp" / ENDED).mkdir(parents=True)
    (base / "corpus").mkdir()
    (base / "notes.log").write_text("synthetic")
    (base / ".ended").mkdir()
    (base / ".ended" / ENDED).touch()
    (owners.PARKING).mkdir()
    (owners.PARKING / PARKED).touch()
    holder = subprocess.Popen(
        ["sleep", "30"], env={**os.environ, "CLAUDE_CODE_SESSION_ID": RUNNING}
    )
    try:
        rows = rows_by_path(owners.report(config))
    finally:
        holder.kill()
        holder.wait()
    project = base / "-realm-project-x"
    assert rows[str(project / RUNNING)]["state"] == "session is open"
    assert "parked" in rows[str(project / PARKED)]["state"]
    assert "removal pending" in rows[str(project / ENDED)]["state"]
    assert "until resumed" in rows[str(project / STOPPED)]["state"]
    for session in (RUNNING, PARKED, ENDED, STOPPED):
        assert rows[str(project / session)]["owner"] == f"session {session}"
    assert rows[str(base / "corpus")]["owner"] is None
    assert rows[str(base / "notes.log")]["owner"] is None


def test_loose_entries_are_owned_only_by_a_holder_or_the_devshell_sweeper(
    layout, config
):
    root, _, _, _ = layout
    (root / "nix-shell.abc").mkdir()
    (root / "named-by-an-agent").mkdir()
    held = root / "in-use"
    held.mkdir()
    holder = subprocess.Popen(["sleep", "30"], cwd=held)
    try:
        listing = owners.report(config, unowned_only=True)
    finally:
        holder.kill()
        holder.wait()
    unowned = rows_by_path(listing)
    assert str(root / "named-by-an-agent") in unowned
    assert str(root / "nix-shell.abc") not in unowned
    assert str(held) not in unowned
    assert listing["unowned"] == len(unowned)


def test_worktrees_and_compiler_targets_need_a_registration(layout, config, tmp_path):
    _, worktrees, cache, _ = layout
    repository = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-q", "--allow-empty", "-m", "base"],
        check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"},
    )
    registered = worktrees / "registered"
    subprocess.run(
        ["git", "-C", str(repository), "worktree", "add", "-q", "--detach", str(registered)],
        check=True,
    )
    (worktrees / "leftover").mkdir()
    for checkout in (registered, worktrees / "removed"):
        entry = cache / str(os.getuid()) / hashlib.sha256(str(checkout).encode()).hexdigest()[:32]
        (entry / "target").mkdir(parents=True)
        (entry / "checkout").write_text(f"{checkout}\n")
    rows = rows_by_path(owners.report(config))
    assert rows[str(registered)]["owner"] == f"worktree of {repository}"
    assert rows[str(worktrees / "leftover")]["owner"] is None
    targets = {
        row["state"].split(";")[0]: row["owner"]
        for row in owners.report(config)["sections"]["compiler_targets"]
    }
    assert targets["compiler target of an existing checkout"] == f"checkout {registered}"
    assert targets[f"checkout {worktrees / 'removed'} is gone"] is None
