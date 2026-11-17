"""The nightly sequence: dumps, a btrbk acquisition, archive jobs, then maintenance.

The sequence owns the schedule, not the Borg lock: each child unit takes the
lock itself, and waiting for a child while holding its lock would deadlock.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

from . import markers, snapshots
from .config import BackupConfig
from .drain import CHECK_FAILURES

# The unit that takes the btrbk snapshots of one acquisition.
SNAPSHOT_UNIT = "btrbk.service"


def _now() -> float:
    return time.time()


def _print(line: str, *, error: bool = False) -> None:
    print(line, file=sys.stderr if error else sys.stdout, flush=True)


def _drain_has_work(config: BackupConfig) -> bool:
    """True when any drain source has a snapshot without a local acknowledgement.

    Reads only local markers; the drains themselves check archives under the
    lock, so this needs no repository access.
    """
    for label in config.nightly.drain_sources:
        source = config.source(label)
        try:
            if snapshots.pending_snapshot_hint(
                source.snapshot_directory,
                source.name_glob,
                source.marker(config.state_directory, "latest-archived"),
            ):
                return True
        except CHECK_FAILURES:
            _print("Queue unavailable; requesting native drain validation", error=True)
            return True
    return False


def _sinex_backup_fresh(path: Path | None, now: float) -> bool:
    """Reuse Sinex's completed pair on boot catch-up, for the daily window."""
    if path is None:
        return False
    try:
        with path.open() as receipt:
            completed = os.fstat(receipt.fileno()).st_mtime
            pair = json.load(receipt)
        hold = str(uuid.UUID(pair["hold"]))
        if pair["hold"] != hold or pair["producers_complete"] is not True:
            return False
        for part in ("main", "keys"):
            archive = pair[part]
            if (
                archive["name"] != f"sinex-core-{hold}"
                or re.fullmatch(r"[0-9a-f]{64}", archive["id"]) is None
            ):
                return False
        return 0 <= now - completed < markers.DAILY_MARKER_SECONDS
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def run_nightly(config: BackupConfig) -> int:
    nightly = config.nightly
    state = config.state_directory
    acquisition_marker = state / "coordinator.acquisition"
    failed = False

    def run_step(unit: str) -> bool:
        nonlocal failed
        _print(f"backup_phase=coordinator unit={unit} status=starting")
        if subprocess.run(["systemctl", "start", unit]).returncode == 0:
            _print(f"backup_phase=coordinator unit={unit} status=finished")
            return True
        _print(
            f"backup_phase=coordinator unit={unit} status=failed; continuing independent jobs",
            error=True,
        )
        failed = True
        return False

    if markers.daily_marker_fresh(
        acquisition_marker, nightly.acquisition_policy, _now()
    ):
        _print("backup_phase=coordinator acquisition=already-fresh")
    else:
        dumps_succeeded = True
        for unit in nightly.dump_units:
            if not run_step(unit):
                dumps_succeeded = False
        if dumps_succeeded:
            # Only a completed acquisition lets a boot catch-up after an
            # interrupted archive phase reuse these dumps and snapshots.
            if run_step(SNAPSHOT_UNIT):
                try:
                    markers.make_directory(state, 0o750, "users")
                    markers.publish_marker(
                        acquisition_marker,
                        markers.marker_text(
                            {
                                "epoch": int(_now()),
                                "policy_sha256": nightly.acquisition_policy,
                            }
                        ),
                    )
                except OSError as error:
                    _print(f"Could not record the acquisition: {error}", error=True)
        else:
            _print(
                f"backup_phase=coordinator unit={SNAPSHOT_UNIT} status=skipped reason=dump-failure",
                error=True,
            )

    if _drain_has_work(config):
        # The weekly check resumes later; pending snapshots go first.
        subprocess.run(["systemctl", "stop", nightly.verify_unit])

    for unit in (*nightly.archive_units, *nightly.final_units):
        if unit == "sinex-backup.service" and _sinex_backup_fresh(
            nightly.sinex_completion, _now()
        ):
            _print(
                f"backup_phase=coordinator unit={unit} status=skipped reason=already-fresh"
            )
            continue
        daily = nightly.daily_markers.get(unit)
        if daily is not None and markers.daily_marker_fresh(daily[0], daily[1], _now()):
            _print(
                f"backup_phase=coordinator unit={unit} status=skipped reason=already-fresh"
            )
            continue
        run_step(unit)
    return 1 if failed else 0
