"""Backup jobs other than snapshot drains: snapshots, direct-path and hourly archives, dump expiry."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from . import create_record, hook_cut, markers, snapshots
from .borg import (
    BorgError,
    BorgLock,
    borg_environment,
    exported,
    initialize_repository,
    run_borg,
)
from .config import BackupConfig

# The state directory is readable by the operator's group, so unprivileged
# health probes can read published markers.
STATE_GROUP = "users"
# Hourly live-state archives accept only Borg's "file changed while read"
# warning: Dolt journals and producer spools grow while Borg reads them.
LIVE_ACCEPTED_STATUSES = (0, 100)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def take_or_skip(lock: BorgLock, reason: str) -> bool:
    """Take the global lock without waiting; print the skip line when it is held."""
    if lock.try_take():
        return True
    print(f"Another Borg operation is active; skipping {reason} and keeping work queued")
    return False


def exclude_patterns(root: Path | str, patterns: list[str]) -> list[str]:
    """`--exclude` arguments for patterns relative to `root`.

    Borg matches patterns against archive paths, which have no leading slash;
    a `**` pattern matches anywhere and passes through unchanged.
    """
    prefix = str(root).removeprefix("/")
    arguments = []
    for pattern in patterns:
        arguments += ["--exclude", pattern if pattern.startswith("**") else f"{prefix}/{pattern}"]
    return arguments


def publish_daily_marker(config: BackupConfig, unit: str, fields: dict[str, object]) -> None:
    """Publish `<unit>`'s daily marker with the policy hash the coordinator compares."""
    marker, policy = config.nightly.daily_markers[unit]
    markers.make_directory(config.state_directory, 0o750, STATE_GROUP)
    markers.publish_marker(
        marker,
        markers.marker_text({**fields, "epoch": int(time.time()), "policy_sha256": policy}),
    )


def take_snapshots(config: BackupConfig) -> int:
    subprocess.run(["btrbk", "--quiet", "--preserve-snapshots", "run"], check=True)
    genome = config.sources.get("genome")
    if genome is None:
        return 0
    # Every successful acquisition, unchanged sources included, publishes
    # only snapshot metadata for the unprivileged health reader.
    settings = config.jobs["genome"]
    markers.make_directory(config.state_directory, 0o750, STATE_GROUP)
    inventory = snapshots.observe_acquisitions(
        genome.snapshot_directory, genome.name_glob, genome.coverage, settings["source"]
    )
    markers.publish_marker(Path(settings["acquisition_inventory"]), json.dumps(inventory) + "\n")
    return 0


def root_snapshot_timestamp(name: str) -> str:
    """The initrd names root cuts in UTC, without btrbk's numeric offset."""
    cut = name.removeprefix("root.")
    moment = datetime(
        int(cut[0:4]), int(cut[4:6]), int(cut[6:8]), int(cut[9:11]), int(cut[11:13]), int(cut[13:15])
    )
    return moment.strftime("%Y-%m-%dT%H:%M:%S")


def _delete_archived_root_snapshot(snapshot: Path, archive: str, snapshot_uuid: str, coverage: list[str]) -> bool:
    """Delete one root snapshot only after its archive matches it exactly.

    Archives without a UUID binding, writable snapshots and plain directories
    stay on disk.
    """
    try:
        create_record.compare_archive(snapshot, archive, snapshot_uuid, coverage)
        if snapshots.identity(snapshot) != snapshot_uuid:
            return False
    except Exception as error:
        print(f"Snapshot retained: {error}", file=sys.stderr)
        return False
    return subprocess.run(["btrfs", "subvolume", "delete", str(snapshot)]).returncode == 0


def archive_root_snapshots(config: BackupConfig) -> int:
    source = config.source("root")
    repository = config.repository(source.repository)
    env = borg_environment(config, repository)
    lock = BorgLock(config.lock_path)
    if not take_or_skip(lock, "root snapshot Borg drain"):
        return 0
    mount_root = Path(tempfile.mkdtemp())
    try:
        subprocess.run(
            ["mount", "-o", "subvol=/", config.jobs["root_snapshots"]["device"], str(mount_root)],
            check=True,
        )
        initialize_repository(repository, env, lock)
        failed = False
        snapshot_directory = mount_root / source.snapshot_directory
        for snapshot in sorted(snapshot_directory.glob(source.name_glob)):
            if not snapshot.is_dir():
                continue
            archive = f"{source.archive_prefix}-{snapshot.name}"
            with exported(env):
                try:
                    snapshot_uuid = snapshots.identity(snapshot)
                except Exception as error:
                    print(f"Snapshot retained: {error}", file=sys.stderr)
                    failed = True
                    continue
                listed = subprocess.run(
                    ["borg", "list", "--short", "--glob-archives", archive, repository.url],
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                ).stdout
                if archive in listed.splitlines():
                    print(f"Archive {archive} already exists; verifying snapshot {snapshot.name}")
                    if not _delete_archived_root_snapshot(snapshot, archive, snapshot_uuid, source.coverage):
                        failed = True
                    continue
                try:
                    run_borg(
                        [
                            "create",
                            "--timestamp",
                            root_snapshot_timestamp(snapshot.name),
                            "--compression",
                            "auto,zstd,1",
                            "--comment",
                            "sinnix-snapshot-v1:" + snapshot_uuid,
                            "--lock-wait",
                            str(config.lock_wait_seconds),
                            *(part for path in source.coverage for part in ("--exclude", f"{snapshot}/{path}")),
                            "::" + archive,
                            f"{snapshot}/./",
                        ],
                        env,
                    )
                except BorgError:
                    print(f"borg create failed for {snapshot.name}; subvolume kept on disk", file=sys.stderr)
                    failed = True
                    continue
                if not _delete_archived_root_snapshot(snapshot, archive, snapshot_uuid, source.coverage):
                    failed = True
        # Compaction is batched by the maintenance job.
        return 1 if failed else 0
    finally:
        try:
            mounted = subprocess.run(["mountpoint", "-q", str(mount_root)]).returncode == 0
            if not mounted or subprocess.run(["umount", str(mount_root)]).returncode == 0:
                mount_root.rmdir()
        finally:
            lock.release()


def archive_sinex_stores(config: BackupConfig) -> int:
    repository = config.repository("sinex-blobs")
    env = borg_environment(config, repository)
    lock = BorgLock(config.lock_path)
    initialize_repository(repository, env, lock)
    archive = f"sinex-blobs-{utc_stamp()}"
    # The retained stores never change, so any warning, a changed file
    # included, fails the archive.
    with lock.held():
        run_borg(
            [
                "create",
                "--compression",
                "auto,zstd,1",
                "--lock-wait",
                str(config.lock_wait_seconds),
                "::" + archive,
                *config.jobs["sinex_store_paths"],
            ],
            {**env, "BORG_EXIT_CODES": "modern"},
        )
    print(f"sinex blob backup complete: {archive}")
    publish_daily_marker(config, "borgbackup-job-sinex-blobs.service", {"archive": archive})
    return 0


def dump_polylogue_databases(config: BackupConfig) -> int:
    settings = config.jobs["polylogue"]
    dump_root = Path(settings["dump_root"])
    state_root = Path(settings["state_root"])
    previous_umask = os.umask(0o077)
    try:
        markers.make_directory(dump_root, 0o700, STATE_GROUP)
        stamp = utc_stamp()
        for name in settings["database_names"]:
            database = state_root / name
            if not database.exists():
                continue
            base = name.removesuffix(".db")
            subprocess.run(
                ["sinnix-sqlite-backup", str(database), str(dump_root / f"{base}-{stamp}.db.zst")],
                check=True,
            )
    finally:
        os.umask(previous_umask)
    return 0


def archive_polylogue_state(config: BackupConfig) -> int:
    """Archive Polylogue state without its live databases, plus the purchased vectors.

    The SQLite dumps cover the live databases. Hooks are archived from a
    read-only cut of the state root so writers keep appending; a failed cut
    stays in the cut directory for recovery. The vectors never change, so
    Borg stores them once.
    """
    settings = config.jobs["polylogue"]
    state_root = Path(settings["state_root"])
    repository = config.repository("polylogue-state")
    env = borg_environment(config, repository)
    lock = BorgLock(config.lock_path)
    initialize_repository(repository, env, lock)
    archive = f"polylogue-state-{utc_stamp()}"
    cut_root = Path(settings["hook_cut_directory"])
    markers.make_directory(cut_root, 0o700)
    markers.make_directory(cut_root / "cuts", 0o700)
    print("polylogue state backup phase: creating archive", flush=True)
    command = [
        "borg",
        "create",
        "--compression",
        "auto,zstd,1",
        "--lock-wait",
        str(config.lock_wait_seconds),
        *exclude_patterns(state_root, settings["state_excludes"]),
        "--exclude",
        f"{state_root}/hooks/**",
        "::" + archive,
        str(state_root),
        settings["paid_vector_root"],
    ]
    try:
        with lock.held(), exported(env):
            status = hook_cut.archive(state_root, cut_root / "cuts", command)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"could not archive Polylogue hooks from native cut: {error}", file=sys.stderr)
        return 1
    if status:
        return status
    print(f"polylogue state backup complete: {archive}")
    publish_daily_marker(config, "borgbackup-job-polylogue-state.service", {"archive": archive})
    return 0


def _publish_hourly_marker(config: BackupConfig, label: str, archive: str, started: int) -> None:
    finished = int(time.time())
    markers.publish_marker(
        config.state_file(f"{label}.last-success"),
        markers.marker_text(
            {"archive": archive, "epoch": finished, "elapsed_seconds": finished - started}
        ),
    )
    print(f"backup_phase=done label={label} archive={archive} elapsed_seconds={finished - started}")


def _hourly_start(config: BackupConfig, repository_name: str) -> tuple[dict[str, str], int]:
    env = borg_environment(
        config, config.repository(repository_name), cache_directory=config.hourly_cache_directory
    )
    markers.make_directory(config.hourly_cache_directory, 0o700)
    markers.make_directory(config.state_directory, 0o750, STATE_GROUP)
    return env, int(time.time())


def _seed_hourly_cache(config: BackupConfig, repository_config: Path) -> None:
    """Copy the drain's cache for this repository once.

    Otherwise the first hourly run re-reads and re-chunks all of /persist and
    rebuilds every archive index from the target disk.
    """
    lines = [line for line in repository_config.read_text().splitlines() if line.startswith("id = ")]
    if not lines:
        raise ValueError(f"repository configuration has no id: {repository_config}")
    repository_id = lines[0].split(" ")[2]
    target = config.hourly_cache_directory / repository_id
    seed = config.cache_directory / repository_id
    if repository_id and not target.exists() and seed.is_dir():
        staging = config.hourly_cache_directory / f".seed-{repository_id}"
        shutil.copytree(seed, staging, symlinks=True)
        staging.rename(target)


def archive_hourly_persist(config: BackupConfig) -> int:
    """Archive a read-only snapshot of /persist at the persist drain's own source path.

    Binding the cut at the drain's path, with its exclusions and files-cache
    flags, keeps the files cache shared with the nightly drain.
    """
    env, started = _hourly_start(config, "persist")
    lock = BorgLock(config.lock_path)
    if not take_or_skip(lock, "hourly persist archive"):
        return 0
    try:
        repository = config.repository("persist")
        if not repository.initialized:
            print("persist repository is not initialized; the nightly drain creates it", file=sys.stderr)
            return 1
        settings = config.jobs["hourly"]
        source = config.source("persist")
        cut = Path(settings["persist_cut"])
        bind = source.bind_path

        def release_cut() -> None:
            if subprocess.run(["mountpoint", "-q", str(bind)]).returncode == 0:
                subprocess.run(["umount", str(bind)], check=True)
            if cut.is_dir():
                subprocess.run(["btrfs", "-q", "subvolume", "delete", str(cut)], check=True)

        release_cut()
        try:
            _seed_hourly_cache(config, repository.path / "config")
            markers.make_directory(bind, 0o700)
            subprocess.run(
                ["btrfs", "-q", "subvolume", "snapshot", "-r", settings["persist_source"], str(cut)],
                check=True,
            )
            subprocess.run(["mount", "--bind", str(cut), str(bind)], check=True)
            archive = f"hourly-persist-{utc_stamp()}"
            run_borg(
                [
                    "create",
                    "--files-cache",
                    "ctime,size,inode",
                    "--files-changed",
                    "ctime",
                    "--compression",
                    "auto,zstd,1",
                    "--lock-wait",
                    str(config.lock_wait_seconds),
                    "--stats",
                    *(part for pattern in source.coverage["borg_excludes"] for part in ("--exclude", pattern)),
                    "::" + archive,
                    f"{bind}/./",
                ],
                {**env, "BORG_EXIT_CODES": "modern"},
            )
            _publish_hourly_marker(config, "persist-hourly", archive, started)
        finally:
            release_cut()
        return 0
    finally:
        lock.release()


def archive_hourly_live(config: BackupConfig) -> int:
    """Archive Polylogue's archive database, the Beads task stores and the Sinex spools."""
    env, started = _hourly_start(config, "live-small")
    lock = BorgLock(config.lock_path)
    if not take_or_skip(lock, "hourly live-small archive"):
        return 0
    try:
        repository = config.repository("live-small")
        initialize_repository(repository, env, lock)
        settings = config.jobs["hourly"]
        create_env = {**env, "BORG_EXIT_CODES": "modern"}
        lock_wait = str(config.lock_wait_seconds)
        # One read transaction gives a consistent dump of whatever schema is
        # deployed while the daemon writes. It streams into its own archive,
        # never onto a disk, and runs as the database's owner so no root-owned
        # WAL files appear.
        database = settings["polylogue_archive_database"]
        if Path(database).exists():
            run_borg(
                [
                    "create",
                    "--compression",
                    "auto,zstd,3",
                    "--lock-wait",
                    lock_wait,
                    "--stats",
                    "--stdin-name",
                    "polylogue-archive.sql",
                    "--content-from-command",
                    f"::polylogue-archive-{utc_stamp()}",
                    "--",
                    "runuser",
                    "-u",
                    settings["user"],
                    "--",
                    "sqlite3",
                    "-readonly",
                    "-bail",
                    database,
                    ".dump",
                ],
                create_env,
            )
        tasks_root = settings["tasks_root"]
        sources = [tasks_root, *(spool for spool in settings["sinex_spools"] if Path(spool).is_dir())]
        # Dolt's table files are immutable, its manifest is replaced
        # atomically and its journal only grows, so a file changing while
        # read is a journal or spool tail the next hour takes.
        archive = f"live-small-{utc_stamp()}"
        result = run_borg(
            [
                "create",
                "--compression",
                "auto,zstd,3",
                "--lock-wait",
                lock_wait,
                "--stats",
                *exclude_patterns(tasks_root, settings["tasks_excludes"]),
                "::" + archive,
                *sources,
            ],
            create_env,
            accepted=LIVE_ACCEPTED_STATUSES,
        )
        if result.returncode == 100:
            print("live-small: accepted files that changed while read (Dolt journals and spools)")
        _publish_hourly_marker(config, "live-small", archive, started)
        return 0
    finally:
        lock.release()


def expire_local_dumps(config: BackupConfig) -> int:
    """Delete local daily dumps whose copy in the latest acknowledged realm archive restores."""
    source = config.source("realm")
    env = borg_environment(config, config.repository(source.repository))
    lock = BorgLock(config.lock_path)
    if not take_or_skip(lock, "local dump expiry"):
        return 0
    try:
        marker = source.marker(config.state_directory, "latest-archived")
        # The acknowledged snapshot must still satisfy the current policy.
        with exported(env):
            snapshots.acknowledged_snapshot(
                source.snapshot_directory,
                source.name_glob,
                marker,
                source.archive_prefix,
                source.replacement_suffix,
                coverage=source.coverage,
            )
        fields = markers.read_marker(marker)
        record = json.loads(fields["coverage"])
        # sinnix-borg-prune-dumps reads the archive under the caller's lock.
        subprocess.run(
            [
                "sinnix-borg-prune-dumps",
                "--root",
                config.jobs["local_dumps_root"],
                "--archive",
                fields["archive"],
                "--archive-id",
                record["archive_id"],
                "--snapshot-uuid",
                record["snapshot_uuid"],
                "--apply",
            ],
            env={**env, "SINNIX_BORG_GLOBAL_LOCK_HELD": "1"},
            check=True,
        )
        publish_daily_marker(config, "borgbackup-local-dumps.service", {})
        return 0
    finally:
        lock.release()
