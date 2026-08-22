from __future__ import annotations

import hashlib
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from sinnix_mcp import Authority, Lifecycle, OwnerRegistry, OwnerSpec, SinnixRef


class ProjectConfigError(ValueError):
    """Raised when a project adapter is missing or violates the v1 contract."""


@dataclass(frozen=True)
class ProjectEnvironment:
    kind: str
    command: tuple[str, ...]
    inherit: tuple[str, ...]
    unset: tuple[str, ...]

    def values(self) -> dict[str, str]:
        environment = {
            key: os.environ[key]
            for key in self.inherit
            if key in os.environ and key not in self.unset
        }
        environment["PATH"] = os.environ.get("PATH", "/run/current-system/sw/bin")
        return environment


@dataclass(frozen=True)
class ProjectOperation:
    name: str
    description: str
    command: tuple[str, ...]
    pool: str
    result: str
    cache: str
    exclusive_keys: tuple[str, ...] = ()

    def catalog_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "command": list(self.command),
            "pool": self.pool,
            "result": self.result,
            "cache": self.cache,
            "exclusive_keys": list(self.exclusive_keys),
        }


@dataclass(frozen=True)
class ProjectOwnerAdapter:
    """One fixed, source-scoped owner process declared by a project."""

    spec: OwnerSpec
    command: tuple[str, ...]
    source_ref: SinnixRef
    timeout_seconds: int = 30

    def catalog_row(self) -> dict[str, Any]:
        return {
            **self.spec.catalog_row(),
            "source_ref": str(self.source_ref),
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass(frozen=True)
class ProjectAdapter:
    project_id: str
    display_name: str
    root: Path
    descriptor: Path
    digest: str
    environment: ProjectEnvironment
    operations: tuple[ProjectOperation, ...]
    owner_adapters: tuple[ProjectOwnerAdapter, ...] = ()

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
            "operations": [operation.catalog_row() for operation in self.operations],
            "owner_adapters": [adapter.catalog_row() for adapter in self.owner_adapters],
        }


def _string_list(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
        raise ProjectConfigError(f"{field} must be a non-empty list of non-empty strings")
    return tuple(value)


def _optional_string_list(value: Any, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ProjectConfigError(f"{field} must be a list of non-empty strings")
    return tuple(value)


def _owner_adapters(raw: Mapping[str, Any], descriptor: Path) -> tuple[ProjectOwnerAdapter, ...]:
    definitions = raw.get("owner_adapters", {})
    if not isinstance(definitions, Mapping):
        raise ProjectConfigError(f"{descriptor} [owner_adapters] must be a table")
    adapters: list[ProjectOwnerAdapter] = []
    for name, definition in sorted(definitions.items()):
        if not isinstance(name, str) or not name.isidentifier() or not isinstance(definition, Mapping):
            raise ProjectConfigError(f"{descriptor} contains an invalid owner adapter declaration")
        allowed = {
            "namespace",
            "owner",
            "authority",
            "lifecycle",
            "protocol_versions",
            "source_scoped",
            "source_ref",
            "exec",
            "timeout_seconds",
            "documentation",
        }
        if set(definition) - allowed:
            raise ProjectConfigError(f"owner_adapters.{name} contains unknown fields")
        namespace = definition.get("namespace")
        owner = definition.get("owner")
        documentation = definition.get("documentation", "")
        versions = definition.get("protocol_versions")
        if not isinstance(namespace, str) or not isinstance(owner, str):
            raise ProjectConfigError(f"owner_adapters.{name} requires namespace and owner")
        if not isinstance(documentation, str):
            raise ProjectConfigError(f"owner_adapters.{name}.documentation must be a string")
        if not isinstance(versions, list) or not versions or any(
            not isinstance(version, int) or isinstance(version, bool) for version in versions
        ):
            raise ProjectConfigError(f"owner_adapters.{name}.protocol_versions must be non-empty integers")
        if definition.get("source_scoped") is not True:
            raise ProjectConfigError(f"owner_adapters.{name} must declare source_scoped = true")
        source_ref = definition.get("source_ref")
        if not isinstance(source_ref, str):
            raise ProjectConfigError(f"owner_adapters.{name}.source_ref must be a string")
        timeout_seconds = definition.get("timeout_seconds", 30)
        if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 300:
            raise ProjectConfigError(f"owner_adapters.{name}.timeout_seconds must be between 1 and 300")
        try:
            spec = OwnerSpec(
                namespace=namespace,
                owner=owner,
                authority=Authority(definition.get("authority")),
                lifecycle=Lifecycle(definition.get("lifecycle")),
                versions=frozenset(versions),
                source_scoped=True,
                documentation=documentation,
            )
            parsed_source_ref = SinnixRef.parse(source_ref)
        except (TypeError, ValueError) as error:
            raise ProjectConfigError(f"owner_adapters.{name} is invalid: {error}") from error
        adapters.append(
            ProjectOwnerAdapter(
                spec=spec,
                command=_string_list(definition.get("exec"), f"owner_adapters.{name}.exec"),
                source_ref=parsed_source_ref,
                timeout_seconds=timeout_seconds,
            )
        )
    try:
        OwnerRegistry(adapter.spec for adapter in adapters)
    except ValueError as error:
        raise ProjectConfigError(f"{descriptor} owner adapters overlap: {error}") from error
    return tuple(adapters)


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
        raise ProjectConfigError(f"{descriptor} root marker(s) missing: {', '.join(missing_markers)}")

    environment = raw.get("environment")
    if not isinstance(environment, Mapping):
        raise ProjectConfigError(f"{descriptor} requires an [environment] table")
    environment_kind = environment.get("kind")
    if not isinstance(environment_kind, str) or not environment_kind:
        raise ProjectConfigError(f"{descriptor} environment.kind must be non-empty")
    execution_environment = ProjectEnvironment(
        kind=environment_kind,
        command=_string_list(environment.get("command"), "environment.command"),
        inherit=_optional_string_list(environment.get("inherit"), "environment.inherit"),
        unset=_optional_string_list(environment.get("unset"), "environment.unset"),
    )

    owner_adapters = _owner_adapters(raw, descriptor)
    raw_operations = raw.get("operations", {})
    if not isinstance(raw_operations, Mapping):
        raise ProjectConfigError(f"{descriptor} [operations] must be a table")
    operations: list[ProjectOperation] = []
    for name, definition in sorted(raw_operations.items()):
        if not isinstance(name, str) or not name.isidentifier() or not isinstance(definition, Mapping):
            raise ProjectConfigError(f"{descriptor} contains an invalid operation declaration")
        description = definition.get("description")
        if not isinstance(description, str) or not description:
            raise ProjectConfigError(f"{descriptor} operation {name} requires description")
        command = _string_list(definition.get("exec"), f"operations.{name}.exec")
        pool = definition.get("pool", "normal")
        result = definition.get("result", "exit")
        cache = definition.get("cache", "none")
        if pool not in {"normal", "bulk", "attached"}:
            raise ProjectConfigError(f"operations.{name}.pool is invalid")
        if result not in {"exit", "json", "pytest", "agent", "service"}:
            raise ProjectConfigError(f"operations.{name}.result is invalid")
        if not isinstance(cache, str) or not cache:
            raise ProjectConfigError(f"operations.{name}.cache must be non-empty")
        operations.append(
            ProjectOperation(
                name=name,
                description=description,
                command=command,
                pool=pool,
                result=result,
                cache=cache,
                exclusive_keys=_optional_string_list(
                    definition.get("exclusive_keys"), f"operations.{name}.exclusive_keys"
                ),
            )
        )
    return ProjectAdapter(
        project_id=project_id,
        display_name=display_name,
        root=root,
        descriptor=descriptor,
        digest="sha256:" + hashlib.sha256(raw_bytes).hexdigest(),
        environment=execution_environment,
        operations=tuple(operations),
        owner_adapters=owner_adapters,
    )


class ProjectCatalog:
    """Discover explicit project roots without treating arbitrary directories as projects."""

    def __init__(self, roots: Iterable[Path]) -> None:
        adapters = [load_project_adapter(root) for root in roots]
        by_id = {adapter.project_id: adapter for adapter in adapters}
        if len(by_id) != len(adapters):
            raise ProjectConfigError("project adapter IDs must be unique")
        self._adapters = by_id

    def list(self) -> list[dict[str, Any]]:
        return [self._adapters[project_id].catalog_row() for project_id in sorted(self._adapters)]

    def get(self, project_id: str) -> ProjectAdapter:
        try:
            return self._adapters[project_id]
        except KeyError as error:
            raise KeyError(f"unknown project: {project_id}") from error

    def owner_adapters(self) -> tuple[ProjectOwnerAdapter, ...]:
        adapters = tuple(
            owner_adapter
            for project in self._adapters.values()
            for owner_adapter in project.owner_adapters
        )
        try:
            OwnerRegistry(adapter.spec for adapter in adapters)
        except ValueError as error:
            raise ProjectConfigError(f"project owner adapters overlap: {error}") from error
        return adapters

    def owner_adapter(self, operation: str) -> tuple[ProjectAdapter, ProjectOwnerAdapter]:
        registry = OwnerRegistry(adapter.spec for adapter in self.owner_adapters())
        spec = registry.resolve(operation)
        for project in self._adapters.values():
            for adapter in project.owner_adapters:
                if adapter.spec == spec:
                    return project, adapter
        raise KeyError(f"no project owner adapter for {operation!r}")
