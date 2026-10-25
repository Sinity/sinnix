"""Project descriptors: the one thing agentctl owns outright.

A descriptor (`.agentctl/project.toml`) declares what a project's operations
mean — argv, pool, result contract, timeout, checkout policy — and
how to enter its environment. Everything else (queueing, worktrees, review,
tasks) belongs to pueue, worktrunk, GitHub and Beads.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import tomllib

from .environment import build_environment
from .launch_input import CAP_NAME, supported_unit_property
from .limits import (
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
CACHE_KINDS = frozenset({"none", "tree+environment"})
# Where an operation's job-owned scratch directory lives: nowhere, in RAM, or
# on disk. `run` owns the roots and the removal.
SCRATCH_KINDS = frozenset({"none", "tmpfs", "nvme"})
# Whether `job start` may be invoked with extra argv. `required` is a
# declaration that the operation cannot execute without a caller-supplied
# selector. Callers pass the selector explicitly after the operation name.
ARGUMENTS_KINDS = frozenset({"none", "required"})

_TABLES = frozenset({"schema", "project", "environment", "workspace", "operations"})
_ENVIRONMENT_FIELDS = frozenset(
    {"kind", "command", "inherit", "unset", "values", "require", "cache_inputs"}
)
# The one environment kind whose realization agentctl-devenv can cache.
NIX_DEVELOP_KIND = "nix-develop"
DEVENV_COMMAND = "agentctl-devenv"
_WORKSPACE_FIELDS = frozenset({"root", "default_base", "retain_artifacts"})


def _warn_unknown(descriptor: Path, table: str, unknown: set[str]) -> None:
    """A field this agentctl does not read is ignored, never a reason to take
    the project out of service: a descriptor written for a newer agentctl
    must keep existing native operations available."""
    if unknown:
        print(
            f"agentctl: {descriptor} {table} ignores unknown fields: "
            + ", ".join(sorted(unknown)),
            file=sys.stderr,
        )


_OPERATION_FIELDS = frozenset(
    {
        "description",
        "exec",
        "pool",
        "result",
        "timeout_seconds",
        "checkout",
        "cache",
        "scratch",
        "arguments",
        "admission",
        "unit_properties",
        "cap",
        "max_io_pressure",
    }
)

#: Which tree an operation runs in; `checkout.py` states what each means.
CHECKOUT_KINDS = frozenset({"any", "default"})
#: An operation's declared memory envelope, in MiB. One key today; the table
#: exists so a second dimension does not become a second top-level key.
ADMISSION_FIELDS = frozenset({"memory_mib"})
#: A declared envelope larger than this is a typo, not a workload: no pool
#: slice on this workstation is declared anywhere near it.
MAX_ADMISSION_MEMORY_MIB = 64 * 1024


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
    # Repository-relative files and directories the devShell evaluation reads.
    # When declared, jobs enter a cached `nix print-dev-env` realization keyed
    # on them instead of re-evaluating (and re-copying a dirty tree) per job.
    cache_inputs: tuple[str, ...] = ()

    def values(self, *, host_values: Mapping[str, str] | None = None) -> dict[str, str]:
        """Resolve the launch environment; a missing required variable fails loudly.

        Inherited names absent from the caller's environment are dropped
        silently; ``require`` names the ones whose absence is a defect.
        """
        # Host-owned inherited values must come from the current declaration,
        # not an agent session started before a path migration. Explicit
        # descriptor values still select custom deployments.
        source = dict(os.environ)
        source.update(host_values or {})
        environment = build_environment(
            inherit=self.inherit,
            unset=self.unset,
            values=dict(self.declared),
            source=source,
        )
        missing = sorted(name for name in self.require if name not in environment)
        if missing:
            raise ProjectEnvironmentError(
                "required environment variable(s) unavailable: "
                + ", ".join(missing)
                + " (declare a value under [environment.values] or export them)"
            )
        # Git status and similar reads must not refresh the index. A killed
        # read therefore cannot strand an index.lock in a shared checkout;
        # required locks for Git mutations remain unaffected.
        environment["GIT_OPTIONAL_LOCKS"] = "0"
        return environment

    def command_for(self, payload: Sequence[str]) -> tuple[str, ...]:
        """Enter the project environment around ``payload``."""
        if self.cache_inputs:
            inputs = (f"--input={item}" for item in self.cache_inputs)
            return (DEVENV_COMMAND, *inputs, "--", *payload)
        return (*self.command, *payload)

    def catalog_row(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "command": list(self.command),
            "declared": sorted(name for name, _value in self.declared),
            "require": list(self.require),
            "cache_inputs": list(self.cache_inputs),
        }


@dataclass(frozen=True)
class WorkspacePolicy:
    """Filesystem placement and artifact custody for preserved checkouts."""

    root: Path
    default_base: str
    retain_artifacts: tuple[str, ...] = ()

    def catalog_row(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "default_base": self.default_base,
            "retain_artifacts": list(self.retain_artifacts),
        }


@dataclass(frozen=True)
class AdmissionEnvelope:
    """What an operation says it expects to need, to compare a measurement to.

    The measured side already exists wherever a workload sizes itself -- a
    Polylogue sizing receipt carries a predicted charge, a budget, and its
    margin. The declared side did not, so there was nothing on this side of
    the boundary to compare those numbers against, and a workload wanting the
    pool's ceiling could only mirror the number by hand from Sinnix's slice
    definition.

    This is a declaration, not a limit. agentctl records it on the job and
    exports it to the command; it does not impose a unit `MemoryMax` from it,
    because silently throttling an operation at a number someone wrote in a
    descriptor is a different decision from letting it state what it expects.
    """

    memory_mib: int

    def catalog_row(self) -> dict[str, Any]:
        return {"memory_mib": self.memory_mib}


@dataclass(frozen=True)
class ProjectOperation:
    name: str
    description: str
    command: tuple[str, ...]
    pool: str = "normal"
    result: str = "exit"
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    # Which tree the operation runs in: `any` (the caller's) or `default`
    # (only the project root).
    checkout: str = "any"
    cache: str = "none"
    scratch: str = "none"
    arguments: str = "none"
    admission: AdmissionEnvelope | None = None
    unit_properties: tuple[str, ...] = ()
    # A host-declared cap shared across pools: at most that many jobs naming
    # it run at once, whichever pools they queue in.
    cap: str | None = None
    # Refuse to start while host I/O `full avg60` exceeds this percentage,
    # for measurements whose numbers would be invalid under load.
    max_io_pressure: float | None = None

    def catalog_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "command": list(self.command),
            "pool": self.pool,
            "result": self.result,
            "timeout_seconds": self.timeout_seconds,
            "checkout": self.checkout,
            "cache": self.cache,
            "scratch": self.scratch,
            "arguments": self.arguments,
            "admission": self.admission.catalog_row() if self.admission else None,
            "unit_properties": list(self.unit_properties),
            "cap": self.cap,
            "max_io_pressure": self.max_io_pressure,
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
    _warn_unknown(descriptor, "[environment]", set(environment) - _ENVIRONMENT_FIELDS)
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
    cache_inputs = _optional_string_list(
        environment.get("cache_inputs"), "environment.cache_inputs"
    )
    if cache_inputs and kind != NIX_DEVELOP_KIND:
        raise ProjectConfigError(
            f"{descriptor} environment.cache_inputs applies only to kind {NIX_DEVELOP_KIND!r}"
        )
    if any(
        Path(item).is_absolute() or ".." in Path(item).parts for item in cache_inputs
    ):
        raise ProjectConfigError(
            f"{descriptor} environment.cache_inputs must be repository-relative paths"
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
        cache_inputs=cache_inputs,
    )


def _workspace(raw: Mapping[str, Any], descriptor: Path) -> WorkspacePolicy | None:
    raw_workspace = raw.get("workspace")
    if raw_workspace is None:
        return None
    if not isinstance(raw_workspace, Mapping):
        raise ProjectConfigError(f"{descriptor} [workspace] must be a table")
    _warn_unknown(descriptor, "[workspace]", set(raw_workspace) - _WORKSPACE_FIELDS)
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
    if "retain_artifacts" in raw_workspace:
        patterns = _optional_string_list(
            raw_workspace["retain_artifacts"], "workspace.retain_artifacts"
        )
        for pattern in patterns:
            path = Path(pattern)
            if path.is_absolute() or ".." in path.parts:
                raise ProjectConfigError(
                    f"{descriptor} workspace.retain_artifacts must be relative"
                )
        fields["retain_artifacts"] = patterns
    return WorkspacePolicy(root=Path(root), default_base=default_base, **fields)


def _admission(name: str, definition: Any, descriptor: Path) -> AdmissionEnvelope:
    if not isinstance(definition, Mapping):
        raise ProjectConfigError(f"operations.{name}.admission must be a table")
    _warn_unknown(
        descriptor,
        f"operation {name} admission",
        set(definition) - ADMISSION_FIELDS,
    )
    memory_mib = definition.get("memory_mib")
    if (
        not isinstance(memory_mib, int)
        or isinstance(memory_mib, bool)
        or not 1 <= memory_mib <= MAX_ADMISSION_MEMORY_MIB
    ):
        raise ProjectConfigError(
            f"operations.{name}.admission.memory_mib must be an integer between "
            f"1 and {MAX_ADMISSION_MEMORY_MIB}"
        )
    return AdmissionEnvelope(memory_mib=memory_mib)


def _operation(name: str, definition: Any, descriptor: Path) -> ProjectOperation:
    if not name.isidentifier() or not isinstance(definition, Mapping):
        raise ProjectConfigError(
            f"{descriptor} contains an invalid operation declaration: {name}"
        )
    _warn_unknown(descriptor, f"operation {name}", set(definition) - _OPERATION_FIELDS)
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
                f"operations.{name}.timeout_seconds must be 0 (no runtime deadline) or between 1 and "
                f"{MAX_DECLARED_OPERATION_TIMEOUT_SECONDS}"
            )
        fields["timeout_seconds"] = timeout_seconds
    if "checkout" in definition:
        if definition["checkout"] not in CHECKOUT_KINDS:
            raise ProjectConfigError(f"operations.{name}.checkout is invalid")
        fields["checkout"] = definition["checkout"]
    if "admission" in definition:
        fields["admission"] = _admission(name, definition["admission"], descriptor)
    properties = _optional_string_list(
        definition.get("unit_properties"), f"operations.{name}.unit_properties"
    )
    if not all(supported_unit_property(value) for value in properties):
        raise ProjectConfigError(
            f"operations.{name}.unit_properties must contain supported task resource or path limits"
        )
    fields["unit_properties"] = properties
    if "cache" in definition:
        if definition["cache"] not in CACHE_KINDS:
            raise ProjectConfigError(f"operations.{name}.cache is invalid")
        fields["cache"] = definition["cache"]
    if "scratch" in definition:
        if definition["scratch"] not in SCRATCH_KINDS:
            raise ProjectConfigError(f"operations.{name}.scratch is invalid")
        fields["scratch"] = definition["scratch"]
    if "arguments" in definition:
        if definition["arguments"] not in ARGUMENTS_KINDS:
            raise ProjectConfigError(f"operations.{name}.arguments is invalid")
        fields["arguments"] = definition["arguments"]
    if "cap" in definition:
        cap = definition["cap"]
        if not isinstance(cap, str) or not CAP_NAME.fullmatch(cap):
            raise ProjectConfigError(f"operations.{name}.cap is invalid")
        fields["cap"] = cap
    if "max_io_pressure" in definition:
        limit = definition["max_io_pressure"]
        if (
            not isinstance(limit, (int, float))
            or isinstance(limit, bool)
            or not 0 <= limit <= 100
        ):
            raise ProjectConfigError(
                f"operations.{name}.max_io_pressure must be a percentage between 0 and 100"
            )
        fields["max_io_pressure"] = float(limit)
    return ProjectOperation(
        name=name,
        description=description,
        command=command,
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
    workspace = _workspace(raw, descriptor)
    return ProjectAdapter(
        project_id=project_id,
        display_name=display_name,
        root=root,
        descriptor=descriptor,
        digest="sha256:" + hashlib.sha256(raw_bytes).hexdigest(),
        environment=_environment(raw, descriptor),
        workspace=workspace,
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
