"""Every prompt agentctl compiles: a worker's, a resumed worker's, and the
landing agents' (`review.md`, `integrate.md` beside this module).

No external tool does this: Beads holds the task text, the repository holds
the worker contract and atlas sheets, and the prompt is the join.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from ..limits import CALL_TIMEOUT_SECONDS
from ..projects import ProjectAdapter

TEMPLATE_VERSION = "v2"
MAX_PROMPT_BYTES = 200_000
# When the full bead bodies do not fit the budget, each is embedded as a
# digest and this many leading characters; the worker reads the rest with
# `bd show` and checks the digest.
DIGEST_EXCERPT_CHARS = 600
EXECUTABLE_STATUSES = frozenset({"open", "in_progress"})
_INACTIVE_STATUSES = frozenset({"closed", "deferred"})
# A PR title is the squash subject; GitHub wraps past this, and the
# repository's commit convention stops here.
MAX_SUBJECT_LENGTH = 72
DEFAULT_BACKEND = "codex"
DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_EFFORT = "medium"
DEFAULT_TEMPLATE_RELATIVE_PATH = (
    "dots/_ai/skills/orchestrate/references/worker-contract.md"
)
DEFAULT_ATLAS_RELATIVE_PATH = "docs/atlas"
DEFAULT_POLICY_MAP: dict[str, tuple[str, str]] = {
    "provider-neutral-calibrated-v2": ("codex", "gpt-5.6-luna"),
    "provider-neutral-capability-v1": ("codex", "gpt-5.6-luna"),
    "provider-pinned-v1": ("codex", "gpt-5.6-luna"),
}
MODEL_ALIASES: dict[str, tuple[str, str]] = {
    "sol": ("codex", "gpt-5.6-sol"),
    "terra": ("codex", "gpt-5.6-terra"),
    "luna": ("codex", "gpt-5.6-luna"),
}
BACKEND_MODEL_PREFIXES = {
    "codex": "gpt-",
    "claude": "claude-",
    "gemini": "gemini-",
    "antigravity": "gemini-",
    "grok": "grok-",
}
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._/-]+")
_SUBJECT_PREFIXES = {"bug": "fix", "feature": "feat"}


class PromptError(ValueError):
    """A prompt cannot be compiled or dispatched safely."""


class BdReader(Protocol):
    def show(self, bead_id: str) -> Mapping[str, Any]: ...

    def list(self) -> Sequence[Mapping[str, Any]]: ...

    def ready(self) -> Sequence[Mapping[str, Any]]: ...


@dataclass(frozen=True)
class SubprocessBdReader:
    """`bd` resolves its database from the working directory: run it in the project."""

    root: Path
    executable: str = "bd"

    def _run(self, arguments: Sequence[str]) -> Any:
        try:
            result = subprocess.run(
                [self.executable, *arguments],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
                timeout=CALL_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise PromptError(
                f"bd {' '.join(arguments)} failed in {self.root}"
            ) from error
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise PromptError("bd returned invalid JSON") from error

    def show(self, bead_id: str) -> Mapping[str, Any]:
        return _one_bead(self._run(("show", bead_id, "--json")), bead_id)

    def list(self) -> Sequence[Mapping[str, Any]]:
        return _bead_list(
            self._run(("list", "--all", "--limit", "0", "--json")), "list"
        )

    def ready(self) -> Sequence[Mapping[str, Any]]:
        return _bead_list(self._run(("ready", "--limit", "0", "--json")), "ready")


def _bead_list(value: Any, what: str) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, list) or any(
        not isinstance(item, Mapping) for item in value
    ):
        raise PromptError(f"bd {what} returned an invalid bead list")
    return value


def _one_bead(value: Any, bead_id: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping) and "error" not in value:
        bead = value
    elif isinstance(value, list) and len(value) == 1 and isinstance(value[0], Mapping):
        bead = value[0]
    else:
        raise PromptError(f"bd show {bead_id} returned an invalid bead")
    if bead.get("id") != bead_id:
        raise PromptError(f"bd show {bead_id} returned the wrong bead")
    return bead


def _metadata(bead: Mapping[str, Any]) -> Mapping[str, Any]:
    value = bead.get("metadata", {})
    return value if isinstance(value, Mapping) else {}


def bead_subject(bead: Mapping[str, Any]) -> str:
    """The PR title: the bead title behind its type prefix, within the subject limit."""
    kind = str(bead.get("issue_type") or bead.get("type") or "").lower()
    prefix = _SUBJECT_PREFIXES.get(kind, "chore")
    title = " ".join(str(bead.get("title") or "").split())
    if re.match(
        r"^(fix|feat|chore|refactor|docs|test|perf|build|ci)(\([^)]*\))?!?:", title
    ):
        subject = title
    else:
        subject = f"{prefix}: {title}" if title else prefix
    if len(subject) > MAX_SUBJECT_LENGTH:
        subject = subject[: MAX_SUBJECT_LENGTH - 1].rstrip() + "…"
    return subject


@dataclass(frozen=True)
class PromptConfig:
    template_path: Path
    atlas_dir: Path
    project_root: Path
    template_version: str = TEMPLATE_VERSION
    branch_prefix: str = "feature/packet"
    default_backend: str = DEFAULT_BACKEND
    default_model: str = DEFAULT_MODEL
    default_effort: str = DEFAULT_EFFORT
    policy_map: Mapping[str, tuple[str, str]] = field(
        default_factory=lambda: dict(DEFAULT_POLICY_MAP)
    )

    @classmethod
    def from_project(
        cls, project: ProjectAdapter, *, shared_template: Path | None = None
    ) -> PromptConfig:
        """The descriptor's ``[packets]``; ``shared_template`` is the worker
        contract a descriptor that names none uses."""
        packets = project.packets
        template = packets.template or shared_template
        return cls(
            template_path=project.root / DEFAULT_TEMPLATE_RELATIVE_PATH
            if template is None
            else template,
            atlas_dir=packets.atlas_dir or project.root / DEFAULT_ATLAS_RELATIVE_PATH,
            project_root=project.root,
            template_version=packets.template_version or TEMPLATE_VERSION,
            branch_prefix=packets.branch_prefix or "feature/packet",
            default_backend=packets.backend or DEFAULT_BACKEND,
            default_model=packets.model or DEFAULT_MODEL,
            default_effort=packets.effort or DEFAULT_EFFORT,
            policy_map={**DEFAULT_POLICY_MAP, **packets.model_policy},
        )

    def branch_for(self, bead_id: str) -> str:
        return f"{self.branch_prefix}/{_safe_name(bead_id)}"

    def resolve_model(self, backend: str, model: str) -> str:
        """Resolve a configured shorthand and reject known provider mismatches."""
        aliases = dict(MODEL_ALIASES)
        for configured_backend, configured_model in self.policy_map.values():
            if configured_backend == "codex" and configured_model.startswith("gpt-"):
                alias = configured_model.removeprefix("gpt-5.6-")
                aliases.setdefault(alias, (configured_backend, configured_model))
        valid = ", ".join(sorted(aliases))
        if model in aliases:
            alias_backend, resolved = aliases[model]
            if backend != alias_backend:
                raise PromptError(
                    f"model alias {model!r} is incompatible with backend {backend!r}; "
                    f"it requires backend {alias_backend!r}; "
                    f"valid aliases: {valid}"
                )
            return resolved
        if (
            model in {value[1] for value in self.policy_map.values()}
            or model == self.default_model
        ):
            resolved = model
        elif not any(
            model.startswith(prefix) for prefix in BACKEND_MODEL_PREFIXES.values()
        ):
            raise PromptError(f"unknown model alias {model!r}; valid aliases: {valid}")
        else:
            resolved = model
        expected_prefix = BACKEND_MODEL_PREFIXES.get(backend)
        if expected_prefix is None:
            valid_backends = ", ".join(sorted(BACKEND_MODEL_PREFIXES))
            raise PromptError(
                f"unsupported backend {backend!r}; valid backends: {valid_backends}"
            )
        known_model = any(
            resolved.startswith(prefix) for prefix in BACKEND_MODEL_PREFIXES.values()
        )
        if known_model and not resolved.startswith(expected_prefix):
            raise PromptError(
                f"model {resolved!r} is incompatible with backend {backend!r}"
            )
        return resolved


@dataclass(frozen=True)
class PromptDimensions:
    template_version: str
    backend: str
    model: str
    effort: str
    model_policy: str
    verification_commands: tuple[str, ...]
    affected_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_version": self.template_version,
            "backend": self.backend,
            "model": self.model,
            "effort": self.effort,
            "model_policy": self.model_policy,
            "verification_commands": list(self.verification_commands),
            "affected_paths": list(self.affected_paths),
        }


@dataclass(frozen=True)
class PromptSnapshot:
    project_id: str
    leader_id: str
    bead_ids: tuple[str, ...]
    beads: tuple[Mapping[str, Any], ...]
    branch: str
    dimensions: PromptDimensions
    atlas_refs: tuple[str, ...]
    worker_contract_path: str
    prompt: str
    # Batch facts the worker needs beyond the beads: run id, worker id, base
    # commit, result path and schema. Empty outside a batch.
    batch: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        document = {
            "schema_version": 2,
            "template_version": self.dimensions.template_version,
            "project_id": self.project_id,
            "leader_id": self.leader_id,
            "bead_ids": list(self.bead_ids),
            "branch": self.branch,
            "beads": [dict(bead) for bead in self.beads],
            "dimensions": self.dimensions.to_dict(),
            "atlas_refs": list(self.atlas_refs),
            "worker_contract_path": self.worker_contract_path,
        }
        if self.batch:
            document["batch"] = dict(self.batch)
        return document


def resolve_group(bead_id: str, reader: BdReader) -> tuple[str, tuple[str, ...]]:
    """The seed's dispatch group: its leader id and the open members.

    A group is co-executed OPEN work: a closed or deferred member — the leader
    included — is done and its spec is never reissued as an instruction.
    """
    seed = reader.show(bead_id)
    group = _metadata(seed).get("dispatch_group")
    leader_id = group if isinstance(group, str) and group else bead_id
    member_ids = {
        row.get("id")
        for row in reader.list()
        if isinstance(row.get("id"), str)
        and _metadata(row).get("dispatch_group") == leader_id
        and row.get("status") not in _INACTIVE_STATUSES
    }
    for candidate in (leader_id, bead_id):
        record = seed if candidate == bead_id else _bead_or_none(reader, candidate)
        if record is not None and record.get("status") not in _INACTIVE_STATUSES:
            member_ids.add(candidate)
    if not member_ids:
        raise PromptError(f"dispatch group {leader_id} has no open members")
    if not all(isinstance(item, str) and item for item in member_ids):
        raise PromptError("dispatch group contains an invalid bead id")
    return leader_id, tuple(sorted(member_ids))


def _bead_or_none(reader: BdReader, bead_id: str) -> Mapping[str, Any] | None:
    try:
        return reader.show(bead_id)
    except PromptError:
        return None


@dataclass(frozen=True)
class Refusal:
    """Why a bead cannot be a batch member. ``code`` is stable; ``detail`` is for people."""

    code: str
    bead: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "bead": self.bead, "detail": self.detail}


def write_scope(bead: Mapping[str, Any]) -> tuple[str, ...]:
    """The globs a bead's worker may write, from metadata ``write_scope``."""
    value = _metadata(bead).get("write_scope")
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(";") if item.strip())
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, str) and item)
    return ()


def _scopes_overlap(left: str, right: str) -> bool:
    """Identical globs, one a directory prefix of the other, or one matching the other."""
    if left == right:
        return True
    left_dir = left.rstrip("/") + "/"
    right_dir = right.rstrip("/") + "/"
    if left.startswith(right_dir) or right.startswith(left_dir):
        return True
    return fnmatch.fnmatchcase(left, right) or fnmatch.fnmatchcase(right, left)


def _open_external_blockers(
    bead: Mapping[str, Any], members: set[str], reader: BdReader
) -> list[str]:
    blockers: list[str] = []
    for item in bead.get("dependencies") or ():
        if isinstance(item, str):
            record = _bead_or_none(reader, item)
            kind = "blocks"
        elif isinstance(item, Mapping):
            record = item
            kind = str(item.get("dependency_type") or item.get("edge_type") or "blocks")
        else:
            continue
        if record is None or kind != "blocks":
            continue
        blocker = record.get("id")
        if (
            isinstance(blocker, str)
            and blocker not in members
            and record.get("status") not in _INACTIVE_STATUSES
        ):
            blockers.append(blocker)
    return blockers


def validate_members(
    reader: BdReader,
    workers: Sequence[Sequence[str]],
    *,
    claimed: set[str],
) -> list[Refusal]:
    """Every reason the workers' members cannot run together, or an empty list.

    ``workers`` groups member ids per worker; ``claimed`` holds ids already in
    another run. A member is executable when it exists, is open or in
    progress, has no open ``blocks`` dependency outside the member set, is
    unclaimed, belongs to one worker only, and its write scope is disjoint
    from every other worker's.
    """
    refusals: list[Refusal] = []
    members = {item for worker in workers for item in worker}
    seen: dict[str, int] = {}
    scopes: list[tuple[int, str, str]] = []
    for index, worker in enumerate(workers):
        for bead_id in worker:
            if bead_id in seen and seen[bead_id] != index:
                refusals.append(Refusal("duplicate", bead_id, "listed in two workers"))
                continue
            seen[bead_id] = index
            bead = _bead_or_none(reader, bead_id)
            if bead is None:
                refusals.append(Refusal("missing", bead_id, "bd has no such bead"))
                continue
            status = str(bead.get("status") or "")
            if status not in EXECUTABLE_STATUSES:
                refusals.append(Refusal("status", bead_id, f"status is {status!r}"))
                continue
            if bead_id in claimed:
                refusals.append(Refusal("in_run", bead_id, "already in another run"))
                continue
            assignee = bead.get("assignee")
            if status == "in_progress" and isinstance(assignee, str) and assignee:
                refusals.append(Refusal("claimed", bead_id, f"claimed by {assignee}"))
                continue
            blockers = _open_external_blockers(bead, members, reader)
            if blockers:
                refusals.append(
                    Refusal("blocked", bead_id, "blocked by " + ", ".join(blockers))
                )
                continue
            scopes.extend((index, bead_id, glob) for glob in write_scope(bead))
    for position, (index, bead_id, glob) in enumerate(scopes):
        for other_index, other_bead, other_glob in scopes[position + 1 :]:
            if other_index != index and _scopes_overlap(glob, other_glob):
                refusals.append(
                    Refusal(
                        "write_scope",
                        bead_id,
                        f"{glob!r} overlaps {other_bead}'s {other_glob!r}",
                    )
                )
    return refusals


def _policy_dimensions(
    beads: Sequence[Mapping[str, Any]],
    config: PromptConfig,
    *,
    backend: str | None,
    model: str | None,
    effort: str | None,
) -> PromptDimensions:
    leader_metadata = _metadata(beads[0])
    policy = leader_metadata.get("model_policy", "")
    policy_name = policy if isinstance(policy, str) and policy else "default"
    policy_backend, policy_model = config.policy_map.get(
        policy_name, (config.default_backend, config.default_model)
    )
    declared_effort = leader_metadata.get("effort")
    if not isinstance(declared_effort, str) or not declared_effort:
        declared_effort = config.default_effort

    def values(name: str) -> tuple[str, ...]:
        result: set[str] = set()
        for bead in beads:
            value = _metadata(bead).get(name)
            if isinstance(value, str):
                result.update(item.strip() for item in value.split(";") if item.strip())
            elif isinstance(value, list):
                result.update(item for item in value if isinstance(item, str) and item)
        return tuple(sorted(result))

    effective_backend = backend or policy_backend
    effective_model = config.resolve_model(effective_backend, model or policy_model)
    return PromptDimensions(
        template_version=config.template_version,
        backend=effective_backend,
        model=effective_model,
        effort=effort or declared_effort,
        model_policy=policy_name,
        verification_commands=values("verification_commands"),
        affected_paths=values("affected_paths"),
    )


def _atlas_refs(
    root: Path, atlas_dir: Path, affected_paths: Sequence[str]
) -> tuple[str, ...]:
    if not atlas_dir.is_dir():
        return ()
    tokens = {Path(path).parts[0] for path in affected_paths if Path(path).parts}
    sheets = sorted(atlas_dir.glob("*.md"))
    relevant = [sheet for sheet in sheets if sheet.stem in tokens] or sheets
    return tuple(str(sheet.relative_to(root)) for sheet in relevant)


def _safe_name(value: str) -> str:
    cleaned = _SAFE_NAME.sub("-", value).strip("-./")
    return cleaned or "packet"


def _bounded(prompt: str) -> str:
    if len(prompt.encode()) > MAX_PROMPT_BYTES:
        raise PromptError(
            f"compiled prompt is {len(prompt.encode())} bytes, over the "
            f"{MAX_PROMPT_BYTES}-byte budget"
        )
    return prompt


def _fits(prompt: str) -> bool:
    return len(prompt.encode()) <= MAX_PROMPT_BYTES


def bead_digest(bead: Mapping[str, Any]) -> str:
    """sha256 of the bead's title and description, as the worker recomputes it."""
    text = f"{bead.get('title') or ''}\n{bead.get('description') or ''}"
    return hashlib.sha256(text.encode()).hexdigest()


def digest_bead(bead: Mapping[str, Any]) -> dict[str, Any]:
    description = str(bead.get("description") or "")
    return {
        "id": bead.get("id"),
        "title": bead.get("title"),
        "status": bead.get("status"),
        "digest": bead_digest(bead),
        "excerpt": description[:DIGEST_EXCERPT_CHARS],
        "truncated": len(description) > DIGEST_EXCERPT_CHARS,
    }


_RELATIONSHIP_FIELDS = (
    "id",
    "status",
    "issue_type",
    "title",
    "dependency_type",
    "edge",
    "edge_type",
    "relation",
    "parent_id",
)


def _compact_relationship(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PromptError("bd returned an invalid relationship record")
    compact = {
        key: value[key]
        for key in _RELATIONSHIP_FIELDS
        if key in value and isinstance(value[key], (str, int, float, bool, type(None)))
    }
    if not isinstance(compact.get("id"), str) or not compact["id"]:
        raise PromptError("bd returned a relationship without an id")
    return compact


def _project_relationships(bead: Mapping[str, Any], reader: BdReader) -> dict[str, Any]:
    """Keep dispatched fields intact while bounding embedded graph records."""
    projected = dict(bead)
    for relationship_name in ("dependencies", "dependents"):
        value = projected.get(relationship_name)
        if value is None:
            continue
        if not isinstance(value, list):
            raise PromptError(
                f"bd returned an invalid {relationship_name} relationship list"
            )
        projected[relationship_name] = [
            _compact_relationship(reader.show(item) if isinstance(item, str) else item)
            for item in value
        ]

    parent = projected.get("parent")
    if isinstance(parent, str) and parent:
        projected["parent"] = _compact_relationship(reader.show(parent))
    elif isinstance(parent, Mapping):
        projected["parent"] = _compact_relationship(parent)
    return projected


_DIGEST_INSTRUCTION = (
    "The bead bodies exceed the prompt budget, so each `beads` entry carries "
    "only an excerpt and a sha256 digest of `<title>\\n<description>`. Read each "
    "full body with `bd show <id> --json` and verify its digest before "
    "implementing; a mismatch means the bead changed after dispatch — stop and "
    "report it."
)


def _render_prompt(snapshot: PromptSnapshot, template: str) -> str:
    def render(payload: Mapping[str, Any], note: str) -> str:
        document = json.dumps(payload, indent=2, sort_keys=True)
        return (
            f"# Dispatch packet ({snapshot.dimensions.template_version})\n\n"
            "The following is the immutable dispatch-time snapshot. Implement every "
            "bead in this worker, run the listed verification commands, and report "
            f"once with exact results.{note}\n\n"
            "## Launch snapshot\n\n"
            f"```json\n{document}\n```\n\n"
            f"## Operating rules (`{snapshot.worker_contract_path}`)\n\n"
            f"{template}\n"
        )

    full = render(snapshot.to_dict(), "")
    if _fits(full):
        return full
    digested = {
        **snapshot.to_dict(),
        "beads": [digest_bead(bead) for bead in snapshot.beads],
        "bead_bodies": "digest",
    }
    return _bounded(render(digested, " " + _DIGEST_INSTRUCTION))


def _template(config: PromptConfig) -> tuple[str, str]:
    try:
        template = config.template_path.read_text()
    except OSError as error:
        raise PromptError(
            f"worker-contract template is unavailable: {config.template_path}"
        ) from error
    contract_path = (
        str(config.template_path.relative_to(config.project_root))
        if config.template_path.is_relative_to(config.project_root)
        else str(config.template_path)
    )
    return template, contract_path


def compile_worker_prompt(
    bead_id: str,
    *,
    project_id: str,
    reader: BdReader,
    config: PromptConfig,
    backend: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    member_ids: Sequence[str] | None = None,
    branch: str | None = None,
    batch: Mapping[str, Any] | None = None,
) -> PromptSnapshot:
    """The prompt for ``bead_id``'s group, or for ``member_ids`` led by ``bead_id``."""
    if member_ids is None:
        leader_id, bead_ids = resolve_group(bead_id, reader)
    else:
        leader_id, bead_ids = bead_id, tuple(sorted(set(member_ids)))
        if leader_id not in bead_ids:
            raise PromptError(f"leader {leader_id} is not among the members")
    beads = tuple(
        _project_relationships(reader.show(item), reader) for item in bead_ids
    )
    ordered = tuple(
        sorted(
            beads,
            key=lambda bead: (str(bead.get("id")) != leader_id, str(bead.get("id"))),
        )
    )
    dimensions = _policy_dimensions(
        ordered, config, backend=backend, model=model, effort=effort
    )
    template, contract_path = _template(config)
    branch_value = _metadata(ordered[0]).get("branch")
    if branch is None:
        branch = (
            branch_value
            if isinstance(branch_value, str) and branch_value
            else config.branch_for(leader_id)
        )
    snapshot = PromptSnapshot(
        project_id=project_id,
        leader_id=leader_id,
        bead_ids=bead_ids,
        beads=ordered,
        branch=branch,
        dimensions=dimensions,
        atlas_refs=_atlas_refs(
            config.project_root, config.atlas_dir, dimensions.affected_paths
        ),
        worker_contract_path=contract_path,
        prompt="",
        batch=dict(batch or {}),
    )
    return PromptSnapshot(
        **{**snapshot.__dict__, "prompt": _render_prompt(snapshot, template)}
    )


def resume_prompt(
    *,
    config: PromptConfig,
    bead: Mapping[str, Any],
    branch: str,
    base: str,
    worktree: Path,
    packet: str | None = None,
) -> str:
    """The prompt for a fresh agent resuming an existing worker's worktree.

    ``packet`` is the worker's original dispatch prompt; the rules and result
    contract it carries apply unchanged.
    """
    template, contract_path = _template(config)
    snapshot = json.dumps(
        {
            "bead": dict(bead),
            "branch": branch,
            "base": base,
            "worktree": str(worktree),
        },
        indent=2,
        sort_keys=True,
    )
    original = f"\n\n## Original dispatch packet\n\n{packet}" if packet else ""
    return _bounded(
        "# Resume packet\n\n"
        f"The worker below lives in `{worktree}` on `{branch}`, branched from "
        f"`{base}`. Continue its work: any uncommitted change in the worktree is "
        "yours, an unfinished merge or rebase is resolved against the bead's "
        "intent, and the result is committed on this branch. Do not push, "
        "publish, or rebase onto anything newer than the base. A conflict you "
        "cannot resolve honestly is reported, never forced to green.\n\n"
        f"```json\n{snapshot}\n```\n\n"
        f"## Operating rules (`{contract_path}`)\n\n"
        f"{template}\n"
        f"{original}"
    )


def landing_template(name: str) -> str:
    """The text of ``<name>.md`` beside this module; callers ``.format`` it."""
    return resources.files(__package__).joinpath(f"{name}.md").read_text()
