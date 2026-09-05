"""Typed browser actions over a faked chrome control plane."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest
from mcp.types import CallToolResult, ImageContent
from sinnix_agent_gateway.actions import browser as browser_actions
from sinnix_agent_gateway.app import create_server
from sinnix_agent_gateway.config import GatewayConfig
from test_actions import call, structured, tiny_png
from test_actions_desktop import commands, register

PAGES = [
    {
        "id": "agent-target",
        "title": "Example Domain",
        "url": "https://example.test/",
        "type": "page",
    },
    {
        "id": "operator-page",
        "title": "Operator mail",
        "url": "https://mail.test/inbox",
        "type": "page",
    },
    {
        "id": "worker-1",
        "title": "",
        "url": "chrome-extension://abc/bg.js",
        "type": "service_worker",
    },
]
SNAPSHOT = {
    "generation": 1,
    "url": "https://example.test/",
    "title": "Example Domain",
    "ready_state": "complete",
    "text": "Example Domain\nMore information...",
    "text_truncated": False,
    "elements": [
        {
            "ref": "g1e1",
            "tag": "a",
            "type": None,
            "role": None,
            "name": "",
            "text": "More information...",
            "href": "https://iana.test/",
            "value": None,
            "disabled": False,
            "rect": {"x": 1, "y": 2, "w": 3, "h": 4},
        },
        {
            "ref": "g1e2",
            "tag": "input",
            "type": "text",
            "role": None,
            "name": "q",
            "text": "",
            "href": None,
            "value": "",
            "disabled": False,
            "rect": {"x": 0, "y": 0, "w": 10, "h": 10},
        },
    ],
    "links": [
        {"text": "More information...", "href": "https://iana.test/", "ref": "g1e1"}
    ],
    "forms": [
        {
            "index": 0,
            "id": "search",
            "name": None,
            "action": "https://example.test/s",
            "method": "get",
            "ref": None,
            "fields": [
                {
                    "ref": "g1e2",
                    "tag": "input",
                    "type": "text",
                    "name": "q",
                    "value": "",
                }
            ],
        }
    ],
}


def fake_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, principal: str = "operator"
):
    captured = tmp_path / "commands.jsonl"
    runner = tmp_path / "chrome-control"
    png = base64.b64encode(tiny_png()).decode()
    runner.write_text(
        f"#!{sys.executable}\n"
        "import base64, json, pathlib, sys\n"
        f"PAGES = json.loads({json.dumps(PAGES)!r})\n"
        f"SNAPSHOT = json.loads({json.dumps(SNAPSHOT)!r})\n"
        f"with pathlib.Path({str(captured)!r}).open('a') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "verb = sys.argv[1]\n"
        "if verb == 'list':\n"
        "    print(json.dumps(PAGES))\n"
        "elif verb == 'list-tabs':\n"
        "    print(json.dumps([p for p in PAGES if p['type'] == 'page']))\n"
        "elif verb == 'agent-window':\n"
        "    print(json.dumps({'id': 'agent-target', 'parked': True, 'url': 'https://example.test/'}))\n"
        "elif verb == 'page-snapshot':\n"
        "    print(json.dumps(SNAPSHOT))\n"
        "elif verb == 'screenshot':\n"
        f"    pathlib.Path(sys.argv[sys.argv.index('--out') + 1]).write_bytes(base64.b64decode({png!r}))\n"
        "    print(json.dumps({'ok': True}))\n"
        "elif verb == 'download':\n"
        "    out = pathlib.Path(sys.argv[sys.argv.index('--out') + 1])\n"
        "    out.write_text('report body')\n"
        "    print(json.dumps({'status': 200, 'type': 'text/plain; charset=utf-8', 'bytes': 11, 'id': sys.argv[2], 'out': str(out)}))\n"
        "elif verb in ('click', 'fill-form'):\n"
        "    print('NOT_FOUND' if 'missing' in ' '.join(sys.argv) else 'OK')\n"
        "elif verb == 'evaluate':\n"
        "    print('ok')\n"
        "elif verb == 'await':\n"
        "    print('https://example.test/next')\n"
        "elif verb == 'key':\n"
        "    print(json.dumps({'id': sys.argv[2], 'key': 'Enter', 'modifiers': 0, 'pressed': True}))\n"
        "elif verb == 'upload-files':\n"
        "    print(json.dumps({'id': sys.argv[2], 'selector': sys.argv[4], 'attached': sys.argv.count('--file')}))\n"
        "elif verb == 'close':\n"
        "    print(json.dumps({'id': sys.argv[2], 'closed': True}))\n"
        "else:\n"
        "    print(json.dumps({'ok': True}))\n"
    )
    runner.chmod(0o700)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        chrome_control_command=str(runner),
        approved_manifest_hash="approved-fixture-hash",
    )
    server = create_server(config, principal)
    register(server, browser_actions.ACTIONS)
    return server, captured


def open_agent_page(server) -> dict:
    payload = structured(
        call(
            server,
            "browser.operate",
            {
                "action": {"operation": "new", "url": "https://example.test"},
                "idempotency_key": "new-1",
            },
        )
    )
    assert payload["result"]["outcome"] == "ok", payload
    return payload["data"]


def test_pages_lists_everything_and_flags_owned(tmp_path, monkeypatch) -> None:
    server, captured = fake_browser(tmp_path, monkeypatch)
    before = structured(call(server, "browser.pages", {}))["data"]
    assert [p["page_id"] for p in before["pages"]] == ["agent-target", "operator-page"]
    assert before["owned_refs"] == [] and before["pages"][0]["affordances"] == []
    assert commands(captured) == [["list-tabs", "--json"]]

    created = open_agent_page(server)
    assert created["ref"] == "sinnix://browser/pages/agent-target"
    assert created["page"]["owned"] is True
    assert ["agent-window", "--url", "https://example.test"] in commands(captured)

    after = structured(call(server, "browser.pages", {"include": "all_targets"}))[
        "data"
    ]
    assert after["owned_refs"] == ["sinnix://browser/pages/agent-target"]
    assert [p["type"] for p in after["pages"]] == ["page", "page", "service_worker"]
    assert "browser.operate" in after["pages"][0]["affordances"]


def test_page_snapshot_only_for_owned_pages(tmp_path, monkeypatch) -> None:
    server, captured = fake_browser(tmp_path, monkeypatch)
    denied = structured(
        call(server, "browser.page", {"target": {"url_contains": "mail.test"}})
    )
    assert denied["error"]["code"] == "policy_denied"
    assert not any(c[0] == "page-snapshot" for c in commands(captured))
    assert (
        structured(
            call(server, "browser.page", {"target": {"title_contains": "nowhere"}})
        )["error"]["code"]
        == "not_found"
    )

    open_agent_page(server)
    page = structured(
        call(
            server,
            "browser.page",
            {"target": {"title_contains": "example"}, "max_text": 100},
        )
    )["data"]
    assert (
        page["ref"] == "sinnix://browser/pages/agent-target" and page["generation"] == 1
    )
    assert [e["ref"] for e in page["elements"]] == ["g1e1", "g1e2"]
    assert page["forms"][0]["fields"][0]["name"] == "q"
    assert [
        "page-snapshot",
        "agent-target",
        "--max-text",
        "100",
        "--max-elements",
        "300",
    ] in commands(captured)


def test_operate_by_element_ref_and_selector(tmp_path, monkeypatch) -> None:
    server, captured = fake_browser(tmp_path, monkeypatch)
    open_agent_page(server)
    target = {"target": {"ref": "sinnix://browser/pages/agent-target"}}

    clicked = structured(
        call(
            server,
            "browser.operate",
            {
                **target,
                "action": {"operation": "click", "element": {"ref": "g1e1"}},
                "idempotency_key": "c1",
            },
        )
    )
    assert clicked["result"]["outcome"] == "ok", clicked
    assert clicked["data"]["page"]["url"] == "https://example.test/"
    assert [
        "click",
        "agent-target",
        "--selector",
        '[data-sinnix-ref="g1e1"]',
    ] in commands(captured)

    filled = structured(
        call(
            server,
            "browser.operate",
            {
                **target,
                "action": {
                    "operation": "fill",
                    "element": {"selector": "#q"},
                    "value": "sinnix",
                },
                "idempotency_key": "f1",
            },
        )
    )
    assert filled["data"]["result"] == "OK"
    stale = structured(
        call(
            server,
            "browser.operate",
            {
                **target,
                "action": {
                    "operation": "fill",
                    "element": {"selector": "#missing"},
                    "value": "x",
                },
                "idempotency_key": "f2",
            },
        )
    )
    assert stale["error"]["code"] == "not_found"

    waited = structured(
        call(
            server,
            "browser.operate",
            {
                **target,
                "action": {"operation": "wait", "for": "navigation", "value": "next"},
                "idempotency_key": "w1",
            },
        )
    )
    assert waited["data"]["result"] == "https://example.test/next"
    await_vector = [c for c in commands(captured) if c[0] == "await"][0]
    assert 'location.href.includes("next")' in await_vector[3]

    key = structured(
        call(
            server,
            "browser.operate",
            {
                **target,
                "action": {"operation": "key", "key": "Enter", "mods": ["ctrl"]},
                "idempotency_key": "k1",
            },
        )
    )
    assert key["data"]["result"]["pressed"] is True
    assert ["key", "agent-target", "--key", "Enter", "--mod", "ctrl"] in commands(
        captured
    )

    for operation in (
        "back",
        "forward",
        "submit",
        "scroll",
        "reload",
        "focus",
        "navigate",
        "evaluate",
    ):
        action = {"operation": operation}
        if operation == "navigate":
            action["url"] = "https://example.test/next"
        if operation == "evaluate":
            action["javascript"] = "document.title"
        payload = structured(
            call(
                server,
                "browser.operate",
                {**target, "action": action, "idempotency_key": f"op-{operation}"},
            )
        )
        assert payload["result"]["outcome"] == "ok", payload
    assert [
        "navigate",
        "agent-target",
        "--url",
        "https://example.test/next",
    ] in commands(captured)
    assert ["activate", "agent-target"] in commands(captured)


def test_operator_tabs_are_never_mutation_targets(tmp_path, monkeypatch) -> None:
    server, captured = fake_browser(tmp_path, monkeypatch)
    open_agent_page(server)
    denied = structured(
        call(
            server,
            "browser.operate",
            {
                "target": {"page_id": "operator-page"},
                "action": {"operation": "reload"},
                "idempotency_key": "d1",
            },
        )
    )
    assert denied["error"]["code"] == "policy_denied"
    assert not any(c[0] == "reload" for c in commands(captured))
    bad = structured(
        call(
            server,
            "browser.operate",
            {
                "target": {"page_id": "agent-target"},
                "action": {"operation": "new"},
                "idempotency_key": "d2",
            },
        )
    )
    assert bad["error"]["code"] == "invalid_request"


def test_screenshot_download_upload_and_close(tmp_path, monkeypatch) -> None:
    server, captured = fake_browser(tmp_path, monkeypatch)
    open_agent_page(server)
    target = {"target": {"page_id": "agent-target"}}

    shot = call(server, "browser.screenshot", {**target, "full_page": True})
    assert isinstance(shot, CallToolResult) and not shot.is_error, shot
    assert [b for b in shot.content if isinstance(b, ImageContent)]
    data = structured(shot)["data"]
    assert (
        data["artifact"]["media_type"] == "image/png"
        and data["receipt"]["source"] == "chrome-cdp"
    )

    downloaded = call(
        server,
        "browser.operate",
        {
            **target,
            "action": {
                "operation": "download",
                "url": "https://example.test/report.txt",
            },
            "idempotency_key": "dl1",
        },
    )
    payload = structured(downloaded)
    assert payload["result"]["outcome"] == "ok", payload
    assert payload["data"]["artifact"]["representation"] == "resource"
    assert payload["data"]["artifact_ref"].startswith("sinnix://artifacts/")
    assert payload["data"]["result"]["status"] == 200

    destination = tmp_path / "out" / "report.txt"
    destination.parent.mkdir()
    saved = structured(
        call(
            server,
            "browser.operate",
            {
                **target,
                "action": {
                    "operation": "download",
                    "url": "https://example.test/report.txt",
                    "destination": {"path": str(destination)},
                },
                "idempotency_key": "dl2",
            },
        )
    )
    assert saved["result"]["outcome"] == "ok", saved
    assert (
        destination.read_text() == "report body"
        and saved["data"]["artifact"]["bytes"] == 11
    )

    upload = tmp_path / "upload.md"
    upload.write_text("hello")
    uploaded = structured(
        call(
            server,
            "browser.operate",
            {
                **target,
                "action": {
                    "operation": "upload",
                    "element": {"selector": "input[type=file]"},
                    "files": [{"path": str(upload)}],
                },
                "idempotency_key": "up1",
            },
        )
    )
    assert uploaded["data"]["result"]["attached"] == 1
    assert [
        "upload-files",
        "agent-target",
        "--selector",
        "input[type=file]",
        "--file",
        str(upload),
    ] in commands(captured)

    closed = structured(
        call(
            server,
            "browser.operate",
            {**target, "action": {"operation": "close"}, "idempotency_key": "cl1"},
        )
    )
    assert (
        closed["data"]["result"] == {"id": "agent-target", "closed": True}
        and closed["data"]["page"] is None
    )
    assert structured(call(server, "browser.pages", {}))["data"]["owned_refs"] == []


def test_observer_lists_but_cannot_operate(tmp_path, monkeypatch) -> None:
    server, _ = fake_browser(tmp_path, monkeypatch, "observer")
    assert len(structured(call(server, "browser.pages", {}))["data"]["pages"]) == 2
    assert "browser.operate" not in server._tool_manager._tools
    assert (
        structured(
            call(server, "browser.page", {"target": {"page_id": "operator-page"}})
        )["error"]["code"]
        == "policy_denied"
    )
