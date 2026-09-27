from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import stat
import subprocess
import sys
import time
from http.client import HTTPConnection
from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import BlobResourceContents, CallToolResult, EmbeddedResource
from sinnix_agent_gateway import actions as action_set
from sinnix_agent_gateway import cli, cli_support
from sinnix_agent_gateway.cli_support import (
    CliInputError,
    build_request,
    load_json_input,
)
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.gateway_codegen import FIXTURE_PATH
from sinnix_agent_gateway.runtime import Runtime


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


def test_private_http_transport_serves_operator_tools(tmp_path: Path) -> None:
    class UnixHTTP(HTTPConnection):
        def __init__(self, path: Path) -> None:
            super().__init__("localhost", timeout=10)
            self.path = path

        def connect(self) -> None:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(str(self.path))

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"stateDir": str(tmp_path / "state"), "projects": {}}))
    socket_path = tmp_path / "mcp.sock"
    command = [
        sys.executable,
        "-c",
        "from sinnix_agent_gateway.cli import main; main()",
        "--config",
        str(config_path),
        "serve-http",
        "--socket",
        str(socket_path),
    ]
    with subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) as process:
        try:
            deadline = time.monotonic() + 10
            while not socket_path.exists():
                assert process.poll() is None
                assert time.monotonic() < deadline, "MCP socket did not appear"
                time.sleep(0.05)

            def request(payload: dict[str, object], session: str | None = None):
                connection = UnixHTTP(socket_path)
                headers = {
                    "Host": "localhost:8000",
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                }
                if session:
                    headers["Mcp-Session-Id"] = session
                try:
                    connection.request("POST", "/mcp", json.dumps(payload), headers)
                    response = connection.getresponse()
                    return response.status, dict(response.getheaders()), response.read()
                finally:
                    connection.close()

            status, headers, body = request({
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "transport-test", "version": "1"}},
            })
            assert status == 200 and "result" in json.loads(body)
            session = headers["mcp-session-id"]
            assert request({"jsonrpc": "2.0", "method": "notifications/initialized"}, session)[0] == 202
            status, _, body = request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, session)
            assert status == 200
            names = {tool["name"] for tool in json.loads(body)["result"]["tools"]}
            assert names == {action.name for action in action_set.visible("operator")}
            status, _, body = request({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                       "params": {"name": "gateway.catalog", "arguments": {"limit": 1}}}, session)
            assert status == 200 and "result" in json.loads(body)
            assert stat.S_IMODE(tmp_path.stat().st_mode) & 0o077 == 0
        finally:
            process.terminate()
            process.wait(timeout=5)

    permissive = tmp_path / "permissive"
    permissive.mkdir(mode=0o755)
    permissive.chmod(0o755)
    refused = subprocess.run(
        [*command[:-1], str(permissive / "mcp.sock")],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert refused.returncode != 0
    assert "socket directory must be owned by this user and private" in refused.stderr


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


def test_cli_projection_preserves_binary_content_blocks() -> None:
    payload = b"\x00\x01binary\xff"
    result = cli_support._structured_response(
        CallToolResult(
            content=[
                EmbeddedResource(
                    type="resource",
                    resource=BlobResourceContents(
                        uri="sinnix://files/example",
                        mime_type="application/octet-stream",
                        blob=base64.b64encode(payload).decode(),
                    ),
                )
            ],
            structured_content={
                "schema": "sinnix.gateway-result.v3",
                "result": {"outcome": "ok"},
            },
        )
    )

    block = result["content"][0]
    assert block["resource"]["mimeType"] == "application/octet-stream"
    assert base64.b64decode(block["resource"]["blob"]) == payload


def test_cli_returns_nonzero_after_printing_typed_action_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "gateway.json"
    config.write_text("{}", encoding="utf-8")
    failure = {
        "schema": "sinnix.gateway-result.v3",
        "result": {"outcome": "error"},
        "error": {"code": "not_found", "message": "missing"},
    }
    monkeypatch.setattr(cli, "invoke", lambda *_args: failure)
    monkeypatch.setattr(
        "sys.argv",
        [
            "sinnix-agent-gateway",
            "--config",
            str(config),
            "call",
            "files.stat",
            "--input",
            '{"target":{"path":"/missing"}}',
        ],
    )

    with pytest.raises(SystemExit) as raised:
        cli.main()

    assert raised.value.code == 1
    assert json.loads(capsys.readouterr().out) == failure


def test_cli_successful_action_keeps_zero_exit_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "gateway.json"
    config.write_text("{}", encoding="utf-8")
    success = {
        "schema": "sinnix.gateway-result.v3",
        "result": {"outcome": "ok"},
    }
    monkeypatch.setattr(cli, "invoke", lambda *_args: success)
    monkeypatch.setattr(
        "sys.argv",
        [
            "sinnix-agent-gateway",
            "--config",
            str(config),
            "call",
            "files.stat",
            "--input",
            '{"target":{"path":"/etc/os-release"}}',
        ],
    )

    cli.main()

    assert json.loads(capsys.readouterr().out) == success


@pytest.mark.skipif(
    not os.environ.get("SINNIX_GATEWAY_TEST_EXECUTABLE"),
    reason="package check supplies the installed gateway executable",
)
def test_cli_subprocess_preserves_failure_envelope_and_status(tmp_path: Path) -> None:
    config = tmp_path / "gateway.json"
    config.write_text(
        json.dumps({"stateDir": str(tmp_path / "state")}), encoding="utf-8"
    )
    executable = os.environ["SINNIX_GATEWAY_TEST_EXECUTABLE"]
    command = [
        executable,
        "--config",
        str(config),
        "--principal",
        "operator",
        "call",
        "files.stat",
        "--input",
        json.dumps({"target": {"path": str(tmp_path / "missing")}}),
    ]

    failure = subprocess.run(command, capture_output=True, text=True, check=False)

    assert failure.returncode == 1
    envelope = json.loads(failure.stdout)
    assert envelope["result"]["outcome"] == "error"
    assert envelope["error"]["code"] == "not_found"


@pytest.mark.skipif(
    not os.environ.get("SINNIX_GATEWAY_TEST_EXECUTABLE"),
    reason="package check supplies the installed gateway executable",
)
def test_cli_subprocess_keeps_binary_bytes_out_of_the_chat(tmp_path: Path) -> None:
    config = tmp_path / "gateway.json"
    config.write_text(
        json.dumps({"stateDir": str(tmp_path / "state")}), encoding="utf-8"
    )
    fixture = tmp_path / "fixture.bin"
    payload = b"\x00cli-resource\xff"
    fixture.write_bytes(payload)
    command = [
        os.environ["SINNIX_GATEWAY_TEST_EXECUTABLE"],
        "--config",
        str(config),
        "--principal",
        "operator",
        "call",
        "files.read",
        "--input",
        json.dumps({"target": {"path": str(fixture)}, "with_sha256": True}),
    ]

    completed = subprocess.run(command, capture_output=True, text=True, check=False)

    assert completed.returncode == 0
    response = json.loads(completed.stdout)
    assert response["data"]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert response["data"]["artifact"]["representation"] == "link"
    assert not any(
        block["type"] in {"resource_link", "resource"} for block in response["content"]
    )


def test_stdio_mcp_client_consumes_complete_binary_artifact(tmp_path: Path) -> None:
    config = _config(tmp_path)
    runtime = Runtime.create(config, "operator")
    capture = config.state_dir / "captures" / "client-witness"
    capture.mkdir(parents=True)
    source = capture / "archive.zip"
    original = bytes(range(251)) * 11
    source.write_bytes(original)
    runtime.artifacts.attest_capture(
        capture, source="client-witness", target={}, files=[source]
    )
    artifact_id = runtime.artifacts.register(
        source, kind="project-export", owner_id="client-witness"
    )
    config_path = tmp_path / "gateway.json"
    config_path.write_text(
        json.dumps({"stateDir": str(config.state_dir), "projects": {}}),
        encoding="utf-8",
    )
    ref = f"sinnix://artifacts/{artifact_id}"

    async def read_pages() -> list[dict]:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "sinnix_agent_gateway.cli",
                "--config",
                str(config_path),
                "serve",
            ],
            env=dict(os.environ),
        )
        pages = []
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()
                offset = 0
                while True:
                    result = await client.call_tool(
                        "artifacts.read",
                        {
                            "target": {"ref": ref},
                            "representation": "binary",
                            "offset": offset,
                            "max_bytes": 257,
                        },
                    )
                    assert result.structured_content is not None
                    envelope = result.structured_content
                    assert envelope["result"]["outcome"] == "ok", envelope
                    page = envelope["data"]
                    pages.append(page)
                    if page["next_offset"] is None:
                        return pages
                    assert page["next_offset"] > offset
                    offset = page["next_offset"]

    pages = anyio.run(read_pages)

    def consume(available: list[dict]) -> bytes:
        chunks = []
        offset = 0
        for page in available:
            chunk = base64.b64decode(page["base64"], validate=True)
            assert page["ref"] == ref
            assert page["offset"] == offset
            assert page["returned_bytes"] == len(chunk) <= 257
            assert page["bytes"] == len(original)
            assert page["sha256"] == hashlib.sha256(original).hexdigest()
            chunks.append(chunk)
            offset += len(chunk)
            assert page["truncated"] == (page["next_offset"] is not None)
            if page["next_offset"] is not None:
                assert page["next_offset"] == offset
        if not available or available[-1]["next_offset"] is not None:
            raise ValueError("binary artifact coverage is incomplete")
        if offset != available[-1]["bytes"]:
            raise ValueError("binary artifact byte count is incomplete")
        return b"".join(chunks)

    assert len(pages) > 1
    with pytest.raises(ValueError, match="coverage is incomplete"):
        consume(pages[:1])
    assert consume(pages) == original


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
