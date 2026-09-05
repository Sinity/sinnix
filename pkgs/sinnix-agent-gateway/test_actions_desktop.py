"""Typed desktop actions over a faked Hyprland/screenshot control plane."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest
from mcp.types import CallToolResult, ImageContent
from sinnix_agent_gateway.actions import desktop as desktop_actions
from sinnix_agent_gateway.app import create_server
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.tooling import build_tool
from test_actions import call, structured, tiny_png

CLIENTS = [
    {
        "address": "0xa",
        "class": "kitty",
        "title": "Codex session",
        "pid": 100,
        "at": [0, 0],
        "size": [800, 600],
        "workspace": {"id": 1, "name": "1"},
        "monitor": 0,
        "floating": False,
        "fullscreen": 0,
        "mapped": True,
        "hidden": False,
        "initialTitle": "kitty",
        "initialClass": "kitty",
        "focusHistoryID": 0,
        "xwayland": False,
    },
    {
        "address": "0xb",
        "class": "kitty",
        "title": "build",
        "pid": 101,
        "at": [800, 0],
        "size": [800, 600],
        "workspace": {"id": 2, "name": "2"},
        "monitor": 0,
    },
    {
        "address": "0xc",
        "class": "google-chrome",
        "title": "Docs",
        "pid": 200,
        "at": [0, 600],
        "size": [1600, 400],
        "workspace": {"id": 1, "name": "1"},
        "monitor": 0,
    },
]
SNAPSHOT = {
    "generation": "1700000000000000000",
    "monitors": [
        {
            "id": 0,
            "name": "DP-1",
            "width": 3840,
            "height": 2160,
            "x": 0,
            "y": 0,
            "scale": 1.0,
            "refreshRate": 144.0,
            "focused": True,
            "activeWorkspace": {"id": 1, "name": "1"},
            "colorManagementPreset": "hdr",
        }
    ],
    "workspaces": [
        {
            "id": 1,
            "name": "1",
            "monitor": "DP-1",
            "windows": 2,
            "hasfullscreen": False,
            "lastwindow": "0xa",
            "lastwindowtitle": "Codex session",
        }
    ],
    "clients": CLIENTS,
    "active_window": CLIENTS[0],
    "active_workspace": {"id": 1, "name": "1"},
    "cursor": {"x": 10, "y": 20},
}


def register(server, actions) -> None:
    runtime = server._sinnix_revision_publisher.runtime
    principal = runtime.principal.name
    for action in actions:
        if principal in action.principals:
            server._tool_manager._tools[action.name] = build_tool(action, runtime)


def fake_desktop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, principal: str = "operator"
):
    captured = tmp_path / "commands.jsonl"
    runner = tmp_path / "desktop-control"
    png = base64.b64encode(tiny_png()).decode()
    runner.write_text(
        f"#!{sys.executable}\n"
        "import base64, json, pathlib, sys\n"
        f"CLIENTS = json.loads({json.dumps(CLIENTS)!r})\n"
        f"SNAPSHOT = json.loads({json.dumps(SNAPSHOT)!r})\n"
        f"with pathlib.Path({str(captured)!r}).open('a') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "verb = sys.argv[1]\n"
        "if verb in ('capture-output', 'capture-region'):\n"
        "    out = pathlib.Path(sys.argv[sys.argv.index('--out-dir') + 1])\n"
        "    raw = out / 'gateway.grim.png'\n"
        f"    raw.write_bytes(base64.b64decode({png!r}))\n"
        "    corrected = out / 'gateway.grim.sdrfix.png'\n"
        "    corrected.write_bytes(raw.read_bytes())\n"
        "    print(json.dumps({'raw_files': [str(raw)], 'corrected_files': [str(corrected)], 'color_management_preset': 'hdr'}))\n"
        "elif verb == 'snapshot':\n"
        "    print(json.dumps(SNAPSHOT))\n"
        "elif verb == 'clients':\n"
        "    print(json.dumps(CLIENTS))\n"
        "elif verb == 'active-window':\n"
        "    print(json.dumps(CLIENTS[0]))\n"
        "elif verb == 'pointer':\n"
        "    if sys.argv[2] == 'move':\n"
        "        print(json.dumps({'available': True, 'operation': 'move'}))\n"
        "    else:\n"
        "        print(json.dumps({'available': False, 'operation': sys.argv[2], 'reason': 'no virtual pointer tool on this host (ydotool); cursor movement only'}))\n"
        "else:\n"
        "    print('ok')\n"
    )
    runner.chmod(0o700)
    for name, value in {
        "XDG_RUNTIME_DIR": str(tmp_path),
        "WAYLAND_DISPLAY": "wayland-1",
        "HYPRLAND_INSTANCE_SIGNATURE": "fixture",
    }.items():
        monkeypatch.setenv(name, value)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        hypr_control_command=str(runner),
        screenshot_control_command=str(runner),
        approved_manifest_hash="approved-fixture-hash",
    )
    server = create_server(config, principal)
    register(server, desktop_actions.ACTIONS)
    return server, captured


def commands(path: Path) -> list[list[str]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_snapshot_is_one_typed_observation(tmp_path, monkeypatch) -> None:
    server, captured = fake_desktop(tmp_path, monkeypatch)
    payload = structured(call(server, "desktop.snapshot", {}))
    assert payload["result"]["outcome"] == "ok", json.dumps(payload.get("error"))
    data = payload["data"]
    assert data["ref"] == "sinnix://desktop/current"
    assert data["generation"] == SNAPSHOT["generation"]
    assert data["focused_monitor"] == "DP-1" and data["active_workspace"] == "1"
    assert data["active_window"]["ref"] == "sinnix://desktop/windows/0xa"
    assert data["active_window"]["class"] == "kitty"
    assert [w["address"] for w in data["windows"]] == ["0xa", "0xb", "0xc"]
    assert data["windows"][0]["geometry"] == {
        "x": 0,
        "y": 0,
        "width": 800,
        "height": 600,
    }
    assert data["windows"][0]["extra"] == {"xwayland": False}
    assert data["cursor"] == {"x": 10, "y": 20}
    assert data["monitors"][0]["color_management_preset"] == "hdr"
    assert commands(captured) == [["snapshot"]]


def test_screenshot_returns_image_block_and_attested_artifact(
    tmp_path, monkeypatch
) -> None:
    server, captured = fake_desktop(tmp_path, monkeypatch)
    result = call(server, "desktop.screenshot", {})
    assert isinstance(result, CallToolResult) and not result.is_error, result
    images = [b for b in result.content if isinstance(b, ImageContent)]
    assert len(images) == 1 and base64.b64decode(images[0].data) == tiny_png()
    data = structured(result)["data"]
    assert data["artifact"]["representation"] == "image"
    assert data["artifact_ref"].startswith("sinnix://artifacts/")
    assert [v["variant"] for v in data["variants"]] == ["raw", "corrected"]
    assert data["artifact_ref"] == data["variants"][1]["artifact_ref"]
    assert data["receipt"]["target"] == {"kind": "full", "window_ref": None}
    assert commands(captured)[0][0] == "capture-output"


def test_screenshot_of_a_window_uses_its_geometry(tmp_path, monkeypatch) -> None:
    server, captured = fake_desktop(tmp_path, monkeypatch)
    data = structured(
        call(
            server,
            "desktop.screenshot",
            {
                "target": {"kind": "window", "window": {"title_contains": "codex"}},
                "variant": "raw",
            },
        )
    )["data"]
    assert data["window_ref"] == "sinnix://desktop/windows/0xa"
    assert data["geometry"] == {"x": 0, "y": 0, "width": 800, "height": 600}
    assert data["artifact_ref"] == data["variants"][0]["artifact_ref"]
    region = [c for c in commands(captured) if c[0] == "capture-region"][0]
    assert region[region.index("--geometry") + 1] == "0,0 800x600"

    rect = structured(
        call(
            server,
            "desktop.screenshot",
            {"target": {"kind": "rect", "x": 5, "y": 6, "width": 7, "height": 8}},
        )
    )["data"]
    assert rect["receipt"]["target"]["kind"] == "rect"
    monitor = structured(
        call(
            server,
            "desktop.screenshot",
            {"target": {"kind": "monitor", "name": "DP-1"}},
        )
    )["data"]
    assert monitor["geometry"] is None
    assert [c for c in commands(captured) if "--output" in c][0][-3:] == [
        "--output",
        "DP-1",
        "--fix-hdr",
    ]


def test_window_locator_ambiguity_lists_candidates(tmp_path, monkeypatch) -> None:
    server, _ = fake_desktop(tmp_path, monkeypatch)
    result = call(
        server,
        "desktop.screenshot",
        {"target": {"kind": "window", "window": {"class": "kitty"}}},
    )
    error = structured(result)["error"]
    assert error["code"] == "conflict"
    assert [c["ref"] for c in error["details"]["candidates"]] == [
        "sinnix://desktop/windows/0xa",
        "sinnix://desktop/windows/0xb",
    ]
    missing = structured(
        call(
            server,
            "desktop.screenshot",
            {"target": {"kind": "window", "window": {"pid": 999}}},
        )
    )
    assert missing["error"]["code"] == "not_found"
    bad = structured(
        call(server, "desktop.screenshot", {"target": {"kind": "window", "window": {}}})
    )
    assert bad["error"]["code"] == "invalid_request"


def test_operate_reports_active_window_after_each_operation(
    tmp_path, monkeypatch
) -> None:
    server, captured = fake_desktop(tmp_path, monkeypatch)
    focus = structured(
        call(
            server,
            "desktop.operate",
            {
                "action": {"operation": "focus", "window": {"title_contains": "Docs"}},
                "idempotency_key": "f1",
            },
        )
    )
    assert focus["result"]["outcome"] == "ok", focus
    assert focus["data"]["window_ref"] == "sinnix://desktop/windows/0xc"
    assert focus["data"]["active_window"]["address"] == "0xa"
    assert ["focus-window", "address:0xc"] in commands(captured)

    for action, expected in [
        (
            {"operation": "close", "window": {"address": "0xb"}},
            ["window", "address:0xb", "close"],
        ),
        (
            {
                "operation": "move",
                "window": {"ref": "sinnix://desktop/windows/0xb"},
                "x": 5,
                "y": 6,
            },
            ["window", "address:0xb", "move", "5", "6"],
        ),
        (
            {"operation": "resize", "window": {"pid": 101}, "width": 50, "height": 60},
            ["window", "address:0xb", "resize", "50", "60"],
        ),
        (
            {"operation": "type", "window": {"active": True}, "text": "hi"},
            ["type", "address:0xa", "--text", "hi", "--delay-ms", "0"],
        ),
        (
            {
                "operation": "paste",
                "window": {"active": True},
                "text": "hi",
                "enter": True,
            },
            ["paste", "address:0xa", "--text", "hi", "--enter"],
        ),
        (
            {"operation": "key", "mods": "CTRL", "key": "L"},
            ["send-shortcut", "CTRL", "L"],
        ),
        (
            {
                "operation": "key_state",
                "mods": "",
                "key": "a",
                "state": "down",
                "window": {"address": "0xa"},
            },
            ["send-keystate", " ", "a", "down", "address:0xa"],
        ),
        (
            {"operation": "launch", "command": "kitty --class scratch"},
            ["exec", "kitty --class scratch"],
        ),
        (
            {"operation": "open", "uri": "https://example.test"},
            ["open", "https://example.test"],
        ),
        (
            {"operation": "dispatch", "expression": "hl.dsp.focus({ workspace = 3 })"},
            ["dispatch", "hl.dsp.focus({ workspace = 3 })"],
        ),
        ({"operation": "wait_window", "window": {"class": "google-chrome"}}, None),
        ({"operation": "scroll", "x": 1, "y": 2, "dx": 0, "dy": -3}, None),
    ]:
        response = call(
            server,
            "desktop.operate",
            {"action": action, "idempotency_key": f"k-{action['operation']}"},
        )
        payload = structured(response)
        if action["operation"] == "close":
            # the fake never removes the window, so close reports a deadline
            assert payload["error"]["code"] == "deadline"
        elif action["operation"] == "scroll":
            assert payload["error"]["code"] == "unavailable"
            assert "ydotool" in payload["error"]["message"]
        else:
            assert payload["result"]["outcome"] == "ok", payload
            assert (
                payload["data"]["active_window"]["ref"]
                == "sinnix://desktop/windows/0xa"
            )
        if expected is not None:
            assert expected in commands(captured), (action, commands(captured))
    assert ["pointer", "move", "1", "2"] in commands(captured)
    click = structured(
        call(
            server,
            "desktop.operate",
            {"action": {"operation": "click", "x": 3, "y": 4}, "idempotency_key": "c1"},
        )
    )
    assert click["error"]["code"] == "unavailable"


def test_tree_is_unavailable_without_pyatspi(tmp_path, monkeypatch) -> None:
    server, _ = fake_desktop(tmp_path, monkeypatch)
    monkeypatch.setitem(sys.modules, "pyatspi", None)
    payload = structured(call(server, "desktop.tree", {}))
    assert payload["error"]["code"] == "unavailable"
    assert payload["error"]["details"]["window_ref"] == "sinnix://desktop/windows/0xa"


def test_observer_reads_but_cannot_operate(tmp_path, monkeypatch) -> None:
    server, _ = fake_desktop(tmp_path, monkeypatch, "observer")
    assert (
        structured(call(server, "desktop.snapshot", {}))["data"]["active_window"][
            "address"
        ]
        == "0xa"
    )
    assert "desktop.operate" not in server._tool_manager._tools
    assert all(a.principals >= {"operator"} for a in desktop_actions.ACTIONS)
