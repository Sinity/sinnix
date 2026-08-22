from __future__ import annotations

from dataclasses import dataclass
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

from .projects import ProjectCatalog


@dataclass(frozen=True)
class SinnixdService:
    """The initial stateless dispatch surface over explicit project adapters.

    This intentionally owns no job process, task record, Git state, or service
    state. Those owner routes are added only when their authoritative adapters
    are ready to move behind the daemon.
    """

    projects: ProjectCatalog
    version: str = "0.1.0"

    @property
    def owners(self) -> OwnerRegistry:
        return OwnerRegistry(
            [
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
            ]
        )

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
            payload = self._dispatch(request.operation, request.arguments)
        except KeyError as error:
            return self._error(request, owner_name, ErrorCode.INVALID_ARGUMENT, str(error))
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

    def _dispatch(self, operation: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
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
        raise ValueError(f"unsupported operation: {operation}")

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
