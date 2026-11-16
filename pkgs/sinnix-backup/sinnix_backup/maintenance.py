"""Prune each archive series, expire retired series, and compact weekly."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from . import markers
from .borg import BorgLock, borg_environment, run_borg
from .config import BackupConfig
from .jobs import utc_stamp

# The nightly coordinator retries a deferred pass; a pass is due after 20 hours.
DUE_SECONDS = 72000
# Prune applies retention daily. Compaction only returns freed space and
# rewrites segments each time, so it runs once a week (6.5 days).
COMPACT_DUE_SECONDS = 561600


def _marker_age(path: Path, now: int) -> int | None:
    if not path.is_file():
        return None
    return now - int(path.read_text())


def maintain(config: BackupConfig, dry_run: bool) -> int:
    """One retention pass over every repository; `dry_run` lists without deleting.

    Active series keep frequent recent archives, then daily, weekly and
    monthly ones. Retired series keep monthly archives and expire by age, so
    even a stopped series eventually disappears.
    """
    settings = config.jobs["maintenance"]
    env = borg_environment(config, config.repository("realm"))
    env["SINNIX_BORG_GLOBAL_LOCK_HELD"] = "1"
    marker = Path(settings["marker"])
    compact_marker = Path(settings["compact_marker"])
    lock_wait = str(config.lock_wait_seconds)
    previous_umask = os.umask(0o077)
    lock = BorgLock(config.lock_path)
    try:
        now = int(time.time())
        if not dry_run:
            age = _marker_age(marker, now)
            if age is not None and age < DUE_SECONDS:
                return 0
        compact_age = _marker_age(compact_marker, now)
        compact_due = compact_age is None or compact_age >= COMPACT_DUE_SECONDS
        if not lock.try_take():
            print("status=deferred reason=borg-lock-contention remains_due=true")
            return 0
        run_directory = Path(settings["retention_directory"]) / f"{utc_stamp()}-{os.getpid()}"
        markers.make_directory(run_directory, 0o700)
        prune_options = ["--dry-run"] if dry_run else ["--stats"]
        for entry in settings["repositories"]:
            repository = config.repository(entry["repository"])
            if not repository.initialized:
                print(f"Skipping uninitialized repo {repository.url}")
                continue
            url = repository.url
            name = repository.path.name
            listing = run_borg(["list", "--json", "--lock-wait", lock_wait, url], env, capture=True)
            (run_directory / f"{name}.before.json").write_text(listing.stdout)
            for series in entry["active"]:
                run_borg(
                    [
                        "prune",
                        "--lock-wait",
                        lock_wait,
                        "--list",
                        *prune_options,
                        "--glob-archives",
                        series,
                        "--keep-within",
                        "2d",
                        "--keep-daily",
                        "14",
                        "--keep-weekly",
                        "8",
                        "--keep-monthly",
                        "12",
                        url,
                    ],
                    env,
                )
            for series in entry["retired"]:
                subprocess.run(
                    ["sinnix-borg-expire", url, series, *(["--dry-run"] if dry_run else [])],
                    env=env,
                    check=True,
                )
                run_borg(
                    [
                        "prune",
                        "--lock-wait",
                        lock_wait,
                        "--list",
                        *prune_options,
                        "--glob-archives",
                        series,
                        "--keep-monthly",
                        "6",
                        url,
                    ],
                    env,
                )
            if not dry_run:
                if compact_due:
                    run_borg(["compact", "--lock-wait", lock_wait, "--progress", url], env)
                listing = run_borg(["list", "--json", "--lock-wait", lock_wait, url], env, capture=True)
                (run_directory / f"{name}.after.json").write_text(listing.stdout)
        if not dry_run:
            markers.publish_marker(marker, f"{int(time.time())}\n", mode=0o600)
            if compact_due:
                markers.publish_marker(compact_marker, f"{int(time.time())}\n", mode=0o600)
        return 0
    finally:
        lock.release()
        os.umask(previous_umask)
