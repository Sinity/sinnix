import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def test_stdio_smoke(tmp_path: Path):
    cfg = {
        "stateDir": str(tmp_path / "state"),
        "repositories": {
            "local/test": {
                "url": str(tmp_path / "missing.git"),
                "tasks": {
                    "echo": {
                        "command": ["echo", "hi"],
                        "description": "Say hi.",
                        "timeout": 30,
                        "risk": "low",
                    }
                },
            }
        },
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))

    proc = subprocess.Popen(
        [sys.executable, "-m", "sinnix_agent_gateway.server", "--config", str(cfg_path), "stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdin is not None
        assert proc.stdout is not None
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n")
        proc.stdin.flush()
        init = json.loads(proc.stdout.readline())
        assert init["result"]["serverInfo"]["name"] == "sinnix-agent-gateway"

        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n")
        proc.stdin.flush()
        tools = json.loads(proc.stdout.readline())["result"]["tools"]
        assert {tool["name"] for tool in tools} >= {"gateway_guide", "repo_materialize", "run_command", "repo_pack", "repo_export_bundle", "artifact_read_base64"}
        assert all("outputSchema" in tool for tool in tools)
        materialize = next(tool for tool in tools if tool["name"] == "repo_materialize")
        assert "Use this before" in materialize["description"]
        assert "description" in materialize["inputSchema"]["properties"]["repo"]
        assert materialize["outputSchema"]["properties"]["workspace"]["type"] == "string"

        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "gateway_info", "arguments": {}}}) + "\n")
        proc.stdin.flush()
        info = json.loads(proc.stdout.readline())["result"]["structuredContent"]
        assert info["yolo"] is True
        assert info["transports"]["streamable_http_path"] == "/mcp"
        assert info["repositories"]["local/test"]["tasks"]["echo"]["description"] == "Say hi."

        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "gateway_guide", "arguments": {}}}) + "\n")
        proc.stdin.flush()
        guide = json.loads(proc.stdout.readline())["result"]["structuredContent"]
        assert "repo_materialize" in " ".join(guide["rules"])
        assert "repo_export_bundle" in " ".join(guide["rules"])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_binary_artifact_base64_chunks(tmp_path: Path):
    from sinnix_agent_gateway.server import Gateway

    g = Gateway({"stateDir": str(tmp_path / "state")})
    artifact = g.art("sample.bin", b"abcdef")
    first = g.artifact_read_base64({"artifact": artifact["artifact"], "offset": 0, "max_bytes": 3})
    second = g.artifact_read_base64({"artifact": artifact["artifact"], "offset": first["next_offset"], "max_bytes": 3})
    assert first["base64"] == "YWJj"
    assert second["base64"] == "ZGVm"
    assert second["next_offset"] is None


def test_info_uses_user_state_by_default(tmp_path: Path):
    env = os.environ.copy()
    env["XDG_STATE_HOME"] = str(tmp_path / "state-home")

    proc = subprocess.run(
        [sys.executable, "-m", "sinnix_agent_gateway.server", "info"],
        capture_output=True,
        check=True,
        env=env,
        text=True,
    )

    info = json.loads(proc.stdout)
    assert info["state_dir"] == str(tmp_path / "state-home" / "sinnix-agent-gateway")


def post_json(url: str, payload: dict, *, accept: str = "application/json") -> tuple[str, str]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", "accept": accept},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.headers.get("content-type", ""), resp.read().decode()


def test_http_mcp_endpoint(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"stateDir": str(tmp_path / "state")}))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    proc = None
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "sinnix_agent_gateway.server", "--config", str(cfg_path), "http", "--host", "127.0.0.1", "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        url = f"http://127.0.0.1:{port}/mcp"
        for _ in range(50):
            try:
                content_type, body = post_json(url, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
                break
            except OSError:
                time.sleep(0.05)
        else:
            raise AssertionError("HTTP MCP endpoint did not start")
        assert content_type.startswith("application/json")
        assert json.loads(body)["result"] == {}

        content_type, body = post_json(url, {"jsonrpc": "2.0", "id": 2, "method": "ping"}, accept="text/event-stream")
        assert content_type.startswith("text/event-stream")
        assert "data: " in body

        try:
            post_json(f"http://127.0.0.1:{port}/", {"jsonrpc": "2.0", "id": 3, "method": "ping"})
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("POST / endpoint must not be accepted")
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


def test_durable_background_job_survives_gateway_instance(tmp_path: Path):
    from sinnix_agent_gateway.server import Gateway

    workspace = tmp_path / "state" / "workspaces" / "w"
    workspace.mkdir(parents=True)
    (workspace / ".sinnix-agent-workspace.json").write_text(json.dumps({"repo": "local/test", "workspace": "w"}))
    cfg = {"stateDir": str(tmp_path / "state"), "repositories": {"local/test": {"tasks": {"slow": {"command": ["sh", "-c", "echo done"], "background": True}}}}}

    first = Gateway(cfg)
    started = first.run_task({"workspace": "w", "task": "slow"})
    job_id = started["job_id"]

    second = Gateway(cfg)
    for _ in range(50):
        status = second.job_status({"job_id": job_id})
        if not status["running"]:
            break
        time.sleep(0.05)
    assert status["returncode"] == 0
    assert "done" in status["stdout_tail"]
