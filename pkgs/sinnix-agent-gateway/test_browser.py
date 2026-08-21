from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from sinnix_agent_gateway.browser import BrowserError, BrowserService
from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import GatewayConfig


def browser_service(tmp_path: Path, principal_name: str) -> tuple[BrowserService, Path]:
    captured = tmp_path / "browser-commands.jsonl"
    runner = tmp_path / "chrome-control"
    runner.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        f"with pathlib.Path({str(captured)!r}).open('a') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1] == 'agent-window':\n"
        "    print(json.dumps({'id': 'agent-target', 'parked': True}))\n"
        "else:\n"
        "    print(json.dumps({'ok': True}))\n"
    )
    runner.chmod(0o700)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        chrome_control_command=str(runner),
    )
    return BrowserService(config, Principal.for_name(principal_name)), captured


def commands(path: Path) -> list[list[str]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_observer_can_read_browser_tabs_without_action_registration(tmp_path: Path) -> None:
    browser, captured = browser_service(tmp_path, "observer")

    result = browser.read("list_tabs")

    assert result == {"operation": "list_tabs", "result": {"ok": True}}
    assert commands(captured) == [["list-tabs"]]


def test_operator_actions_require_gateway_created_agent_target(tmp_path: Path) -> None:
    browser, captured = browser_service(tmp_path, "operator")

    target = browser.action("agent_window", {"url": "https://example.test"})
    result = browser.action(
        "navigate",
        {"page_id": "agent-target", "url": "https://example.test/next"},
    )

    assert target["target"]["id"] == "agent-target"
    assert result["page_id"] == "agent-target"
    assert commands(captured) == [
        ["agent-window", "--url", "https://example.test"],
        ["navigate", "agent-target", "--url", "https://example.test/next"],
    ]


def test_agent_window_rejects_visible_target_after_wrapper_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    browser, _ = browser_service(tmp_path, "operator")
    commands: list[list[str]] = []

    def run(arguments: list[str]) -> dict[str, object]:
        commands.append(arguments)
        return {
            "result": '{"id":"agent-target","parked":false}\nnote: visible window'
        }

    monkeypatch.setattr(browser, "_run", run)

    with pytest.raises(BrowserError, match="hidden workspace"):
        browser.action("agent_window", {})

    assert commands == [["agent-window"], ["close", "agent-target"]]


def test_operator_cannot_act_on_existing_browser_page(tmp_path: Path) -> None:
    browser, _ = browser_service(tmp_path, "operator")

    with pytest.raises(BrowserError, match="gateway-created agent window"):
        browser.action(
            "navigate",
            {"page_id": "operator-page", "url": "https://example.test"},
        )


def test_observer_cannot_create_or_operate_browser_window(tmp_path: Path) -> None:
    browser, _ = browser_service(tmp_path, "observer")

    with pytest.raises(PolicyError, match="browser.action"):
        browser.action("agent_window", {})
