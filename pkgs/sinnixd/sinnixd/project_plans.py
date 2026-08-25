"""Generic bounded execution plans over declared project operations.

This module deliberately knows only about project operation descriptors and
dependency graphs.  A project may use the node payload contract for any
domain, but Sinnixd never interprets that payload or its result.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Mapping, Sequence
from uuid import uuid4

from .jobs import GenericJobs, JobRecordError, JobResultError, MAX_RESULT_BYTES
from .projects import ProjectAdapter, ProjectCatalog, RegisteredCheckout

MAX_PLAN_NODES = 256
MAX_PLAN_DEPENDENCIES = 1_024
MAX_PLAN_ID_BYTES = 64
MAX_INPUT_GENERATION_BYTES = 256
MAX_PLAN_RESULT_BYTES = 64_000
MAX_NODE_PAYLOAD_BYTES = 64_000
MAX_PLAN_LIST = 100
_PLAN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_GENERATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:+@=-]{0,255}\Z")


class ProjectPlanError(ValueError):
    """Raised when a plan is malformed or cannot be safely resumed."""


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def _safe_text(value: Any, field: str, pattern: re.Pattern[str], limit: int) -> str:
    if not isinstance(value, str) or not value or len(value.encode()) > limit:
        raise ProjectPlanError(f"{field} must be a bounded non-empty string")
    if pattern.fullmatch(value) is None:
        raise ProjectPlanError(f"{field} contains unsupported characters")
    return value


@dataclass
class PlanStore:
    """Small atomic manifest store.  Node jobs and their artifacts remain job-owned."""

    root: Path
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    @property
    def plans_root(self) -> Path:
        return self.root / "plans"

    def save(self, value: Mapping[str, Any]) -> None:
        plan_id = value.get("plan_id")
        if not isinstance(plan_id, str) or _PLAN_ID.fullmatch(plan_id) is None:
            raise ProjectPlanError("plan ID is invalid")
        self.plans_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.plans_root / f"{plan_id}.json"
        temporary = path.with_suffix(".json.tmp")
        with self._lock:
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(value, handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            descriptor = os.open(self.plans_root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def load(self, plan_id: str) -> dict[str, Any]:
        plan_id = _safe_text(plan_id, "plan_id", _PLAN_ID, MAX_PLAN_ID_BYTES)
        try:
            value = json.loads((self.plans_root / f"{plan_id}.json").read_text())
        except (FileNotFoundError, OSError, json.JSONDecodeError) as error:
            raise ProjectPlanError(f"unknown plan: {plan_id}") from error
        self.validate_record(value)
        return dict(value)

    def list(self) -> list[dict[str, Any]]:
        if not self.plans_root.exists():
            return []
        records: list[dict[str, Any]] = []
        for path in sorted(self.plans_root.glob("*.json")):
            try:
                value = json.loads(path.read_text())
                self.validate_record(value)
            except (OSError, json.JSONDecodeError, ProjectPlanError):
                continue
            records.append(dict(value))
        return records

    @staticmethod
    def validate_record(value: Any) -> None:
        if not isinstance(value, Mapping):
            raise ProjectPlanError("plan record is invalid")
        required = {
            "schema_version",
            "plan_id",
            "project_id",
            "project_digest",
            "checkout",
            "input_generation",
            "plan_digest",
            "nodes",
            "created_at",
            "state",
        }
        if set(value) != required or value.get("schema_version") != 1:
            raise ProjectPlanError("plan record schema is invalid")
        _safe_text(value.get("plan_id"), "plan_id", _PLAN_ID, MAX_PLAN_ID_BYTES)
        _safe_text(value.get("project_id"), "project_id", _PLAN_ID, 128)
        if (
            re.fullmatch(r"sha256:[0-9a-f]{64}", str(value.get("project_digest")))
            is None
        ):
            raise ProjectPlanError("project_digest is invalid")
        _safe_text(
            value.get("input_generation"),
            "input_generation",
            _GENERATION,
            MAX_INPUT_GENERATION_BYTES,
        )
        if re.fullmatch(r"[0-9a-f]{64}", str(value.get("plan_digest"))) is None:
            raise ProjectPlanError("plan_digest is invalid")
        if (
            not isinstance(value.get("checkout"), Mapping)
            or not isinstance(value.get("plan_digest"), str)
            or not isinstance(value.get("created_at"), str)
            or not isinstance(value.get("state"), Mapping)
            or not isinstance(value.get("nodes"), list)
            or not 1 <= len(value["nodes"]) <= MAX_PLAN_NODES
        ):
            raise ProjectPlanError("plan record fields are invalid")
        if set(value["checkout"]) != {
            "project_id",
            "project_path",
            "checkout_id",
            "path",
            "git_common_dir",
            "head",
        } or any(
            not isinstance(item, str) or not item for item in value["checkout"].values()
        ):
            raise ProjectPlanError("plan checkout identity is invalid")
        for node in value["nodes"]:
            if not isinstance(node, Mapping) or set(node) != {
                "node_id",
                "operation",
                "dependencies",
                "parameter_digest",
                "input_generation",
                "job_id",
                "reused",
            }:
                raise ProjectPlanError("plan node record is invalid")
            _safe_text(node.get("node_id"), "node_id", _PLAN_ID, 128)
            _safe_text(node.get("operation"), "operation", _PLAN_ID, 128)
            _safe_text(
                node.get("input_generation"),
                "node input_generation",
                _GENERATION,
                MAX_INPUT_GENERATION_BYTES,
            )
            if (
                not isinstance(node.get("dependencies"), list)
                or any(
                    not isinstance(item, str) or _PLAN_ID.fullmatch(item) is None
                    for item in node["dependencies"]
                )
                or not isinstance(node.get("parameter_digest"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", node["parameter_digest"])
                or (
                    node.get("job_id") is not None
                    and not isinstance(node["job_id"], str)
                )
                or not isinstance(node.get("reused"), bool)
            ):
                raise ProjectPlanError("plan node fields are invalid")


@dataclass
class ProjectPlanExecutor:
    projects: ProjectCatalog
    jobs: GenericJobs
    store: PlanStore
    workspaces: Any
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def submit(
        self,
        arguments: Mapping[str, Any],
        *,
        correlation_id: str,
        principal: str,
    ) -> dict[str, Any]:
        if principal not in {"operator", "agent-control"}:
            raise ProjectPlanError(
                "project plans require agent-control or operator principal"
            )
        normalized = self._validate_submission(arguments)
        project = self.projects.get(normalized["project_id"])
        checkout = self._checkout(project, normalized)
        nodes = self._normalize_nodes(project, normalized)
        self._validate_graph(nodes)
        plan_id = str(uuid4())
        plan_digest = _digest(
            {
                "project_id": project.project_id,
                "checkout": checkout.to_dict(),
                "input_generation": normalized["input_generation"],
                "nodes": nodes,
            }
        )
        record = {
            "schema_version": 1,
            "plan_id": plan_id,
            "project_id": project.project_id,
            "project_digest": project.digest,
            "checkout": checkout.to_dict(),
            "input_generation": normalized["input_generation"],
            "plan_digest": plan_digest,
            "nodes": [
                {
                    "node_id": node["node_id"],
                    "operation": node["operation"],
                    "dependencies": list(node["dependencies"]),
                    "parameter_digest": node["parameter_digest"],
                    "input_generation": node["input_generation"],
                    "job_id": None,
                    "reused": False,
                }
                for node in nodes
            ],
            "created_at": _timestamp(),
            "state": {"phase": "submitting", "terminal": False},
        }
        with self._lock:
            self.store.save(record)
            self._materialize(
                project, checkout, record, nodes, correlation_id, principal
            )
            return self._public(record)

    def get(self, plan_id: str) -> dict[str, Any]:
        with self._lock:
            record = self.store.load(plan_id)
            self._reconcile(record)
            return self._public(record)

    def wait(self, plan_id: str, timeout_seconds: int = 30) -> dict[str, Any]:
        if (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or not 1 <= timeout_seconds <= 300
        ):
            raise ProjectPlanError(
                "plan wait timeout_seconds must be between 1 and 300"
            )
        deadline = time.monotonic() + timeout_seconds
        while True:
            result = self.get(plan_id)
            if result["state"]["terminal"] or time.monotonic() >= deadline:
                if not result["state"]["terminal"]:
                    result["wait_timed_out"] = True
                return result
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))

    def result(
        self, plan_id: str, *, max_bytes: int = MAX_PLAN_RESULT_BYTES
    ) -> dict[str, Any]:
        if (
            not isinstance(max_bytes, int)
            or isinstance(max_bytes, bool)
            or not 1 <= max_bytes <= MAX_PLAN_RESULT_BYTES
        ):
            raise ProjectPlanError(
                f"plan result max_bytes must be between 1 and {MAX_PLAN_RESULT_BYTES}"
            )
        response = self.get(plan_id)
        encoded = json.dumps(
            response["result"], sort_keys=True, separators=(",", ":")
        ).encode()
        if len(encoded) > max_bytes:
            raise ProjectPlanError(
                "aggregate plan result exceeds the requested response limit"
            )
        return {"plan_id": plan_id, "kind": "project-plan", "value": response["result"]}

    def list(self, *, project_id: str | None = None) -> dict[str, Any]:
        records = self.store.list()
        if project_id is not None:
            project_id = _safe_text(project_id, "project_id", _PLAN_ID, 128)
            records = [
                record for record in records if record["project_id"] == project_id
            ]
        records.sort(
            key=lambda item: (item["created_at"], item["plan_id"]), reverse=True
        )
        return {
            "plans": [
                {
                    "plan_id": record["plan_id"],
                    "project_id": record["project_id"],
                    "input_generation": record["input_generation"],
                    "node_count": len(record["nodes"]),
                    "created_at": record["created_at"],
                    "state": dict(record["state"]),
                }
                for record in records[:MAX_PLAN_LIST]
            ],
            "total": len(records),
            "truncated": len(records) > MAX_PLAN_LIST,
        }

    def _validate_submission(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {
            "project_id",
            "workspace_id",
            "checkout_id",
            "input_generation",
            "generation",
            "nodes",
            "payloads",
            "node_operation",
            "operation",
        }
        if set(arguments) - allowed:
            raise ProjectPlanError("plan.submit received unknown fields")
        project_id = _safe_text(
            arguments.get("project_id"), "project_id", _PLAN_ID, 128
        )
        generation = arguments.get("input_generation", arguments.get("generation"))
        generation = _safe_text(
            generation, "input_generation", _GENERATION, MAX_INPUT_GENERATION_BYTES
        )
        if "input_generation" in arguments and "generation" in arguments:
            raise ProjectPlanError("plan submission accepts one input_generation field")
        workspace_id = arguments.get("workspace_id")
        checkout_id = arguments.get("checkout_id")
        if workspace_id is not None and checkout_id is not None:
            raise ProjectPlanError(
                "plan submission accepts workspace_id or checkout_id, not both"
            )
        if workspace_id is not None:
            workspace_id = _safe_text(workspace_id, "workspace_id", _PLAN_ID, 128)
        if checkout_id is not None:
            checkout_id = _safe_text(checkout_id, "checkout_id", _PLAN_ID, 128)
        if "nodes" in arguments and "payloads" in arguments:
            raise ProjectPlanError(
                "plan submission accepts nodes or payloads, not both"
            )
        nodes = arguments.get("nodes", arguments.get("payloads"))
        if nodes is None:
            raise ProjectPlanError("plan submission requires nodes")
        node_operation = arguments.get("node_operation", arguments.get("operation"))
        if "node_operation" in arguments and "operation" in arguments:
            raise ProjectPlanError("plan submission accepts one node_operation field")
        if node_operation is not None:
            node_operation = _safe_text(node_operation, "node_operation", _PLAN_ID, 128)
        return {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "checkout_id": checkout_id,
            "input_generation": generation,
            "nodes": nodes,
            "node_operation": node_operation,
        }

    def _checkout(
        self, project: ProjectAdapter, arguments: Mapping[str, Any]
    ) -> RegisteredCheckout:
        if arguments["workspace_id"] is not None:
            return self.workspaces.resolve_checkout(
                project.project_id, arguments["workspace_id"]
            )
        return self.projects.checkout(
            project.project_id, arguments["checkout_id"] or "default"
        )

    def _normalize_nodes(
        self, project: ProjectAdapter, arguments: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        raw_nodes = arguments["nodes"]
        if not isinstance(raw_nodes, list) or not 1 <= len(raw_nodes) <= MAX_PLAN_NODES:
            raise ProjectPlanError(
                f"plan nodes must contain 1-{MAX_PLAN_NODES} entries"
            )
        node_operation = arguments["node_operation"]
        if node_operation is not None:
            operation = project.operation(node_operation)
            if not operation.plan_node:
                raise ProjectPlanError(
                    f"operation {node_operation!r} is not declared as a plan node"
                )
        normalized: list[dict[str, Any]] = []
        ids: set[str] = set()
        total_dependencies = 0
        for index, raw in enumerate(raw_nodes):
            if not isinstance(raw, Mapping):
                raise ProjectPlanError(f"plan node {index} must be an object")
            allowed_node_fields = {
                "node_id",
                "id",
                "depends_on",
                "dependencies",
                "payload",
                "parameters",
                "input_generation",
            }
            if node_operation is None:
                allowed_node_fields |= {"operation"}
            if set(raw) - allowed_node_fields:
                raise ProjectPlanError(f"plan node {index} contains unknown fields")
            node_id = raw.get("node_id", raw.get("id"))
            node_id = _safe_text(node_id, f"nodes[{index}].node_id", _PLAN_ID, 128)
            if node_id in ids:
                raise ProjectPlanError(f"plan node ID is duplicated: {node_id}")
            ids.add(node_id)
            dependencies = raw.get("depends_on", raw.get("dependencies", []))
            if "depends_on" in raw and "dependencies" in raw:
                raise ProjectPlanError(
                    f"plan node {node_id} declares dependencies twice"
                )
            if (
                not isinstance(dependencies, list)
                or any(
                    not isinstance(item, str) or _PLAN_ID.fullmatch(item) is None
                    for item in dependencies
                )
                or len(set(dependencies)) != len(dependencies)
            ):
                raise ProjectPlanError(f"plan node {node_id} dependencies are invalid")
            total_dependencies += len(dependencies)
            if total_dependencies > MAX_PLAN_DEPENDENCIES:
                raise ProjectPlanError("plan dependency count exceeds its bound")
            if node_operation is None:
                operation_name = raw.get("operation")
                operation_name = _safe_text(
                    operation_name, f"nodes[{index}].operation", _PLAN_ID, 128
                )
            else:
                operation_name = node_operation
            operation = project.operation(operation_name)
            payload = raw.get("payload", raw.get("parameters", {}))
            if "payload" in raw and "parameters" in raw:
                raise ProjectPlanError(f"plan node {node_id} declares payload twice")
            if not isinstance(payload, Mapping):
                raise ProjectPlanError(f"plan node {node_id} payload must be an object")
            try:
                payload_bytes = json.dumps(
                    payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode()
            except (TypeError, ValueError) as error:
                raise ProjectPlanError(
                    f"plan node {node_id} payload is not JSON serializable"
                ) from error
            if len(payload_bytes) > MAX_NODE_PAYLOAD_BYTES:
                raise ProjectPlanError(f"plan node {node_id} payload exceeds its bound")
            try:
                _, parameter_digest = operation.derive_argv(payload)
            except ValueError as error:
                raise ProjectPlanError(f"plan node {node_id}: {error}") from error
            node_generation = raw.get("input_generation", arguments["input_generation"])
            node_generation = _safe_text(
                node_generation,
                f"nodes[{index}].input_generation",
                _GENERATION,
                MAX_INPUT_GENERATION_BYTES,
            )
            normalized.append(
                {
                    "node_id": node_id,
                    "operation": operation_name,
                    "dependencies": list(dependencies),
                    "parameter_digest": parameter_digest,
                    "input_generation": node_generation,
                    "payload": dict(payload),
                }
            )
        return normalized

    @staticmethod
    def _validate_graph(nodes: Sequence[Mapping[str, Any]]) -> None:
        ids = {node["node_id"] for node in nodes}
        indegree = {node_id: 0 for node_id in ids}
        children = {node_id: [] for node_id in ids}
        for node in nodes:
            for dependency in node["dependencies"]:
                if dependency not in ids:
                    raise ProjectPlanError(
                        f"plan dependency is undeclared: {dependency}"
                    )
                indegree[node["node_id"]] += 1
                children[dependency].append(node["node_id"])
        ready = [node_id for node_id, count in indegree.items() if count == 0]
        visited = 0
        while ready:
            current = ready.pop()
            visited += 1
            for child in children[current]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
        if visited != len(nodes):
            raise ProjectPlanError("plan dependency graph contains a cycle")

    def _materialize(
        self,
        project: ProjectAdapter,
        checkout: RegisteredCheckout,
        record: dict[str, Any],
        nodes: Sequence[Mapping[str, Any]],
        correlation_id: str,
        principal: str,
    ) -> None:
        self._materialize_missing(
            project, checkout, record, nodes, correlation_id, principal
        )

    def _materialize_missing(
        self,
        project: ProjectAdapter,
        checkout: RegisteredCheckout,
        record: dict[str, Any],
        nodes: Sequence[Mapping[str, Any]],
        correlation_id: str,
        principal: str,
    ) -> None:
        manifest_by_id = {node["node_id"]: node for node in record["nodes"]}
        pending = {node["node_id"]: node for node in nodes}
        while pending:
            ready = [
                node
                for node in pending.values()
                if all(
                    isinstance(manifest_by_id[dependency]["job_id"], str)
                    for dependency in node["dependencies"]
                )
            ]
            if not ready:
                raise ProjectPlanError("validated plan has no materializable node")
            for node in sorted(ready, key=lambda item: item["node_id"]):
                manifest = manifest_by_id[node["node_id"]]
                if manifest["job_id"] is None:
                    reusable = self._reusable_job(record, manifest)
                    if reusable is not None:
                        manifest["job_id"] = reusable
                        manifest["reused"] = True
                    else:
                        dependency_ids = tuple(
                            manifest_by_id[dependency]["job_id"]
                            for dependency in node["dependencies"]
                        )
                        response = self.jobs.start_declared(
                            project=project,
                            operation=project.operation(node["operation"]),
                            correlation_id=correlation_id,
                            parameters=node["payload"],
                            checkout=checkout,
                            principal=principal,
                            contract={
                                "plan": {
                                    "plan_id": record["plan_id"],
                                    "node_id": node["node_id"],
                                    "input_generation": node["input_generation"],
                                    "project_digest": project.digest,
                                }
                            },
                            dependency_job_ids=dependency_ids,
                            input_generation=node["input_generation"],
                            plan_node=True,
                        )
                        manifest["job_id"] = response["job_id"]
                    self.store.save(record)
                pending.pop(node["node_id"])
        self._reconcile(record)

    def _reconcile(self, record: dict[str, Any]) -> None:
        if any(node["job_id"] is None for node in record["nodes"]):
            for manifest in record["nodes"]:
                if manifest["job_id"] is None:
                    manifest["job_id"] = self._recover_job_for_node(record, manifest)
            self.store.save(record)
        if any(node["job_id"] is None for node in record["nodes"]):
            # A crash before the node job was durably created leaves no
            # executable payload in the public manifest.  Keep the plan
            # inspectable and retryable by submitting the exact plan again.
            record["state"] = {
                "phase": "interrupted",
                "terminal": False,
                "error": "node job was not durably created",
                "updated_at": _timestamp(),
            }
            self.store.save(record)
            return
        states = []
        for manifest in record["nodes"]:
            try:
                job = self.jobs.get(manifest["job_id"])
            except JobRecordError:
                job = {"state": {"phase": "missing", "terminal": True}}
            states.append((manifest, job))
        phases = [job["state"].get("phase") for _, job in states]
        if all(phase == "succeeded" for phase in phases):
            phase, terminal = "succeeded", True
        elif any(
            phase
            in {
                "failed",
                "timed_out",
                "cancelled",
                "missing",
                "dependency-failed",
                "launch-failed",
            }
            for phase in phases
        ):
            phase, terminal = "failed", True
        else:
            phase, terminal = "running", False
        record["state"] = {
            "phase": phase,
            "terminal": terminal,
            "updated_at": _timestamp(),
        }
        self.store.save(record)

    def _recover_job_for_node(
        self, record: Mapping[str, Any], node: Mapping[str, Any]
    ) -> str | None:
        for job in self.jobs.store.list():
            contract = job.spec.contract.get("plan")
            if (
                not isinstance(contract, Mapping)
                or contract.get("plan_id") != record["plan_id"]
                or contract.get("node_id") != node["node_id"]
                or contract.get("project_digest") != record["project_digest"]
                or job.spec.project_id != record["project_id"]
                or dict(job.spec.checkout or {}) != dict(record["checkout"])
                or job.spec.operation != node["operation"]
                or job.spec.parameter_digest != node["parameter_digest"]
                or job.spec.input_generation != node["input_generation"]
            ):
                continue
            return job.job_id
        return None

    def _reusable_job(
        self, record: Mapping[str, Any], node: Mapping[str, Any]
    ) -> str | None:
        for prior in self.store.list():
            if (
                prior["plan_id"] == record["plan_id"]
                or prior["project_id"] != record["project_id"]
                or prior["project_digest"] != record["project_digest"]
            ):
                continue
            if prior["checkout"] != record["checkout"]:
                continue
            for prior_node in prior["nodes"]:
                if (
                    prior_node["node_id"] != node["node_id"]
                    or prior_node["operation"] != node["operation"]
                    or prior_node["dependencies"] != node["dependencies"]
                    or prior_node["parameter_digest"] != node["parameter_digest"]
                    or prior_node["input_generation"] != node["input_generation"]
                    or not isinstance(prior_node["job_id"], str)
                ):
                    continue
                try:
                    job = self.jobs.store.load(prior_node["job_id"])
                    if (
                        job.spec.project_id != record["project_id"]
                        or job.spec.operation != node["operation"]
                        or job.spec.parameter_digest != node["parameter_digest"]
                        or job.spec.input_generation != node["input_generation"]
                        or not isinstance(job.spec.contract.get("plan"), Mapping)
                        or job.spec.contract["plan"].get("project_digest")
                        != record["project_digest"]
                        or dict(job.spec.checkout or {}) != dict(record["checkout"])
                        or job.state.get("phase") != "succeeded"
                        or not job.state.get("terminal")
                        or not self.jobs._has_authoritative_result(job)
                    ):
                        continue
                    self.jobs.result(job.job_id, max_bytes=MAX_RESULT_BYTES)
                except (JobRecordError, JobResultError):
                    continue
                return prior_node["job_id"]
        return None

    def _public(self, record: Mapping[str, Any]) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        for manifest in record["nodes"]:
            job = None
            if isinstance(manifest["job_id"], str):
                try:
                    job = self.jobs.get(manifest["job_id"])
                except JobRecordError:
                    job = {"state": {"phase": "missing", "terminal": True}}
            state = (
                dict(job["state"])
                if job is not None
                else {"phase": "pending", "terminal": False}
            )
            result: dict[str, Any] | None = None
            if state.get("phase") == "succeeded" and isinstance(
                manifest["job_id"], str
            ):
                try:
                    result = self.jobs.result(
                        manifest["job_id"], max_bytes=MAX_RESULT_BYTES
                    )
                except JobResultError:
                    result = {
                        "job_id": manifest["job_id"],
                        "artifact": f"sinnix://jobs/{manifest['job_id']}/artifacts/result",
                    }
            nodes.append(
                {
                    "node_id": manifest["node_id"],
                    "operation": manifest["operation"],
                    "dependencies": list(manifest["dependencies"]),
                    "job_id": manifest["job_id"],
                    "dependency_job_ids": list(
                        state.get("dependencies", [])
                        if isinstance(state.get("dependencies", []), list)
                        else []
                    ),
                    "parameter_digest": manifest["parameter_digest"],
                    "input_generation": manifest["input_generation"],
                    "reused": manifest["reused"],
                    "state": state,
                    "result": result,
                }
            )
        aggregate = {
            "plan_id": record["plan_id"],
            "project_id": record["project_id"],
            "input_generation": record["input_generation"],
            "node_count": len(nodes),
            "state": dict(record["state"]),
            "nodes": nodes,
        }
        self._bound_aggregate(aggregate)
        return {
            "plan_id": record["plan_id"],
            "project_id": record["project_id"],
            "checkout": dict(record["checkout"]),
            "input_generation": record["input_generation"],
            "node_count": len(nodes),
            "state": dict(record["state"]),
            "nodes": aggregate["nodes"],
            "result": aggregate,
        }

    @staticmethod
    def _bound_aggregate(aggregate: dict[str, Any]) -> None:
        encoded = json.dumps(aggregate, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded) <= MAX_PLAN_RESULT_BYTES:
            return
        for node in aggregate["nodes"]:
            result = node.get("result")
            if isinstance(result, Mapping):
                node["result"] = {
                    "job_id": node["job_id"],
                    "artifact": f"sinnix://jobs/{node['job_id']}/artifacts/result",
                    "bounded": False,
                }
        if (
            len(json.dumps(aggregate, sort_keys=True, separators=(",", ":")).encode())
            <= MAX_PLAN_RESULT_BYTES
        ):
            return
        aggregate["nodes"] = [
            {
                "node_id": node["node_id"],
                "job_id": node["job_id"],
                "state": {
                    "phase": node["state"].get("phase"),
                    "terminal": node["state"].get("terminal"),
                },
                "reused": node["reused"],
            }
            for node in aggregate["nodes"]
        ]
        if (
            len(json.dumps(aggregate, sort_keys=True, separators=(",", ":")).encode())
            > MAX_PLAN_RESULT_BYTES
        ):
            aggregate["nodes"] = []
            aggregate["truncated"] = True
