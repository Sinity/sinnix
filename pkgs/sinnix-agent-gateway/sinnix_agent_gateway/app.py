from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .artifacts import ArtifactService
from .audit import AuditService
from .capabilities import Capability, Principal
from .captures import CaptureService
from .config import GatewayConfig
from .files import HostFileService
from .jobs import JobService
from .observe import ObserveService
from .projects import ProjectService
from .redaction import public_error
from .schemas import AgentLaunchRequest
from .sessions import SessionLogService
from .shell import ShellService

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
    captures: CaptureService
    files: HostFileService
    sessions: SessionLogService
    shell: ShellService

    @classmethod
    def create(cls, config: GatewayConfig, principal_name: str) -> "Runtime":
        principal = Principal.for_name(principal_name)
        artifacts = ArtifactService(config, principal)
        return cls(
            principal_name=principal_name,
            principal=principal,
            config=config,
            projects=ProjectService(config, principal),
            artifacts=artifacts,
            audit=AuditService(config, principal),
            jobs=JobService(config, principal, artifacts),
            observe=ObserveService(config, principal),
            captures=CaptureService(config, principal),
            files=HostFileService(config, principal),
            sessions=SessionLogService(config, principal),
            shell=ShellService(config, principal),
        )

    def execute(self, operation: str, callback: Callable[[], T]) -> T:
        try:
            result = callback()
        except Exception as exc:
            message = public_error(exc)
            self.audit.append(operation, "error", {"error": message})
            raise ValueError(message) from None
        payload: dict[str, Any] = {}
        if isinstance(result, dict):
            for key in ("job_id", "artifact_id", "project_id", "unit"):
                value = result.get(key)
                if isinstance(value, (str, int, float, bool)):
                    payload[key] = value
            if "job_id" in payload:
                payload["correlation_id"] = payload["job_id"]
        self.audit.append(operation, "ok", payload)
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
