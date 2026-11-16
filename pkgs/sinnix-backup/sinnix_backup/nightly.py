"""The nightly sequence: dumps, a btrbk acquisition, archive jobs, then maintenance."""

from __future__ import annotations

from .config import BackupConfig


def run_nightly(config: BackupConfig) -> int:
    raise NotImplementedError
