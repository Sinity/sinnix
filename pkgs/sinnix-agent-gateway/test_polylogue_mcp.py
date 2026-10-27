"""Session products keep the owner's MCP schemas, annotations and references."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sinnix_agent_gateway.actions import mcp_tools
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.runtime import Runtime
from test_actions_machine import call
from test_mcp_broker import write_stdio_fixture

ACTIONS = {action.name: action for action in mcp_tools.ACTIONS}


def test_discovered_query_hit_reads_its_exact_message_over_stdio(tmp_path):
    fixture = write_stdio_fixture(
        tmp_path,
        """import json, sys
for line in sys.stdin:
    request = json.loads(line)
    method = request["method"]
    if method == "initialize":
        result = {"protocolVersion": request["params"]["protocolVersion"], "capabilities": {"tools": {}}, "serverInfo": {"name": "polylogue", "version": "fixture"}}
    elif method == "tools/list":
        result = {"tools": [
            {"name": name, "description": name, "inputSchema": {"type": "object", "properties": fields, "required": list(fields)}, "annotations": {"readOnlyHint": read}}
            for name, fields, read in [
                ("query", {"query": {"type": "string"}}, True),
                ("read", {"session": {"type": "string"}, "message": {"type": "string"}}, True),
                ("status", {}, True), ("note_add", {}, False)]]}
    elif method == "tools/call":
        params = request["params"]
        if params["name"] == "query":
            assert params["arguments"] == {"query": "messages where written_by:human hydrus"}
            data = {"rows": [{"id": "fixture:m1", "session": "fixture:s1"}], "next": "owner-cursor"}
        else:
            assert params["name"] == "read"
            assert params["arguments"] == {"session": "fixture:s1", "message": "fixture:m1"}
            data = {"text": "Synthetic hydrus prompt", "message_id": "fixture:m1", "next": None}
        result = {"content": [{"type": "text", "text": json.dumps(data)}], "isError": False}
    else:
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
""",
    )
    runtime = Runtime.create(
        GatewayConfig(
            projects={},
            state_dir=tmp_path / "state",
            hub_socket_path=tmp_path / "hub.sock",
            mcp_broker_servers={
                "polylogue": {
                    "description": "Fixture archive",
                    "transport": "stdio",
                    "tier": "recall",
                    "brokered": True,
                    "command": sys.executable,
                    "args": [str(fixture)],
                    "env": {},
                }
            },
        )
    )
    catalog = call(
        runtime, "mcp.tools", {"server": "polylogue", "effect": "read"}, ACTIONS
    )
    tools = catalog["data"]["tools"]
    assert {tool["name"] for tool in tools} == {"query", "read", "status"}
    query = next(tool for tool in tools if tool["name"] == "query")
    assert query["input_schema"]["required"] == ["query"]
    result = call(
        runtime,
        "mcp.call",
        {
            "target": {"ref": query["ref"]},
            "arguments": {"query": "messages where written_by:human hydrus"},
        },
        ACTIONS,
    )
    response = result["data"]["response"]
    page = json.loads(response["content"][0]["text"])
    assert page["next"] == "owner-cursor"
    hit = page["rows"][0]
    result = call(
        runtime,
        "mcp.call",
        {
            "target": {"server": "polylogue", "tool": "read"},
            "arguments": {"session": hit["session"], "message": hit["id"]},
        },
        ACTIONS,
    )
    message = json.loads(result["data"]["response"]["content"][0]["text"])
    assert message == {
        "text": "Synthetic hydrus prompt",
        "message_id": hit["id"],
        "next": None,
    }


def test_packaged_rewrite_search_read_and_consumer_queries(tmp_path):
    import os
    import subprocess
    import time

    import pytest

    executable = os.environ.get("SINNIX_POLYLOGUE_TEST_EXECUTABLE")
    if executable is None:
        pytest.skip("the package check supplies the rewrite executable")
    home = tmp_path / "home"
    project = home / ".claude/projects/-fixture"
    project.mkdir(parents=True)
    source = project / "s1.jsonl"
    source.write_text(
        json.dumps(
            {
                "type": "user",
                "uuid": "m1",
                "sessionId": "s1",
                "cwd": "/fixture",
                "timestamp": "2026-10-01T12:00:00Z",
                "message": {
                    "role": "user",
                    "content": "Synthetic hydrus prompt, actually revise it",
                },
            }
        )
        + "\n"
    )
    environment = {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "XDG_RUNTIME_DIR": str(tmp_path / "runtime"),
    }
    for key in ("XDG_CONFIG_HOME", "XDG_RUNTIME_DIR"):
        Path(environment[key]).mkdir()
    daemon_env = {"PATH": os.environ["PATH"], **environment}
    with (tmp_path / "daemon.stderr").open("w+") as errors:
        daemon = subprocess.Popen(
            [executable, "daemon"],
            env=daemon_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=errors,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                probe = subprocess.run(
                    [executable, "status", "--json"],
                    env=daemon_env,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if probe.returncode == 0:
                    break
                if daemon.poll() is not None or time.monotonic() > deadline:
                    errors.seek(0)
                    pytest.fail("synthetic daemon did not start: " + errors.read())
                time.sleep(0.05)
            imported = subprocess.run(
                [executable, "import", str(source), "--json"],
                env=daemon_env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            assert imported.returncode == 0, imported.stderr
            runtime = Runtime.create(
                GatewayConfig(
                    projects={},
                    state_dir=tmp_path / "gateway",
                    hub_socket_path=tmp_path / "hub.sock",
                    mcp_broker_servers={
                        "polylogue": {
                            "description": "Synthetic archive",
                            "transport": "stdio",
                            "tier": "recall",
                            "brokered": True,
                            "command": executable,
                            "args": ["mcp"],
                            "env": environment,
                        }
                    },
                )
            )
            catalog = call(
                runtime, "mcp.tools", {"server": "polylogue", "effect": "read"}, ACTIONS
            )
            tools = {tool["name"]: tool for tool in catalog["data"]["tools"]}
            assert {"query", "read", "status"} <= set(tools)
            assert "note_add" not in tools

            def request(tool, arguments):
                result = call(
                    runtime,
                    "mcp.call",
                    {"target": {"ref": tools[tool]["ref"]}, "arguments": arguments},
                    ACTIONS,
                )
                assert result["result"]["outcome"] == "ok", result
                response = result["data"]["response"]
                assert not response.get("isError"), response
                return json.loads(response["content"][0]["text"])

            status = request("status", {})
            assert status["archive"] == str(tmp_path / "data/polylogue")
            page = request("query", {"query": "messages where written_by:human hydrus"})
            (hit,) = page["rows"]
            message = request(
                "read", {"session": hit["session"], "message": hit["id"], "budget": 100}
            )
            assert "Synthetic hydrus prompt" in message["text"]
            tagged = subprocess.run(
                [
                    executable,
                    "--json",
                    "note",
                    "tag",
                    f"session:{hit['session']}",
                    "--tag",
                    "synthetic-tag",
                ],
                env=daemon_env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            assert tagged.returncode == 0, tagged.stderr
            queries = [
                'messages where written_by:human since:9999d ("no wait" or actually or "that.s wrong" or "you are wrong" or incorrect)',
                "sessions since:9999d | group by origin | count",
                "sessions since:9999d | group by repo | count",
                "notes where kind:tag current:true withdrawn:false since:9999d | group by key | count",
            ]
            for query in queries:
                result = request("query", {"query": query})
                assert isinstance(result["rows"], list)
                if query.startswith("notes "):
                    (tag,) = result["rows"]
                    assert tag["key"] == "synthetic-tag"
        finally:
            daemon.terminate()
            try:
                daemon.wait(timeout=10)
            except subprocess.TimeoutExpired:
                daemon.kill()
                daemon.wait(timeout=10)
