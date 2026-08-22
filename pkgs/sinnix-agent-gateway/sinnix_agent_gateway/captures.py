from __future__ import annotations

import json
from typing import Any

from .capabilities import Capability, Principal
from .config import GatewayConfig
from .execution import ExecutionProfile, OwnerExecution, OwnerRoute


class CaptureService:
    """Per-pipe (per capture-lane) data-permission model over the
    sinnix-capture-v1 envelope lake. Enforcement
    lives in Principal.filter_lanes/require_lane (capabilities.py); this
    service is the mechanical read path, matching ObserveService's
    shell-to-CLI pattern rather than reimplementing envelope parsing here.
    """

    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal
        self.execution = OwnerExecution()

    def _available_lanes(self) -> list[str]:
        root = self.config.captures_root
        if not root.is_dir():
            return []
        return sorted(p.name for p in root.iterdir() if p.is_dir())

    def lanes_visible(self) -> dict[str, Any]:
        """List the capture lanes THIS profile may query -- not every lane
        that exists on disk. A profile probing what it can see is itself a
        read, gated the same as an actual query."""
        self.principal.require(Capability.CAPTURE_READ)
        available = self._available_lanes()
        visible = self.principal.filter_lanes(None, available)
        return {"lanes": visible, "total_lanes_on_disk": len(available)}

    def query(
        self, lanes: list[str] | None = None, since: float = 0.0, limit: int = 100
    ) -> dict[str, Any]:
        available = self._available_lanes()
        effective_lanes = self.principal.filter_lanes(lanes, available)
        if not effective_lanes:
            return {"records": [], "lanes_queried": []}

        cmd = [
            self.config.capture_command,
            "query",
            "--capture-root",
            str(self.config.captures_root),
            "--since",
            str(since),
        ]
        for lane in effective_lanes:
            cmd += ["--lane", lane]

        result = self.execution.run(
            cmd,
            ExecutionProfile(
                route=OwnerRoute("capture-query"),
                timeout_seconds=20,
                max_stdout_bytes=self.config.max_result_bytes * 4,
            ),
        )
        if result.failure_class is not None:
            failure_class = {
                "command_timeout": "collector_timeout",
                "command_unavailable:FileNotFoundError": "collector_unavailable",
            }.get(result.failure_class, "collector_failed")
            return {
                "available": False,
                "failure_class": failure_class,
                "reason": result.stderr_excerpt()
                or (
                    "sinnix-capture query is unavailable"
                    if failure_class == "collector_unavailable"
                    else "sinnix-capture query failed"
                ),
                "command": list(result.command),
            }

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "available": False,
                "failure_class": "unparseable_output",
                "reason": "sinnix-capture query did not return valid JSON",
            }

        records = (
            payload.get("records", payload) if isinstance(payload, dict) else payload
        )
        if isinstance(records, list):
            records = records[: max(0, limit)]

        return {"records": records, "lanes_queried": effective_lanes}
