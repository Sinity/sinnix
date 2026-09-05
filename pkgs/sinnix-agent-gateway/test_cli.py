from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest
from sinnix_agent_gateway import actions as action_set
from sinnix_agent_gateway import cli, cli_support
from sinnix_agent_gateway.cli_support import (
    CliInputError,
    build_request,
    load_json_input,
)
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
    assert cli.parser().parse_args(["info"]).config == local_config
    explicit = tmp_path / "explicit.json"
    assert (
        cli.parser().parse_args(["--config", str(explicit), "info"]).config == explicit
    )


def test_cli_config_environment_overrides_the_deployed_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = tmp_path / "configured.json"
    monkeypatch.setenv("SINNIX_AGENT_GATEWAY_CONFIG", str(configured))
    assert cli.parser().parse_args(["info"]).config == configured


class FakeServer:
    def __init__(self, calls: list[tuple[str, dict[str, object]]]) -> None:
        self.calls = calls

    async def call_tool(
        self, name: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        self.calls.append((name, arguments))
        return {"schema": "sinnix.gateway-result.v3", "result": {"outcome": "ok"}}


def test_call_replays_through_the_named_tool_after_local_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        cli_support, "create_server", lambda _config, _principal: FakeServer(calls)
    )
    payload = {"target": {"path": "/etc/os-release"}}
    response = anyio.run(
        cli_support.invoke_mcp, _config(tmp_path), "operator", "files.read", payload
    )
    assert response["schema"] == "sinnix.gateway-result.v3"
    assert calls == [("files.read", payload)]

    with pytest.raises(CliInputError, match="target"):
        anyio.run(
            cli_support.invoke_mcp, _config(tmp_path), "operator", "files.read", {}
        )
    with pytest.raises(CliInputError, match="did you mean"):
        anyio.run(
            cli_support.invoke_mcp, _config(tmp_path), "operator", "files.rea", {}
        )
    with pytest.raises(CliInputError, match="cannot invoke"):
        anyio.run(
            cli_support.invoke_mcp,
            _config(tmp_path),
            "observer",
            "files.change",
            {
                "target": {"path": "/x"},
                "change": {"operation": "remove"},
                "idempotency_key": "k",
            },
        )


def test_input_sources_are_bounded_and_require_a_json_object(tmp_path: Path) -> None:
    with pytest.raises(CliInputError, match="valid JSON"):
        load_json_input(inline="not-json")
    with pytest.raises(CliInputError, match="JSON object"):
        load_json_input(inline="[]")
    with pytest.raises(CliInputError, match="bound"):
        load_json_input(inline=json.dumps({"value": "x" * cli_support.MAX_INPUT_BYTES}))
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"{" + b"x" * cli_support.MAX_INPUT_BYTES)
    with pytest.raises(CliInputError, match="bound"):
        load_json_input(input_file=oversized)
    with pytest.raises(CliInputError, match="bound"):
        load_json_input(
            use_stdin=True, stdin=SimpleNamespace(read=lambda limit: "x" * limit)
        )


def test_set_flags_merge_json_values_without_conflicts() -> None:
    request = build_request(
        inline=json.dumps({"target": {"path": "/tmp/a"}}),
        assignments=["line_start=3", 'representation="text"', "flag=true"],
        idempotency_key="k1",
    )
    assert request == {
        "target": {"path": "/tmp/a"},
        "line_start": 3,
        "representation": "text",
        "flag": True,
        "idempotency_key": "k1",
    }
    with pytest.raises(CliInputError, match="different value"):
        build_request(inline=json.dumps({"idempotency_key": "a"}), idempotency_key="b")
    with pytest.raises(CliInputError, match="key=value"):
        build_request(assignments=["novalue"])


def test_catalog_display_exposes_schema_example_and_completion() -> None:
    schema = cli_support.catalog_display(
        principal="operator", action_name="files.patch", schema=True
    )
    example = cli_support.catalog_display(
        principal="operator", action_name="files.patch", example=True
    )
    completion = cli_support.catalog_display(principal="operator", complete="files.")
    assert schema["input_schema"]["type"] == "object"
    assert "data" in schema["output_schema"]["properties"]
    assert example["examples"]
    assert {row["name"] for row in completion["actions"]} >= {
        "files.read",
        "files.patch",
    }
    assert all(row["name"].startswith("files.") for row in completion["actions"])


def test_generated_examples_replay_and_validate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / FIXTURE_PATH.name
    fixtures = json.loads(fixture_path.read_text())
    calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        cli_support, "create_server", lambda _config, _principal: FakeServer(calls)
    )
    assert fixtures["examples"]
    for fixture in fixtures["examples"]:
        anyio.run(
            cli_support.invoke_mcp,
            _config(tmp_path),
            "operator",
            fixture["action"],
            fixture["input"],
        )
    assert [name for name, _ in calls] == [f["action"] for f in fixtures["examples"]]
    assert {f["action"] for f in fixtures["examples"]} == {
        a.name for a in action_set.visible("operator")
    }
