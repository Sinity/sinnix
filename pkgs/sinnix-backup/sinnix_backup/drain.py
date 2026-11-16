"""Archive one source's queued snapshots, check each archive, then delete archived snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .borg import BorgLock
from .config import BackupConfig, SnapshotSource

# Deleting a snapshot starts Btrfs cleaner I/O; the next deletion waits for
# full I/O pressure to fall below IO_SETTLED, checked IO_CHECKS times.
IO_PRESSURE = Path("/proc/pressure/io")
IO_CHECKS = 60
IO_CHECK_SECONDS = 5
IO_SETTLED = 10


@dataclass(frozen=True)
class CreateResult:
    archive_id: str
    original_bytes: int
    seconds: int
    stats: dict[str, Any]


def drain(config: BackupConfig, label: str) -> int:
    raise NotImplementedError


def plan(config: BackupConfig, label: str) -> dict[str, Any]:
    raise NotImplementedError


def choose_archive_name(source: SnapshotSource, snapshot: str, archives: set[str]) -> str:
    raise NotImplementedError


def archive_snapshot(config: BackupConfig, source: SnapshotSource, snapshot: str, lock: BorgLock) -> None:
    raise NotImplementedError


def create_archive(config: BackupConfig, source: SnapshotSource, snapshot: str, archive: str, details: tuple[str, int, int]) -> CreateResult:
    raise NotImplementedError


def check_archive(config: BackupConfig, source: SnapshotSource, snapshot: str, archive: str, details: tuple[str, int, int], created: CreateResult | None) -> dict[str, Any]:
    raise NotImplementedError


def retire_snapshot(config: BackupConfig, source: SnapshotSource, row: tuple[str, str, int, int], lock: BorgLock) -> bool:
    raise NotImplementedError


def wait_for_io_settle() -> None:
    raise NotImplementedError
