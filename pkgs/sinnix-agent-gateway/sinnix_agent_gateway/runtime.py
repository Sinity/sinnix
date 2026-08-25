from __future__ import annotations

import base64
import binascii
import hashlib
import json
import time
import anyio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, TypeVar, cast
from uuid import uuid4

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from .artifacts import ArtifactService
from .audit import AuditService
from .beads import BeadsError, BeadsService
from .bindings import TargetToolBinding, TargetToolBindings
from .browser import BrowserService
from .capabilities import Capability, PolicyError, Principal
from .capability_index import CapabilityIndexService
from .captures import CaptureService
from .config import GatewayConfig
from .contexts import ComponentResult, ComponentSpec, ContextComposer, ContextSnapshotStore, CONTEXT_INTENTS, source_revision
from .contracts import ActionSpec, EffectMode, VerbFamily
from .desktop import DesktopService
from .legacy_manifest import LEGACY_MANIFEST
from sinnix_mcp.execution import ExecutionProfile, OwnerDiagnosticError, OwnerExecution
from .files import HostFileService
from .machine_actions import MachineActionService
from .mcp_broker import McpBrokerService
from .memory import MemoryService
from .observe import ObserveService
from .project_context import ProjectContextService
from .projects import ProjectPreconditionError, ProjectService
from .events import EventCursorError, NormalizedEventService
from .redaction import public_error
from .results import ProtocolError, RequestContext, ResultError, ResultService
from .route_preflight import GatewayRoutePreflight
from .registry import CatalogSearch, MACHINE_OPERATIONS, REGISTRY, RegistryError
from .schemas import AgentLaunchRequest, V2ToolEnvelope
from .sessions import SessionLogService
from .terminals import TerminalService
from .timeline import TimelineService
from .waits import BoundedWaitService, WaitEvidence, WaitRequest, WaitTarget
from sinnix_mcp import ErrorCode, RequestEnvelope
from sinnixd.api import SinnixdClient, SinnixdClientError

T = TypeVar("T")

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

AUDITED_READ_TOOL = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

LEGACY_OPERATOR_MANIFEST_BYTES = LEGACY_MANIFEST["canonical_bytes"]
LEGACY_OPERATOR_TOOL_COUNT = len(LEGACY_MANIFEST["tools"])
TOKEN_ESTIMATE_BYTES_PER_TOKEN = 4
IDEMPOTENT_RUN_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
IDEMPOTENT_MUTATION_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=True,
    openWorldHint=False,
)


def _orientation_task_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    """Keep project orientation useful without embedding full Beads bodies."""
    items = result.get("items")
    if not isinstance(items, list):
        return dict(result)
    fields = (
        "id", "ref", "title", "status", "priority", "issue_type",
        "assignee", "labels", "parent", "task_revision", "etag",
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
        "baseline": {
            "source_commit": LEGACY_MANIFEST["source_commit"],
            "canonical_bytes": LEGACY_OPERATOR_MANIFEST_BYTES,
            "tool_count": LEGACY_OPERATOR_TOOL_COUNT,
        },
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
    sinnixd: SinnixdClient
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
            sinnixd=SinnixdClient(config.sinnixd_socket),
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
            jobs=lambda limit, cursor: runtime.v2_jobs_query(
                {"limit": limit, **({"cursor": cursor} if cursor else {})}
            ),
        )
        runtime.context_snapshots = ContextSnapshotStore(config.state_dir, principal_name)
        runtime.waits = BoundedWaitService(runtime._resolve_wait)
        return runtime

    def owner_revision_observations(self) -> dict[str, str]:
        """Read real owner revisions used by the subscription publisher."""
        observations: dict[str, str] = {}
        for project_id in self.config.projects:
            try:
                summary = self.projects.summary(project_id)
                latest = summary.get("latest_commit") if isinstance(summary, Mapping) else None
                revision = latest.get("id") if isinstance(latest, Mapping) else None
                if isinstance(revision, str) and revision:
                    observations[REGISTRY.reference("project", {"project_id": project_id})] = revision
            except Exception:
                continue
            try:
                authority = self.beads.task_authority_status(project_id)
                revision = authority.get("revision") if isinstance(authority, Mapping) else None
                if isinstance(revision, str) and revision:
                    observations[f"sinnix://projects/{project_id}/task-authority"] = revision
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

    def catalog(self, search: CatalogSearch) -> dict[str, Any]:
        def resolve_availability(kind: str, name: str) -> tuple[str, str | None]:
            if kind == "action":
                return "available", None
            if any(
                action.name != "gateway.catalog"
                and name in action.resource_kinds
                and (search.principal is None or search.principal in action.principals)
                for action in REGISTRY.actions
            ):
                return "available", None
            return "unavailable", "no migrated V2 action currently exposes this resource"

        selected_project: dict[str, Any] | None = None
        if search.project is not None:
            selected_project = next(
                (
                    project
                    for project in self.projects.list()["projects"]
                    if project["project_id"] == search.project
                ),
                None,
            )
            if selected_project is None or not selected_project["available"]:
                raise ProtocolError(
                    "unavailable", "project is unavailable to this principal"
                )
        catalog = REGISTRY.search(
            search, availability_resolver=resolve_availability
        )
        if selected_project is not None:
            catalog["project"] = {
                **selected_project,
                "ref": REGISTRY.reference(
                    "project", {"project_id": selected_project["project_id"]}
                ),
            }
        return catalog

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
            raise ProtocolError("not_found", "canonical project resource was not found") from exc
        allowed = {"project", "checkout"} if allow_checkout else {"project"}
        if resource.kind not in allowed:
            raise ProtocolError("invalid_request", "ref does not identify the required project resource")
        return (
            values["project_id"],
            values.get("checkout_id"),
            str(resource.ref_template.format(values)),
        )

    def _sinnixd_job(
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
        try:
            response = self.sinnixd.dispatch(request)
        except SinnixdClientError as exc:
            raise ProtocolError("unavailable", str(exc)) from exc
        if response.owner != "systemd-jobs":
            raise ProtocolError(
                "owner_failed", "sinnixd response violates the job-owner contract"
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
                "owner_failed", "sinnixd job response must contain an inline object"
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

    def v2_query(
        self, reference: str, query: str, max_matches: int
    ) -> dict[str, Any]:
        project_id, checkout_id, canonical_ref = self._project_reference(
            reference, allow_checkout=True
        )
        if (
            not isinstance(max_matches, int)
            or isinstance(max_matches, bool)
            or not 1 <= max_matches <= 1_000
        ):
            raise ProtocolError("invalid_request", "max_matches must be 1-1000")
        result = self.projects.search(project_id, query, max_matches, checkout_id)
        selected_checkout = checkout_id or "default"
        return {
            "ref": canonical_ref,
            "project_ref": REGISTRY.reference("project", {"project_id": project_id}),
            "checkout_ref": REGISTRY.reference(
                "checkout",
                {"project_id": project_id, "checkout_id": selected_checkout},
            ),
            **result,
        }

    def compose_context(
        self, reference: str, intent: str, job_ref: str | None = None
    ) -> dict[str, Any]:
        if intent == "project":
            intent = "project.orientation"
        if intent not in CONTEXT_INTENTS:
            raise ProtocolError("invalid_request", f"unknown context intent: {intent}")
        try:
            resource, values = REGISTRY.resolve(reference)
        except RegistryError as exc:
            raise ProtocolError("not_found", "context target is not canonical") from exc
        if intent in {"project.orientation", "project.triage", "incident"}:
            if resource.kind not in {"project", "checkout"}:
                raise ProtocolError("invalid_request", f"{intent} requires a project reference")
            project_id = values["project_id"]
            target_ref = str(resource.ref_template.format(values))
        elif intent in {"bead.work", "bead.review"}:
            if resource.kind != "bead":
                raise ProtocolError("invalid_request", f"{intent} requires a Beads reference")
            project_id = values["project_id"]
            target_ref = str(resource.ref_template.format(values))
        else:
            if resource.kind != "job":
                raise ProtocolError("invalid_request", "job.review requires a job reference")
            project_id = None
            target_ref = str(resource.ref_template.format(values))
        if self.principal.name == "agent-control" and intent in {"project.orientation", "project.triage"}:
            raise PolicyError("agent-control project context is limited to an assigned Beads job")

        declared = dict(CONTEXT_INTENTS[intent].components)

        def component(name: str, fn: Callable[[], Any], source_ref: str | None = None) -> ComponentSpec:
            def probe() -> ComponentResult:
                try:
                    value = fn()
                except ProtocolError as exc:
                    if exc.code in {"invalid_request", "not_found", "policy_denied", "precondition_failed"}:
                        raise
                    return ComponentResult.unavailable(name, public_error(exc), source_ref=source_ref)
                except Exception as exc:
                    return ComponentResult.unavailable(name, public_error(exc), source_ref=source_ref)
                revision = value.get("source_revision") if isinstance(value, Mapping) else None
                return ComponentResult.available(
                    name,
                    value,
                    revision=revision if isinstance(revision, str) else source_revision(value),
                    source_ref=source_ref,
                )
            return ComponentSpec(name, declared[name], probe)

        project_ref = REGISTRY.reference("project", {"project_id": project_id}) if project_id else None
        assigned_bead: Mapping[str, Any] | None = None
        review_job_observation: dict[str, Any] | None = None
        if intent == "bead.review" and self.principal.name != "agent-control":
            if not isinstance(job_ref, str):
                raise ProtocolError("invalid_request", "bead.review requires job_ref")
            _job_resource, job_values, _canonical_job_ref = self._resource_reference(
                job_ref, {"job"}, "bead.review requires a canonical job reference"
            )
            review_job_observation = self._sinnixd_job("job.get", {"job_id": job_values["job_id"]})
            binding = review_job_observation.get("contract", {}).get("bead_binding")
            if (
                not isinstance(binding, Mapping)
                or binding.get("bead_ref") != target_ref
                or binding.get("project_ref") != project_ref
            ):
                raise ProtocolError("precondition_failed", "job is not the requested Beads assignment")
        if intent in {"bead.work", "bead.review"} and self.principal.name == "agent-control":
            self._assigned_bead_job(target_ref, project_id, None, job_ref)
            assigned_bead = self.beads.get(
                project_id,
                values["bead_id"],
                includes=(
                    ["blockers", "dependencies", "dependents", "children", "refs"]
                    if intent == "bead.work"
                    else ["history", "events", "dependencies", "dependents", "refs"]
                ),
            )
            self._assigned_bead_job(target_ref, project_id, assigned_bead, job_ref)
        components: list[ComponentSpec] = []
        if intent == "project.orientation":
            assert project_id is not None
            components = [
                component("project", lambda: self.projects.summary(project_id), project_ref),
                component("checkout", lambda: self.projects.checkout(project_id, "default"), REGISTRY.reference("checkout", {"project_id": project_id, "checkout_id": "default"})),
                component("tasks", lambda: _orientation_task_summary(self.beads.query(project_ids=[project_id], view="ready", limit=20)), f"{project_ref}/beads"),
                component("authority", lambda: self.project_authority(project_id), f"{project_ref}/task-authority"),
            ]
        elif intent == "project.triage":
            assert project_id is not None
            components = [
                component("project", lambda: self.projects.summary(project_id), project_ref),
                component("open_beads", lambda: self.beads.query(project_ids=[project_id], view="open", limit=50), f"{project_ref}/beads"),
                component("stale_claims", lambda: self.beads.query(project_ids=[project_id], view="stale_claims", limit=50), f"{project_ref}/beads"),
                component("changes", lambda: self.projects.diff(project_id, None, None), project_ref),
            ]
        elif intent == "bead.work":
            bead_ref = target_ref
            bead_id = values["bead_id"]
            components = [
                component("bead", lambda: assigned_bead if assigned_bead is not None else self.beads.get(project_id, bead_id, includes=["blockers", "dependencies", "dependents", "children", "refs"]), bead_ref),
                component("project", lambda: self.projects.summary(project_id), project_ref),
                component("checkout", lambda: self.projects.checkout(project_id, "default"), REGISTRY.reference("checkout", {"project_id": project_id, "checkout_id": "default"})),
                component("assignment", lambda: self._context_assignment(bead_ref, project_id, job_ref), job_ref),
                component("blockers", lambda: self.beads.graph(project_id, bead_id, direction="down", edge_type="blocks", max_rows=50), f"{bead_ref}/blockers"),
            ]
        elif intent == "bead.review":
            if not isinstance(job_ref, str):
                raise ProtocolError("invalid_request", "bead.review requires job_ref")
            _job_resource, job_values, canonical_job_ref = self._resource_reference(job_ref, {"job"}, "bead.review requires a canonical job reference")
            review_bead = assigned_bead
            bead_id = values["bead_id"]
            job_observation: dict[str, Any] | None = review_job_observation

            def job() -> dict[str, Any]:
                nonlocal job_observation
                if job_observation is None:
                    job_observation = self._sinnixd_job("job.get", {"job_id": job_values["job_id"]})
                return job_observation

            components = [
                component("bead", lambda: review_bead if review_bead is not None else self.beads.get(project_id, bead_id, includes=["history", "events", "dependencies", "dependents", "refs"]), target_ref),
                component("job", job, canonical_job_ref),
                component("checkout", lambda: self.projects.checkout(project_id, "default"), REGISTRY.reference("checkout", {"project_id": project_id, "checkout_id": "default"})),
                component("diff", lambda: self.projects.diff(project_id, None, None), project_ref),
                component("evidence", lambda: self._review_evidence(job_values["job_id"], job()), canonical_job_ref),
            ]
        elif intent == "job.review":
            job_id = values["job_id"]
            job_observation: dict[str, Any] | None = None

            def job_value() -> dict[str, Any]:
                nonlocal job_observation
                if job_observation is None:
                    job_observation = self._sinnixd_job("job.get", {"job_id": job_id})
                return job_observation

            components = [
                component("job", job_value, target_ref),
                component("result", lambda: self._sinnixd_job("job.result", {"job_id": job_id, "max_bytes": 64_000}), target_ref),
                component("project", lambda: self.projects.summary(str(job_value().get("project_id"))), project_ref),
                component("events", lambda: self.audit.tail(50), f"sinnix://receipts"),
            ]
        else:
            components = [
                component("runtime", lambda: self.observe.machine_query("overview"), "sinnix://machine/overview"),
                component("transitions", lambda: (self.normalized_events.read(limit=50) if self.normalized_events else {"events": []}), "sinnix://events"),
                component("receipts", lambda: self.audit.tail(50), "sinnix://receipts"),
                component("jobs", lambda: self.v2_jobs_query({"limit": 50}), "sinnix://jobs"),
            ]
        context = self.context_composer.compose(intent, target_ref, components)
        by_name = {row["name"]: row for row in context["components"]}
        if intent == "bead.review" and by_name.get("job", {}).get("status") == "available":
            job_data = by_name["job"].get("data")
            binding = job_data.get("contract", {}).get("bead_binding") if isinstance(job_data, Mapping) else None
            if not isinstance(binding, Mapping) or binding.get("bead_ref") != target_ref:
                raise ProtocolError("precondition_failed", "job is not the requested Beads assignment")
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
        elif intent in {"bead.work", "job.review", "incident"}:
            compatibility.update(
                {
                    name: row["data"]
                    for name, row in by_name.items()
                    if row.get("status") == "available" and "data" in row
                }
            )
        elif intent == "bead.review":
            if all(by_name.get(name, {}).get("status") == "available" for name in ("bead", "job", "checkout", "evidence")):
                bead_data = by_name["bead"]["data"]
                job_data = by_name["job"]["data"]
                checkout_data = by_name["checkout"]["data"]
                binding = job_data.get("contract", {}).get("bead_binding") if isinstance(job_data, Mapping) else None
                launch_checkout = job_data.get("checkout") if isinstance(job_data, Mapping) else None
                current_checkout = checkout_data.get("checkout") if isinstance(checkout_data, Mapping) else None
                if isinstance(binding, Mapping) and isinstance(launch_checkout, Mapping) and isinstance(current_checkout, Mapping):
                    try:
                        compatibility = {
                            "bead": {"launch": dict(binding), "current": bead_data},
                            "job": {"ref": by_name["job"].get("source_ref"), **job_data},
                            "checkout": {
                                "launch": dict(launch_checkout),
                                "current": dict(current_checkout),
                                "commit_range": self.projects.commit_range(
                                    values["project_id"],
                                    launch_checkout["checkout_id"],
                                    launch_checkout["head"],
                                    current_checkout["head"],
                                ),
                            },
                            "evidence": by_name["evidence"]["data"],
                            "revision_mismatch": {
                                "task_revision": binding.get("task_revision") != bead_data.get("task_revision"),
                                "task_etag": binding.get("task_etag") != bead_data.get("etag"),
                                "code_revision": launch_checkout.get("head") != current_checkout.get("head"),
                            },
                        }
                    except (KeyError, TypeError, ValueError):
                        compatibility = {}
        if compatibility:
            candidate = {**context, **compatibility}
            if len(json.dumps(candidate, sort_keys=True, separators=(",", ":")).encode()) <= context["total_budget_bytes"]:
                context = candidate
        snapshot_body = {key: value for key, value in context.items() if key != "snapshot_ref"}
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

    def _context_assignment(self, bead_ref: str, project_id: str, job_ref: str | None) -> dict[str, Any]:
        if self.principal.name == "agent-control":
            job, binding, checkout, assignment_ref = self._assigned_bead_job(bead_ref, project_id, None, job_ref)
            return {"ref": assignment_ref, "job": job, "binding": dict(binding), "checkout": checkout}
        jobs = self.v2_jobs_query({"limit": 50})
        return {"jobs": [job for job in jobs.get("jobs", []) if isinstance(job.get("contract"), Mapping) and job["contract"].get("bead_binding", {}).get("bead_ref") == bead_ref]}

    def v2_context(
        self, reference: str, intent: str = "project", job_ref: str | None = None
    ) -> dict[str, Any]:
        return self.compose_context(reference, intent, job_ref)

    def _assigned_bead_job(
        self,
        bead_ref: str,
        project_id: str,
        bead: Mapping[str, Any] | None,
        job_ref: str | None,
    ) -> tuple[dict[str, Any], Mapping[str, Any], dict[str, Any], str]:
        if not isinstance(job_ref, str):
            raise ProtocolError("precondition_failed", "agent-control Beads context requires an assignment job ref")
        _resource, values, canonical_job_ref = self._resource_reference(
            job_ref, {"job"}, "agent-control assignment requires a canonical job reference"
        )
        job = self._sinnixd_job("job.get", {"job_id": values["job_id"]})
        binding = job.get("contract", {}).get("bead_binding")
        checkout = job.get("checkout")
        if (
            job.get("principal") != "agent-control"
            or not isinstance(binding, Mapping)
            or binding.get("bead_ref") != bead_ref
            or binding.get("project_ref") != REGISTRY.reference("project", {"project_id": project_id})
            or not isinstance(checkout, Mapping)
            or not isinstance(checkout.get("checkout_id"), str)
            or binding.get("checkout_ref") != REGISTRY.reference(
                "checkout", {"project_id": project_id, "checkout_id": checkout["checkout_id"]}
            )
        ):
            raise ProtocolError("precondition_failed", "job is not the requested agent-control Beads assignment")
        if bead is not None:
            self._assert_assignment_current(binding, bead)
        return job, binding, dict(checkout), canonical_job_ref

    @staticmethod
    def _assert_assignment_current(binding: Mapping[str, Any], bead: Mapping[str, Any]) -> None:
        if (
            binding.get("task_revision") != bead.get("task_revision")
            or binding.get("task_etag") != bead.get("etag")
        ):
            raise ProtocolError("precondition_failed", "agent-control Beads assignment is stale")

    def _review_evidence(self, job_id: str, job: Mapping[str, Any]) -> dict[str, Any]:
        artifacts = job.get("artifacts")
        declared_result = artifacts.get("result") if isinstance(artifacts, Mapping) else None
        tests = {
            "availability": "unavailable",
            "reason": "bead-bound attested-agent jobs declare no structured test result",
        }
        if not isinstance(declared_result, Mapping):
            return {
                "result": {"availability": "unavailable", "reason": "job declares no result artifact"},
                "tests": tests,
            }
        try:
            observed = self._sinnixd_job("job.result", {"job_id": job_id, "max_bytes": 64_000})
        except ProtocolError as exc:
            return {
                "result": {
                    "availability": "unavailable",
                    "artifact": dict(declared_result),
                    "failure_code": exc.code,
                },
                "tests": tests,
            }
        if observed.get("job_id") != job_id:
            raise ProtocolError("owner_failed", "sinnixd result response does not match the reviewed job")
        artifact = observed.get("artifact")
        if not isinstance(artifact, Mapping) or artifact.get("ref") != declared_result.get("ref"):
            raise ProtocolError("owner_failed", "sinnixd result does not match the declared job artifact")
        return {
            "result": {
                "availability": "available",
                "artifact": dict(declared_result),
                "observation": observed,
            },
            "tests": tests,
        }

    def v2_run_for_bead(
        self,
        *,
        reference: str | None,
        checkout_id: str | None,
        claim_mode: str,
        assignment_ref: str | None,
        instructions: str | None,
        backend: str | None,
        model: str | None,
        reasoning_effort: str | None,
        timeout_seconds: int,
        credential_profile: str,
        request_id: str | None,
    ) -> dict[str, Any]:
        self.principal.require(Capability.JOB_START)
        if self.principal.name not in {"agent-control", "operator"}:
            raise PolicyError("bead-bound agent jobs require agent-control or operator authority")
        if not isinstance(request_id, str):
            raise ProtocolError("invalid_request", "bead-bound agent launch requires request_id")
        _resource, values, bead_ref = self._resource_reference(
            reference or "", {"bead"}, "bead-bound agent launch requires a canonical Beads reference"
        )
        if not isinstance(checkout_id, str) or not checkout_id:
            raise ProtocolError("invalid_request", "bead-bound agent launch requires an explicit checkout_id")
        if claim_mode not in {"none", "claim"}:
            raise ProtocolError("invalid_request", "claim_mode must be none or claim")
        project_id, bead_id = values["project_id"], values["bead_id"]
        checkout = self.projects.checkout(project_id, checkout_id)["checkout"]
        project_ref = REGISTRY.reference("project", {"project_id": project_id})
        checkout_ref = REGISTRY.reference("checkout", {"project_id": project_id, "checkout_id": checkout_id})
        claim_receipt: dict[str, Any] | None = None
        claim_ref: str | None = None
        parent_assignment_ref: str | None = None
        if self.principal.name == "agent-control":
            if claim_mode != "none":
                raise PolicyError("agent-control cannot claim Beads tasks")
            _assignment_job, binding, assigned_checkout, parent_assignment_ref = self._assigned_bead_job(
                bead_ref, project_id, None, assignment_ref
            )
            if assigned_checkout["checkout_id"] != checkout_id or binding.get("checkout_ref") != checkout_ref:
                raise ProtocolError("precondition_failed", "agent-control launch must use its assigned checkout")
        bead = self.beads.get(project_id, bead_id, includes=["blockers", "dependencies", "dependents", "children", "refs"])
        if self.principal.name == "agent-control":
            self._assert_assignment_current(binding, bead)
        if claim_mode == "claim":
            claim = self.beads.change(
                project_id,
                "claim",
                {"id": bead_id},
                preconditions={
                    "expected_task_revision": bead["task_revision"],
                    "expected_etag": bead["etag"],
                },
            )
            after = claim.get("after")
            if not isinstance(after, Mapping):
                raise ProtocolError("owner_failed", "Beads claim omitted its after state")
            bead = dict(after)
            claim_ref = f"{bead_ref}/claims/{bead['etag']}"
            claim_receipt = {
                "ref": claim_ref,
                "owner_route": claim.get("owner_route"),
                "before_revision": claim.get("before_revision"),
                "after_revision": claim.get("after_revision"),
                "owner_history_ref": claim.get("owner_history_ref"),
            }
        binding = {
            "bead_ref": bead_ref,
            "project_ref": project_ref,
            "checkout_ref": checkout_ref,
            "task_revision": bead["task_revision"],
            "task_etag": bead["etag"],
            "claim_ref": claim_ref,
            "claim_receipt": claim_receipt,
            "request_id": request_id,
            "assignment_ref": parent_assignment_ref,
        }
        metadata = bead.get("metadata")
        encoded_scope = metadata.get("write_scope") if isinstance(metadata, Mapping) else None
        if isinstance(encoded_scope, str):
            try:
                write_scope = json.loads(encoded_scope)
            except json.JSONDecodeError as error:
                raise ProtocolError("invalid_request", "Bead write_scope metadata must be a JSON array") from error
            if not isinstance(write_scope, list):
                raise ProtocolError("invalid_request", "Bead write_scope metadata must be a JSON array")
            binding["write_scope"] = write_scope
        assigned_context = {
            "bead": bead,
            "project_ref": project_ref,
            "checkout_ref": checkout_ref,
            "worker_authority": "task.read only; task mutation and closure require an explicit operator call",
        }
        prompt = (
            "Work the assigned canonical Beads task. Read the supplied context, make and verify the requested code change in the assigned checkout, and report evidence plus residuals. Do not mutate or close Beads.\n\n"
            + json.dumps(assigned_context, sort_keys=True, separators=(",", ":"))
            + ("\n\nOperator instructions:\n" + instructions if isinstance(instructions, str) and instructions else "")
        )
        request = AgentLaunchRequest(
            project_id=project_id,
            checkout_id=checkout_id,
            prompt=prompt,
            backend=backend,
            model=model,
            reasoning_effort=reasoning_effort,
            timeout_seconds=timeout_seconds,
            credential_profile=credential_profile,
        )
        try:
            result = self._sinnixd_job(
                "job.agent.start",
                {
                    "project_id": request.project_id,
                    "checkout_id": request.checkout_id,
                    "prompt": request.prompt,
                    "backend": request.backend,
                    "model": request.model,
                    "effort": request.reasoning_effort,
                    "credential_profile": request.credential_profile,
                    "timeout_seconds": request.timeout_seconds,
                    "result": "last-message",
                    "bead_binding": binding,
                },
                principal="agent-control",
            )
        except ProtocolError as exc:
            if claim_ref is None:
                raise
            raise ProtocolError(
                "partial_completion",
                "Beads claim succeeded but agent launch failed",
                details={
                    "bead_ref": bead_ref,
                    "project_ref": project_ref,
                    "checkout_ref": checkout_ref,
                    "claim_ref": claim_ref,
                    "claim_receipt": claim_receipt,
                    "request_id": request_id,
                    "launch_error": {
                        "code": exc.code,
                        "details": exc.details,
                    },
                },
            ) from exc
        if result.get("state", {}).get("phase") == "launch-failed":
            job_id = result.get("job_id")
            launch_details = {
                "bead_ref": bead_ref,
                "project_ref": project_ref,
                "checkout_ref": checkout_ref,
                "claim_ref": claim_ref,
                "claim_receipt": claim_receipt,
                "request_id": request_id,
            }
            if isinstance(job_id, str) and job_id:
                launch_details["job_ref"] = REGISTRY.reference("job", {"job_id": job_id})
            raise ProtocolError(
                "partial_completion" if claim_ref else "owner_failed",
                "Beads claim succeeded but agent launch failed"
                if claim_ref
                else "agent launch failed",
                details=launch_details,
            )
        job_id = result.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise ProtocolError("owner_failed", "sinnixd bead-agent start response omitted the job ID")
        return {
            **result,
            "ref": REGISTRY.reference("job", {"job_id": job_id}),
            "bead_ref": bead_ref,
            "project_ref": project_ref,
            "checkout_ref": checkout_ref,
            "claim_ref": claim_ref,
            "claim_receipt": claim_receipt,
            "assignment_ref": parent_assignment_ref,
            "atomicity": "native_claim_then_daemon_launch" if claim_ref else "daemon_launch",
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
                row["ref"] = REGISTRY.reference("receipt", {"receipt_id": event["event_id"]})
            elif isinstance(event.get("subject_ref"), str):
                row["ref"] = event["subject_ref"]
            rows.append(row)
        result["events"] = rows
        return result

    def v2_get(
        self,
        reference: str,
        projection: str = "summary",
        offset: int = 0,
        max_bytes: int = 64_000,
        includes: list[str] | None = None,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        try:
            resource, values = REGISTRY.resolve(reference)
        except RegistryError as exc:
            raise ProtocolError("not_found", "canonical resource was not found") from exc
        canonical_ref = str(resource.ref_template.format(values))
        if self.principal.name not in resource.principals:
            raise PolicyError(f"principal {self.principal.name} cannot read {resource.kind} resources")
        if projection not in {"summary", "log", "result"}:
            raise ProtocolError("invalid_request", "resource projection is not recognized")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ProtocolError("invalid_request", "resource offset is malformed")
        if (
            not isinstance(max_bytes, int)
            or isinstance(max_bytes, bool)
            or not 1 <= max_bytes <= 262_144
        ):
            raise ProtocolError("invalid_request", "resource max_bytes must be 1-262144")
        if resource.kind != "job" and projection != "summary":
            raise ProtocolError(
                "invalid_request", "resource projection requires a canonical job reference"
            )
        if resource.kind == "project":
            return {
                "ref": canonical_ref,
                "kind": resource.kind,
                **self.project_authority(values["project_id"]),
            }
        if resource.kind == "checkout":
            return {
                "ref": canonical_ref,
                "kind": resource.kind,
                "checkout": self.projects.checkout(
                    values["project_id"], values["checkout_id"]
                ),
            }
        if resource.kind == "bead":
            return {
                "ref": canonical_ref,
                "kind": resource.kind,
                "bead": self.beads.get(values["project_id"], values["bead_id"], includes=includes, as_of=as_of),
            }
        if resource.kind == "task_authority":
            return {
                "ref": canonical_ref,
                "kind": resource.kind,
                "task_authority": self.beads.task_authority_status(
                    values["project_id"]
                ),
            }
        if resource.kind == "job":
            job_id = values["job_id"]
            self.principal.require(Capability.JOB_READ)
            if projection == "summary":
                result = self._sinnixd_job("job.get", {"job_id": job_id})
            elif projection == "log":
                result = self._sinnixd_job(
                    "job.logs",
                    {"job_id": job_id, "offset": offset, "max_bytes": max_bytes},
                )
            else:
                if offset:
                    raise ProtocolError("invalid_request", "job result does not support offsets")
                result = self._sinnixd_job(
                    "job.result", {"job_id": job_id, "max_bytes": max_bytes}
                )
            if result.get("job_id") != job_id:
                raise ProtocolError(
                    "owner_failed", "sinnixd get response does not match the requested job"
                )
            return {
                "ref": canonical_ref,
                "kind": resource.kind,
                "projection": projection,
                "job": result,
            }
        if resource.kind == "artifact":
            return {
                "ref": canonical_ref,
                "kind": resource.kind,
                "artifact": self.artifacts.read(values["artifact_id"], offset, max_bytes),
            }
        if resource.kind == "receipt":
            return {
                "ref": canonical_ref,
                "kind": resource.kind,
                "receipt": self.audit.receipt(values["receipt_id"]),
            }
        if resource.kind == "result":
            return {
                "ref": canonical_ref,
                "kind": resource.kind,
                "result": self.results.read(values["result_id"]),
            }
        if resource.kind == "machine_unit":
            page = self.observe.machine_query("units", limit=500)
            rows = page.get("rows") if isinstance(page, Mapping) else None
            if not isinstance(rows, list):
                raise ProtocolError("unavailable", "machine unit owner is unavailable")
            unit = next(
                (
                    row for row in rows
                    if isinstance(row, Mapping)
                    and row.get("unit") == values["unit"]
                    and row.get("manager", values["manager"]) == values["manager"]
                ),
                None,
            )
            if unit is None:
                raise ProtocolError("not_found", "machine unit is not in the current bounded owner page")
            return {"ref": canonical_ref, "kind": resource.kind, "unit": dict(unit), "source": page.get("source")}
        if resource.kind == "process":
            page = self.observe.machine_query("workloads", limit=500)
            rows = page.get("rows") if isinstance(page, Mapping) else None
            if not isinstance(rows, list):
                raise ProtocolError("unavailable", "process owner is unavailable")
            process = next(
                (
                    row for row in rows
                    if isinstance(row, Mapping)
                    and str(row.get("pid")) == values["pid"]
                    and str(row.get("start_ticks", row.get("start_time", ""))) == values["start_ticks"]
                ),
                None,
            )
            if process is None:
                raise ProtocolError("not_found", "process is not in the current bounded owner page")
            return {"ref": canonical_ref, "kind": resource.kind, "process": dict(process), "source": page.get("source")}
        if resource.kind == "browser_page":
            return {"ref": canonical_ref, "kind": resource.kind, "page": self.browser.describe_target(values["page_id"])}
        if resource.kind == "browser_workspace":
            return {"ref": canonical_ref, "kind": resource.kind, "workspace": self.browser.read("status")}
        if resource.kind == "terminal":
            return {
                "ref": canonical_ref,
                "kind": resource.kind,
                "terminal": self.terminals.read("capture", {"match": f"id:{values['terminal_id']}", "extent": "last_non_empty_output"}),
            }
        if resource.kind == "desktop":
            return {"ref": canonical_ref, "kind": resource.kind, "desktop": self.desktop.read("status")}
        if resource.kind == "host_file":
            return {
                "ref": canonical_ref,
                "kind": resource.kind,
                "file": self.files.read("stat", self._decode_file_token(values["file_token"])),
            }
        if resource.kind == "mcp_tool":
            return {
                "ref": canonical_ref,
                "kind": resource.kind,
                "tool": {
                    "server": values["server"],
                    "name": values["tool"],
                    "availability": "unavailable",
                    "reason": "live MCP tool metadata requires an asynchronous owner read",
                },
            }
        if resource.kind == "capture_lane":
            return {"ref": canonical_ref, "kind": resource.kind, "lane": self.captures.lane(values["lane"])}
        if resource.kind == "capability":
            return {"ref": canonical_ref, "kind": resource.kind, "capability": self.capability_index.describe(values["name"])}
        if resource.kind == "session":
            return {
                "ref": canonical_ref,
                "kind": resource.kind,
                "session": self.sessions.read(f"{values['provider']}:{values['session_id']}", offset, max_bytes),
            }
        if resource.kind == "context_snapshot":
            if self.context_snapshots is None:
                raise ProtocolError("unavailable", "context snapshot store is unavailable")
            try:
                snapshot = self.context_snapshots.get(values["snapshot_id"])
            except KeyError as exc:
                raise ProtocolError("not_found", "context snapshot is not retained") from exc
            return {"ref": canonical_ref, "kind": resource.kind, "snapshot": snapshot}
        raise ValueError(f"V2 get does not support resource kind {resource.kind!r}")

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
        result = self._sinnixd_job(
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
            raise ProtocolError("owner_failed", "sinnixd start response omitted the job ID")
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
            raise PolicyError("declared operations require agent-control or operator principal")
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
        result = self._sinnixd_job("job.start", arguments)
        job_id = result.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise ProtocolError("owner_failed", "sinnixd declared-operation start response omitted the job ID")
        return {**result, "ref": REGISTRY.reference("job", {"job_id": job_id})}

    @staticmethod
    def _required_preconditions(
        preconditions: Mapping[str, Any] | None,
        allowed: set[str],
    ) -> dict[str, Any]:
        if not isinstance(preconditions, Mapping) or not preconditions:
            raise ProtocolError("precondition_failed", "mutation requires preconditions")
        values = dict(preconditions)
        if set(values) - allowed:
            raise ProtocolError("invalid_request", "mutation preconditions are not recognized")
        return values

    def _project_change_preconditions(
        self,
        project_id: str,
        checkout_id: str | None,
        preconditions: Mapping[str, Any] | None,
    ) -> str:
        values = self._required_preconditions(preconditions, {"head", "dirty_sha256"})
        selected_checkout = checkout_id or "default"
        checkout = self.projects.checkout(project_id, selected_checkout)["checkout"]
        for name, expected in values.items():
            if not isinstance(expected, str) or checkout.get(name) != expected:
                raise ProtocolError(
                    "precondition_failed", f"project checkout {name} no longer matches"
                )
        return selected_checkout

    def v2_change(
        self,
        *,
        reference: str,
        operation: str,
        path: str | None,
        content: str | None,
        patch: str | None,
        preconditions: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        project_id, checkout_id, canonical_ref = self._project_reference(
            reference, allow_checkout=True
        )
        selected_checkout = self._project_change_preconditions(
            project_id, checkout_id, preconditions
        )
        if operation == "write":
            if not isinstance(path, str) or not path or not isinstance(content, str):
                raise ProtocolError("invalid_request", "write requires path and content")
            if patch is not None:
                raise ProtocolError("invalid_request", "write does not accept patch")
            try:
                result = self.projects.write(
                    project_id,
                    path,
                    content,
                    selected_checkout,
                    preconditions,
                )
            except ProjectPreconditionError as exc:
                raise ProtocolError("precondition_failed", str(exc)) from exc
        elif operation == "apply_patch":
            if not isinstance(patch, str) or not patch:
                raise ProtocolError("invalid_request", "apply_patch requires patch")
            if path is not None or content is not None:
                raise ProtocolError("invalid_request", "apply_patch does not accept path or content")
            try:
                result = self.projects.apply_patch(
                    project_id,
                    patch,
                    selected_checkout,
                    preconditions,
                )
            except ProjectPreconditionError as exc:
                raise ProtocolError("precondition_failed", str(exc)) from exc
        else:
            raise ProtocolError("invalid_request", "project change operation is not recognized")
        return {
            "ref": canonical_ref,
            "project_ref": REGISTRY.reference("project", {"project_id": project_id}),
            "checkout_ref": REGISTRY.reference(
                "checkout", {"project_id": project_id, "checkout_id": selected_checkout}
            ),
            "operation": operation,
            "owner_result": result,
        }

    @staticmethod
    def _parameters(value: Mapping[str, Any] | None) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise ProtocolError("invalid_request", "parameters must be an object")
        return dict(value)

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
    def _decode_file_token(token: str) -> str:
        try:
            padded = token + "=" * (-len(token) % 4)
            path = base64.b64decode(
                padded.encode(), altchars=b"-_", validate=True
            ).decode("utf-8")
        except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
            raise ProtocolError("invalid_request", "file reference is malformed") from exc
        if not path or len(path) > 4_096 or not path.startswith("/"):
            raise ProtocolError("invalid_request", "file reference is malformed")
        return path

    def v2_file_change(
        self,
        *,
        reference: str,
        operation: str,
        parameters: Mapping[str, Any] | None,
        preconditions: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        _resource, values, canonical_ref = self._resource_reference(
            reference, {"host_file"}, "ref does not identify a canonical host file"
        )
        arguments = self._parameters(parameters)
        allowed = {
            "append": {"content"},
            "copy": {"destination_ref"},
            "mkdir": set(),
            "move": {"destination_ref"},
            "remove": set(),
            "replace": {"content"},
        }
        if operation not in allowed:
            raise ProtocolError("unsupported_capability", "file operation is not declared")
        if set(arguments) - allowed[operation]:
            raise ProtocolError("invalid_request", "file parameters are not valid for this operation")
        if operation in {"append", "replace"} and not isinstance(
            arguments.get("content"), str
        ):
            raise ProtocolError("invalid_request", "file operation requires content")
        destination: str | None = None
        if operation in {"copy", "move"}:
            destination_ref = arguments.get("destination_ref")
            if not isinstance(destination_ref, str):
                raise ProtocolError("invalid_request", "file operation requires destination_ref")
            _destination, destination_values, _ = self._resource_reference(
                destination_ref,
                {"host_file"},
                "destination_ref does not identify a canonical host file",
            )
            destination = self._decode_file_token(destination_values["file_token"])
        expected_sha256: str | None = None
        if preconditions is not None:
            if not isinstance(preconditions, Mapping) or set(preconditions) - {"expected_sha256"}:
                raise ProtocolError("invalid_request", "file preconditions are not recognized")
            value = preconditions.get("expected_sha256")
            if value is not None and (
                not isinstance(value, str) or len(value) != 64
            ):
                raise ProtocolError("invalid_request", "expected_sha256 is malformed")
            expected_sha256 = value
        result = self.files.write(
            operation,
            self._decode_file_token(values["file_token"]),
            content=arguments.get("content"),
            destination=destination,
            expected_sha256=expected_sha256,
        )
        response = {"ref": canonical_ref, **result}
        if destination is not None:
            destination_token = base64.urlsafe_b64encode(destination.encode()).decode().rstrip("=")
            response["destination_ref"] = REGISTRY.reference(
                "host_file", {"file_token": destination_token}
            )
        return response

    def v2_beads_query(self, parameters: Mapping[str, Any]) -> dict[str, Any]:
        if self.principal.name == "agent-control":
            raise PolicyError("agent-control Beads reads require an assigned Beads context")
        values = self._parameters(parameters)
        graph = values.pop("graph", None)
        memory = values.pop("memory", None)
        if graph is not None:
            projects = values.pop("project_ids", None)
            if not isinstance(graph, Mapping) or not isinstance(projects, list) or len(projects) != 1:
                raise ProtocolError("invalid_request", "Beads graph requires one project_id and graph object")
            return self.beads.graph(projects[0], **dict(graph))
        if memory is not None:
            projects = values.pop("project_ids", None)
            if not isinstance(memory, Mapping) or not isinstance(projects, list) or len(projects) != 1:
                raise ProtocolError("invalid_request", "Beads memory requires one project_id and memory object")
            return self.beads.memories(projects[0], **dict(memory))
        return self.beads.query(**values)

    def v2_beads_change(
        self,
        *,
        reference: str,
        operation: str,
        parameters: Mapping[str, Any] | None,
        preconditions: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        resource, values, canonical_ref = self._resource_reference(
            reference, {"project", "bead"}, "ref does not identify a canonical project or bead"
        )
        mutation = self._parameters(parameters)
        if operation == "close_with_evidence":
            if resource.kind != "bead":
                raise ProtocolError("invalid_request", "close_with_evidence requires a canonical Beads ref")
            result = self._close_with_evidence(values["project_id"], values["bead_id"], canonical_ref, mutation)
            return {"ref": canonical_ref, **result}
        if resource.kind == "bead":
            mutation.setdefault("id", values["bead_id"])
        result = self.beads.change(
            values["project_id"], operation, mutation,
            mode=str(mutation.pop("mode", "apply")),
            preconditions=preconditions,
            preview_digest=mutation.pop("preview_digest", None),
        )
        return {"ref": canonical_ref, **result}

    def _close_with_evidence(
        self, project_id: str, bead_id: str, bead_ref: str, values: Mapping[str, Any]
    ) -> dict[str, Any]:
        required = {
            "verdict",
            "residuals",
            "evidence_refs",
            "job_ref",
            "code_revision",
            "task_revision",
            "task_etag",
        }
        if set(values) != required:
            raise ProtocolError("invalid_request", "close_with_evidence requires a complete evidence record")
        job_ref = values["job_ref"]
        _resource, job_values, canonical_job_ref = self._resource_reference(
            job_ref, {"job"}, "close_with_evidence requires a canonical job ref"
        )
        job = self._sinnixd_job("job.get", {"job_id": job_values["job_id"]})
        if job.get("state", {}).get("phase") != "succeeded":
            raise ProtocolError("precondition_failed", "failed or cancelled jobs cannot close a bead")
        binding = job.get("contract", {}).get("bead_binding")
        if not isinstance(binding, Mapping) or binding.get("bead_ref") != bead_ref:
            raise ProtocolError("precondition_failed", "job is not bound to the requested bead")
        checkout = job.get("checkout")
        if not isinstance(checkout, Mapping) or not isinstance(checkout.get("checkout_id"), str):
            raise ProtocolError("owner_failed", "bead-bound job omitted its checkout identity")
        current_checkout = self.projects.checkout(project_id, checkout["checkout_id"])["checkout"]
        if values["code_revision"] != current_checkout.get("head"):
            raise ProtocolError("precondition_failed", "code_revision does not match the current checkout")
        current = self.beads.get(project_id, bead_id)
        if values["task_revision"] != current.get("task_revision") or values["task_etag"] != current.get("etag"):
            raise ProtocolError("precondition_failed", "task revision does not match the current bead")
        if not isinstance(values["residuals"], list) or not isinstance(values["evidence_refs"], list):
            raise ProtocolError("invalid_request", "closure residuals and evidence_refs must be lists")
        evidence = {
            "schema": "sinnix.bead-close-evidence.v1",
            "verdict": values["verdict"],
            "residuals": values["residuals"],
            "evidence_refs": values["evidence_refs"],
            "job_ref": canonical_job_ref,
            "code_revision": values["code_revision"],
            "task_revision": values["task_revision"],
            "task_etag": values["task_etag"],
            "launch_code_revision": checkout.get("head"),
            "launch_task_revision": binding.get("task_revision"),
            "launch_task_etag": binding.get("task_etag"),
        }
        mutation = self.beads.change(
            project_id,
            "close",
            {
                "id": bead_id,
                "reason": json.dumps(evidence, sort_keys=True, separators=(",", ":")),
                "force": True,
            },
            preconditions={"expected_task_revision": current["task_revision"], "expected_etag": current["etag"]},
        )
        return {"closure": evidence, "bead": mutation}

    def v2_beads_changeset(
        self,
        *,
        reference: str,
        operation: str,
        parameters: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        _resource, values, canonical_ref = self._resource_reference(
            reference, {"project"}, "ref does not identify a canonical project"
        )
        mutation = self._parameters(parameters)
        actions = mutation.pop("actions", None)
        if not isinstance(actions, list) or not actions:
            raise ProtocolError("invalid_request", "Beads changeset requires ordered actions")
        first = actions[0]
        if not isinstance(first, Mapping) or first.get("ref") != canonical_ref:
            raise ProtocolError("invalid_request", "changeset ref must anchor its first action")
        result = self.beads.changeset(
            actions,
            mode=operation,
            on_error=mutation.pop("on_error", None),
            preview_digest=mutation.pop("preview_digest", None),
        )
        if mutation:
            raise ProtocolError("invalid_request", "Beads changeset received unsupported parameters")
        return {"ref": canonical_ref, **result}

    def v2_beads_operate(
        self,
        *,
        reference: str,
        operation: str,
        parameters: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        _resource, values, canonical_ref = self._resource_reference(
            reference, {"project"}, "ref does not identify a canonical project"
        )
        return {"ref": canonical_ref, **self.beads.operate(values["project_id"], operation, self._parameters(parameters))}

    async def v2_mcp_change(
        self,
        *,
        reference: str,
        operation: str,
        parameters: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        _resource, values, canonical_ref = self._resource_reference(
            reference, {"mcp_tool"}, "ref does not identify a canonical MCP tool"
        )
        if operation != "call":
            raise ProtocolError("unsupported_capability", "MCP operation is not declared")
        result = await self.mcp_broker.call(
            values["server"], values["tool"], self._parameters(parameters), write=True
        )
        return {"ref": canonical_ref, **result}

    def v2_desktop_operate(
        self, *, reference: str, operation: str, parameters: Mapping[str, Any] | None
    ) -> dict[str, Any]:
        _resource, _values, canonical_ref = self._resource_reference(
            reference, {"desktop"}, "ref does not identify the canonical desktop"
        )
        return {"ref": canonical_ref, **self.desktop.action(operation, self._parameters(parameters))}

    def v2_terminal_operate(
        self, *, reference: str, operation: str, parameters: Mapping[str, Any] | None
    ) -> dict[str, Any]:
        _resource, values, canonical_ref = self._resource_reference(
            reference, {"terminal"}, "ref does not identify a canonical terminal"
        )
        arguments = self._parameters(parameters)
        if "match" in arguments:
            raise ProtocolError("invalid_request", "terminal match is derived from the canonical ref")
        return {
            "ref": canonical_ref,
            **self.terminals.action(
                operation, {"match": f"id:{values['terminal_id']}", **arguments}
            ),
        }

    def v2_browser_operate(
        self, *, reference: str, operation: str, parameters: Mapping[str, Any] | None
    ) -> dict[str, Any]:
        resource, values, canonical_ref = self._resource_reference(
            reference,
            {"browser_workspace", "browser_page"},
            "ref does not identify a canonical browser target",
        )
        arguments = self._parameters(parameters)
        if operation == "agent_window":
            if resource.kind != "browser_workspace":
                raise ProtocolError("invalid_request", "agent_window requires the browser workspace ref")
        else:
            if resource.kind != "browser_page":
                raise ProtocolError("invalid_request", "browser operation requires a gateway-owned page ref")
            if "page_id" in arguments:
                raise ProtocolError("invalid_request", "browser page_id is derived from the canonical ref")
            arguments = {"page_id": values["page_id"], **arguments}
        result = self.browser.action(operation, arguments)
        response = {"ref": canonical_ref, **result}
        target = result.get("target")
        if isinstance(target, Mapping) and isinstance(target.get("id"), str):
            response["target_ref"] = REGISTRY.reference(
                "browser_page", {"page_id": target["id"]}
            )
        return response

    def _machine_target(self, reference: str) -> tuple[str, dict[str, Any]]:
        try:
            resource, values = REGISTRY.resolve(reference)
        except RegistryError as exc:
            raise ProtocolError("not_found", "canonical machine target was not found") from exc
        canonical_ref = str(resource.ref_template.format(values))
        if resource.kind == "job":
            return canonical_ref, {"job_id": values["job_id"]}
        if resource.kind == "machine_unit":
            if values["manager"] not in {"user", "system"}:
                raise ProtocolError("invalid_request", "machine unit manager is not recognized")
            return canonical_ref, {"unit": values["unit"]}
        if resource.kind == "process":
            try:
                pid = int(values["pid"])
                start_ticks = int(values["start_ticks"])
            except ValueError as exc:
                raise ProtocolError("invalid_request", "process reference is malformed") from exc
            if pid <= 1 or start_ticks < 0:
                raise ProtocolError("invalid_request", "process reference is malformed")
            return canonical_ref, {"process": {"pid": pid, "start_ticks": start_ticks}}
        raise ProtocolError("invalid_request", "reference does not identify an operable machine target")

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
                "owner_failed", "ops reducer receipt does not match the submitted action"
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
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise ProtocolError("invalid_request", "expected_revision must be a non-negative integer")
        if not isinstance(action, str) or action not in MACHINE_OPERATIONS:
            raise ProtocolError("invalid_request", "machine action is not recognized")
        if not isinstance(parameters, Mapping):
            raise ProtocolError("invalid_request", "machine parameters must be an object")
        if not isinstance(reason, str) or not reason:
            raise ProtocolError("invalid_request", "machine operation requires reason")
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise ProtocolError("invalid_request", "machine operation requires idempotency_key")
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

    def v2_cancel_job(
        self,
        *,
        reference: str,
        preconditions: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            resource, values = REGISTRY.resolve(reference)
        except RegistryError as exc:
            raise ProtocolError("not_found", "canonical job resource was not found") from exc
        if resource.kind != "job":
            raise ProtocolError("invalid_request", "cancel requires a canonical job reference")
        expected_phase = self._required_preconditions(
            preconditions, {"expected_phase"}
        ).get("expected_phase")
        if not isinstance(expected_phase, str) or not expected_phase:
            raise ProtocolError("invalid_request", "expected_phase is malformed")
        job_id = values["job_id"]
        self.principal.require(Capability.JOB_CANCEL)
        status = self._sinnixd_job("job.get", {"job_id": job_id})
        if status.get("job_id") != job_id:
            raise ProtocolError(
                "owner_failed", "sinnixd status response does not match the requested job"
            )
        state = status.get("state")
        phase = state.get("phase") if isinstance(state, Mapping) else None
        if phase != expected_phase:
            raise ProtocolError("precondition_failed", "job phase no longer matches")
        cancelled = self._sinnixd_job("job.cancel", {"job_id": job_id})
        if cancelled.get("job_id") != job_id or not isinstance(
            cancelled.get("cancel_requested"), bool
        ):
            raise ProtocolError(
                "owner_failed", "sinnixd cancel response does not prove cancellation truth"
            )
        return {
            "ref": str(resource.ref_template.format(values)),
            "previous_state": status,
            "cancel": cancelled,
        }

    def v2_wait(
        self,
        reference: str,
        timeout_seconds: int,
        target: str = "job_terminal",
        expected: Mapping[str, Any] | None = None,
        poll_seconds: float = 0.25,
    ) -> dict[str, Any]:
        if not isinstance(reference, str) or not 1 <= len(reference) <= 2_048:
            raise ProtocolError("invalid_request", "wait ref is malformed")
        if (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or not 1 <= timeout_seconds <= 300
        ):
            raise ProtocolError(
                "invalid_request", "wait timeout_seconds must be between 1 and 300"
            )
        try:
            resource, values = REGISTRY.resolve(reference)
        except RegistryError as exc:
            raise ProtocolError("not_found", "canonical job resource was not found") from exc
        try:
            wait_target = WaitTarget(target)
        except ValueError as exc:
            raise ProtocolError("invalid_request", "wait target is not recognized") from exc
        if wait_target is WaitTarget.JOB_TERMINAL:
            if resource.kind != "job":
                raise ProtocolError("invalid_request", "job_terminal requires a canonical job reference")
            job_id = values["job_id"]
            self.principal.require(Capability.JOB_READ)
            result = self._sinnixd_job(
                "job.wait", {"job_id": job_id, "timeout_seconds": timeout_seconds}
            )
            if result.get("job_id") != job_id:
                raise ProtocolError(
                    "owner_failed", "sinnixd wait response does not match the requested job"
                )
            if result.get("timed_out") is True:
                evidence = result.get("state", result)
                result = {
                    **result,
                    "outcome": "timeout",
                    "evidence": evidence if isinstance(evidence, Mapping) else {"value": evidence},
                    "source_revision": source_revision(evidence),
                    "continuation": source_revision({"ref": reference, "evidence": evidence}),
                }
            return {**result, "ref": REGISTRY.reference("job", {"job_id": job_id}), "target": wait_target.value}
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
            return self.waits.wait(request)
        except ValueError as exc:
            raise ProtocolError("invalid_request", str(exc)) from exc

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
            raise ProtocolError("invalid_request", "wait target or reference is not recognized") from exc
        if wait_target is WaitTarget.JOB_TERMINAL:
            if resource.kind != "job":
                raise ProtocolError("invalid_request", "job_terminal requires a canonical job reference")
            self.principal.require(Capability.JOB_READ)
            if cancelled is not None and cancelled():
                return {"schema": "sinnix.gateway-wait.v1", "outcome": "cancelled", "target": wait_target.value, "ref": reference, "polls": 0, "evidence": {}, "source_revision": "cancelled", "continuation": source_revision({"ref": reference})}
            if cancelled is None:
                result = await anyio.to_thread.run_sync(
                    self._sinnixd_job,
                    "job.wait",
                    {"job_id": values["job_id"], "timeout_seconds": timeout_seconds},
                    abandon_on_cancel=True,
                )
            else:
                result_box: dict[str, Any] = {}
                request_cancelled = False

                async def wait_for_owner() -> None:
                    result_box["result"] = await anyio.to_thread.run_sync(
                        self._sinnixd_job,
                        "job.wait",
                        {"job_id": values["job_id"], "timeout_seconds": timeout_seconds},
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
                    return {"schema": "sinnix.gateway-wait.v1", "outcome": "cancelled", "target": wait_target.value, "ref": reference, "polls": 0, "evidence": {}, "source_revision": "cancelled", "continuation": source_revision({"ref": reference})}
                result = result_box["result"]
            if cancelled is not None and cancelled():
                evidence = result.get("state", result)
                return {"schema": "sinnix.gateway-wait.v1", "outcome": "cancelled", "target": wait_target.value, "ref": reference, "polls": 0, "evidence": evidence if isinstance(evidence, Mapping) else {"value": evidence}, "source_revision": source_revision(evidence), "continuation": source_revision({"ref": reference, "evidence": evidence})}
            if result.get("job_id") != values["job_id"]:
                raise ProtocolError("owner_failed", "sinnixd wait response does not match the requested job")
            return {**result, "ref": REGISTRY.reference("job", {"job_id": values["job_id"]}), "target": wait_target.value}
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
        if request.target is WaitTarget.BEAD_STATUS or request.target is WaitTarget.BEAD_REVISION:
            if resource.kind != "bead":
                raise ValueError("Beads waits require a canonical bead reference")
            bead = self.beads.get(values["project_id"], values["bead_id"])
            fields = bead.get("fields", {}) if isinstance(bead.get("fields"), Mapping) else {}
            current = fields.get("status") if request.target is WaitTarget.BEAD_STATUS else bead.get("task_revision")
            wanted = expected.get("status") if request.target is WaitTarget.BEAD_STATUS else expected.get("revision", expected.get("task_revision"))
            return WaitEvidence(current == wanted, {"current": current, "bead": bead}, str(bead.get("task_revision", source_revision(bead))))
        if request.target is WaitTarget.UNIT_STATE:
            if resource.kind != "machine_unit":
                raise ValueError("unit waits require a canonical machine unit reference")
            current = self.v2_get(request.reference)["unit"]
            state = current.get("active_state", current.get("state")) if isinstance(current, Mapping) else None
            wanted = expected.get("state", expected.get("active_state"))
            return WaitEvidence(state == wanted, {"state": state, "unit": current}, source_revision(current))
        if request.target is WaitTarget.FILE_HASH:
            if resource.kind != "host_file":
                raise ValueError("file waits require a canonical host file reference")
            current = self.files.read("stat", self._decode_file_token(values["file_token"]))
            wanted = expected.get("sha256") or expected.get("hash")
            return WaitEvidence(current.get("sha256") == wanted, current, str(current.get("sha256")))
        if request.target is WaitTarget.CAPTURE_FRESHNESS:
            if resource.kind != "capture_lane":
                raise ValueError("capture waits require a canonical capture lane reference")
            lane = self.captures.lane(values["lane"])
            path = Path(str(lane["path"]))
            mtime = path.stat().st_mtime if path.exists() else 0.0
            age = max(0.0, time.time() - mtime) if mtime else None
            max_age = float(expected.get("max_age_seconds", 0))
            return WaitEvidence(age is not None and age <= max_age, {"mtime": mtime, "age_seconds": age, "lane": lane}, source_revision({"mtime": mtime, "lane": lane.get("name")}))
        if request.target is WaitTarget.RECEIPT_APPEARANCE:
            if resource.kind != "receipt":
                raise ValueError("receipt waits require a canonical receipt reference")
            try:
                receipt = self.audit.receipt(values["receipt_id"])
            except ValueError:
                return WaitEvidence(False, {"available": False, "ref": request.reference}, "missing")
            return WaitEvidence(True, {"available": True, "receipt": receipt}, str(receipt["entry_hash"]))
        raise ValueError(f"wait target {request.target.value} is not implemented")

    def v2_jobs_query(self, parameters: Mapping[str, Any] | None) -> dict[str, Any]:
        values = self._parameters(parameters)
        if set(values) - {"limit", "cursor"}:
            raise ProtocolError("invalid_request", "jobs.query parameters are not recognized")
        limit = values.get("limit", 100)
        cursor = values.get("cursor")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1_000:
            raise ProtocolError("invalid_request", "jobs.query limit must be 1-1000")
        if cursor is not None and (
            not isinstance(cursor, str) or not 1 <= len(cursor.encode()) <= 512
        ):
            raise ProtocolError("invalid_request", "jobs.query cursor is malformed")
        self.principal.require(Capability.JOB_READ)
        arguments: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            arguments["cursor"] = cursor
        response = self._sinnixd_job("job.list", arguments)
        jobs = response.get("jobs")
        if not isinstance(jobs, list) or any(not isinstance(job, Mapping) for job in jobs):
            raise ProtocolError("owner_failed", "sinnixd job list response is malformed")
        if len(jobs) > limit:
            raise ProtocolError("owner_failed", "sinnixd job list response exceeds its bound")
        total = response.get("total")
        truncated = response.get("truncated")
        next_cursor = response.get("next_cursor")
        snapshot = response.get("snapshot")
        if (
            (total is not None and (not isinstance(total, int) or total < len(jobs)))
            or not isinstance(truncated, bool)
            or (
                next_cursor is not None
                and (
                    not isinstance(next_cursor, str)
                    or not 1 <= len(next_cursor.encode()) <= 512
                )
            )
            or not isinstance(snapshot, Mapping)
            or set(snapshot) != {"ordering", "ceiling"}
            or snapshot.get("ordering") != "created_at_desc_job_id_desc"
            or not isinstance(snapshot.get("ceiling"), list)
            or len(snapshot["ceiling"]) != 2
            or any(not isinstance(value, str) for value in snapshot["ceiling"])
        ):
            raise ProtocolError("owner_failed", "sinnixd job list response omits paging metadata")
        if truncated != (next_cursor is not None):
            raise ProtocolError("owner_failed", "sinnixd job list paging metadata is inconsistent")
        rows: list[dict[str, Any]] = []
        for job in jobs:
            job_id = job.get("job_id")
            if not isinstance(job_id, str) or not job_id:
                raise ProtocolError("owner_failed", "sinnixd job list response omitted a job ID")
            rows.append({"ref": REGISTRY.reference("job", {"job_id": job_id}), **job})
        return {
            "jobs": rows,
            "limit": limit,
            "total": total,
            "truncated": truncated,
            "next_cursor": next_cursor,
            "snapshot": dict(snapshot),
        }

    def _record_result(
        self, operation: str, result: Any, request_sha256: str | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if isinstance(result, dict):
            for key in (
                "job_id",
                "artifact_id",
                "project_id",
                "receipt_id",
                "unit",
                "path",
                "destination",
                "operation",
                "sha256",
                "previous_sha256",
                "bytes",
                "created",
                "removed",
                "identity",
                "exit_status",
                "timed_out",
                "truncated",
                "cwd",
                "accepted",
                "cancelled",
                "already_terminal",
                "kind",
                "server",
                "tool",
                "mode",
            ):
                value = result.get(key)
                if isinstance(value, (str, int, float, bool)):
                    payload[key] = value
            artifact_ids = result.get("artifact_ids")
            if isinstance(artifact_ids, list) and all(
                isinstance(value, str) for value in artifact_ids
            ):
                payload["artifact_ids"] = artifact_ids
            if "job_id" in payload:
                payload["correlation_id"] = payload["job_id"]
        if request_sha256 is not None:
            payload["request_sha256"] = request_sha256
        return self.audit.append(operation, "ok", payload)

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
        action: ActionSpec,
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
                if key in {"artifact_id", "diagnostic_artifact_id"} and isinstance(value, str):
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
            "owner_route": owner_route if isinstance(owner_route, str) else action.route,
            "owner_version": owner_version if isinstance(owner_version, (str, int)) else REGISTRY.revision,
            "preconditions": dict(context.preconditions or {}),
            "before_refs": before_refs,
            "after_refs": after_refs,
            "before_revision": before_revision,
            "after_revision": after_revision,
            "owner_history_ref": owner_history_ref if isinstance(owner_history_ref, str) else None,
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
            "compensation": result.get("compensation") if isinstance(result, Mapping) else None,
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
        for name, value in (("actor", actor), ("reason", reason), ("idempotency_key", idempotency_key)):
            if value is not None and (not isinstance(value, str) or not value):
                raise ProtocolError("invalid_request", f"{name} must be a non-empty string")
        if deadline_at is not None and not isinstance(deadline_at, (int, float)):
            raise ProtocolError("invalid_request", "deadline_at must be a Unix timestamp")
        if preconditions is not None and not isinstance(preconditions, Mapping):
            raise ProtocolError("invalid_request", "preconditions must be an object")
        try:
            encoded = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
        except (TypeError, ValueError) as exc:
            raise ProtocolError("invalid_request", "V2 request is not JSON serializable") from exc
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
        self, action: ActionSpec, result: Any, context: RequestContext
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
        action: ActionSpec,
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
        self, action: ActionSpec, context: RequestContext
    ) -> dict[str, Any] | None:
        if action.effect is EffectMode.READ:
            return None
        if not action.supports_idempotency:
            raise ProtocolError(
                "invalid_request", "mutating action does not declare idempotency support"
            )
        if context.idempotency_key is None:
            raise ProtocolError("invalid_request", "mutating action requires idempotency_key")
        state, response = self.audit.claim_idempotency(
            action.name, context.idempotency_key, context.request_sha256
        )
        if state == "new":
            return None
        if state == "replay":
            if not isinstance(response, dict):
                raise ProtocolError("unavailable", "stored idempotency response is malformed")
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
        self, action: ActionSpec, context: RequestContext, response: Mapping[str, Any]
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
        action: ActionSpec,
        callback: Callable[[], Any],
        request: Mapping[str, Any],
        *,
        selector_error: Exception | None = None,
    ) -> dict[str, Any]:
        context = RequestContext.create(hashlib.sha256(b"{}").hexdigest())
        reserved = False
        try:
            context = self._request_context(request)
            if selector_error is not None:
                raise selector_error
            if self.principal_name not in action.principals:
                raise PolicyError(
                    f"principal {self.principal_name!r} cannot invoke action {action.name!r}"
                )
            if context.preconditions and not action.supports_precondition:
                raise ProtocolError("invalid_request", "action does not support preconditions")
            if context.deadline_at is not None and time.time() >= context.deadline_at:
                raise ProtocolError("deadline", "request deadline elapsed before execution")
            replay = self._claim_v2_idempotency(action, context)
            if replay is not None:
                return replay
            reserved = action.effect is not EffectMode.READ
            response = self._v2_success(action, callback(), context)
        except Exception as exc:
            response = self._v2_failure(
                action,
                exc,
                context,
                enforce_action_failure_codes=selector_error is None,
            )
        if reserved:
            self._complete_v2_idempotency(action, context, response)
        return response

    async def execute_v2_async(
        self,
        action: ActionSpec,
        callback: Callable[[], Awaitable[Any]],
        request: Mapping[str, Any],
        *,
        selector_error: Exception | None = None,
    ) -> dict[str, Any]:
        context = RequestContext.create(hashlib.sha256(b"{}").hexdigest())
        reserved = False
        try:
            context = self._request_context(request)
            if selector_error is not None:
                raise selector_error
            if self.principal_name not in action.principals:
                raise PolicyError(
                    f"principal {self.principal_name!r} cannot invoke action {action.name!r}"
                )
            if context.preconditions and not action.supports_precondition:
                raise ProtocolError("invalid_request", "action does not support preconditions")
            if context.deadline_at is not None and time.time() >= context.deadline_at:
                raise ProtocolError("deadline", "request deadline elapsed before execution")
            replay = self._claim_v2_idempotency(action, context)
            if replay is not None:
                return replay
            reserved = action.effect is not EffectMode.READ
            response = self._v2_success(action, await callback(), context)
        except Exception as exc:
            response = self._v2_failure(
                action,
                exc,
                context,
                enforce_action_failure_codes=selector_error is None,
            )
        if reserved:
            self._complete_v2_idempotency(action, context, response)
        return response

    def execute_v2_jsonl(
        self,
        action: ActionSpec,
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
                raise ProtocolError("deadline", "request deadline elapsed before execution")
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
        except (OwnerDiagnosticError, ProtocolError, ResultError, PolicyError, ValueError) as exc:
            if writer is not None:
                writer.abort()
            return self._v2_failure(action, exc, context)

    def execute(self, operation: str, callback: Callable[[], T]) -> T:
        try:
            result = callback()
        except OwnerDiagnosticError as exc:
            self.audit.append(operation, "error", self._diagnostic_payload(exc.response))
            return cast(T, {"operation": operation, **exc.response})
        except Exception as exc:
            message = public_error(exc)
            self.audit.append(operation, "error", {"error": message})
            raise ValueError(message) from None
        self._record_result(operation, result)
        return result

    async def execute_async(
        self, operation: str, callback: Callable[[], Awaitable[T]]
    ) -> T:
        try:
            result = await callback()
        except OwnerDiagnosticError as exc:
            self.audit.append(operation, "error", self._diagnostic_payload(exc.response))
            return cast(T, {"operation": operation, **exc.response})
        except Exception as exc:
            message = public_error(exc)
            self.audit.append(operation, "error", {"error": message})
            raise ValueError(message) from None
        self._record_result(operation, result)
        return result


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
