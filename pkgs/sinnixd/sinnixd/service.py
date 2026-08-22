from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from sinnix_mcp import (
    Authority,
    ErrorCode,
    ErrorEnvelope,
    Lifecycle,
    OpaquePayload,
    OwnerRegistry,
    OwnerSpec,
    RequestEnvelope,
    ResponseEnvelope,
)
from sinnix_mcp.execution import OwnerExecution

from .jobs import GenericJobStore, GenericJobs, JobRecordError, SystemdJobError, UserSystemdJobs, default_state_dir
from .owner_adapters import DeclaredOwnerAdapters, OwnerAdapterError
from .projects import ProjectCatalog


@dataclass(frozen=True)
class SinnixdService:
    """The initial stateless dispatch surface over explicit project adapters.

    This intentionally owns no job process, task record, Git state, or service
    state. Those owner routes are added only when their authoritative adapters
    are ready to move behind the daemon.
    """

    projects: ProjectCatalog
    jobs: GenericJobs = field(
        default_factory=lambda: GenericJobs(UserSystemdJobs(), GenericJobStore(default_state_dir()))
    )
    owner_adapters: DeclaredOwnerAdapters = field(
        default_factory=lambda: DeclaredOwnerAdapters(OwnerExecution())
    )
    version: str = "0.2.0"

    def __post_init__(self) -> None:
        _ = self.owners

    @property
    def owners(self) -> OwnerRegistry:
        builtin = (
            OwnerSpec(
                namespace="runtime",
                owner="sinnixd",
                authority=Authority.OWNER,
                lifecycle=Lifecycle.DAEMON_OWNED,
                versions=frozenset({1}),
                documentation="Sinnix runtime discovery and project adapter catalog.",
            ),
            OwnerSpec(
                namespace="project",
                owner="project-adapters",
                authority=Authority.OWNER,
                lifecycle=Lifecycle.READ_ONLY,
                versions=frozenset({1}),
                documentation="Declared project adapter discovery and operation catalog.",
            ),
            OwnerSpec(
                namespace="job",
                owner="systemd-jobs",
                authority=Authority.SYSTEMD,
                lifecycle=Lifecycle.DAEMON_OWNED,
                versions=frozenset({1}),
                documentation="Durable generic jobs reconciled from transient user services.",
            ),
        )
        return OwnerRegistry((*builtin, *(adapter.spec for adapter in self.projects.owner_adapters())))

    def dispatch(self, request: RequestEnvelope) -> ResponseEnvelope:
        owner_name = "sinnixd"
        try:
            owner = self.owners.resolve(request.operation, request.schema)
            owner_name = owner.owner
            if request.owner != owner.owner:
                return self._error(
                    request,
                    owner_name,
                    ErrorCode.AUTHORITY_MISMATCH,
                    f"operation {request.operation!r} belongs to {owner.owner!r}, not {request.owner!r}",
                )
            if owner.source_scoped:
                project, adapter = self.projects.owner_adapter(request.operation)
                return self.owner_adapters.call(project=project, adapter=adapter, request=request)
            payload = self._dispatch(request.operation, request.arguments, request.correlation_id)
        except KeyError as error:
            return self._error(request, owner_name, ErrorCode.INVALID_ARGUMENT, str(error))
        except OwnerAdapterError as error:
            return self._error(
                request,
                owner_name,
                ErrorCode(error.code.upper()),
                str(error),
            )
        except (JobRecordError, SystemdJobError) as error:
            return self._error(request, owner_name, ErrorCode.OPERATION_FAILED, str(error))
        except ValueError as error:
            return self._error(request, owner_name, ErrorCode.INVALID_ARGUMENT, str(error))
        try:
            bounded_payload = OpaquePayload.bounded(payload)
        except ValueError as error:
            return self._error(request, owner_name, ErrorCode.RESOURCE_EXHAUSTED, str(error))
        return ResponseEnvelope(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            owner=owner_name,
            payload=bounded_payload,
        )

    def _dispatch(
        self,
        operation: str,
        arguments: Mapping[str, Any],
        correlation_id: str,
    ) -> dict[str, Any]:
        if operation == "runtime.status":
            return {
                "version": self.version,
                "owners": self.owners.catalog(),
                "projects": len(self.projects.list()),
            }
        if operation == "project.list":
            return {"projects": self.projects.list()}
        if operation == "project.get":
            project_id = arguments.get("project_id")
            if not isinstance(project_id, str) or not project_id:
                raise ValueError("project.get requires project_id")
            return self.projects.get(project_id).catalog_row()
        if operation == "project.operations":
            project_id = arguments.get("project_id")
            if not isinstance(project_id, str) or not project_id:
                raise ValueError("project.operations requires project_id")
            project = self.projects.get(project_id)
            return {
                "project_id": project.project_id,
                "operations": [operation.catalog_row() for operation in project.operations],
            }
        if operation == "job.start":
            project_id = self._job_argument(arguments, "project_id")
            operation_name = self._job_argument(arguments, "operation")
            if set(arguments) != {"project_id", "operation"}:
                raise ValueError("job.start accepts only project_id and operation")
            project = self.projects.get(project_id)
            return self.jobs.start_declared(
                project=project,
                operation=project.operation(operation_name),
                correlation_id=correlation_id,
            )
        if operation == "job.get":
            return self.jobs.get(self._single_job_id(arguments, "job.get"))
        if operation == "job.list":
            if arguments:
                raise ValueError("job.list accepts no arguments")
            return self.jobs.list()
        if operation == "job.wait":
            job_id = self._job_argument(arguments, "job_id")
            timeout_seconds = arguments.get("timeout_seconds", 30)
            if set(arguments) - {"job_id", "timeout_seconds"}:
                raise ValueError("job.wait accepts job_id and optional timeout_seconds")
            if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
                raise ValueError("job.wait timeout_seconds must be an integer")
            return self.jobs.wait(job_id, timeout_seconds)
        if operation == "job.logs":
            job_id = self._job_argument(arguments, "job_id")
            offset = arguments.get("offset", 0)
            max_bytes = arguments.get("max_bytes", 64_000)
            if set(arguments) - {"job_id", "offset", "max_bytes"}:
                raise ValueError("job.logs accepts job_id, optional offset, and optional max_bytes")
            if any(not isinstance(value, int) or isinstance(value, bool) for value in (offset, max_bytes)):
                raise ValueError("job.logs offset and max_bytes must be integers")
            return self.jobs.logs(job_id, offset=offset, max_bytes=max_bytes)
        if operation == "job.cancel":
            return self.jobs.cancel(self._single_job_id(arguments, "job.cancel"))
        raise ValueError(f"unsupported operation: {operation}")

    def start_foreground(
        self,
        *,
        command: tuple[str, ...],
        working_directory: str,
        environment: Mapping[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        """Create an internal foreground job without widening the RPC authority."""

        return self.jobs.start_foreground(
            command=command,
            working_directory=working_directory,
            environment=environment,
            timeout_seconds=timeout_seconds,
        )

    @staticmethod
    def _job_argument(arguments: Mapping[str, Any], name: str) -> str:
        value = arguments.get(name)
        if not isinstance(value, str) or not value:
            raise ValueError(f"job operation requires {name}")
        return value

    def _single_job_id(self, arguments: Mapping[str, Any], operation: str) -> str:
        if set(arguments) != {"job_id"}:
            raise ValueError(f"{operation} accepts only job_id")
        return self._job_argument(arguments, "job_id")

    def _error(
        self,
        request: RequestEnvelope,
        owner: str,
        code: ErrorCode,
        message: str,
    ) -> ResponseEnvelope:
        return ResponseEnvelope(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            owner=owner,
            error=ErrorEnvelope(code, message),
        )
