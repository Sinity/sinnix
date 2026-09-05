"""Typed terminal actions over a faked kitty control plane."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sinnix_agent_gateway.actions import terminals as terminal_actions
from sinnix_agent_gateway.app import create_server
from sinnix_agent_gateway.config import GatewayConfig
from test_actions import call, structured
from test_actions_desktop import commands, register

LISTING = [
    {
        "id": 1,
        "is_focused": True,
        "tabs": [
            {
                "id": 2,
                "is_active": True,
                "title": "tab",
                "windows": [
                    {
                        "id": 7,
                        "title": "Codex session",
                        "cwd": "/realm/project/sinnix",
                        "pid": 100,
                        "is_active": True,
                        "is_focused": True,
                        "at_prompt": True,
                        "cmdline": ["zsh"],
                        "foreground_processes": [
                            {
                                "pid": 100,
                                "cmdline": ["zsh"],
                                "cwd": "/realm/project/sinnix",
                            }
                        ],
                        "columns": 80,
                    },
                    {
                        "id": 9,
                        "title": "build",
                        "cwd": "/realm/project/sinnix",
                        "pid": 101,
                        "is_active": False,
                        "is_focused": False,
                        "at_prompt": False,
                        "cmdline": ["zsh"],
                        "foreground_processes": [
                            {"pid": 101, "cmdline": ["zsh"]},
                            {"pid": 555, "cmdline": ["make"]},
                        ],
                    },
                ],
            },
        ],
    },
    {
        "id": 3,
        "is_focused": False,
        "tabs": [
            {
                "id": 4,
                "is_active": True,
                "windows": [
                    {
                        "id": 11,
                        "title": "new",
                        "cwd": "/tmp",
                        "pid": 300,
                        "is_active": True,
                        "is_focused": False,
                        "at_prompt": True,
                    },
                ],
            }
        ],
    },
]


def fake_terminals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, principal: str = "operator"
):
    captured = tmp_path / "commands.jsonl"
    runner = tmp_path / "kitty-control"
    runner.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        f"LISTING = json.loads({json.dumps(LISTING)!r})\n"
        f"with pathlib.Path({str(captured)!r}).open('a') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "verb = sys.argv[1]\n"
        "if verb == 'list':\n"
        "    print(json.dumps(LISTING))\n"
        "elif verb == 'capture':\n"
        "    extent = sys.argv[sys.argv.index('--extent') + 1]\n"
        "    if extent == 'last_cmd_output':\n"
        "        print('hello\\n__SINNIX_RC:3__')\n"
        "    else:\n"
        "        print('\\n'.join(f'line {i} of {extent}' for i in range(1, 6)))\n"
        "elif verb == 'await':\n"
        "    print('build done')\n"
        "elif verb == 'launch':\n"
        "    print(json.dumps({'id': 11, 'cwd': '/tmp', 'title': ''}))\n"
        "else:\n"
        "    print('')\n"
    )
    runner.chmod(0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        kitty_control_command=str(runner),
        approved_manifest_hash="approved-fixture-hash",
    )
    server = create_server(config, principal)
    register(server, terminal_actions.ACTIONS)
    return server, captured


def test_list_and_get_resolve_natural_locators(tmp_path, monkeypatch) -> None:
    server, captured = fake_terminals(tmp_path, monkeypatch)
    listing = structured(call(server, "terminals.list", {}))["data"]
    assert [t["kitty_id"] for t in listing["terminals"]] == [7, 9, 11]
    assert listing["focused_ref"] == "sinnix://terminals/7"
    first = listing["terminals"][0]
    assert (
        first["ref"] == "sinnix://terminals/7"
        and first["os_window_id"] == 1
        and first["tab_id"] == 2
    )
    assert first["extra"] == {"columns": 80}
    assert commands(captured) == [["list", "--json"]]

    focused = structured(call(server, "terminals.get", {"target": {"focused": True}}))[
        "data"
    ]
    assert focused["kitty_id"] == 7 and focused["at_prompt"] is True
    by_pid = structured(call(server, "terminals.get", {"target": {"pid": 101}}))["data"]
    assert by_pid["ref"] == "sinnix://terminals/9"
    by_ref = structured(
        call(server, "terminals.get", {"target": {"ref": "sinnix://terminals/11"}})
    )["data"]
    assert by_ref["cwd"] == "/tmp"
    ambiguous = structured(
        call(server, "terminals.get", {"target": {"cwd": "/realm/project/sinnix/"}})
    )
    assert ambiguous["error"]["code"] == "conflict"
    assert [c["ref"] for c in ambiguous["error"]["details"]["candidates"]] == [
        "sinnix://terminals/7",
        "sinnix://terminals/9",
    ]
    assert (
        structured(call(server, "terminals.get", {"target": {"kitty_id": 42}}))[
            "error"
        ]["code"]
        == "not_found"
    )


def test_screen_scrollback_and_processes(tmp_path, monkeypatch) -> None:
    server, captured = fake_terminals(tmp_path, monkeypatch)
    screen = structured(
        call(server, "terminals.screen", {"target": {"title_contains": "codex"}})
    )["data"]
    assert screen["extent"] == "screen" and screen["lines"] == 5
    assert ["capture", "--match", "id:7", "--extent", "screen"] in commands(captured)

    tail = structured(
        call(server, "terminals.scrollback", {"target": {"kitty_id": 7}, "lines": 2})
    )["data"]
    assert tail["text"] == "line 4 of all\nline 5 of all"
    assert tail["total_lines"] == 5 and tail["truncated"] is True
    assert ["capture", "--match", "id:7", "--extent", "all"] in commands(captured)

    processes = structured(
        call(server, "terminals.processes", {"target": {"kitty_id": 9}})
    )["data"]
    assert processes["at_prompt"] is False
    assert [p["pid"] for p in processes["processes"]] == [101, 555]


def test_send_run_and_wait(tmp_path, monkeypatch) -> None:
    server, captured = fake_terminals(tmp_path, monkeypatch)
    sent = structured(
        call(
            server,
            "terminals.send",
            {
                "target": {"kitty_id": 7},
                "input": {"kind": "text", "text": "status", "enter": True},
                "idempotency_key": "s1",
            },
        )
    )
    assert sent["result"]["outcome"] == "ok", sent
    assert sent["data"]["terminal"]["kitty_id"] == 7
    assert ["send", "--match", "id:7", "--text", "status", "--enter"] in commands(
        captured
    )
    keys = structured(
        call(
            server,
            "terminals.send",
            {
                "target": {"kitty_id": 7},
                "input": {"kind": "keys", "keys": ["ctrl+c"]},
                "idempotency_key": "s2",
            },
        )
    )
    assert keys["data"]["sent"] == ["ctrl+c"]
    assert ["key", "--match", "id:7", "--keys", "ctrl+c"] in commands(captured)

    ran = structured(
        call(
            server,
            "terminals.run",
            {
                "target": {"kitty_id": 7},
                "command": ["git", "status", "--short"],
                "capture_exit_status": True,
                "idempotency_key": "r1",
            },
        )
    )
    assert ran["result"]["outcome"] == "ok", ran
    data = ran["data"]
    assert data["command"] == "git status --short" and data["completed"] is True
    assert data["exit_status"] == 3 and data["output"] == "hello"
    assert data["cwd"] == "/realm/project/sinnix" and data["duration_seconds"] >= 0
    run_vector = [c for c in commands(captured) if c[0] == "run"][0]
    assert run_vector[:3] == ["run", "--match", "id:7"] and run_vector[-1].startswith(
        "git status --short; printf"
    )

    busy = structured(
        call(
            server,
            "terminals.run",
            {
                "target": {"kitty_id": 9},
                "command": "sleep 1",
                "timeout_seconds": 1,
                "idempotency_key": "r2",
            },
        )
    )
    assert busy["data"]["completed"] is False and busy["data"]["exit_status"] is None

    waited = structured(
        call(
            server,
            "terminals.wait",
            {
                "target": {"kitty_id": 9},
                "condition": {"kind": "regex", "pattern": "done"},
                "timeout_seconds": 5,
            },
        )
    )
    assert (
        waited["data"]["satisfied"] is True
        and waited["data"]["matched_text"] == "build done"
    )
    assert [
        "await",
        "--match",
        "id:9",
        "--pattern",
        "done",
        "--timeout-sec",
        "5",
        "--extent",
        "all",
    ] in commands(captured)
    prompt = structured(
        call(
            server,
            "terminals.wait",
            {"target": {"kitty_id": 7}, "condition": {"kind": "prompt"}},
        )
    )["data"]
    assert prompt["satisfied"] is True
    title = structured(
        call(
            server,
            "terminals.wait",
            {
                "target": {"kitty_id": 9},
                "condition": {"kind": "title", "contains": "BUILD"},
            },
        )
    )["data"]
    assert title["satisfied"] is True and title["matched_text"] == "build"
    exited = structured(
        call(
            server,
            "terminals.wait",
            {
                "target": {"kitty_id": 9},
                "condition": {"kind": "process_exit", "pid": 555},
                "timeout_seconds": 1,
            },
        )
    )["data"]
    assert exited["satisfied"] is False and exited["waited_seconds"] >= 1


def test_focus_and_open(tmp_path, monkeypatch) -> None:
    server, captured = fake_terminals(tmp_path, monkeypatch)
    focused = structured(
        call(
            server,
            "terminals.focus",
            {"target": {"title_contains": "build"}, "idempotency_key": "f1"},
        )
    )
    assert focused["data"]["ref"] == "sinnix://terminals/9"
    assert ["focus", "--match", "id:9"] in commands(captured)

    opened = structured(
        call(
            server,
            "terminals.open",
            {
                "cwd": "/tmp",
                "command": ["htop"],
                "placement": "tab",
                "title": "top",
                "idempotency_key": "o1",
            },
        )
    )
    assert opened["result"]["outcome"] == "ok", opened
    assert opened["data"]["ref"] == "sinnix://terminals/11"
    assert opened["data"]["terminal"]["title"] == "new"
    assert [
        "launch",
        "--type",
        "tab",
        "--cwd",
        "/tmp",
        "--title",
        "top",
        "--command",
        "htop",
    ] in commands(captured)


def test_observer_reads_but_cannot_mutate(tmp_path, monkeypatch) -> None:
    server, _ = fake_terminals(tmp_path, monkeypatch, "observer")
    assert (
        structured(call(server, "terminals.list", {}))["data"]["focused_ref"]
        == "sinnix://terminals/7"
    )
    tools = server._tool_manager._tools
    assert {
        "terminals.send",
        "terminals.run",
        "terminals.focus",
        "terminals.open",
    }.isdisjoint(tools)
    assert "terminals.wait" in tools
