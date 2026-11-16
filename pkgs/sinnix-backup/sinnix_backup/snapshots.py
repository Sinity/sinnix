"""Snapshot names, Btrfs identities, acknowledgements and the prune plan."""

import json
import os
import re
import stat
import subprocess
import time
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from glob import escape as glob_escape
from pathlib import Path

from . import markers
from .coverage import policy_identity

SNAPSHOT_NAME = re.compile(r"^[^.]+\.(\d{8}T\d{6}[+-]\d{4})$")


def snapshot_epoch(name):
    match = SNAPSHOT_NAME.fullmatch(name)
    if not match:
        raise ValueError(f"invalid snapshot timestamp: {name}")
    return int(datetime.strptime(match[1], "%Y%m%dT%H%M%S%z").timestamp())


def read_latest_epoch(marker):
    fields = markers.read_marker(marker)
    return snapshot_epoch(fields["snapshot"]) if fields is not None else None


ACQUISITION_SCHEMA = "sinnix.backup-acquisition-inventory.v1"


def observe_acquisitions(directory, glob, coverage, source):
    """Root producer projects immutable metadata, never private file contents."""
    source_info = run("btrfs", "subvolume", "show", str(source))
    source_uuid = re.search(r"^\s*UUID:\s*([0-9a-f-]{36})\s*$", source_info, re.M)
    filesystem = filesystem_identity(directory)
    if not source_uuid or filesystem_identity(source) != filesystem:
        raise ValueError("acquisition source identity is unavailable or changed")
    snapshots = []
    for name in snapshot_names(directory, glob):
        path = Path(directory) / name
        uuid, generation, subvolume_id = snapshot_details(path)
        info = run("btrfs", "subvolume", "show", str(path))
        parent = re.search(r"^\s*Parent UUID:\s*([0-9a-f-]{36})\s*$", info, re.M)
        if not parent or parent[1] != source_uuid[1]:
            raise ValueError("acquired snapshot belongs to another source")
        snapshots.append(
            {
                "name": name,
                "uuid": uuid,
                "generation": generation,
                "subvolume_id": subvolume_id,
                "parent_uuid": parent[1],
                "cut_epoch": snapshot_epoch(name),
            }
        )
    return {
        "schema": ACQUISITION_SCHEMA,
        "observed_at": datetime.fromtimestamp(time.time(), timezone.utc).isoformat(),
        "source": str(source),
        "source_uuid": source_uuid[1],
        "filesystem_uuid": filesystem,
        "snapshot_directory": str(directory),
        "snapshot_glob": glob,
        "policy_sha256": policy_identity(coverage, require_borg_excludes=True),
        "snapshots": snapshots,
    }


def marker_order(fields):
    if fields is None or ("generation" not in fields and "subvolume_id" not in fields):
        return None
    try:
        order = int(fields["generation"]), int(fields["subvolume_id"])
    except (KeyError, ValueError) as error:
        raise ValueError(
            "invalid snapshot acknowledgement creation generation"
        ) from error
    if min(order) <= 0:
        raise ValueError("invalid snapshot acknowledgement creation generation")
    return order


def snapshot_names(directory, glob):
    # Path.glob suppresses directory-read errors. A failed inventory must not
    # become an empty pending queue or an incomplete pruning inventory.
    with os.scandir(directory) as entries:
        names = [
            entry.name
            for entry in entries
            if fnmatchcase(entry.name, glob)
            and stat.S_ISDIR(entry.stat(follow_symlinks=False).st_mode)
        ]
    return sorted(names, key=snapshot_epoch)


def acknowledgement_directory(marker):
    return Path(str(marker) + ".by-snapshot")


def verified_acknowledgement(directory, glob, marker, prefix, replacement_suffix):
    """Accept only the snapshot actually named by this archive receipt."""
    fields = markers.read_marker(marker)
    if fields is None:
        raise ValueError("no verified archive acknowledgement")
    snapshot = fields["snapshot"]
    archive = fields["archive"]
    proof = json.loads(fields["coverage"])
    if not fnmatchcase(snapshot, glob):
        raise ValueError("verified acknowledgement names another snapshot volume")
    snapshot_epoch(snapshot)
    order = marker_order(fields)
    if order is None or "filesystem_uuid" not in fields:
        return None
    if fields["filesystem_uuid"] != filesystem_identity(directory):
        raise ValueError("verified acknowledgement filesystem identity changed")
    expected_archive = f"{prefix}-{snapshot}"
    replacement = re.escape(expected_archive) + r"-coverage-v(?:[2-9]|[1-9][0-9]+)"
    producer = re.escape(expected_archive) + r"-producer-v[1-9][0-9]*"
    if archive not in (
        expected_archive,
        expected_archive + replacement_suffix,
    ) and not (re.fullmatch(replacement, archive) or re.fullmatch(producer, archive)):
        raise ValueError("verified acknowledgement names another archive")
    uuid = proof["snapshot_uuid"]
    if (
        proof["archive"] != archive
        or archive_identity(archive, uuid) != proof["archive_id"]
    ):
        raise ValueError("verified acknowledgement archive identity changed")
    if snapshot not in snapshot_names(directory, glob):
        raise ValueError("verified acknowledgement snapshot is unavailable")
    selected = snapshot_details(Path(directory) / snapshot)
    if selected != (uuid, *order):
        raise ValueError("verified acknowledgement snapshot identity changed")
    return snapshot, *selected


def should_advance_marker(directory, marker, snapshot):
    """Keep data freshness ordered by Btrfs creation generation, not the clock."""
    fields = markers.read_marker(marker)
    order = marker_order(fields)
    if order is None or fields.get("filesystem_uuid") != filesystem_identity(directory):
        return True
    previous = Path(directory) / fields["snapshot"]
    if not previous.exists():
        return True
    details = snapshot_details(previous)
    if details != (json.loads(fields["coverage"])["snapshot_uuid"], *order):
        raise ValueError("latest acknowledged snapshot identity changed")
    return snapshot_details(Path(directory) / snapshot)[1:] >= order


def queued_snapshots(directory, glob, marker, prefix, replacement_suffix):
    """Freeze one finite queue: newest pending state, then historical states."""
    receipts = acknowledgement_directory(marker)
    if receipts.is_symlink():
        raise ValueError("snapshot acknowledgement directory is a symlink")
    latest = markers.read_marker(marker)
    pending = []
    for name in snapshot_names(directory, glob):
        details = snapshot_details(Path(directory) / name)
        receipt = receipts / name
        if receipt.is_symlink():
            raise ValueError("snapshot acknowledgement is a symlink")
        if receipt.exists():
            acknowledged = verified_acknowledgement(
                directory, glob, receipt, prefix, replacement_suffix
            )
            if acknowledged != (name, *details):
                raise ValueError("unqualified snapshot acknowledgement")
            # Recover an interruption between durable receipt publication and
            # advancement of the latest marker without recreating the archive.
            if markers.read_marker(receipt) == latest or not should_advance_marker(
                directory, marker, name
            ):
                continue
        pending.append((name, details))
    if not pending:
        return []
    newest = max(pending, key=lambda row: row[1][1:])
    return [
        newest[0],
        *[
            name
            for name, _ in sorted(pending, key=lambda row: row[1][1:])
            if name != newest[0]
        ],
    ]


def pending_snapshot_hint(directory, glob, marker):
    """Decide check preemption from local receipts; never accept an archive.

    The drains always check archives themselves under the Borg lock. The coordinator must
    not open repositories or require their credentials before taking that gate.
    """
    receipts = acknowledgement_directory(marker)
    if receipts.is_symlink():
        raise ValueError("snapshot acknowledgement directory is a symlink")
    latest = markers.read_marker(marker)
    for name in snapshot_names(directory, glob):
        receipt = receipts / name
        if receipt.is_symlink():
            raise ValueError("snapshot acknowledgement is a symlink")
        fields = markers.read_marker(receipt)
        if fields is None or fields.get("snapshot") != name:
            return True
        if fields != latest and should_advance_marker(directory, marker, name):
            return True
    return False


def _releasable(directory, glob, receipts, latest, name, prefix, replacement_suffix):
    """The verified row for one snapshot that may be deleted, or None."""
    if name == latest[0]:
        return None  # The independent full audit needs this immutable source.
    receipt = receipts / name
    if receipt.is_symlink():
        raise ValueError("snapshot acknowledgement is a symlink")
    if not receipt.exists():
        return None  # A different snapshot's proof never covers this snapshot.
    acknowledged = verified_acknowledgement(
        directory, glob, receipt, prefix, replacement_suffix
    )
    if acknowledged is None or acknowledged[0] != name:
        raise ValueError("unqualified snapshot acknowledgement")
    if acknowledged[2:] > latest[2:]:
        raise ValueError("latest marker lags a newer acknowledged snapshot")
    return acknowledged


def _latest_and_receipts(directory, glob, marker, prefix, replacement_suffix):
    latest = verified_acknowledgement(
        directory, glob, marker, prefix, replacement_suffix
    )
    receipts = acknowledgement_directory(marker)
    if receipts.is_symlink():
        raise ValueError("snapshot acknowledgement directory is a symlink")
    return latest, receipts


def verified_prune_plan(directory, glob, marker, prefix, replacement_suffix):
    latest, receipts = _latest_and_receipts(
        directory, glob, marker, prefix, replacement_suffix
    )
    if latest is None:
        return []
    releasable = []
    for name in snapshot_names(directory, glob):
        row = _releasable(
            directory, glob, receipts, latest, name, prefix, replacement_suffix
        )
        if row is not None:
            releasable.append(row)
    return sorted(releasable, key=lambda row: row[2:])


def verified_prune_candidate(directory, glob, marker, prefix, replacement_suffix, name):
    """Recheck one planned deletion: its archive and source as they are now."""
    latest, receipts = _latest_and_receipts(
        directory, glob, marker, prefix, replacement_suffix
    )
    if latest is None or name not in snapshot_names(directory, glob):
        return None
    return _releasable(
        directory, glob, receipts, latest, name, prefix, replacement_suffix
    )


def run(*args):
    return subprocess.check_output(args, text=True, timeout=300)


def filesystem_identity(source):
    mounts = json.loads(
        run("findmnt", "--json", "--output", "TARGET,FSTYPE", "--target", str(source))
    ).get("filesystems", [])
    # findmnt includes the autofs trigger alongside its mounted filesystem.
    # Ignore only that same-target trigger, retaining ambiguity checks.
    backing = [mount for mount in mounts if mount.get("fstype") != "autofs"]
    if (
        len(backing) != 1
        or backing[0].get("fstype") != "btrfs"
        or not backing[0].get("target")
        or any(mount.get("target") != backing[0]["target"] for mount in mounts)
    ):
        raise ValueError(f"cannot identify one Btrfs mount: {source}")
    mounts = backing
    # btrfs filesystem show accepts a mount point, not an arbitrary child.
    output = run("btrfs", "filesystem", "show", "--raw", mounts[0]["target"])
    identities = re.findall(
        r"^Label:.*\buuid:\s*([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\s*$",
        output,
        re.M,
    )
    if len(identities) != 1:
        raise ValueError(f"cannot identify one Btrfs filesystem: {source}")
    return identities[0]


def snapshot_details(source):
    output = run("btrfs", "subvolume", "show", str(source))
    uuid = re.search(r"^\s*UUID:\s*([0-9a-f-]{36})\s*$", output, re.M)
    generation = re.search(r"^\s*Gen at creation:\s*(\d+)\s*$", output, re.M)
    subvolume_id = re.search(r"^\s*Subvolume ID:\s*(\d+)\s*$", output, re.M)
    if (
        not uuid
        or not generation
        or not subvolume_id
        or run("btrfs", "property", "get", "-ts", str(source), "ro").strip()
        != "ro=true"
    ):
        raise ValueError(f"snapshot is not an identified read-only subvolume: {source}")
    return uuid[1], int(generation[1]), int(subvolume_id[1])


def identity(source):
    return snapshot_details(source)[0]


def archive_identity(archive, snapshot_uuid):
    archives = json.loads(
        run(
            "borg",
            "list",
            "--json",
            "--format",
            "{comment}",
            "--glob-archives",
            glob_escape(archive),
        )
    )["archives"]
    matches = [
        entry
        for entry in archives
        if entry.get("archive", entry.get("name")) == archive
    ]
    if (
        len(matches) != 1
        or matches[0].get("comment") != "sinnix-snapshot-v1:" + snapshot_uuid
    ):
        raise ValueError(f"archive does not bind this snapshot UUID: {archive}")
    archive_id = matches[0]["id"]
    if not re.fullmatch(r"[0-9a-f]{64}", archive_id):
        raise ValueError("invalid archive ID")
    return archive_id


def acknowledged_snapshot(
    directory, glob, marker, prefix, replacement_suffix, coverage=None
):
    """The snapshot a verified acknowledgement names; `coverage` checks the policy."""
    record = verified_acknowledgement(
        directory, glob, marker, prefix, replacement_suffix
    )
    if record is None:
        raise ValueError("unqualified snapshot acknowledgement")
    if coverage is not None:
        recorded = json.loads(markers.read_marker(marker)["coverage"])
        if recorded.get("proof_mode") not in {"full", "created"} or recorded.get(
            "policy_sha256"
        ) != policy_identity(coverage, require_borg_excludes=True):
            raise ValueError(
                "prior acknowledgement does not establish the active policy"
            )
    return record[0]
