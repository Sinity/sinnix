import importlib.machinery
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[3] / "scripts"
LOADER = importlib.machinery.SourceFileLoader(
    "desktop_session", str(SCRIPTS / "sinnix-desktop-session")
)
session = importlib.util.module_from_spec(
    importlib.util.spec_from_loader(LOADER.name, LOADER)
)
LOADER.exec_module(session)
BOOT = "a" * 32
PREVIOUS = "b" * 32
CLAUDE = "11111111-1111-4111-8111-111111111111"
CODEX = "22222222-2222-4222-8222-222222222222"
STARTED_AT = "2026-01-05T00:01:00+00:00"


def process(proc, pid, parent, group, leader, tty, foreground, cwd, argv=None):
    entry = proc / str(pid)
    entry.mkdir(parents=True)
    fields = ["S", str(parent), str(group), str(leader), str(tty), str(foreground)] + [
        "0"
    ] * 14
    (entry / "stat").write_text(f"{pid} (synthetic) " + " ".join(fields))
    (entry / "cwd").symlink_to(cwd)
    if argv:
        (entry / "cmdline").write_bytes(
            b"\0".join(word.encode() for word in argv) + b"\0"
        )
    return entry


def pane(pid, title):
    return {"pid": pid, "title": title, "cwd": "/fixture/original", "is_active": True}


@pytest.fixture
def desktop(tmp_path, monkeypatch):
    proc = tmp_path / "proc"
    for root, cwd, agent in [
        (30, "/fixture/one", 33),
        (40, "/fixture/two", 43),
        (50, "/fixture/plain", 0),
    ]:
        process(proc, root, 100, root, root, 10, root, "/fixture/original")
        process(
            proc,
            root + 1,
            root,
            root,
            root,
            10,
            root,
            "/fixture/original",
            ["asciinema"],
        )
        process(
            proc,
            root + 2,
            root + 1,
            root + 2,
            root + 2,
            11,
            agent or root + 2,
            cwd,
            ["zsh"],
        )
        if agent:
            entry = process(
                proc,
                agent,
                root + 2,
                agent,
                root + 2,
                11,
                agent,
                cwd,
                ["codex" if agent == 43 else "claude"],
            )
            if agent == 43:
                (entry / "fd").mkdir()
                (entry / "fd/3").symlink_to(
                    f"/fixture/rollout-2026-01-05T00-00-00-{CODEX}.jsonl"
                )
    registry = tmp_path / "claude/sessions"
    registry.mkdir(parents=True)
    (registry / "33.json").write_text(
        json.dumps(
            {
                "pid": 33,
                "sessionId": CLAUDE,
                "cwd": "/fixture/one",
                "kind": "interactive",
                "procStart": "0",
            }
        )
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(registry.parent))
    windows = [
        {
            "wm_class": "kitty",
            "tabs": [
                {
                    "is_active": True,
                    "title": "Tools $HOME",
                    "windows": [pane(pid, title)],
                }
            ],
        }
        for pid, title in ((30, "Claude"), (40, "Codex"), (50, "Plain"))
    ]
    clients = [
        {
            "pid": 100,
            "class": "kitty",
            "title": title,
            "workspace": {"id": workspace},
            "at": [1, 2],
            "size": [3, 4],
        }
        for title, workspace in (("Plain", 3), ("Claude", 3), ("Codex", 7))
    ]
    clients.append({"pid": 200, "class": "google-chrome"})
    monkeypatch.setattr(session, "kitty_inventory", lambda _: [(100, windows)])
    monkeypatch.setattr(session, "previous_boot", lambda: PREVIOUS)
    return proc, clients


def test_snapshot_restore_native_session_grammar(tmp_path, monkeypatch, desktop):
    proc, clients = desktop
    root, runtime = tmp_path / "state", tmp_path / "run"
    runtime.mkdir()
    commands = []
    active = [
        {
            "task_id": n,
            "job_id": f"fixture-{n}",
            "phase": phase,
            "started_at": STARTED_AT,
        }
        for n, phase in (
            (10, "running"),
            (11, "running"),
            (12, "queued"),
            (13, "running"),
        )
    ]

    def call(*argv):
        commands.append(argv)
        if argv == ("hyprctl", "-j", "clients"):
            return json.dumps(clients)
        if argv[:3] == ("agentctl", "job", "list"):
            return json.dumps(active)
        if argv[:3] == ("agentctl", "job", "get"):
            if argv[3] == "13":
                return json.dumps({"phase": "succeeded"})
            return json.dumps(
                {
                    "phase": "cancelled",
                    "queue_present": True,
                    "started_at": STARTED_AT,
                    "result": "Killed",
                }
            )
        if argv[:4] == ("agentctl", "job", "retry", "11"):
            raise RuntimeError("the launch did not declare retry_after_reboot")
        return "ok"

    monkeypatch.setattr(session, "call", call)
    session.snapshot(root, PREVIOUS, proc, runtime)
    snapshot = session.read_snapshot(root, PREVIOUS)
    assert [w["workspace"] for w in snapshot["kitty"]] == [3, 7, 3]
    assert snapshot["kitty"][0]["geometry"] == {"at": [1, 2], "size": [3, 4]}
    assert snapshot["chrome"]
    assert len(snapshot["jobs"]) == 4
    assert (next(root.glob("snapshot-*.json")).stat().st_mode & 0o777) == 0o600
    assert (root.stat().st_mode & 0o777) == 0o700
    # A current-boot snapshot must not win over the previous boot's data.
    session.put_json(
        root / f"snapshot-9999999999999999999-{BOOT}.json",
        {**snapshot, "boot_id": BOOT, "kitty": [], "chrome": False},
    )
    session.restore(root, BOOT, runtime, "/fixture/desktop-session")
    launches = [
        argv[3] for argv in commands if argv[:3] == ("hyprctl", "dispatch", "exec")
    ]
    assert [command.split("]")[0] for command in launches] == [
        "[workspace 3 silent",
        "[workspace 7 silent",
        "[workspace 3 silent",
    ]
    # Ask the actual Kitty parser for its parsed program arguments, not just
    # whether the file happens to contain an ID or a directory.
    parse = """
from pathlib import Path
from kitty.config import defaults
from kitty.session import parse_session
import json, sys
saved = list(parse_session(Path(sys.argv[-1]).read_text(), defaults))
print(json.dumps([[tab.name, [pane.launch_spec.args for pane in tab.windows]]
                  for window in saved for tab in window.tabs]))
"""
    expected = [
        ["/fixture/desktop-session", "terminal", "/fixture/one", "claude", CLAUDE],
        ["/fixture/desktop-session", "terminal", "/fixture/two", "codex", CODEX],
        ["/fixture/desktop-session", "terminal", "/fixture/plain"],
    ]
    for launch, want in zip(launches, expected, strict=True):
        name = shlex.split(launch)[-1]
        result = subprocess.run(
            ["kitty", "+runpy", parse, name], capture_output=True, check=True, text=True
        )
        assert json.loads(result.stdout) == [["Tools $HOME", [want]]]
    assert ("sinnix-chrome",) in commands
    assert [
        argv[3] for argv in commands if argv[:3] == ("agentctl", "job", "retry")
    ] == ["10", "11"]
    notice = next(argv[-1] for argv in commands if argv[0] == "notify-send")
    assert "fixture-10" in notice and "fixture-11" in notice
    receipt = session.get_json(root / "restore.json")
    assert [job["status"] for job in receipt["jobs"]] == ["retried", "reported"]
    before = list(commands)
    session.restore(root, BOOT, runtime, "/fixture/desktop-session")
    assert commands == before


def test_no_snapshot_from_previous_boot(tmp_path, monkeypatch):
    def unexpected(*argv):
        raise AssertionError(argv)

    monkeypatch.setattr(session, "call", unexpected)
    monkeypatch.setattr(session, "previous_boot", lambda: PREVIOUS)
    session.put_json(
        tmp_path / f"snapshot-1-{'c' * 32}.json", {"boot_id": "c" * 32, "kitty": []}
    )
    session.restore(tmp_path, BOOT, tmp_path, "/fixture/session")
    assert (
        session.get_json(tmp_path / "restore.json")["status"]
        == "no-previous-boot-snapshot"
    )


def test_snapshot_requires_active_graphical_target(tmp_path, monkeypatch):
    def inactive(*argv):
        assert argv == ("systemctl", "--user", "is-active", "graphical-session.target")
        raise RuntimeError("inactive")

    monkeypatch.setattr(session, "call", inactive)
    root = tmp_path / "state"
    with pytest.raises(RuntimeError, match="inactive"):
        session.snapshot(root, BOOT, tmp_path, tmp_path)
    assert not root.exists()


@pytest.mark.parametrize("status", [0, 1])
def test_reboot_requires_successful_snapshot(tmp_path, status):
    shell = Path(shutil.which("bash"))
    stub = tmp_path / "systemctl"
    stub.write_text(
        f'#!{shell}\nprintf \'%s\\n\' "$*" >> "$COMMANDS"\n'
        f"if [[ $1 == --user ]]; then exit {status}; fi\n"
    )
    stub.chmod(0o755)
    commands = tmp_path / "commands"
    proc = subprocess.run(
        [shell, str(SCRIPTS / "sinnix-reboot")],
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "COMMANDS": str(commands),
        },
    )
    assert proc.returncode == status
    expected = ["--user start sinnix-desktop-snapshot.service"]
    assert commands.read_text().splitlines() == (
        expected if status else [*expected, "reboot"]
    )


@pytest.mark.parametrize(
    ("harness", "ident", "resume"),
    [
        ("claude", CLAUDE, f'claude --resume {CLAUDE}; exec "$SHELL"'),
        ("codex", CODEX, f'codex resume {CODEX}; exec "$SHELL"'),
    ],
)
def test_terminal_resumes_inside_the_captured_shell(
    tmp_path, monkeypatch, harness, ident, resume
):
    commands = []
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        session.os, "execv", lambda exe, argv: commands.append((exe, argv))
    )
    cwd = tmp_path / "repository with spaces"
    cwd.mkdir()
    shell = str(tmp_path / ".local/bin/sinnix-captured-shell")
    with monkeypatch.context() as directory:
        directory.chdir(cwd.parent)
        session.reopen_terminal(cwd, harness, ident)
        assert Path.cwd() == cwd
        assert commands == [(shell, [shell, "-ic", resume])]
        session.reopen_terminal(tmp_path / "gone", harness, ident)
        assert Path.cwd() == tmp_path
        assert commands[-1] == (shell, [shell])
