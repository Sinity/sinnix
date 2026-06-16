import json
import os
import subprocess
import sys
from pathlib import Path


def test_stdio_smoke(tmp_path: Path):
    cfg = {
        "stateDir": str(tmp_path / "state"),
        "repositories": {
            "local/test": {
                "url": str(tmp_path / "missing.git"),
                "tasks": {"echo": ["echo", "hi"]},
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
        assert {tool["name"] for tool in tools} >= {"repo_materialize", "run_command", "repo_pack"}

        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "gateway_info", "arguments": {}}}) + "\n")
        proc.stdin.flush()
        info = json.loads(proc.stdout.readline())["result"]["structuredContent"]
        assert info["yolo"] is True
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


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
