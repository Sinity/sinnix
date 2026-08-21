from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeVar

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .artifacts import ArtifactService
from .audit import AuditService
from .beads import BeadsService
from .browser import BrowserService
from .capabilities import Capability, Principal
from .capability_index import CapabilityIndexService
from .captures import CaptureService
from .config import GatewayConfig
from .desktop import DesktopService
from .files import HostFileService
from .jobs import JobService
from .machine_actions import MachineActionService
from .mcp_broker import McpBrokerService
from .memory import MemoryService
from .observe import ObserveService
from .projects import ProjectService
from .redaction import public_error
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
    artifacts: ArtifactService
    audit: AuditService
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

    @classmethod
    def create(cls, config: GatewayConfig, principal_name: str) -> "Runtime":
        principal = Principal.for_name(principal_name)
        artifacts = ArtifactService(config, principal)
        sessions = SessionLogService(config, principal)
        return cls(
            principal_name=principal_name,
            principal=principal,
            config=config,
            projects=ProjectService(config, principal),
            artifacts=artifacts,
            audit=AuditService(config, principal),
            jobs=JobService(config, principal, artifacts),
            observe=ObserveService(config, principal),
            machine_actions=MachineActionService(config, principal),
            desktop=DesktopService(config, principal, artifacts),
            terminals=TerminalService(config, principal),
            browser=BrowserService(config, principal, artifacts),
            beads=BeadsService(config, principal),
            capability_index=CapabilityIndexService(config, principal),
            captures=CaptureService(config, principal),
            files=HostFileService(config, principal),
            sessions=sessions,
            memory=MemoryService(principal, sessions),
            timeline=TimelineService(principal, sessions),
            mcp_broker=McpBrokerService(config, principal, artifacts),
            shell=ShellService(config, principal),
        )

    def _record_result(self, operation: str, result: Any) -> None:
        payload: dict[str, Any] = {}
        if isinstance(result, dict):
            for key in ("job_id", "artifact_id", "project_id", "receipt_id", "unit"):
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
        self.audit.append(operation, "ok", payload)

    def execute(self, operation: str, callback: Callable[[], T]) -> T:
        try:
            result = callback()
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

    @mcp.tool(title="Gateway status", annotations=READ_ONLY_TOOL)
    async def gateway_status() -> dict[str, Any]:
        """Return principal, manifest provenance, transport, runtime state, and contract hash."""
        manifest = canonical_manifest(await mcp.list_tools())
        return runtime.execute(
            "gateway_status",
            lambda: runtime.observe.gateway_status(
                principal_name,
                _principal_contract(principal_name),
                manifest["sha256"],
            ),
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
        def mcp_catalog() -> dict[str, Any]:
            """List registry-derived MCP upstreams and their broker admission state."""
            return runtime.execute("mcp_catalog", runtime.mcp_broker.catalog)

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

    @mcp.tool(title="Project tree", annotations=READ_ONLY_TOOL)
    def project_tree(
        project_id: str, path: str = ".", max_entries: int = 500
    ) -> dict[str, Any]:
        """List a bounded project-relative directory tree without following symlinks."""
        return runtime.execute(
            "project_tree", lambda: runtime.projects.tree(project_id, path, max_entries)
        )

    @mcp.tool(title="Read project file", annotations=READ_ONLY_TOOL)
    def project_read(
        project_id: str,
        path: str,
        start_line: int = 1,
        end_line: int | None = None,
        max_bytes: int = 64_000,
    ) -> dict[str, Any]:
        """Read a bounded line range from a regular project file."""
        return runtime.execute(
            "project_read",
            lambda: runtime.projects.read(
                project_id, path, start_line, end_line, max_bytes
            ),
        )

    @mcp.tool(title="Search project", annotations=READ_ONLY_TOOL)
    def project_search(
        project_id: str, query: str, max_matches: int = 200
    ) -> dict[str, Any]:
        """Search project text with bounded results and safe leading-dash handling."""
        return runtime.execute(
            "project_search",
            lambda: runtime.projects.search(project_id, query, max_matches),
        )

    @mcp.tool(title="Project diff", annotations=READ_ONLY_TOOL)
    def project_diff(project_id: str, ref: str | None = None) -> dict[str, Any]:
        """Return a bounded Git diff for an allowlisted project."""
        return runtime.execute(
            "project_diff", lambda: runtime.projects.diff(project_id, ref)
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
            expected_sha256: str | None = None,
        ) -> dict[str, Any]:
            """Replace, append, create, or remove a host path with a durable receipt."""
            return runtime.execute(
                "files_write",
                lambda: runtime.files.write(
                    operation,
                    path,
                    content=content,
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

    if Capability.SHELL_QUERY in runtime.principal.capabilities:

        @mcp.tool(title="Run read-only shell query", annotations=READ_ONLY_TOOL)
        def shell_query(
            argv: list[str],
            cwd: str = "/",
            timeout_seconds: int = 30,
            max_bytes: int = 64_000,
        ) -> dict[str, Any]:
            """Run exact argv in a transient user service with a read-only filesystem."""
            return runtime.execute(
                "shell_query",
                lambda: runtime.shell.query(argv, cwd, timeout_seconds, max_bytes),
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
        def project_write(project_id: str, path: str, content: str) -> dict[str, Any]:
            """Atomically write one project-relative file under operator policy."""
            return runtime.execute(
                "project_write",
                lambda: runtime.projects.write(project_id, path, content),
            )

        @mcp.tool(title="Apply project patch", annotations=DESTRUCTIVE_TOOL)
        def project_apply_patch(project_id: str, patch: str) -> dict[str, Any]:
            """Apply a bounded Git patch under operator policy."""
            return runtime.execute(
                "project_apply_patch",
                lambda: runtime.projects.apply_patch(project_id, patch),
            )

    return mcp
