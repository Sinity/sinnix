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

    def _connector_snapshot(self) -> dict[str, str] | None:
        path = self.config.connector_snapshot_path or (
            self.config.state_dir / "connector-snapshot.json"
        )
        try:
            snapshot = json.loads(path.read_text())
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError):
            return None
        if (
            snapshot.get("schema") != "sinnix.gateway-connector-snapshot.v1"
            or not isinstance(snapshot.get("principal"), str)
            or not isinstance(snapshot.get("manifest_sha256"), str)
        ):
            return None
        return {
            "principal": snapshot["principal"],
            "manifest_sha256": snapshot["manifest_sha256"],
        }

    @staticmethod
    def _comparison(left: str | None, right: str | None) -> str:
        if left is None or right is None:
            return "unobserved"
        return "match" if left == right else "mismatch"

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
        self,
        principal_name: str,
        capability_contract_hash: str,
        live_manifest_hash: str,
    ) -> dict[str, Any]:
        self.principal.require(Capability.MACHINE_READ)
        inventory_available = self.config.runtime_inventory.is_file()
        approved_hash = (
            self.config.approved_manifest_hash
            if self.config.approved_manifest_principal == principal_name
            else None
        )
        snapshot = self._connector_snapshot()
        observed_hash = (
            snapshot["manifest_sha256"]
            if snapshot is not None and snapshot["principal"] == principal_name
            else None
        )
        return {
            "status": "ready",
            "principal": principal_name,
            "capability_contract_hash": capability_contract_hash,
            "manifests": {
                "live_server": {
                    "principal": principal_name,
                    "sha256": live_manifest_hash,
                },
                "nix_approved": (
                    {
                        "principal": self.config.approved_manifest_principal,
                        "sha256": approved_hash,
                    }
                    if approved_hash is not None
                    else None
                ),
                "chatgpt_observed": (
                    {
                        "principal": principal_name,
                        "sha256": observed_hash,
                    }
                    if observed_hash is not None
                    else None
                ),
                "comparisons": {
                    "live_to_nix_approved": self._comparison(
                        live_manifest_hash, approved_hash
                    ),
                    "live_to_chatgpt_observed": self._comparison(
                        live_manifest_hash, observed_hash
                    ),
                    "nix_approved_to_chatgpt_observed": self._comparison(
                        approved_hash, observed_hash
                    ),
                },
            },
            "runtime_inventory": "available" if inventory_available else "unavailable",
            "transport": "stdio",
        }
