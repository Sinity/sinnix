"""Compile a bead (and its dispatch group) into one agent prompt.

No external tool does this: Beads holds the task text, the repository holds
the worker contract and atlas sheets, and the prompt is the join.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

import tomllib

TEMPLATE_VERSION = "v2"
MAX_PROMPT_BYTES = 200_000
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
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._/-]+")
_SUBJECT_PREFIXES = {"bug": "fix", "feature": "feat"}


class PacketError(ValueError):
    """A packet cannot be compiled or dispatched safely."""


def project_id_from_descriptor(root: Path) -> str:
    try:
        raw = tomllib.loads((root / ".agentctl" / "project.toml").read_text())
        project_id = raw["project"]["id"]
    except (KeyError, OSError, TypeError, tomllib.TOMLDecodeError) as error:
        raise PacketError(f"project descriptor is invalid: {root}") from error
    if not isinstance(project_id, str) or not project_id:
        raise PacketError(f"project descriptor has no project.id: {root}")
    return project_id


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
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise PacketError(f"bd {' '.join(arguments)} failed in {self.root}") from error
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise PacketError("bd returned invalid JSON") from error

    def show(self, bead_id: str) -> Mapping[str, Any]:
        return _one_bead(self._run(("show", bead_id, "--json")), bead_id)

    def list(self) -> Sequence[Mapping[str, Any]]:
        return _bead_list(self._run(("list", "--all", "--limit", "0", "--json")), "list")

    def ready(self) -> Sequence[Mapping[str, Any]]:
        return _bead_list(self._run(("ready", "--limit", "0", "--json")), "ready")


def _bead_list(value: Any, what: str) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise PacketError(f"bd {what} returned an invalid bead list")
    return value


def _one_bead(value: Any, bead_id: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping) and "error" not in value:
        bead = value
    elif isinstance(value, list) and len(value) == 1 and isinstance(value[0], Mapping):
        bead = value[0]
    else:
        raise PacketError(f"bd show {bead_id} returned an invalid bead")
    if bead.get("id") != bead_id:
        raise PacketError(f"bd show {bead_id} returned the wrong bead")
    return bead


def _metadata(bead: Mapping[str, Any]) -> Mapping[str, Any]:
    value = bead.get("metadata", {})
    return value if isinstance(value, Mapping) else {}


def bead_subject(bead: Mapping[str, Any]) -> str:
    """The PR title: the bead title behind its type prefix, within the subject limit."""
    kind = str(bead.get("issue_type") or bead.get("type") or "").lower()
    prefix = _SUBJECT_PREFIXES.get(kind, "chore")
    title = " ".join(str(bead.get("title") or "").split())
    if re.match(r"^(fix|feat|chore|refactor|docs|test|perf|build|ci)(\([^)]*\))?!?:", title):
        subject = title
    else:
        subject = f"{prefix}: {title}" if title else prefix
    if len(subject) > MAX_SUBJECT_LENGTH:
        subject = subject[: MAX_SUBJECT_LENGTH - 1].rstrip() + "…"
    return subject


@dataclass(frozen=True)
class PacketConfig:
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
    def load(cls, root: Path) -> PacketConfig:
        descriptor = root / ".agentctl" / "project.toml"
        try:
            raw = tomllib.loads(descriptor.read_text())
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise PacketError(f"could not read project descriptor {descriptor}") from error
        packets = raw.get("packets", {})
        if not isinstance(packets, Mapping):
            raise PacketError("[packets] must be a table")
        defaults = packets.get("defaults", {})
        if not isinstance(defaults, Mapping):
            raise PacketError("[packets.defaults] must be a table")

        def path_value(name: str, fallback: str) -> Path:
            value = packets.get(name, fallback)
            if not isinstance(value, str) or not value:
                raise PacketError(f"packets.{name} must be a non-empty path")
            path = Path(value)
            if path.is_absolute():
                return path
            local = root / path
            if local.exists() or name != "template":
                return local
            # The worker contract lives in sinnix; other projects reference it
            # by the same relative path.
            shared = Path("/realm/project/sinnix") / path
            return shared if shared.exists() else local

        def string_value(name: str, fallback: str) -> str:
            value = packets.get(name, defaults.get(name, fallback))
            if not isinstance(value, str) or not value:
                raise PacketError(f"packets.{name} must be a non-empty string")
            return value

        raw_map = packets.get("model_policy", {})
        if not isinstance(raw_map, Mapping):
            raise PacketError("packets.model_policy must be a table")
        policy_map = dict(DEFAULT_POLICY_MAP)
        for policy, value in raw_map.items():
            if not isinstance(policy, str) or not isinstance(value, Mapping):
                raise PacketError("packets.model_policy entries must be tables")
            backend = value.get("backend")
            model = value.get("model")
            if not isinstance(backend, str) or not isinstance(model, str):
                raise PacketError("packets.model_policy entries need backend and model")
            policy_map[policy] = (backend, model)
        return cls(
            template_path=path_value("template", DEFAULT_TEMPLATE_RELATIVE_PATH),
            atlas_dir=path_value("atlas_dir", DEFAULT_ATLAS_RELATIVE_PATH),
            project_root=root,
            template_version=string_value("template_version", TEMPLATE_VERSION),
            branch_prefix=string_value("branch_prefix", "feature/packet"),
            default_backend=string_value("backend", DEFAULT_BACKEND),
            default_model=string_value("model", DEFAULT_MODEL),
            default_effort=string_value("effort", DEFAULT_EFFORT),
            policy_map=policy_map,
        )

    def branch_for(self, bead_id: str) -> str:
        return f"{self.branch_prefix}/{_safe_name(bead_id)}"


@dataclass(frozen=True)
class PacketDimensions:
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
class PacketSnapshot:
    project_id: str
    leader_id: str
    bead_ids: tuple[str, ...]
    beads: tuple[Mapping[str, Any], ...]
    branch: str
    dimensions: PacketDimensions
    atlas_refs: tuple[str, ...]
    worker_contract_path: str
    prompt: str

    def to_dict(self) -> dict[str, Any]:
        return {
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


def resolve_group(bead_id: str, reader: BdReader) -> tuple[str, tuple[str, ...]]:
    seed = reader.show(bead_id)
    group = _metadata(seed).get("dispatch_group")
    leader_id = group if isinstance(group, str) and group else bead_id
    member_ids = {
        row.get("id")
        for row in reader.list()
        if isinstance(row.get("id"), str)
        and _metadata(row).get("dispatch_group") == leader_id
        # A dispatch group is co-executed OPEN work; closed members are done
        # and their specs must not be reissued as instructions.
        and row.get("status") not in {"closed", "deferred"}
    }
    member_ids.add(leader_id)
    member_ids.add(bead_id)
    if not all(isinstance(item, str) and item for item in member_ids):
        raise PacketError("dispatch group contains an invalid bead id")
    return leader_id, tuple(sorted(member_ids))


def _policy_dimensions(
    beads: Sequence[Mapping[str, Any]],
    config: PacketConfig,
    *,
    backend: str | None,
    model: str | None,
    effort: str | None,
) -> PacketDimensions:
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

    return PacketDimensions(
        template_version=config.template_version,
        backend=backend or policy_backend,
        model=model or policy_model,
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
        raise PacketError(
            f"compiled prompt is {len(prompt.encode())} bytes, over the "
            f"{MAX_PROMPT_BYTES}-byte budget"
        )
    return prompt


def _render_prompt(snapshot: PacketSnapshot, template: str) -> str:
    payload = json.dumps(snapshot.to_dict(), indent=2, sort_keys=True)
    return _bounded(
        f"# Dispatch packet ({snapshot.dimensions.template_version})\n\n"
        "The following is the immutable dispatch-time snapshot. Implement every "
        "bead in this lane, run the listed verification commands, and report "
        "once with exact results.\n\n"
        "## Launch snapshot\n\n"
        f"```json\n{payload}\n```\n\n"
        f"## Operating rules (`{snapshot.worker_contract_path}`)\n\n"
        f"{template}\n"
    )


def _template(config: PacketConfig) -> tuple[str, str]:
    try:
        template = config.template_path.read_text()
    except OSError as error:
        raise PacketError(
            f"worker-contract template is unavailable: {config.template_path}"
        ) from error
    contract_path = (
        str(config.template_path.relative_to(config.project_root))
        if config.template_path.is_relative_to(config.project_root)
        else str(config.template_path)
    )
    return template, contract_path


def compile_launch_snapshot(
    bead_id: str,
    *,
    project_id: str,
    reader: BdReader,
    config: PacketConfig,
    backend: str | None = None,
    model: str | None = None,
    effort: str | None = None,
) -> PacketSnapshot:
    leader_id, bead_ids = resolve_group(bead_id, reader)
    beads = tuple(reader.show(item) for item in bead_ids)
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
    branch = (
        branch_value
        if isinstance(branch_value, str) and branch_value
        else config.branch_for(leader_id)
    )
    snapshot = PacketSnapshot(
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
    )
    return PacketSnapshot(**{**snapshot.__dict__, "prompt": _render_prompt(snapshot, template)})


def rebase_prompt(
    *,
    config: PacketConfig,
    bead: Mapping[str, Any],
    branch: str,
    base: str,
    worktree: Path,
) -> str:
    """The prompt for an agent that brings an existing lane back onto its base."""
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
    return _bounded(
        "# Rebase packet\n\n"
        f"The lane below lives in `{worktree}` on `{branch}`. Fetch, rebase it "
        f"onto `{base}`, resolve every conflict against the bead's intent, run "
        "the quick gate in the rebased state, and push with `--force-with-lease`. "
        "Any uncommitted work in the worktree is yours. A conflict you cannot "
        "resolve honestly is reported, never forced to green.\n\n"
        f"```json\n{snapshot}\n```\n\n"
        f"## Operating rules (`{contract_path}`)\n\n"
        f"{template}\n"
    )
