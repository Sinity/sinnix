from __future__ import annotations

import json
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier

import pytest
from sinnix_agent_gateway import browser as browser_module
from sinnix_agent_gateway.artifacts import ArtifactService
from sinnix_agent_gateway.browser import (
    BrowserDiagnosticError,
    BrowserError,
    BrowserService,
)
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.owner_execution import ExecutionResult


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
        "elif sys.argv[1] == 'screenshot':\n"
        "    pathlib.Path(sys.argv[sys.argv.index('--out') + 1]).write_bytes(b'PNG fixture')\n"
        "    print(json.dumps({'ok': True}))\n"
        "else:\n"
        "    print(json.dumps({'ok': True}))\n"
    )
    runner.chmod(0o700)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        chrome_control_command=str(runner),
    )
    principal = Principal.for_name(principal_name)
    return BrowserService(
        config, principal, ArtifactService(config, principal)
    ), captured


def commands(path: Path) -> list[list[str]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def run_concurrent_registry_updates(
    monkeypatch: pytest.MonkeyPatch,
    state_dir: Path,
    first_update: Callable[[BrowserService], None],
    second_update: Callable[[BrowserService], None],
) -> BrowserService:
    barrier = Barrier(2)
    lock_paths: list[Path] = []
    original_flock = browser_module.flock
    browser, _ = browser_service(state_dir.parent, "operator")

    @contextmanager
    def synchronized_flock(path):
        lock_paths.append(Path(path))
        barrier.wait(timeout=5)
        with original_flock(path):
            yield

    monkeypatch.setattr(browser_module, "flock", synchronized_flock)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_update, browser)
        second = pool.submit(second_update, browser)
        first.result(timeout=5)
        second.result(timeout=5)

    assert lock_paths == [state_dir / "browser-targets.lock"] * 2
    return browser


def test_concurrent_target_registration_preserves_both_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_dir = tmp_path / "state"
    browser = run_concurrent_registry_updates(
        monkeypatch,
        state_dir,
        lambda service: service.register_target({"id": "first"}),
        lambda service: service.register_target({"id": "second"}),
    )

    assert browser.owned_page_ids() == {"first", "second"}


def test_concurrent_register_and_forget_preserve_unrelated_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_dir = tmp_path / "state"
    browser, _ = browser_service(tmp_path, "operator")
    browser.register_target({"id": "existing"})
    browser = run_concurrent_registry_updates(
        monkeypatch,
        state_dir,
        lambda service: service.register_target({"id": "new"}),
        lambda service: service.forget_target("existing"),
    )

    assert browser.owned_page_ids() == {"new"}


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


def test_canonical_browser_target_read_requires_registered_agent_window(
    tmp_path: Path,
) -> None:
    browser, captured = browser_service(tmp_path, "operator")

    browser.action("agent_window", {})
    result = browser.describe_target("agent-target")

    assert result == {
        "operation": "info",
        "page_id": "agent-target",
        "result": {"ok": True},
    }
    assert commands(captured) == [["agent-window"], ["info", "agent-target"]]
    with pytest.raises(BrowserError, match="gateway-created agent window"):
        browser.describe_target("operator-page")


@pytest.mark.parametrize("operation", ["info", "get_text", "get_html"])
def test_direct_browser_target_reads_require_registered_agent_window(
    tmp_path: Path, operation: str
) -> None:
    browser, captured = browser_service(tmp_path, "operator")

    with pytest.raises(BrowserError, match="gateway-created agent window"):
        browser.read(operation, "operator-page")

    assert not captured.exists()


def test_browser_owner_failure_is_attested_as_a_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    browser, _ = browser_service(tmp_path, "operator")
    monkeypatch.setattr(
        browser.execution,
        "run",
        lambda command, profile: ExecutionResult(
            tuple(command),
            None,
            b"",
            b"chrome missing",
            failure_class="command_unavailable:FileNotFoundError",
        ),
    )

    with pytest.raises(BrowserDiagnosticError) as error:
        browser.read("status")

    diagnostic_id = error.value.response["diagnostic_artifact_id"]
    assert isinstance(diagnostic_id, str)
    diagnostic = browser.artifacts.read(diagnostic_id)
    assert diagnostic["kind"] == "owner-diagnostic"


def test_agent_window_rejects_visible_target_after_wrapper_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    browser, _ = browser_service(tmp_path, "operator")
    commands: list[list[str]] = []

    def run(arguments: list[str]) -> dict[str, object]:
        commands.append(arguments)
        return {"result": '{"id":"agent-target","parked":false}\nnote: visible window'}

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


def test_browser_capture_registers_only_owned_target_as_artifact(
    tmp_path: Path,
) -> None:
    browser, captured = browser_service(tmp_path, "operator")

    browser.action("agent_window", {})
    result = browser.capture("agent-target", full_page=True)
    artifact = browser.artifacts.read(result["artifact_id"])

    assert result["page_id"] == "agent-target"
    assert result["receipt"]["source"] == "chrome-cdp"
    assert result["receipt"]["target"] == {
        "kind": "gateway-owned-browser-target",
        "page_id": "agent-target",
    }
    assert result["artifact"]["content_type"] == "image/png"
    assert artifact["base64"] == "UE5HIGZpeHR1cmU="
    assert commands(captured) == [
        ["agent-window"],
        [
            "screenshot",
            "agent-target",
            "--format",
            "png",
            "--out",
            str(next((tmp_path / "state" / "captures").glob("*/browser.png"))),
            "--full-page",
        ],
    ]


def test_browser_capture_rejects_existing_operator_target_before_invocation(
    tmp_path: Path,
) -> None:
    browser, captured = browser_service(tmp_path, "operator")

    with pytest.raises(BrowserError, match="gateway-created agent window"):
        browser.capture("operator-page")

    assert not captured.exists()
