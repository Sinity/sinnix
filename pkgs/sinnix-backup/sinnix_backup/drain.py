"""Archive one source's queued snapshots, check each archive, then delete archived snapshots."""

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import borg, coverage, create_record, markers, snapshots
from .borg import BorgError, BorgLock
from .config import BackupConfig, SnapshotSource

# Deleting a snapshot starts Btrfs cleaner I/O; the next deletion waits for
# full I/O pressure to fall below IO_SETTLED, checked IO_CHECKS times.
IO_PRESSURE = Path("/proc/pressure/io")
IO_CHECKS = 60
IO_CHECK_SECONDS = 5
IO_SETTLED = 10

# A check that raises one of these found that an archive, record or snapshot
# does not match. Programming errors are not listed and fail the drain.
CHECK_FAILURES = (
    ValueError,
    KeyError,
    TypeError,
    OSError,
    subprocess.SubprocessError,
    sqlite3.Error,
)


@dataclass(frozen=True)
class CreateResult:
    archive_id: str
    original_bytes: int
    seconds: int
    stats: dict[str, Any]


def _latest(config: BackupConfig, source: SnapshotSource) -> Path:
    return source.marker(config.state_directory, "latest-archived")


def _pending_record(config: BackupConfig, source: SnapshotSource) -> Path:
    return source.marker(config.state_directory, "pending-create.json")


def _queue_arguments(config: BackupConfig, source: SnapshotSource) -> tuple[Path, str, Path, str, str]:
    return (
        source.snapshot_directory,
        source.name_glob,
        _latest(config, source),
        source.archive_prefix,
        source.replacement_suffix,
    )


def _compact(value: dict[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _number_text(value: Any) -> str:
    """A JSON number as a journal field value (whole floats print as integers)."""
    if value is None:
        return "null"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _archives(repository_url: str) -> set[str]:
    return set(borg.run_borg(["list", "--short", repository_url], capture=True).stdout.splitlines())


def _unmount(bind_path: Path) -> None:
    if subprocess.run(["mountpoint", "-q", str(bind_path)]).returncode == 0:
        subprocess.run(["umount", str(bind_path)], check=True)


def _adoptable_acknowledgement(config: BackupConfig, source: SnapshotSource) -> str | None:
    """The snapshot the latest marker acknowledges under the current policy, or None.

    Only the same named, still-identified snapshot is adopted, so no large
    comparison repeats and no other snapshot inherits the acknowledgement.
    """
    latest = _latest(config, source)
    try:
        record = snapshots.verified_acknowledgement(*_queue_arguments(config, source))
        if record is None:
            return None
        check = json.loads(markers.read_marker(latest)["coverage"])
        if check.get("proof_mode") not in {"full", "created"} or check.get(
            "policy_sha256"
        ) != coverage.policy_identity(source.coverage, require_borg_excludes=True):
            return None
    except CHECK_FAILURES:
        return None
    return record[0]


def _publish_acknowledgement(config: BackupConfig, source: SnapshotSource, snapshot: str, acknowledgement: Path) -> None:
    """Advance the latest marker when this snapshot is not older; always record last success."""
    latest = _latest(config, source)
    text = acknowledgement.read_text()
    if snapshots.should_advance_marker(source.snapshot_directory, latest, snapshot):
        markers.publish_marker(latest, text)
    markers.publish_marker(source.marker(config.state_directory, "last-success"), text)


def drain(config: BackupConfig, label: str) -> int:
    source = config.source(label)
    repository = config.repository(source.repository)
    env = borg.borg_environment(
        config, repository, files_cache_suffix=source.files_cache_suffix
    )
    markers.make_directory(config.state_directory, 0o750, "users")
    lock = BorgLock(config.lock_path)
    if not lock.try_take():
        print(
            f"Another Borg operation is active; skipping {label} Borg drain and keeping work queued",
            flush=True,
        )
        return 0
    bind_path = source.bind_path
    with borg.exported(env):
        try:
            _unmount(bind_path)
            borg.initialize_repository(repository, env, lock)
            bind_path.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(bind_path, 0o700)

            latest = _latest(config, source)
            acknowledgements = snapshots.acknowledgement_directory(latest)
            markers.make_directory(acknowledgements, 0o750, "users")
            if latest.is_file():
                previous = _adoptable_acknowledgement(config, source)
                if previous is not None:
                    target = acknowledgements / previous
                    if not target.exists() and not target.is_symlink():
                        markers.publish_marker(target, latest.read_text())
            # One finite queue per run; later snapshots wait for the next run.
            queue = snapshots.queued_snapshots(*_queue_arguments(config, source))
            lock.release()

            # The lock is taken per snapshot, so maintenance and checks queued
            # behind it run between snapshots and between deletions.
            for snapshot in queue:
                lock.wait()
                archive_snapshot(config, source, snapshot, lock)
                lock.release()

            # Every acknowledged snapshot except the newest is deleted; the
            # newest stays for the independent audit.
            if latest.is_file():
                lock.wait()
                prune_plan = snapshots.verified_prune_plan(*_queue_arguments(config, source))
                lock.release()
                for row in prune_plan:
                    lock.wait()
                    retired = retire_snapshot(config, source, row, lock)
                    lock.release()
                    if not retired:
                        continue
                    # Cleaner completion and pressure settling do not use Borg,
                    # so they run without the lock before the next deletion.
                    subprocess.run(
                        ["btrfs", "subvolume", "sync", str(source.snapshot_directory), str(row[3])],
                        check=True,
                    )
                    wait_for_io_settle()
        finally:
            _unmount(bind_path)
            lock.release()
    return 0


def plan(config: BackupConfig, label: str) -> dict[str, Any]:
    """What `drain` would archive and delete now; takes no lock and changes nothing."""
    source = config.source(label)
    repository = config.repository(source.repository)
    env = borg.borg_environment(
        config, repository, files_cache_suffix=source.files_cache_suffix
    )
    with borg.exported(env):
        latest = _latest(config, source)
        acknowledgements = snapshots.acknowledgement_directory(latest)
        queue = snapshots.queued_snapshots(*_queue_arguments(config, source))
        archives = _archives(repository.url) if queue and repository.initialized else set()
        rows = []
        for snapshot in queue:
            archive = choose_archive_name(source, snapshot, archives)
            snapshot_uuid = snapshots.snapshot_details(source.snapshot_directory / snapshot)[0]
            rows.append(
                {
                    "snapshot": snapshot,
                    "acknowledged": (acknowledgements / snapshot).is_file(),
                    "archive": archive,
                    "create_command": borg.snapshot_create_command(
                        "borg",
                        source.bind_path,
                        archive,
                        snapshot_uuid,
                        source.coverage,
                        borg.cut_timestamp(snapshot),
                    ),
                }
            )
        prune_plan = (
            snapshots.verified_prune_plan(*_queue_arguments(config, source))
            if latest.is_file()
            else []
        )
    return {
        "label": label,
        "policy_sha256": coverage.policy_identity(
            source.coverage, require_borg_excludes=source.create_check
        ),
        "queue": rows,
        "prune_plan": [
            {"snapshot": name, "uuid": uuid, "generation": generation, "subvolume_id": subvolume_id}
            for name, uuid, generation, subvolume_id in prune_plan
        ],
    }


def choose_archive_name(source: SnapshotSource, snapshot: str, archives: set[str]) -> str:
    """The archive name for a snapshot before any create record is consulted.

    An archive made under an older policy keeps its name and the snapshot gets
    the replacement suffix. A source checked by content comparison resumes its
    newest `-coverage-vN` retry archive rather than creating another.
    """
    original = f"{source.archive_prefix}-{snapshot}"
    archive = original
    if source.replacement_suffix and original in archives:
        archive = original + source.replacement_suffix
    if not source.create_check:
        number = 3
        while f"{original}-coverage-v{number}" in archives:
            archive = f"{original}-coverage-v{number}"
            number += 1
    return archive


def _unused_name(original: str, kind: str, first: int, archives: set[str]) -> str:
    number = first
    while f"{original}-{kind}-v{number}" in archives:
        number += 1
    return f"{original}-{kind}-v{number}"


def archive_snapshot(config: BackupConfig, source: SnapshotSource, snapshot: str, lock: BorgLock) -> None:
    """Create, check and acknowledge one snapshot. The caller holds `lock`.

    Any failure raises and keeps the snapshot on disk.
    """
    latest = _latest(config, source)
    pending_record = _pending_record(config, source)
    acknowledgement = snapshots.acknowledgement_directory(latest) / snapshot
    if acknowledgement.is_file():
        record = snapshots.verified_acknowledgement(
            source.snapshot_directory,
            source.name_glob,
            acknowledgement,
            source.archive_prefix,
            source.replacement_suffix,
        )
        if record is None:
            raise ValueError("unqualified snapshot acknowledgement")
        if record[0] != snapshot:
            raise ValueError(f"acknowledgement for {snapshot} names {record[0]}")
        _publish_acknowledgement(config, source, snapshot, acknowledgement)
        return

    snapshot_path = source.snapshot_directory / snapshot
    bind_path = source.bind_path
    original = f"{source.archive_prefix}-{snapshot}"
    details = snapshots.snapshot_details(snapshot_path)
    filesystem = snapshots.filesystem_identity(snapshot_path)
    subprocess.run(["mount", "--bind", str(snapshot_path), str(bind_path)], check=True)
    try:
        archives = _archives(config.repository(source.repository).url)
        archive = choose_archive_name(source, snapshot, archives)
        created: CreateResult | None = None
        check: dict[str, Any] | None = None
        if source.create_check and pending_record.is_file():
            # A create record can survive a crash before the acknowledgement;
            # reuse its archive rather than creating another.
            try:
                recorded = json.loads(pending_record.read_text())["archive"]
                if (
                    isinstance(recorded, str)
                    and (recorded == original or recorded.startswith(original + "-"))
                    and recorded in archives
                ):
                    check = create_record.verify_created(
                        bind_path, recorded, details[0], source.coverage, pending_record
                    )
                    archive = recorded
            except CHECK_FAILURES:
                check = None
        if source.create_check and check is None and archive in archives:
            try:
                check = create_record.verify_created(
                    bind_path, archive, details[0], source.coverage, pending_record
                )
            except CHECK_FAILURES:
                # An archive without a matching create record was never seen
                # to succeed; create a separately named archive instead.
                archive = _unused_name(original, "producer", 1, archives)
        if check is None and archive not in archives:
            created = create_archive(config, source, snapshot, archive, details)

        if source.create_check:
            if check is None:
                check = create_record.verify_created(
                    bind_path, archive, details[0], source.coverage, pending_record
                )
        else:
            try:
                check = check_archive(config, source, snapshot, archive, details, created)
            except CHECK_FAILURES as error:
                if created is not None:
                    raise
                # An older archive can lack content the current policy keeps.
                # It is never acknowledged; one fresh name is created and
                # compared in full instead.
                print(f"Snapshot retained: {error}", file=sys.stderr, flush=True)
                archive = _unused_name(original, "coverage", 3, archives)
                created = create_archive(config, source, snapshot, archive, details)
                check = _content_check(config, source, archive, details[0], "full")

        if created is not None and check.get("archive_id") != created.archive_id:
            raise ValueError(f"Created archive identity changed; retaining {snapshot_path}")
        fallback = {
            "create_seconds": created.seconds if created else 0,
            "create_original_bytes": created.original_bytes if created else 0,
        }
        # A recorded value wins unless it is null or false.
        check = {
            **check,
            **{
                key: value if check.get(key) is None or check.get(key) is False else check[key]
                for key, value in fallback.items()
            },
        }
        print(
            f"backup_phase=verify label={source.label} archive={archive} mode={check['proof_mode']}"
            f" elapsed_seconds={_number_text(check.get('verification_seconds'))}"
            f" source_hashed_bytes={_number_text(check.get('source_hashed_bytes'))}"
            f" archive_content_verified_bytes={_number_text(check.get('archive_content_verified_bytes'))}",
            flush=True,
        )
    finally:
        _unmount(bind_path)
    if (
        snapshots.snapshot_details(snapshot_path) != details
        or snapshots.filesystem_identity(snapshot_path) != filesystem
    ):
        raise ValueError(f"Snapshot identity changed; retaining {snapshot_path}")
    markers.publish_marker(
        acknowledgement,
        markers.marker_text(
            {
                "archive": archive,
                "snapshot": snapshot,
                "filesystem_uuid": filesystem,
                "generation": details[1],
                "subvolume_id": details[2],
                "coverage": _compact(check),
                "epoch": int(time.time()),
            }
        ),
    )
    _publish_acknowledgement(config, source, snapshot, acknowledgement)


def create_archive(config: BackupConfig, source: SnapshotSource, snapshot: str, archive: str, details: tuple[str, int, int]) -> CreateResult:
    """Run the drain's `borg create` on the bind mount; record it for create-checked sources."""
    command = borg.snapshot_create_command(
        "borg",
        source.bind_path,
        archive,
        details[0],
        source.coverage,
        borg.cut_timestamp(snapshot),
    )
    started = int(time.time())
    try:
        result = borg.run_borg(command[1:], capture=True)
    except BorgError as error:
        raise ValueError(
            f"borg create failed for {source.label} snapshot {snapshot}; subvolume kept on disk"
        ) from error
    seconds = int(time.time()) - started
    try:
        stats = json.loads(result.stdout)
    except ValueError:
        stats = None
    created = stats.get("archive") if isinstance(stats, dict) else None
    if not isinstance(created, dict) or created.get("name") != archive:
        raise ValueError(
            f"borg create returned no usable stats; retaining {source.label} snapshot {snapshot}"
        )
    archive_id = created.get("id")
    original_bytes = (created.get("stats") or {}).get("original_size")
    if (
        not isinstance(archive_id, str)
        or len(archive_id) != 64
        or any(character not in "0123456789abcdef" for character in archive_id)
        or type(original_bytes) is not int
        or original_bytes < 0
    ):
        raise ValueError(
            f"borg create returned invalid stats; retaining {source.label} snapshot {snapshot}"
        )
    if source.create_check:
        try:
            record = create_record.record_create(
                source.bind_path, archive, source.coverage, stats
            )
        except CHECK_FAILURES as error:
            raise ValueError(
                f"Could not bind Borg create to snapshot; retaining {source.label} snapshot {snapshot}"
            ) from error
        record = {**record, "create_seconds": seconds}
        try:
            markers.publish_marker(_pending_record(config, source), _compact(record) + "\n")
        except OSError as error:
            raise ValueError(
                f"Could not publish creation receipt; retaining {source.label} snapshot {snapshot}"
            ) from error
    print(
        f"backup_phase=create label={source.label} archive={archive}"
        f" elapsed_seconds={seconds} original_bytes={original_bytes}",
        flush=True,
    )
    return CreateResult(archive_id, original_bytes, seconds, stats)


def check_archive(config: BackupConfig, source: SnapshotSource, snapshot: str, archive: str, details: tuple[str, int, int], created: CreateResult | None) -> dict[str, Any]:
    """Check an archive of a source that is compared by content.

    A fresh create relies on the previous full comparison while that is under
    a week old and under the current policy; otherwise the archive is compared
    in full.
    """
    latest = _latest(config, source)
    mode = "full"
    if created is not None:
        mode = create_record.choose_check_mode(latest, source.snapshot_directory, source.coverage)
    return _content_check(config, source, archive, details[0], mode)


def _content_check(config: BackupConfig, source: SnapshotSource, archive: str, snapshot_uuid: str, mode: str) -> dict[str, Any]:
    return create_record.compare_archive(
        source.bind_path,
        archive,
        snapshot_uuid,
        source.coverage,
        mode=mode,
        latest_marker=_latest(config, source),
        snapshot_directory=source.snapshot_directory,
    )


def retire_snapshot(config: BackupConfig, source: SnapshotSource, row: tuple[str, str, int, int], lock: BorgLock) -> bool:
    """Delete one acknowledged snapshot after rechecking it; the caller holds `lock`.

    Maintenance may have changed archives since the prune plan, so the
    snapshot's archive and source are checked again. Returns True when the
    snapshot was deleted.
    """
    name, snapshot_uuid, generation, subvolume_id = row
    latest = _latest(config, source)
    current = snapshots.verified_prune_candidate(*_queue_arguments(config, source), name)
    if current != (name, snapshot_uuid, generation, subvolume_id):
        return False
    path = source.snapshot_directory / name
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        # An independent audit holds a shared lock on its snapshot directory,
        # not the Borg lock; the drain never waits for it.
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"Retaining snapshot held by an independent audit: {name}", flush=True)
            return False
        actual = snapshots.snapshot_details(path)
        marker_filesystem = (markers.read_marker(latest) or {}).get("filesystem_uuid", "")
        if snapshots.filesystem_identity(path) != marker_filesystem:
            raise ValueError(f"Snapshot filesystem changed; retaining {path}")
        if actual != (snapshot_uuid, generation, subvolume_id):
            raise ValueError(f"Snapshot identity changed; retaining {path}")
        subprocess.run(["btrfs", "subvolume", "delete", str(path)], check=True)
    finally:
        os.close(descriptor)
    return True


def _full_io_pressure() -> int:
    for line in IO_PRESSURE.read_text().splitlines():
        fields = line.split()
        if fields and fields[0] == "full" and len(fields) > 1:
            return int(float(fields[1].removeprefix("avg10=")))
    return 0


def wait_for_io_settle() -> None:
    for _ in range(IO_CHECKS):
        if _full_io_pressure() < IO_SETTLED:
            return
        time.sleep(IO_CHECK_SECONDS)
