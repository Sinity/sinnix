from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
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
from .contracts import TypedJobContracts
from .delivery import DeliveryError, GitHubDelivery
from .owner_adapters import DeclaredOwnerAdapters, OwnerAdapterError
from .projects import ProjectCatalog
from .workspaces import GitWorkspaces, WorkspaceError, WorkspaceStore


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
    native_runner: Path = Path("/home/sinity/.config/hermes/skills/agent-orchestration/scripts/run_agent_prompt.sh")
    workspaces: GitWorkspaces | None = None
    delivery: GitHubDelivery | None = None

    def __post_init__(self) -> None:
        if self.workspaces is None:
            object.__setattr__(self, "workspaces", GitWorkspaces(self.projects, WorkspaceStore(self.jobs.store.root)))
        if self.delivery is None:
            assert self.workspaces is not None
            object.__setattr__(self, "delivery", GitHubDelivery(self.projects, self.workspaces, self.jobs))
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
            OwnerSpec(
                namespace="workspace",
                owner="git-workspaces",
                authority=Authority.OWNER,
                lifecycle=Lifecycle.DAEMON_OWNED,
                versions=frozenset({1}),
                documentation="Durable workspace relationships over Git-owned linked worktrees.",
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
            payload = self._dispatch(request.operation, request.arguments, request.correlation_id, request.principal)
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
        except (WorkspaceError, DeliveryError) as error:
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

    def _dispatch(
        self,
        operation: str,
        arguments: Mapping[str, Any],
        correlation_id: str,
        principal: str,
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
        if operation == "workspace.list":
            if set(arguments) - {"project_id"}:
                raise ValueError("workspace.list accepts optional project_id")
            project_id = arguments.get("project_id")
            if project_id is not None and (not isinstance(project_id, str) or not project_id):
                raise ValueError("workspace.list project_id must be non-empty")
            assert self.workspaces is not None
            return self.workspaces.list(project_id)
        if operation == "workspace.get":
            assert self.workspaces is not None
            return self.workspaces.get(self._single_workspace_id(arguments, "workspace.get"))
        if operation == "workspace.create":
            if principal not in {"agent-control", "operator"}:
                raise ValueError("workspace creation requires agent-control or operator principal")
            required = {"project_id", "name", "branch", "base"}
            if set(arguments) != required:
                raise ValueError("workspace.create requires project_id, name, branch, and nullable base")
            base = arguments.get("base")
            if base is not None and (not isinstance(base, str) or not base):
                raise ValueError("workspace.create base must be null or non-empty")
            assert self.workspaces is not None
            return self.workspaces.create(
                project_id=self._job_argument(arguments, "project_id"),
                name=self._job_argument(arguments, "name"),
                branch=self._job_argument(arguments, "branch"),
                base=base,
            )
        if operation == "workspace.adopt":
            if principal not in {"agent-control", "operator"}:
                raise ValueError("workspace adoption requires agent-control or operator principal")
            required = {"project_id", "checkout_id", "name"}
            if set(arguments) != required:
                raise ValueError("workspace.adopt requires project_id, checkout_id, and name")
            assert self.workspaces is not None
            return self.workspaces.adopt(
                project_id=self._job_argument(arguments, "project_id"),
                checkout_id=self._job_argument(arguments, "checkout_id"),
                name=self._job_argument(arguments, "name"),
            )
        if operation == "workspace.reap":
            if principal not in {"agent-control", "operator"}:
                raise ValueError("workspace reap requires agent-control or operator principal")
            assert self.workspaces is not None
            return self.workspaces.reap(self._single_workspace_id(arguments, "workspace.reap"))
        if operation == "workspace.checkpoint":
            if principal not in {"agent-control", "operator"}:
                raise ValueError("workspace checkpoint requires agent-control or operator principal")
            assert self.workspaces is not None
            return self.workspaces.checkpoint(self._single_workspace_id(arguments, "workspace.checkpoint"))
        if operation == "workspace.restore":
            if principal not in {"agent-control", "operator"}:
                raise ValueError("workspace restore requires agent-control or operator principal")
            if set(arguments) != {"workspace_id", "checkpoint_id"}:
                raise ValueError("workspace.restore requires workspace_id and checkpoint_id")
            assert self.workspaces is not None
            return self.workspaces.restore(
                self._job_argument(arguments, "workspace_id"),
                self._job_argument(arguments, "checkpoint_id"),
            )
        if operation == "workspace.stack":
            if principal not in {"agent-control", "operator"}:
                raise ValueError("workspace stacking requires agent-control or operator principal")
            if set(arguments) != {"parent_workspace_id", "name", "branch"}:
                raise ValueError("workspace.stack requires parent_workspace_id, name, and branch")
            assert self.workspaces is not None
            return self.workspaces.stack(
                parent_workspace_id=self._job_argument(arguments, "parent_workspace_id"),
                name=self._job_argument(arguments, "name"),
                branch=self._job_argument(arguments, "branch"),
            )
        if operation == "workspace.restack":
            if principal not in {"agent-control", "operator"}:
                raise ValueError("workspace restacking requires agent-control or operator principal")
            assert self.workspaces is not None
            return self.workspaces.restack(self._single_workspace_id(arguments, "workspace.restack"))
        if operation == "workspace.publish":
            if principal not in {"agent-control", "operator"}:
                raise ValueError("workspace publication requires agent-control or operator principal")
            if set(arguments) != {"workspace_id", "job_id", "title", "body"}:
                raise ValueError("workspace.publish requires workspace_id, job_id, title, and body")
            assert self.delivery is not None
            return self.delivery.publish(
                self._job_argument(arguments, "workspace_id"),
                self._job_argument(arguments, "job_id"),
                self._job_argument(arguments, "title"),
                arguments.get("body") if isinstance(arguments.get("body"), str) else "",
            )
        if operation == "workspace.review-status":
            assert self.delivery is not None
            return self.delivery.review_status(self._single_workspace_id(arguments, "workspace.review-status"))
        if operation == "workspace.land":
            if principal not in {"agent-control", "operator"} or set(arguments) != {"workspace_id", "job_id"}:
                raise ValueError("workspace.land requires agent-control or operator plus workspace_id and job_id")
            assert self.delivery is not None
            return self.delivery.land(
                self._job_argument(arguments, "workspace_id"), self._job_argument(arguments, "job_id")
            )
        if operation == "workspace.finish":
            if principal not in {"agent-control", "operator"}:
                raise ValueError("workspace finish requires agent-control or operator principal")
            assert self.delivery is not None
            return self.delivery.finish(self._single_workspace_id(arguments, "workspace.finish"))
        if operation == "job.start":
            project_id = self._job_argument(arguments, "project_id")
            operation_name = self._job_argument(arguments, "operation")
            if set(arguments) - {"project_id", "operation", "workspace_id"}:
                raise ValueError("job.start accepts project_id, operation, and optional workspace_id")
            project = self.projects.get(project_id)
            workspace_id = arguments.get("workspace_id")
            if workspace_id is not None and (not isinstance(workspace_id, str) or not workspace_id):
                raise ValueError("job.start workspace_id must be null or non-empty")
            assert self.workspaces is not None
            checkout = self.workspaces.checkout(workspace_id) if workspace_id is not None else None
            return self._cleanup_terminal(self.jobs.start_declared(
                project=project,
                operation=project.operation(operation_name),
                correlation_id=correlation_id,
                checkout=checkout,
            ))
        if operation == "job.shell.start":
            required = {"project_id", "checkout_id", "argv", "cwd", "timeout_seconds", "result"}
            if set(arguments) != required:
                raise ValueError("job.shell.start requires project_id, checkout_id, argv, cwd, timeout_seconds, and result")
            argv = arguments["argv"]
            if not isinstance(argv, list):
                raise ValueError("job.shell.start argv must be a list")
            return self._cleanup_terminal(self.job_contracts.start_shell(
                principal=principal,
                project_id=self._job_argument(arguments, "project_id"),
                checkout_id=self._job_argument(arguments, "checkout_id"),
                argv=argv,
                cwd=self._job_argument(arguments, "cwd"),
                timeout_seconds=self._integer_argument(arguments, "timeout_seconds"),
                result=self._job_argument(arguments, "result"),
            ))
        if operation == "job.agent.start":
            required = {
                "project_id", "checkout_id", "prompt", "backend", "model", "effort", "credential_profile", "timeout_seconds", "result"
            }
            if set(arguments) != required:
                raise ValueError("job.agent.start requires the complete typed agent contract")
            return self._cleanup_terminal(self.job_contracts.start_agent(
                principal=principal,
                project_id=self._job_argument(arguments, "project_id"),
                checkout_id=self._job_argument(arguments, "checkout_id"),
                prompt=self._job_argument(arguments, "prompt"),
                backend=self._job_argument(arguments, "backend"),
                model=self._job_argument(arguments, "model"),
                effort=self._job_argument(arguments, "effort"),
                credential_profile=self._job_argument(arguments, "credential_profile"),
                timeout_seconds=self._integer_argument(arguments, "timeout_seconds"),
                result=self._job_argument(arguments, "result"),
            ))
        if operation == "job.get":
            return self._cleanup_terminal(self.jobs.get(self._single_job_id(arguments, "job.get")))
        if operation == "job.list":
            if arguments:
                raise ValueError("job.list accepts no arguments")
            return {"jobs": [self._cleanup_terminal(job) for job in self.jobs.list()["jobs"]]}
        if operation == "job.wait":
            job_id = self._job_argument(arguments, "job_id")
            timeout_seconds = arguments.get("timeout_seconds", 30)
            if set(arguments) - {"job_id", "timeout_seconds"}:
                raise ValueError("job.wait accepts job_id and optional timeout_seconds")
            if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
                raise ValueError("job.wait timeout_seconds must be an integer")
            return self._cleanup_terminal(self.jobs.wait(job_id, timeout_seconds))
        if operation == "job.logs":
            job_id = self._job_argument(arguments, "job_id")
            offset = arguments.get("offset", 0)
            max_bytes = arguments.get("max_bytes", 64_000)
            if set(arguments) - {"job_id", "offset", "max_bytes"}:
                raise ValueError("job.logs accepts job_id, optional offset, and optional max_bytes")
            if any(not isinstance(value, int) or isinstance(value, bool) for value in (offset, max_bytes)):
                raise ValueError("job.logs offset and max_bytes must be integers")
            return self.jobs.logs(job_id, offset=offset, max_bytes=max_bytes)
        if operation == "job.result":
            job_id = self._job_argument(arguments, "job_id")
            max_bytes = arguments.get("max_bytes", 64_000)
            if set(arguments) - {"job_id", "max_bytes"}:
                raise ValueError("job.result accepts job_id and optional max_bytes")
            if not isinstance(max_bytes, int) or isinstance(max_bytes, bool):
                raise ValueError("job.result max_bytes must be an integer")
            return self.jobs.result(job_id, max_bytes=max_bytes)
        if operation == "job.cancel":
            return self._cleanup_terminal(self.jobs.cancel(self._single_job_id(arguments, "job.cancel")))
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

    def _cleanup_terminal(self, response: Mapping[str, Any]) -> dict[str, Any]:
        return self.job_contracts.cleanup_terminal(response)

    @staticmethod
    def _single_workspace_id(arguments: Mapping[str, Any], operation: str) -> str:
        if set(arguments) != {"workspace_id"}:
            raise ValueError(f"{operation} requires workspace_id")
        value = arguments.get("workspace_id")
        if not isinstance(value, str) or not value:
            raise ValueError(f"{operation} workspace_id must be non-empty")
        return value

    @staticmethod
    def _job_argument(arguments: Mapping[str, Any], name: str) -> str:
        value = arguments.get(name)
        if not isinstance(value, str) or not value:
            raise ValueError(f"job operation requires {name}")
        return value

    @staticmethod
    def _integer_argument(arguments: Mapping[str, Any], name: str) -> int:
        value = arguments.get(name)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"job operation requires integer {name}")
        return value

    @property
    def job_contracts(self) -> TypedJobContracts:
        return TypedJobContracts(self.projects, self.jobs, self.native_runner)

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
