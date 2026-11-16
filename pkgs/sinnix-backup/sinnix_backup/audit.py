"""Independent checks of the latest archives and the freshness probes."""

from __future__ import annotations

from .config import BackupConfig


def audit_realm(config: BackupConfig) -> int:
    raise NotImplementedError
