"""Execution artifacts, independent of pueue's mutable task positions.

Directories are allocated once per invocation. Compatibility names point at the
latest invocation; canonical paths never change or get reused by a retry.
"""

from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .launch_input import write_input

CANONICAL_NAMES = {
    "log": "output.log",
    "result": "output.result",
    "outcome": "output.outcome",
}


def root_for(log: Path) -> Path:
    return log.with_suffix(".attempts")


def paths_for(launch: Mapping[str, Any]) -> dict[str, Path]:
    log = Path(launch["log_path"])
    stem = log.name[:-4] if log.name.endswith(".log") else log.name
    paths = {"log": log, "outcome": log.with_name(stem + ".outcome")}
    if launch.get("result_path"):
        paths["result"] = Path(launch["result_path"])
    return paths


def attempts(launch: Mapping[str, Any]) -> list[dict[str, Any]]:
    paths = paths_for(launch)
    root = root_for(paths["log"])
    directories = sorted(
        (path for path in root.glob("[0-9]*") if path.is_dir() and path.name.isdigit()),
        key=lambda path: int(path.name),
    )
    if not directories:
        return (
            [
                {
                    "attempt": 1,
                    "legacy": True,
                    "artifacts": {key: str(path) for key, path in paths.items()},
                }
            ]
            if any(path.exists() for path in paths.values())
            else []
        )
    return [
        {
            "attempt": int(directory.name),
            "legacy": False,
            "artifacts": {key: str(directory / CANONICAL_NAMES[key]) for key in paths},
        }
        for directory in directories
    ]


def begin(launch: Mapping[str, Any], launch_input: str) -> dict[str, Any]:
    """Allocate an invocation, preserving pre-upgrade files before replacing aliases.

    The short allocation lock protects the migration and numbering only. Pueue
    and the wrapper's unit remain the owners of execution and admission.
    """
    paths = paths_for(launch)
    root = root_for(paths["log"])
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    with (root / ".allocation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing = attempts(launch)
        migration = root / ".legacy-migration.json"
        if migration.exists() or (existing and existing[0]["legacy"]):
            if not migration.exists():
                write_input(migration, {key: str(path) for key, path in paths.items()})
            sources = json.loads(migration.read_text())
            directory = root / "1"
            directory.mkdir(mode=0o700, exist_ok=True)
            for key, source in sources.items():
                path = Path(source)
                if path.exists() or path.is_symlink():
                    target = directory / CANONICAL_NAMES[key]
                    if target.exists() or target.is_symlink():
                        raise FileExistsError(
                            f"legacy migration would overwrite {target}"
                        )
                    path.replace(target)
            write_input(directory / "attempt.json", {"attempt": 1, "legacy": True})
            migration.unlink()
            existing = attempts(launch)
        number = max((item["attempt"] for item in existing), default=0) + 1
        directory = root / str(number)
        directory.mkdir(mode=0o700)
        record = {
            "attempt": number,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "launch_input": launch_input,
        }
        write_input(directory / "attempt.json", record)
        current = dict(launch)
        current["attempt"] = number
        for key, path in paths.items():
            target = directory / CANONICAL_NAMES[key]
            alias = path.with_name(path.name + ".latest")
            alias.unlink(missing_ok=True)
            alias.symlink_to(target.absolute())
            os.replace(alias, path)
            if key != "outcome":
                current[key + "_path"] = str(target)
        return current
