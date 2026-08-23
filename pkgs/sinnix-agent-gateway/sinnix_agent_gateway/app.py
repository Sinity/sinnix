from __future__ import annotations

import base64
import binascii
import hashlib
import json
import time
from dataclasses import dataclass
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
from .contracts import ActionSpec, EffectMode, VerbFamily
from .desktop import DesktopService
from sinnix_mcp.execution import ExecutionProfile, OwnerDiagnosticError, OwnerExecution
from .files import HostFileService
from .machine_actions import MachineActionService
from .mcp_broker import McpBrokerService
from .memory import MemoryService
from .observe import ObserveService
from .project_context import ProjectContextService
from .projects import ProjectService
from .redaction import public_error
from .results import ProtocolError, RequestContext, ResultError, ResultService
from .route_preflight import GatewayRoutePreflight
from .registry import CatalogSearch, MACHINE_OPERATIONS, REGISTRY, RegistryError
from .schemas import AgentLaunchRequest, V2ToolEnvelope
from .sessions import SessionLogService
from .terminals import TerminalService
from .timeline import TimelineService
from sinnix_mcp import ErrorCode, RequestEnvelope
from sinnixd.api import SinnixdClient, SinnixdClientError

T = TypeVar("T")

DAEMON_ERROR_CLASSES = {
    ErrorCode.INVALID_ARGUMENT: "invalid_request",
    ErrorCode.POLICY_DENIED: "policy_denied",
    ErrorCode.OWNER_UNAVAILABLE: "unavailable",
    ErrorCode.AUTHORITY_MISMATCH: "policy_denied",
    ErrorCode.RESOURCE_DEFERRED: "unavailable",
    ErrorCode.RESOURCE_EXHAUSTED: "response_bound",
    ErrorCode.OPERATION_FAILED: "owner_failed",
    ErrorCode.RESULT_INVALID: "owner_failed",
}

READ_ONLY_TOOL = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
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


def canonical_manifest(tools: list[Any]) -> dict[str, Any]:
    rows = [
        tool.model_dump(by_alias=True, exclude_none=True, mode="json") for tool in tools
    ]
    rows.sort(key=lambda row: row["name"])
    payload = {"schema": "sinnix.gateway-tools.v1", "tools": rows}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["sha256"] = hashlib.sha256(encoded).hexdigest()
    return payload


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

    @classmethod
    def create(cls, config: GatewayConfig, principal_name: str) -> "Runtime":
        principal = Principal.for_name(principal_name)
        artifacts = ArtifactService(config, principal)
        sessions = SessionLogService(config, principal)
        projects = ProjectService(config, principal)
        beads = BeadsService(config, principal)
        return cls(
            principal_name=principal_name,
            principal=principal,
            config=config,
            projects=projects,
            project_context=ProjectContextService(principal, projects, beads),
            artifacts=artifacts,
            audit=AuditService(config, principal),
            results=ResultService(config, principal),
            sinnixd=SinnixdClient(config.sinnixd_socket),
            observe=ObserveService(config, principal),
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

    def v2_context(self, reference: str) -> dict[str, Any]:
        project_id, _checkout_id, canonical_ref = self._project_reference(
            reference, allow_checkout=False
        )
        return {"ref": canonical_ref, **self._bounded_project_context(project_id)}

    def v2_events(self, limit: int) -> dict[str, Any]:
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 1_000
        ):
            raise ProtocolError("invalid_request", "limit must be 1-1000")
        events = self.audit.tail(limit)["events"]
        return {
            "events": [
                {
                    "ref": REGISTRY.reference("receipt", {"receipt_id": event["event_id"]}),
                    **event,
                }
                for event in events
            ]
        }

    def v2_get(
        self,
        reference: str,
        projection: str = "summary",
        offset: int = 0,
        max_bytes: int = 64_000,
    ) -> dict[str, Any]:
        try:
            resource, values = REGISTRY.resolve(reference)
        except RegistryError as exc:
            raise ProtocolError("not_found", "canonical resource was not found") from exc
        canonical_ref = str(resource.ref_template.format(values))
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
                "bead": self.beads.read(
                    values["project_id"], "show", {"id": values["bead_id"]}
                ),
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

    def v2_run_agent(
        self,
        *,
        project_id: str | None,
        checkout_id: str | None,
        prompt: str | None,
        backend: str | None,
        model: str | None,
        reasoning_effort: str | None,
        timeout_seconds: int,
        credential_profile: str,
    ) -> dict[str, Any]:
        self.principal.require(Capability.JOB_START)
        if self.principal.name != "agent-control":
            raise PolicyError("agent jobs require the agent-control principal")
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
        result = self._sinnixd_job(
            "job.agent.start",
            {
                "project_id": request.project_id,
                "checkout_id": request.checkout_id or "default",
                "prompt": request.prompt,
                "backend": request.backend,
                "model": request.model,
                "effort": request.reasoning_effort,
                "credential_profile": request.credential_profile,
                "timeout_seconds": request.timeout_seconds,
                "result": "last-message",
            },
            principal="agent-control",
        )
        job_id = result.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise ProtocolError(
                "owner_failed", "sinnixd agent start response omitted the job ID"
            )
        return {
            **result,
            "ref": REGISTRY.reference("job", {"job_id": job_id}),
        }

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
            result = self.projects.write(project_id, path, content, checkout_id)
        elif operation == "apply_patch":
            if not isinstance(patch, str) or not patch:
                raise ProtocolError("invalid_request", "apply_patch requires patch")
            if path is not None or content is not None:
                raise ProtocolError("invalid_request", "apply_patch does not accept path or content")
            result = self.projects.apply_patch(project_id, patch, checkout_id)
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

    def v2_beads_change(
        self,
        *,
        reference: str,
        operation: str,
        parameters: Mapping[str, Any] | None,
        preconditions: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        _resource, values, canonical_ref = self._resource_reference(
            reference, {"project"}, "ref does not identify a canonical project"
        )
        if preconditions is not None:
            if not isinstance(preconditions, Mapping) or set(preconditions) != {"expected_task_revision"}:
                raise ProtocolError("invalid_request", "Beads change requires expected_task_revision when preconditions are supplied")
            expected = preconditions["expected_task_revision"]
            actual = self.beads.task_authority_status(values["project_id"])["revision"]
            if not isinstance(expected, str) or expected != actual:
                raise ProtocolError("precondition_failed", "Beads task revision no longer matches")
        result = self.beads.write(
            values["project_id"], operation, self._parameters(parameters)
        )
        return {"ref": canonical_ref, **result}

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
        if resource.kind == "scope":
            return canonical_ref, {"scope": values["scope_unit"]}
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

    def v2_wait(self, reference: str, timeout_seconds: int) -> dict[str, Any]:
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
        if resource.kind != "job":
            raise ProtocolError("invalid_request", "wait requires a canonical job reference")
        job_id = values["job_id"]
        self.principal.require(Capability.JOB_READ)
        result = self._sinnixd_job(
            "job.wait", {"job_id": job_id, "timeout_seconds": timeout_seconds}
        )
        if result.get("job_id") != job_id:
            raise ProtocolError(
                "owner_failed", "sinnixd wait response does not match the requested job"
            )
        return {**result, "ref": REGISTRY.reference("job", {"job_id": job_id})}

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
            "owner_route": action.route,
            "owner_version": REGISTRY.revision,
            "preconditions": dict(context.preconditions or {}),
            "before_refs": [],
            "after_refs": [],
            "effects": [],
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
                "read_only"
                if action.effect is EffectMode.READ
                else "not_atomic"
                if error and error.get("code") == "partial_completion"
                else "owner_declared"
            ),
            "partial_completion": bool(
                error and error.get("code") == "partial_completion"
            ),
            "compensation": None,
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
        self, action: ActionSpec, exc: Exception, context: RequestContext
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
            raise exc
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
                raise ProtocolError("invalid_request", "action does not support preconditions")
            if context.deadline_at is not None and time.time() >= context.deadline_at:
                raise ProtocolError("deadline", "request deadline elapsed before execution")
            replay = self._claim_v2_idempotency(action, context)
            if replay is not None:
                return replay
            reserved = action.effect is not EffectMode.READ
            response = self._v2_success(action, callback(), context)
        except (OwnerDiagnosticError, ProtocolError, ResultError, PolicyError, ValueError) as exc:
            response = self._v2_failure(action, exc, context)
        if reserved:
            self._complete_v2_idempotency(action, context, response)
        return response

    async def execute_v2_async(
        self,
        action: ActionSpec,
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
                raise ProtocolError("invalid_request", "action does not support preconditions")
            if context.deadline_at is not None and time.time() >= context.deadline_at:
                raise ProtocolError("deadline", "request deadline elapsed before execution")
            replay = self._claim_v2_idempotency(action, context)
            if replay is not None:
                return replay
            reserved = action.effect is not EffectMode.READ
            response = self._v2_success(action, await callback(), context)
        except (OwnerDiagnosticError, ProtocolError, ResultError, PolicyError, ValueError) as exc:
            response = self._v2_failure(action, exc, context)
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


def create_server(config: GatewayConfig, principal_name: str) -> MCPServer:
    runtime = Runtime.create(config, principal_name)
    mcp = MCPServer(
        name="sinnix-agent-gateway",
        title="Sinnix Agent Gateway",
        description="Principal-scoped project, machine, and attested-agent control plane.",
        instructions=(
            f"Active principal: {principal_name}. Use project_list before project operations. "
            "All outputs are bounded; unavailable evidence is reported explicitly."
        ),
        version="0.2.0",
    )

    @mcp.resource("sinnix://gateway/instructions")
    def gateway_instructions() -> str:
        return (
            f"Principal {principal_name}. Projects are allowlisted. Paths are project-relative. "
            "Job IDs and artifact IDs are the only accepted control identities."
        )

    @mcp.resource("sinnix://gateway/v2/catalog")
    def gateway_v2_catalog() -> str:
        """Return the principal-filtered V2 contract catalog during migration."""
        return json.dumps(
            REGISTRY.search(CatalogSearch(principal=principal_name)),
            sort_keys=True,
            separators=(",", ":"),
        )

    @mcp.resource("sinnix://gateway/v2/documentation")
    def gateway_v2_documentation() -> str:
        """Return generated V2 resource and action documentation rows."""
        return json.dumps(
            REGISTRY.documentation_rows(principal_name),
            sort_keys=True,
            separators=(",", ":"),
        )

    @mcp.resource("sinnix://gateway/v2/actions/{action_name}")
    def gateway_v2_action_schema(action_name: str) -> str:
        """Return the generated schema and contract for one visible V2 action."""
        return json.dumps(
            REGISTRY.action_schema(action_name, principal_name),
            sort_keys=True,
            separators=(",", ":"),
        )

    @mcp.resource("sinnix://gateway/v2/resources/{resource_kind}")
    def gateway_v2_resource_contract(resource_kind: str) -> str:
        """Return the generated contract for one canonical V2 resource kind."""
        return json.dumps(
            REGISTRY.resource_contract(resource_kind, principal_name),
            sort_keys=True,
            separators=(",", ":"),
        )

    @mcp.resource("sinnix://results/{result_id}")
    def gateway_v2_result(result_id: str) -> str:
        """Return one immutable V2 result snapshot for the active principal."""
        return json.dumps(
            runtime.results.read(result_id),
            sort_keys=True,
            separators=(",", ":"),
        )

    @mcp.resource("sinnix://receipts/{receipt_id}")
    def gateway_v2_receipt(receipt_id: str) -> str:
        """Return one principal-scoped audit receipt behind its canonical ref."""
        return json.dumps(
            runtime.audit.receipt(receipt_id),
            sort_keys=True,
            separators=(",", ":"),
        )

    target_bindings = TargetToolBindings(
        REGISTRY,
        (
            TargetToolBinding(
                tool_name="status",
                action_name="gateway.status",
                owner="gateway",
                route="observe.gateway_status",
            ),
            TargetToolBinding(
                tool_name="catalog",
                action_name="gateway.catalog",
                owner="registry",
                route="registry.search",
            ),
            TargetToolBinding(
                tool_name="get",
                action_name="resources.get",
                owner="resolver",
                route="resources.get",
            ),
            TargetToolBinding(
                tool_name="query",
                action_name="projects.query",
                owner="projects",
                route="projects.search",
            ),
            TargetToolBinding(
                tool_name="context",
                action_name="projects.context",
                owner="project-context",
                route="project_context.context",
            ),
            TargetToolBinding(
                tool_name="events",
                action_name="audit.events",
                owner="audit",
                route="audit.tail",
            ),
            TargetToolBinding(
                tool_name="wait",
                action_name="jobs.wait",
                owner="systemd-jobs",
                route="job.wait",
            ),
            TargetToolBinding(
                tool_name="run",
                action_name="shell.run",
                owner="systemd-jobs",
                route="job.shell.start",
            ),
            TargetToolBinding(
                tool_name="run",
                action_name="agents.run",
                owner="systemd-jobs",
                route="job.agent.start",
            ),
            TargetToolBinding(
                tool_name="change",
                action_name="projects.change",
                owner="projects",
                route="projects.change",
            ),
            TargetToolBinding(
                tool_name="change",
                action_name="files.change",
                owner="files",
                route="files.change",
            ),
            TargetToolBinding(
                tool_name="change",
                action_name="beads.change",
                owner="beads",
                route="beads.write",
            ),
            TargetToolBinding(
                tool_name="change",
                action_name="mcp.change",
                owner="mcp-broker",
                route="mcp.call.write",
            ),
            TargetToolBinding(
                tool_name="operate",
                action_name="machine.operate",
                owner="ops-reducer",
                route="ops.actions.execute",
            ),
            TargetToolBinding(
                tool_name="operate",
                action_name="jobs.cancel",
                owner="systemd-jobs",
                route="job.cancel",
            ),
            TargetToolBinding(
                tool_name="operate",
                action_name="desktop.operate",
                owner="desktop",
                route="desktop.action",
            ),
            TargetToolBinding(
                tool_name="operate",
                action_name="terminals.operate",
                owner="terminals",
                route="terminals.action",
            ),
            TargetToolBinding(
                tool_name="operate",
                action_name="browser.operate",
                owner="browser",
                route="browser.action",
            ),
        ),
    )

    def selector_failure(tool_name: str, error: RegistryError) -> ProtocolError:
        if "cannot invoke action" in str(error):
            return ProtocolError(
                "policy_denied",
                f"this principal cannot invoke the selected {tool_name} action",
            )
        return ProtocolError(
            "unsupported_capability",
            f"the selected {tool_name} action is not declared for this principal",
        )

    if target_bindings.is_visible("status", principal_name):

        @mcp.tool(title="Gateway status", annotations=READ_ONLY_TOOL)
        async def status(
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Return the current principal's gateway contract and availability observations."""
            action = target_bindings.action_for_tool("status", principal=principal_name)
            manifest = canonical_manifest(await mcp.list_tools())
            response = await runtime.execute_v2_async(
                action,
                lambda: runtime.gateway_status(
                    _principal_contract(principal_name),
                    manifest["sha256"],
                    REGISTRY.action_catalog_hash(principal_name),
                    REGISTRY.revision,
                ),
                {
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("catalog", principal_name):

        @mcp.tool(title="Gateway V2 catalog", annotations=READ_ONLY_TOOL)
        def catalog(
            text: str | None = None,
            domain: str | None = None,
            verb: str | None = None,
            effect: str | None = None,
            resource_kind: str | None = None,
            project: str | None = None,
            availability: str | None = None,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Search the principal-filtered V2 resource and executable action catalog."""
            action = target_bindings.action_for_tool("catalog", principal=principal_name)
            response = runtime.execute_v2(
                action,
                lambda: runtime.catalog(
                    CatalogSearch(
                        text=text,
                        domain=domain,
                        verb=VerbFamily(verb) if verb is not None else None,
                        effect=EffectMode(effect) if effect is not None else None,
                        resource_kind=resource_kind,
                        project=project,
                        availability=availability,
                        principal=principal_name,
                    )
                ),
                {
                    "text": text,
                    "domain": domain,
                    "verb": verb,
                    "effect": effect,
                    "resource_kind": resource_kind,
                    "project": project,
                    "availability": availability,
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("get", principal_name):

        @mcp.tool(title="Get V2 resource", annotations=READ_ONLY_TOOL)
        def get(
            ref: str,
            projection: str = "summary",
            offset: int = 0,
            max_bytes: int = 64_000,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Resolve a canonical resource, including bounded daemon job status or output."""
            action = target_bindings.action_for_tool("get", principal=principal_name)
            response = runtime.execute_v2(
                action,
                lambda: runtime.v2_get(ref, projection, offset, max_bytes),
                {
                    "ref": ref,
                    "projection": projection,
                    "offset": offset,
                    "max_bytes": max_bytes,
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("query", principal_name):

        @mcp.tool(title="Query V2 project", annotations=READ_ONLY_TOOL)
        def query(
            ref: str,
            query: str,
            max_matches: int = 200,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Search one canonical project or checkout through the bounded project owner."""
            action = target_bindings.action_for_tool("query", principal=principal_name)
            response = runtime.execute_v2(
                action,
                lambda: runtime.v2_query(ref, query, max_matches),
                {
                    "ref": ref,
                    "query": query,
                    "max_matches": max_matches,
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("context", principal_name):

        @mcp.tool(title="Get V2 project context", annotations=READ_ONLY_TOOL)
        def context(
            ref: str,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Compose Git and bounded task orientation for one canonical project."""
            action = target_bindings.action_for_tool("context", principal=principal_name)
            response = runtime.execute_v2(
                action,
                lambda: runtime.v2_context(ref),
                {
                    "ref": ref,
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("events", principal_name):

        @mcp.tool(title="Get V2 audit events", annotations=READ_ONLY_TOOL)
        def events(
            limit: int = 100,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Read bounded audit events visible to the active principal."""
            action = target_bindings.action_for_tool("events", principal=principal_name)
            response = runtime.execute_v2(
                action,
                lambda: runtime.v2_events(limit),
                {
                    "limit": limit,
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("wait", principal_name):

        @mcp.tool(title="Wait for V2 job", annotations=READ_ONLY_TOOL)
        def wait(
            ref: str,
            timeout_seconds: int = 30,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Wait for a bounded interval on one daemon-owned job reference."""
            action = target_bindings.action_for_tool("wait", principal=principal_name)
            response = runtime.execute_v2(
                action,
                lambda: runtime.v2_wait(ref, timeout_seconds),
                {
                    "ref": ref,
                    "timeout_seconds": timeout_seconds,
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("run", principal_name):

        @mcp.tool(title="Run typed V2 job", annotations=IDEMPOTENT_RUN_TOOL)
        def run(
            action_name: str,
            idempotency_key: str,
            project_id: str | None = None,
            checkout_id: str | None = None,
            argv: list[str] | None = None,
            prompt: str | None = None,
            backend: str | None = None,
            model: str | None = None,
            reasoning_effort: str | None = None,
            credential_profile: str = "subscription",
            cwd: str = ".",
            timeout_seconds: int | None = None,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Start one catalog-declared shell or attested-agent job by action name."""
            request = {
                "action_name": action_name,
                "project_id": project_id,
                "checkout_id": checkout_id,
                "argv": argv,
                "prompt": prompt,
                "backend": backend,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "credential_profile": credential_profile,
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
                "request_id": request_id,
                "actor": actor,
                "reason": reason,
                "idempotency_key": idempotency_key,
                "deadline_at": deadline_at,
                "preconditions": preconditions,
            }
            try:
                action = target_bindings.action_for_tool(
                    "run", action_name, principal=principal_name
                )
            except RegistryError as error:
                action = target_bindings.fallback_for_tool("run", principal_name)
                failure = selector_failure("run", error)

                def callback() -> dict[str, Any]:
                    raise failure

            else:
                if action.name == "shell.run":
                    callback = lambda: runtime.v2_run_shell(
                        project_id=project_id,
                        checkout_id=checkout_id,
                        argv=argv,
                        cwd=cwd,
                        timeout_seconds=3_600 if timeout_seconds is None else timeout_seconds,
                    )
                elif action.name == "agents.run":
                    callback = lambda: runtime.v2_run_agent(
                        project_id=project_id,
                        checkout_id=checkout_id,
                        prompt=prompt,
                        backend=backend,
                        model=model,
                        reasoning_effort=reasoning_effort,
                        timeout_seconds=14_400 if timeout_seconds is None else timeout_seconds,
                        credential_profile=credential_profile,
                    )
                else:
                    raise RegistryError(f"run action {action.name!r} is not implemented")
            response = runtime.execute_v2(action, callback, request)
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("change", principal_name):

        @mcp.tool(title="Change canonical target", annotations=IDEMPOTENT_MUTATION_TOOL)
        async def change(
            action_name: str,
            ref: str,
            operation: str,
            idempotency_key: str,
            parameters: dict[str, Any] | None = None,
            preconditions: dict[str, Any] | None = None,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            deadline_at: float | None = None,
        ) -> V2ToolEnvelope:
            """Apply one catalog-declared mutation through its canonical owner route."""
            request = {
                "action_name": action_name,
                "ref": ref,
                "operation": operation,
                "parameters": parameters,
                "request_id": request_id,
                "actor": actor,
                "reason": reason,
                "idempotency_key": idempotency_key,
                "deadline_at": deadline_at,
                "preconditions": preconditions,
            }
            try:
                action = target_bindings.action_for_tool(
                    "change", action_name, principal=principal_name
                )
            except RegistryError as error:
                action = target_bindings.fallback_for_tool("change", principal_name)
                failure = selector_failure("change", error)

                async def callback() -> dict[str, Any]:
                    raise failure

            else:
                async def callback() -> dict[str, Any]:
                    if action.name == "projects.change":
                        return runtime.v2_change(
                            reference=ref,
                            operation=operation,
                            path=parameters.get("path") if parameters else None,
                            content=parameters.get("content") if parameters else None,
                            patch=parameters.get("patch") if parameters else None,
                            preconditions=preconditions,
                        )
                    if action.name == "files.change":
                        return runtime.v2_file_change(
                            reference=ref,
                            operation=operation,
                            parameters=parameters,
                            preconditions=preconditions,
                        )
                    if action.name == "beads.change":
                        return runtime.v2_beads_change(
                            reference=ref,
                            operation=operation,
                            parameters=parameters,
                            preconditions=preconditions,
                        )
                    if action.name == "mcp.change":
                        return await runtime.v2_mcp_change(
                            reference=ref, operation=operation, parameters=parameters
                        )
                    raise RegistryError(f"change action {action.name!r} is not implemented")

            response = await runtime.execute_v2_async(action, callback, request)
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("operate", principal_name):

        @mcp.tool(title="Operate canonical machine target", annotations=IDEMPOTENT_MUTATION_TOOL)
        def operate(
            action_name: str,
            ref: str,
            idempotency_key: str,
            operation: str | None = None,
            parameters: dict[str, Any] | None = None,
            reason: str | None = None,
            preconditions: dict[str, Any] | None = None,
            request_id: str | None = None,
            actor: str | None = None,
            deadline_at: float | None = None,
        ) -> V2ToolEnvelope:
            """Run one catalog-declared machine or job operation against a canonical target."""
            request = {
                "action_name": action_name,
                "ref": ref,
                "operation": operation,
                "parameters": parameters,
                "request_id": request_id,
                "actor": actor,
                "reason": reason,
                "idempotency_key": idempotency_key,
                "deadline_at": deadline_at,
                "preconditions": preconditions,
            }
            try:
                contract = target_bindings.action_for_tool(
                    "operate", action_name, principal=principal_name
                )
            except RegistryError as error:
                contract = target_bindings.fallback_for_tool("operate", principal_name)
                failure = selector_failure("operate", error)

                def callback() -> dict[str, Any]:
                    raise failure

            else:
                if contract.name == "machine.operate":
                    callback = lambda: runtime.v2_operate(
                        reference=ref,
                        action=operation,
                        parameters=parameters,
                        reason=reason,
                        idempotency_key=idempotency_key,
                        preconditions=preconditions,
                    )
                elif contract.name == "jobs.cancel":
                    callback = lambda: runtime.v2_cancel_job(
                        reference=ref,
                        preconditions=preconditions,
                    )
                elif contract.name == "desktop.operate":
                    callback = lambda: runtime.v2_desktop_operate(
                        reference=ref, operation=operation, parameters=parameters
                    )
                elif contract.name == "terminals.operate":
                    callback = lambda: runtime.v2_terminal_operate(
                        reference=ref, operation=operation, parameters=parameters
                    )
                elif contract.name == "browser.operate":
                    callback = lambda: runtime.v2_browser_operate(
                        reference=ref, operation=operation, parameters=parameters
                    )
                else:
                    raise RegistryError(f"operate action {contract.name!r} is not implemented")
            response = runtime.execute_v2(contract, callback, request)
            return cast(V2ToolEnvelope, v2_tool_result(response))

    @mcp.tool(title="Machine report", annotations=READ_ONLY_TOOL)
    def machine_report() -> dict[str, Any]:
        """Return a bounded machine and runtime report through the canonical sinnix-observe contract."""
        return runtime.execute("machine_report", runtime.observe.machine_report)

    @mcp.tool(title="Query machine state", annotations=READ_ONLY_TOOL)
    def machine_query(
        operation: str, cursor: int = 0, limit: int = 100
    ) -> dict[str, Any]:
        """Read a bounded, provenance-carrying section from canonical machine evidence."""
        return runtime.execute(
            "machine_query",
            lambda: runtime.observe.machine_query(operation, cursor, limit),
        )

    if Capability.CAPABILITY_READ in runtime.principal.capabilities:

        @mcp.tool(title="Search machine capabilities", annotations=READ_ONLY_TOOL)
        def capability_search(
            query: str = "",
            kind: str | None = None,
            enabled: bool | None = None,
            cursor: int = 0,
            limit: int = 100,
        ) -> dict[str, Any]:
            """Search the derived capability index with bounded, provenance-carrying pages."""
            return runtime.execute(
                "capability_search",
                lambda: runtime.capability_index.search(
                    query=query,
                    kind=kind,
                    enabled=enabled,
                    cursor=cursor,
                    limit=limit,
                ),
            )

        @mcp.tool(title="Describe machine capability", annotations=READ_ONLY_TOOL)
        def capability_describe(
            name: str, kind: str | None = None
        ) -> dict[str, Any]:
            """Resolve a capability by exact name and optional kind from the derived index."""
            return runtime.execute(
                "capability_describe",
                lambda: runtime.capability_index.describe(name=name, kind=kind),
            )

    if Capability.MCP_READ in runtime.principal.capabilities:

        @mcp.tool(title="List registered MCP servers", annotations=READ_ONLY_TOOL)
        async def mcp_catalog() -> dict[str, Any]:
            """List registry-derived MCP upstreams and their live availability."""
            return await runtime.execute_async("mcp_catalog", runtime.mcp_broker.catalog)

        @mcp.tool(title="Call read-only upstream MCP tool", annotations=READ_ONLY_TOOL)
        async def mcp_read(
            server: str, tool: str, arguments: dict[str, Any]
        ) -> dict[str, Any]:
            """Call an upstream tool only when its live manifest declares it read-only."""
            return await runtime.execute_async(
                "mcp_read",
                lambda: runtime.mcp_broker.call(server, tool, arguments, write=False),
            )

    if Capability.TASK_READ in runtime.principal.capabilities:

        @mcp.tool(title="Read Beads tasks", annotations=READ_ONLY_TOOL)
        def tasks_read(
            project_id: str, operation: str, arguments: dict[str, Any] | None = None
        ) -> dict[str, Any]:
            """Read bounded Beads records through the native owner CLI."""
            return runtime.execute(
                "tasks_read", lambda: runtime.beads.read(project_id, operation, arguments)
            )

    if Capability.DESKTOP_READ in runtime.principal.capabilities:

        @mcp.tool(title="Read desktop state", annotations=READ_ONLY_TOOL)
        def desktop_read(operation: str) -> dict[str, Any]:
            """Read bounded Hyprland or screen-color state through its owner wrapper."""
            return runtime.execute(
                "desktop_read", lambda: runtime.desktop.read(operation)
            )

    if Capability.DESKTOP_READ in runtime.principal.capabilities:

        @mcp.tool(title="Capture desktop output", annotations=READ_ONLY_TOOL)
        def desktop_capture(fix_hdr: bool = True) -> dict[str, Any]:
            """Capture the current output into opaque artifacts without changing desktop focus."""
            return runtime.execute(
                "desktop_capture", lambda: runtime.desktop.capture_output(fix_hdr)
            )

    if Capability.TERMINAL_READ in runtime.principal.capabilities:

        @mcp.tool(title="Read terminal state", annotations=READ_ONLY_TOOL)
        def terminal_read(
            operation: str, arguments: dict[str, Any] | None = None
        ) -> dict[str, Any]:
            """List Kitty terminals or read a bounded capture through its owner wrapper."""
            return runtime.execute(
                "terminal_read", lambda: runtime.terminals.read(operation, arguments)
            )

    if Capability.BROWSER_READ in runtime.principal.capabilities:

        @mcp.tool(title="Read browser state", annotations=READ_ONLY_TOOL)
        def browser_read(
            operation: str,
            page_id: str | None = None,
            selector: str | None = None,
        ) -> dict[str, Any]:
            """Read Chrome state or bounded content without making a page actionable."""
            return runtime.execute(
                "browser_read",
                lambda: runtime.browser.read(operation, page_id, selector),
            )

    if Capability.BROWSER_READ in runtime.principal.capabilities:

        @mcp.tool(title="Capture owned browser target", annotations=READ_ONLY_TOOL)
        def browser_capture(
            page_id: str,
            image_format: str = "png",
            full_page: bool = False,
            quality: int | None = None,
        ) -> dict[str, Any]:
            """Capture only a gateway-created hidden Chrome target as an opaque artifact."""
            return runtime.execute(
                "browser_capture",
                lambda: runtime.browser.capture(
                    page_id, image_format, full_page, quality
                ),
            )

    @mcp.tool(title="List projects", annotations=READ_ONLY_TOOL)
    def project_list() -> dict[str, Any]:
        """List projects available to the active principal without exposing host paths."""
        return runtime.execute("project_list", runtime.projects.list)

    @mcp.tool(title="Project tree", annotations=READ_ONLY_TOOL)
    def project_tree(
        project_id: str,
        path: str = ".",
        max_entries: int = 500,
        checkout_id: str | None = None,
    ) -> dict[str, Any]:
        """List a bounded project-relative directory tree without following symlinks."""
        return runtime.execute(
            "project_tree",
            lambda: runtime.projects.tree(project_id, path, max_entries, checkout_id),
        )

    @mcp.tool(title="Read project file", annotations=READ_ONLY_TOOL)
    def project_read(
        project_id: str,
        path: str,
        start_line: int = 1,
        end_line: int | None = None,
        max_bytes: int = 64_000,
        checkout_id: str | None = None,
    ) -> dict[str, Any]:
        """Read a bounded line range from a regular project file."""
        return runtime.execute(
            "project_read",
            lambda: runtime.projects.read(
                project_id, path, start_line, end_line, max_bytes, checkout_id
            ),
        )

    @mcp.tool(title="Project diff", annotations=READ_ONLY_TOOL)
    def project_diff(
        project_id: str, ref: str | None = None, checkout_id: str | None = None
    ) -> dict[str, Any]:
        """Return a bounded Git diff for an allowlisted project."""
        return runtime.execute(
            "project_diff", lambda: runtime.projects.diff(project_id, ref, checkout_id)
        )

    if Capability.FILE_READ in runtime.principal.capabilities:

        @mcp.tool(title="Read host files", annotations=READ_ONLY_TOOL)
        def files_read(
            operation: str,
            path: str,
            offset: int = 0,
            max_bytes: int = 64_000,
            max_entries: int = 200,
        ) -> dict[str, Any]:
            """Stat, read, or list a bounded host path available to this principal."""
            return runtime.execute(
                "files_read",
                lambda: runtime.files.read(
                    operation,
                    path,
                    offset=offset,
                    max_bytes=max_bytes,
                    max_entries=max_entries,
                ),
            )

    if Capability.SESSION_READ in runtime.principal.capabilities:

        @mcp.tool(title="List raw coding sessions", annotations=READ_ONLY_TOOL)
        def session_list(provider: str, limit: int = 100) -> dict[str, Any]:
            """List bounded Claude Code or Codex session-log references."""
            return runtime.execute(
                "session_list", lambda: runtime.sessions.list(provider, limit)
            )

        @mcp.tool(title="Read raw coding session", annotations=READ_ONLY_TOOL)
        def session_read(
            reference: str, offset: int = 0, max_bytes: int = 64_000
        ) -> dict[str, Any]:
            """Read a bounded page from one provider-scoped raw session JSONL."""
            return runtime.execute(
                "session_read",
                lambda: runtime.sessions.read(reference, offset, max_bytes),
            )

        @mcp.tool(title="Search raw coding sessions", annotations=READ_ONLY_TOOL)
        def session_search(
            provider: str, query: str, max_results: int = 100
        ) -> dict[str, Any]:
            """Search a bounded prefix of authoritative raw coding-session JSONL files."""
            return runtime.execute(
                "session_search",
                lambda: runtime.sessions.search(provider, query, max_results),
            )

        @mcp.tool(title="Search semantic memory", annotations=READ_ONLY_TOOL)
        def memory_search(
            query: str, providers: list[str] | None = None, limit: int = 100
        ) -> dict[str, Any]:
            """Search available memory sources while retaining source availability and provenance."""
            return runtime.execute(
                "memory_search", lambda: runtime.memory.search(query, providers, limit)
            )

        @mcp.tool(title="Get semantic memory object", annotations=READ_ONLY_TOOL)
        def memory_get(
            reference: str, offset: int = 0, max_bytes: int = 64_000
        ) -> dict[str, Any]:
            """Read one source-scoped memory object with its original provenance."""
            return runtime.execute(
                "memory_get", lambda: runtime.memory.get(reference, offset, max_bytes)
            )

        @mcp.tool(title="Query evidence timeline", annotations=READ_ONLY_TOOL)
        def timeline_query(
            start: str | None = None,
            end: str | None = None,
            query: str | None = None,
            providers: list[str] | None = None,
            limit: int = 100,
        ) -> dict[str, Any]:
            """Timeline available session evidence without fabricating unavailable upstream coverage."""
            return runtime.execute(
                "timeline_query",
                lambda: runtime.timeline.query(start, end, query, providers, limit),
            )

    @mcp.tool(title="List artifacts", annotations=READ_ONLY_TOOL)
    def artifact_list(limit: int = 100) -> dict[str, Any]:
        """List opaque artifact metadata without host paths."""
        return runtime.execute("artifact_list", lambda: runtime.artifacts.list(limit))

    @mcp.tool(title="Read artifact", annotations=READ_ONLY_TOOL)
    def artifact_read(
        artifact_id: str, offset: int = 0, max_bytes: int = 64_000
    ) -> dict[str, Any]:
        """Read a bounded binary range as base64 from an opaque artifact ID."""
        return runtime.execute(
            "artifact_read",
            lambda: runtime.artifacts.read(artifact_id, offset, max_bytes),
        )

    @mcp.tool(title="Verify audit ledger", annotations=READ_ONLY_TOOL)
    def audit_verify() -> dict[str, Any]:
        """Verify the complete tamper-evident audit hash chain."""
        return runtime.execute("audit_verify", runtime.audit.verify)

    if Capability.CAPTURE_READ in runtime.principal.capabilities:

        @mcp.tool(title="List visible capture lanes", annotations=READ_ONLY_TOOL)
        def capture_lanes() -> dict[str, Any]:
            """List the capture-data lanes this principal may query."""
            return runtime.execute("capture_lanes", runtime.captures.lanes_visible)

        @mcp.tool(title="Query capture data", annotations=READ_ONLY_TOOL)
        def capture_query(
            lanes: list[str] | None = None, since: float = 0.0, limit: int = 100
        ) -> dict[str, Any]:
            """Query envelope records within the principal's lane authority."""
            return runtime.execute(
                "capture_query", lambda: runtime.captures.query(lanes, since, limit)
            )

    return mcp
