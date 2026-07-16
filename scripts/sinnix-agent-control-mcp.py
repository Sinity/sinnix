#!/usr/bin/env python3
# @sinnix-package
# name: sinnix-agent-control-mcp
# description: Typed MCP control plane for attested native Claude, Codex, and Gemini jobs
# runtimeInputs: bash coreutils jq @sinnix-agent-scope-exec
"""Stdio MCP adapter for the Sinnix native-agent orchestration scripts.

This process deliberately exposes only stable job identities and artifacts. It
never accepts a shell command, PID, arbitrary file path, or terminal selector.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
MAX_PROMPT_CHARS = 200_000
MAX_OUTPUT_CHARS = 100_000
DEFAULT_OUTPUT_CHARS = 12_000


class ToolError(Exception):
    """An expected caller-visible tool failure."""


def state_dir() -> Path:
    configured = os.environ.get("SINNIX_AGENT_JOB_STATE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    xdg_state = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg_state).expanduser() if xdg_state else Path.home() / ".local" / "state"
    return (base / "sinnix" / "agent-jobs").resolve()


def skill_dir() -> Path:
    configured = os.environ.get("SINNIX_AGENT_ORCHESTRATION_SKILL_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".config" / "hermes" / "skills" / "agent-orchestration").resolve()


def runner() -> Path:
    path = skill_dir() / "scripts" / "run_agent_prompt.sh"
    if not path.is_file():
        raise ToolError(f"agent orchestration runner is unavailable: {path}")
    return path


def controller() -> Path:
    path = skill_dir() / "scripts" / "agent_job_control.sh"
    if not path.is_file():
        raise ToolError(f"agent job controller is unavailable: {path}")
    return path


def require_object(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise ToolError("arguments must be an object")
    return arguments


def require_string(arguments: dict[str, Any], name: str, *, limit: int | None = None) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"{name} must be a non-empty string")
    if limit is not None and len(value) > limit:
        raise ToolError(f"{name} exceeds {limit} characters")
    return value


def optional_string(arguments: dict[str, Any], name: str, *, limit: int = 256) -> str | None:
    value = arguments.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"{name} must be a non-empty string when provided")
    if len(value) > limit:
        raise ToolError(f"{name} exceeds {limit} characters")
    return value


def require_job_id(arguments: dict[str, Any]) -> str:
    job_id = require_string(arguments, "job_id", limit=128)
    if not JOB_ID_RE.fullmatch(job_id):
        raise ToolError("job_id must match [A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
    return job_id


def manifest_path(job_id: str) -> Path:
    return state_dir() / f"{job_id}.json"


def load_manifest(job_id: str) -> dict[str, Any]:
    path = manifest_path(job_id)
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ToolError(f"unknown job ID: {job_id}") from exc
    except json.JSONDecodeError as exc:
        raise ToolError(f"malformed job manifest: {job_id}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1 or value.get("job_id") != job_id:
        raise ToolError(f"unattested job manifest: {job_id}")
    return value


def json_text(value: Any) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, sort_keys=True)}],
        "structuredContent": value,
    }


def run_control(*args: str) -> Any:
    result = subprocess.run(
        [str(controller()), "--state-dir", str(state_dir()), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ToolError(result.stderr.strip() or result.stdout.strip() or "agent job controller failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ToolError("agent job controller returned invalid JSON") from exc


def safe_artifact(manifest: dict[str, Any], artifact: str) -> Path:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ToolError("attested job manifest has no artifacts")
    raw = artifacts.get(artifact)
    if not isinstance(raw, str) or not raw:
        raise ToolError(f"job has no {artifact} artifact")
    try:
        path = Path(raw).resolve(strict=True)
    except FileNotFoundError as exc:
        raise ToolError(f"job {artifact} artifact is not available") from exc
    root = state_dir().resolve()
    if path != root and root not in path.parents:
        raise ToolError("refusing artifact outside attested job state")
    if not path.is_file():
        raise ToolError(f"job {artifact} artifact is not a regular file")
    return path


def start_agent_job(arguments: Any) -> dict[str, Any]:
    a = require_object(arguments)
    backend = require_string(a, "backend", limit=16)
    if backend not in {"claude", "codex", "gemini"}:
        raise ToolError("backend must be one of: claude, codex, gemini")

    workdir = Path(require_string(a, "workdir", limit=4096)).expanduser().resolve()
    if not workdir.is_dir():
        raise ToolError(f"workdir is not a directory: {workdir}")
    prompt = require_string(a, "prompt", limit=MAX_PROMPT_CHARS)
    model = optional_string(a, "model")
    effort = optional_string(a, "reasoning_effort", limit=32)
    role = optional_string(a, "job_role", limit=512)
    work_item = optional_string(a, "work_item", limit=512)
    supplied_id = optional_string(a, "job_id", limit=128)
    job_id = supplied_id or f"agent-{int(time.time())}-{secrets.token_hex(8)}"
    if not JOB_ID_RE.fullmatch(job_id):
        raise ToolError("job_id must match [A-Za-z0-9][A-Za-z0-9_.-]{0,127}")

    root = state_dir()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    manifest = manifest_path(job_id)
    prompt_path = root / f"{job_id}.prompt.md"
    log_path = root / f"{job_id}.log"
    final_path = root / f"{job_id}.final.md"
    if manifest.exists() or prompt_path.exists():
        raise ToolError(f"job ID already exists: {job_id}")
    prompt_path.write_text(prompt)
    prompt_path.chmod(0o600)

    command = [
        str(runner()),
        "--agent",
        backend,
        "--workdir",
        str(workdir),
        "--prompt-file",
        str(prompt_path),
        "--log-file",
        str(log_path),
        "--last-file",
        str(final_path),
        "--job-id",
        job_id,
        "--job-state-dir",
        str(root),
    ]
    if backend == "codex" and model is None:
        model = "gpt-5.6-terra"
    if model is not None:
        command.extend(["--model", model])
    if effort is not None:
        command.extend(["--reasoning-effort", effort])
    if role is not None:
        command.extend(["--job-role", role])
    if work_item is not None:
        command.extend(["--work-item", work_item])

    env = os.environ.copy()
    env["SINNIX_AGENT_JOB_STATE_DIR"] = str(root)
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
    except OSError as exc:
        raise ToolError(f"failed to launch native {backend} job: {exc}") from exc

    for _ in range(10):
        if manifest.exists():
            break
        if process.poll() is not None:
            break
        time.sleep(0.05)

    return json_text(
        {
            "job_id": job_id,
            "backend": backend,
            "workdir": str(workdir),
            "launcher_pid": process.pid,
            "accepted": True,
        }
    )


def list_agent_jobs(arguments: Any) -> dict[str, Any]:
    require_object(arguments)
    return json_text(run_control("list"))


def agent_job_status(arguments: Any) -> dict[str, Any]:
    a = require_object(arguments)
    return json_text(run_control("status", "--job", require_job_id(a)))


def interrupt_agent_job(arguments: Any) -> dict[str, Any]:
    a = require_object(arguments)
    job_id = require_job_id(a)
    run_control("interrupt", "--job", job_id)
    return json_text({"job_id": job_id, "interrupted": True})


def read_agent_job_output(arguments: Any) -> dict[str, Any]:
    a = require_object(arguments)
    job_id = require_job_id(a)
    artifact = a.get("artifact", "log")
    if artifact not in {"log", "final", "json"}:
        raise ToolError("artifact must be one of: log, final, json")
    max_chars = a.get("max_chars", DEFAULT_OUTPUT_CHARS)
    if not isinstance(max_chars, int) or not 1 <= max_chars <= MAX_OUTPUT_CHARS:
        raise ToolError(f"max_chars must be an integer from 1 to {MAX_OUTPUT_CHARS}")
    path = safe_artifact(load_manifest(job_id), artifact)
    content = path.read_text(errors="replace")
    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars]
    return json_text(
        {
            "job_id": job_id,
            "artifact": artifact,
            "path": str(path),
            "content": content,
            "truncated": truncated,
        }
    )


TOOLS = [
    {
        "name": "start_agent_job",
        "description": "Launch an attested native Claude, Codex, or Gemini coding job asynchronously.",
        "inputSchema": {
            "type": "object",
            "required": ["backend", "workdir", "prompt"],
            "properties": {
                "backend": {"type": "string", "enum": ["claude", "codex", "gemini"]},
                "workdir": {"type": "string"},
                "prompt": {"type": "string"},
                "model": {"type": "string"},
                "reasoning_effort": {"type": "string"},
                "job_role": {"type": "string"},
                "work_item": {"type": "string"},
                "job_id": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "list_agent_jobs",
        "description": "List attested native-agent jobs and their current scope state.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "agent_job_status",
        "description": "Read the attested manifest and live scope state for one native-agent job.",
        "inputSchema": {
            "type": "object",
            "required": ["job_id"],
            "properties": {"job_id": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "read_agent_job_output",
        "description": "Read a bounded log, final answer, or JSON artifact from an attested native-agent job.",
        "inputSchema": {
            "type": "object",
            "required": ["job_id"],
            "properties": {
                "job_id": {"type": "string"},
                "artifact": {"type": "string", "enum": ["log", "final", "json"]},
                "max_chars": {"type": "integer", "minimum": 1, "maximum": MAX_OUTPUT_CHARS},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "interrupt_agent_job",
        "description": "Interrupt a live attested native-agent job by stable job ID only.",
        "inputSchema": {
            "type": "object",
            "required": ["job_id"],
            "properties": {"job_id": {"type": "string"}},
            "additionalProperties": False,
        },
    },
]


def ok(message_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    message_id = message.get("id")
    method = message.get("method")
    try:
        if method == "initialize":
            return ok(
                message_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "sinnix-agent-control", "version": VERSION},
                },
            )
        if method == "notifications/initialized":
            return None
        if method == "ping":
            return ok(message_id, {})
        if method == "tools/list":
            return ok(message_id, {"tools": TOOLS})
        if method == "tools/call":
            params = message.get("params") or {}
            if not isinstance(params, dict):
                raise ToolError("tools/call params must be an object")
            name = params.get("name")
            if not isinstance(name, str):
                raise ToolError("tools/call name must be a string")
            functions = {
                "start_agent_job": start_agent_job,
                "list_agent_jobs": list_agent_jobs,
                "agent_job_status": agent_job_status,
                "read_agent_job_output": read_agent_job_output,
                "interrupt_agent_job": interrupt_agent_job,
            }
            function = functions.get(name)
            if function is None:
                return error(message_id, -32602, f"unknown tool: {name}")
            return ok(message_id, function(params.get("arguments") or {}))
        return error(message_id, -32601, f"method not found: {method}")
    except ToolError as exc:
        return error(message_id, -32000, str(exc))
    except Exception as exc:  # Preserve actionable context without terminating the server.
        return error(message_id, -32603, f"internal agent-control error: {exc}")


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("JSON-RPC message must be an object")
            response = handle(message)
        except (json.JSONDecodeError, ValueError) as exc:
            response = error(None, -32700, str(exc))
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
