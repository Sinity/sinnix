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
from ..beads import (
    _LIST_BOOLEAN_FLAGS,
    _LIST_FLAGS,
    _LIST_REPEAT_FLAGS,
    _READY_BOOLEAN_FLAGS,
)
from ..contracts import VerbFamily
from ..locators import BeadLocator, ProjectLocator, bead_ref, project_ref
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

# The owner's native list flags, exposed one field each so the schema is honest.
NativeFilters = create_model(
    "NativeFilters",
    __base__=GatewayModel,
    __doc__="Owner-native list filters; ready and stale_claims views accept a subset.",
    **dict.fromkeys(_LIST_FLAGS, (str | None, None)),
    **{
        key: (list[str] | None, Field(default=None, min_length=1, max_length=32))
        for key in _LIST_REPEAT_FLAGS
    },
    **dict.fromkeys(
        {**_LIST_BOOLEAN_FLAGS, **_READY_BOOLEAN_FLAGS}, (Literal[True] | None, None)
    ),
    mol=(str | None, None),
    stale_days=(int | None, Field(default=None, ge=1)),
)


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
        description="Beads-compatible comparison/AND/OR/NOT expression compiled to read-only owner SQL. Supports RFC3339/date and h/d/w relative dates; natural-language dates are unavailable.",
    )
    native_filters: NativeFilters | None = None  # type: ignore[valid-type]
    order: Order | None = None
    includes: list[Include] = Field(default_factory=list, max_length=8)
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Page size within an immutable snapshot; matching rows are projected at the owner, with a 10,000-row snapshot bound.",
    )
    cursor: str | None = Field(default=None, min_length=1, max_length=256)
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
    affordances = ["beads.get", "beads.change", "projects.context"]
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
        native_filters=(
            inp.native_filters.model_dump(exclude_none=True)
            if inp.native_filters
            else None
        ),
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
        affordances=["beads.change", "beads.query", "projects.context"],
    )


# --------------------------------------------------------------------- change


class Notes(GatewayModel):
    text: str = Field(max_length=32_000)
    mode: Literal["append", "replace"] = "append"


class CreateOp(GatewayModel):
    operation: Literal["create"] = "create"
    project: ProjectLocator
    title: str = Field(min_length=1, max_length=512)
    description: str | None = Field(default=None, max_length=32_000)
    design: str | None = Field(default=None, max_length=32_000)
    acceptance: str | None = Field(default=None, max_length=32_000)
    type: str | None = Field(default=None, max_length=64)
    priority: str | None = Field(
        default=None, max_length=8, description="0-4 or P0-P4."
    )
    assignee: str | None = Field(default=None, max_length=256)
    parent: str | None = Field(default=None, max_length=128)
    due: str | None = Field(default=None, max_length=64)
    defer: str | None = Field(default=None, max_length=64)
    external_ref: str | None = Field(default=None, max_length=1_000)
    spec_id: str | None = Field(default=None, max_length=256)
    status: str | None = Field(default=None, max_length=64)
    labels: list[str] | None = Field(default=None, max_length=32)
    dependencies: list[str] | None = Field(default=None, max_length=32)
    notes: Notes | None = None


class GraphCreateOp(GatewayModel):
    operation: Literal["graph.create"] = "graph.create"
    project: ProjectLocator
    graph: dict[str, Any] = Field(
        min_length=1, description="Native bd create --graph plan."
    )


class LabelPatch(GatewayModel):
    add: list[str] | None = None
    remove: list[str] | None = None
    replace: list[str] | None = None


class MetadataPatch(GatewayModel):
    set: dict[str, Any] | None = None
    unset: list[str] | None = None


class Patch(GatewayModel):
    set: dict[str, Any] | None = Field(
        default=None,
        description="Scalar fields: title, description, design, acceptance, status, priority, assignee, due, defer, estimate, external_ref, spec_id, parent.",
    )
    labels: LabelPatch | None = None
    metadata: MetadataPatch | None = None
    notes: Notes | None = None
    unset: list[Literal["due", "defer", "parent"]] | None = None


class UpdateOp(GatewayModel):
    operation: Literal["update"] = "update"
    target: BeadLocator
    patch: Patch


class ClaimOp(GatewayModel):
    operation: Literal["claim"] = "claim"
    target: BeadLocator


class UnclaimOp(GatewayModel):
    operation: Literal["unclaim"] = "unclaim"
    target: BeadLocator
    reason: str | None = Field(default=None, max_length=32_000)


class CloseOp(GatewayModel):
    operation: Literal["close"] = "close"
    target: BeadLocator
    reason: str | None = Field(default=None, max_length=32_000)
    force: Literal[True] | None = Field(
        default=None, description="Close despite open blockers."
    )


class ReopenOp(GatewayModel):
    operation: Literal["reopen"] = "reopen"
    target: BeadLocator
    reason: str | None = Field(default=None, max_length=32_000)


class CommentOp(GatewayModel):
    operation: Literal["comment"] = "comment"
    target: BeadLocator
    text: str = Field(min_length=1, max_length=32_000)


class DependencyAddOp(GatewayModel):
    operation: Literal["dependency.add"] = "dependency.add"
    target: BeadLocator
    depends_on: str = _BEAD_ID
    type: str = Field(default="blocks", max_length=64)


class DependencyRemoveOp(GatewayModel):
    operation: Literal["dependency.remove"] = "dependency.remove"
    target: BeadLocator
    depends_on: str = _BEAD_ID


class RelateOp(GatewayModel):
    operation: Literal["relate"] = "relate"
    target: BeadLocator
    other_id: str = _BEAD_ID


class UnrelateOp(GatewayModel):
    operation: Literal["unrelate"] = "unrelate"
    target: BeadLocator
    other_id: str = _BEAD_ID


class ReparentOp(GatewayModel):
    operation: Literal["reparent"] = "reparent"
    target: BeadLocator
    parent_id: str = Field(
        default="", max_length=128, description="Empty detaches from the parent."
    )


class MemoryRememberOp(GatewayModel):
    operation: Literal["memory.remember"] = "memory.remember"
    target: BeadLocator = Field(description="Bead the memory is attested against.")
    key: str = Field(min_length=1, max_length=256)
    text: str = Field(min_length=1, max_length=32_000)


class MemoryForgetOp(GatewayModel):
    operation: Literal["memory.forget"] = "memory.forget"
    target: BeadLocator
    key: str = Field(min_length=1, max_length=256)


BeadOp = (
    CreateOp
    | GraphCreateOp
    | UpdateOp
    | ClaimOp
    | UnclaimOp
    | CloseOp
    | ReopenOp
    | CommentOp
    | DependencyAddOp
    | DependencyRemoveOp
    | RelateOp
    | UnrelateOp
    | ReparentOp
    | MemoryRememberOp
    | MemoryForgetOp
)
Operation = Literal[
    "create",
    "graph.create",
    "update",
    "claim",
    "unclaim",
    "close",
    "reopen",
    "comment",
    "dependency.add",
    "dependency.remove",
    "relate",
    "unrelate",
    "reparent",
    "memory.remember",
    "memory.forget",
]


class Preconditions(GatewayModel):
    expected_task_revision: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    expected_etag: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    expected_status: str | None = Field(default=None, max_length=64)
    expected_assignee: str | None = Field(default=None, max_length=256)


_PRECONDITION_KEYS = set(Preconditions.model_fields)


def _preconditions(
    typed: Preconditions | None, raw: dict[str, Any] | None
) -> dict[str, Any] | None:
    merged = dict(raw or {})
    if set(merged) - _PRECONDITION_KEYS:
        raise ProtocolError(
            "invalid_request",
            "Beads preconditions are not recognized",
            details={"allowed": sorted(_PRECONDITION_KEYS)},
        )
    if typed is not None:
        merged.update(typed.model_dump(exclude_unset=True))
    return merged or None


def _compile(runtime: Runtime, op: BeadOp) -> tuple[str, str | None, dict[str, Any]]:
    """Return ``(project_id, target_bead_id, owner parameters)`` for one operation."""
    parameters = op.model_dump(
        exclude={"operation", "project", "target"}, exclude_none=True
    )
    if isinstance(op, (CreateOp, GraphCreateOp)):
        return op.project.resolve(runtime), None, parameters
    project_id, bead_id, _ref = op.target.resolve(runtime)
    if isinstance(op, UpdateOp):
        parameters["patch"] = op.patch.model_dump(exclude_none=True)
    return project_id, bead_id, {"id": bead_id, **parameters}


class ChangeInput(MutationControls):
    change: BeadOp = Field(discriminator="operation")
    mode: Literal["apply", "preview"] = Field(
        default="apply",
        description="preview compiles and dry-runs without writing and returns a preview_digest.",
    )
    preview_digest: str | None = Field(
        default=None,
        pattern="^[0-9a-f]{64}$",
        description="From a preview; apply is refused if the source moved since.",
    )
    expected: Preconditions | None = Field(
        default=None, description="Typed preconditions; merged with preconditions."
    )


class ChangeResult(GatewayModel):
    ref: str = Field(
        description="The bead acted on, or the project for create, graph and memory operations."
    )
    project_ref: str
    project_id: str
    bead_id: str | None = None
    created_id: str | None = None
    target_ref: str | None = None
    operation: Operation
    mode: Literal["apply", "preview"]
    preview_digest: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    before_revision: str
    after_revision: str | None = None
    owner_result: Any = None
    owner_history_ref: str | None = None
    owner_history: Any = None
    mutation_state: Literal["applied", "indeterminate"] | None = None
    post_write: dict[str, Any] | None = None
    uncertainty: dict[str, str] | None = None
    native_validation: str
    atomicity: str
    command: list[str]
    preconditions: dict[str, Any]
    precondition_semantics: dict[str, Any]
    owner_route: str
    owner_version: Any = None
    affordances: list[str] = Field(default_factory=list)


def _change(runtime: Runtime, inp: ChangeInput) -> ChangeResult:
    project_id, bead_id, parameters = _compile(runtime, inp.change)
    result = runtime.beads.change(
        project_id,
        inp.change.operation,
        parameters,
        mode=inp.mode,
        preconditions=_preconditions(inp.expected, inp.preconditions),
        preview_digest=inp.preview_digest,
    )
    after = result.get("after")
    created = after.get("id") if isinstance(after, dict) and bead_id is None else None
    bead = bead_id or created or result.get("created_id")
    return ChangeResult(
        ref=bead_ref(project_id, bead) if bead else project_ref(project_id),
        project_id=project_id,
        bead_id=bead,
        operation=inp.change.operation,
        affordances=["beads.get", "beads.query", "beads.change"],
        **result,
    )


# ------------------------------------------------------------------ changeset


class ChangesetStep(GatewayModel):
    operation: Operation
    bead: str | None = Field(
        default=None,
        max_length=128,
        description="Target bead id, or a $symbol bound by an earlier step; omit for create, graph and memory operations.",
    )
    project: str | None = Field(
        default=None,
        max_length=128,
        description="Project id; defaults to the changeset project.",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Operation fields as for beads.change (title, text, patch, ...); values may reference $symbols.",
    )
    preconditions: Preconditions | None = None
    bind: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$",
        description="Name the created bead for later steps as $name.",
    )


class ChangesetInput(MutationControls):
    project: ProjectLocator
    mode: Literal["preview", "apply"] = "preview"
    steps: list[ChangesetStep] = Field(min_length=1, max_length=128)
    on_error: Literal["stop", "continue"] = "stop"
    preview_digest: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")


class ChangesetResult(GatewayModel):
    ref: str
    project_ref: str
    project_id: str
    mode: Literal["preview", "apply"]
    owner_route: str
    source_revisions: dict[str, str]
    preview_digest: str
    on_error: str
    atomicity: str
    partitions: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    compensation: dict[str, Any]
    outcomes: list[dict[str, Any]] | None = None
    after_source_revisions: dict[str, str] | None = None
    after_source_revision_errors: dict[str, dict[str, str]] | None = None
    partial_completion: bool | None = None
    affordances: list[str] = Field(default_factory=list)


def _changeset(runtime: Runtime, inp: ChangesetInput) -> ChangesetResult:
    anchor = inp.project.resolve(runtime)
    if inp.preconditions is not None:
        raise ProtocolError(
            "invalid_request", "changeset preconditions belong to individual steps"
        )
    actions = []
    for step in inp.steps:
        project_id = step.project or anchor
        ProjectLocator(project=project_id).resolve(runtime)
        if step.bead is not None and not step.bead.startswith("$"):
            ref = bead_ref(project_id, step.bead)
        else:
            ref = project_ref(project_id)
        parameters = dict(step.parameters)
        if step.bead is not None and step.bead.startswith("$"):
            parameters["id"] = step.bead
        row: dict[str, Any] = {
            "ref": ref,
            "operation": step.operation,
            "parameters": parameters,
        }
        if step.preconditions is not None:
            row["preconditions"] = step.preconditions.model_dump(exclude_unset=True)
        if step.bind is not None:
            row["bind"] = step.bind
        actions.append(row)
    result = runtime.beads.changeset(
        actions, mode=inp.mode, on_error=inp.on_error, preview_digest=inp.preview_digest
    )
    return ChangesetResult(
        ref=project_ref(anchor),
        project_ref=project_ref(anchor),
        project_id=anchor,
        affordances=["beads.query", "beads.get", "beads.changeset"],
        **result,
    )


# -------------------------------------------------------------------- operate


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
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    provenance_edges: list[dict[str, Any]]
    provenance_coverage: dict[str, Any]
    cycles: list[list[str]]
    graph_leaves: list[str]
    declared_gates: list[str]
    declared_decisions: list[str]
    unknown_roles: list[str]
    readiness: dict[str, Any]
    frontier: list[dict[str, Any]]
    coverage: dict[str, Any]
    counts: dict[str, Any]
    complete: bool
    temporal: dict[str, Any]
    task_revision: str


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
        summary="Read a bounded dependency closure, cycles, declared gates and decisions, readiness and incomplete frontier at one revision.",
        Input=ClosureInput,
        Output=ClosureOutput,
        handler=_closure,
        principals=ALL_PRINCIPALS,
        resource_kinds=_KINDS,
        affordances=("beads.get", "beads.query"),
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
        affordances=("beads.get", "beads.change", "projects.context"),
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
        documentation="The owner filters, projects and counts before serialization. limit sizes pages of one immutable snapshot (10,000 matching rows per project maximum); cursors never reread live rows. at pins historical reads to an exact resolved Dolt revision. aggregate counts or groups without fetching issue bodies.",
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
        affordances=("beads.change", "beads.query"),
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
        name="beads.change",
        family=VerbFamily.CHANGE,
        owner="beads",
        summary="One typed Beads mutation: create, update, claim, close, reopen, comment, dependencies, relations, reparent, memory.",
        Input=ChangeInput,
        Output=ChangeResult,
        handler=_change,
        principals=OPERATOR_ONLY,
        resource_kinds=_KINDS,
        affordances=("beads.get", "beads.query", "beads.changeset"),
        aliases=(
            "create task",
            "close task",
            "claim",
            "comment",
            "add note",
            "bd update",
            "bd close",
            "block on",
        ),
        supports_precondition=True,
        documentation="expected.expected_task_revision/expected_etag come from beads.get. Use mode=preview to see the compiled command and a preview_digest before applying.",
        examples=(
            Example(
                title="Create",
                input={
                    "change": {
                        "operation": "create",
                        "project": _PROJECT,
                        "title": "Port beads actions",
                        "type": "task",
                        "priority": "2",
                    },
                    "idempotency_key": "create-1",
                },
            ),
            Example(
                title="Comment",
                input={
                    "change": {
                        "operation": "comment",
                        "target": {"id": "sinnix-abc1"},
                        "text": "landed in gateway-overhaul",
                    },
                    "idempotency_key": "comment-1",
                },
            ),
            Example(
                title="Close with reason",
                input={
                    "change": {
                        "operation": "close",
                        "target": {"id": "sinnix-abc1"},
                        "reason": "shipped",
                    },
                    "expected": {"expected_status": "in_progress"},
                    "idempotency_key": "close-1",
                },
            ),
        ),
    ),
    Action(
        name="beads.changeset",
        family=VerbFamily.CHANGE,
        owner="beads",
        summary="Preview or apply an ordered list of Beads operations, binding created ids for later steps.",
        Input=ChangesetInput,
        Output=ChangesetResult,
        handler=_changeset,
        principals=OPERATOR_ONLY,
        resource_kinds=_KINDS,
        affordances=("beads.query", "beads.get", "beads.change"),
        aliases=("batch", "bulk create", "epic with children", "several tasks"),
        documentation="No global rollback: each applied step reports its outcome and a compensation hint. Preview first, then apply with the returned preview_digest.",
        examples=(
            Example(
                title="Epic with one child",
                input={
                    "project": _PROJECT,
                    "steps": [
                        {
                            "operation": "create",
                            "parameters": {"title": "Epic", "type": "epic"},
                            "bind": "epic",
                        },
                        {
                            "operation": "create",
                            "parameters": {"title": "Child", "parent": "$epic"},
                        },
                    ],
                    "idempotency_key": "changeset-1",
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
)
