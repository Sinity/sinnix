from __future__ import annotations

import json
import os
from typing import Any

from .capabilities import Capability, Principal
from .config import GatewayConfig
from .execution import ExecutionProfile, OwnerExecution, OwnerRoute


class ObserveService:
    _ARRAY_OPERATIONS = {
        "units": "systemd_units",
        "workloads": "workload_rows",
        "slices": "resource_slices",
        "blocked_tasks": "blocked_tasks",
    }
    _SECTION_OPERATIONS = {
        "overview": (
            "schema",
            "generated_at",
            "window",
            "live_pressure",
            "config_drift",
            "gaps_summary",
            "storage",
            "sources",
            "below",
        ),
        "pressure": ("live_pressure",),
        "runtime_inventory": ("runtime_inventory",),
        "gateway": ("agent_gateway",),
        "browser": ("chrome_io",),
        "storage": ("storage",),
        "ingestion": ("polylogue_live_attempts", "sinex_xtask_history"),
    }

    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal
        self.execution = OwnerExecution()

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

    def _collector_bound(self) -> int:
        return min(max(self.config.max_result_bytes * 8, 1_048_576), 8_388_608)

    def _collect_report(
        self, operation: str, cursor: int = 0, page_limit: int = 100
    ) -> dict[str, Any]:
        environment = {
            "HOME": os.environ.get("HOME", "/home/sinity"),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PATH": os.environ.get("PATH", "/run/current-system/sw/bin"),
            "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000"),
        }
        result = self.execution.run(
            [
                self.config.observe_command,
                "--format",
                "json",
                "--limit",
                "20",
                "--section",
                operation,
                "--cursor",
                str(cursor),
                "--page-limit",
                str(page_limit),
            ],
            ExecutionProfile(
                route=OwnerRoute("machine-observe"),
                timeout_seconds=20,
                max_stdout_bytes=self._collector_bound(),
                environment=environment,
            ),
        )
        if result.failure_class == "command_timeout":
            return {
                "available": False,
                "failure_class": "collector_timeout",
                "reason": "sinnix-observe timed out",
                "command": list(result.command),
            }
        if result.failure_class == "command_output_bound":
            return {
                "available": False,
                "failure_class": "collector_response_bound",
                "reason": "sinnix-observe exceeded collector bound",
                "command": list(result.command),
            }
        if result.failure_class is not None:
            return {
                "available": False,
                "failure_class": "collector_failed",
                "reason": result.stderr_excerpt() or "sinnix-observe failed",
                "command": list(result.command),
            }
        try:
            return {"available": True, "report": json.loads(result.stdout)}
        except json.JSONDecodeError:
            return {
                "available": False,
                "failure_class": "malformed_report",
                "reason": "sinnix-observe returned malformed JSON",
                "command": list(result.command),
            }

    def _within_response_bound(self, response: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(response, separators=(",", ":")).encode()
        if len(encoded) <= self.config.max_result_bytes:
            return response
        return {
            "available": False,
            "failure_class": "response_bound",
            "reason": "selected machine response exceeded response bound",
        }

    def machine_report(self) -> dict[str, Any]:
        """Return the bounded overview retained for callers of the old route."""
        return self.machine_query("overview")

    def machine_query(
        self, operation: str, cursor: int = 0, limit: int = 100
    ) -> dict[str, Any]:
        self.principal.require(Capability.MACHINE_READ)
        if cursor < 0:
            raise ValueError("cursor must be non-negative")
        if limit < 1 or limit > 500:
            raise ValueError("limit must be 1-500")
        available = self._ARRAY_OPERATIONS | self._SECTION_OPERATIONS
        if operation not in available:
            raise ValueError(
                f"unknown machine operation {operation!r}; available: {sorted(available)}"
            )
        if operation not in self._ARRAY_OPERATIONS and cursor:
            raise ValueError("cursor is only valid for array machine operations")
        if operation in self._ARRAY_OPERATIONS:
            key = self._ARRAY_OPERATIONS[operation]
            page_limit = limit
            while True:
                collected = self._collect_report(operation, cursor, page_limit)
                if not collected["available"]:
                    return collected
                report = collected["report"]
                source = {
                    "schema": report.get("schema"),
                    "generated_at": report.get("generated_at"),
                    "window": report.get("window"),
                }
                page = report.get(key)
                if not isinstance(page, dict):
                    return {
                        "available": False,
                        "failure_class": "malformed_report",
                        "reason": f"sinnix-observe section {key} is not a page",
                    }
                rows = page.get("rows")
                total = page.get("total")
                next_cursor = page.get("next_cursor")
                if (
                    not isinstance(rows, list)
                    or not isinstance(total, int)
                    or not isinstance(page.get("cursor"), int)
                    or page["cursor"] != cursor
                    or (next_cursor is not None and not isinstance(next_cursor, int))
                ):
                    return {
                        "available": False,
                        "failure_class": "malformed_report",
                        "reason": f"sinnix-observe section {key} has an invalid page",
                    }
                response = {
                    "available": True,
                    "operation": operation,
                    "source": source,
                    "total": total,
                    "cursor": cursor,
                    "next_cursor": next_cursor,
                    "rows": rows,
                }
                bounded = self._within_response_bound(response)
                if bounded["available"]:
                    return bounded
                if len(rows) <= 1:
                    return {
                        "available": False,
                        "failure_class": "response_bound",
                        "reason": "one machine row exceeded response bound",
                    }
                page_limit = len(rows) - 1
        collected = self._collect_report(operation)
        if not collected["available"]:
            return collected
        report = collected["report"]
        source = {
            "schema": report.get("schema"),
            "generated_at": report.get("generated_at"),
            "window": report.get("window"),
        }
        keys = self._SECTION_OPERATIONS[operation]
        response = {
            "available": True,
            "operation": operation,
            "source": source,
            "sections": {key: report.get(key) for key in keys},
        }
        return self._within_response_bound(response)

    def gateway_status(
        self,
        principal_name: str,
        capability_contract_hash: str,
        live_manifest_hash: str,
        action_catalog_hash: str,
        catalog_revision: str,
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
            "principal_contract_hash": capability_contract_hash,
            "catalog": {
                "revision": catalog_revision,
                "action_catalog_hash": action_catalog_hash,
            },
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
