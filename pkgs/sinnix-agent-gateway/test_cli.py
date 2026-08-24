from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest

from sinnix_agent_gateway import cli, cli_support
from sinnix_agent_gateway.cli_support import CliInputError, build_request, load_json_input
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.gateway_codegen import FIXTURE_PATH


def _config(tmp_path: Path) -> GatewayConfig:
    return GatewayConfig(state_dir=tmp_path / "state", projects={})


def test_cli_defaults_to_the_deployed_local_estate_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local_config = tmp_path / "agent-gateway.json"
    local_config.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("SINNIX_AGENT_GATEWAY_CONFIG", raising=False)
    monkeypatch.setattr(cli, "LOCAL_CONFIG_PATH", local_config)

    assert cli.parser().parse_args(["status"]).config == local_config

    explicit = tmp_path / "explicit.json"
    assert cli.parser().parse_args(["--config", str(explicit), "status"]).config == explicit


def test_cli_config_environment_overrides_the_deployed_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = tmp_path / "configured.json"
    monkeypatch.setenv("SINNIX_AGENT_GATEWAY_CONFIG", str(configured))

    assert cli.parser().parse_args(["status"]).config == configured


class FakeServer:
    def __init__(self, calls: list[tuple[str, dict[str, object]]]) -> None:
        self.calls = calls

    async def call_tool(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        self.calls.append((name, arguments))
        return {"schema": "sinnix.gateway-result.v3", "result": {"outcome": "ok"}}


@pytest.mark.parametrize(
    ("verb", "payload"),
    [
        ("status", {}),
        ("catalog", {}),
        ("query", {"action_name": "projects.query", "ref": "sinnix://projects/fixture", "query": "fixture"}),
        ("get", {"ref": "sinnix://projects/fixture"}),
        ("context", {"ref": "sinnix://projects/fixture"}),
        ("events", {}),
        ("wait", {"ref": "sinnix://jobs/job-fixture"}),
        ("change", {"action_name": "beads.change", "ref": "sinnix://projects/fixture", "operation": "comment", "parameters": {"id": "fixture-1", "text": "fixture"}, "idempotency_key": "cli-change"}),
        ("operate", {"action_name": "beads.operate", "ref": "sinnix://projects/fixture", "operation": "snapshot.publish", "parameters": {}, "idempotency_key": "cli-operate"}),
        ("run", {"action_name": "operations.run", "project_id": "fixture", "operation": "check", "parameters": {}, "idempotency_key": "cli-run"}),
    ],
)
def test_every_v2_verb_replays_through_the_matching_mcp_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verb: str, payload: dict[str, object]
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(cli_support, "create_server", lambda _config, _principal: FakeServer(calls))
    response = anyio.run(cli_support.invoke_mcp, _config(tmp_path), "operator", verb, payload)
    assert response["schema"] == "sinnix.gateway-result.v3"
    assert calls == [(verb, payload)]


def test_input_sources_are_bounded_and_require_a_json_object(tmp_path: Path) -> None:
    with pytest.raises(CliInputError, match="valid UTF-8 JSON"):
        load_json_input(inline="not-json")
    with pytest.raises(CliInputError, match="JSON object"):
        load_json_input(inline="[]")
    with pytest.raises(CliInputError, match="input bound"):
        load_json_input(inline=json.dumps({"value": "x" * cli_support.MAX_INPUT_BYTES}))
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"{" + b"x" * cli_support.MAX_INPUT_BYTES)
    with pytest.raises(CliInputError, match="input bound"):
        load_json_input(input_file=oversized)
    with pytest.raises(CliInputError, match="input bound"):
        load_json_input(use_stdin=True, stdin=SimpleNamespace(read=lambda limit: "x" * limit))


def test_input_flags_merge_without_allowing_conflicting_values() -> None:
    request = build_request(
        "change",
        inline=json.dumps({"action_name": "beads.changeset", "ref": "sinnix://projects/fixture", "parameters": {"actions": []}}),
        operation="preview",
        idempotency_key="changeset",
    )
    assert request["operation"] == "preview"
    with pytest.raises(CliInputError, match="different value"):
        build_request(
            "get",
            inline=json.dumps({"ref": "sinnix://projects/one"}),
            ref="sinnix://projects/two",
        )


def test_catalog_display_exposes_schema_example_and_resource_completion() -> None:
    schema = cli_support.catalog_display(principal="operator", action_name="beads.change", schema=True)
    example = cli_support.catalog_display(principal="operator", action_name="beads.change", example=True)
    completion = cli_support.catalog_display(principal="operator", complete="sinnix://gateway/v2/actions/beads.")
    assert schema["schema"]["type"] == "object"
    assert example["examples"]
    assert completion["actions"]


def test_catalog_need_query_selects_the_beads_registry_term() -> None:
    request = build_request("catalog", query="wire dependency between Polylogue beads")
    assert request["text"] == "beads"


def test_generated_cli_examples_are_replayable_against_a_fixture_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / FIXTURE_PATH.name
    fixtures = json.loads(fixture_path.read_text())
    calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(cli_support, "create_server", lambda _config, _principal: FakeServer(calls))
    for fixture in fixtures["examples"]:
        anyio.run(
            cli_support.invoke_mcp,
            _config(tmp_path),
            "operator",
            fixture["verb"],
            fixture["cli_input"],
        )
    assert [name for name, _ in calls] == [fixture["verb"] for fixture in fixtures["examples"]]
