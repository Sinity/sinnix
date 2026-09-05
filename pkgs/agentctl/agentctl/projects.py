"""Project descriptors: the one thing agentctl owns outright.

A descriptor (`.agentctl/project.toml`) declares what a project's operations
mean — argv, pool, result contract, timeout, checkout policy, schedule — and
how to enter its environment. Everything else (queueing, worktrees, review,
tasks) belongs to pueue, worktrunk, GitHub and Beads.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import tomllib

from .environment import build_environment
from .limits import (
    AGENT_MEMORY_MAX,
    DECLARABLE_RESULT_KINDS,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_DECLARED_OPERATION_TIMEOUT_SECONDS,
    valid_timeout_seconds,
)


class ProjectConfigError(ValueError):
    """The descriptor is missing or violates the schema-1 contract."""


# pueue's group name grammar; the value passes through as the pueue group.
_POOL_NAME = re.compile(r"[a-z][a-z0-9-]{0,63}")
_ENVIRONMENT_NAME = re.compile(r"[A-Z_][A-Z0-9_]*\Z")
MAX_OPERATION_SCHEDULE_LENGTH = 256
CACHE_KINDS = frozenset({"none", "tree+environment"})

_TABLES = frozenset(
    {"schema", "project", "environment", "workspace", "packets", "operations"}
)
_ENVIRONMENT_FIELDS = frozenset(
    {"kind", "command", "inherit", "unset", "values", "require"}
)
_WORKSPACE_FIELDS = frozenset(
    {
        "root",
        "default_base",
        "agent_memory_max",
        "verify",
        "publish",
    }
)
# `[workspace].verify` names one operation per profile; `candidate` may be
# `hosted:<check>` for a project whose candidate verification is a required
# PR check.
_VERIFY_PROFILES = frozenset({"focused", "candidate", "corpus"})
PUBLISH_POLICIES = frozenset({"pr", "master"})
# systemd's size grammar for MemoryMax: an integer with an optional K/M/G/T
# suffix.
_MEMORY_SIZE = re.compile(r"[1-9][0-9]*[KMGT]?\Z")
# `[packets]`: how a worker prompt is compiled. `backend`, `model` and
# `effort` may sit in the table or under `[packets.defaults]`;
# `[packets.review]` names the reviewer's and integrator's agent.
_PACKETS_FIELDS = frozenset(
    {
        "template",
        "atlas_dir",
        "branch_prefix",
        "template_version",
        "model_policy",
        "defaults",
        "review",
        "backend",
        "model",
        "effort",
    }
)
_PACKETS_DEFAULTS = ("backend", "model", "effort", "template_version", "branch_prefix")
_PACKETS_REVIEW = ("backend", "model", "effort")
_OPERATION_FIELDS = frozenset(
    {
        "description",
        "exec",
        "pool",
        "result",
        "timeout_seconds",
        "schedule",
        "checkout",
        "cache",
        "dependencies",
    }
)


class ProjectEnvironmentError(ProjectConfigError):
    """A declared-required environment variable is absent at launch."""


@dataclass(frozen=True)
class ProjectEnvironment:
    kind: str
    command: tuple[str, ...]
    inherit: tuple[str, ...]
    unset: tuple[str, ...]
    declared: tuple[tuple[str, str], ...] = ()
    require: tuple[str, ...] = ()

    def values(self) -> dict[str, str]:
        """Resolve the launch environment; a missing required variable fails loudly.

        Inherited names absent from the caller's environment are dropped
        silently; ``require`` names the ones whose absence is a defect.
        """
        environment = build_environment(
            inherit=self.inherit, unset=self.unset, values=dict(self.declared)
        )
        missing = sorted(name for name in self.require if name not in environment)
        if missing:
            raise ProjectEnvironmentError(
                "required environment variable(s) unavailable: "
                + ", ".join(missing)
                + " (declare a value under [environment.values] or export them)"
            )
        return environment

    def command_for(self, payload: Sequence[str]) -> tuple[str, ...]:
        """Enter the project environment around ``payload``."""
        return (*self.command, *payload)

    def catalog_row(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "command": list(self.command),
            "declared": sorted(name for name, _value in self.declared),
            "require": list(self.require),
        }


@dataclass(frozen=True)
class WorkspacePolicy:
    root: Path
    default_base: str
    # The hard MemoryMax of one agent's scope; the descriptor's only say in
    # an agent's resources.
    agent_memory_max: str = AGENT_MEMORY_MAX
    # Profile name -> operation name, or `hosted:<check>` for `candidate`.
    verify: Mapping[str, str] = field(default_factory=dict)
    # How a landed candidate reaches the default branch: a squash-merged PR
    # or a fast-forward push.
    publish: str = "pr"

    @property
    def base_branch(self) -> str:
        base = self.default_base
        return base.split("/", 1)[1] if base.startswith("origin/") else base

    def catalog_row(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "default_base": self.default_base,
            "agent_memory_max": self.agent_memory_max,
            "verify": dict(self.verify),
            "publish": self.publish,
        }


@dataclass(frozen=True)
class PacketsPolicy:
    """The descriptor's `[packets]`; None or empty means the compiler's default."""

    template: Path | None = None
    atlas_dir: Path | None = None
    branch_prefix: str | None = None
    template_version: str | None = None
    backend: str | None = None
    model: str | None = None
    effort: str | None = None
    # Policy name -> (backend, model), from `[packets.model_policy.<name>]`.
    model_policy: Mapping[str, tuple[str, str]] = field(default_factory=dict)
    # `[packets.review]`: backend, model, effort of the reviewer and the
    # integration agent; None means the leader worker's.
    review: Mapping[str, str] | None = None


@dataclass(frozen=True)
class ProjectOperation:
    name: str
    description: str
    command: tuple[str, ...]
    pool: str = "normal"
    result: str = "exit"
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    schedule: str | None = None
    # "default": the operation runs only on the project's main checkout.
    checkout: str = "any"
    cache: str = "none"
    dependencies: tuple[str, ...] = ()

    def catalog_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "command": list(self.command),
            "pool": self.pool,
            "result": self.result,
            "timeout_seconds": self.timeout_seconds,
            "schedule": self.schedule,
            "checkout": self.checkout,
            "cache": self.cache,
            "dependencies": list(self.dependencies),
        }


@dataclass(frozen=True)
class ProjectAdapter:
    project_id: str
    display_name: str
    root: Path
    descriptor: Path
    digest: str
    environment: ProjectEnvironment
    workspace: WorkspacePolicy | None
    operations: tuple[ProjectOperation, ...]
    packets: PacketsPolicy = field(default_factory=PacketsPolicy)

    @property
    def agent_capable(self) -> bool:
        return self.workspace is not None

    def operation(self, name: str) -> ProjectOperation:
        for operation in self.operations:
            if operation.name == name:
                return operation
        raise KeyError(f"unknown project operation: {self.project_id}.{name}")

    def catalog_row(self) -> dict[str, Any]:
        return {
            "id": self.project_id,
            "display_name": self.display_name,
            "root": str(self.root),
            "descriptor": str(self.descriptor),
            "digest": self.digest,
            "environment": self.environment.catalog_row(),
            "workspace": self.workspace.catalog_row() if self.workspace else None,
            "operations": [operation.catalog_row() for operation in self.operations],
        }


def _string_list(value: Any, field: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise ProjectConfigError(
            f"{field} must be a non-empty list of non-empty strings"
        )
    return tuple(value)


def _optional_string_list(value: Any, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ProjectConfigError(f"{field} must be a list of non-empty strings")
    return tuple(value)


def _environment(raw: Mapping[str, Any], descriptor: Path) -> ProjectEnvironment:
    environment = raw.get("environment")
    if not isinstance(environment, Mapping):
        raise ProjectConfigError(f"{descriptor} requires an [environment] table")
    unknown = set(environment) - _ENVIRONMENT_FIELDS
    if unknown:
        raise ProjectConfigError(
            f"{descriptor} [environment] contains unknown fields: "
            + ", ".join(sorted(unknown))
        )
    kind = environment.get("kind")
    if not isinstance(kind, str) or not kind:
        raise ProjectConfigError(f"{descriptor} environment.kind must be non-empty")
    declared_values = environment.get("values", {})
    if not isinstance(declared_values, Mapping) or any(
        not isinstance(name, str)
        or _ENVIRONMENT_NAME.fullmatch(name) is None
        or name.startswith("SINNIX")
        or not isinstance(value, str)
        for name, value in declared_values.items()
    ):
        raise ProjectConfigError(
            f"{descriptor} [environment.values] must map uppercase non-SINNIX"
            " variable names to strings"
        )
    required = _optional_string_list(environment.get("require"), "environment.require")
    if any(
        _ENVIRONMENT_NAME.fullmatch(name) is None or name.startswith("SINNIX")
        for name in required
    ):
        raise ProjectConfigError(
            f"{descriptor} environment.require must name uppercase non-SINNIX variables"
        )
    return ProjectEnvironment(
        kind=kind,
        command=_string_list(environment.get("command"), "environment.command"),
        inherit=_optional_string_list(
            environment.get("inherit"), "environment.inherit"
        ),
        unset=_optional_string_list(environment.get("unset"), "environment.unset"),
        declared=tuple(sorted(declared_values.items())),
        require=required,
    )


def _workspace(raw: Mapping[str, Any], descriptor: Path) -> WorkspacePolicy | None:
    raw_workspace = raw.get("workspace")
    if raw_workspace is None:
        return None
    if not isinstance(raw_workspace, Mapping):
        raise ProjectConfigError(f"{descriptor} [workspace] must be a table")
    unknown = set(raw_workspace) - _WORKSPACE_FIELDS
    if unknown:
        raise ProjectConfigError(
            f"{descriptor} [workspace] contains unknown fields: "
            + ", ".join(sorted(unknown))
        )
    root = raw_workspace.get("root")
    default_base = raw_workspace.get("default_base")
    if not isinstance(root, str) or not Path(root).is_absolute():
        raise ProjectConfigError(
            f"{descriptor} workspace.root must be an absolute path"
        )
    if not isinstance(default_base, str) or not default_base:
        raise ProjectConfigError(
            f"{descriptor} workspace.default_base must be non-empty"
        )
    fields: dict[str, Any] = {}
    if "agent_memory_max" in raw_workspace:
        memory_max = raw_workspace["agent_memory_max"]
        if (
            not isinstance(memory_max, str)
            or _MEMORY_SIZE.fullmatch(memory_max) is None
        ):
            raise ProjectConfigError(
                f"{descriptor} workspace.agent_memory_max must be a systemd size such as 10G"
            )
        fields["agent_memory_max"] = memory_max
    if "verify" in raw_workspace:
        raw_verify = raw_workspace["verify"]
        if (
            not isinstance(raw_verify, Mapping)
            or set(raw_verify) - _VERIFY_PROFILES
            or any(
                not isinstance(value, str) or not value for value in raw_verify.values()
            )
        ):
            raise ProjectConfigError(
                f"{descriptor} workspace.verify must map focused/candidate/corpus to operation names"
            )
        fields["verify"] = dict(raw_verify)
    if "publish" in raw_workspace:
        if raw_workspace["publish"] not in PUBLISH_POLICIES:
            raise ProjectConfigError(
                f"{descriptor} workspace.publish must be one of {sorted(PUBLISH_POLICIES)}"
            )
        fields["publish"] = raw_workspace["publish"]
    return WorkspacePolicy(root=Path(root), default_base=default_base, **fields)


def _packets(raw: Mapping[str, Any], root: Path, descriptor: Path) -> PacketsPolicy:
    packets = raw.get("packets", {})
    if not isinstance(packets, Mapping):
        raise ProjectConfigError(f"{descriptor} [packets] must be a table")
    unknown = set(packets) - _PACKETS_FIELDS
    if unknown:
        raise ProjectConfigError(
            f"{descriptor} [packets] contains unknown fields: "
            + ", ".join(sorted(unknown))
        )
    defaults = packets.get("defaults", {})
    if not isinstance(defaults, Mapping) or set(defaults) - set(_PACKETS_DEFAULTS):
        raise ProjectConfigError(
            f"{descriptor} [packets.defaults] may set only "
            + ", ".join(_PACKETS_DEFAULTS)
        )
    fields: dict[str, Any] = {}
    for name in ("template", "atlas_dir"):
        if name in packets:
            value = packets[name]
            if not isinstance(value, str) or not value:
                raise ProjectConfigError(
                    f"{descriptor} packets.{name} must be a non-empty path"
                )
            path = Path(value)
            fields[name] = path if path.is_absolute() else root / path
    for name in _PACKETS_DEFAULTS:
        value = packets.get(name, defaults.get(name))
        if value is None:
            continue
        if not isinstance(value, str) or not value:
            raise ProjectConfigError(
                f"{descriptor} packets.{name} must be a non-empty string"
            )
        fields[name] = value
    raw_review = packets.get("review")
    if raw_review is not None:
        if (
            not isinstance(raw_review, Mapping)
            or set(raw_review) != set(_PACKETS_REVIEW)
            or any(
                not isinstance(value, str) or not value for value in raw_review.values()
            )
        ):
            raise ProjectConfigError(
                f"{descriptor} [packets.review] must set exactly "
                + ", ".join(_PACKETS_REVIEW)
            )
        fields["review"] = dict(raw_review)
    raw_map = packets.get("model_policy", {})
    if not isinstance(raw_map, Mapping):
        raise ProjectConfigError(f"{descriptor} packets.model_policy must be a table")
    policy_map: dict[str, tuple[str, str]] = {}
    for policy, value in raw_map.items():
        backend = value.get("backend") if isinstance(value, Mapping) else None
        model = value.get("model") if isinstance(value, Mapping) else None
        if not isinstance(backend, str) or not isinstance(model, str):
            raise ProjectConfigError(
                f"{descriptor} packets.model_policy entries need backend and model"
            )
        policy_map[str(policy)] = (backend, model)
    return PacketsPolicy(model_policy=policy_map, **fields)


def _operation(name: str, definition: Any, descriptor: Path) -> ProjectOperation:
    if not name.isidentifier() or not isinstance(definition, Mapping):
        raise ProjectConfigError(
            f"{descriptor} contains an invalid operation declaration: {name}"
        )
    unknown = set(definition) - _OPERATION_FIELDS
    if unknown:
        raise ProjectConfigError(
            f"{descriptor} operation {name} contains unknown fields: "
            + ", ".join(sorted(unknown))
        )
    description = definition.get("description")
    if not isinstance(description, str) or not description:
        raise ProjectConfigError(f"{descriptor} operation {name} requires description")
    command = _string_list(definition.get("exec"), f"operations.{name}.exec")
    fields: dict[str, Any] = {}
    if "pool" in definition:
        pool = definition["pool"]
        if not isinstance(pool, str) or not _POOL_NAME.fullmatch(pool):
            raise ProjectConfigError(f"operations.{name}.pool is invalid")
        fields["pool"] = pool
    if "result" in definition:
        if definition["result"] not in DECLARABLE_RESULT_KINDS:
            raise ProjectConfigError(f"operations.{name}.result is invalid")
        fields["result"] = definition["result"]
    if "timeout_seconds" in definition:
        timeout_seconds = definition["timeout_seconds"]
        if not valid_timeout_seconds(timeout_seconds, kind="declared-operation"):
            raise ProjectConfigError(
                f"operations.{name}.timeout_seconds must be between 1 and "
                f"{MAX_DECLARED_OPERATION_TIMEOUT_SECONDS}"
            )
        fields["timeout_seconds"] = timeout_seconds
    if "checkout" in definition:
        if definition["checkout"] not in {"any", "default"}:
            raise ProjectConfigError(f"operations.{name}.checkout is invalid")
        fields["checkout"] = definition["checkout"]
    schedule = definition.get("schedule")
    if schedule is not None and (
        not isinstance(schedule, str)
        or not schedule
        or len(schedule) > MAX_OPERATION_SCHEDULE_LENGTH
        or any(
            ord(character) < 0x20 or ord(character) == 0x7F for character in schedule
        )
    ):
        raise ProjectConfigError(
            f"operations.{name}.schedule must be a non-empty OnCalendar expression"
        )
    if "cache" in definition:
        if definition["cache"] not in CACHE_KINDS:
            raise ProjectConfigError(f"operations.{name}.cache is invalid")
        fields["cache"] = definition["cache"]
    dependencies = _optional_string_list(
        definition.get("dependencies"), f"operations.{name}.dependencies"
    )
    if name in dependencies or len(set(dependencies)) != len(dependencies):
        raise ProjectConfigError(f"operations.{name}.dependencies is invalid")
    return ProjectOperation(
        name=name,
        description=description,
        command=command,
        schedule=schedule,
        dependencies=dependencies,
        **fields,
    )


def load_project_adapter(root: Path) -> ProjectAdapter:
    root = root.resolve()
    descriptor = root / ".agentctl" / "project.toml"
    try:
        raw_bytes = descriptor.read_bytes()
    except FileNotFoundError as error:
        raise ProjectConfigError(f"project adapter is missing: {descriptor}") from error
    try:
        raw = tomllib.loads(raw_bytes.decode())
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ProjectConfigError(
            f"invalid project adapter {descriptor}: {error}"
        ) from error
    if raw.get("schema") != 1:
        raise ProjectConfigError(f"{descriptor} must declare schema = 1")
    unknown_tables = set(raw) - _TABLES
    if unknown_tables:
        raise ProjectConfigError(
            f"{descriptor} contains unknown tables: "
            + ", ".join(sorted(unknown_tables))
        )
    project = raw.get("project")
    if not isinstance(project, Mapping):
        raise ProjectConfigError(f"{descriptor} requires a [project] table")
    project_id = project.get("id")
    display_name = project.get("display_name")
    if not isinstance(project_id, str) or not project_id.isidentifier():
        raise ProjectConfigError(f"{descriptor} project.id must be an identifier")
    if not isinstance(display_name, str) or not display_name:
        raise ProjectConfigError(f"{descriptor} project.display_name must be non-empty")
    markers = _string_list(project.get("root_markers"), "project.root_markers")
    missing_markers = [marker for marker in markers if not (root / marker).exists()]
    if missing_markers:
        raise ProjectConfigError(
            f"{descriptor} root marker(s) missing: {', '.join(missing_markers)}"
        )
    raw_operations = raw.get("operations", {})
    if not isinstance(raw_operations, Mapping):
        raise ProjectConfigError(f"{descriptor} [operations] must be a table")
    operations = tuple(
        _operation(str(name), definition, descriptor)
        for name, definition in sorted(raw_operations.items())
    )
    operation_names = {operation.name for operation in operations}
    unknown_dependencies = {
        dependency
        for operation in operations
        for dependency in operation.dependencies
        if dependency not in operation_names
    }
    if unknown_dependencies:
        raise ProjectConfigError(
            f"{descriptor} operation dependency/dependencies are undeclared: "
            + ", ".join(sorted(unknown_dependencies))
        )
    workspace = _workspace(raw, descriptor)
    if workspace is not None:
        unknown_verifiers = {
            name
            for profile, name in workspace.verify.items()
            if not (profile == "candidate" and name.startswith("hosted:"))
            and name not in operation_names
        }
        if unknown_verifiers:
            raise ProjectConfigError(
                f"{descriptor} workspace verification operation(s) are undeclared: "
                + ", ".join(sorted(unknown_verifiers))
            )
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise ProjectConfigError(
                f"{descriptor} operation dependencies contain a cycle"
            )
        if name in visited:
            return
        visiting.add(name)
        for dependency in next(
            operation for operation in operations if operation.name == name
        ).dependencies:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)

    for operation in operations:
        visit(operation.name)
    return ProjectAdapter(
        project_id=project_id,
        display_name=display_name,
        root=root,
        descriptor=descriptor,
        digest="sha256:" + hashlib.sha256(raw_bytes).hexdigest(),
        environment=_environment(raw, descriptor),
        workspace=workspace,
        operations=operations,
        packets=_packets(raw, root, descriptor),
    )


class ProjectCatalog:
    """The explicitly configured project roots; no directory is scanned."""

    def __init__(self, roots: Iterable[Path], *, tolerant: bool = False) -> None:
        # One caller validating one descriptor wants the error raised. A
        # listing over many roots must not let one bad descriptor hide the
        # others, so it asks for tolerance and reports the rejected root.
        self._adapters: dict[str, ProjectAdapter] = {}
        self._unavailable: dict[str, str] = {}
        for root in roots:
            try:
                adapter = load_project_adapter(root)
            except (ProjectConfigError, OSError, ValueError) as error:
                if not tolerant:
                    raise
                self._unavailable[str(root)] = str(error)
                continue
            if adapter.project_id in self._adapters:
                if not tolerant:
                    raise ProjectConfigError("project adapter IDs must be unique")
                self._unavailable[str(adapter.root)] = (
                    f"duplicate project id: {adapter.project_id}"
                )
                continue
            self._adapters[adapter.project_id] = adapter

    @property
    def unavailable(self) -> Mapping[str, str]:
        return dict(self._unavailable)

    def list(self) -> list[dict[str, Any]]:
        return [
            self._adapters[project_id].catalog_row()
            for project_id in sorted(self._adapters)
        ]

    def get(self, project_id: str) -> ProjectAdapter:
        try:
            return self._adapters[project_id]
        except KeyError as error:
            for root, reason in sorted(self._unavailable.items()):
                if Path(root).name == project_id:
                    raise KeyError(
                        f"project {project_id} is out of service: {reason}"
                    ) from error
            raise KeyError(f"unknown project: {project_id}") from error

    def scheduled_operations(
        self,
    ) -> tuple[tuple[ProjectAdapter, ProjectOperation], ...]:
        return tuple(
            (project, operation)
            for project in self._adapters.values()
            for operation in project.operations
            if operation.schedule is not None
        )
