"""Bounded observation of AgentCTL's current queue projection.

Pueue owns the queue. AgentCTL reduces its one full status read before this
observer sees it, so this source neither reads retired job records nor joins
current jobs to historical transcript search.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

MAX_RESPONSE_BYTES = 1_048_576


def _snapshot(limit: int) -> dict[str, Any]:
    command = os.environ.get("AGENTCTL_EXECUTABLE", "agentctl")
    try:
        result = subprocess.run(
            [command, "--json", "job", "snapshot", "--limit", str(limit)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"agentctl unavailable: {type(error).__name__}") from error
    if result.returncode != 0:
        raise RuntimeError("agentctl rejected the job snapshot request")
    if len(result.stdout.encode()) > MAX_RESPONSE_BYTES:
        raise RuntimeError("agentctl job snapshot exceeds the protocol bound")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("agentctl job snapshot is malformed") from error
    if (
        not isinstance(value, dict)
        or value.get("schema") != "sinnix.agentctl.job-snapshot.v1"
        or not isinstance(value.get("groups"), dict)
        or not isinstance(value.get("jobs"), list)
        or not isinstance(value.get("omitted"), dict)
        or not isinstance(value.get("coverage"), dict)
        or any(not isinstance(job, dict) for job in value["jobs"])
    ):
        raise RuntimeError("agentctl job snapshot has an invalid shape")
    return value


def collect_agent_gateway(
    limit: int = 20, below: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Read the owner projection. `below` remains caller-compatible input."""
    _ = below
    bounded_limit = max(1, min(limit, 100))
    try:
        snapshot = _snapshot(bounded_limit)
    except RuntimeError as error:
        return {
            "schema": "sinnix-observe-agentctl-v2",
            "available": False,
            "groups": {},
            "jobs": [],
            "omitted": {"total": 0, "active": 0, "terminal": 0},
            "coverage": {},
            "error": str(error),
        }
    return {
        "schema": "sinnix-observe-agentctl-v2",
        "available": True,
        "groups": snapshot["groups"],
        "jobs": snapshot["jobs"],
        "omitted": snapshot["omitted"],
        "coverage": snapshot["coverage"],
        "error": None,
    }
