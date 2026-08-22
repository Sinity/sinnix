from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, TypeVar, cast

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .artifacts import ArtifactService
from .audit import AuditService
from .beads import BeadsError, BeadsService
from .bindings import TargetToolBinding, TargetToolBindings
from .browser import BrowserService
from .capabilities import Capability, Principal
from .capability_index import CapabilityIndexService
from .captures import CaptureService
from .config import GatewayConfig
from .contracts import ActionSpec, EffectMode, VerbFamily
from .desktop import DesktopService
from .execution import OwnerDiagnosticError
from .files import HostFileService
from .jobs import JobService
from .machine_actions import MachineActionService
from .mcp_broker import McpBrokerService
from .memory import MemoryService
from .observe import ObserveService
from .project_context import ProjectContextService
from .projects import ProjectService
from .redaction import public_error
from .results import ResultError, ResultService
from .route_preflight import GatewayRoutePreflight
from .registry import CatalogSearch, REGISTRY
from .schemas import AgentLaunchRequest
from .sessions import SessionLogService
from .shell import ShellService
from .terminals import TerminalService
from .timeline import TimelineService

T = TypeVar("T")

READ_ONLY_TOOL = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
AGENT_LAUNCH_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)
DESTRUCTIVE_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
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
    jobs: JobService
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
    shell: ShellService
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
            jobs=JobService(config, principal, artifacts, projects=projects),
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
            shell=ShellService(config, principal),
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

    def v2_get(self, reference: str) -> dict[str, Any]:
        resource, values = REGISTRY.resolve(reference)
        canonical_ref = str(resource.ref_template.format(values))
        if resource.kind == "project":
            project_id = values["project_id"]
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
            canonical_checkout_ref = canonical_checkout["ref"]
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
            return {
                "ref": canonical_ref,
                "kind": resource.kind,
                "project": self.projects.summary(project_id),
                "canonical_checkout_ref": canonical_checkout_ref,
                "code_revision": code_revision,
                "checkouts": checkouts,
                "task_authority": task_authority,
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
        raise ValueError(f"V2 get does not support resource kind {resource.kind!r}")

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
    def _request_digest(request: Mapping[str, Any]) -> str:
        try:
            encoded = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
        except (TypeError, ValueError) as exc:
            raise ValueError("V2 request is not JSON serializable") from exc
        return hashlib.sha256(encoded).hexdigest()

    def _v2_success(
        self, action: ActionSpec, result: Any, request_sha256: str
    ) -> dict[str, Any]:
        self.results.require_payload_bound(result)
        receipt = self._record_result(action.name, result, request_sha256)
        return self.results.record(
            action=action.name,
            owner=action.owner,
            route=action.route,
            outcome="ok",
            payload=result,
            receipt=receipt,
            request_sha256=request_sha256,
        )

    def _v2_failure(
        self, action: ActionSpec, exc: Exception, request_sha256: str
    ) -> dict[str, Any]:
        if isinstance(exc, OwnerDiagnosticError):
            details = self._diagnostic_payload(exc.response)
            error: dict[str, object] = {
                "code": "owner_diagnostic",
                "message": "owner route failed",
                **details,
            }
            audit_payload = {"code": "owner_diagnostic", **details}
        else:
            code = (
                exc.failure_class
                if isinstance(exc, ResultError)
                else "invalid_request"
                if isinstance(exc, ValueError)
                else "internal_error"
            )
            message = public_error(exc)
            error = {"code": code, "message": message}
            audit_payload = {"code": code, "error": message}
        audit_payload["request_sha256"] = request_sha256
        receipt = self.audit.append(action.name, "error", audit_payload)
        return self.results.record(
            action=action.name,
            owner=action.owner,
            route=action.route,
            outcome="error",
            payload=error,
            receipt=receipt,
            request_sha256=request_sha256,
        )

    def execute_v2(
        self,
        action: ActionSpec,
        callback: Callable[[], Any],
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        request_sha256 = self._request_digest(request)
        try:
            return self._v2_success(action, callback(), request_sha256)
        except Exception as exc:
            return self._v2_failure(action, exc, request_sha256)

    async def execute_v2_async(
        self,
        action: ActionSpec,
        callback: Callable[[], Awaitable[Any]],
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        request_sha256 = self._request_digest(request)
        try:
            return self._v2_success(action, await callback(), request_sha256)
        except Exception as exc:
            return self._v2_failure(action, exc, request_sha256)

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
        ),
    )

    if target_bindings.is_visible("status", principal_name):

        @mcp.tool(title="Gateway status", annotations=READ_ONLY_TOOL)
        async def status() -> dict[str, Any]:
            """Return the current principal's gateway contract and availability observations."""
            action = target_bindings.action_for_tool("status", principal_name)
            manifest = canonical_manifest(await mcp.list_tools())
            return await runtime.execute_v2_async(
                action,
                lambda: runtime.gateway_status(
                    _principal_contract(principal_name),
                    manifest["sha256"],
                    REGISTRY.action_catalog_hash(principal_name),
                    REGISTRY.revision,
                ),
                {},
            )

    if target_bindings.is_visible("catalog", principal_name):

        @mcp.tool(title="Gateway V2 catalog", annotations=READ_ONLY_TOOL)
        def catalog(
            text: str | None = None,
            domain: str | None = None,
            verb: str | None = None,
            effect: str | None = None,
            resource_kind: str | None = None,
            availability: str | None = None,
        ) -> dict[str, Any]:
            """Search the principal-filtered V2 resource and executable action catalog."""
            action = target_bindings.action_for_tool("catalog", principal_name)
            return runtime.execute_v2(
                action,
                lambda: REGISTRY.search(
                    CatalogSearch(
                        text=text,
                        domain=domain,
                        verb=VerbFamily(verb) if verb is not None else None,
                        effect=EffectMode(effect) if effect is not None else None,
                        resource_kind=resource_kind,
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
                    "availability": availability,
                },
            )

    if target_bindings.is_visible("get", principal_name):

        @mcp.tool(title="Get V2 resource", annotations=READ_ONLY_TOOL)
        def get(ref: str) -> dict[str, Any]:
            """Resolve one canonical project, checkout, or Beads task reference."""
            action = target_bindings.action_for_tool("get", principal_name)
            return runtime.execute_v2(
                action,
                lambda: runtime.v2_get(ref),
                {"ref": ref},
            )

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

    if Capability.MCP_WRITE in runtime.principal.capabilities:

        @mcp.tool(title="Call writable upstream MCP tool", annotations=DESTRUCTIVE_TOOL)
        async def mcp_write(
            server: str, tool: str, arguments: dict[str, Any]
        ) -> dict[str, Any]:
            """Call one non-read-only upstream tool through the configured broker."""
            return await runtime.execute_async(
                "mcp_write",
                lambda: runtime.mcp_broker.call(server, tool, arguments, write=True),
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

    if Capability.TASK_WRITE in runtime.principal.capabilities:

        @mcp.tool(title="Write Beads tasks", annotations=DESTRUCTIVE_TOOL)
        def tasks_write(
            project_id: str, operation: str, arguments: dict[str, Any]
        ) -> dict[str, Any]:
            """Perform one structured Beads mutation through the native owner CLI."""
            return runtime.execute(
                "tasks_write", lambda: runtime.beads.write(project_id, operation, arguments)
            )

    if Capability.MACHINE_ACTION in runtime.principal.capabilities:

        @mcp.tool(title="Run typed machine action", annotations=DESTRUCTIVE_TOOL)
        def machine_action(
            action: str,
            target: dict[str, Any],
            expected_revision: int,
            idempotency_key: str,
            operator_reason: str,
            parameters: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            """Submit one revision-checked, idempotent action to the ops reducer."""
            return runtime.execute(
                "machine_action",
                lambda: runtime.machine_actions.execute(
                    action,
                    target,
                    expected_revision,
                    idempotency_key,
                    operator_reason,
                    parameters,
                ),
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

    if Capability.DESKTOP_ACTION in runtime.principal.capabilities:

        @mcp.tool(title="Run desktop action", annotations=DESTRUCTIVE_TOOL)
        def desktop_action(operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
            """Run one exact operator desktop action through the Hyprland wrapper."""
            return runtime.execute(
                "desktop_action", lambda: runtime.desktop.action(operation, arguments)
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

    if Capability.TERMINAL_ACTION in runtime.principal.capabilities:

        @mcp.tool(title="Run terminal action", annotations=DESTRUCTIVE_TOOL)
        def terminal_action(operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
            """Send one exact operator action to a selected Kitty terminal."""
            return runtime.execute(
                "terminal_action", lambda: runtime.terminals.action(operation, arguments)
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

    if Capability.BROWSER_ACTION in runtime.principal.capabilities:

        @mcp.tool(title="Run browser action", annotations=DESTRUCTIVE_TOOL)
        def browser_action(operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
            """Operate only a gateway-created hidden Chrome agent window."""
            return runtime.execute(
                "browser_action", lambda: runtime.browser.action(operation, arguments)
            )

    @mcp.tool(title="List projects", annotations=READ_ONLY_TOOL)
    def project_list() -> dict[str, Any]:
        """List projects available to the active principal without exposing host paths."""
        return runtime.execute("project_list", runtime.projects.list)

    @mcp.tool(title="Get project context", annotations=READ_ONLY_TOOL)
    def project_context(project_id: str) -> dict[str, Any]:
        """Get structured Git and ready-work orientation from existing project owners."""
        return runtime.execute(
            "project_context", lambda: runtime.project_context.context(project_id)
        )

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

    @mcp.tool(title="Search project", annotations=READ_ONLY_TOOL)
    def project_search(
        project_id: str,
        query: str,
        max_matches: int = 200,
        checkout_id: str | None = None,
    ) -> dict[str, Any]:
        """Search project text with bounded results and safe leading-dash handling."""
        return runtime.execute(
            "project_search",
            lambda: runtime.projects.search(project_id, query, max_matches, checkout_id),
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

    if Capability.FILE_WRITE in runtime.principal.capabilities:

        @mcp.tool(title="Write host files", annotations=DESTRUCTIVE_TOOL)
        def files_write(
            operation: str,
            path: str,
            content: str | None = None,
            destination: str | None = None,
            expected_sha256: str | None = None,
        ) -> dict[str, Any]:
            """Replace, append, create, remove, copy, or move a host path with a receipt."""
            return runtime.execute(
                "files_write",
                lambda: runtime.files.write(
                    operation,
                    path,
                    content=content,
                    destination=destination,
                    expected_sha256=expected_sha256,
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

    if Capability.SHELL_RUN in runtime.principal.capabilities:

        @mcp.tool(title="Run operator shell command", annotations=DESTRUCTIVE_TOOL)
        def shell_run(
            argv: list[str],
            cwd: str = "/",
            timeout_seconds: int = 300,
            max_bytes: int = 64_000,
            environment: dict[str, str] | None = None,
            as_root: bool = False,
        ) -> dict[str, Any]:
            """Run exact argv as the operator, or explicitly through sudo without a prompt."""
            return runtime.execute(
                "shell_run",
                lambda: runtime.shell.run(
                    argv,
                    cwd,
                    timeout_seconds,
                    max_bytes,
                    environment,
                    as_root,
                ),
            )

        @mcp.tool(title="Start operator shell job", annotations=DESTRUCTIVE_TOOL)
        def shell_start(
            argv: list[str],
            cwd: str = "/",
            timeout_seconds: int = 3_600,
            environment: dict[str, str] | None = None,
            as_root: bool = False,
        ) -> dict[str, Any]:
            """Start exact argv as an attested, cancellable operator shell job."""
            return runtime.execute(
                "shell_start",
                lambda: runtime.jobs.start_shell(
                    argv,
                    cwd,
                    timeout_seconds,
                    environment,
                    as_root,
                ),
            )

    @mcp.tool(title="List attested jobs", annotations=READ_ONLY_TOOL)
    def job_list(limit: int = 100) -> dict[str, Any]:
        """List recent attested jobs and report malformed records explicitly."""
        return runtime.execute("job_list", lambda: runtime.jobs.list(limit))

    @mcp.tool(title="Attested job status", annotations=READ_ONLY_TOOL)
    def job_status(job_id: str) -> dict[str, Any]:
        """Return manifest and live systemd/cgroup state for one attested job ID."""
        return runtime.execute("job_status", lambda: runtime.jobs.status(job_id))

    @mcp.tool(title="Read job output", annotations=READ_ONLY_TOOL)
    def job_read_output(
        job_id: str,
        artifact: str = "log",
        offset: int = 0,
        max_bytes: int = 64_000,
    ) -> dict[str, Any]:
        """Read a bounded byte range from an attested job artifact."""
        return runtime.execute(
            "job_read_output",
            lambda: runtime.jobs.read_output(job_id, artifact, offset, max_bytes),
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

    @mcp.tool(title="Audit tail", annotations=READ_ONLY_TOOL)
    def audit_tail(limit: int = 100) -> dict[str, Any]:
        """Return recent semantic gateway audit events."""
        return runtime.execute("audit_tail", lambda: runtime.audit.tail(limit))

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

    if Capability.JOB_START in runtime.principal.capabilities:

        @mcp.tool(title="Launch agent job", annotations=AGENT_LAUNCH_TOOL)
        def agent_launch(
            project_id: str,
            prompt: str,
            backend: str,
            checkout_id: str | None = None,
            model: str | None = None,
            reasoning_effort: str | None = None,
            job_role: str | None = None,
            work_item: str | None = None,
            timeout_seconds: int = 14_400,
            credential_profile: str = "subscription",
        ) -> dict[str, Any]:
            """Launch an attested native coding-agent job in an allowlisted project."""
            request = AgentLaunchRequest(
                project_id=project_id,
                checkout_id=checkout_id,
                prompt=prompt,
                backend=backend,
                model=model,
                reasoning_effort=reasoning_effort,
                job_role=job_role,
                work_item=work_item,
                timeout_seconds=timeout_seconds,
                credential_profile=credential_profile,
            )
            return runtime.execute(
                "agent_launch", lambda: runtime.jobs.launch_agent(request)
            )

    if Capability.JOB_CANCEL in runtime.principal.capabilities:

        @mcp.tool(title="Cancel attested job", annotations=DESTRUCTIVE_TOOL)
        def job_cancel(job_id: str) -> dict[str, Any]:
            """Stop a live job by attested job ID and systemd cgroup identity."""
            return runtime.execute("job_cancel", lambda: runtime.jobs.cancel(job_id))

    if Capability.PROJECT_WRITE in runtime.principal.capabilities:

        @mcp.tool(title="Write project file", annotations=DESTRUCTIVE_TOOL)
        def project_write(
            project_id: str,
            path: str,
            content: str,
            checkout_id: str | None = None,
        ) -> dict[str, Any]:
            """Atomically write one project-relative file under operator policy."""
            return runtime.execute(
                "project_write",
                lambda: runtime.projects.write(project_id, path, content, checkout_id),
            )

        @mcp.tool(title="Apply project patch", annotations=DESTRUCTIVE_TOOL)
        def project_apply_patch(
            project_id: str, patch: str, checkout_id: str | None = None
        ) -> dict[str, Any]:
            """Apply a bounded Git patch under operator policy."""
            return runtime.execute(
                "project_apply_patch",
                lambda: runtime.projects.apply_patch(project_id, patch, checkout_id),
            )

    return mcp
