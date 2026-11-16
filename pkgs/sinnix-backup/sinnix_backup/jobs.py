"""Backup jobs other than snapshot drains: snapshots, direct-path and hourly archives, dump expiry."""

from __future__ import annotations

from .config import BackupConfig


def take_snapshots(config: BackupConfig) -> int:
    raise NotImplementedError


def archive_root_snapshots(config: BackupConfig) -> int:
    raise NotImplementedError


def archive_sinex_stores(config: BackupConfig) -> int:
    raise NotImplementedError


def dump_polylogue_databases(config: BackupConfig) -> int:
    raise NotImplementedError


def archive_polylogue_state(config: BackupConfig) -> int:
    raise NotImplementedError


def archive_hourly_persist(config: BackupConfig) -> int:
    raise NotImplementedError


def archive_hourly_live(config: BackupConfig) -> int:
    raise NotImplementedError


def expire_local_dumps(config: BackupConfig) -> int:
    raise NotImplementedError
