from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from sinnix_mcp import Authority, Lifecycle, OwnerRegistry, OwnerSpec, SinnixRef

from .environment import build_environment


class ProjectConfigError(ValueError):
    """Raised when a project adapter is missing or violates the v1 contract."""


MAX_OPERATION_PARAMETERS = 16
MAX_PARAMETER_LIST_ITEMS = 32
MAX_PARAMETER_STRING_LENGTH = 128
_PARAMETER_FLAG = re.compile(r"--[a-z][a-z0-9-]*\Z")
_PACKAGE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")


def _parameter_digest(parameters: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def parse_worktree_records(output: str) -> tuple[dict[str, str], ...]:
    """Parse Git's porcelain records, including flag-only fields."""
    value_fields = {"worktree", "HEAD", "branch"}
    flag_fields = {"bare", "detached", "locked", "prunable"}
    records: list[dict[str, str]] = []
    record: dict[str, str] = {}
    for line in output.splitlines():
        if not line:
            if record:
                records.append(record)
                record = {}
            continue
        key, separator, value = line.partition(" ")
        if key in record or key not in value_fields | flag_fields:
            raise ProjectConfigError("git worktree returned malformed porcelain")
        if key in value_fields and (not separator or not value):
            raise ProjectConfigError("git worktree returned malformed porcelain")
        if key in flag_fields and separator and key not in {"locked", "prunable"}:
            raise ProjectConfigError("git worktree returned malformed porcelain")
        record[key] = value
    if record:
        records.append(record)
    return tuple(records)


@dataclass(frozen=True)
class RegisteredCheckout:
    """A Git-worktree identity revalidated at the execution boundary."""

    project_id: str
    project_path: Path
    checkout_id: str
    path: Path
    git_common_dir: Path
    head: str

    def to_dict(self) -> dict[str, str]:
        return {
            "project_id": self.project_id,
            "project_path": str(self.project_path),
            "checkout_id": self.checkout_id,
            "path": str(self.path),
            "git_common_dir": str(self.git_common_dir),
            "head": self.head,
        }


@dataclass(frozen=True)
class WorkspacePolicy:
    provider: str
    root: Path
    default_base: str
    identity_check: tuple[str, ...]
    checkpoint_untracked: bool
    verification_operations: tuple[str, ...]

    def catalog_row(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "root": str(self.root),
            "default_base": self.default_base,
            "identity_check": list(self.identity_check),
            "checkpoint_untracked": self.checkpoint_untracked,
            "verification_operations": list(self.verification_operations),
        }


@dataclass(frozen=True)
class ConflictPolicy:
    exact_files: tuple[str, ...]
    generated_surfaces: tuple[str, ...]
    semantic_slots: Mapping[str, tuple[str, ...]]

    def catalog_row(self) -> dict[str, Any]:
        return {
            "exact_files": list(self.exact_files),
            "generated_surfaces": list(self.generated_surfaces),
            "semantic_slots": {name: list(paths) for name, paths in self.semantic_slots.items()},
        }


@dataclass(frozen=True)
class ProjectEnvironment:
    kind: str
    command: tuple[str, ...]
    inherit: tuple[str, ...]
    unset: tuple[str, ...]

    def values(self) -> dict[str, str]:
        return build_environment(inherit=self.inherit, unset=self.unset)


@dataclass(frozen=True)
class OperationParameter:
    """A fixed descriptor-owned mapping from a typed value to argv entries."""

    name: str
    kind: str
    flag: str
    max_items: int | None = None
    max_length: int | None = None

    def catalog_row(self) -> dict[str, Any]:
        row: dict[str, Any] = {"name": self.name, "type": self.kind, "flag": self.flag}
        if self.kind == "string-list":
            row.update({"max_items": self.max_items, "max_length": self.max_length})
        return row

    def canonicalize(self, value: Any) -> bool | tuple[str, ...]:
        if self.kind == "bool":
            if not isinstance(value, bool):
                raise ValueError(f"parameter {self.name} must be boolean")
            return value
        if not isinstance(value, list) or not value:
            raise ValueError(f"parameter {self.name} must be a non-empty list")
        assert self.max_items is not None and self.max_length is not None
        if len(value) > self.max_items:
            raise ValueError(f"parameter {self.name} exceeds max_items")
        if any(
            not isinstance(item, str)
            or not item
            or len(item) > self.max_length
            or _PACKAGE_NAME.fullmatch(item) is None
            for item in value
        ):
            raise ValueError(f"parameter {self.name} must contain bounded package strings")
        return tuple(sorted(set(value)))


@dataclass(frozen=True)
class ProjectOperation:
    name: str
    description: str
    command: tuple[str, ...]
    pool: str
    result: str
    cache: str
    exclusive_keys: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    estimate_memory_bytes: int | None = None
    scratch: str = "none"
    parameters: tuple[OperationParameter, ...] = ()

    def derive_argv(self, raw_parameters: Mapping[str, Any]) -> tuple[tuple[str, ...], str]:
        if not isinstance(raw_parameters, Mapping):
            raise ValueError("declared job parameters must be an object")
        parameter_by_name = {parameter.name: parameter for parameter in self.parameters}
        unknown = set(raw_parameters) - set(parameter_by_name)
        if unknown:
            raise ValueError("declared job parameters contain unknown field(s): " + ", ".join(sorted(unknown)))
        canonical: dict[str, Any] = {}
        argv = list(self.command)
        for parameter in self.parameters:
            if parameter.name not in raw_parameters:
                continue
            value = parameter.canonicalize(raw_parameters[parameter.name])
            if parameter.kind == "bool":
                if value:
                    canonical[parameter.name] = True
                    argv.append(parameter.flag)
                continue
            assert isinstance(value, tuple)
            canonical[parameter.name] = list(value)
            for item in value:
                argv.extend((parameter.flag, item))
        return tuple(argv), _parameter_digest(canonical)

    def catalog_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "command": list(self.command),
            "pool": self.pool,
            "result": self.result,
            "cache": self.cache,
            "exclusive_keys": list(self.exclusive_keys),
            "dependencies": list(self.dependencies),
            "estimate_memory_bytes": self.estimate_memory_bytes,
            "scratch": self.scratch,
            "parameters": [parameter.catalog_row() for parameter in self.parameters],
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
    workspace: WorkspacePolicy | None
    conflicts: ConflictPolicy
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
            "workspace": self.workspace.catalog_row() if self.workspace is not None else None,
            "conflicts": self.conflicts.catalog_row(),
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


def _operation_parameters(value: Any, field: str) -> tuple[OperationParameter, ...]:
    if value is None:
        return ()
    if not isinstance(value, Mapping) or len(value) > MAX_OPERATION_PARAMETERS:
        raise ProjectConfigError(f"{field} must be a bounded table")
    parameters: list[OperationParameter] = []
    for name, definition in sorted(value.items()):
        if not isinstance(name, str) or not name.isidentifier() or not isinstance(definition, Mapping):
            raise ProjectConfigError(f"{field} contains an invalid parameter declaration")
        kind = definition.get("type")
        flag = definition.get("flag")
        if kind not in {"bool", "string-list"} or not isinstance(flag, str) or _PARAMETER_FLAG.fullmatch(flag) is None:
            raise ProjectConfigError(f"{field}.{name} has an invalid type or flag")
        if kind == "bool":
            if set(definition) != {"type", "flag"}:
                raise ProjectConfigError(f"{field}.{name} bool parameters only accept type and flag")
            parameters.append(OperationParameter(name=name, kind=kind, flag=flag))
            continue
        if set(definition) != {"type", "flag", "max_items", "max_length"}:
            raise ProjectConfigError(f"{field}.{name} string-list parameters require explicit bounds")
        max_items = definition.get("max_items")
        max_length = definition.get("max_length")
        if (
            not isinstance(max_items, int)
            or isinstance(max_items, bool)
            or not 1 <= max_items <= MAX_PARAMETER_LIST_ITEMS
            or not isinstance(max_length, int)
            or isinstance(max_length, bool)
            or not 1 <= max_length <= MAX_PARAMETER_STRING_LENGTH
        ):
            raise ProjectConfigError(f"{field}.{name} has invalid bounds")
        parameters.append(OperationParameter(name=name, kind=kind, flag=flag, max_items=max_items, max_length=max_length))
    if len({parameter.flag for parameter in parameters}) != len(parameters):
        raise ProjectConfigError(f"{field} parameter flags must be unique")
    return tuple(parameters)


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

    raw_workspace = raw.get("workspace")
    workspace: WorkspacePolicy | None = None
    if raw_workspace is not None:
        if not isinstance(raw_workspace, Mapping):
            raise ProjectConfigError(f"{descriptor} [workspace] must be a table")
        allowed_workspace = {
            "provider", "root", "default_base", "identity_check", "checkpoint_untracked",
            "verification_operations",
        }
        if set(raw_workspace) - allowed_workspace:
            raise ProjectConfigError(f"{descriptor} [workspace] contains unknown fields")
        provider = raw_workspace.get("provider")
        workspace_root = raw_workspace.get("root")
        default_base = raw_workspace.get("default_base")
        checkpoint_untracked = raw_workspace.get("checkpoint_untracked")
        if provider != "git-worktree":
            raise ProjectConfigError(f"{descriptor} workspace.provider must be git-worktree")
        if not isinstance(workspace_root, str) or not Path(workspace_root).is_absolute():
            raise ProjectConfigError(f"{descriptor} workspace.root must be an absolute path")
        if not isinstance(default_base, str) or not default_base:
            raise ProjectConfigError(f"{descriptor} workspace.default_base must be non-empty")
        if not isinstance(checkpoint_untracked, bool):
            raise ProjectConfigError(f"{descriptor} workspace.checkpoint_untracked must be boolean")
        workspace = WorkspacePolicy(
            provider=provider,
            root=Path(workspace_root),
            default_base=default_base,
            identity_check=_string_list(raw_workspace.get("identity_check"), "workspace.identity_check"),
            checkpoint_untracked=checkpoint_untracked,
            verification_operations=_optional_string_list(
                raw_workspace.get("verification_operations"), "workspace.verification_operations"
            ),
        )

    raw_conflicts = raw.get("conflicts", {})
    if not isinstance(raw_conflicts, Mapping) or set(raw_conflicts) - {
        "exact_files", "generated_surfaces", "semantic_slots"
    }:
        raise ProjectConfigError(f"{descriptor} [conflicts] is invalid")
    raw_semantic_slots = raw_conflicts.get("semantic_slots", {})
    if isinstance(raw_semantic_slots, list):
        semantic_slots = {
            name: () for name in _optional_string_list(raw_semantic_slots, "conflicts.semantic_slots")
        }
    elif isinstance(raw_semantic_slots, Mapping) and all(isinstance(name, str) and name for name in raw_semantic_slots):
        semantic_slots = {
            name: _string_list(paths, f"conflicts.semantic_slots.{name}")
            for name, paths in sorted(raw_semantic_slots.items())
        }
    else:
        raise ProjectConfigError(f"{descriptor} conflicts.semantic_slots is invalid")
    conflicts = ConflictPolicy(
        exact_files=_optional_string_list(raw_conflicts.get("exact_files"), "conflicts.exact_files"),
        generated_surfaces=_optional_string_list(
            raw_conflicts.get("generated_surfaces"), "conflicts.generated_surfaces"
        ),
        semantic_slots=semantic_slots,
    )

    owner_adapters = _owner_adapters(raw, descriptor)
    raw_operations = raw.get("operations", {})
    if not isinstance(raw_operations, Mapping):
        raise ProjectConfigError(f"{descriptor} [operations] must be a table")
    operations: list[ProjectOperation] = []
    for name, definition in sorted(raw_operations.items()):
        if not isinstance(name, str) or not name.isidentifier() or not isinstance(definition, Mapping):
            raise ProjectConfigError(f"{descriptor} contains an invalid operation declaration")
        allowed_operation = {
            "description", "exec", "pool", "result", "cache", "exclusive_keys",
            "dependencies", "estimate_memory_bytes", "scratch", "parameters",
        }
        if set(definition) - allowed_operation:
            raise ProjectConfigError(f"{descriptor} operation {name} contains unknown fields")
        description = definition.get("description")
        if not isinstance(description, str) or not description:
            raise ProjectConfigError(f"{descriptor} operation {name} requires description")
        command = _string_list(definition.get("exec"), f"operations.{name}.exec")
        pool = definition.get("pool", "normal")
        result = definition.get("result", "exit")
        cache = definition.get("cache", "none")
        if pool not in {"interactive", "normal", "bulk"}:
            raise ProjectConfigError(f"operations.{name}.pool is invalid")
        if result not in {"exit", "json", "pytest"}:
            raise ProjectConfigError(f"operations.{name}.result is invalid")
        if not isinstance(cache, str) or not cache:
            raise ProjectConfigError(f"operations.{name}.cache must be non-empty")
        if cache not in {"none", "tree+environment"}:
            raise ProjectConfigError(f"operations.{name}.cache is invalid")
        dependencies = _optional_string_list(definition.get("dependencies"), f"operations.{name}.dependencies")
        if name in dependencies or len(set(dependencies)) != len(dependencies):
            raise ProjectConfigError(f"operations.{name}.dependencies is invalid")
        estimate_memory_bytes = definition.get("estimate_memory_bytes")
        if estimate_memory_bytes is not None and (
            not isinstance(estimate_memory_bytes, int)
            or isinstance(estimate_memory_bytes, bool)
            or not 1 <= estimate_memory_bytes <= 128 * 1024 * 1024 * 1024
        ):
            raise ProjectConfigError(f"operations.{name}.estimate_memory_bytes is invalid")
        scratch = definition.get("scratch", "none")
        if scratch not in {"none", "tmpfs", "nvme"}:
            raise ProjectConfigError(f"operations.{name}.scratch is invalid")
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
                dependencies=dependencies,
                estimate_memory_bytes=estimate_memory_bytes,
                scratch=scratch,
                parameters=_operation_parameters(definition.get("parameters"), f"operations.{name}.parameters"),
            )
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
            f"{descriptor} operation dependency/dependencies are undeclared: " + ", ".join(sorted(unknown_dependencies))
        )
    if workspace is not None:
        unknown_verifiers = set(workspace.verification_operations) - operation_names
        if unknown_verifiers:
            raise ProjectConfigError(
                f"{descriptor} workspace verification operation(s) are undeclared: "
                + ", ".join(sorted(unknown_verifiers))
            )
    return ProjectAdapter(
        project_id=project_id,
        display_name=display_name,
        root=root,
        descriptor=descriptor,
        digest="sha256:" + hashlib.sha256(raw_bytes).hexdigest(),
        environment=execution_environment,
        workspace=workspace,
        conflicts=conflicts,
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

    @staticmethod
    def _git(path: Path, *arguments: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(path), *arguments],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ProjectConfigError(f"could not verify registered checkout {path}") from error
        return result.stdout

    @staticmethod
    def _checkout_id(path: Path, configured_root: Path) -> str:
        if path == configured_root:
            return "default"
        return "worktree-" + hashlib.sha256(str(path).encode()).hexdigest()[:16]

    def checkouts(self, project_id: str) -> tuple[RegisteredCheckout, ...]:
        project = self.get(project_id)
        root = project.root.resolve(strict=True)
        records = parse_worktree_records(self._git(root, "worktree", "list", "--porcelain"))
        checkouts: list[RegisteredCheckout] = []
        for record in records:
            raw_path = record.get("worktree")
            head = record.get("HEAD")
            if raw_path is None or head is None:
                raise ProjectConfigError("git worktree record is missing worktree or HEAD")
            path = Path(raw_path).resolve(strict=True)
            top_level = Path(self._git(path, "rev-parse", "--show-toplevel").strip()).resolve(strict=True)
            common_dir = Path(
                self._git(path, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
            ).resolve(strict=True)
            if top_level != path:
                raise ProjectConfigError("registered checkout has a non-canonical worktree root")
            checkouts.append(
                RegisteredCheckout(
                    project_id=project.project_id,
                    project_path=root,
                    checkout_id=self._checkout_id(path, root),
                    path=path,
                    git_common_dir=common_dir,
                    head=head,
                )
            )
        if not any(checkout.checkout_id == "default" and checkout.path == root for checkout in checkouts):
            raise ProjectConfigError("configured project root is not a registered Git worktree")
        return tuple(sorted(checkouts, key=lambda checkout: (checkout.checkout_id != "default", checkout.checkout_id)))

    def checkout(self, project_id: str, checkout_id: str) -> RegisteredCheckout:
        if not isinstance(checkout_id, str) or not checkout_id:
            raise KeyError("checkout_id must be a non-empty string")
        for checkout in self.checkouts(project_id):
            if checkout.checkout_id == checkout_id:
                return checkout
        raise KeyError(f"unknown registered checkout: {project_id}.{checkout_id}")

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
