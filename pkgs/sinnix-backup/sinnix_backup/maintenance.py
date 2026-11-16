"""Prune each archive series, expire retired series, and compact weekly."""

from __future__ import annotations

from .config import BackupConfig


def maintain(config: BackupConfig, dry_run: bool) -> int:
    raise NotImplementedError
