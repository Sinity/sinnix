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
    cancelled = tmp_path / "cancelled.log"
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
        f"    print(json.dumps({{'job_id': 'baseline-' + str(len(open({str(started)!r}).readlines()))}}))\n"
        "elif args[:2] == ['job', 'cancel']:\n"
        f"    with open({str(cancelled)!r}, 'a') as output:\n"
        "        output.write(args[args.index('--job-id') + 1] + '\\n')\n"
        "    print('{}')\n"
        "elif args[:2] == ['job', 'get']:\n"
        "    phase = os.environ.get('BASELINE_JOB_PHASE', 'succeeded')\n"
        "    if phase == 'lookup-fails':\n"
        "        sys.exit(1)\n"
        "    print(json.dumps({'job_id': args[args.index('--job-id') + 1], 'phase': phase}))\n"
        "else:\n"
        "    sys.exit(9)\n"
    )
    agentctl.chmod(0o755)
    env = dict(os.environ, AGENTCTL=str(agentctl))
    return {
        "root": root,
        "checkout": workspaces / "fixture-master",
        "started": started,
        "cancelled": cancelled,
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
            "--json",
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

    world["active"].write_text(
        json.dumps(
            [{"label": "fixture:baseline", "job_id": "baseline-1", "phase": "running"}]
        )
    )
    baseline(world)
    assert git("rev-parse", "HEAD", cwd=world["checkout"]) == first
    assert len(started(world)) == 1
    assert not world["cancelled"].exists()

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
    assert stamp.read_text().split() == [
        git("rev-parse", "HEAD", cwd=world["checkout"]),
        "baseline-1",
    ]
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


@pytest.mark.parametrize(
    ("phase", "queued_again"),
    [
        ("succeeded", False),
        ("failed", False),
        ("timeout", False),
        ("running", False),
        ("refused", False),
        ("launch-failed", False),
        ("cancelled", False),
        ("vanished", True),
        ("unknown", True),
        ("lookup-fails", True),
    ],
)
def test_a_head_whose_baseline_was_lost_is_queued_again(
    world: dict, phase: str, queued_again: bool
) -> None:
    baseline(world)
    world["env"]["BASELINE_JOB_PHASE"] = phase
    baseline(world)
    runs = started(world)
    assert len(runs) == (2 if queued_again else 1)
    # The descriptor's priority places every baseline; a requeue keeps it.
    assert all("--priority" not in run for run in runs)


def test_a_stamp_without_a_job_is_queued_again(world: dict) -> None:
    baseline(world)
    stamp = Path(
        git(
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "baseline-head",
            cwd=world["checkout"],
        )
    )
    stamp.write_text(stamp.read_text().split()[0] + "\n")
    baseline(world)
    assert len(started(world)) == 2


def advance(tmp_path: Path) -> str:
    other = tmp_path / "advance"
    if not other.exists():
        subprocess.run(
            ["git", "clone", "-q", str(tmp_path / "origin.git"), str(other)], check=True
        )
    git("pull", "-q", "origin", "master", cwd=other)
    git("commit", "-q", "--allow-empty", "-m", "next", cwd=other)
    git("push", "-q", "origin", "HEAD:master", cwd=other)
    return git("rev-parse", "HEAD", cwd=other)


def test_a_queued_baseline_for_an_older_head_is_replaced(
    world: dict, tmp_path: Path
) -> None:
    baseline(world)
    queued = [{"label": "fixture:baseline", "job_id": "baseline-1", "phase": "queued"}]
    world["active"].write_text(json.dumps(queued))

    # Still the newest head: the queued job stands and nothing is added.
    baseline(world)
    assert len(started(world)) == 1
    assert not world["cancelled"].exists()

    head = advance(tmp_path)
    baseline(world)
    assert world["cancelled"].read_text().split() == ["baseline-1"]
    assert len(started(world)) == 2
    assert git("rev-parse", "HEAD", cwd=world["checkout"]) == head
