from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

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

from .campaign import CampaignRunner, WaveDrainedError
from .campaign_status import build_campaign_status
from .contracts import TypedJobContracts
from .delivery import DeliveryError, GitHubDelivery
from .delivery_runner import DELIVERY_INPUT_SCHEMA_VERSION, delivery_runner_executable
from .jobs import (
    AdmissionConflictError,
    GenericJobs,
    GenericJobSpec,
    GenericJobStore,
    JobPageCursorError,
    JobRecordError,
    JobResultError,
    JobResultLimitError,
    SystemdJobError,
    UserSystemdJobs,
    default_state_dir,
    scheduled_operation_id,
    scheduled_timer_unit,
)
from .owner_adapters import DeclaredOwnerAdapters, OwnerAdapterError
from .packet import PacketFinalizeSaga, PacketSagaError, PacketSagaStore
from .project_plans import PlanStore, ProjectPlanExecutor
from .projects import ProjectCatalog
from .reactor import CampaignBoard
from .tasks import TaskError, TaskService
from .workspaces import GitWorkspaces, WorkspaceError, WorkspaceStore


class JobAuthorizationError(PermissionError):
    """The caller does not own this job and is not the operator."""


# Delivery runs bounded Git/GitHub commands; these ceilings cover the command
# deadlines in delivery.py. They bound the background job, not a control
# worker: workspace.publish/land return a job id immediately.
DELIVERY_TIMEOUT_SECONDS = {"publish": 790, "land": 185}
CAPABILITIES = [
    "completion_events",
    "wait_any",
    "environment_require",
    "workspace_provision",
    "usage_capture",
    "timeout_wip_preserve",
]
# The dispatchable operation surface. A contract test keeps this in sync with
# the dispatch branches below and with the client response-budget table in
# api.py — extending dispatch without registering here (or without a budget)
# is a red test, not a silent 5s fallback.
SUPPORTED_OPERATIONS = frozenset(
    {
        "runtime.status",
        "project.list",
        "project.reload",
        "project.get",
        "project.operations",
        "plan.submit",
        "plan.get",
        "plan.list",
        "plan.wait",
        "plan.result",
        "packet.finalize",
        "packet.status",
        "campaign.run",
        "campaign.status",
        "workspace.list",
        "workspace.get",
        "workspace.create",
        "workspace.adopt",
        "workspace.reap",
        "workspace.dispose",
        "workspace.checkpoint",
        "workspace.restore",
        "workspace.recover",
        "workspace.stack",
        "workspace.restack",
        "workspace.publish",
        "workspace.review-status",
        "workspace.land",
        "workspace.finish",
        "workspace.finish-integrated",
        "job.start",
        "job.fire",
        "job.shell.start",
        "job.agent.start",
        "job.admission.reset",
        "job.admission",
        "job.admission.explain",
        "job.get",
        "job.retry",
        "job.resume",
        "job.list",
        "job.wait",
        "job.notify-exit",
        "job.logs",
        "job.result",
        "job.cancel",
        "task.complete",
    }
)


@dataclass(frozen=True)
class SinnixdService:
    """The initial stateless dispatch surface over explicit project adapters.

    This intentionally owns no job process, task record, Git state, or service
    state. Those owner routes are added only when their authoritative adapters
    are ready to move behind the daemon.
    """

    projects: ProjectCatalog
    jobs: GenericJobs = field(
        default_factory=lambda: GenericJobs(
            UserSystemdJobs(), GenericJobStore(default_state_dir())
        )
    )
    owner_adapters: DeclaredOwnerAdapters = field(
        default_factory=lambda: DeclaredOwnerAdapters(OwnerExecution())
    )
    version: str = "0.2.0"
    native_runner: Path = Path(
        "/home/sinity/.config/hermes/skills/agent-runtime/scripts/run_agent_prompt.sh"
    )
    workspaces: GitWorkspaces | None = None
    delivery: GitHubDelivery | None = None
    tasks: TaskService | None = None
    plans: ProjectPlanExecutor | None = None
    packet_sagas: PacketFinalizeSaga | None = None
    campaign_board_path: Path = Path("/realm/tmp/work/campaign-board.json")

    def __post_init__(self) -> None:
        if self.workspaces is None:
            object.__setattr__(
                self,
                "workspaces",
                GitWorkspaces(self.projects, WorkspaceStore(self.jobs.store.root)),
            )
        if self.delivery is None:
            assert self.workspaces is not None
            object.__setattr__(
                self,
                "delivery",
                GitHubDelivery(self.projects, self.workspaces, self.jobs),
            )
        if self.tasks is None:
            object.__setattr__(
                self, "tasks", TaskService(self.projects, jobs=self.jobs)
            )
        if self.plans is None:
            assert self.workspaces is not None
            object.__setattr__(
                self,
                "plans",
                ProjectPlanExecutor(
                    self.projects,
                    self.jobs,
                    PlanStore(self.jobs.store.root),
                    self.workspaces,
                ),
            )
        if self.packet_sagas is None:
            assert self.delivery is not None and self.tasks is not None
            object.__setattr__(
                self,
                "packet_sagas",
                PacketFinalizeSaga(
                    self.delivery,
                    self.tasks,
                    PacketSagaStore(self.jobs.store.root),
                ),
            )
        self.jobs.register_schedules(self.projects.scheduled_operations())
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
                lifecycle=Lifecycle.DAEMON_OWNED,
                versions=frozenset({1}),
                documentation="Declared project adapter catalog; reload re-reads descriptors.",
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
                namespace="plan",
                owner="project-plans",
                authority=Authority.SYSTEMD,
                lifecycle=Lifecycle.DAEMON_OWNED,
                versions=frozenset({1}),
                documentation="Bounded generic project execution plans over declared operation jobs.",
            ),
            OwnerSpec(
                namespace="campaign",
                owner="campaign-orchestrator",
                authority=Authority.SYSTEMD,
                lifecycle=Lifecycle.DAEMON_OWNED,
                versions=frozenset({1}),
                documentation="Ready-Beads packet campaign waves over the plan and job seams.",
            ),
            OwnerSpec(
                namespace="workspace",
                owner="git-workspaces",
                authority=Authority.OWNER,
                lifecycle=Lifecycle.DAEMON_OWNED,
                versions=frozenset({1}),
                documentation="Durable workspace relationships over Git-owned linked worktrees.",
            ),
            OwnerSpec(
                namespace="task",
                owner="task-backend",
                authority=Authority.TASK_BACKEND,
                lifecycle=Lifecycle.DAEMON_OWNED,
                versions=frozenset({1}),
                documentation="Backend-neutral AgentCTL task operations through the current task authority.",
            ),
            OwnerSpec(
                namespace="packet",
                owner="packet-saga",
                authority=Authority.OWNER,
                lifecycle=Lifecycle.DAEMON_OWNED,
                versions=frozenset({1}),
                documentation="Retryable packet land, task completion, and workspace finish saga.",
            ),
        )
        return OwnerRegistry(
            (*builtin, *(adapter.spec for adapter in self.projects.owner_adapters()))
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
            if owner.source_scoped:
                project, adapter = self.projects.owner_adapter(request.operation)
                return self.owner_adapters.call(
                    project=project, adapter=adapter, request=request
                )
            payload = self._dispatch(
                request.operation,
                request.arguments,
                request.correlation_id,
                request.principal,
                request.idempotency_key,
            )
        except KeyError as error:
            return self._error(
                request, owner_name, ErrorCode.INVALID_ARGUMENT, str(error)
            )
        except OwnerAdapterError as error:
            return self._error(
                request,
                owner_name,
                ErrorCode(error.code.upper()),
                str(error),
            )
        except JobResultLimitError as error:
            return self._error(
                request, owner_name, ErrorCode.RESOURCE_EXHAUSTED, str(error)
            )
        except JobResultError as error:
            return self._error(
                request, owner_name, ErrorCode.RESULT_INVALID, str(error)
            )
        except JobAuthorizationError as error:
            return self._error(request, owner_name, ErrorCode.POLICY_DENIED, str(error))
        except (AdmissionConflictError, WaveDrainedError) as error:
            return self._error(
                request, owner_name, ErrorCode.RESOURCE_DEFERRED, str(error)
            )
        except JobPageCursorError as error:
            return self._error(
                request, owner_name, ErrorCode.INVALID_ARGUMENT, str(error)
            )
        except (JobRecordError, SystemdJobError) as error:
            return self._error(
                request, owner_name, ErrorCode.OPERATION_FAILED, str(error)
            )
        except (WorkspaceError, DeliveryError) as error:
            return self._error(
                request, owner_name, ErrorCode.INVALID_ARGUMENT, str(error)
            )
        except TaskError as error:
            return self._error(request, owner_name, error.code, str(error))
        except PacketSagaError as error:
            return self._error(request, owner_name, error.code, str(error))
        except ValueError as error:
            return self._error(
                request, owner_name, ErrorCode.INVALID_ARGUMENT, str(error)
            )
        try:
            bounded_payload = OpaquePayload.bounded(payload)
        except ValueError as error:
            return self._error(
                request, owner_name, ErrorCode.RESOURCE_EXHAUSTED, str(error)
            )
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
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        if operation == "runtime.status":
            return {
                "version": self.version,
                "capabilities": list(CAPABILITIES),
                "owners": self.owners.catalog(),
                "projects": len(self.projects.list()),
                "backend_capacity": self.jobs.capacity_status(),
            }
        if operation == "project.list":
            return {
                "projects": self.projects.list(),
                "unavailable": [
                    {"root": root, "reason": reason}
                    for root, reason in sorted(self.projects.unavailable.items())
                ],
            }
        if operation == "project.reload":
            if principal not in {"agent-control", "operator"}:
                raise JobAuthorizationError(
                    "project reload requires agent-control or operator principal"
                )
            return self.projects.reload()
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
                "descriptor_status": project.descriptor_status(),
                "operations": [
                    operation.catalog_row() for operation in project.operations
                ],
            }
        if operation == "plan.submit":
            if principal not in {"agent-control", "operator"}:
                raise JobAuthorizationError(
                    "project plans require agent-control or operator principal"
                )
            assert self.plans is not None
            return self.plans.submit(
                arguments, correlation_id=correlation_id, principal=principal
            )
        if operation == "campaign.run":
            if principal not in {"agent-control", "operator"}:
                raise JobAuthorizationError(
                    "campaign waves require agent-control or operator principal"
                )
            allowed = {
                "project_id",
                "limit",
                "bead_ids",
                "dry_run",
                "credential_profile",
                "timeout_seconds",
            }
            if set(arguments) - allowed or not isinstance(
                arguments.get("project_id"), str
            ):
                raise ValueError(
                    "campaign.run requires project_id and accepts limit, dry_run, credential_profile, and timeout_seconds"
                )
            limit = arguments.get("limit")
            if limit is not None and (
                not isinstance(limit, int) or isinstance(limit, bool)
            ):
                raise ValueError("campaign.run limit must be an integer")
            bead_ids = arguments.get("bead_ids")
            if bead_ids is not None and (
                not isinstance(bead_ids, list)
                or not bead_ids
                or any(not isinstance(item, str) or not item for item in bead_ids)
            ):
                raise ValueError("campaign.run bead_ids must be a non-empty list")
            dry_run = arguments.get("dry_run", False)
            if not isinstance(dry_run, bool):
                raise ValueError("campaign.run dry_run must be boolean")
            credential_profile = arguments.get("credential_profile", "subscription")
            timeout_seconds = arguments.get("timeout_seconds", 3_600)
            if not isinstance(credential_profile, str) or not isinstance(
                timeout_seconds, int
            ):
                raise ValueError("campaign.run launch arguments are invalid")
            assert self.workspaces is not None and self.plans is not None
            return CampaignRunner(
                self.projects,
                self.jobs,
                self.workspaces,
                self.plans,
                self.native_runner,
            ).run(
                arguments["project_id"],
                limit=limit,
                bead_ids=bead_ids,
                dry_run=dry_run,
                credential_profile=credential_profile,
                timeout_seconds=timeout_seconds,
            )
        if operation == "campaign.status":
            if principal != "operator":
                raise JobAuthorizationError(
                    "campaign status requires the operator principal"
                )
            allowed = {"project_id", "coordinator_label"}
            if set(arguments) - allowed:
                raise ValueError(
                    "campaign.status accepts project_id and coordinator_label"
                )
            project_id = arguments.get("project_id")
            if not isinstance(project_id, str) or not project_id:
                raise ValueError("campaign.status requires project_id")
            label = arguments.get("coordinator_label")
            if label is not None and (not isinstance(label, str) or not label):
                raise ValueError("campaign.status coordinator_label must be a string")
            board = CampaignBoard.load(self.campaign_board_path)
            return build_campaign_status(
                project_id,
                self.jobs.store.list(),
                board,
                self.jobs.admission_ledger(),
                coordinator_label=label,
            )
        if operation == "plan.get":
            if set(arguments) != {"plan_id"}:
                raise ValueError("plan.get requires plan_id")
            assert self.plans is not None
            return self.plans.get(self._job_argument(arguments, "plan_id"))
        if operation == "plan.list":
            if set(arguments) - {"project_id"}:
                raise ValueError("plan.list accepts optional project_id")
            project_id = arguments.get("project_id")
            if project_id is not None and not isinstance(project_id, str):
                raise ValueError("plan.list project_id must be a string")
            assert self.plans is not None
            return self.plans.list(project_id=project_id)
        if operation == "plan.wait":
            if (
                set(arguments) - {"plan_id", "timeout_seconds"}
                or "plan_id" not in arguments
            ):
                raise ValueError(
                    "plan.wait requires plan_id and optional timeout_seconds"
                )
            timeout_seconds = arguments.get("timeout_seconds", 30)
            if not isinstance(timeout_seconds, int) or isinstance(
                timeout_seconds, bool
            ):
                raise ValueError("plan.wait timeout_seconds must be an integer")
            assert self.plans is not None
            return self.plans.wait(
                self._job_argument(arguments, "plan_id"), timeout_seconds
            )
        if operation == "plan.result":
            if set(arguments) - {"plan_id", "max_bytes"} or "plan_id" not in arguments:
                raise ValueError("plan.result requires plan_id and optional max_bytes")
            max_bytes = arguments.get("max_bytes", 64_000)
            if not isinstance(max_bytes, int) or isinstance(max_bytes, bool):
                raise ValueError("plan.result max_bytes must be an integer")
            assert self.plans is not None
            return self.plans.result(
                self._job_argument(arguments, "plan_id"), max_bytes=max_bytes
            )
        if operation.startswith("task."):
            assert self.tasks is not None
            return self.tasks.execute(
                operation=operation,
                arguments=dict(arguments),
                principal=principal,
                mutation_id=idempotency_key,
            )
        if operation == "packet.finalize":
            if principal not in {"agent-control", "operator"}:
                raise ValueError(
                    "packet finalization requires agent-control or operator principal"
                )
            if set(arguments) != {
                "workspace_id",
                "verification_job_id",
                "packet_job_id",
            }:
                raise ValueError(
                    "packet.finalize requires workspace_id, verification_job_id, and packet_job_id"
                )
            assert self.packet_sagas is not None
            return self.packet_sagas.finalize(
                workspace_id=self._workspace_argument(arguments, "packet.finalize"),
                verification_job_id=self._job_argument(
                    arguments, "verification_job_id"
                ),
                packet_job_id=self._job_argument(arguments, "packet_job_id"),
            )
        if operation == "packet.status":
            if principal not in {"agent-control", "operator", "observer"}:
                raise ValueError("packet status requires an authorized principal")
            if set(arguments) != {"saga_id"}:
                raise ValueError("packet.status requires saga_id")
            assert self.packet_sagas is not None
            return self.packet_sagas.status(self._job_argument(arguments, "saga_id"))
        if operation == "workspace.list":
            if set(arguments) - {"project_id"}:
                raise ValueError("workspace.list accepts optional project_id")
            project_id = arguments.get("project_id")
            if project_id is not None and (
                not isinstance(project_id, str) or not project_id
            ):
                raise ValueError("workspace.list project_id must be non-empty")
            assert self.workspaces is not None
            return self.workspaces.list(project_id)
        if operation == "workspace.get":
            assert self.workspaces is not None
            return self.workspaces.get(
                self._workspace_argument(arguments, "workspace.get")
            )
        if operation == "workspace.create":
            if principal not in {"agent-control", "operator"}:
                raise ValueError(
                    "workspace creation requires agent-control or operator principal"
                )
            required = {"project_id", "name", "branch", "base"}
            if set(arguments) - required - {"recover_dead"} or not required.issubset(
                arguments
            ):
                raise ValueError(
                    "workspace.create requires project_id, name, branch, and nullable base, and accepts recover_dead"
                )
            base = arguments.get("base")
            if base is not None and (not isinstance(base, str) or not base):
                raise ValueError("workspace.create base must be null or non-empty")
            recover_dead = arguments.get("recover_dead", False)
            if not isinstance(recover_dead, bool):
                raise ValueError("workspace.create recover_dead must be boolean")
            assert self.workspaces is not None
            return self.workspaces.create(
                project_id=self._job_argument(arguments, "project_id"),
                name=self._job_argument(arguments, "name"),
                branch=self._job_argument(arguments, "branch"),
                base=base,
                recover_dead=recover_dead,
                is_live=self._workspace_has_live_job if recover_dead else None,
            )
        if operation == "workspace.adopt":
            if principal not in {"agent-control", "operator"}:
                raise ValueError(
                    "workspace adoption requires agent-control or operator principal"
                )
            required = {"project_id", "checkout_id", "name"}
            if set(arguments) != required:
                raise ValueError(
                    "workspace.adopt requires project_id, checkout_id, and name"
                )
            assert self.workspaces is not None
            return self.workspaces.adopt(
                project_id=self._job_argument(arguments, "project_id"),
                checkout_id=self._job_argument(arguments, "checkout_id"),
                name=self._job_argument(arguments, "name"),
            )
        if operation == "workspace.reap":
            if principal not in {"agent-control", "operator"}:
                raise ValueError(
                    "workspace reap requires agent-control or operator principal"
                )
            assert self.workspaces is not None
            return self.workspaces.reap(
                self._workspace_argument(arguments, "workspace.reap")
            )
        if operation == "workspace.dispose":
            if principal not in {"agent-control", "operator"}:
                raise ValueError(
                    "workspace disposal requires agent-control or operator principal"
                )
            assert self.workspaces is not None
            if set(arguments) - {"workspace_id", "acknowledge_published"}:
                raise ValueError(
                    "workspace.dispose accepts workspace_id and optional acknowledge_published"
                )
            acknowledge = arguments.get("acknowledge_published", False)
            if not isinstance(acknowledge, bool):
                raise ValueError(
                    "workspace.dispose acknowledge_published must be boolean"
                )
            return self.workspaces.dispose(
                self._workspace_argument(arguments, "workspace.dispose"),
                acknowledge_published=acknowledge,
            )
        if operation == "workspace.checkpoint":
            if principal not in {"agent-control", "operator"}:
                raise ValueError(
                    "workspace checkpoint requires agent-control or operator principal"
                )
            assert self.workspaces is not None
            return self.workspaces.checkpoint(
                self._workspace_argument(arguments, "workspace.checkpoint")
            )
        if operation == "workspace.restore":
            if principal not in {"agent-control", "operator"}:
                raise ValueError(
                    "workspace restore requires agent-control or operator principal"
                )
            if set(arguments) != {"workspace_id", "checkpoint_id"}:
                raise ValueError(
                    "workspace.restore requires workspace_id and checkpoint_id"
                )
            assert self.workspaces is not None
            return self.workspaces.restore(
                self._workspace_argument(arguments, "workspace.restore"),
                self._job_argument(arguments, "checkpoint_id"),
            )
        if operation == "workspace.recover":
            if principal not in {"agent-control", "operator"}:
                raise ValueError(
                    "workspace recovery requires agent-control or operator principal"
                )
            if set(arguments) != {"workspace_id", "checkpoint_id"}:
                raise ValueError(
                    "workspace.recover requires workspace_id and checkpoint_id"
                )
            assert self.workspaces is not None
            return self.workspaces.recover(
                self._workspace_argument(arguments, "workspace.recover"),
                self._job_argument(arguments, "checkpoint_id"),
            )
        if operation == "workspace.stack":
            if principal not in {"agent-control", "operator"}:
                raise ValueError(
                    "workspace stacking requires agent-control or operator principal"
                )
            if set(arguments) != {"parent_workspace_id", "name", "branch"}:
                raise ValueError(
                    "workspace.stack requires parent_workspace_id, name, and branch"
                )
            assert self.workspaces is not None
            return self.workspaces.stack(
                parent_workspace_id=self.workspaces.resolve_id(
                    self._job_argument(arguments, "parent_workspace_id")
                ),
                name=self._job_argument(arguments, "name"),
                branch=self._job_argument(arguments, "branch"),
            )
        if operation == "workspace.restack":
            if principal not in {"agent-control", "operator"}:
                raise ValueError(
                    "workspace restacking requires agent-control or operator principal"
                )
            assert self.workspaces is not None
            return self.workspaces.restack(
                self._workspace_argument(arguments, "workspace.restack")
            )
        if operation == "workspace.publish":
            if principal not in {"agent-control", "operator"}:
                raise ValueError(
                    "workspace publication requires agent-control or operator principal"
                )
            if set(arguments) - {
                "workspace_id",
                "job_id",
                "packet_job_id",
                "title",
                "body",
            } or not {"workspace_id", "job_id", "title", "body"} <= set(arguments):
                raise ValueError(
                    "workspace.publish requires workspace_id, job_id, title, and body"
                )
            packet_job_id = arguments.get("packet_job_id")
            return self._start_delivery(
                "publish",
                principal,
                self._workspace_argument(arguments, "workspace.publish"),
                {
                    "workspace_id": self._workspace_argument(
                        arguments, "workspace.publish"
                    ),
                    "job_id": self._job_argument(arguments, "job_id"),
                    "title": self._job_argument(arguments, "title"),
                    "body": arguments.get("body")
                    if isinstance(arguments.get("body"), str)
                    else "",
                    **(
                        {"packet_job_id": packet_job_id}
                        if isinstance(packet_job_id, str)
                        else {}
                    ),
                },
            )
        if operation == "workspace.review-status":
            assert self.delivery is not None
            return self.delivery.review_status(
                self._workspace_argument(arguments, "workspace.review-status")
            )
        if operation == "workspace.land":
            if (
                principal not in {"agent-control", "operator"}
                or set(arguments) - {"workspace_id", "job_id", "packet_job_id"}
                or not {"workspace_id", "job_id"} <= set(arguments)
            ):
                raise ValueError(
                    "workspace.land requires agent-control or operator plus workspace_id and job_id"
                )
            packet_job_id = arguments.get("packet_job_id")
            return self._start_delivery(
                "land",
                principal,
                self._workspace_argument(arguments, "workspace.land"),
                {
                    "workspace_id": self._workspace_argument(
                        arguments, "workspace.land"
                    ),
                    "job_id": self._job_argument(arguments, "job_id"),
                    **(
                        {"packet_job_id": packet_job_id}
                        if isinstance(packet_job_id, str)
                        else {}
                    ),
                },
            )
        if operation == "workspace.finish":
            if principal not in {"agent-control", "operator"}:
                raise ValueError(
                    "workspace finish requires agent-control or operator principal"
                )
            assert self.delivery is not None
            allowed = {"workspace_id", "beads", "receipt", "partial_note"}
            if set(arguments) - allowed:
                raise ValueError("workspace.finish received unsupported arguments")
            self._validate_workspace_settlement(arguments)
            workspace_id = self._workspace_argument(arguments, "workspace.finish")
            project_id = self.workspaces.get(workspace_id)["project_id"]
            result = self.delivery.finish(workspace_id)
            return self._settle_workspace(result, arguments, project_id)
        if operation == "workspace.finish-integrated":
            if principal not in {"agent-control", "operator"}:
                raise ValueError(
                    "workspace.finish-integrated requires agent-control or operator"
                )
            allowed = {"workspace_id", "target_ref", "beads", "receipt", "partial_note"}
            if set(arguments) - allowed or not {
                "workspace_id",
                "target_ref",
            } <= set(arguments):
                raise ValueError(
                    "workspace.finish-integrated requires workspace_id and target_ref"
                )
            self._validate_workspace_settlement(arguments)
            assert self.workspaces is not None
            workspace_id = self._workspace_argument(
                arguments, "workspace.finish-integrated"
            )
            project_id = self.workspaces.get(workspace_id)["project_id"]
            result = self.workspaces.finish_integrated(
                workspace_id,
                self._job_argument(arguments, "target_ref"),
            )
            return self._settle_workspace(result, arguments, project_id)
        if operation == "job.start":
            if principal not in {"agent-control", "operator"}:
                raise JobAuthorizationError(
                    "declared operations require agent-control or operator principal"
                )
            project_id = self._job_argument(arguments, "project_id")
            operation_name = self._job_argument(arguments, "operation")
            if set(arguments) - {
                "project_id",
                "operation",
                "workspace_id",
                "parameters",
                "bead_binding",
                "dimensions",
            }:
                raise ValueError(
                    "job.start accepts project_id, operation, optional workspace_id, optional parameters, and optional bead_binding"
                )
            parameters = arguments.get("parameters", {})
            if not isinstance(parameters, Mapping):
                raise ValueError("job.start parameters must be an object")
            dimensions = arguments.get("dimensions", {})
            if not isinstance(dimensions, Mapping):
                raise ValueError("job.start dimensions must be an object")
            project = self.projects.get(project_id)
            workspace_id = arguments.get("workspace_id")
            if workspace_id is not None and (
                not isinstance(workspace_id, str) or not workspace_id
            ):
                raise ValueError("job.start workspace_id must be null or non-empty")
            assert self.workspaces is not None
            checkout = (
                self.workspaces.resolve_checkout(project_id, workspace_id)
                if workspace_id is not None
                else self.projects.checkout(project_id, "default")
            )
            binding = arguments.get("bead_binding")
            if (
                binding is not None
                and operation_name not in project.workspace.verification_operations
            ):
                raise ValueError(
                    "a Beads packet binding requires a declared verification operation"
                )
            packet_contract = (
                {"bead_binding": self.job_contracts.bead_binding(binding, checkout)}
                if binding is not None
                else {}
            )
            return self._cleanup_terminal(
                self.jobs.start_declared(
                    project=project,
                    operation=project.operation(operation_name),
                    correlation_id=correlation_id,
                    principal=principal,
                    parameters=parameters,
                    checkout=checkout,
                    contract=packet_contract,
                    dimensions=dimensions,
                )
            )
        if operation == "job.fire":
            if principal != "operator":
                raise JobAuthorizationError(
                    "scheduled operation firing requires the operator principal"
                )
            if set(arguments) != {"project_id", "operation", "schedule_id"}:
                raise ValueError(
                    "job.fire requires project_id, operation, and schedule_id"
                )
            project_id = self._job_argument(arguments, "project_id")
            operation_name = self._job_argument(arguments, "operation")
            schedule_id = self._job_argument(arguments, "schedule_id")
            project = self.projects.get(project_id)
            declared = project.operation(operation_name)
            expected_id = scheduled_operation_id(project_id, operation_name)
            if declared.schedule is None or schedule_id != expected_id:
                raise ValueError(
                    "job.fire does not match a declared operation schedule"
                )
            checkout = self.projects.checkout(project_id, "default")
            return self._cleanup_terminal(
                self.jobs.start_declared(
                    project=project,
                    operation=declared,
                    correlation_id=correlation_id,
                    principal=principal,
                    parameters={},
                    checkout=checkout,
                    dimensions={
                        "trigger": "systemd-timer",
                        "schedule_id": schedule_id,
                        "schedule": declared.schedule,
                        "timer_unit": scheduled_timer_unit(schedule_id) + ".timer",
                    },
                )
            )
        if operation == "job.shell.start":
            required = {
                "project_id",
                "checkout_id",
                "argv",
                "cwd",
                "timeout_seconds",
                "result",
            }
            if set(arguments) != required:
                raise ValueError(
                    "job.shell.start requires project_id, checkout_id, argv, cwd, timeout_seconds, and result"
                )
            argv = arguments["argv"]
            if not isinstance(argv, list):
                raise ValueError("job.shell.start argv must be a list")
            return self._cleanup_terminal(
                self.job_contracts.start_shell(
                    principal=principal,
                    project_id=self._job_argument(arguments, "project_id"),
                    checkout_id=self._job_argument(arguments, "checkout_id"),
                    argv=argv,
                    cwd=self._job_argument(arguments, "cwd"),
                    timeout_seconds=self._integer_argument(
                        arguments, "timeout_seconds"
                    ),
                    result=self._job_argument(arguments, "result"),
                )
            )
        if operation == "job.agent.start":
            required = {
                "project_id",
                "checkout_id",
                "prompt",
                "backend",
                "model",
                "effort",
                "credential_profile",
                "timeout_seconds",
                "result",
            }
            if not required <= set(arguments) or set(arguments) - (
                required
                | {
                    "bead_binding",
                    "parameters",
                    "admission_bypass",
                    "dimensions",
                    "exclusive_keys",
                    "reject_conflicts",
                    "coordinator_label",
                }
            ):
                raise ValueError(
                    "job.agent.start requires the complete typed agent contract"
                )
            return self._cleanup_terminal(
                self.job_contracts.start_agent(
                    principal=principal,
                    project_id=self._job_argument(arguments, "project_id"),
                    checkout_id=self._job_argument(arguments, "checkout_id"),
                    prompt=self._job_argument(arguments, "prompt"),
                    backend=self._job_argument(arguments, "backend"),
                    model=self._job_argument(arguments, "model"),
                    effort=self._job_argument(arguments, "effort"),
                    credential_profile=self._job_argument(
                        arguments, "credential_profile"
                    ),
                    timeout_seconds=self._integer_argument(
                        arguments, "timeout_seconds"
                    ),
                    result=self._job_argument(arguments, "result"),
                    bead_binding=arguments.get("bead_binding"),
                    parameters=arguments.get("parameters"),
                    admission_bypass=arguments.get("admission_bypass", False),
                    dimensions=arguments.get("dimensions"),
                    exclusive_keys=arguments.get("exclusive_keys", ()),
                    reject_conflicts=arguments.get("reject_conflicts", False),
                    coordinator_label=arguments.get("coordinator_label"),
                )
            )
        if operation == "job.admission.reset":
            if principal != "operator":
                raise JobAuthorizationError(
                    "admission estimate reset requires the operator principal"
                )
            if set(arguments) - {"estimate_key", "all"}:
                raise ValueError("job.admission.reset accepts estimate_key or all")
            estimate_key = arguments.get("estimate_key")
            if estimate_key is not None and (
                not isinstance(estimate_key, str) or not estimate_key
            ):
                raise ValueError("job.admission.reset estimate_key must be non-empty")
            clear_all = arguments.get("all", False)
            if not isinstance(clear_all, bool):
                raise ValueError("job.admission.reset all must be a boolean")
            if (estimate_key is None and not clear_all) or (
                estimate_key is not None and clear_all
            ):
                raise ValueError(
                    "job.admission.reset requires estimate_key or all=true"
                )
            return self.jobs.reset_admission_estimates(estimate_key)
        if operation == "job.admission":
            if principal != "operator":
                raise JobAuthorizationError(
                    "job admission ledger requires the operator principal"
                )
            if set(arguments) - {"project_id"}:
                raise ValueError("job.admission accepts optional project_id")
            project_id = arguments.get("project_id")
            if project_id is not None and (
                not isinstance(project_id, str) or not project_id
            ):
                raise ValueError("job.admission project_id must be non-empty")
            return self.jobs.admission_ledger(project_id)
        if operation == "job.admission.explain":
            if principal != "operator":
                raise JobAuthorizationError(
                    "admission explanation requires the operator principal"
                )
            if set(arguments) != {"job_id"} or not isinstance(
                arguments.get("job_id"), str
            ):
                raise ValueError("job.admission.explain requires job_id")
            return self.jobs.admission_explain(arguments["job_id"])
        if operation == "job.get":
            return self._cleanup_terminal(
                self.jobs.get(
                    self._authorize_job(
                        principal, self._single_job_id(arguments, "job.get")
                    )
                )
            )
        if operation == "job.retry":
            if principal not in {"agent-control", "operator"}:
                raise JobAuthorizationError(
                    "job retry requires agent-control or operator principal"
                )
            if set(arguments) - {"job_id", "hint", "escalate"}:
                raise ValueError("job.retry accepts job_id, hint, and escalate")
            escalate = arguments.get("escalate", False)
            if not isinstance(escalate, bool):
                raise ValueError("job.retry escalate must be boolean")
            hint = arguments.get("hint")
            if hint is not None and not isinstance(hint, str):
                raise ValueError("job.retry hint must be a string")
            return self._cleanup_terminal(
                self.job_contracts.retry_agent(
                    job_id=self._authorize_job(
                        principal, self._job_argument(arguments, "job_id")
                    ),
                    hint=hint,
                    escalate=escalate,
                )
            )
        if operation == "job.resume":
            if principal not in {"agent-control", "operator"}:
                raise JobAuthorizationError(
                    "job resume requires agent-control or operator principal"
                )
            if set(arguments) != {"job_id", "native_session_id"}:
                raise ValueError("job.resume requires job_id and native_session_id")
            session_id = arguments["native_session_id"]
            if not isinstance(session_id, str):
                raise ValueError("job.resume native_session_id must be a string")
            return self._cleanup_terminal(
                self.job_contracts.resume_agent(
                    job_id=self._authorize_job(
                        principal, self._job_argument(arguments, "job_id")
                    ),
                    native_session_id=session_id,
                )
            )
        if operation == "job.list":
            if set(arguments) - {
                "limit",
                "cursor",
                "project_id",
                "phases",
                "kinds",
                "active_only",
            }:
                raise ValueError(
                    "job.list accepts only pagination and filter arguments"
                )
            limit = arguments.get("limit", 100)
            if not isinstance(limit, int) or isinstance(limit, bool):
                raise ValueError("job.list limit must be an integer")
            cursor = arguments.get("cursor")
            if cursor is not None and not isinstance(cursor, str):
                raise ValueError("job.list cursor must be a string")
            project_id = arguments.get("project_id")
            if project_id is not None and not isinstance(project_id, str):
                raise ValueError("job.list project_id must be a string")
            phases = arguments.get("phases", [])
            if not isinstance(phases, list) or any(
                not isinstance(phase, str) for phase in phases
            ):
                raise ValueError("job.list phases must be a list of strings")
            kinds = arguments.get("kinds", [])
            if not isinstance(kinds, list) or any(
                not isinstance(kind, str) for kind in kinds
            ):
                raise ValueError("job.list kinds must be a list of strings")
            active_only = arguments.get("active_only", False)
            if not isinstance(active_only, bool):
                raise ValueError("job.list active_only must be a boolean")
            return self._cleanup_terminal(
                self.jobs.list(
                    principal=principal,
                    limit=limit,
                    cursor=cursor,
                    project_id=project_id,
                    phases=tuple(phases),
                    kinds=tuple(kinds),
                    active_only=active_only,
                )
            )
        if operation == "job.wait":
            timeout_seconds = arguments.get("timeout_seconds", 30)
            if not isinstance(timeout_seconds, int) or isinstance(
                timeout_seconds, bool
            ):
                raise ValueError("job.wait timeout_seconds must be an integer")
            if "job_ids" in arguments:
                if set(arguments) - {"job_ids", "timeout_seconds"}:
                    raise ValueError(
                        "job.wait accepts job_ids and optional timeout_seconds"
                    )
                job_ids = arguments.get("job_ids")
                if not isinstance(job_ids, list) or any(
                    not isinstance(job_id, str) or not job_id for job_id in job_ids
                ):
                    raise ValueError("job.wait job_ids must be non-empty strings")
                authorized = tuple(
                    self._authorize_job(principal, job_id) for job_id in job_ids
                )
                return self._cleanup_terminal(
                    self.jobs.wait_any(authorized, timeout_seconds)
                )
            job_id = self._authorize_job(
                principal, self._job_argument(arguments, "job_id")
            )
            if set(arguments) - {"job_id", "timeout_seconds"}:
                raise ValueError("job.wait accepts job_id and optional timeout_seconds")
            return self._cleanup_terminal(self.jobs.wait(job_id, timeout_seconds))
        if operation == "job.notify-exit":
            if set(arguments) - {"job_id", "exit_code", "dimensions"}:
                raise ValueError(
                    "job.notify-exit accepts job_id, exit_code, and optional dimensions"
                )
            dimensions = arguments.get("dimensions")
            if dimensions is not None and not isinstance(dimensions, Mapping):
                raise ValueError("job.notify-exit dimensions must be an object")
            return self.jobs.notify_exit(
                self._job_argument(arguments, "job_id"), dimensions
            )
        if operation == "job.logs":
            job_id = self._authorize_job(
                principal, self._job_argument(arguments, "job_id")
            )
            offset = arguments.get("offset", 0)
            max_bytes = arguments.get("max_bytes", 64_000)
            if set(arguments) - {"job_id", "offset", "max_bytes"}:
                raise ValueError(
                    "job.logs accepts job_id, optional offset, and optional max_bytes"
                )
            if any(
                not isinstance(value, int) or isinstance(value, bool)
                for value in (offset, max_bytes)
            ):
                raise ValueError("job.logs offset and max_bytes must be integers")
            return self.jobs.logs(job_id, offset=offset, max_bytes=max_bytes)
        if operation == "job.result":
            job_id = self._authorize_job(
                principal, self._job_argument(arguments, "job_id")
            )
            max_bytes = arguments.get("max_bytes", 64_000)
            if set(arguments) - {"job_id", "max_bytes"}:
                raise ValueError("job.result accepts job_id and optional max_bytes")
            if not isinstance(max_bytes, int) or isinstance(max_bytes, bool):
                raise ValueError("job.result max_bytes must be an integer")
            return self.jobs.result(job_id, max_bytes=max_bytes)
        if operation == "job.cancel":
            return self._cleanup_terminal(
                self.jobs.cancel(
                    self._authorize_job(
                        principal, self._single_job_id(arguments, "job.cancel")
                    )
                )
            )
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

    def _start_delivery(
        self,
        operation: str,
        principal: str,
        workspace_id: str,
        call_arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Launch publish/land as a bounded background job and return its id.

        Delivery preconditions are re-verified inside the runner against the
        durable stores; holding a control worker for the full Git/GitHub
        conversation starved every other caller of the daemon.
        """
        assert self.workspaces is not None
        workspace = self.workspaces.get(workspace_id)
        project = self.projects.get(workspace["project_id"])
        job_id = str(uuid4())
        input_path = self.jobs.store.root / "inputs" / f"{job_id}.json"
        private = {
            "schema_version": DELIVERY_INPUT_SCHEMA_VERSION,
            "operation": operation,
            "project_root": str(project.root),
            "state_dir": str(self.jobs.store.root),
            "arguments": dict(call_arguments),
        }
        self.job_contracts.write_private(
            input_path,
            json.dumps(private, sort_keys=True, separators=(",", ":")).encode(),
        )
        try:
            return self.jobs.start(
                GenericJobSpec(
                    kind="delivery-operation",
                    command=(
                        str(delivery_runner_executable()),
                        "--input",
                        str(input_path),
                    ),
                    working_directory=str(project.root),
                    environment=project.environment.values(),
                    timeout_seconds=DELIVERY_TIMEOUT_SECONDS[operation],
                    project_id=project.project_id,
                    operation=f"workspace.{operation}",
                    principal=principal,
                    contract={
                        "operation": f"workspace.{operation}",
                        "workspace_id": workspace_id,
                    },
                    result_kind="json",
                ),
                job_id,
            )
        except BaseException:
            input_path.unlink(missing_ok=True)
            raise

    def _settle_workspace(
        self,
        result: dict[str, Any],
        arguments: Mapping[str, Any],
        project_id: str,
    ) -> dict[str, Any]:
        """Apply an authored landing receipt and publish one completion event."""
        self._validate_workspace_settlement(arguments)
        beads = arguments.get("beads", [])
        if (
            not isinstance(beads, list)
            or not beads
            or any(not isinstance(item, str) or not item for item in beads)
        ):
            if "beads" in arguments:
                raise ValueError("beads must be a non-empty list of IDs")
            beads = []
        receipt = arguments.get("receipt")
        partial_note = arguments.get("partial_note")
        if receipt is not None and not isinstance(receipt, Mapping):
            raise ValueError("receipt must map bead IDs to authored close reasons")
        if partial_note is not None and (
            not isinstance(partial_note, str) or not partial_note.strip()
        ):
            raise ValueError("partial_note must be a non-empty string")
        if beads and receipt is None and partial_note is None:
            raise ValueError("each bead requires an authored receipt or partial note")
        if receipt is not None and set(receipt) != set(beads):
            raise ValueError("receipt must contain exactly the beads being settled")
        settled: list[str] = []
        if self.tasks is not None:
            for bead_id in beads:
                value = receipt[bead_id] if receipt is not None else partial_note
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"missing authored receipt for bead {bead_id}")
                operation = "task.complete" if receipt is not None else "task.note"
                task_args = (
                    {
                        "project_id": project_id,
                        "task_id": bead_id,
                        "reason": value,
                        "merge_sha": result["head"],
                    }
                    if operation == "task.complete"
                    else {"project_id": project_id, "task_id": bead_id, "text": value}
                )
                self.tasks.execute(
                    operation=operation,
                    arguments=task_args,
                    principal="operator",
                )
                settled.append(bead_id)
        disposition = (
            "close" if receipt is not None else ("comment" if beads else "none")
        )
        event = {
            "schema_version": 1,
            "kind": "workspace_completion",
            "workspace_id": result["workspace_id"],
            "target_ref": arguments.get("target_ref", result.get("head")),
            "beads_settled": settled,
            "disposition": disposition,
        }
        self.jobs.spool_event(event)
        return {
            **result,
            "beads_settled": settled,
            "disposition": disposition,
            "completion_event": event,
        }

    @staticmethod
    def _validate_workspace_settlement(arguments: Mapping[str, Any]) -> None:
        beads = arguments.get("beads", [])
        if "beads" in arguments and (
            not isinstance(beads, list)
            or not beads
            or any(not isinstance(item, str) or not item for item in beads)
        ):
            raise ValueError("beads must be a non-empty list of IDs")
        receipt = arguments.get("receipt")
        note = arguments.get("partial_note")
        if receipt is not None and (
            not isinstance(receipt, Mapping) or set(receipt) != set(beads)
        ):
            raise ValueError("receipt must contain exactly the beads being settled")
        if note is not None and (not isinstance(note, str) or not note.strip()):
            raise ValueError("partial_note must be a non-empty string")
        if beads and receipt is None and note is None:
            raise ValueError("each bead requires an authored receipt or partial note")

    def _cleanup_terminal(self, response: Mapping[str, Any]) -> dict[str, Any]:
        return self.job_contracts.cleanup_terminal(response)

    def _workspace_has_live_job(self, path: Path) -> bool:
        active = self.jobs.list(
            principal="operator",
            project_id=None,
            kinds=("attested-agent",),
            active_only=True,
        )
        for job in active["jobs"]:
            checkout = job.get("checkout") if isinstance(job, Mapping) else None
            if isinstance(checkout, Mapping) and checkout.get("path") == str(path):
                return True
        return False

    def _workspace_argument(self, arguments: Mapping[str, Any], operation: str) -> str:
        value = arguments.get("workspace_id")
        if not isinstance(value, str) or not value:
            raise ValueError(f"{operation} workspace_id must be non-empty")
        assert self.workspaces is not None
        return self.workspaces.resolve_id(value)

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

    def _authorize_job(self, principal: str, job_id: str) -> str:
        record = self.jobs.store.load(job_id)
        if principal == "operator" or record.spec.principal == principal:
            return job_id
        raise JobAuthorizationError(
            "job access requires its creator or the operator principal"
        )

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
