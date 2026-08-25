from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import tomllib
from sinnix_mcp import Authority, Lifecycle, OwnerRegistry, OwnerSpec, SinnixRef

from .environment import build_environment
from .limits import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_DECLARED_OPERATION_TIMEOUT_SECONDS,
    valid_timeout_seconds,
)


class ProjectConfigError(ValueError):
    """Raised when a project adapter is missing or violates the v1 contract."""


MAX_OPERATION_PARAMETERS = 32
MAX_PARAMETER_LIST_ITEMS = 32
MAX_PARAMETER_STRING_LENGTH = 128
MAX_PARAMETER_ENUM_VALUES = 64
MIN_PARAMETER_INTEGER = -(2**31)
MAX_PARAMETER_INTEGER = 2**31 - 1
MAX_SERVICE_PORT_SLOTS = 8
MAX_SERVICE_PORT_RANGE = 256
_PARAMETER_FLAG = re.compile(r"--[a-z][a-z0-9-]*\Z")
_SERVICE_PORT_SLOT = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")
_SERVICE_ENVIRONMENT = re.compile(r"(?:[A-Z][A-Z0-9_]*_)?PORT\Z")
_PARAMETER_GRAMMARS = {
    "identifier": re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z"),
    "package-name": re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z"),
    "safe-token": re.compile(r"[A-Za-z0-9][A-Za-z0-9._:+@=-]*\Z"),
    "duration": re.compile(r"[1-9][0-9]{0,8}(?:ms|s|m|h)\Z"),
}
DEFAULT_PARAMETER_GRAMMAR = "safe-token"


def _parameter_digest(parameters: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
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


def _registered_checkout_id(path: Path, project_path: Path) -> str:
    if path == project_path:
        return "default"
    return "worktree-" + hashlib.sha256(str(path).encode()).hexdigest()[:16]


def _checkout_git(path: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ProjectConfigError(
            f"could not verify registered checkout {path}"
        ) from error
    return result.stdout


def revalidate_registered_checkout(checkout: Mapping[str, Any]) -> Path:
    """Prove a durable checkout binding still names the same registered Git worktree."""
    expected = {
        "project_id",
        "project_path",
        "checkout_id",
        "path",
        "git_common_dir",
        "head",
    }
    if set(checkout) != expected or any(
        not isinstance(checkout.get(field), str) or not checkout[field]
        for field in expected
    ):
        raise ProjectConfigError("registered checkout identity is invalid")
    recorded_path = Path(checkout["path"])
    project_path = Path(checkout["project_path"])
    if not recorded_path.is_absolute() or not project_path.is_absolute():
        raise ProjectConfigError("registered checkout path is not absolute")
    try:
        path = recorded_path.resolve(strict=True)
        project_root = project_path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ProjectConfigError("registered checkout is unavailable") from error
    if str(path) != checkout["path"] or str(project_root) != checkout["project_path"]:
        raise ProjectConfigError("registered checkout path is not canonical")
    if not (project_root / ".agentctl" / "project.toml").is_file():
        raise ProjectConfigError("registered project is unavailable")
    try:
        top_level = Path(
            _checkout_git(path, "rev-parse", "--show-toplevel").strip()
        ).resolve(strict=True)
        common_dir = Path(
            _checkout_git(
                path, "rev-parse", "--path-format=absolute", "--git-common-dir"
            ).strip()
        ).resolve(strict=True)
        project_top_level = Path(
            _checkout_git(project_root, "rev-parse", "--show-toplevel").strip()
        ).resolve(strict=True)
        project_common_dir = Path(
            _checkout_git(
                project_root, "rev-parse", "--path-format=absolute", "--git-common-dir"
            ).strip()
        ).resolve(strict=True)
    except OSError as error:
        raise ProjectConfigError("registered checkout is unavailable") from error
    if (
        top_level != path
        or project_top_level != project_root
        or str(common_dir) != checkout["git_common_dir"]
        or common_dir != project_common_dir
        or _registered_checkout_id(path, project_root) != checkout["checkout_id"]
    ):
        raise ProjectConfigError("registered checkout identity changed")
    records = parse_worktree_records(
        _checkout_git(project_root, "worktree", "list", "--porcelain")
    )
    if not any(
        record.get("worktree") == str(path) and record.get("HEAD") == checkout["head"]
        for record in records
    ):
        raise ProjectConfigError("checkout is no longer a registered Git worktree")
    return path


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
            "semantic_slots": {
                name: list(paths) for name, paths in self.semantic_slots.items()
            },
        }


@dataclass(frozen=True)
class ProjectEnvironment:
    kind: str
    command: tuple[str, ...]
    inherit: tuple[str, ...]
    unset: tuple[str, ...]
    preflight: tuple[str, ...] = ()

    def values(self) -> dict[str, str]:
        return build_environment(inherit=self.inherit, unset=self.unset)

    def command_for(
        self, payload: Sequence[str], *, overrides: Mapping[str, str] | None = None
    ) -> tuple[str, ...]:
        """Enter the project environment and apply runtime-owned payload variables.

        Nix creates a per-invocation ``nix-shell.*`` TMPDIR while entering a
        development shell.  That directory is an implementation detail, not a
        durable job scratch contract.  Place runtime-owned overrides after
        ``nix develop --command`` so the payload sees the job-owned path.
        """
        assignments = tuple(
            f"{name}={value}" for name, value in sorted((overrides or {}).items())
        )
        if not assignments:
            return (*self.command, *payload)
        if self.kind == "nix-develop":
            return (*self.command, "env", *assignments, *payload)
        return ("env", *assignments, *self.command, *payload)

    def catalog_row(self, *, agent_capable: bool) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "command": list(self.command),
            "preflight": list(self.preflight),
            "agent_capable": agent_capable,
        }


@dataclass(frozen=True)
class ServicePortSlot:
    """One descriptor-owned loopback port and the sole environment name it injects."""

    name: str
    environment: str
    minimum: int
    maximum: int

    def catalog_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "environment": self.environment,
            "range": [self.minimum, self.maximum],
        }


@dataclass(frozen=True)
class OperationService:
    """Closed metadata for a development service owned by one declared operation."""

    readiness: str
    lifetime: str
    ports: tuple[ServicePortSlot, ...]

    def catalog_row(self) -> dict[str, Any]:
        return {
            "readiness": self.readiness,
            "lifetime": self.lifetime,
            "ports": [port.catalog_row() for port in self.ports],
        }


@dataclass(frozen=True)
class OperationParameter:
    """A fixed descriptor-owned mapping from a typed value to argv entries."""

    name: str
    kind: str
    flag: str | None = None
    position: int | None = None
    required: bool = False
    max_items: int | None = None
    max_length: int | None = None
    grammar: str | None = None
    values: tuple[str, ...] = ()
    minimum: int | None = None
    maximum: int | None = None

    def catalog_row(self) -> dict[str, Any]:
        row: dict[str, Any] = {"name": self.name, "type": self.kind}
        if self.flag is not None:
            row["flag"] = self.flag
            if self.required:
                row["required"] = True
        else:
            assert self.position is not None and self.required
            row.update({"position": self.position, "required": True})
        if self.kind in {"string", "string-list"}:
            row.update({"max_length": self.max_length, "grammar": self.grammar})
        if self.kind in {"string-list", "enum-list"}:
            row["max_items"] = self.max_items
        if self.kind in {"enum", "enum-list"}:
            row.update(
                {
                    "values": list(self.values),
                    "max_length": self.max_length,
                    "grammar": self.grammar,
                }
            )
        if self.kind == "integer":
            row.update({"min": self.minimum, "max": self.maximum})
        return row

    def canonicalize(self, value: Any) -> bool | int | str | tuple[str, ...]:
        if self.kind == "bool":
            if not isinstance(value, bool):
                raise ValueError(f"parameter {self.name} must be boolean")
            return value
        if self.kind == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"parameter {self.name} must be an integer")
            assert self.minimum is not None and self.maximum is not None
            if not self.minimum <= value <= self.maximum:
                raise ValueError(f"parameter {self.name} is outside its declared range")
            return value
        if self.kind in {"string", "enum"}:
            self._validate_string(value)
            if self.kind == "enum" and value not in self.values:
                raise ValueError(
                    f"parameter {self.name} must be one of its declared values"
                )
            return value
        if not isinstance(value, list) or not value:
            raise ValueError(f"parameter {self.name} must be a non-empty list")
        assert self.max_items is not None
        if len(value) > self.max_items:
            raise ValueError(f"parameter {self.name} exceeds max_items")
        for item in value:
            self._validate_string(item)
            if self.kind == "enum-list" and item not in self.values:
                raise ValueError(
                    f"parameter {self.name} must contain only declared values"
                )
        return tuple(sorted(set(value)))

    def _validate_string(self, value: Any) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError(f"parameter {self.name} must be a non-empty string")
        assert self.max_length is not None and self.grammar is not None
        if (
            len(value) > self.max_length
            or _PARAMETER_GRAMMARS[self.grammar].fullmatch(value) is None
        ):
            raise ValueError(
                f"parameter {self.name} contains an unsafe or malformed string"
            )


@dataclass(frozen=True)
class ProjectOperation:
    name: str
    description: str
    command: tuple[str, ...]
    pool: str
    result: str
    cache: str
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    exclusive_keys: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    estimate_memory_bytes: int | None = None
    scratch: str = "none"
    parameters: tuple[OperationParameter, ...] = ()
    service: OperationService | None = None
    plan_node: bool = False

    def derive_argv(
        self, raw_parameters: Mapping[str, Any]
    ) -> tuple[tuple[str, ...], str]:
        if not isinstance(raw_parameters, Mapping):
            raise ValueError("declared job parameters must be an object")
        parameter_by_name = {parameter.name: parameter for parameter in self.parameters}
        unknown = set(raw_parameters) - set(parameter_by_name)
        if unknown:
            raise ValueError(
                "declared job parameters contain unknown field(s): "
                + ", ".join(sorted(unknown))
            )
        canonical: dict[str, Any] = {}
        positional_argv: list[tuple[int, str]] = []
        flag_argv: list[str] = []
        for parameter in self.parameters:
            if parameter.name not in raw_parameters:
                if parameter.required:
                    raise ValueError(
                        f"declared job parameters omit required field: {parameter.name}"
                    )
                continue
            value = parameter.canonicalize(raw_parameters[parameter.name])
            if parameter.position is not None:
                assert isinstance(value, (int, str))
                canonical[parameter.name] = value
                positional_argv.append((parameter.position, str(value)))
                continue
            assert parameter.flag is not None
            if parameter.kind == "bool":
                if value:
                    canonical[parameter.name] = True
                    flag_argv.append(parameter.flag)
                continue
            if parameter.kind in {"string-list", "enum-list"}:
                assert isinstance(value, tuple)
                canonical[parameter.name] = list(value)
                for item in value:
                    flag_argv.extend((parameter.flag, item))
                continue
            assert isinstance(value, (int, str))
            canonical[parameter.name] = value
            flag_argv.extend((parameter.flag, str(value)))
        argv = [*self.command]
        argv.extend(value for _, value in sorted(positional_argv))
        argv.extend(flag_argv)
        return tuple(argv), _parameter_digest(canonical)

    def catalog_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "command": list(self.command),
            "pool": self.pool,
            "result": self.result,
            "cache": self.cache,
            "timeout_seconds": self.timeout_seconds,
            "exclusive_keys": list(self.exclusive_keys),
            "dependencies": list(self.dependencies),
            "estimate_memory_bytes": self.estimate_memory_bytes,
            "scratch": self.scratch,
            "parameters": [parameter.catalog_row() for parameter in self.parameters],
            "service": self.service.catalog_row() if self.service is not None else None,
            "plan_node": self.plan_node,
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

    @property
    def agent_capable(self) -> bool:
        return self.workspace is not None

    def operation(self, name: str) -> ProjectOperation:
        for operation in self.operations:
            if operation.name == name:
                return operation
        raise KeyError(f"unknown project operation: {self.project_id}.{name}")

    def descriptor_status(self) -> dict[str, Any]:
        try:
            on_disk_digest = (
                "sha256:" + hashlib.sha256(self.descriptor.read_bytes()).hexdigest()
            )
        except OSError:
            on_disk_digest = None
        return {
            "loaded_digest": self.digest,
            "on_disk_digest": on_disk_digest,
            "matches_loaded": on_disk_digest == self.digest,
        }

    def catalog_row(self) -> dict[str, Any]:
        return {
            "id": self.project_id,
            "display_name": self.display_name,
            "root": str(self.root),
            "descriptor": str(self.descriptor),
            "digest": self.digest,
            "descriptor_status": self.descriptor_status(),
            "environment": self.environment.catalog_row(
                agent_capable=self.agent_capable
            ),
            "workspace": self.workspace.catalog_row() if self.agent_capable else None,
            "conflicts": self.conflicts.catalog_row(),
            "operations": [operation.catalog_row() for operation in self.operations],
            "owner_adapters": [
                adapter.catalog_row() for adapter in self.owner_adapters
            ],
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


def _operation_parameters(value: Any, field: str) -> tuple[OperationParameter, ...]:
    if value is None:
        return ()
    if not isinstance(value, Mapping) or len(value) > MAX_OPERATION_PARAMETERS:
        raise ProjectConfigError(f"{field} must be a bounded table")
    parameters: list[OperationParameter] = []
    for name, definition in value.items():
        if (
            not isinstance(name, str)
            or not name.isidentifier()
            or not isinstance(definition, Mapping)
        ):
            raise ProjectConfigError(
                f"{field} contains an invalid parameter declaration"
            )
        kind = definition.get("type")
        if kind not in {
            "bool",
            "string",
            "enum",
            "integer",
            "string-list",
            "enum-list",
        }:
            raise ProjectConfigError(f"{field}.{name} has an invalid type")
        has_flag = "flag" in definition
        has_position = "position" in definition
        if has_flag == has_position:
            raise ProjectConfigError(
                f"{field}.{name} must declare exactly one flag or position"
            )
        flag: str | None = None
        position: int | None = None
        required = False
        if has_flag:
            flag = definition.get("flag")
            if not isinstance(flag, str) or _PARAMETER_FLAG.fullmatch(flag) is None:
                raise ProjectConfigError(f"{field}.{name} has an invalid flag")
            required = definition.get("required", False)
            if not isinstance(required, bool):
                raise ProjectConfigError(f"{field}.{name} required must be boolean")
        else:
            position = definition.get("position")
            required = definition.get("required")
            if (
                kind not in {"string", "enum", "integer"}
                or not isinstance(position, int)
                or isinstance(position, bool)
                or not 1 <= position <= MAX_OPERATION_PARAMETERS
                or required is not True
            ):
                raise ProjectConfigError(
                    f"{field}.{name} has an invalid required positional declaration"
                )
        mapping_fields = (
            {"flag", "required"}
            if flag is not None and "required" in definition
            else {"flag"} if flag is not None else {"position", "required"}
        )
        if kind == "bool":
            if set(definition) != {"type", *mapping_fields}:
                raise ProjectConfigError(
                    f"{field}.{name} bool parameters only accept type and flag"
                )
            parameters.append(OperationParameter(name=name, kind=kind, flag=flag))
            continue
        if kind == "integer":
            if set(definition) != {"type", *mapping_fields, "min", "max"}:
                raise ProjectConfigError(
                    f"{field}.{name} integer parameters require min and max"
                )
            minimum = definition.get("min")
            maximum = definition.get("max")
            if (
                not isinstance(minimum, int)
                or isinstance(minimum, bool)
                or not isinstance(maximum, int)
                or isinstance(maximum, bool)
                or not MIN_PARAMETER_INTEGER
                <= minimum
                <= maximum
                <= MAX_PARAMETER_INTEGER
            ):
                raise ProjectConfigError(f"{field}.{name} has invalid integer bounds")
            parameters.append(
                OperationParameter(
                    name=name,
                    kind=kind,
                    flag=flag,
                    position=position,
                    required=required,
                    minimum=minimum,
                    maximum=maximum,
                )
            )
            continue
        if kind in {"enum", "enum-list"}:
            allowed = {"type", *mapping_fields, "values"}
            if kind == "enum-list":
                allowed.add("max_items")
            if set(definition) != allowed:
                raise ProjectConfigError(
                    f"{field}.{name} {kind} parameters require declared values and bounds"
                )
            values = definition.get("values")
            if (
                not isinstance(values, list)
                or not 1 <= len(values) <= MAX_PARAMETER_ENUM_VALUES
            ):
                raise ProjectConfigError(
                    f"{field}.{name} must declare bounded enum values"
                )
            if any(
                not isinstance(item, str)
                or not item
                or len(item) > MAX_PARAMETER_STRING_LENGTH
                or _PARAMETER_GRAMMARS[DEFAULT_PARAMETER_GRAMMAR].fullmatch(item)
                is None
                for item in values
            ) or len(set(values)) != len(values):
                raise ProjectConfigError(
                    f"{field}.{name} has invalid or duplicate enum values"
                )
            max_items = None
            if kind == "enum-list":
                max_items = definition.get("max_items")
                if not _bounded_parameter_count(max_items, MAX_PARAMETER_LIST_ITEMS):
                    raise ProjectConfigError(f"{field}.{name} has invalid list bounds")
            parameters.append(
                OperationParameter(
                    name=name,
                    kind=kind,
                    flag=flag,
                    position=position,
                    required=required,
                    max_items=max_items,
                    max_length=MAX_PARAMETER_STRING_LENGTH,
                    grammar=DEFAULT_PARAMETER_GRAMMAR,
                    values=tuple(values),
                )
            )
            continue
        allowed = {"type", *mapping_fields, "max_length", "grammar"}
        if kind == "string-list":
            allowed.add("max_items")
        if set(definition) != allowed - {"grammar"} and set(definition) != allowed:
            raise ProjectConfigError(
                f"{field}.{name} {kind} parameters require explicit bounds"
            )
        max_length = definition.get("max_length")
        grammar = definition.get("grammar", DEFAULT_PARAMETER_GRAMMAR)
        if (
            not _bounded_parameter_count(max_length, MAX_PARAMETER_STRING_LENGTH)
            or not isinstance(grammar, str)
            or grammar not in _PARAMETER_GRAMMARS
        ):
            raise ProjectConfigError(f"{field}.{name} has invalid string constraints")
        max_items = None
        if kind == "string-list":
            max_items = definition.get("max_items")
            if not _bounded_parameter_count(max_items, MAX_PARAMETER_LIST_ITEMS):
                raise ProjectConfigError(f"{field}.{name} has invalid list bounds")
        parameters.append(
            OperationParameter(
                name=name,
                kind=kind,
                flag=flag,
                position=position,
                required=required,
                max_items=max_items,
                max_length=max_length,
                grammar=grammar,
            )
        )
    flags = [parameter.flag for parameter in parameters if parameter.flag is not None]
    if len(set(flags)) != len(flags):
        raise ProjectConfigError(f"{field} parameter flags must be unique")
    positions = [
        parameter.position for parameter in parameters if parameter.position is not None
    ]
    if len(set(positions)) != len(positions):
        raise ProjectConfigError(
            f"{field} positional parameter positions must be unique"
        )
    if positions and set(positions) != set(range(1, len(positions) + 1)):
        raise ProjectConfigError(
            f"{field} positional parameter positions must be contiguous from 1"
        )
    return tuple(parameters)


def _operation_service(value: Any, field: str) -> OperationService | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {
        "readiness",
        "lifetime",
        "ports",
    }:
        raise ProjectConfigError(
            f"{field} must contain only readiness, lifetime, and ports"
        )
    readiness = value.get("readiness")
    lifetime = value.get("lifetime")
    ports = value.get("ports")
    if readiness not in {"none", "project-command"}:
        raise ProjectConfigError(f"{field}.readiness is invalid")
    if lifetime != "job":
        raise ProjectConfigError(f"{field}.lifetime is invalid")
    if not isinstance(ports, Mapping) or not 1 <= len(ports) <= MAX_SERVICE_PORT_SLOTS:
        raise ProjectConfigError(f"{field}.ports must be a bounded table")
    slots: list[ServicePortSlot] = []
    environments: set[str] = set()
    for name, definition in sorted(ports.items()):
        if (
            not isinstance(name, str)
            or _SERVICE_PORT_SLOT.fullmatch(name) is None
            or not isinstance(definition, Mapping)
            or set(definition) != {"environment", "range"}
        ):
            raise ProjectConfigError(f"{field}.ports contains an invalid slot")
        environment = definition.get("environment")
        port_range = definition.get("range")
        if (
            not isinstance(environment, str)
            or _SERVICE_ENVIRONMENT.fullmatch(environment) is None
            or environment.startswith("SINNIXD_")
            or environment in environments
        ):
            raise ProjectConfigError(f"{field}.ports.{name}.environment is invalid")
        if (
            not isinstance(port_range, list)
            or len(port_range) != 2
            or any(
                not isinstance(port, int) or isinstance(port, bool)
                for port in port_range
            )
        ):
            raise ProjectConfigError(f"{field}.ports.{name}.range is invalid")
        minimum, maximum = port_range
        if (
            not 1024 <= minimum <= maximum <= 65535
            or maximum - minimum + 1 > MAX_SERVICE_PORT_RANGE
        ):
            raise ProjectConfigError(f"{field}.ports.{name}.range is invalid")
        environments.add(environment)
        slots.append(
            ServicePortSlot(
                name=name, environment=environment, minimum=minimum, maximum=maximum
            )
        )
    return OperationService(readiness=readiness, lifetime=lifetime, ports=tuple(slots))


def _bounded_parameter_count(value: Any, maximum: int) -> bool:
    return (
        isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= maximum
    )


def _owner_adapters(
    raw: Mapping[str, Any], descriptor: Path
) -> tuple[ProjectOwnerAdapter, ...]:
    definitions = raw.get("owner_adapters", {})
    if not isinstance(definitions, Mapping):
        raise ProjectConfigError(f"{descriptor} [owner_adapters] must be a table")
    adapters: list[ProjectOwnerAdapter] = []
    for name, definition in sorted(definitions.items()):
        if (
            not isinstance(name, str)
            or not name.isidentifier()
            or not isinstance(definition, Mapping)
        ):
            raise ProjectConfigError(
                f"{descriptor} contains an invalid owner adapter declaration"
            )
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
            raise ProjectConfigError(
                f"owner_adapters.{name} requires namespace and owner"
            )
        if not isinstance(documentation, str):
            raise ProjectConfigError(
                f"owner_adapters.{name}.documentation must be a string"
            )
        if (
            not isinstance(versions, list)
            or not versions
            or any(
                not isinstance(version, int) or isinstance(version, bool)
                for version in versions
            )
        ):
            raise ProjectConfigError(
                f"owner_adapters.{name}.protocol_versions must be non-empty integers"
            )
        if definition.get("source_scoped") is not True:
            raise ProjectConfigError(
                f"owner_adapters.{name} must declare source_scoped = true"
            )
        source_ref = definition.get("source_ref")
        if not isinstance(source_ref, str):
            raise ProjectConfigError(
                f"owner_adapters.{name}.source_ref must be a string"
            )
        timeout_seconds = definition.get("timeout_seconds", 30)
        if (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or not 1 <= timeout_seconds <= 300
        ):
            raise ProjectConfigError(
                f"owner_adapters.{name}.timeout_seconds must be between 1 and 300"
            )
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
            raise ProjectConfigError(
                f"owner_adapters.{name} is invalid: {error}"
            ) from error
        adapters.append(
            ProjectOwnerAdapter(
                spec=spec,
                command=_string_list(
                    definition.get("exec"), f"owner_adapters.{name}.exec"
                ),
                source_ref=parsed_source_ref,
                timeout_seconds=timeout_seconds,
            )
        )
    try:
        OwnerRegistry(adapter.spec for adapter in adapters)
    except ValueError as error:
        raise ProjectConfigError(
            f"{descriptor} owner adapters overlap: {error}"
        ) from error
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
        raise ProjectConfigError(
            f"invalid project adapter {descriptor}: {error}"
        ) from error
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

    environment = raw.get("environment")
    if not isinstance(environment, Mapping):
        raise ProjectConfigError(f"{descriptor} requires an [environment] table")
    environment_kind = environment.get("kind")
    if not isinstance(environment_kind, str) or not environment_kind:
        raise ProjectConfigError(f"{descriptor} environment.kind must be non-empty")
    execution_environment = ProjectEnvironment(
        kind=environment_kind,
        command=_string_list(environment.get("command"), "environment.command"),
        inherit=_optional_string_list(
            environment.get("inherit"), "environment.inherit"
        ),
        unset=_optional_string_list(environment.get("unset"), "environment.unset"),
        preflight=(
            _string_list(environment["preflight"], "environment.preflight")
            if "preflight" in environment
            else ()
        ),
    )

    raw_workspace = raw.get("workspace")
    workspace: WorkspacePolicy | None = None
    if raw_workspace is not None:
        if not isinstance(raw_workspace, Mapping):
            raise ProjectConfigError(f"{descriptor} [workspace] must be a table")
        allowed_workspace = {
            "provider",
            "root",
            "default_base",
            "identity_check",
            "checkpoint_untracked",
            "verification_operations",
        }
        if set(raw_workspace) - allowed_workspace:
            raise ProjectConfigError(
                f"{descriptor} [workspace] contains unknown fields"
            )
        provider = raw_workspace.get("provider")
        workspace_root = raw_workspace.get("root")
        default_base = raw_workspace.get("default_base")
        checkpoint_untracked = raw_workspace.get("checkpoint_untracked")
        if provider != "git-worktree":
            raise ProjectConfigError(
                f"{descriptor} workspace.provider must be git-worktree"
            )
        if (
            not isinstance(workspace_root, str)
            or not Path(workspace_root).is_absolute()
        ):
            raise ProjectConfigError(
                f"{descriptor} workspace.root must be an absolute path"
            )
        if not isinstance(default_base, str) or not default_base:
            raise ProjectConfigError(
                f"{descriptor} workspace.default_base must be non-empty"
            )
        if not isinstance(checkpoint_untracked, bool):
            raise ProjectConfigError(
                f"{descriptor} workspace.checkpoint_untracked must be boolean"
            )
        workspace = WorkspacePolicy(
            provider=provider,
            root=Path(workspace_root),
            default_base=default_base,
            identity_check=_string_list(
                raw_workspace.get("identity_check"), "workspace.identity_check"
            ),
            checkpoint_untracked=checkpoint_untracked,
            verification_operations=_optional_string_list(
                raw_workspace.get("verification_operations"),
                "workspace.verification_operations",
            ),
        )

    raw_conflicts = raw.get("conflicts", {})
    if not isinstance(raw_conflicts, Mapping) or set(raw_conflicts) - {
        "exact_files",
        "generated_surfaces",
        "semantic_slots",
    }:
        raise ProjectConfigError(f"{descriptor} [conflicts] is invalid")
    raw_semantic_slots = raw_conflicts.get("semantic_slots", {})
    if isinstance(raw_semantic_slots, list):
        semantic_slots = dict.fromkeys(
            _optional_string_list(raw_semantic_slots, "conflicts.semantic_slots"), ()
        )
    elif isinstance(raw_semantic_slots, Mapping) and all(
        isinstance(name, str) and name for name in raw_semantic_slots
    ):
        semantic_slots = {
            name: _string_list(paths, f"conflicts.semantic_slots.{name}")
            for name, paths in sorted(raw_semantic_slots.items())
        }
    else:
        raise ProjectConfigError(f"{descriptor} conflicts.semantic_slots is invalid")
    conflicts = ConflictPolicy(
        exact_files=_optional_string_list(
            raw_conflicts.get("exact_files"), "conflicts.exact_files"
        ),
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
        if (
            not isinstance(name, str)
            or not name.isidentifier()
            or not isinstance(definition, Mapping)
        ):
            raise ProjectConfigError(
                f"{descriptor} contains an invalid operation declaration"
            )
        allowed_operation = {
            "description",
            "exec",
            "pool",
            "result",
            "cache",
            "exclusive_keys",
            "dependencies",
            "estimate_memory_bytes",
            "scratch",
            "parameters",
            "timeout_seconds",
            "service",
            "plan_node",
        }
        if set(definition) - allowed_operation:
            raise ProjectConfigError(
                f"{descriptor} operation {name} contains unknown fields"
            )
        description = definition.get("description")
        if not isinstance(description, str) or not description:
            raise ProjectConfigError(
                f"{descriptor} operation {name} requires description"
            )
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
        timeout_seconds = definition.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
        if not valid_timeout_seconds(timeout_seconds, kind="declared-operation"):
            raise ProjectConfigError(
                f"operations.{name}.timeout_seconds must be between 1 and "
                f"{MAX_DECLARED_OPERATION_TIMEOUT_SECONDS}"
            )
        dependencies = _optional_string_list(
            definition.get("dependencies"), f"operations.{name}.dependencies"
        )
        if name in dependencies or len(set(dependencies)) != len(dependencies):
            raise ProjectConfigError(f"operations.{name}.dependencies is invalid")
        estimate_memory_bytes = definition.get("estimate_memory_bytes")
        if estimate_memory_bytes is not None and (
            not isinstance(estimate_memory_bytes, int)
            or isinstance(estimate_memory_bytes, bool)
            or not 1 <= estimate_memory_bytes <= 128 * 1024 * 1024 * 1024
        ):
            raise ProjectConfigError(
                f"operations.{name}.estimate_memory_bytes is invalid"
            )
        scratch = definition.get("scratch", "none")
        if scratch not in {"none", "tmpfs", "nvme"}:
            raise ProjectConfigError(f"operations.{name}.scratch is invalid")
        service = _operation_service(
            definition.get("service"), f"operations.{name}.service"
        )
        plan_node = definition.get("plan_node", False)
        if not isinstance(plan_node, bool):
            raise ProjectConfigError(f"operations.{name}.plan_node is invalid")
        operations.append(
            ProjectOperation(
                name=name,
                description=description,
                command=command,
                pool=pool,
                result=result,
                cache=cache,
                timeout_seconds=timeout_seconds,
                exclusive_keys=_optional_string_list(
                    definition.get("exclusive_keys"),
                    f"operations.{name}.exclusive_keys",
                ),
                dependencies=dependencies,
                estimate_memory_bytes=estimate_memory_bytes,
                scratch=scratch,
                parameters=_operation_parameters(
                    definition.get("parameters"), f"operations.{name}.parameters"
                ),
                service=service,
                plan_node=plan_node,
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
            f"{descriptor} operation dependency/dependencies are undeclared: "
            + ", ".join(sorted(unknown_dependencies))
        )
    required_parameter_operations = {
        operation.name
        for operation in operations
        if any(parameter.required for parameter in operation.parameters)
    }
    invalid_parameter_dependencies = {
        dependency
        for operation in operations
        for dependency in operation.dependencies
        if dependency in required_parameter_operations
    }
    if invalid_parameter_dependencies:
        raise ProjectConfigError(
            f"{descriptor} operation dependencies cannot target operations with required parameters: "
            + ", ".join(sorted(invalid_parameter_dependencies))
        )
    invalid_required_parameter_operations = {
        operation.name
        for operation in operations
        if operation.dependencies and operation.name in required_parameter_operations
    }
    if invalid_required_parameter_operations:
        raise ProjectConfigError(
            f"{descriptor} operations with required parameters cannot declare dependencies: "
            + ", ".join(sorted(invalid_required_parameter_operations))
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
        return [
            self._adapters[project_id].catalog_row()
            for project_id in sorted(self._adapters)
        ]

    def get(self, project_id: str) -> ProjectAdapter:
        try:
            return self._adapters[project_id]
        except KeyError as error:
            raise KeyError(f"unknown project: {project_id}") from error

    @staticmethod
    def _git(path: Path, *arguments: str) -> str:
        return _checkout_git(path, *arguments)

    @staticmethod
    def _checkout_id(path: Path, configured_root: Path) -> str:
        return _registered_checkout_id(path, configured_root)

    def checkouts(self, project_id: str) -> tuple[RegisteredCheckout, ...]:
        project = self.get(project_id)
        root = project.root.resolve(strict=True)
        records = parse_worktree_records(
            self._git(root, "worktree", "list", "--porcelain")
        )
        checkouts: list[RegisteredCheckout] = []
        for record in records:
            raw_path = record.get("worktree")
            head = record.get("HEAD")
            if raw_path is None or head is None:
                raise ProjectConfigError(
                    "git worktree record is missing worktree or HEAD"
                )
            path = Path(raw_path).resolve(strict=True)
            top_level = Path(
                self._git(path, "rev-parse", "--show-toplevel").strip()
            ).resolve(strict=True)
            common_dir = Path(
                self._git(
                    path, "rev-parse", "--path-format=absolute", "--git-common-dir"
                ).strip()
            ).resolve(strict=True)
            if top_level != path:
                raise ProjectConfigError(
                    "registered checkout has a non-canonical worktree root"
                )
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
        if not any(
            checkout.checkout_id == "default" and checkout.path == root
            for checkout in checkouts
        ):
            raise ProjectConfigError(
                "configured project root is not a registered Git worktree"
            )
        return tuple(
            sorted(
                checkouts,
                key=lambda checkout: (
                    checkout.checkout_id != "default",
                    checkout.checkout_id,
                ),
            )
        )

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
            raise ProjectConfigError(
                f"project owner adapters overlap: {error}"
            ) from error
        return adapters

    def owner_adapter(
        self, operation: str
    ) -> tuple[ProjectAdapter, ProjectOwnerAdapter]:
        registry = OwnerRegistry(adapter.spec for adapter in self.owner_adapters())
        spec = registry.resolve(operation)
        for project in self._adapters.values():
            for adapter in project.owner_adapters:
                if adapter.spec == spec:
                    return project, adapter
        raise KeyError(f"no project owner adapter for {operation!r}")


def validate_agent_environment_descriptors(roots: Iterable[Path]) -> None:
    """Require a declared command and preflight for every checkout-capable project."""
    diagnostics: list[str] = []
    for root in roots:
        descriptor = root / ".agentctl" / "project.toml"
        project_name = str(root)
        try:
            raw = tomllib.loads(descriptor.read_text())
            project = raw.get("project")
            if isinstance(project, Mapping) and isinstance(project.get("id"), str):
                project_name = project["id"]
            if isinstance(raw.get("workspace"), Mapping):
                environment = raw.get("environment")
                command = (
                    environment.get("command")
                    if isinstance(environment, Mapping)
                    else None
                )
                preflight = (
                    environment.get("preflight")
                    if isinstance(environment, Mapping)
                    else None
                )
                invalid_environment = False
                if not (
                    isinstance(command, list)
                    and command
                    and all(isinstance(value, str) and value for value in command)
                ):
                    diagnostics.append(
                        f"{project_name}: {descriptor} must declare a non-empty environment.command"
                    )
                    invalid_environment = True
                if not (
                    isinstance(preflight, list)
                    and preflight
                    and all(isinstance(value, str) and value for value in preflight)
                ):
                    diagnostics.append(
                        f"{project_name}: {descriptor} must declare a non-empty environment.preflight"
                    )
                    invalid_environment = True
                if invalid_environment:
                    continue
            adapter = load_project_adapter(root)
        except (
            OSError,
            UnicodeDecodeError,
            tomllib.TOMLDecodeError,
            ProjectConfigError,
        ) as error:
            diagnostics.append(
                f"{project_name}: invalid descriptor {descriptor}: {error}"
            )
            continue
        if not adapter.agent_capable:
            continue
    if diagnostics:
        raise ProjectConfigError(
            "agent-capable project environment contract failed:\n"
            + "\n".join(f"- {diagnostic}" for diagnostic in diagnostics)
        )


def project_environment_check_main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnixd-project-environment-check")
    parser.add_argument("--project-root", type=Path, action="append", required=True)
    args = parser.parse_args(arguments)
    try:
        validate_agent_environment_descriptors(args.project_root)
    except ProjectConfigError as error:
        parser.error(str(error))
    return 0
