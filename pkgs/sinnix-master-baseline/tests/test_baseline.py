"""sinnix-master-baseline against a synthetic remote and a stand-in agentctl."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/sinnix-master-baseline"
GIT = ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid"]


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        [*GIT, *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def world(tmp_path: Path) -> dict:
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "master", str(origin)], check=True
    )
    root = tmp_path / "repo"
    subprocess.run(["git", "clone", "-q", str(origin), str(root)], check=True)
    git("commit", "-q", "--allow-empty", "-m", "first", cwd=root)
    git("push", "-q", "origin", "HEAD:master", cwd=root)
    workspaces = tmp_path / "worktrees"
    workspaces.mkdir()
    started = tmp_path / "started.log"
    active = tmp_path / "active.json"
    active.write_text("[]")
    agentctl = tmp_path / "agentctl"
    agentctl.write_text(
        f"#!{shutil.which('bash')}\nset -eu\n"
        f'case "$1 $2" in\n'
        f"  'project get') printf '%s' '{json.dumps({'root': str(root), 'workspace': {'root': str(workspaces), 'default_base': 'origin/master'}, 'operations': [{'name': 'baseline'}]})}' ;;\n"
        f"  'job list') cat '{active}' ;;\n"
        f"  'job start') printf '%s\\n' \"$*\" >>'{started}' ;;\n"
        "  *) exit 9 ;;\n"
        "esac\n"
    )
    agentctl.chmod(0o755)
    env = dict(os.environ, AGENTCTL=str(agentctl))
    return {
        "root": root,
        "checkout": workspaces / "fixture-master",
        "started": started,
        "active": active,
        "env": env,
    }


def baseline(world: dict) -> None:
    subprocess.run(["bash", str(SCRIPT), "fixture"], env=world["env"], check=True)


def started(world: dict) -> list[str]:
    path = world["started"]
    return path.read_text().splitlines() if path.exists() else []


def test_a_new_head_is_queued_once_in_the_reserved_checkout(world: dict) -> None:
    baseline(world)
    checkout = world["checkout"]
    head = git("rev-parse", "origin/master", cwd=world["root"])
    assert git("rev-parse", "HEAD", cwd=checkout) == head
    assert started(world) == [f"job start fixture baseline --workspace {checkout}"]
    assert git("config", "--get", "sinnix.baselineCheckout", cwd=world["root"]) == str(
        checkout
    )
    # Worktree cleanup keeps a locked checkout.
    assert "locked" in git("worktree", "list", "--porcelain", cwd=world["root"])

    baseline(world)
    assert len(started(world)) == 1


def test_the_checkout_follows_master_but_never_moves_under_an_active_baseline(
    world: dict, tmp_path: Path
) -> None:
    baseline(world)
    first = git("rev-parse", "HEAD", cwd=world["checkout"])
    other = tmp_path / "other"
    subprocess.run(
        ["git", "clone", "-q", str(tmp_path / "origin.git"), str(other)], check=True
    )
    git("commit", "-q", "--allow-empty", "-m", "second", cwd=other)
    git("push", "-q", "origin", "HEAD:master", cwd=other)

    world["active"].write_text(json.dumps([{"label": "fixture:baseline"}]))
    baseline(world)
    assert git("rev-parse", "HEAD", cwd=world["checkout"]) == first
    assert len(started(world)) == 1

    world["active"].write_text(json.dumps([{"label": "fixture:check"}]))
    baseline(world)
    assert git("rev-parse", "HEAD", cwd=world["checkout"]) == git(
        "rev-parse", "HEAD", cwd=other
    )
    assert len(started(world)) == 2


def test_a_project_without_a_baseline_operation_is_left_alone(world: dict) -> None:
    agentctl = Path(world["env"]["AGENTCTL"])
    agentctl.write_text(agentctl.read_text().replace('"baseline"', '"check"'))
    baseline(world)
    assert started(world) == []
    assert not world["checkout"].exists()
