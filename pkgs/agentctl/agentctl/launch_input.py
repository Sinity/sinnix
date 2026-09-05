"""The launch input: the private JSON document a queued task is named by.

`launch.enqueue` writes it; `agentctl-run` reads it back and refuses anything
that is not this contract. The path is the only argument the task's command
carries, and a launch input may bound its own unit and nothing else.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .limits import RESULT_KINDS

REQUIRED_FIELDS = (
    "job_id",
    "project_id",
    "operation",
    "argv",
    "environment",
    "working_directory",
    "timeout_seconds",
    "result_kind",
    "log_path",
)
# pueue's group name grammar.
POOL_NAME = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
# The unit settings agentctl passes through to `systemd-run -p`. Each one only
# bounds what the workload may consume or reach, so a launch input can limit
# its own task and nothing else: no capability, no credential, no execution
# setting is reachable from here.
UNIT_PROPERTIES = frozenset(
    {
        "MemoryMax",
        "MemoryHigh",
        "MemorySwapMax",
        "MemoryZSwapMax",
        "TasksMax",
        "CPUWeight",
        "IOWeight",
    }
)
UNIT_PROPERTY_VALUE = re.compile(r"(infinity|[0-9]+[KMGTPE]?)\Z")
# Path settings: one absolute path per property, optionally `-`-prefixed so
# a missing path is ignored. `ReadWritePaths` only re-opens what a
# `ReadOnlyPaths` on a parent closed.
UNIT_PATH_PROPERTIES = frozenset(
    {"InaccessiblePaths", "ReadOnlyPaths", "ReadWritePaths"}
)
UNIT_PATH_VALUE = re.compile(r"-?/[^\x00-\x20:]+\Z")

# A job-owned scratch directory: created before the command, exported as
# `AGENTCTL_SCRATCH`, measured at unit exit and removed. `tmpfs` is RAM,
# `nvme` the scratch filesystem; the environment overrides exist so a test
# owns both roots.
SCRATCH_KINDS = frozenset({"tmpfs", "nvme"})
SCRATCH_ROOTS = {
    "tmpfs": ("AGENTCTL_TMPFS_SCRATCH_ROOT", "/dev/shm/agentctl"),
    "nvme": ("AGENTCTL_NVME_SCRATCH_ROOT", "/realm/tmp/work/agentctl"),
}


class QueueInputError(ValueError):
    """The private launch input is absent, malformed, or not this contract."""


def supported_unit_property(value: object) -> bool:
    """Whether a launch input may set this on its own unit."""
    if not isinstance(value, str):
        return False
    name, separator, size = value.partition("=")
    if not separator:
        return False
    if name in UNIT_PROPERTIES:
        return UNIT_PROPERTY_VALUE.fullmatch(size) is not None
    if name in UNIT_PATH_PROPERTIES:
        return UNIT_PATH_VALUE.fullmatch(size) is not None
    return False


def scratch_root(kind: str) -> Path | None:
    """The directory holding one tier's job-owned scratch, or None for no tier."""
    declared = SCRATCH_ROOTS.get(kind)
    if declared is None:
        return None
    variable, default = declared
    return Path(os.environ.get(variable) or default)


def scratch_path(kind: str, reference: str) -> Path | None:
    """Where the job named ``reference`` owns its scratch under ``kind``'s root."""
    root = scratch_root(kind)
    return root / reference if root is not None else None


def write_input(path: Path, document: Mapping[str, Any]) -> None:
    """Write the document privately (0600, never through a symlink)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        )


def read_input(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise QueueInputError(f"launch input is unreadable: {error}") from error
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise QueueInputError("launch input is not JSON") from error
    if not isinstance(value, dict):
        raise QueueInputError("launch input is not an object")
    missing = [field for field in REQUIRED_FIELDS if field not in value]
    if missing:
        raise QueueInputError(f"launch input omits {', '.join(sorted(missing))}")
    argv = value["argv"]
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(item, str) for item in argv)
    ):
        raise QueueInputError("launch input argv must be a non-empty list of strings")
    environment = value["environment"]
    if not isinstance(environment, dict) or not all(
        isinstance(key, str) and isinstance(item, str)
        for key, item in environment.items()
    ):
        raise QueueInputError("launch input environment must be a string map")
    if value["result_kind"] not in RESULT_KINDS:
        raise QueueInputError(f"unknown result kind: {value['result_kind']!r}")
    timeout = value["timeout_seconds"]
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        raise QueueInputError("launch input timeout_seconds must be a positive integer")
    pool = value.get("pool")
    if pool is not None and (
        not isinstance(pool, str) or POOL_NAME.fullmatch(pool) is None
    ):
        raise QueueInputError("launch input pool must be a lowercase pueue group name")
    properties = value.get("unit_properties")
    if properties is not None and (
        not isinstance(properties, list)
        or not all(supported_unit_property(item) for item in properties)
    ):
        raise QueueInputError(
            "launch input unit_properties must be "
            f"{'/'.join(sorted(UNIT_PROPERTIES | UNIT_PATH_PROPERTIES))} settings"
        )
    scratch = value.get("scratch")
    if scratch is not None:
        if not isinstance(scratch, dict):
            raise QueueInputError("launch input scratch must be an object")
        kind = scratch.get("kind")
        root = scratch_root(kind) if isinstance(kind, str) else None
        if root is None:
            raise QueueInputError(
                f"launch input scratch kind must be one of {sorted(SCRATCH_KINDS)}"
            )
        path = scratch.get("path")
        # The wrapper creates this directory and removes it afterwards, so a
        # path outside the tier's own root is refused rather than trusted.
        if (
            not isinstance(path, str)
            or not PurePosixPath(path).is_absolute()
            or Path(path).parent != root
        ):
            raise QueueInputError(f"launch input scratch path must be under {root}")
    return value
