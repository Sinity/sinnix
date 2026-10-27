"""The installed MCP launcher exposes the rewrite's command schemas."""

import json
import subprocess
import sys


def send(process, message):
    process.stdin.write(json.dumps(message) + "\n")
    process.stdin.flush()


def response(process, request_id):
    for line in process.stdout:
        message = json.loads(line)
        if message.get("id") == request_id:
            assert "error" not in message, message
            return message["result"]
    raise AssertionError(f"MCP ended before answering {request_id}")


def main():
    process = subprocess.Popen(
        [sys.argv[1]], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    try:
        send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "sinnix-check", "version": "1"},
                },
            },
        )
        initialized = response(process, 1)
        assert initialized["serverInfo"]["name"] == "polylogue", initialized
        send(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        send(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = {tool["name"]: tool for tool in response(process, 2)["tools"]}
        assert {
            "query",
            "read",
            "status",
            "brief",
            "recall",
            "takeover",
        } <= tools.keys()
        assert tools["query"]["inputSchema"]["properties"]["query"]["type"] == "string"
        assert tools["read"]["inputSchema"]["properties"]["session"]["type"] == "string"
        assert "session" in tools["read"]["inputSchema"]["required"]
        process.stdin.close()
        assert process.wait(timeout=30) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


if __name__ == "__main__":
    main()
