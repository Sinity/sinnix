from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping
from uuid import uuid4

import anyio
from mcp.types import CallToolResult, TextContent
from sinnix_mcp import ErrorCode, RequestEnvelope
from sinnix_mcp.execution import ExecutionProfile, OwnerDiagnosticError, OwnerExecution

from .action import Action
from .actions import REVISION as ACTION_REVISION
from .artifacts import ArtifactService
from .audit import AuditService
from .beads import BeadsError, BeadsService
from .browser import BrowserService
from .capabilities import Capability, PolicyError, Principal
from .capability_index import CapabilityIndexService
from .captures import CaptureService
from .config import GatewayConfig
from .contexts import (
    CONTEXT_INTENTS,
    ComponentResult,
    ComponentSpec,
    ContextComposer,
    ContextSnapshotStore,
    source_revision,
)
from .contracts import EffectMode
from .desktop import DesktopService
from .events import EventCursorError, NormalizedEventService
from .execution import LocalJobs
from .files import HostFileService
from .locators import decode_file_ref
from .machine_actions import MachineActionService
from .mcp_broker import McpBrokerService
from .memory import MemoryService
from .observe import ObserveService
from .project_context import ProjectContextService
from .projects import ProjectService
from .redaction import public_error
from .registry import REGISTRY, RegistryError
from .results import ProtocolError, RequestContext, ResultError, ResultService
from .route_preflight import GatewayRoutePreflight
from .schemas import V2ToolEnvelope
from .sessions import SessionLogService
from .terminals import TerminalService
from .timeline import TimelineService
from .waits import BoundedWaitService, WaitEvidence, WaitRequest, WaitTarget

DAEMON_ERROR_CLASSES = {
    ErrorCode.INVALID_ARGUMENT: "invalid_request",
    ErrorCode.STALE_CURSOR: "stale_cursor",
    ErrorCode.POLICY_DENIED: "policy_denied",
    ErrorCode.OWNER_UNAVAILABLE: "unavailable",
    ErrorCode.AUTHORITY_MISMATCH: "policy_denied",
    ErrorCode.RESOURCE_DEFERRED: "unavailable",
    ErrorCode.RESOURCE_EXHAUSTED: "response_bound",
    ErrorCode.OPERATION_FAILED: "owner_failed",
    ErrorCode.RESULT_INVALID: "owner_failed",
}

TOKEN_ESTIMATE_BYTES_PER_TOKEN = 4
MACHINE_OPERATIONS = (
    "interrupt",
    "freeze",
    "thaw",
    "reset_policy",
    "set_policy",
    "park",
    "rebuild_override",
    "restart",
    "start",
    "stop",
)


def _orientation_task_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    """Keep project orientation useful without embedding full Beads bodies."""
    items = result.get("items")
    if not isinstance(items, list):
        return dict(result)
    fields = (
        "id",
        "ref",
        "title",
        "status",
        "priority",
        "issue_type",
        "assignee",
        "labels",
        "parent",
        "task_revision",
        "etag",
    )
    return {
        **result,
        "items": [
            {field: item[field] for field in fields if field in item}
            for item in items
            if isinstance(item, Mapping)
        ],
    }


def canonical_manifest(tools: list[Any]) -> dict[str, Any]:
    rows = [
        tool.model_dump(by_alias=True, exclude_none=True, mode="json") for tool in tools
    ]
    rows.sort(key=lambda row: row["name"])
    payload = {"schema": "sinnix.gateway-tools.v1", "tools": rows}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["sha256"] = hashlib.sha256(encoded).hexdigest()
    return payload


def manifest_measurement(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Measure the canonical manifest without adding a runtime tokenizer dependency."""
    canonical = {
        "schema": manifest.get("schema"),
        "tools": manifest.get("tools"),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    canonical_bytes = len(encoded)
    return {
        "schema": "sinnix.gateway-schema-measurement.v1",
        "canonical_bytes": canonical_bytes,
        "tool_count": len(manifest.get("tools", [])),
        "token_lane": {
            "status": "estimated",
            "method": "canonical_bytes_divided_by_4",
            "estimated_tokens": (canonical_bytes + TOKEN_ESTIMATE_BYTES_PER_TOKEN - 1)
            // TOKEN_ESTIMATE_BYTES_PER_TOKEN,
            "reason": "No tokenizer is a declared gateway runtime dependency.",
        },
    }


def v2_tool_result(envelope: Mapping[str, Any]) -> dict[str, Any] | CallToolResult:
    """Render one validated V2 object as structured MCP content and compatible text."""
    typed = V2ToolEnvelope.model_validate(envelope)
    if typed.result.outcome == "ok":
        return typed.model_dump(mode="json", by_alias=True)
    serialized = typed.model_dump(mode="json", by_alias=True)
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(serialized, sort_keys=True, separators=(",", ":")),
            )
        ],
        structured_content=serialized,
        is_error=True,
    )


@dataclass
class Runtime:
    principal_name: str
    principal: Principal
    config: GatewayConfig
    projects: ProjectService
    project_context: ProjectContextService
    artifacts: ArtifactService
    audit: AuditService
    results: ResultService
    jobs: LocalJobs
    observe: ObserveService
    machine_actions: MachineActionService
    desktop: DesktopService
    terminals: TerminalService
    browser: BrowserService
    beads: BeadsService
    capability_index: CapabilityIndexService
    captures: CaptureService
    files: HostFileService
    sessions: SessionLogService
    memory: MemoryService
    timeline: TimelineService
    mcp_broker: McpBrokerService
    route_preflight: GatewayRoutePreflight
    context_composer: ContextComposer = field(default_factory=ContextComposer)
    normalized_events: NormalizedEventService | None = None
    waits: BoundedWaitService | None = None
    context_snapshots: ContextSnapshotStore | None = None
    tool_manifest: Callable[[], Awaitable[dict[str, Any]]] | None = None

    def principal_contract_hash(self) -> str:
        return _principal_contract(self.principal_name)

    @classmethod
    def create(cls, config: GatewayConfig, principal_name: str) -> "Runtime":
        principal = Principal.for_name(principal_name)
        artifacts = ArtifactService(config, principal)
        sessions = SessionLogService(config, principal)
        projects = ProjectService(config, principal)
        beads = BeadsService(config, principal)
        runtime = cls(
            principal_name=principal_name,
            principal=principal,
            config=config,
            projects=projects,
            project_context=ProjectContextService(principal, projects, beads),
            artifacts=artifacts,
            audit=AuditService(config, principal),
            results=ResultService(config, principal, artifacts),
            jobs=LocalJobs(),
            observe=ObserveService(config, principal, artifacts),
            machine_actions=MachineActionService(config, principal),
            desktop=DesktopService(config, principal, artifacts),
            terminals=TerminalService(config, principal, artifacts),
            browser=BrowserService(config, principal, artifacts),
            beads=beads,
            capability_index=CapabilityIndexService(config, principal),
            captures=CaptureService(config, principal),
            files=HostFileService(config, principal),
            sessions=sessions,
            memory=MemoryService(principal, sessions),
            timeline=TimelineService(principal, sessions),
            mcp_broker=McpBrokerService(config, principal, artifacts),
            route_preflight=GatewayRoutePreflight(config),
        )
        runtime.normalized_events = NormalizedEventService(
            principal=principal_name,
            cursor_key=runtime.results.cursor_key,
            projects=runtime.projects,
            beads=runtime.beads,
            audit=runtime.audit,
            transitions_path=config.runtime_transitions,
            jobs=lambda limit, cursor: runtime._recent_jobs(limit, cursor),
        )
        runtime.context_snapshots = ContextSnapshotStore(
            config.state_dir, principal_name
        )
        runtime.waits = BoundedWaitService(runtime._resolve_wait)
        return runtime

    def owner_revision_observations(self) -> dict[str, str]:
        """Read real owner revisions used by the subscription publisher."""
        observations: dict[str, str] = {}
        for project_id in self.config.projects:
            try:
                summary = self.projects.summary(project_id)
                latest = (
                    summary.get("latest_commit")
                    if isinstance(summary, Mapping)
                    else None
                )
                revision = latest.get("id") if isinstance(latest, Mapping) else None
                if isinstance(revision, str) and revision:
                    observations[
                        REGISTRY.reference("project", {"project_id": project_id})
                    ] = revision
            except Exception:
                continue
            try:
                authority = self.beads.task_authority_status(project_id)
                revision = (
                    authority.get("revision")
                    if isinstance(authority, Mapping)
                    else None
                )
                if isinstance(revision, str) and revision:
                    observations[f"sinnix://projects/{project_id}/task-authority"] = (
                        revision
                    )
            except Exception:
                continue
        return observations

    async def gateway_status(
        self,
        principal_contract_hash: str,
        manifest_hash: str,
        action_catalog_hash: str,
        catalog_revision: str,
    ) -> dict[str, Any]:
        status = self.observe.gateway_status(
            self.principal_name,
            principal_contract_hash,
            manifest_hash,
            action_catalog_hash,
            catalog_revision,
        )
        preflight = self.route_preflight.run()
        if Capability.MCP_READ in self.principal.capabilities:
            broker_catalog = await self.mcp_broker.catalog()
            broker_routes = []
            for server in broker_catalog["servers"]:
                if not server.get("brokered"):
                    continue
                available = server.get("availability") == "available"
                route = {
                    "route": f"mcp.{server['name']}",
                    "status": "pass" if available else "unavailable",
                    "tool_count": server.get("tool_count"),
                    "read_only_tool_count": server.get("read_only_tool_count"),
                }
                if not available:
                    route["failure_class"] = server.get(
                        "failure_class", "upstream_unavailable"
                    )
                broker_routes.append(route)
            preflight["routes"].extend(broker_routes)
            preflight["status"] = (
                "ready"
                if all(route["status"] == "pass" for route in preflight["routes"])
                else "degraded"
            )
        status["route_preflight"] = preflight
        return status

    def project_authority(self, project_id: str) -> dict[str, Any]:
        checkouts = self.projects.checkouts(project_id)["checkouts"]
        for checkout in checkouts:
            checkout["ref"] = REGISTRY.reference(
                "checkout",
                {
                    "project_id": project_id,
                    "checkout_id": checkout["checkout_id"],
                },
            )
        canonical_checkout = next(
            checkout for checkout in checkouts if checkout["checkout_id"] == "default"
        )
        task_authority_ref = REGISTRY.reference(
            "task_authority", {"project_id": project_id}
        )
        try:
            task_authority: dict[str, Any] = {
                "availability": "available",
                "ref": task_authority_ref,
                "status": self.beads.task_authority_status(project_id),
            }
        except BeadsError as exc:
            task_authority = {
                "availability": "unavailable",
                "ref": task_authority_ref,
                "error": public_error(exc),
            }
        code_revision = hashlib.sha256(
            json.dumps(
                {
                    key: canonical_checkout[key]
                    for key in ("head", "branch", "upstream", "dirty_sha256")
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return {
            "project": self.projects.summary(project_id),
            "canonical_checkout_ref": canonical_checkout["ref"],
            "code_revision": code_revision,
            "checkouts": checkouts,
            "task_authority": task_authority,
        }

    def _project_reference(
        self, reference: str, *, allow_checkout: bool
    ) -> tuple[str, str | None, str]:
        if not isinstance(reference, str) or not 1 <= len(reference) <= 2_048:
            raise ProtocolError("invalid_request", "project ref is malformed")
        try:
            resource, values = REGISTRY.resolve(reference)
        except RegistryError as exc:
            raise ProtocolError(
                "not_found", "canonical project resource was not found"
            ) from exc
        allowed = {"project", "checkout"} if allow_checkout else {"project"}
        if resource.kind not in allowed:
            raise ProtocolError(
                "invalid_request", "ref does not identify the required project resource"
            )
        return (
            values["project_id"],
            values.get("checkout_id"),
            str(resource.ref_template.format(values)),
        )

    def _job(
        self,
        operation: str,
        arguments: Mapping[str, Any],
        *,
        principal: str | None = None,
    ) -> dict[str, Any]:
        request = RequestEnvelope(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            operation=operation,
            owner="systemd-jobs",
            principal=principal or self.principal.name,
            arguments=dict(arguments),
        )
        response = self.jobs.dispatch(request)
        if response.owner != "systemd-jobs":
            raise ProtocolError(
                "owner_failed", "job owner response violates its contract"
            )
        if response.error is not None:
            details = response.error.details.inline
            raise ProtocolError(
                DAEMON_ERROR_CLASSES[response.error.code],
                response.error.message,
                details=details if isinstance(details, Mapping) else {},
            )
        if response.payload is None or not isinstance(response.payload.inline, Mapping):
            raise ProtocolError(
                "owner_failed", "job owner response must contain an inline object"
            )
        return dict(response.payload.inline)

    def _bounded_project_context(self, project_id: str) -> dict[str, Any]:
        context = self.project_context.context(project_id)
        authority = self.project_authority(project_id)
        response = {**context, "authority": authority}
        if (
            len(json.dumps(response, sort_keys=True, separators=(",", ":")).encode())
            <= self.config.max_result_bytes
        ):
            return response
        return {
            **context,
            "authority": {
                "availability": "unavailable",
                "reason": "project authority exceeded project context response bound",
                "ref": REGISTRY.reference("project", {"project_id": project_id}),
            },
        }

    def compose_context(self, reference: str, intent: str) -> dict[str, Any]:
        if intent == "project":
            intent = "project.orientation"
        if intent not in CONTEXT_INTENTS:
            raise ProtocolError("invalid_request", f"unknown context intent: {intent}")
        try:
            resource, values = REGISTRY.resolve(reference)
        except RegistryError as exc:
            raise ProtocolError("not_found", "context target is not canonical") from exc
        if intent == "job.review":
            if resource.kind != "job":
                raise ProtocolError(
                    "invalid_request", "job.review requires a job reference"
                )
            project_id = None
        else:
            if resource.kind not in {"project", "checkout"}:
                raise ProtocolError(
                    "invalid_request", f"{intent} requires a project reference"
                )
            project_id = values["project_id"]
        target_ref = str(resource.ref_template.format(values))
        declared = dict(CONTEXT_INTENTS[intent].components)

        def component(
            name: str, fn: Callable[[], Any], source_ref: str | None = None
        ) -> ComponentSpec:
            def probe() -> ComponentResult:
                try:
                    value = fn()
                except ProtocolError as exc:
                    if exc.code in {
                        "invalid_request",
                        "not_found",
                        "policy_denied",
                        "precondition_failed",
                    }:
                        raise
                    return ComponentResult.unavailable(
                        name, public_error(exc), source_ref=source_ref
                    )
                except Exception as exc:
                    return ComponentResult.unavailable(
                        name, public_error(exc), source_ref=source_ref
                    )
                revision = (
                    value.get("source_revision") if isinstance(value, Mapping) else None
                )
                return ComponentResult.available(
                    name,
                    value,
                    revision=revision
                    if isinstance(revision, str)
                    else source_revision(value),
                    source_ref=source_ref,
                )

            return ComponentSpec(name, declared[name], probe)

        project_ref = (
            REGISTRY.reference("project", {"project_id": project_id})
            if project_id
            else None
        )
        components: list[ComponentSpec] = []
        if intent == "project.orientation":
            assert project_id is not None
            components = [
                component(
                    "project", lambda: self.projects.summary(project_id), project_ref
                ),
                component(
                    "checkout",
                    lambda: self.projects.checkout(project_id, "default"),
                    REGISTRY.reference(
                        "checkout", {"project_id": project_id, "checkout_id": "default"}
                    ),
                ),
                component(
                    "tasks",
                    lambda: _orientation_task_summary(
                        self.beads.query(
                            project_ids=[project_id], view="ready", limit=20
                        )
                    ),
                    f"{project_ref}/beads",
                ),
                component(
                    "authority",
                    lambda: self.project_authority(project_id),
                    f"{project_ref}/task-authority",
                ),
            ]
        elif intent == "project.triage":
            assert project_id is not None
            components = [
                component(
                    "project", lambda: self.projects.summary(project_id), project_ref
                ),
                component(
                    "open_beads",
                    lambda: self.beads.query(
                        project_ids=[project_id], view="open", limit=50
                    ),
                    f"{project_ref}/beads",
                ),
                component(
                    "stale_claims",
                    lambda: self.beads.query(
                        project_ids=[project_id], view="stale_claims", limit=50
                    ),
                    f"{project_ref}/beads",
                ),
                component(
                    "changes",
                    lambda: self.projects.diff(project_id, None, None),
                    project_ref,
                ),
            ]
        elif intent == "job.review":
            job_id = values["job_id"]
            job_observation: dict[str, Any] | None = None

            def job_value() -> dict[str, Any]:
                nonlocal job_observation
                if job_observation is None:
                    job_observation = self._job("job.get", {"job_id": job_id})
                return job_observation

            components = [
                component("job", job_value, target_ref),
                component(
                    "result",
                    lambda: self._job(
                        "job.result", {"job_id": job_id, "max_bytes": 64_000}
                    ),
                    target_ref,
                ),
                component(
                    "project",
                    lambda: self.projects.summary(str(job_value().get("project_id"))),
                    project_ref,
                ),
                component("events", lambda: self.audit.tail(50), "sinnix://receipts"),
            ]
        else:
            components = [
                component(
                    "runtime",
                    lambda: self.observe.machine_query("overview"),
                    "sinnix://machine/overview",
                ),
                component(
                    "transitions",
                    lambda: (
                        self.normalized_events.read(limit=50)
                        if self.normalized_events
                        else {"events": []}
                    ),
                    "sinnix://events",
                ),
                component("receipts", lambda: self.audit.tail(50), "sinnix://receipts"),
                component("jobs", lambda: self._recent_jobs(50), "sinnix://jobs"),
            ]
        context = self.context_composer.compose(intent, target_ref, components)
        by_name = {row["name"]: row for row in context["components"]}
        compatibility: dict[str, Any] = {}
        if intent == "project.orientation" and all(
            by_name.get(name, {}).get("status") == "available"
            for name in ("project", "tasks", "authority")
        ):
            compatibility.update(
                {
                    "project": by_name["project"]["data"],
                    "tasks": by_name["tasks"]["data"],
                    "authority": by_name["authority"]["data"],
                }
            )
        elif intent in {"job.review", "incident"}:
            compatibility.update(
                {
                    name: row["data"]
                    for name, row in by_name.items()
                    if row.get("status") == "available" and "data" in row
                }
            )
        if compatibility:
            candidate = {**context, **compatibility}
            if (
                len(
                    json.dumps(
                        candidate, sort_keys=True, separators=(",", ":")
                    ).encode()
                )
                <= context["total_budget_bytes"]
            ):
                context = candidate
        snapshot_body = {
            key: value for key, value in context.items() if key != "snapshot_ref"
        }
        snapshot_body["components"] = [
            {**component, "snapshot_ref": "pending"}
            for component in context["components"]
        ]
        snapshot_ref = f"sinnix://contexts/{source_revision(snapshot_body)}"
        context["snapshot_ref"] = snapshot_ref
        for component in context["components"]:
            component["snapshot_ref"] = snapshot_ref
        if self.context_snapshots is None:
            raise ProtocolError("unavailable", "context snapshot store is unavailable")
        self.context_snapshots.put(context)
        return {"ref": target_ref, **context}

    def v2_run_for_bead(
        self,
        *,
        reference: str | None,
        backend: str | None,
        model: str | None,
        reasoning_effort: str | None,
    ) -> dict[str, Any]:
        """A batch of one worker for one bead: agentctl compiles the packet, creates the worktree, queues the agent."""
        self.principal.require(Capability.JOB_START)
        _resource, values, bead_ref = self._resource_reference(
            reference or "", {"bead"}, "a worker requires a canonical Beads reference"
        )
        for name, value in (
            ("backend", backend),
            ("model", model),
            ("reasoning_effort", reasoning_effort),
        ):
            if value is not None and (
                not isinstance(value, str) or not 1 <= len(value) <= 256
            ):
                raise ProtocolError("invalid_request", f"{name} is malformed")
        result = self._job(
            "job.agent.start",
            {
                "project_id": values["project_id"],
                "bead_id": values["bead_id"],
                "backend": backend,
                "model": model,
                "effort": reasoning_effort,
            },
        )
        job_id = result.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise ProtocolError(
                "owner_failed", "agent.for_bead response omitted the job ID"
            )
        return {
            **result,
            "ref": REGISTRY.reference("job", {"job_id": job_id}),
            "bead_ref": bead_ref,
            "project_ref": REGISTRY.reference(
                "project", {"project_id": values["project_id"]}
            ),
        }

    def v2_events(
        self,
        limit: int,
        cursor: str | None = None,
        project_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 1_000
        ):
            raise ProtocolError("invalid_request", "limit must be 1-1000")
        if self.normalized_events is None:
            raise ProtocolError("unavailable", "normalized event owner is unavailable")
        try:
            result = self.normalized_events.read(
                limit=limit, cursor=cursor, project_ids=project_ids
            )
        except EventCursorError as exc:
            raise ProtocolError("stale_cursor", str(exc)) from exc
        except ValueError as exc:
            raise ProtocolError("invalid_request", str(exc)) from exc
        rows = []
        for event in result["events"]:
            row = dict(event)
            if event.get("exact") is True and event.get("source") == "gateway.audit":
                row["ref"] = REGISTRY.reference(
                    "receipt", {"receipt_id": event["event_id"]}
                )
            elif isinstance(event.get("subject_ref"), str):
                row["ref"] = event["subject_ref"]
            rows.append(row)
        result["events"] = rows
        return result

    def v2_run_shell(
        self,
        *,
        project_id: str,
        checkout_id: str,
        argv: list[str],
        cwd: str,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        self.principal.require(Capability.SHELL_RUN)
        if self.principal.name != "operator":
            raise PolicyError("operator shell jobs require the operator principal")
        if not isinstance(project_id, str) or not 1 <= len(project_id) <= 128:
            raise ProtocolError("invalid_request", "project_id is malformed")
        if not isinstance(checkout_id, str) or not 1 <= len(checkout_id) <= 128:
            raise ProtocolError("invalid_request", "checkout_id is malformed")
        if (
            not isinstance(argv, list)
            or not 1 <= len(argv) <= 128
            or any(
                not isinstance(argument, str) or not 1 <= len(argument) <= 32_768
                for argument in argv
            )
        ):
            raise ProtocolError("invalid_request", "argv is malformed")
        if not isinstance(cwd, str) or not 1 <= len(cwd) <= 4_096:
            raise ProtocolError("invalid_request", "cwd is malformed")
        if (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or not 1 <= timeout_seconds <= 3_600
        ):
            raise ProtocolError(
                "invalid_request", "run timeout_seconds must be between 1 and 3600"
            )
        result = self._job(
            "job.shell.start",
            {
                "project_id": project_id,
                "checkout_id": checkout_id,
                "argv": argv,
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
                "result": "exit-status",
            },
            principal="operator",
        )
        job_id = result.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise ProtocolError(
                "owner_failed", "job owner start response omitted the job ID"
            )
        return {
            **result,
            "ref": REGISTRY.reference("job", {"job_id": job_id}),
        }

    def v2_run_declared_operation(
        self,
        *,
        project_id: str | None,
        operation: str | None,
        workspace_id: str | None,
        parameters: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        self.principal.require(Capability.JOB_START)
        if self.principal.name not in {"agent-control", "operator"}:
            raise PolicyError(
                "declared operations require agent-control or operator principal"
            )
        if not isinstance(project_id, str) or not 1 <= len(project_id) <= 128:
            raise ProtocolError("invalid_request", "project_id is malformed")
        if not isinstance(operation, str) or not 1 <= len(operation) <= 128:
            raise ProtocolError("invalid_request", "operation is malformed")
        if workspace_id is not None and (
            not isinstance(workspace_id, str) or not 1 <= len(workspace_id) <= 128
        ):
            raise ProtocolError("invalid_request", "workspace_id is malformed")
        if parameters is not None and not isinstance(parameters, Mapping):
            raise ProtocolError("invalid_request", "parameters must be an object")
        arguments: dict[str, Any] = {
            "project_id": project_id,
            "operation": operation,
            "parameters": dict(parameters or {}),
        }
        if workspace_id is not None:
            arguments["workspace_id"] = workspace_id
        result = self._job("job.start", arguments)
        job_id = result.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise ProtocolError(
                "owner_failed",
                "job owner declared-operation start response omitted the job ID",
            )
        return {**result, "ref": REGISTRY.reference("job", {"job_id": job_id})}

    @staticmethod
    def _resource_reference(
        reference: str, allowed: set[str], message: str
    ) -> tuple[Any, dict[str, str], str]:
        try:
            resource, values = REGISTRY.resolve(reference)
        except RegistryError as exc:
            raise ProtocolError("not_found", message) from exc
        if resource.kind not in allowed:
            raise ProtocolError("invalid_request", message)
        return resource, values, str(resource.ref_template.format(values))

    @staticmethod
    def _required_preconditions(
        preconditions: Mapping[str, Any] | None,
        allowed: set[str],
    ) -> dict[str, Any]:
        if not isinstance(preconditions, Mapping) or not preconditions:
            raise ProtocolError(
                "precondition_failed", "mutation requires preconditions"
            )
        values = dict(preconditions)
        if set(values) - allowed:
            raise ProtocolError(
                "invalid_request", "mutation preconditions are not recognized"
            )
        return values

    def _recent_jobs(self, limit: int, cursor: str | None = None) -> dict[str, Any]:
        self.principal.require(Capability.JOB_READ)
        arguments: dict[str, Any] = {"limit": limit}
        if cursor:
            arguments["cursor"] = cursor
        response = self._job("job.list", arguments)
        jobs = response.get("jobs")
        if not isinstance(jobs, list):
            raise ProtocolError("owner_failed", "job owner list response is malformed")
        rows = [
            {
                "ref": REGISTRY.reference("job", {"job_id": str(job.get("job_id"))}),
                **job,
            }
            for job in jobs
            if isinstance(job, Mapping)
        ]
        return {
            "jobs": rows,
            "limit": limit,
            "truncated": bool(response.get("truncated")),
            "next_cursor": response.get("next_cursor"),
            "snapshot": response.get("snapshot"),
        }

    def _unit_view(self, values: Mapping[str, str]) -> dict[str, Any]:
        page = self.observe.machine_query("units", limit=500)
        rows = page.get("rows") if isinstance(page, Mapping) else None
        if not isinstance(rows, list):
            raise ProtocolError("unavailable", "machine unit owner is unavailable")
        unit = next(
            (
                row
                for row in rows
                if isinstance(row, Mapping)
                and row.get("unit") == values["unit"]
                and row.get("manager", values["manager"]) == values["manager"]
            ),
            None,
        )
        if unit is None:
            raise ProtocolError(
                "not_found", "machine unit is not in the current bounded owner page"
            )
        return dict(unit)

    def _machine_target(self, reference: str) -> tuple[str, dict[str, Any]]:
        try:
            resource, values = REGISTRY.resolve(reference)
        except RegistryError as exc:
            raise ProtocolError(
                "not_found", "canonical machine target was not found"
            ) from exc
        canonical_ref = str(resource.ref_template.format(values))
        if resource.kind == "job":
            return canonical_ref, {"job_id": values["job_id"]}
        if resource.kind == "machine_unit":
            if values["manager"] not in {"user", "system"}:
                raise ProtocolError(
                    "invalid_request", "machine unit manager is not recognized"
                )
            return canonical_ref, {"unit": values["unit"]}
        if resource.kind == "process":
            try:
                pid = int(values["pid"])
                start_ticks = int(values["start_ticks"])
            except ValueError as exc:
                raise ProtocolError(
                    "invalid_request", "process reference is malformed"
                ) from exc
            if pid <= 1 or start_ticks < 0:
                raise ProtocolError("invalid_request", "process reference is malformed")
            return canonical_ref, {"process": {"pid": pid, "start_ticks": start_ticks}}
        raise ProtocolError(
            "invalid_request", "reference does not identify an operable machine target"
        )

    @staticmethod
    def _machine_receipt(
        receipt: Mapping[str, Any],
        *,
        action: str,
        target: Mapping[str, Any],
        expected_revision: int,
        idempotency_key: str,
        operator_reason: str,
    ) -> dict[str, Any]:
        required = {
            "schema": str,
            "receipt_id": str,
            "idempotency_key": str,
            "action": str,
            "target": dict,
            "operator_reason": str,
            "expected_revision": int,
        }
        if any(
            not isinstance(receipt.get(key), value_type)
            or (key == "expected_revision" and isinstance(receipt.get(key), bool))
            for key, value_type in required.items()
        ):
            raise ProtocolError(
                "owner_failed", "ops reducer returned a malformed action receipt"
            )
        if receipt["schema"] != "sinnix-ops-action-v1" or (
            receipt["idempotency_key"] != idempotency_key
            or receipt["action"] != action
            or receipt["target"] != target
            or receipt["expected_revision"] != expected_revision
            or receipt["operator_reason"] != operator_reason
        ):
            raise ProtocolError(
                "owner_failed",
                "ops reducer receipt does not match the submitted action",
            )
        return {
            key: receipt[key]
            for key in (
                "schema",
                "receipt_id",
                "idempotency_key",
                "action",
                "target",
                "operator_reason",
                "expected_revision",
                "status",
                "preconditions",
                "previous_state",
                "resulting_state",
                "adapter",
                "created_at",
            )
            if key in receipt
        }

    def v2_operate(
        self,
        *,
        reference: str,
        action: str,
        parameters: Mapping[str, Any] | None,
        reason: str | None,
        idempotency_key: str | None,
        preconditions: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        canonical_ref, target = self._machine_target(reference)
        values = self._required_preconditions(preconditions, {"expected_revision"})
        expected_revision = values.get("expected_revision")
        if (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision < 0
        ):
            raise ProtocolError(
                "invalid_request", "expected_revision must be a non-negative integer"
            )
        if not isinstance(action, str) or action not in MACHINE_OPERATIONS:
            raise ProtocolError("invalid_request", "machine action is not recognized")
        if not isinstance(parameters, Mapping):
            raise ProtocolError(
                "invalid_request", "machine parameters must be an object"
            )
        if not isinstance(reason, str) or not reason:
            raise ProtocolError("invalid_request", "machine operation requires reason")
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise ProtocolError(
                "invalid_request", "machine operation requires idempotency_key"
            )
        owner_receipt = self._machine_receipt(
            self.machine_actions.execute(
                action,
                target,
                expected_revision,
                idempotency_key,
                reason,
                dict(parameters),
            ),
            action=action,
            target=target,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            operator_reason=reason,
        )
        return {"ref": canonical_ref, "action": action, "owner_receipt": owner_receipt}

    async def v2_wait_async(
        self,
        reference: str,
        timeout_seconds: int,
        target: str = "job_terminal",
        expected: Mapping[str, Any] | None = None,
        poll_seconds: float = 0.25,
        cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(reference, str) or not 1 <= len(reference) <= 2_048:
            raise ProtocolError("invalid_request", "wait ref is malformed")
        try:
            resource, values = REGISTRY.resolve(reference)
            wait_target = WaitTarget(target)
        except (RegistryError, ValueError) as exc:
            raise ProtocolError(
                "invalid_request", "wait target or reference is not recognized"
            ) from exc
        if wait_target is WaitTarget.JOB_TERMINAL:
            if resource.kind != "job":
                raise ProtocolError(
                    "invalid_request", "job_terminal requires a canonical job reference"
                )
            self.principal.require(Capability.JOB_READ)
            if cancelled is not None and cancelled():
                return {
                    "schema": "sinnix.gateway-wait.v1",
                    "outcome": "cancelled",
                    "target": wait_target.value,
                    "ref": reference,
                    "polls": 0,
                    "evidence": {},
                    "source_revision": "cancelled",
                    "continuation": source_revision({"ref": reference}),
                }
            if cancelled is None:
                result = await anyio.to_thread.run_sync(
                    self._job,
                    "job.wait",
                    {"job_id": values["job_id"], "timeout_seconds": timeout_seconds},
                    abandon_on_cancel=True,
                )
            else:
                result_box: dict[str, Any] = {}
                request_cancelled = False

                async def wait_for_owner() -> None:
                    result_box["result"] = await anyio.to_thread.run_sync(
                        self._job,
                        "job.wait",
                        {
                            "job_id": values["job_id"],
                            "timeout_seconds": timeout_seconds,
                        },
                        abandon_on_cancel=True,
                    )
                    task_group.cancel_scope.cancel()

                async def watch_request() -> None:
                    nonlocal request_cancelled
                    while not cancelled():
                        await anyio.sleep(0.05)
                    request_cancelled = True
                    task_group.cancel_scope.cancel()

                async with anyio.create_task_group() as task_group:
                    task_group.start_soon(wait_for_owner)
                    task_group.start_soon(watch_request)
                if request_cancelled:
                    return {
                        "schema": "sinnix.gateway-wait.v1",
                        "outcome": "cancelled",
                        "target": wait_target.value,
                        "ref": reference,
                        "polls": 0,
                        "evidence": {},
                        "source_revision": "cancelled",
                        "continuation": source_revision({"ref": reference}),
                    }
                result = result_box["result"]
            if cancelled is not None and cancelled():
                evidence = result.get("state", result)
                return {
                    "schema": "sinnix.gateway-wait.v1",
                    "outcome": "cancelled",
                    "target": wait_target.value,
                    "ref": reference,
                    "polls": 0,
                    "evidence": evidence
                    if isinstance(evidence, Mapping)
                    else {"value": evidence},
                    "source_revision": source_revision(evidence),
                    "continuation": source_revision(
                        {"ref": reference, "evidence": evidence}
                    ),
                }
            if result.get("job_id") != values["job_id"]:
                raise ProtocolError(
                    "owner_failed",
                    "job owner wait response does not match the requested job",
                )
            return {
                **result,
                "ref": REGISTRY.reference("job", {"job_id": values["job_id"]}),
                "target": wait_target.value,
            }
        if self.waits is None:
            raise ProtocolError("unavailable", "wait owner is unavailable")
        try:
            request = WaitRequest(
                target=wait_target,
                reference=reference,
                expected={} if expected is None else expected,
                timeout_seconds=timeout_seconds,
                poll_seconds=poll_seconds,
            )
            return await self.waits.wait_async(request, cancelled=cancelled)
        except ValueError as exc:
            raise ProtocolError("invalid_request", str(exc)) from exc

    def _resolve_wait(self, request: WaitRequest) -> WaitEvidence:
        resource, values = REGISTRY.resolve(request.reference)
        expected = dict(request.expected)
        if (
            request.target is WaitTarget.BEAD_STATUS
            or request.target is WaitTarget.BEAD_REVISION
        ):
            if resource.kind != "bead":
                raise ValueError("Beads waits require a canonical bead reference")
            bead = self.beads.get(values["project_id"], values["bead_id"])
            fields = (
                bead.get("fields", {})
                if isinstance(bead.get("fields"), Mapping)
                else {}
            )
            current = (
                fields.get("status")
                if request.target is WaitTarget.BEAD_STATUS
                else bead.get("task_revision")
            )
            wanted = (
                expected.get("status")
                if request.target is WaitTarget.BEAD_STATUS
                else expected.get("revision", expected.get("task_revision"))
            )
            return WaitEvidence(
                current == wanted,
                {"current": current, "bead": bead},
                str(bead.get("task_revision", source_revision(bead))),
            )
        if request.target is WaitTarget.UNIT_STATE:
            if resource.kind != "machine_unit":
                raise ValueError(
                    "unit waits require a canonical machine unit reference"
                )
            current = self._unit_view(values)
            state = (
                current.get("active_state", current.get("state"))
                if isinstance(current, Mapping)
                else None
            )
            wanted = expected.get("state", expected.get("active_state"))
            return WaitEvidence(
                state == wanted,
                {"state": state, "unit": current},
                source_revision(current),
            )
        if request.target is WaitTarget.FILE_HASH:
            if resource.kind != "host_file":
                raise ValueError("file waits require a canonical host file reference")
            current = self.files.read("stat", decode_file_ref(request.reference))
            wanted = expected.get("sha256") or expected.get("hash")
            return WaitEvidence(
                current.get("sha256") == wanted, current, str(current.get("sha256"))
            )
        if request.target is WaitTarget.CAPTURE_FRESHNESS:
            if resource.kind != "capture_lane":
                raise ValueError(
                    "capture waits require a canonical capture lane reference"
                )
            lane = self.captures.lane(values["lane"])
            path = Path(str(lane["path"]))
            mtime = path.stat().st_mtime if path.exists() else 0.0
            age = max(0.0, time.time() - mtime) if mtime else None
            max_age = float(expected.get("max_age_seconds", 0))
            return WaitEvidence(
                age is not None and age <= max_age,
                {"mtime": mtime, "age_seconds": age, "lane": lane},
                source_revision({"mtime": mtime, "lane": lane.get("name")}),
            )
        if request.target is WaitTarget.RECEIPT_APPEARANCE:
            if resource.kind != "receipt":
                raise ValueError("receipt waits require a canonical receipt reference")
            try:
                receipt = self.audit.receipt(values["receipt_id"])
            except ValueError:
                return WaitEvidence(
                    False, {"available": False, "ref": request.reference}, "missing"
                )
            return WaitEvidence(
                True,
                {"available": True, "receipt": receipt},
                str(receipt["entry_hash"]),
            )
        raise ValueError(f"wait target {request.target.value} is not implemented")

    @staticmethod
    def _resource_refs(result: Any) -> list[str]:
        refs: list[str] = []

        def collect(value: Any) -> None:
            if len(refs) >= 128:
                return
            if isinstance(value, Mapping):
                for key, item in value.items():
                    if (
                        (key == "ref" or key.endswith("_ref"))
                        and isinstance(item, str)
                        and item.startswith("sinnix://")
                    ):
                        try:
                            REGISTRY.resolve(item)
                        except RegistryError:
                            continue
                        refs.append(item)
                    else:
                        collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        collect(result)
        return sorted(set(refs))

    def _record_v2_receipt(
        self,
        action: Action,
        outcome: str,
        context: RequestContext,
        result: Any | None = None,
        error: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        target_refs: list[str] = self._resource_refs(result)
        artifact_refs: list[str] = []
        created_objects: list[str] = []
        if isinstance(result, Mapping):
            for key, value in result.items():
                if key in {"artifact_id", "diagnostic_artifact_id"} and isinstance(
                    value, str
                ):
                    artifact_refs.append(f"sinnix://artifacts/{value}")
                elif key == "created" and value is True:
                    created_objects.append(action.name)
            before = result.get("before")
            after = result.get("after")
            before_refs = self._resource_refs(before)
            after_refs = self._resource_refs(after)
            before_revision = result.get("before_revision")
            after_revision = result.get("after_revision")
            owner_route = result.get("owner_route")
            owner_version = result.get("owner_version")
            owner_history_ref = result.get("owner_history_ref")
        else:
            before_refs = []
            after_refs = []
            before_revision = None
            after_revision = None
            owner_route = None
            owner_version = None
            owner_history_ref = None
        payload = {
            "schema": "sinnix.gateway-receipt.v2",
            "action": action.name,
            "principal": self.principal.name,
            "actor": context.actor or self.principal.name,
            "reason": context.reason,
            "request_id": context.request_id,
            "correlation_id": context.request_id,
            "request_sha256": context.request_sha256,
            "idempotency_key": context.idempotency_key,
            "target_refs": sorted(set(target_refs)),
            "owner": action.owner,
            "owner_route": owner_route
            if isinstance(owner_route, str)
            else action.route,
            "owner_version": owner_version
            if isinstance(owner_version, (str, int))
            else ACTION_REVISION,
            "preconditions": dict(context.preconditions or {}),
            "before_refs": before_refs,
            "after_refs": after_refs,
            "before_revision": before_revision,
            "after_revision": after_revision,
            "owner_history_ref": owner_history_ref
            if isinstance(owner_history_ref, str)
            else None,
            "effects": sorted(effect.value for effect in action.storage_effects),
            "created_objects": created_objects,
            "artifact_refs": sorted(set(artifact_refs)),
            "owner_receipt_id": (
                result.get("owner_receipt", {}).get("receipt_id")
                if isinstance(result, Mapping)
                and isinstance(result.get("owner_receipt"), Mapping)
                and isinstance(result["owner_receipt"].get("receipt_id"), str)
                else None
            ),
            "atomicity": (
                "read_only_with_observability_persistence"
                if action.effect is EffectMode.READ
                else result.get("atomicity", "owner_declared")
                if isinstance(result, Mapping)
                else "not_atomic"
                if error and error.get("code") == "partial_completion"
                else "owner_declared"
            ),
            "partial_completion": bool(
                (isinstance(result, Mapping) and result.get("partial_completion"))
                or (error and error.get("code") == "partial_completion")
            ),
            "compensation": result.get("compensation")
            if isinstance(result, Mapping)
            else None,
            "error": dict(error or {}),
        }
        return self.audit.append(action.name, outcome, payload)

    @staticmethod
    def _diagnostic_payload(response: dict[str, object]) -> dict[str, object]:
        return {
            key: response[key]
            for key in (
                "failure_class",
                "route",
                "exit_status",
                "timed_out",
                "output_exceeded",
                "diagnostic_artifact_id",
            )
            if key in response
        }

    @staticmethod
    def _request_context(request: Mapping[str, Any]) -> RequestContext:
        raw = dict(request)
        request_id = raw.pop("request_id", None)
        actor = raw.get("actor")
        reason = raw.get("reason")
        idempotency_key = raw.get("idempotency_key")
        deadline_at = raw.get("deadline_at")
        preconditions = raw.get("preconditions")
        if request_id is not None and not isinstance(request_id, str):
            raise ProtocolError("invalid_request", "request_id must be a string")
        for name, value in (
            ("actor", actor),
            ("reason", reason),
            ("idempotency_key", idempotency_key),
        ):
            if value is not None and (not isinstance(value, str) or not value):
                raise ProtocolError(
                    "invalid_request", f"{name} must be a non-empty string"
                )
        if deadline_at is not None and not isinstance(deadline_at, (int, float)):
            raise ProtocolError(
                "invalid_request", "deadline_at must be a Unix timestamp"
            )
        if preconditions is not None and not isinstance(preconditions, Mapping):
            raise ProtocolError("invalid_request", "preconditions must be an object")
        try:
            encoded = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
        except (TypeError, ValueError) as exc:
            raise ProtocolError(
                "invalid_request", "V2 request is not JSON serializable"
            ) from exc
        return RequestContext.create(
            hashlib.sha256(encoded).hexdigest(),
            request_id=request_id,
            actor=actor,
            reason=reason,
            idempotency_key=idempotency_key,
            deadline_at=float(deadline_at) if deadline_at is not None else None,
            preconditions=preconditions,
        )

    def _v2_success(
        self, action: Action, result: Any, context: RequestContext
    ) -> dict[str, Any]:
        receipt = self._record_v2_receipt(action, "ok", context, result=result)
        return self.results.record(
            action=action.name,
            owner=action.owner,
            route=action.route,
            outcome="ok",
            payload=result,
            receipt=receipt,
            request=context,
            meta={"resource_refs": self._resource_refs(result)},
        )

    def _v2_failure(
        self,
        action: Action,
        exc: Exception,
        context: RequestContext,
        *,
        enforce_action_failure_codes: bool = True,
    ) -> dict[str, Any]:
        if isinstance(exc, OwnerDiagnosticError):
            details = self._diagnostic_payload(exc.response)
            diagnostic_id = details.pop("diagnostic_artifact_id", None)
            error: dict[str, Any] = {
                "code": "owner_failed",
                "message": "owner route failed",
                "details": details,
                "diagnostic_refs": (
                    [f"sinnix://artifacts/{diagnostic_id}"]
                    if isinstance(diagnostic_id, str)
                    else []
                ),
            }
        elif isinstance(exc, ProtocolError):
            error = {
                "code": exc.code,
                "message": public_error(exc),
                "details": exc.details,
                "diagnostic_refs": exc.diagnostic_refs,
            }
        elif isinstance(exc, ResultError):
            error = {
                "code": exc.failure_class,
                "message": public_error(exc),
                "details": {},
                "diagnostic_refs": [],
            }
        elif isinstance(exc, PolicyError):
            error = {
                "code": "policy_denied",
                "message": public_error(exc),
                "details": {},
                "diagnostic_refs": [],
            }
        elif isinstance(exc, ValueError):
            error = {
                "code": "invalid_request",
                "message": public_error(exc),
                "details": {},
                "diagnostic_refs": [],
            }
        else:
            error = {
                "code": "owner_failed",
                "message": "gateway owner route failed",
                "details": {},
                "diagnostic_refs": [],
            }
        if (
            enforce_action_failure_codes
            and action.failure_codes is not None
            and error["code"] not in action.typed_failures
        ):
            error = {
                "code": "owner_failed",
                "message": "gateway owner route failed",
                "details": {},
                "diagnostic_refs": [],
            }
        receipt = self._record_v2_receipt(action, "error", context, error=error)
        return self.results.record(
            action=action.name,
            owner=action.owner,
            route=action.route,
            outcome="error",
            payload=error,
            receipt=receipt,
            request=context,
        )

    def _claim_v2_idempotency(
        self, action: Action, context: RequestContext
    ) -> dict[str, Any] | None:
        if action.effect is EffectMode.READ:
            return None
        if not action.supports_idempotency:
            raise ProtocolError(
                "invalid_request",
                "mutating action does not declare idempotency support",
            )
        if context.idempotency_key is None:
            raise ProtocolError(
                "invalid_request", "mutating action requires idempotency_key"
            )
        state, response = self.audit.claim_idempotency(
            action.name, context.idempotency_key, context.request_sha256
        )
        if state == "new":
            return None
        if state == "replay":
            if not isinstance(response, dict):
                raise ProtocolError(
                    "unavailable", "stored idempotency response is malformed"
                )
            return response
        if state == "conflict":
            raise ProtocolError(
                "idempotency_conflict",
                "idempotency key was already used with a different request",
            )
        raise ProtocolError(
            "conflict", "matching idempotency request is still in progress"
        )

    def _complete_v2_idempotency(
        self, action: Action, context: RequestContext, response: Mapping[str, Any]
    ) -> None:
        if action.effect is not EffectMode.READ and context.idempotency_key is not None:
            self.audit.complete_idempotency(
                action.name,
                context.idempotency_key,
                context.request_sha256,
                response,
            )

    def execute_v2(
        self,
        action: Action,
        callback: Callable[[], Any],
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        context = RequestContext.create(hashlib.sha256(b"{}").hexdigest())
        reserved = False
        try:
            context = self._request_context(request)
            if self.principal_name not in action.principals:
                raise PolicyError(
                    f"principal {self.principal_name!r} cannot invoke action {action.name!r}"
                )
            if context.preconditions and not action.supports_precondition:
                raise ProtocolError(
                    "invalid_request", "action does not support preconditions"
                )
            if context.deadline_at is not None and time.time() >= context.deadline_at:
                raise ProtocolError(
                    "deadline", "request deadline elapsed before execution"
                )
            replay = self._claim_v2_idempotency(action, context)
            if replay is not None:
                return replay
            reserved = action.effect is not EffectMode.READ
            response = self._v2_success(action, callback(), context)
        except Exception as exc:
            response = self._v2_failure(action, exc, context)
        if reserved:
            self._complete_v2_idempotency(action, context, response)
        return response

    async def execute_v2_async(
        self,
        action: Action,
        callback: Callable[[], Awaitable[Any]],
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        context = RequestContext.create(hashlib.sha256(b"{}").hexdigest())
        reserved = False
        try:
            context = self._request_context(request)
            if self.principal_name not in action.principals:
                raise PolicyError(
                    f"principal {self.principal_name!r} cannot invoke action {action.name!r}"
                )
            if context.preconditions and not action.supports_precondition:
                raise ProtocolError(
                    "invalid_request", "action does not support preconditions"
                )
            if context.deadline_at is not None and time.time() >= context.deadline_at:
                raise ProtocolError(
                    "deadline", "request deadline elapsed before execution"
                )
            replay = self._claim_v2_idempotency(action, context)
            if replay is not None:
                return replay
            reserved = action.effect is not EffectMode.READ
            response = self._v2_success(action, await callback(), context)
        except Exception as exc:
            response = self._v2_failure(action, exc, context)
        if reserved:
            self._complete_v2_idempotency(action, context, response)
        return response

    def execute_v2_jsonl(
        self,
        action: Action,
        command: list[str],
        profile: ExecutionProfile,
        request: Mapping[str, Any],
        *,
        source_revision: str,
        page_size: int = 100,
        execution: OwnerExecution | None = None,
    ) -> dict[str, Any]:
        """Run a JSONL owner through the shared kernel into an immutable snapshot."""
        context = RequestContext.create(hashlib.sha256(b"{}").hexdigest())
        writer = None
        try:
            context = self._request_context(request)
            if context.deadline_at is not None and time.time() >= context.deadline_at:
                raise ProtocolError(
                    "deadline", "request deadline elapsed before execution"
                )
            writer = self.results.start_snapshot(
                query_sha256=context.request_sha256,
                source_revision=source_revision,
                page_size=page_size,
            )
            result = (execution or OwnerExecution()).run_jsonl(
                command, profile, writer.append
            )
            if not result.available:
                writer.abort()
                writer = None
                raise OwnerDiagnosticError(
                    self.artifacts.record_owner_diagnostic(action.route, result)
                )
            receipt = self._record_v2_receipt(action, "ok", context)
            return self.results.record_snapshot(
                action=action.name,
                owner=action.owner,
                route=action.route,
                writer=writer,
                receipt=receipt,
                request=context,
            )
        except (
            OwnerDiagnosticError,
            ProtocolError,
            ResultError,
            PolicyError,
            ValueError,
        ) as exc:
            if writer is not None:
                writer.abort()
            return self._v2_failure(action, exc, context)


def _principal_contract(principal_name: str) -> str:
    principal = Principal.for_name(principal_name)
    payload = {
        "principal": principal_name,
        "capabilities": sorted(
            capability.value for capability in principal.capabilities
        ),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
