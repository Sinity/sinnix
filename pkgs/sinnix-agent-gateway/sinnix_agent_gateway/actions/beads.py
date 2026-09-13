"""Beads task actions: typed operations over the project task authority."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, create_model, model_validator

from ..action import (
    ALL_PRINCIPALS,
    OPERATOR_ONLY,
    Action,
    Example,
    MutationControls,
    RequestControls,
)
from ..contracts import VerbFamily
from ..generated_beads_inputs import OwnerReadInput
from ..locators import BeadLocator, ProjectLocator, project_ref
from ..results import ProtocolError
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime

View = Literal[
    "query",
    "ready",
    "blocked",
    "open",
    "all",
    "recent",
    "overdue",
    "deferred",
    "unassigned",
    "stale_claims",
    "epic_progress",
    "changed_since",
]
Include = Literal[
    "comments",
    "history",
    "events",
    "dependencies",
    "dependents",
    "children",
    "refs",
    "blockers",
]
OrderField = Literal[
    "priority",
    "created",
    "updated",
    "closed",
    "status",
    "id",
    "title",
    "type",
    "assignee",
]
_BEAD_ID = Field(min_length=1, max_length=128)
_KINDS = ("project", "bead", "task_authority")


class Order(GatewayModel):
    field: OrderField
    reverse: bool = False


class GraphQuery(GatewayModel):
    bead: str = Field(min_length=1, max_length=128, description="Root bead id.")
    direction: Literal["down", "up", "both"] = "down"
    edge_type: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, max_length=64)
    depth: int = Field(default=1, ge=1, le=20)
    max_rows: int = Field(default=200, ge=1, le=1_000)
    mermaid: bool = False


class MemoryQuery(GatewayModel):
    key: str | None = Field(
        default=None, max_length=256, description="Recall one memory by key."
    )
    query: str | None = Field(
        default=None, max_length=1_000, description="Search memories."
    )


class QueryInput(RequestControls):
    at: str | None = Field(
        default=None,
        max_length=256,
        description="Exact revision or RFC3339 timestamp with timezone; all reads use the resolved revision.",
    )
    projection: Literal["summary", "full"] = "summary"
    aggregate: dict[str, Any] | None = Field(
        default=None,
        description="Count matching records; optional group_by status/type/priority/assignee/owner.",
    )
    projects: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=32,
        description="Project ids; omitted means every configured project (graph and memory need exactly one).",
    )
    view: View = Field(
        default="query",
        description="query needs filters or expression; the other views are owner lists.",
    )
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Filter AST: field=value or field={op,value}; combine with and/or/not.",
    )
    expression: str | None = Field(
        default=None,
        min_length=1,
        max_length=4_000,
        description="Native Beads comparison/AND/OR/NOT expression; parsing and time semantics belong to the owner.",
    )
    native_filters: dict[str, Any] | None = None
    order: Order | None = None
    includes: list[Include] = Field(default_factory=list, max_length=8)
    limit: int = Field(
        default=50,
        ge=1,
        description="Page size within an immutable owner observation. Coverage reports any owner read bound; beads.read exposes native offset paging. Use aggregate for counts.",
    )
    cursor: str | None = Field(default=None, min_length=1, max_length=4_096)
    graph: GraphQuery | None = Field(
        default=None,
        description="Dependency graph walk from one bead instead of a list.",
    )
    memory: MemoryQuery | None = Field(
        default=None, description="Project memories instead of a list."
    )

    @model_validator(mode="after")
    def one_mode(self) -> QueryInput:
        if self.graph is not None and self.memory is not None:
            raise ValueError("give graph or memory, not both")
        if (self.graph or self.memory) and (
            self.projects is None or len(self.projects) != 1
        ):
            raise ValueError("graph and memory need exactly one project")
        return self


class BeadQuery(GatewayModel):
    kind: Literal["bead_query", "bead_graph", "bead_memory"]
    project_refs: list[str]
    items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Normalized beads: ref, id, fields, links, task_revision, etag.",
    )
    page: dict[str, Any] | None = None
    coverage: dict[str, Any] | None = None
    totals: dict[str, Any] | None = None
    source_revisions: dict[str, str] | None = None
    temporal: dict[str, Any] | None = None
    native_parse: dict[str, Any] | None = None
    owner_capabilities: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    graph: dict[str, Any] | None = None
    memory: dict[str, Any] | None = None
    affordances: list[str] = Field(default_factory=list)


def _query(runtime: Runtime, inp: QueryInput) -> BeadQuery:
    projects = inp.projects or sorted(runtime.config.projects)
    for project_id in projects:
        ProjectLocator(project=project_id).resolve(runtime)
    refs = [project_ref(project_id) for project_id in projects]
    affordances = ["beads.get", "beads.update", "projects.context"]
    if inp.graph is not None:
        if inp.at:
            if inp.graph.status or inp.graph.mermaid:
                raise ProtocolError(
                    "unsupported_capability",
                    "historical graph status and Mermaid projections are unavailable",
                )
            result = runtime.beads.campaign_closure(
                projects[0],
                [inp.graph.bead],
                at=inp.at,
                relation=inp.graph.edge_type,
                direction={"down": "prerequisites", "up": "dependents", "both": "both"}[
                    inp.graph.direction
                ],
                max_nodes=inp.graph.max_rows,
                max_depth=inp.graph.depth,
            )
        else:
            result = runtime.beads.graph(
                projects[0], inp.graph.bead, **inp.graph.model_dump(exclude={"bead"})
            )
        return BeadQuery(
            kind="bead_graph",
            project_refs=refs,
            graph=result,
            items=result.get("nodes", []),
            affordances=affordances,
        )
    if inp.memory is not None:
        if inp.at:
            raise ProtocolError(
                "unsupported_capability",
                "owner memories have no historical revision projection",
            )
        result = runtime.beads.memories(projects[0], **inp.memory.model_dump())
        return BeadQuery(
            kind="bead_memory",
            project_refs=refs,
            memory=result,
            affordances=affordances,
        )
    result = runtime.beads.query(
        project_ids=projects,
        view=inp.view,
        filters=inp.filters,
        expression=inp.expression,
        native_filters=inp.native_filters,
        order=inp.order.model_dump() if inp.order else None,
        includes=list(inp.includes),
        limit=inp.limit,
        cursor=inp.cursor,
        at=inp.at,
        projection=inp.projection,
        aggregate=inp.aggregate,
    )
    return BeadQuery(project_refs=refs, affordances=affordances, **result)


# ------------------------------------------------------------------------ get


class GetInput(RequestControls):
    target: BeadLocator
    projection: Literal["summary", "graph", "notes"] = Field(
        default="summary",
        description="summary: the bead with requested includes; graph: also its dependency graph both ways; notes: only notes, description, design and acceptance.",
    )
    includes: list[Include] = Field(default_factory=list, max_length=8)
    as_of: str | None = Field(
        default=None,
        max_length=256,
        description="Exact owner revision or RFC3339 timestamp with timezone, resolved to the latest reachable revision at or before it.",
    )
    graph_depth: int = Field(default=2, ge=1, le=20)


class Bead(GatewayModel):
    ref: str
    project_ref: str
    project_id: str
    bead_id: str
    projection: Literal["summary", "graph", "notes"]
    bead: dict[str, Any] = Field(
        description="Normalized bead: fields, links, includes, task_revision, etag."
    )
    graph: dict[str, Any] | None = None
    affordances: list[str] = Field(default_factory=list)


def _get(runtime: Runtime, inp: GetInput) -> Bead:
    historical_revision = inp.as_of
    if inp.as_of and inp.target.title_contains:
        project_id = inp.target.project or ""
        ProjectLocator(project=project_id).resolve(runtime)
        matches = runtime.beads.query(
            project_ids=[project_id],
            view="all",
            native_filters={"title_contains": inp.target.title_contains},
            at=inp.as_of,
            limit=2,
        )
        if matches["coverage"].get(project_id, {}).get("state") != "complete":
            raise ProtocolError("unavailable", "historical title lookup is incomplete")
        if len(matches["items"]) != 1:
            raise ProtocolError(
                "invalid_request" if matches["items"] else "not_found",
                "historical title must identify exactly one bead",
            )
        selected = matches["items"][0]
        bead_id, ref = selected["id"], selected["ref"]
        historical_revision = selected["task_revision"]
    else:
        project_id, bead_id, ref = inp.target.resolve(runtime)
    bead = runtime.beads.get(
        project_id, bead_id, includes=list(inp.includes), as_of=historical_revision
    )
    graph = None
    if inp.projection == "graph":
        graph = (
            runtime.beads.campaign_closure(
                project_id,
                [bead_id],
                at=bead["task_revision"],
                relation=None,
                direction="both",
                max_depth=inp.graph_depth,
            )
            if inp.as_of
            else runtime.beads.graph(
                project_id, bead_id, direction="both", depth=inp.graph_depth
            )
        )
    elif inp.projection == "notes":
        fields = bead.get("fields", {})
        bead = {
            **{
                key: bead[key]
                for key in ("ref", "id", "project_id", "task_revision", "etag")
                if key in bead
            },
            "fields": {
                key: fields[key]
                for key in (
                    "title",
                    "status",
                    "notes",
                    "description",
                    "design",
                    "acceptance_criteria",
                )
                if key in fields
            },
        }
    return Bead(
        ref=ref,
        project_ref=project_ref(project_id),
        project_id=project_id,
        bead_id=bead_id,
        projection=inp.projection,
        bead=bead,
        graph=graph,
        affordances=["beads.update", "beads.query", "projects.context"],
    )


# --------------------------------------------------------------------- change


class NativeResult(GatewayModel):
    project_ref: str
    owner_operation: str
    owner_result: dict[str, Any]
    affordances: list[str] = Field(default_factory=lambda: ["beads.get", "beads.query"])


class ReadInput(RequestControls, OwnerReadInput):
    project: ProjectLocator


def _read(runtime: Runtime, inp: ReadInput) -> NativeResult:
    project_id = inp.project.resolve(runtime)
    payload = inp.model_dump(
        mode="json",
        exclude_unset=True,
        exclude={*RequestControls.model_fields, "project"},
    )
    return NativeResult(
        project_ref=project_ref(project_id),
        owner_operation="read",
        owner_result=runtime.beads.read(project_id, payload),
    )


_NATIVE_EXAMPLES: dict[str, dict[str, Any]] = {
    "addComment": {
        "path": {"id": "sinnix-abc1"},
        "body": {
            "author": "example-worker",
            "text": "Focused regression checks passed.",
        },
    },
    "addDependencies": {
        "body": {
            "actor": "example-worker",
            "edges": [
                {
                    "issue_id": "sinnix-abc2",
                    "depends_on_id": "sinnix-abc1",
                    "type": "blocks",
                }
            ],
        },
    },
    "applyBatch": {
        "body": {
            "actor": "example-worker",
            "items": [
                {
                    "kind": "create",
                    "create": {
                        "key": "implementation",
                        "title": "Implement bounded result paging",
                    },
                },
                {
                    "kind": "create",
                    "create": {"key": "verification", "title": "Verify result paging"},
                },
                {
                    "kind": "dep_add",
                    "dep_add": {
                        "source": {"key": "verification"},
                        "target": {"key": "implementation"},
                        "type": "blocks",
                    },
                },
            ],
        },
    },
    "batchCloseIssues": {
        "body": {
            "actor": "example-worker",
            "items": [{"id": "sinnix-abc1", "reason": "Acceptance checks passed"}],
        },
    },
    "batchCreateIssues": {
        "body": {
            "actor": "example-worker",
            "items": [
                {"title": "Add a bounded reader"},
                {"title": "Document reader pagination"},
            ],
        },
    },
    "claimIssue": {"path": {"id": "sinnix-abc1"}, "body": {"actor": "example-worker"}},
    "claimNextIssue": {
        "body": {"actor": "example-worker"},
        "query": {"unassigned": True, "sort": "priority"},
    },
    "closeIssue": {
        "path": {"id": "sinnix-abc1"},
        "body": {
            "actor": "example-worker",
            "expected_version": 7,
            "reason": "Acceptance checks passed",
        },
    },
    "compareAndSetMetadata": {
        "path": {"id": "sinnix-abc1"},
        "body": {
            "actor": "example-worker",
            "key": "verification",
            "expected": "pending",
            "value": "passed",
        },
    },
    "countDependencyEdges": {
        "query": {"direction": "out", "issue_id": ["sinnix-abc1"], "type": ["blocks"]}
    },
    "createIssue": {
        "body": {
            "actor": "example-worker",
            "title": "Add bounded result paging",
            "issue_type": "task",
            "priority": 2,
        }
    },
    "forgetMemory": {"path": {"key": "reader-checks"}},
    "getDependencyTree": {
        "query": {"root_id": "sinnix-abc1", "direction": "both", "max_depth": 3}
    },
    "getMemory": {"path": {"key": "reader-checks"}},
    "listBlockingAnnotations": {"query": {"issue_id": ["sinnix-abc1"]}},
    "listDependencies": {"query": {"issue_id": ["sinnix-abc1"], "type": ["blocks"]}},
    "listDependencyCycles": {},
    "listMemories": {"query": {"search": "reader"}},
    "listRelatedIssues": {
        "path": {"id": "sinnix-abc1"},
        "query": {"direction": "out", "type": ["blocks"]},
    },
    "releaseIssue": {
        "path": {"id": "sinnix-abc1"},
        "body": {"actor": "example-worker", "expected_assignee": "example-worker"},
    },
    "rememberMemory": {
        "body": {
            "key": "reader-checks",
            "content": "The reader contract includes bounded pages and continuation tokens.",
        }
    },
    "removeDependency": {
        "body": {
            "actor": "example-worker",
            "issue_id": "sinnix-abc2",
            "depends_on_id": "sinnix-abc1",
        }
    },
    "reopenIssue": {
        "path": {"id": "sinnix-abc1"},
        "body": {
            "actor": "example-worker",
            "expected_version": 8,
            "reason": "A pagination regression remains",
        },
    },
    "updateIssue": {
        "path": {"id": "sinnix-abc1"},
        "body": {
            "actor": "example-worker",
            "expected_version": 7,
            "patch": {
                "append_notes": "Focused regression checks passed.",
                "add_labels": ["verified"],
            },
        },
    },
}


def _native_actions() -> tuple[Action, ...]:
    import json
    from pathlib import Path

    from .. import generated_beads_inputs

    contracts = json.loads(
        (Path(__file__).parents[1] / "generated_beads_contracts.json").read_text()
    )["source"]["operations"]
    actions = []
    for operation, declaration in contracts.items():
        write = declaration["write"]
        controls = MutationControls if write else RequestControls
        native_model = getattr(generated_beads_inputs, declaration["model"])
        Input = create_model(
            declaration["model"] + "Gateway",
            __base__=(controls, native_model),
            project=(ProjectLocator, ...),
        )

        def handler(
            runtime, inp, *, operation=operation, write=write, controls=controls
        ):
            project_id = inp.project.resolve(runtime)
            if write and inp.preconditions:
                raise ProtocolError(
                    "invalid_request", "Use the native request body's preconditions"
                )
            payload = inp.model_dump(
                mode="json",
                by_alias=True,
                exclude_unset=True,
                exclude={*controls.model_fields, "project"},
            )
            result = runtime.beads.native(project_id, operation, payload, write=write)
            return NativeResult(
                project_ref=project_ref(project_id),
                owner_operation=operation,
                owner_result=result,
            )

        actions.append(
            Action(
                name=declaration["action"],
                family=VerbFamily.CHANGE if write else VerbFamily.QUERY,
                owner="beads",
                summary=declaration["summary"],
                Input=Input,
                Output=NativeResult,
                handler=handler,
                principals=OPERATOR_ONLY if write else ALL_PRINCIPALS,
                resource_kinds=_KINDS,
                affordances=("beads.get", "beads.query"),
                examples=(
                    Example(
                        title=declaration["summary"],
                        input={
                            "project": {"project": "sinnix"},
                            **_NATIVE_EXAMPLES[operation],
                            **(
                                {"idempotency_key": f"example-{operation}-1"}
                                if write
                                else {}
                            ),
                        },
                    ),
                ),
                documentation=(
                    "The native Beads operation owns validation and transaction semantics. "
                    "Input fields come from its published OpenAPI contract. "
                    "beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. "
                    "Interrupted effects remain indeterminate and are never automatically retried."
                ),
            )
        )
    return tuple(actions)


class SnapshotPublish(GatewayModel):
    operation: Literal["snapshot.publish"] = "snapshot.publish"


class SyncPush(GatewayModel):
    operation: Literal["sync.push"] = "sync.push"


class SyncPull(GatewayModel):
    operation: Literal["sync.pull"] = "sync.pull"


class BackupCreate(GatewayModel):
    operation: Literal["backup.create"] = "backup.create"


class BackupList(GatewayModel):
    operation: Literal["backup.list"] = "backup.list"


class BackupRestore(GatewayModel):
    operation: Literal["backup.restore"] = "backup.restore"
    backup_id: str = Field(min_length=1, max_length=256)


class OperateInput(MutationControls):
    project: ProjectLocator
    operation: (
        SnapshotPublish
        | SyncPush
        | SyncPull
        | BackupCreate
        | BackupList
        | BackupRestore
    ) = Field(discriminator="operation")


class OperateResult(GatewayModel):
    ref: str
    project_ref: str
    project_id: str
    owner_route: str
    operation: Literal[
        "snapshot.publish",
        "sync.push",
        "sync.pull",
        "backup.create",
        "backup.list",
        "backup.restore",
    ]
    before_revision: str
    after_revision: str
    owner_result: Any = None
    publication: dict[str, Any] | None = None
    atomicity: str
    git_bookkeeping: str
    affordances: list[str] = Field(default_factory=list)


def _operate(runtime: Runtime, inp: OperateInput) -> OperateResult:
    project_id = inp.project.resolve(runtime)
    if inp.preconditions:
        raise ProtocolError(
            "invalid_request", "Beads maintenance takes no preconditions"
        )
    result = runtime.beads.operate(
        project_id,
        inp.operation.operation,
        inp.operation.model_dump(exclude={"operation"}),
    )
    return OperateResult(
        ref=project_ref(project_id),
        project_id=project_id,
        affordances=["beads.query", "projects.get"],
        **result,
    )


_PROJECT = {"project": "sinnix"}


class ClosureInput(RequestControls):
    project: str = Field(min_length=1, max_length=128)
    roots: list[str] = Field(min_length=1, max_length=100)
    relation: str | None = Field(default="blocks", max_length=64)
    direction: Literal["prerequisites", "dependents", "both"] = "prerequisites"
    at: str | None = Field(default=None, max_length=256)
    max_nodes: int = Field(default=500, ge=1, le=1000)
    max_depth: int = Field(default=50, ge=1, le=100)


class ClosureOutput(GatewayModel):
    project_id: str
    roots: list[str]
    owner_product: dict[str, Any]


def _closure(runtime: Runtime, inp: ClosureInput) -> ClosureOutput:
    ProjectLocator(project=inp.project).resolve(runtime)
    return ClosureOutput(
        **runtime.beads.campaign_closure(
            project_id=inp.project,
            roots=inp.roots,
            at=inp.at,
            relation=inp.relation,
            direction=inp.direction,
            max_nodes=inp.max_nodes,
            max_depth=inp.max_depth,
        )
    )


ACTIONS: tuple[Action, ...] = (
    Action(
        name="beads.closure",
        family=VerbFamily.QUERY,
        owner="beads",
        summary="Read native dependency closure, cycles, readiness and incomplete frontier at one revision.",
        Input=ClosureInput,
        Output=ClosureOutput,
        handler=_closure,
        principals=ALL_PRINCIPALS,
        resource_kinds=_KINDS,
        affordances=("beads.get", "beads.query", "campaign.progress"),
        aliases=("dependency closure", "campaign closure"),
        examples=(
            Example(
                title="Blocking closure at a historical time",
                input={
                    "project": "sinnix",
                    "roots": ["sinnix-abc1"],
                    "relation": "blocks",
                    "at": "2026-09-01T12:00:00Z",
                    "max_nodes": 100,
                },
            ),
        ),
    ),
    Action(
        name="beads.query",
        family=VerbFamily.QUERY,
        owner="beads",
        summary="List beads by view, filter AST or native expression; or walk one bead's graph; or read project memories.",
        Input=QueryInput,
        Output=BeadQuery,
        handler=_query,
        principals=ALL_PRINCIPALS,
        resource_kinds=_KINDS,
        affordances=("beads.get", "beads.update", "projects.context"),
        aliases=(
            "tasks",
            "issues",
            "todo",
            "ready work",
            "what is blocked",
            "bd list",
            "bd ready",
            "backlog",
        ),
        documentation="The owner filters, projects and counts before serialization. limit sizes immutable observation pages; cursors never reread live rows. Owner coverage reports any bounded prefix; beads.read exposes native offset paging. at pins historical reads to an exact resolved Dolt revision. aggregate counts or groups without fetching issue bodies.",
        examples=(
            Example(
                title="Ready work in one project",
                input={"projects": ["sinnix"], "view": "ready", "limit": 10},
            ),
            Example(
                title="Open P0-P1 with dependencies",
                input={
                    "projects": ["polylogue"],
                    "filters": {"status": "open", "priority": {"op": "<=", "value": 1}},
                    "includes": ["dependencies"],
                },
            ),
            Example(
                title="Title search",
                input={
                    "projects": ["sinnix"],
                    "view": "open",
                    "native_filters": {"title_contains": "gateway"},
                },
            ),
            Example(
                title="Dependency graph",
                input={
                    "projects": ["sinnix"],
                    "graph": {"bead": "sinnix-abc1", "direction": "both", "depth": 2},
                },
            ),
        ),
    ),
    Action(
        name="beads.get",
        family=VerbFamily.GET,
        owner="beads",
        summary="Read one bead by ref, id or title fragment, with optional comments, history, dependencies or graph.",
        Input=GetInput,
        Output=Bead,
        handler=_get,
        principals=ALL_PRINCIPALS,
        resource_kinds=("bead",),
        affordances=("beads.update", "beads.query"),
        aliases=("show task", "bd show", "issue details", "task notes"),
        examples=(
            Example(
                title="By id",
                input={
                    "target": {"id": "sinnix-abc1"},
                    "includes": ["comments", "dependencies"],
                },
            ),
            Example(
                title="By title",
                input={
                    "target": {
                        "project": "sinnix",
                        "title_contains": "gateway overhaul",
                    },
                    "projection": "notes",
                },
            ),
        ),
    ),
    Action(
        name="beads.operate",
        family=VerbFamily.OPERATE,
        owner="beads",
        summary="Beads maintenance: publish the export snapshot, push or pull sync, create, list or restore backups.",
        Input=OperateInput,
        Output=OperateResult,
        handler=_operate,
        principals=OPERATOR_ONLY,
        resource_kinds=("project", "task_authority"),
        affordances=("beads.query", "projects.get"),
        aliases=("bd sync", "bd export", "backup beads", "restore beads"),
        examples=(
            Example(
                title="Publish snapshot",
                input={
                    "project": _PROJECT,
                    "operation": {"operation": "snapshot.publish"},
                    "idempotency_key": "publish-1",
                },
            ),
            Example(
                title="Restore a backup",
                input={
                    "project": _PROJECT,
                    "operation": {
                        "operation": "backup.restore",
                        "backup_id": "2026-09-01",
                    },
                    "idempotency_key": "restore-1",
                },
            ),
        ),
    ),
    Action(
        name="beads.read",
        family=VerbFamily.QUERY,
        owner="beads",
        summary="Read native Beads queries, counts or dependency closure with owner revisions and paging.",
        Input=ReadInput,
        Output=NativeResult,
        handler=_read,
        principals=ALL_PRINCIPALS,
        resource_kinds=_KINDS,
        affordances=("beads.get", "beads.query"),
        examples=(
            Example(
                title="Page a pinned dependency closure",
                input={
                    "project": {"project": "sinnix"},
                    "at": "HEAD",
                    "roots": ["sinnix-abc1"],
                    "direction": "dependencies",
                    "relations": ["blocks"],
                    "depth": 3,
                    "limit": 50,
                    "offset": 0,
                },
            ),
        ),
    ),
    *_native_actions(),
)
