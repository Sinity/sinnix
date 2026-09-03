"""Project descriptors: the one thing agentctl owns outright.

A descriptor (`.agentctl/project.toml`) declares what a project's operations
mean — argv, pool, result contract, timeout, checkout policy, schedule — and
how to enter its environment. Everything else (queueing, worktrees, review,
tasks) belongs to pueue, worktrunk, GitHub and Beads.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import tomllib

from .environment import build_environment
from .limits import (
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
RESULT_KINDS = frozenset({"exit", "json", "pytest"})

# Retired descriptor tables still present in deployed descriptors. They are
# inert here and ignored rather than taking the project out of service.
_IGNORED_TABLES = frozenset({"conflicts", "owner_adapters", "packets"})
_WORKSPACE_FIELDS = frozenset({"root", "default_base"})
_IGNORED_WORKSPACE_FIELDS = frozenset(
    {
        "provider",
        "identity_check",
        "checkpoint_untracked",
        "verification_operations",
        "provision",
    }
)
_OPERATION_FIELDS = frozenset(
    {
        "description",
        "exec",
        "pool",
        "result",
        "timeout_seconds",
        "schedule",
        "checkout",
        # Accepted and ignored: descriptors still declare it.
        "cache",
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

    def catalog_row(self) -> dict[str, Any]:
        return {"root": str(self.root), "default_base": self.default_base}


@dataclass(frozen=True)
class ProjectOperation:
    name: str
    description: str
    command: tuple[str, ...]
    pool: str
    result: str
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    schedule: str | None = None
    # "default": the operation runs only on the project's main checkout. A
    # complete corpus run belongs to the master boundary, not to a lane.
    checkout: str = "any"

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
        inherit=_optional_string_list(environment.get("inherit"), "environment.inherit"),
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
    unknown = set(raw_workspace) - _WORKSPACE_FIELDS - _IGNORED_WORKSPACE_FIELDS
    if unknown:
        raise ProjectConfigError(f"{descriptor} [workspace] contains unknown fields")
    root = raw_workspace.get("root")
    default_base = raw_workspace.get("default_base")
    if not isinstance(root, str) or not Path(root).is_absolute():
        raise ProjectConfigError(f"{descriptor} workspace.root must be an absolute path")
    if not isinstance(default_base, str) or not default_base:
        raise ProjectConfigError(f"{descriptor} workspace.default_base must be non-empty")
    return WorkspacePolicy(root=Path(root), default_base=default_base)


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
    pool = definition.get("pool", "normal")
    result = definition.get("result", "exit")
    if not isinstance(pool, str) or not _POOL_NAME.fullmatch(pool):
        raise ProjectConfigError(f"operations.{name}.pool is invalid")
    if result not in RESULT_KINDS:
        raise ProjectConfigError(f"operations.{name}.result is invalid")
    timeout_seconds = definition.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    if not valid_timeout_seconds(timeout_seconds, kind="declared-operation"):
        raise ProjectConfigError(
            f"operations.{name}.timeout_seconds must be between 1 and "
            f"{MAX_DECLARED_OPERATION_TIMEOUT_SECONDS}"
        )
    checkout = definition.get("checkout", "any")
    if checkout not in {"any", "default"}:
        raise ProjectConfigError(f"operations.{name}.checkout is invalid")
    schedule = definition.get("schedule")
    if schedule is not None and (
        not isinstance(schedule, str)
        or not schedule
        or len(schedule) > MAX_OPERATION_SCHEDULE_LENGTH
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in schedule)
    ):
        raise ProjectConfigError(
            f"operations.{name}.schedule must be a non-empty OnCalendar expression"
        )
    return ProjectOperation(
        name=name,
        description=description,
        command=command,
        pool=pool,
        result=result,
        timeout_seconds=timeout_seconds,
        schedule=schedule,
        checkout=checkout,
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
        raise ProjectConfigError(f"invalid project adapter {descriptor}: {error}") from error
    if raw.get("schema") != 1:
        raise ProjectConfigError(f"{descriptor} must declare schema = 1")
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
    return ProjectAdapter(
        project_id=project_id,
        display_name=display_name,
        root=root,
        descriptor=descriptor,
        digest="sha256:" + hashlib.sha256(raw_bytes).hexdigest(),
        environment=_environment(raw, descriptor),
        workspace=_workspace(raw, descriptor),
        operations=operations,
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
