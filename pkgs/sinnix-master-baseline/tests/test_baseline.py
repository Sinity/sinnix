"""sinnix-master-baseline against a synthetic remote and a stand-in agentctl."""

import json
import os
import subprocess
import sys
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
    descriptor = {
        "id": "fixture",
        "root": str(root),
        "workspace": {"root": str(workspaces), "default_base": "origin/master"},
        "operations": [{"name": "baseline"}],
    }
    agentctl.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        f"descriptor = json.loads({json.dumps(descriptor)!r})\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['project', 'get']:\n"
        "    if args[2] != 'fixture':\n"
        "        descriptor['id'] = os.environ.get('BASELINE_CHECKOUT_ID', 'fixture')\n"
        "    print(json.dumps(descriptor))\n"
        "elif args[:2] == ['job', 'list']:\n"
        f"    print(open({str(active)!r}).read())\n"
        "elif args[:2] == ['job', 'start']:\n"
        "    if failure := int(os.environ.get('BASELINE_START_FAIL', '0')):\n"
        "        sys.exit(failure)\n"
        f"    with open({str(started)!r}, 'a') as output:\n"
        "        output.write(json.dumps(args) + '\\n')\n"
        "else:\n"
        "    sys.exit(9)\n"
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


def baseline(world: dict, *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), "fixture"],
        env=world["env"],
        check=check,
        capture_output=True,
        text=True,
    )


def started(world: dict) -> list[list[str]]:
    path = world["started"]
    return (
        [json.loads(line) for line in path.read_text().splitlines()]
        if path.exists()
        else []
    )


def test_a_new_head_is_queued_once_in_the_reserved_checkout(world: dict) -> None:
    baseline(world)
    checkout = world["checkout"]
    head = git("rev-parse", "origin/master", cwd=world["root"])
    assert git("rev-parse", "HEAD", cwd=checkout) == head
    assert started(world) == [
        [
            "job",
            "start",
            "--project",
            str(checkout),
            "baseline",
            "--workspace",
            str(checkout),
        ]
    ]
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
    agentctl.write_text(agentctl.read_text().replace("baseline", "check"))
    baseline(world)
    assert started(world) == []
    assert not world["checkout"].exists()


def test_a_refused_launch_does_not_stamp_the_head_or_suppress_the_next_attempt(
    world: dict,
) -> None:
    world["env"]["BASELINE_START_FAIL"] = "37"
    assert baseline(world, check=False).returncode == 37
    stamp = Path(
        git(
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "baseline-head",
            cwd=world["checkout"],
        )
    )
    assert not stamp.exists()
    assert started(world) == []
    del world["env"]["BASELINE_START_FAIL"]
    baseline(world)
    assert stamp.read_text().strip() == git("rev-parse", "HEAD", cwd=world["checkout"])
    baseline(world)
    assert len(started(world)) == 1


def test_a_checkout_cannot_queue_a_different_project_identity(world: dict) -> None:
    world["env"]["BASELINE_CHECKOUT_ID"] = "other-project"
    result = baseline(world, check=False)
    assert result.returncode == 1
    assert "different project ID" in result.stderr
    assert started(world) == []
    stamp = Path(
        git(
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "baseline-head",
            cwd=world["checkout"],
        )
    )
    assert not stamp.exists()
