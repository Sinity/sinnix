"""Compile Beads carriers into one dispatchable agent packet."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

import tomllib

TEMPLATE_VERSION = "v2"
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


class PacketError(ValueError):
    """A packet cannot be compiled or dispatched safely."""


def resolve_project_root(project: str | None, *, cwd: Path | None = None) -> Path:
    """Resolve a project selector without asking the daemon to infer cwd."""
    current = (cwd or Path.cwd()).resolve()
    candidates: list[Path] = []
    if project:
        selected = Path(project).expanduser()
        if selected.is_dir():
            candidates.append(selected.resolve())
        candidates.extend(
            path
            for path in (
                Path("/realm/project") / project,
                Path("/realm/worktrees") / project,
            )
            if path.is_dir()
        )
    else:
        candidates.extend((current, *current.parents))
    for candidate in candidates:
        descriptor = candidate / ".agentctl" / "project.toml"
        if descriptor.is_file():
            return candidate
    selector = project or str(current)
    raise PacketError(f"could not resolve an AgentCTL project for {selector}")


def project_id_from_descriptor(root: Path) -> str:
    try:
        raw = tomllib.loads((root / ".agentctl" / "project.toml").read_text())
        project = raw["project"]
        project_id = project["id"]
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
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise PacketError(f"bd command failed in {self.root}") from error
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise PacketError("bd returned invalid JSON") from error

    def show(self, bead_id: str) -> Mapping[str, Any]:
        return _one_bead(self._run(("show", bead_id, "--json")), bead_id)

    def list(self) -> Sequence[Mapping[str, Any]]:
        value = self._run(("list", "--all", "--json"))
        if not isinstance(value, list) or any(
            not isinstance(item, Mapping) for item in value
        ):
            raise PacketError("bd list returned an invalid bead list")
        return value

    def ready(self) -> Sequence[Mapping[str, Any]]:
        value = self._run(("ready", "--json"))
        if not isinstance(value, list) or any(
            not isinstance(item, Mapping) for item in value
        ):
            raise PacketError("bd ready returned an invalid bead list")
        return value


def _one_bead(value: Any, bead_id: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
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


@dataclass(frozen=True)
class PacketConfig:
    template_path: Path
    atlas_dir: Path
    project_root: Path | None = None
    envelope_aggregates: Path | None = None
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
            raise PacketError(
                f"could not read project descriptor {descriptor}"
            ) from error
        packets = raw.get("packets", {})
        if not isinstance(packets, Mapping):
            raise PacketError("[packets] must be a table")
        defaults = packets.get("defaults", {})
        if not isinstance(defaults, Mapping):
            raise PacketError("[packets.defaults] must be a table")

        def path_value(name: str, fallback: str) -> Path:
            aliases = {"template": "template_path"}
            value = packets.get(name, packets.get(aliases.get(name, ""), fallback))
            if not isinstance(value, str) or not value:
                raise PacketError(f"packets.{name} must be a non-empty path")
            path = Path(value)
            if path.is_absolute():
                return path
            local = root / path
            if local.exists() or name != "template":
                return local
            shared = Path("/realm/project/sinnix") / path
            return shared if shared.exists() else local

        def string_value(name: str, fallback: str) -> str:
            value = packets.get(name, fallback)
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

        aggregate_value = packets.get("envelope_aggregates")
        aggregates = None
        if aggregate_value is not None:
            if not isinstance(aggregate_value, str) or not aggregate_value:
                raise PacketError("packets.envelope_aggregates must be a path")
            aggregates = Path(aggregate_value)
            if not aggregates.is_absolute():
                aggregates = root / aggregates
        return cls(
            template_path=path_value("template", DEFAULT_TEMPLATE_RELATIVE_PATH),
            atlas_dir=path_value("atlas_dir", DEFAULT_ATLAS_RELATIVE_PATH),
            project_root=root,
            envelope_aggregates=aggregates,
            template_version=string_value("template_version", TEMPLATE_VERSION),
            branch_prefix=string_value("branch_prefix", "feature/packet"),
            default_backend=string_value(
                "backend", defaults.get("backend", DEFAULT_BACKEND)
            ),
            default_model=string_value("model", defaults.get("model", DEFAULT_MODEL)),
            default_effort=string_value(
                "effort", defaults.get("effort", DEFAULT_EFFORT)
            ),
            policy_map=policy_map,
        )


@dataclass(frozen=True)
class PacketDimensions:
    template_version: str
    backend: str
    model: str
    effort: str
    model_policy: str
    verification_commands: tuple[str, ...]
    conflict_keys: tuple[str, ...]
    affected_paths: tuple[str, ...]
    packet_intent: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_version": self.template_version,
            "backend": self.backend,
            "model": self.model,
            "effort": self.effort,
            "model_policy": self.model_policy,
            "verification_commands": list(self.verification_commands),
            "conflict_keys": list(self.conflict_keys),
            "affected_paths": list(self.affected_paths),
            "packet_intent": list(self.packet_intent),
        }


@dataclass(frozen=True)
class PacketSnapshot:
    project_id: str
    leader_id: str
    bead_ids: tuple[str, ...]
    beads: tuple[Mapping[str, Any], ...]
    group: str
    dimensions: PacketDimensions
    atlas_refs: tuple[str, ...]
    worker_contract_residue: str
    prompt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "template_version": self.dimensions.template_version,
            "project_id": self.project_id,
            "leader_id": self.leader_id,
            "bead_ids": list(self.bead_ids),
            "group": self.group,
            "beads": [dict(bead) for bead in self.beads],
            "dimensions": self.dimensions.to_dict(),
            "atlas_refs": list(self.atlas_refs),
            "worker_contract_residue": self.worker_contract_residue,
        }


def resolve_group(bead_id: str, reader: BdReader) -> tuple[str, tuple[str, ...]]:
    seed = reader.show(bead_id)
    seed_metadata = _metadata(seed)
    group = seed_metadata.get("dispatch_group")
    leader_id = group if isinstance(group, str) and group else bead_id
    rows = reader.list()
    member_ids = {
        row.get("id")
        for row in rows
        if isinstance(row.get("id"), str)
        and _metadata(row).get("dispatch_group") == leader_id
    }
    member_ids.add(leader_id)
    member_ids.add(bead_id)
    if not all(isinstance(item, str) and item for item in member_ids):
        raise PacketError("dispatch group contains an invalid bead id")
    return leader_id, tuple(sorted(member_ids))


def _policy_dimensions(
    beads: Sequence[Mapping[str, Any]], config: PacketConfig
) -> PacketDimensions:
    leader_metadata = _metadata(beads[0])
    policy = leader_metadata.get("model_policy", "")
    policy_name = policy if isinstance(policy, str) and policy else "default"
    backend, model = config.policy_map.get(
        policy_name, (config.default_backend, config.default_model)
    )
    effort = leader_metadata.get("effort", config.default_effort)
    if not isinstance(effort, str) or not effort:
        effort = config.default_effort

    def values(name: str) -> tuple[str, ...]:
        result: set[str] = set()
        for bead in beads:
            value = _metadata(bead).get(name)
            if isinstance(value, str):
                result.update(item.strip() for item in value.split(";") if item.strip())
            elif isinstance(value, list):
                result.update(item for item in value if isinstance(item, str) and item)
        return tuple(sorted(result))

    intents = tuple(
        intent
        for bead in beads
        for intent in [_metadata(bead).get("packet_intent")]
        if isinstance(intent, str) and intent
    )
    return PacketDimensions(
        template_version=config.template_version,
        backend=backend,
        model=model,
        effort=effort,
        model_policy=policy_name,
        verification_commands=values("verification_commands"),
        conflict_keys=values("conflict_keys"),
        affected_paths=values("affected_paths"),
        packet_intent=intents,
    )


def _atlas_refs(
    root: Path, atlas_dir: Path, affected_paths: Sequence[str]
) -> tuple[str, ...]:
    if not atlas_dir.is_dir():
        return ()
    tokens = {Path(path).parts[0] for path in affected_paths if Path(path).parts}
    sheets = sorted(atlas_dir.glob("*.md"))
    relevant = [sheet for sheet in sheets if sheet.stem in tokens]
    if not relevant:
        relevant = sheets
    return tuple(str(sheet.relative_to(root)) for sheet in relevant)


def _safe_name(value: str) -> str:
    cleaned = _SAFE_NAME.sub("-", value).strip("-./")
    return cleaned or "packet"


def _render_prompt(snapshot: PacketSnapshot, template: str) -> str:
    payload = json.dumps(snapshot.to_dict(), indent=2, sort_keys=True)
    prompt = (
        f"# Dispatch packet ({snapshot.dimensions.template_version})\n\n"
        "The following is the immutable dispatch-time snapshot. Implement every bead in this lane, "
        "run the listed verification commands, and report once with exact results.\n\n"
        "## Launch snapshot\n\n"
        f"```json\n{payload}\n```\n\n"
        "## Worker-contract residue\n\n"
        f"The residue is defined by `{snapshot.worker_contract_residue}`.\n\n"
        f"{template}\n"
    )
    if len(prompt.encode()) > 200_000:
        raise PacketError("compiled packet prompt exceeds the agent prompt limit")
    return prompt


def compile_launch_snapshot(
    bead_id: str,
    *,
    project_root: Path,
    project_id: str,
    reader: BdReader,
    config: PacketConfig | None = None,
) -> PacketSnapshot:
    config = config or PacketConfig.load(project_root)
    leader_id, bead_ids = resolve_group(bead_id, reader)
    beads = tuple(reader.show(item) for item in bead_ids)
    ordered = tuple(
        sorted(
            beads,
            key=lambda bead: (str(bead.get("id")) != leader_id, str(bead.get("id"))),
        )
    )
    dimensions = _policy_dimensions(ordered, config)
    atlas_refs = _atlas_refs(project_root, config.atlas_dir, dimensions.affected_paths)
    try:
        template = config.template_path.read_text()
    except OSError as error:
        raise PacketError(
            f"worker-contract template is unavailable: {config.template_path}"
        ) from error
    residue = (
        str(config.template_path.relative_to(project_root))
        if config.template_path.is_relative_to(project_root)
        else str(config.template_path)
    )
    snapshot = PacketSnapshot(
        project_id=project_id,
        leader_id=leader_id,
        bead_ids=bead_ids,
        beads=ordered,
        group=leader_id,
        dimensions=dimensions,
        atlas_refs=atlas_refs,
        worker_contract_residue=residue,
        prompt="",
    )
    return PacketSnapshot(
        **{**snapshot.__dict__, "prompt": _render_prompt(snapshot, template)}
    )


def derived_workspace(
    snapshot: PacketSnapshot, config: PacketConfig
) -> tuple[str, str]:
    name = f"packet-{_safe_name(snapshot.leader_id)}"
    leader = snapshot.beads[0]
    branch_value = _metadata(leader).get("branch")
    branch = (
        branch_value
        if isinstance(branch_value, str) and branch_value
        else f"{config.branch_prefix}/{_safe_name(snapshot.leader_id)}"
    )
    return name, branch


def checkout_id_from_workspace_response(response: Mapping[str, Any]) -> str:
    payload = response.get("payload")
    value = payload.get("value") if isinstance(payload, Mapping) else None
    checkout_id = value.get("checkout_id") if isinstance(value, Mapping) else None
    if not isinstance(checkout_id, str) or not checkout_id:
        raise PacketError("workspace.create did not return CHECKOUT_ID")
    return checkout_id


def load_envelope_aggregate(
    config: PacketConfig, snapshot: PacketSnapshot
) -> Mapping[str, Any] | None:
    path = config.envelope_aggregates
    if path is None:
        candidate = (
            config.project_root / ".agentctl" / "envelope-aggregates.json"
            if config.project_root is not None
            else Path(".agentctl/envelope-aggregates.json")
        )
        path = candidate if candidate.is_file() else None
    if path is None or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, Mapping):
        return None
    keys = (
        f"{snapshot.dimensions.backend}/{snapshot.dimensions.model}/{snapshot.dimensions.effort}",
        snapshot.dimensions.model,
        snapshot.leader_id,
    )
    for key in keys:
        aggregate = value.get(key)
        if isinstance(aggregate, Mapping):
            return aggregate
    aggregates = value.get("aggregates")
    if isinstance(aggregates, Mapping):
        for key in keys:
            aggregate = aggregates.get(key)
            if isinstance(aggregate, Mapping):
                return aggregate
    return None


def plan_row(snapshot: PacketSnapshot, config: PacketConfig) -> dict[str, Any]:
    aggregate = load_envelope_aggregate(config, snapshot) or {}
    return {
        "beads": ",".join(snapshot.bead_ids),
        "group": snapshot.group,
        "model": snapshot.dimensions.model,
        "effort": snapshot.dimensions.effort,
        "conflict_keys": ",".join(snapshot.dimensions.conflict_keys) or "-",
        "predicted_duration": aggregate.get("duration_seconds", "?"),
        "predicted_rss": aggregate.get("rss_bytes", "?"),
    }


def plan_table(snapshot: PacketSnapshot, config: PacketConfig) -> str:
    row = plan_row(snapshot, config)
    headers = (
        "BEADS",
        "GROUP",
        "MODEL/EFFORT",
        "CONFLICT KEYS",
        "PREDICTED DURATION",
        "PREDICTED RSS",
    )
    values = (
        row["beads"],
        row["group"],
        f"{row['model']}/{row['effort']}",
        row["conflict_keys"],
        str(row["predicted_duration"]),
        str(row["predicted_rss"]),
    )
    widths = [
        max(len(header), len(str(value)))
        for header, value in zip(headers, values, strict=True)
    ]
    line = "  ".join(
        header.ljust(width) for header, width in zip(headers, widths, strict=True)
    )
    separator = "  ".join("-" * width for width in widths)
    return (
        f"{line}\n{separator}\n"
        f"{'  '.join(str(value).ljust(width) for value, width in zip(values, widths, strict=True))}"
    )
