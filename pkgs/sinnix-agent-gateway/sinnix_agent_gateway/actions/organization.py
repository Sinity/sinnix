"""Explicit, reviewable filesystem relocation plans and application."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from ..action import OPERATOR_ONLY, Action, Example, MutationControls, RequestControls
from ..capabilities import Capability
from ..contracts import VerbFamily
from ..locators import FileLocator, encode_file_ref
from ..organization import (
    OrganizationError,
    OrganizationService,
    file_identity,
    identity_matches,
)
from ..results import ProtocolError
from ..schemas import GatewayModel
from .files import SearchInput, _search

if TYPE_CHECKING:
    from ..runtime import Runtime


class MoveMapping(GatewayModel):
    source: FileLocator
    destination: FileLocator


class PlanInput(RequestControls):
    """Only caller-selected moves and mkdirs are considered."""

    moves: list[MoveMapping] = Field(min_length=1, max_length=2_000)
    mkdirs: list[FileLocator] = Field(default_factory=list, max_length=2_000)


class PlannedMove(GatewayModel):
    index: int
    source: str
    source_ref: str
    destination: str
    destination_ref: str
    identity: dict[str, Any] | None = None
    parent: str | None = None
    same_filesystem: bool | None = None
    ready: bool
    refusal: str | None = None


class PlannedMkdir(GatewayModel):
    index: int
    target: str
    target_ref: str
    parent: str | None = None
    ready: bool
    refusal: str | None = None


class PlanResult(GatewayModel):
    plan_artifact: dict[str, Any]
    plan_digest: str
    moves: list[PlannedMove]
    mkdirs: list[PlannedMkdir]
    ready: bool
    catalog_note: str
    limitations: list[str]


class ChangesetInput(MutationControls):
    plan_ref: str = Field(pattern=r"^sinnix://artifacts/[0-9a-fA-F-]{36}$")
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class AppliedEntry(GatewayModel):
    kind: Literal["mkdir", "move"]
    index: int
    state: Literal["applied", "failed"]
    source: str | None = None
    destination: str | None = None
    error: str | None = None
    compensation_hint: str | None = None


class ChangesetResult(GatewayModel):
    state: Literal["applied", "partial"]
    atomic: Literal[False] = False
    plan_ref: str
    plan_digest: str
    entries: list[AppliedEntry]
    receipt_artifact: dict[str, Any]
    limitations: list[str]


class ReferencesInput(RequestControls):
    roots: list[FileLocator] = Field(min_length=1, max_length=8)
    old_paths: list[str] = Field(min_length=1, max_length=64)
    include_hidden: bool = False
    respect_ignore_files: bool = True
    max_depth: int | None = Field(default=None, ge=1, le=64)
    limit_per_path: int = Field(default=100, ge=1, le=1_000)
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class ReferenceHit(GatewayModel):
    old_path: str
    path: str
    ref: str
    line_number: int
    text: str


class ReferencesResult(GatewayModel):
    roots: list[str]
    hits: list[ReferenceHit]
    truncated: bool
    warnings: list[str] = Field(default_factory=list)


def _resolve_existing(runtime: Runtime, locator: FileLocator) -> Path:
    raw, _ = locator.resolve()
    return runtime.files._resolve(raw, existing=True)


def _destination_state(
    runtime: Runtime, locator: FileLocator, planned_parents: set[str]
) -> tuple[Path | None, str | None]:
    raw, _ = locator.resolve()
    candidate = Path(raw).expanduser()
    if candidate.is_symlink():
        return None, "destination is a symlink"
    if candidate.exists():
        return None, "destination already exists"
    try:
        return runtime.files._resolve(raw, existing=False), None
    except Exception as exc:
        if str(candidate.parent) not in planned_parents:
            return None, f"destination parent is unavailable: {exc}"
        ancestor = candidate.parent
        while not ancestor.exists():
            if ancestor == ancestor.parent:
                return None, "destination parent is unavailable"
            ancestor = ancestor.parent
        try:
            runtime.files._resolve(str(ancestor), existing=True)
        except Exception as parent_exc:
            return None, f"destination parent is unavailable: {parent_exc}"
        return candidate, None


def _nearest_existing_parent(path: Path) -> Path:
    parent = path.parent
    while not parent.exists():
        if parent == parent.parent:
            raise OSError("no existing destination ancestor")
        parent = parent.parent
    return parent


def _directory_boundary_refusal(runtime: Runtime, source: Path) -> str | None:
    """Keep broad roots and owner-managed state outside relocation workflows."""
    protected = {
        Path("/"),
        Path("/realm"),
        Path("/realm/state"),
        Path("/realm/worktrees"),
        Path.home().resolve(),
        *(project.path.resolve() for project in runtime.config.projects.values()),
    }
    if source in protected:
        return "directory is a broad, mount, project, home, or owner-managed root; directory moves are refused"
    if source.is_mount():
        return "directory is a mount point; directory moves are refused"
    for root in (Path("/realm/state"), Path("/realm/worktrees")):
        if root in source.parents:
            return "directory lies under owner-managed state or worktrees; directory moves are refused"
    return None


def _plan_move(
    runtime: Runtime, index: int, mapping: MoveMapping, planned_parents: set[str]
) -> PlannedMove:
    raw_source, source_ref = mapping.source.resolve()
    raw_destination, destination_ref = mapping.destination.resolve()
    raw_source_path = Path(raw_source).expanduser()
    if raw_source_path.is_symlink():
        return PlannedMove(
            index=index,
            source=raw_source,
            source_ref=source_ref,
            destination=raw_destination,
            destination_ref=destination_ref,
            ready=False,
            refusal="source is a symlink; relocation follows no final symlink",
        )
    try:
        source = _resolve_existing(runtime, mapping.source)
    except Exception as exc:
        return PlannedMove(
            index=index,
            source=raw_source,
            source_ref=source_ref,
            destination=raw_destination,
            destination_ref=destination_ref,
            ready=False,
            refusal=f"source is unavailable: {exc}",
        )
    if source.is_dir():
        boundary_refusal = _directory_boundary_refusal(runtime, source)
        if boundary_refusal is not None:
            return PlannedMove(
                index=index,
                source=str(source),
                source_ref=encode_file_ref(str(source)),
                destination=raw_destination,
                destination_ref=destination_ref,
                ready=False,
                refusal=boundary_refusal,
            )
    try:
        identity = file_identity(source)
    except Exception as exc:
        return PlannedMove(
            index=index,
            source=str(source),
            source_ref=encode_file_ref(str(source)),
            destination=raw_destination,
            destination_ref=destination_ref,
            ready=False,
            refusal=f"source cannot be inspected: {exc}",
        )
    if identity["kind"] not in {"file", "directory"}:
        return PlannedMove(
            index=index,
            source=str(source),
            source_ref=encode_file_ref(str(source)),
            destination=raw_destination,
            destination_ref=destination_ref,
            identity=identity,
            ready=False,
            refusal="only regular-file and same-filesystem directory moves are supported; symlink and special-file moves are refused",
        )
    destination, refusal = _destination_state(
        runtime, mapping.destination, planned_parents
    )
    if destination is None:
        return PlannedMove(
            index=index,
            source=str(source),
            source_ref=encode_file_ref(str(source)),
            destination=raw_destination,
            destination_ref=destination_ref,
            identity=identity,
            ready=False,
            refusal=refusal,
        )
    try:
        same_filesystem = (
            source.stat().st_dev == _nearest_existing_parent(destination).stat().st_dev
        )
    except OSError as exc:
        return PlannedMove(
            index=index,
            source=str(source),
            source_ref=encode_file_ref(str(source)),
            destination=str(destination),
            destination_ref=encode_file_ref(str(destination)),
            identity=identity,
            ready=False,
            refusal=f"destination parent is unavailable: {exc}",
        )
    if identity["kind"] == "directory" and not same_filesystem:
        return PlannedMove(
            index=index,
            source=str(source),
            source_ref=encode_file_ref(str(source)),
            destination=str(destination),
            destination_ref=encode_file_ref(str(destination)),
            identity=identity,
            parent=str(destination.parent),
            same_filesystem=False,
            ready=False,
            refusal="directory source and destination parent are on different filesystems; recursive copy is refused",
        )
    return PlannedMove(
        index=index,
        source=str(source),
        source_ref=encode_file_ref(str(source)),
        destination=str(destination),
        destination_ref=encode_file_ref(str(destination)),
        identity=identity,
        parent=str(destination.parent),
        same_filesystem=same_filesystem,
        ready=True,
    )


def _plan_mkdir(runtime: Runtime, index: int, locator: FileLocator) -> PlannedMkdir:
    raw, ref = locator.resolve()
    candidate = Path(raw).expanduser()
    if candidate.exists() or candidate.is_symlink():
        return PlannedMkdir(
            index=index,
            target=raw,
            target_ref=ref,
            ready=False,
            refusal="directory target already exists",
        )
    try:
        target = runtime.files._resolve(raw, existing=False)
    except Exception as exc:
        return PlannedMkdir(
            index=index,
            target=raw,
            target_ref=ref,
            ready=False,
            refusal=f"directory parent is unavailable: {exc}",
        )
    return PlannedMkdir(
        index=index,
        target=str(target),
        target_ref=encode_file_ref(str(target)),
        parent=str(target.parent),
        ready=True,
    )


def _plan(runtime: Runtime, inp: PlanInput) -> PlanResult:
    runtime.principal.require(Capability.FILE_READ)
    mkdirs = [
        _plan_mkdir(runtime, index, target) for index, target in enumerate(inp.mkdirs)
    ]
    planned_parents = {entry.target for entry in mkdirs if entry.ready}
    moves = [
        _plan_move(runtime, index, mapping, planned_parents)
        for index, mapping in enumerate(inp.moves)
    ]
    _refuse_nested_or_cyclic_moves(moves)
    plan: dict[str, Any] = {
        "schema": OrganizationService.plan_schema,
        "principal": runtime.principal.name,
        "moves": [entry.model_dump() for entry in moves],
        "mkdirs": [entry.model_dump() for entry in mkdirs],
    }
    service = OrganizationService(runtime.files, runtime.artifacts)
    artifact = service.persist_plan(plan)
    return PlanResult(
        plan_artifact=artifact,
        plan_digest=plan["plan_digest"],
        moves=moves,
        mkdirs=mkdirs,
        ready=all(entry.ready for entry in [*moves, *mkdirs]),
        catalog_note="The file catalog remains a separately owned read/write workflow. This action records no catalog changes.",
        limitations=[
            "Only explicit regular-file moves, same-filesystem directory renames, and explicit mkdirs are supported.",
            "No automatic classification, recursive directory copy, deletion, or catalog mutation occurs.",
            "A cross-filesystem move is an exclusive copy followed by source unlink, so it is not atomic.",
        ],
    )


def _refuse_nested_or_cyclic_moves(moves: list[PlannedMove]) -> None:
    """Reject mappings that could make plan ordering change their meaning."""
    for index, left in enumerate(moves):
        if not left.ready:
            continue
        source = Path(left.source)
        for other_index, right in enumerate(moves):
            if index == other_index or not right.ready:
                continue
            other_source, other_destination = (
                Path(right.source),
                Path(right.destination),
            )
            if (
                source == other_source
                or source in other_source.parents
                or other_source in source.parents
            ):
                left.ready = False
                left.refusal = "nested or duplicate move sources are refused"
                break
            if source.is_dir() and (
                other_destination == source
                or source in other_destination.parents
                or other_destination in source.parents
            ):
                left.ready = False
                left.refusal = "directory mappings may not be nested or cyclic"
                break


def _require_preconditions(runtime: Runtime, plan: dict[str, Any]) -> None:
    failures: list[dict[str, Any]] = []
    mkdir_targets = {row["target"] for row in plan["mkdirs"] if row["ready"]}
    for row in plan["mkdirs"]:
        target = Path(row["target"])
        if not row["ready"]:
            failures.append(
                {"kind": "mkdir", "index": row["index"], "reason": row["refusal"]}
            )
        elif target.exists() or target.is_symlink():
            failures.append(
                {
                    "kind": "mkdir",
                    "index": row["index"],
                    "reason": "directory target now exists",
                }
            )
        elif not target.parent.exists() and str(target.parent) not in mkdir_targets:
            failures.append(
                {
                    "kind": "mkdir",
                    "index": row["index"],
                    "reason": "directory parent is unavailable",
                }
            )
    for row in plan["moves"]:
        source, destination = Path(row["source"]), Path(row["destination"])
        if not row["ready"]:
            failures.append(
                {"kind": "move", "index": row["index"], "reason": row["refusal"]}
            )
        elif not identity_matches(source, row["identity"]):
            failures.append(
                {
                    "kind": "move",
                    "index": row["index"],
                    "reason": "source identity changed",
                }
            )
        elif destination.exists() or destination.is_symlink():
            failures.append(
                {
                    "kind": "move",
                    "index": row["index"],
                    "reason": "destination now exists",
                }
            )
        elif (
            not destination.parent.exists()
            and str(destination.parent) not in mkdir_targets
        ):
            failures.append(
                {
                    "kind": "move",
                    "index": row["index"],
                    "reason": "destination parent is unavailable",
                }
            )
    if failures:
        raise ProtocolError(
            "precondition_failed",
            "plan preconditions changed; no filesystem mutation was attempted",
            details={"failures": failures},
        )


def _changeset(runtime: Runtime, inp: ChangesetInput) -> ChangesetResult:
    runtime.principal.require(Capability.FILE_WRITE)
    service = OrganizationService(runtime.files, runtime.artifacts)
    try:
        plan = service.load_plan(inp.plan_ref)
    except OrganizationError as exc:
        raise ProtocolError("not_found", str(exc)) from exc
    if plan.get("principal") != runtime.principal.name:
        raise ProtocolError("policy_denied", "plan belongs to another principal")
    if plan.get("plan_digest") != inp.plan_digest:
        raise ProtocolError(
            "precondition_failed", "plan digest does not match the selected artifact"
        )
    _require_preconditions(runtime, plan)

    entries: list[AppliedEntry] = []
    failed = False
    for row in sorted(
        plan["mkdirs"],
        key=lambda value: (len(Path(value["target"]).parts), value["index"]),
    ):
        target = Path(row["target"])
        try:
            target.mkdir(mode=0o700)
            entries.append(
                AppliedEntry(
                    kind="mkdir",
                    index=row["index"],
                    state="applied",
                    destination=str(target),
                    compensation_hint="Remove this directory only if it remains empty.",
                )
            )
        except OSError as exc:
            failed = True
            entries.append(
                AppliedEntry(
                    kind="mkdir",
                    index=row["index"],
                    state="failed",
                    destination=str(target),
                    error=str(exc),
                )
            )
            break
    if not failed:
        for row in plan["moves"]:
            source, destination = Path(row["source"]), Path(row["destination"])
            try:
                if row["identity"]["kind"] == "directory":
                    service.move_directory_same_filesystem(source, destination)
                    hint = "Rename the destination back only if the original source path is still absent and the directory tree identity is verified."
                else:
                    service.move_regular_file(
                        source, destination, row["identity"]["sha256"]
                    )
                    hint = "Move the destination back only if the original source path is still absent and the destination identity is verified."
                entries.append(
                    AppliedEntry(
                        kind="move",
                        index=row["index"],
                        state="applied",
                        source=str(source),
                        destination=str(destination),
                        compensation_hint=hint,
                    )
                )
            except OrganizationError as exc:
                failed = True
                entries.append(
                    AppliedEntry(
                        kind="move",
                        index=row["index"],
                        state="failed",
                        source=str(source),
                        destination=str(destination),
                        error=str(exc),
                    )
                )
                break
    receipt = {
        "schema": "sinnix.gateway-files-changeset-receipt.v1",
        "principal": runtime.principal.name,
        "plan_ref": inp.plan_ref,
        "plan_digest": inp.plan_digest,
        "atomic": False,
        "state": "partial" if failed else "applied",
        "entries": [entry.model_dump() for entry in entries],
    }
    receipt_artifact = runtime.artifacts.register_json(
        receipt,
        kind="files-changeset-receipt",
        owner_id="organization",
        source="files.changeset",
        target={"plan_ref": inp.plan_ref, "plan_digest": inp.plan_digest},
    )
    return ChangesetResult(
        state="partial" if failed else "applied",
        plan_ref=inp.plan_ref,
        plan_digest=inp.plan_digest,
        entries=entries,
        receipt_artifact=receipt_artifact,
        limitations=[
            "No global transaction or rollback exists. A partial result contains compensation hints for only the entries already applied."
        ],
    )


def _references(runtime: Runtime, inp: ReferencesInput) -> ReferencesResult:
    runtime.principal.require(Capability.FILE_READ)
    hits: list[ReferenceHit] = []
    truncated = False
    warnings: list[str] = []
    roots = [
        encode_file_ref(str(_resolve_existing(runtime, root))) for root in inp.roots
    ]
    for old_path in inp.old_paths:
        result = _search(
            runtime,
            SearchInput(
                roots=inp.roots,
                content_regex=old_path,
                fixed_string=True,
                include_hidden=inp.include_hidden,
                respect_ignore_files=inp.respect_ignore_files,
                max_depth=inp.max_depth,
                limit=inp.limit_per_path,
                timeout_seconds=inp.timeout_seconds,
            ),
        )
        truncated = truncated or result.truncated
        warnings.extend(result.warnings)
        for match in result.matches:
            for line in match.lines:
                if line.is_match:
                    hits.append(
                        ReferenceHit(
                            old_path=old_path,
                            path=match.path,
                            ref=match.ref,
                            line_number=line.line_number,
                            text=line.text,
                        )
                    )
    return ReferencesResult(
        roots=roots, hits=hits, truncated=truncated, warnings=warnings
    )


ACTIONS: tuple[Action, ...] = (
    Action(
        name="files.plan",
        family=VerbFamily.QUERY,
        owner="organization",
        summary="Build an immutable preview for explicit regular-file moves and mkdirs.",
        Input=PlanInput,
        Output=PlanResult,
        handler=_plan,
        principals=OPERATOR_ONLY,
        resource_kinds=("host_file",),
        affordances=("files.changeset", "files.references"),
        aliases=("move plan", "relocation preview"),
        documentation="The caller supplies every mapping. The plan hashes each regular source file and records collision, parent and filesystem facts without changing host files.",
        examples=(
            Example(
                title="Plan one explicit move",
                input={
                    "moves": [
                        {
                            "source": {"path": "/realm/tmp/work/a.txt"},
                            "destination": {"path": "/realm/archive/a.txt"},
                        }
                    ]
                },
            ),
        ),
    ),
    Action(
        name="files.changeset",
        family=VerbFamily.CHANGE,
        owner="organization",
        summary="Apply an approved explicit filesystem plan after revalidating every entry.",
        Input=ChangesetInput,
        Output=ChangesetResult,
        handler=_changeset,
        principals=OPERATOR_ONLY,
        resource_kinds=("host_file",),
        affordances=("files.stat", "files.references"),
        aliases=("apply move plan", "relocation changeset"),
        supports_precondition=True,
        documentation="All planned sources, destinations and parents are revalidated before the first mutation. Transfers never overwrite. Results are honest about partial completion and no global atomicity is claimed.",
        examples=(
            Example(
                title="Apply an approved plan",
                input={
                    "plan_ref": "sinnix://artifacts/00000000-0000-0000-0000-000000000000",
                    "plan_digest": "0" * 64,
                    "idempotency_key": "apply-relocation-1",
                },
            ),
        ),
    ),
    Action(
        name="files.references",
        family=VerbFamily.QUERY,
        owner="organization",
        summary="Find explicit old absolute paths in bounded text roots before a filesystem cutover.",
        Input=ReferencesInput,
        Output=ReferencesResult,
        handler=_references,
        principals=OPERATOR_ONLY,
        resource_kinds=("host_file",),
        affordances=("files.read", "files.plan"),
        aliases=("find old paths", "path references"),
        documentation="Runs the existing bounded files.search text primitive once for each supplied old path. It only reports provenance and never rewrites references.",
        examples=(
            Example(
                title="Find one old path",
                input={
                    "roots": [{"path": "/realm/project/sinnix"}],
                    "old_paths": ["/realm/data/old-note.md"],
                },
            ),
        ),
    ),
)
