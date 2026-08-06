from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any

from .capabilities import Capability, Principal
from .config import GatewayConfig


class ObserveService:
    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal

    def machine_report(self) -> dict[str, Any]:
        self.principal.require(Capability.MACHINE_READ)
        environment = {
            "HOME": os.environ.get("HOME", "/home/sinity"),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PATH": os.environ.get("PATH", "/run/current-system/sw/bin"),
            "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000"),
        }
        try:
            with tempfile.TemporaryFile() as output:
                result = subprocess.run(
                    [self.config.observe_command, "--format", "json", "--limit", "20"],
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    timeout=20,
                    check=False,
                    env=environment,
                )
                output.seek(0)
                data = output.read(self.config.max_result_bytes + 1)
        except subprocess.TimeoutExpired:
            return {
                "available": False,
                "failure_class": "collector_timeout",
                "reason": "sinnix-observe timed out",
            }
        if result.returncode != 0:
            return {
                "available": False,
                "failure_class": "collector_failed",
                "reason": "sinnix-observe failed",
            }
        if len(data) > self.config.max_result_bytes:
            return {
                "available": False,
                "failure_class": "response_bound",
                "reason": "sinnix-observe exceeded response bound",
            }
        try:
            return {"available": True, "report": json.loads(data)}
        except json.JSONDecodeError:
            return {
                "available": False,
                "failure_class": "malformed_report",
                "reason": "sinnix-observe returned malformed JSON",
            }

    def gateway_status(
        self, profile: str, capability_contract_hash: str
    ) -> dict[str, Any]:
        self.principal.require(Capability.MACHINE_READ)
        inventory_available = self.config.runtime_inventory.is_file()
        return {
            "status": "ready",
            "profile": profile,
            "capability_contract_hash": capability_contract_hash,
            "manifest_hash": (
                self.config.approved_manifest_hash
                if profile == "remote-readonly"
                else None
            ),
            "runtime_inventory": "available" if inventory_available else "unavailable",
            "transport": "stdio",
        }
