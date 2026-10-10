"""Configured project actions: project-relative paths in, canonical refs out."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import anyio
from pydantic import Field

from ..action import (
    ALL_PRINCIPALS,
    OPERATOR_ONLY,
    Action,
    ActionResult,
    Example,
    MutationControls,
    RequestControls,
)
from ..content import Artifact, attach
from ..contracts import VerbFamily
from ..locators import CheckoutLocator, ProjectLocator, ResolvedCheckout, project_ref
from ..projects import ProjectError, ProjectPreconditionError
from ..results import ProtocolError, ResultError
from ..schemas import GatewayModel
from .contexts import ComposedContext

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
    repository_path: str
    repository_kind: Literal["bare", "worktree"] | None
    default_checkout_id: str | None
    default_checkout_path: str | None
    checkout_discovery_error: str | None
    checkouts: list[dict[str, Any]]
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
        description="summary: branch, change counts and latest commit for the selected checkout; git: repository-store identity plus live checkouts with head, branch and dirty_sha256; authority: summary, checkouts, code_revision and Beads task authority.",
    )


class ProjectView(Identity):
    projection: Literal["summary", "git", "authority"]
    project: dict[str, Any] = Field(description="Project summary from git status.")
    repository: dict[str, Any] | None = Field(
        default=None,
        description="Repository-store identity and configured default ref, separate from checkout status.",
    )
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
    summary = owner(runtime.projects.summary, resolved.project_id, resolved.checkout_id)
    if inp.projection == "git":
        catalog = owner(runtime.projects.checkouts, resolved.project_id)
        checkouts = catalog["checkouts"]
        checkout = next(
            (row for row in checkouts if row["checkout_id"] == selected), None
        )
        if checkout is None:
            raise ProtocolError("not_found", "unknown configured checkout")
        return ProjectView(
            **identity,
            projection="git",
            project=summary,
            repository=catalog["repository"],
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
    max_entries: int = Field(default=500, ge=1)
    start_after: str | None = Field(default=None, max_length=4_096)


class TreeEntry(GatewayModel):
    path: str
    kind: Literal["file", "directory"]
    bytes: int | None = None


class Tree(Identity):
    path: str
    entries: list[TreeEntry]
    truncated: bool
    next_start_after: str | None = None


def _tree(runtime: Runtime, inp: TreeInput) -> Tree:
    resolved = inp.target.resolve(runtime)
    result = owner(
        runtime.projects.tree,
        resolved.project_id,
        inp.path,
        inp.max_entries,
        resolved.checkout_id,
        inp.start_after,
    )
    return Tree(
        **_identity(resolved),
        path=inp.path,
        entries=result["entries"],
        truncated=result["truncated"],
        next_start_after=result["next_start_after"],
    )


# ----------------------------------------------------------------------- read


class ReadInput(RequestControls):
    target: CheckoutLocator
    path: str = Field(
        min_length=1, max_length=4_096, description="Project-relative file path."
    )
    start_line: int = Field(default=1, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    max_bytes: int = Field(default=64_000, ge=1)


class ProjectFile(Identity):
    path: str
    start_line: int
    end_line: int | None
    content: str
    bytes: int
    truncated: bool
    content_sha256: str
    checkout_revision: str
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


class ReadRequest(GatewayModel):
    path: str = Field(min_length=1, max_length=4_096)
    start_line: int = Field(default=1, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    max_bytes: int = Field(default=64_000, ge=1)


class ReadManyInput(RequestControls):
    target: CheckoutLocator
    files: list[ReadRequest] = Field(min_length=1, max_length=32)


class ReadMany(Identity):
    files: list[ProjectFile]
    checkout_revision: str | None = None


def _read_many(runtime: Runtime, inp: ReadManyInput) -> ReadMany:
    resolved = inp.target.resolve(runtime)
    result = owner(
        runtime.projects.read_many,
        resolved.project_id,
        [request.model_dump() for request in inp.files],
        resolved.checkout_id,
    )
    rows = [
        ProjectFile(
            **_identity(resolved),
            **file,
            affordances=["projects.change", "projects.diff"],
        )
        for file in result["files"]
    ]
    return ReadMany(
        **_identity(resolved),
        files=rows,
        checkout_revision=result["checkout_revision"],
    )


class ExportInput(RequestControls):
    target: CheckoutLocator
    max_files: int | None = Field(default=None, ge=1)
    max_bytes: int | None = Field(default=None, ge=1)
    start_after: str | None = None
    expected_revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ProjectExport(Identity):
    checkout_revision: str
    manifest: dict[str, Any]
    artifact: Artifact


def _export(runtime: Runtime, inp: ExportInput) -> ActionResult:
    resolved = inp.target.resolve(runtime)
    result = owner(
        runtime.projects.export,
        resolved.project_id,
        resolved.checkout_id,
        inp.max_files,
        inp.max_bytes,
        inp.start_after,
        inp.expected_revision,
    )
    archive = result["archive"]
    receipt = runtime.artifacts.attest_capture(
        result["directory"],
        source=f"projects.export:{resolved.ref}",
        target=_identity(resolved),
        files=[archive],
    )
    artifact_id = runtime.artifacts.register(
        archive, kind="project-export", owner_id=resolved.ref
    )
    artifact, blocks = attach(
        runtime.artifacts.registered_content(artifact_id),
        ref=f"sinnix://artifacts/{artifact_id}",
        media_type="application/zip",
    )
    output = ProjectExport(
        **_identity(resolved),
        checkout_revision=result["manifest"]["checkout_revision"],
        manifest={
            **{
                key: value
                for key, value in result["manifest"].items()
                if key != "files"
            },
            "receipt_id": receipt["capture_id"],
        },
        artifact=artifact,
    )
    return ActionResult(output, blocks=blocks)


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
    truncated: bool


def _diff(runtime: Runtime, inp: DiffInput) -> Diff:
    resolved = inp.target.resolve(runtime)
    result = owner(
        runtime.projects.diff, resolved.project_id, inp.git_ref, resolved.checkout_id
    )
    return Diff(
        **_identity(resolved),
        git_ref=inp.git_ref,
        diff=result["diff"],
        truncated=result["truncated"],
    )


# --------------------------------------------------------------------- search


class SearchInput(RequestControls):
    target: CheckoutLocator
    query: str = Field(min_length=1, max_length=1_000, description="ripgrep regex.")
    max_matches: int = Field(default=200, ge=1)
    page_size: int = Field(default=200, ge=1)
    cursor: str | None = Field(default=None, min_length=1, max_length=4096)


class SearchMatch(GatewayModel):
    path: str
    line: int | None
    text: str


class SearchResult(Identity):
    checkout_revision: str
    query: str
    matches: list[SearchMatch]
    truncated: bool
    row_count: int
    offset: int
    next_cursor: str | None
    snapshot_ref: str
    expires_at: float


def _search(runtime: Runtime, inp: SearchInput) -> SearchResult:
    resolved = inp.target.resolve(runtime)
    try:
        page = owner(
            runtime.projects.search_page,
            resolved.project_id,
            inp.query,
            inp.max_matches,
            resolved.checkout_id,
            page_size=inp.page_size,
            cursor=inp.cursor,
        )
    except ResultError as exc:
        raise ProtocolError(exc.failure_class, str(exc)) from exc
    return SearchResult(
        **_identity(resolved),
        query=inp.query,
        checkout_revision=page["metadata"]["checkout_revision"],
        matches=page["rows"],
        truncated=page["metadata"]["truncated"],
        row_count=page["row_count"],
        offset=page["offset"],
        next_cursor=page["next_cursor"],
        snapshot_ref=page["snapshot_ref"],
        expires_at=page["expires_at"],
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
    expected_file_path: str | None = Field(
        default=None,
        max_length=4_096,
        description="Project-relative file guarded by expected_file_sha256.",
    )
    expected_file_sha256: str | None = Field(
        default=None,
        pattern="^[0-9a-f]{64}$",
        description="SHA-256 returned by projects.read for the file being written.",
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
    if set(preconditions) - {"head", "dirty_sha256", "file_path", "file_sha256"}:
        raise ProtocolError(
            "invalid_request",
            "project preconditions are head, dirty_sha256, or file_sha256/file_path",
        )
    if inp.expected_head is not None:
        preconditions["head"] = inp.expected_head
    if inp.expected_dirty_sha256 is not None:
        preconditions["dirty_sha256"] = inp.expected_dirty_sha256
    if inp.expected_file_path is not None:
        preconditions["file_path"] = inp.expected_file_path
    if inp.expected_file_sha256 is not None:
        preconditions["file_sha256"] = inp.expected_file_sha256
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
        if name in {"file_path", "file_sha256"}:
            continue
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


class ProjectContext(ComposedContext):
    project_ref: str
    project_id: str
    intent: Literal["project.orientation", "project.triage"]


async def _context(runtime: Runtime, inp: ContextInput) -> ProjectContext:
    from ..contexts import canonical_bytes
    from .contexts import ComposeInput, _compose, _within_budget

    project_id = await anyio.to_thread.run_sync(inp.target.resolve, runtime)
    ref = project_ref(project_id)
    context = await _compose(
        runtime,
        ComposeInput(
            intent=inp.intent,
            project={"project": project_id},
            deadline_at=inp.deadline_at,
        ),
    )
    fields = context.model_dump()
    fields["affordances"] = ["projects.get", "beads.query", "projects.diff", "projects.tree"]
    project_fields = {"project_ref": ref, "project_id": project_id}
    # Inserting these keys replaces no composer fields. Account for their
    # encoded bytes and the joining comma before selecting the inline view.
    reserve = len(canonical_bytes(project_fields)) - 1
    bounded = _within_budget(fields, reserve_bytes=reserve)
    return ProjectContext(**bounded, **project_fields)



_KINDS = ("project", "checkout")
_EXAMPLE = {"target": {"project": "sinnix"}}

ACTIONS: tuple[Action, ...] = (
    Action(
        name="projects.list",
        family=VerbFamily.QUERY,
        owner="projects",
        summary="List configured repository stores, their explicit default ref, and live checkout ids.",
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
        summary="Describe a selected checkout and its repository store; bare stores require an explicit default checkout or checkout id for code reads.",
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
                input={"target": {"path": "/realm/project/sinnix/repo/flake.nix"}},
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
        documentation="Lists project files without following symlinks. When truncated, pass next_start_after as start_after to list the next page of the same directory.",
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
        name="projects.read_many",
        family=VerbFamily.QUERY,
        owner="projects",
        summary="Read several bounded project files from one checkout observation.",
        Input=ReadManyInput,
        Output=ReadMany,
        handler=_read_many,
        principals=ALL_PRINCIPALS,
        resource_kinds=_KINDS,
        affordances=("projects.read", "projects.change", "projects.diff"),
        aliases=("bulk read", "read files", "batch files"),
        examples=(
            Example(
                title="Read two files",
                input={
                    **_EXAMPLE,
                    "files": [
                        {"path": "README.md", "end_line": 40},
                        {"path": "flake.nix", "end_line": 80},
                    ],
                },
            ),
        ),
    ),
    Action(
        name="projects.export",
        family=VerbFamily.QUERY,
        owner="projects",
        summary="Create a policy-filtered ZIP snapshot of the Git source set.",
        Input=ExportInput,
        Output=ProjectExport,
        handler=_export,
        principals=ALL_PRINCIPALS,
        resource_kinds=_KINDS,
        affordances=("projects.get", "projects.read"),
        aliases=("snapshot", "bundle", "download project", "portable export"),
        documentation="Exports tracked and nonignored untracked files, excluding sensitive and local-only paths. Symlink entries retain their link targets; symlinked parent directories are refused. Optional file and byte bounds return next_start_after; pass it with checkout_revision as expected_revision to continue. Fetch the ZIP through its artifact ref; its manifest_path holds the complete per-file manifest.",
        examples=(
            Example(
                title="Export a bounded checkout",
                input={**_EXAMPLE, "max_files": 500, "max_bytes": 8_000_000},
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
        documentation="max_matches selects retained matches; page_size sizes responses. next_cursor pages the immutable observation after checkout edits. checkout_revision identifies its captured source; truncated reports additional matches beyond max_matches. Cursors bind the principal, checkout and query.",
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
        summary="Write one project file or apply a patch, guarded by checkout or file content revisions.",
        Input=ChangeInput,
        Output=ChangeResult,
        handler=_change,
        principals=OPERATOR_ONLY,
        resource_kinds=_KINDS,
        affordances=("projects.diff", "projects.read", "projects.get"),
        aliases=("write file", "edit", "apply patch", "save"),
        supports_precondition=True,
        documentation="Paths stay project-relative and policy-excluded paths (.git, secrets, local-only agent state) are refused. Take expected_dirty_sha256 or expected_head from projects.get, or expected_file_sha256 from projects.read.",
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
        documentation="Project-scoped view of context.compose with the same owner coverage, compact presentation and snapshot retrieval, plus project navigation affordances.",
        examples=(
            Example(title="Orientation", input=_EXAMPLE),
            Example(title="Triage", input={**_EXAMPLE, "intent": "project.triage"}),
        ),
    ),
)
