"""The weekly repository integrity check and the Beads restore check."""

from __future__ import annotations

from .config import BackupConfig


def check_repositories(config: BackupConfig) -> int:
    raise NotImplementedError


def check_beads_restore(config: BackupConfig) -> int:
    raise NotImplementedError
