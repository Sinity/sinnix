"""Configured project actions: project-relative paths in, canonical refs out."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from ..action import (
    ALL_PRINCIPALS,
    OPERATOR_ONLY,
    Action,
    Example,
    MutationControls,
    RequestControls,
)
from ..contracts import VerbFamily
from ..locators import CheckoutLocator, ProjectLocator, ResolvedCheckout, project_ref
from ..projects import ProjectError, ProjectPreconditionError
from ..results import ProtocolError
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime

_NOT_FOUND = ("unknown project", "does not exist", "unknown configured checkout")
_DENIED = ("excluded", "outside", "must be relative", "unavailable to")


def owner(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Call a project owner method, typing its ``ProjectError`` at the boundary."""
    try:
        return fn(*args, **kwargs)
    except ProjectPreconditionError as exc:
        raise ProtocolError("precondition_failed", str(exc)) from exc
    except ProjectError as exc:
        message = str(exc)
        if any(marker in message for marker in _DENIED):
            code = "policy_denied"
        elif any(marker in message for marker in _NOT_FOUND):
            code = "not_found"
        elif "timed out" in message:
            code = "deadline"
        elif "unavailable" in message:
            code = "unavailable"
        else:
            code = "invalid_request"
        raise ProtocolError(code, message) from exc


class Identity(GatewayModel):
    ref: str = Field(description="Canonical checkout ref the call resolved to.")
    project_ref: str
    checkout_ref: str
    project_id: str
    checkout_id: str


def _identity(resolved: ResolvedCheckout) -> dict[str, Any]:
    return {
        "ref": resolved.ref,
        "project_ref": resolved.project_ref,
        "checkout_ref": resolved.checkout_ref,
        "project_id": resolved.project_id,
        "checkout_id": resolved.checkout_id or "default",
    }


# ----------------------------------------------------------------------- list


class ListInput(RequestControls):
    pass


class ProjectRow(GatewayModel):
    ref: str
    project_id: str
    available: bool
    default_ref: str
    observer_read: bool
    writable: bool


class ProjectList(GatewayModel):
    projects: list[ProjectRow]


def _list(runtime: Runtime, inp: ListInput) -> ProjectList:
    rows = owner(runtime.projects.list)["projects"]
    return ProjectList(
        projects=[ProjectRow(ref=project_ref(row["project_id"]), **row) for row in rows]
    )


# ------------------------------------------------------------------------ get


class GetInput(RequestControls):
    target: CheckoutLocator
    projection: Literal["summary", "git", "authority"] = Field(
        default="summary",
        description="summary: branch, change counts and latest commit plus the selected checkout; git: every checkout with head, branch and dirty_sha256; authority: summary, checkouts, code_revision and the Beads task authority.",
    )


class ProjectView(Identity):
    projection: Literal["summary", "git", "authority"]
    project: dict[str, Any] = Field(description="Project summary from git status.")
    checkout: dict[str, Any] | None = Field(
        default=None, description="The selected checkout: head, branch, dirty_sha256."
    )
    checkouts: list[dict[str, Any]] | None = None
    canonical_checkout_ref: str | None = None
    code_revision: str | None = None
    task_authority: dict[str, Any] | None = None
    affordances: list[str] = Field(default_factory=list)


def _get(runtime: Runtime, inp: GetInput) -> ProjectView:
    resolved = inp.target.resolve(runtime)
    identity = _identity(resolved)
    selected = identity["checkout_id"]
    affordances = [
        "projects.tree",
        "projects.read",
        "projects.diff",
        "projects.search",
        "projects.context",
        "beads.query",
    ]
    if inp.projection == "authority":
        authority = owner(runtime.project_authority, resolved.project_id)
        checkouts = authority["checkouts"]
        checkout = next(
            (row for row in checkouts if row["checkout_id"] == selected), None
        )
        if checkout is None:
            raise ProtocolError("not_found", "unknown configured checkout")
        return ProjectView(
            **identity,
            projection=inp.projection,
            project=authority["project"],
            checkout=checkout,
            checkouts=checkouts,
            canonical_checkout_ref=authority["canonical_checkout_ref"],
            code_revision=authority["code_revision"],
            task_authority=authority["task_authority"],
            affordances=affordances,
        )
    summary = owner(runtime.projects.summary, resolved.project_id)
    if inp.projection == "git":
        checkouts = owner(runtime.projects.checkouts, resolved.project_id)["checkouts"]
        checkout = next(
            (row for row in checkouts if row["checkout_id"] == selected), None
        )
        if checkout is None:
            raise ProtocolError("not_found", "unknown configured checkout")
        return ProjectView(
            **identity,
            projection="git",
            project=summary,
            checkout=checkout,
            checkouts=checkouts,
            affordances=affordances,
        )
    checkout = owner(runtime.projects.checkout, resolved.project_id, selected)[
        "checkout"
    ]
    return ProjectView(
        **identity,
        projection="summary",
        project=summary,
        checkout=checkout,
        affordances=affordances,
    )


# ----------------------------------------------------------------------- tree


class TreeInput(RequestControls):
    target: CheckoutLocator
    path: str = Field(
        default=".",
        min_length=1,
        max_length=4_096,
        description="Project-relative directory.",
    )
    max_entries: int = Field(default=500, ge=1, le=2_000)


class TreeEntry(GatewayModel):
    path: str
    kind: Literal["file", "directory"]
    bytes: int | None = None


class Tree(Identity):
    path: str
    entries: list[TreeEntry]
    truncated: bool


def _tree(runtime: Runtime, inp: TreeInput) -> Tree:
    resolved = inp.target.resolve(runtime)
    result = owner(
        runtime.projects.tree,
        resolved.project_id,
        inp.path,
        inp.max_entries,
        resolved.checkout_id,
    )
    return Tree(
        **_identity(resolved),
        path=inp.path,
        entries=result["entries"],
        truncated=result["truncated"],
    )


# ----------------------------------------------------------------------- read


class ReadInput(RequestControls):
    target: CheckoutLocator
    path: str = Field(
        min_length=1, max_length=4_096, description="Project-relative file path."
    )
    start_line: int = Field(default=1, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    max_bytes: int = Field(default=64_000, ge=1, le=262_144)


class ProjectFile(Identity):
    path: str
    start_line: int
    end_line: int | None
    content: str
    bytes: int
    truncated: bool
    affordances: list[str] = Field(default_factory=list)


def _read(runtime: Runtime, inp: ReadInput) -> ProjectFile:
    resolved = inp.target.resolve(runtime)
    result = owner(
        runtime.projects.read,
        resolved.project_id,
        inp.path,
        inp.start_line,
        inp.end_line,
        inp.max_bytes,
        resolved.checkout_id,
    )
    result.pop("project_id")
    return ProjectFile(
        **_identity(resolved),
        **result,
        affordances=["projects.change", "projects.diff"],
    )


# ----------------------------------------------------------------------- diff


class DiffInput(RequestControls):
    target: CheckoutLocator
    git_ref: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}$",
        description="Diff the worktree against this commit-ish; omitted diffs against the index.",
    )


class Diff(Identity):
    git_ref: str | None
    diff: str


def _diff(runtime: Runtime, inp: DiffInput) -> Diff:
    resolved = inp.target.resolve(runtime)
    result = owner(
        runtime.projects.diff, resolved.project_id, inp.git_ref, resolved.checkout_id
    )
    return Diff(**_identity(resolved), git_ref=inp.git_ref, diff=result["diff"])


# --------------------------------------------------------------------- search


class SearchInput(RequestControls):
    target: CheckoutLocator
    query: str = Field(min_length=1, max_length=1_000, description="ripgrep regex.")
    max_matches: int = Field(default=200, ge=1, le=1_000)


class SearchMatch(GatewayModel):
    path: str
    line: int | None
    text: str


class SearchResult(Identity):
    query: str
    matches: list[SearchMatch]
    truncated: bool


def _search(runtime: Runtime, inp: SearchInput) -> SearchResult:
    resolved = inp.target.resolve(runtime)
    result = owner(
        runtime.projects.search,
        resolved.project_id,
        inp.query,
        inp.max_matches,
        resolved.checkout_id,
    )
    matches = [
        {**row, "path": row["path"].removeprefix("./")} for row in result["matches"]
    ]
    return SearchResult(
        **_identity(resolved),
        query=inp.query,
        matches=matches,
        truncated=result["truncated"],
    )


# --------------------------------------------------------------------- change


class WriteOp(GatewayModel):
    operation: Literal["write"] = "write"
    path: str = Field(
        min_length=1, max_length=4_096, description="Project-relative file path."
    )
    content: str = Field(max_length=262_144)


class ApplyPatchOp(GatewayModel):
    operation: Literal["apply_patch"] = "apply_patch"
    patch: str = Field(
        min_length=1, max_length=262_144, description="git-apply compatible patch."
    )


class ChangeInput(MutationControls):
    target: CheckoutLocator
    change: WriteOp | ApplyPatchOp = Field(discriminator="operation")
    expected_head: str | None = Field(default=None, pattern="^[0-9a-f]{40,64}$")
    expected_dirty_sha256: str | None = Field(
        default=None,
        pattern="^[0-9a-f]{64}$",
        description="dirty_sha256 from projects.get; at least one of expected_head or expected_dirty_sha256 is required.",
    )


class ChangeResult(Identity):
    operation: Literal["write", "apply_patch"]
    path: str | None = None
    bytes: int | None = None
    applied: bool
    checkout: dict[str, Any] = Field(
        description="Checkout after the change: new head and dirty_sha256."
    )
    affordances: list[str] = Field(default_factory=list)


def _change(runtime: Runtime, inp: ChangeInput) -> ChangeResult:
    resolved = inp.target.resolve(runtime)
    preconditions = dict(inp.preconditions or {})
    if set(preconditions) - {"head", "dirty_sha256"}:
        raise ProtocolError(
            "invalid_request", "project preconditions are head and dirty_sha256"
        )
    if inp.expected_head is not None:
        preconditions["head"] = inp.expected_head
    if inp.expected_dirty_sha256 is not None:
        preconditions["dirty_sha256"] = inp.expected_dirty_sha256
    if not preconditions:
        raise ProtocolError(
            "precondition_failed",
            "mutation requires expected_head or expected_dirty_sha256",
        )
    checkout_id = resolved.checkout_id or "default"
    checkout = owner(runtime.projects.checkout, resolved.project_id, checkout_id)[
        "checkout"
    ]
    for name, expected in preconditions.items():
        if checkout.get(name) != expected:
            raise ProtocolError(
                "precondition_failed",
                f"project checkout {name} no longer matches",
                details={"expected": expected, "current": checkout.get(name)},
            )
    op = inp.change
    if isinstance(op, WriteOp):
        result = owner(
            runtime.projects.write,
            resolved.project_id,
            op.path,
            op.content,
            checkout_id,
            preconditions,
        )
    else:
        result = owner(
            runtime.projects.apply_patch,
            resolved.project_id,
            op.patch,
            checkout_id,
            preconditions,
        )
    after = owner(runtime.projects.checkout, resolved.project_id, checkout_id)[
        "checkout"
    ]
    return ChangeResult(
        **_identity(resolved),
        operation=op.operation,
        path=result.get("path"),
        bytes=result.get("bytes"),
        applied=True,
        checkout=after,
        affordances=["projects.diff", "projects.read", "projects.get"],
    )


# -------------------------------------------------------------------- context


class ContextInput(RequestControls):
    target: ProjectLocator
    intent: Literal["project.orientation", "project.triage"] = "project.orientation"


class ContextComponent(GatewayModel):
    name: str
    status: str
    data: dict[str, Any] | None = None
    reason: str | None = None
    source_ref: str | None = None
    source_revision: str | None = None
    snapshot_ref: str | None = None
    budget_bytes: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ProjectContext(GatewayModel):
    ref: str
    project_ref: str
    project_id: str
    intent: Literal["project.orientation", "project.triage"]
    context_schema: str = Field(description="Context envelope schema id.")
    target_ref: str
    snapshot_ref: str
    components: list[ContextComponent]
    component_plan: list[dict[str, Any]]
    total_budget_bytes: int
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Compatibility projections of available components.",
    )
    affordances: list[str] = Field(default_factory=list)


_COMPONENT_KEYS = set(ContextComponent.model_fields) - {"extra"}
_CONTEXT_KEYS = {
    "schema",
    "intent",
    "target_ref",
    "snapshot_ref",
    "components",
    "component_plan",
    "total_budget_bytes",
    "ref",
}


def _context(runtime: Runtime, inp: ContextInput) -> ProjectContext:
    project_id = inp.target.resolve(runtime)
    ref = project_ref(project_id)
    context = owner(runtime.compose_context, ref, inp.intent)
    components = [
        ContextComponent(
            **{key: value for key, value in row.items() if key in _COMPONENT_KEYS},
            extra={
                key: value for key, value in row.items() if key not in _COMPONENT_KEYS
            },
        )
        for row in context["components"]
    ]
    return ProjectContext(
        ref=ref,
        project_ref=ref,
        project_id=project_id,
        intent=inp.intent,
        context_schema=context["schema"],
        target_ref=context["target_ref"],
        snapshot_ref=context["snapshot_ref"],
        components=components,
        component_plan=context["component_plan"],
        total_budget_bytes=context["total_budget_bytes"],
        extra={
            key: value for key, value in context.items() if key not in _CONTEXT_KEYS
        },
        affordances=["projects.get", "beads.query", "projects.diff", "projects.tree"],
    )


_KINDS = ("project", "checkout")
_EXAMPLE = {"target": {"project": "sinnix"}}

ACTIONS: tuple[Action, ...] = (
    Action(
        name="projects.list",
        family=VerbFamily.QUERY,
        owner="projects",
        summary="List the projects this principal may read, with canonical refs.",
        Input=ListInput,
        Output=ProjectList,
        handler=_list,
        principals=ALL_PRINCIPALS,
        resource_kinds=("project",),
        affordances=("projects.get", "projects.context", "beads.query"),
        aliases=("repos", "repositories", "workspaces", "which projects"),
        examples=(Example(title="List projects", input={}),),
    ),
    Action(
        name="projects.get",
        family=VerbFamily.GET,
        owner="projects",
        summary="Describe one project or checkout: git status, checkouts, task authority.",
        Input=GetInput,
        Output=ProjectView,
        handler=_get,
        principals=ALL_PRINCIPALS,
        resource_kinds=_KINDS,
        affordances=(
            "projects.tree",
            "projects.diff",
            "projects.change",
            "projects.context",
        ),
        aliases=("git status", "branch", "worktrees", "checkouts", "head", "dirty"),
        documentation="The checkout row carries head and dirty_sha256, the preconditions projects.change requires.",
        examples=(
            Example(title="Summary by project id", input=_EXAMPLE),
            Example(
                title="All worktrees",
                input={
                    "target": {"ref": "sinnix://projects/sinnix"},
                    "projection": "git",
                },
            ),
            Example(
                title="Checkout containing a path",
                input={"target": {"path": "/realm/project/sinnix/flake.nix"}},
            ),
        ),
    ),
    Action(
        name="projects.tree",
        family=VerbFamily.QUERY,
        owner="projects",
        summary="List files under a project-relative directory without following symlinks.",
        Input=TreeInput,
        Output=Tree,
        handler=_tree,
        principals=ALL_PRINCIPALS,
        resource_kinds=_KINDS,
        affordances=("projects.read", "projects.search"),
        aliases=("ls", "file list", "directory", "layout"),
        examples=(
            Example(
                title="Top-level modules",
                input={**_EXAMPLE, "path": "modules", "max_entries": 100},
            ),
        ),
    ),
    Action(
        name="projects.read",
        family=VerbFamily.QUERY,
        owner="projects",
        summary="Read a bounded line range of one project file.",
        Input=ReadInput,
        Output=ProjectFile,
        handler=_read,
        principals=ALL_PRINCIPALS,
        resource_kinds=_KINDS,
        affordances=("projects.change", "projects.search", "projects.diff"),
        aliases=("cat", "open", "view file", "source"),
        examples=(
            Example(
                title="Read CLAUDE.md",
                input={**_EXAMPLE, "path": "CLAUDE.md", "end_line": 80},
            ),
        ),
    ),
    Action(
        name="projects.diff",
        family=VerbFamily.QUERY,
        owner="projects",
        summary="Show uncommitted changes in a checkout, optionally against a git ref.",
        Input=DiffInput,
        Output=Diff,
        handler=_diff,
        principals=ALL_PRINCIPALS,
        resource_kinds=_KINDS,
        affordances=("projects.read", "projects.get"),
        aliases=("git diff", "changes", "what changed", "working tree"),
        examples=(
            Example(
                title="Working tree vs HEAD", input={**_EXAMPLE, "git_ref": "HEAD"}
            ),
        ),
    ),
    Action(
        name="projects.search",
        family=VerbFamily.QUERY,
        owner="projects",
        summary="Search project file contents with ripgrep.",
        Input=SearchInput,
        Output=SearchResult,
        handler=_search,
        principals=ALL_PRINCIPALS,
        resource_kinds=_KINDS,
        affordances=("projects.read", "projects.tree"),
        aliases=("grep", "rg", "find in files", "where is"),
        examples=(
            Example(
                title="Find a symbol",
                input={**_EXAMPLE, "query": "mkServiceModule", "max_matches": 20},
            ),
        ),
    ),
    Action(
        name="projects.change",
        family=VerbFamily.CHANGE,
        owner="projects",
        summary="Write one project file or apply a patch, guarded by the checkout's head or dirty_sha256.",
        Input=ChangeInput,
        Output=ChangeResult,
        handler=_change,
        principals=OPERATOR_ONLY,
        resource_kinds=_KINDS,
        affordances=("projects.diff", "projects.read", "projects.get"),
        aliases=("write file", "edit", "apply patch", "save"),
        supports_precondition=True,
        documentation="Paths stay project-relative and policy-excluded paths (.git, secrets, local-only agent state) are refused. Take expected_dirty_sha256 or expected_head from projects.get.",
        examples=(
            Example(
                title="Write a file",
                input={
                    "target": {"ref": "sinnix://projects/sinnix/checkouts/default"},
                    "change": {
                        "operation": "write",
                        "path": "docs/notes.md",
                        "content": "hello\n",
                    },
                    "expected_head": "a" * 40,
                    "idempotency_key": "write-notes-1",
                },
            ),
            Example(
                title="Apply a patch",
                input={
                    **_EXAMPLE,
                    "change": {
                        "operation": "apply_patch",
                        "patch": "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n",
                    },
                    "expected_dirty_sha256": "0" * 64,
                    "idempotency_key": "patch-readme-1",
                },
            ),
        ),
    ),
    Action(
        name="projects.context",
        family=VerbFamily.CONTEXT,
        owner="projects",
        summary="Compose orientation or triage context for one project: git state, ready or open beads, task authority.",
        Input=ContextInput,
        Output=ProjectContext,
        handler=_context,
        principals=ALL_PRINCIPALS,
        resource_kinds=("project",),
        affordances=("projects.get", "beads.query", "projects.diff", "projects.tree"),
        aliases=("orient", "overview", "where are we", "triage", "what is ready"),
        documentation="Components are budgeted independently; an unavailable component names its reason and source ref so the caller can follow the direct route.",
        examples=(
            Example(title="Orientation", input=_EXAMPLE),
            Example(title="Triage", input={**_EXAMPLE, "intent": "project.triage"}),
        ),
    ),
)
