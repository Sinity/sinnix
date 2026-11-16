"""Shared fixtures: the evaluated policy file relocated into a scratch tree.

`SINNIX_BACKUP_FIXTURE_CONFIG` names /etc/sinnix/backup.json as Nix renders
it for the fixture host in flake/tests/backup.nix, so tests read the same
schema and values production does. Every absolute path in it, and every
root-qualified Borg exclusion, moves under the test's scratch root.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from sinnix_backup.config import BackupConfig, parse_config

FIXTURE_CONFIG = os.environ.get("SINNIX_BACKUP_FIXTURE_CONFIG")


def relocate(value: Any, root: Path) -> Any:
    """Move absolute paths (and file:// URLs) under `root`, recursively."""
    if isinstance(value, dict):
        relocated = {key: relocate(item, root) for key, item in value.items()}
        if "borg_excludes" in relocated:
            prefix = str(root).lstrip("/")
            relocated["borg_excludes"] = [
                pattern if pattern.startswith("**") else f"{prefix}/{pattern}"
                for pattern in value["borg_excludes"]
            ]
        return relocated
    if isinstance(value, list):
        return [relocate(item, root) for item in value]
    if isinstance(value, str):
        if value.startswith("file:///"):
            return "file://" + str(root) + value[len("file://") :]
        if value.startswith("/"):
            return str(root) + value
    return value


def fixture_config_data(root: Path) -> dict[str, Any]:
    if FIXTURE_CONFIG is None:
        pytest.skip("SINNIX_BACKUP_FIXTURE_CONFIG names no evaluated policy file")
    return relocate(json.loads(Path(FIXTURE_CONFIG).read_text()), root)


def write_fixture_config(root: Path, data: dict[str, Any] | None = None) -> tuple[Path, BackupConfig]:
    """Write the relocated policy to root/backup.json; create its parent directories."""
    data = fixture_config_data(root) if data is None else data
    path = root / "backup.json"
    path.write_text(json.dumps(data))
    config = parse_config(data)
    for directory in (
        config.state_directory,
        config.lock_path.parent,
        config.cache_directory,
        config.scratch_directory,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    # Jobs that create their repository use repokey encryption.
    config.passphrase_path.parent.mkdir(parents=True, exist_ok=True)
    config.passphrase_path.write_text("synthetic fixture passphrase\n")
    return path, config


@pytest.fixture
def backup_root(tmp_path: Path) -> Path:
    return tmp_path.resolve()


@pytest.fixture
def fixture_config(backup_root: Path) -> tuple[Path, BackupConfig]:
    return write_fixture_config(backup_root)
