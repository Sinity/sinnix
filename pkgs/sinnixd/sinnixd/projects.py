from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


class ProjectConfigError(ValueError):
    """Raised when a project adapter is missing or violates the v1 contract."""


@dataclass(frozen=True)
class ProjectEnvironment:
    kind: str
    command: tuple[str, ...]
    inherit: tuple[str, ...]
    unset: tuple[str, ...]


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
class ProjectAdapter:
    project_id: str
    display_name: str
    root: Path
    descriptor: Path
    digest: str
    environment: ProjectEnvironment
    operations: tuple[ProjectOperation, ...]

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
