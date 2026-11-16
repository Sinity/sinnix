"""Independent checks of the latest archives and the freshness probes."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime
from fnmatch import fnmatchcase
from pathlib import Path

from . import markers, snapshots
from .borg import BorgLock, borg_environment, exported
from .config import BackupConfig
from .coverage import decode_policy, policy_identity, verify
from .create_record import REALM_PRODUCER_CONTRACT


def audit_realm(config: BackupConfig) -> int:
    """Compare the latest acknowledged realm archive's metadata and a content sample.

    Runs when the last sampled audit is a week old. It selects the snapshot
    under the Borg lock, then holds only a shared flock on that snapshot so
    drains keep working; a drain never deletes a snapshot pinned this way.
    """
    settings = config.jobs["audit"]
    source = config.source("realm")
    record = Path(settings["record"])
    env = borg_environment(config, config.repository(source.repository))
    with exported(env):
        try:
            audit_status(
                record, source.coverage, settings["max_age_seconds"], mode="sampled"
            )
            return 0
        except Exception:
            pass
        markers.make_directory(config.state_directory, 0o750, "users")
        lock = BorgLock(config.lock_path)
        if not lock.try_take():
            print(
                "Another Borg operation is active; realm coverage selection remains due",
                file=sys.stderr,
            )
            markers.publish_marker(
                Path(settings["attempt"]),
                f'{{"status":"deferred","reason":"borg-lock-contention","epoch":{int(time.time())}}}\n',
            )
            print(
                "backup_phase=independent_coverage_audit status=deferred reason=borg-lock-contention remains_due=true"
            )
            return 0
        scratch = Path(settings["scratch_directory"])
        scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(scratch, 0o700)
        saved_tempdir = tempfile.tempdir
        # The inventory of millions of paths stays off the audited filesystem.
        tempfile.tempdir = str(scratch)
        descriptor, selection = tempfile.mkstemp(prefix="selection.", dir=scratch)
        os.close(descriptor)
        pin = None
        try:
            latest = source.marker(config.state_directory, "latest-archived")
            if latest.is_file():
                shutil.copyfile(latest, selection)
            else:
                os.unlink(selection)
            readiness = audit_readiness(selection, source.coverage)
            if not readiness["ready"]:
                markers.publish_marker(
                    Path(settings["attempt"]),
                    json.dumps(
                        readiness | {"status": "deferred", "epoch": int(time.time())},
                        indent=2,
                    )
                    + "\n",
                )
                print(
                    "backup_phase=independent_coverage_audit status=deferred remains_due=true"
                )
                return 0
            snapshot = readiness["snapshot"]
            pin = os.open(source.snapshot_directory / snapshot, os.O_RDONLY)
            try:
                fcntl.flock(pin, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                print(
                    "backup_phase=independent_coverage_audit status=deferred reason=snapshot-in-use remains_due=true"
                )
                return 0
            # The selected marker copy is fixed for this run; the snapshot pin
            # keeps its source, and Borg's own locking protects the archive.
            lock.release()
            result = audit_latest(
                selection,
                source.snapshot_directory,
                source.coverage,
                mode="sampled",
                sample_bytes=settings["sample_bytes"],
                sample_files=settings["sample_files"],
                previous_receipt=record,
            )
            markers.publish_marker(record, json.dumps(result) + "\n")
            print(
                "backup_phase=independent_coverage_audit label=realm"
                f" elapsed_seconds={result['verification_seconds']}"
                f" sampled_files={result['sampled_files']}"
                f" source_hashed_bytes={result['source_hashed_bytes']}"
                f" archive_content_verified_bytes={result['archive_content_verified_bytes']}"
                f" content_coverage={result['content_coverage']}"
            )
            return 0
        finally:
            tempfile.tempdir = saved_tempdir
            Path(selection).unlink(missing_ok=True)
            if pin is not None:
                os.close(pin)
            lock.release()


def acquisition_freshness(
    inventory, glob, marker, coverage, budget, source, max_observation_age
):
    """Operator reads the root producer's projection; no snapshot or Borg access."""
    observed = json.loads(Path(inventory).read_text())
    policy_hash = policy_identity(coverage, require_borg_excludes=True)
    now = time.time()
    stamp = datetime.fromisoformat(observed["observed_at"])
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError("acquisition observation must have an explicit UTC timestamp")
    observed_epoch = stamp.timestamp()
    if (
        observed.get("schema") != snapshots.ACQUISITION_SCHEMA
        or observed.get("source") != str(source)
        or observed.get("snapshot_glob") != glob
        or observed.get("policy_sha256") != policy_hash
        or re.fullmatch(r"[0-9a-f-]{36}", observed.get("source_uuid", "")) is None
        or re.fullmatch(r"[0-9a-f-]{36}", observed.get("filesystem_uuid", "")) is None
        or not 0 <= now - observed_epoch <= max_observation_age
    ):
        raise ValueError(
            "acquisition observation is stale, future, unavailable or changed"
        )
    ready = audit_readiness(marker, coverage)
    if not ready["ready"]:
        raise ValueError(ready["reason"])
    fields = markers.read_marker(marker)
    proof = json.loads(fields["coverage"])
    snapshot = ready["snapshot"]
    receipt = snapshots.acknowledgement_directory(marker) / snapshot
    if (
        not fnmatchcase(snapshot, glob)
        or snapshots.marker_order(fields) is None
        or receipt.is_symlink()
        or markers.read_marker(receipt) != fields
    ):
        raise ValueError("onchange acknowledgement receipt is unavailable or changed")
    entries = {}
    for row in observed["snapshots"]:
        name = row["name"]
        if (
            not fnmatchcase(name, glob)
            or name in entries
            or re.fullmatch(r"[0-9a-f-]{36}", row["uuid"]) is None
            or row["parent_uuid"] != observed["source_uuid"]
            or any(
                type(row[k]) is not int or row[k] <= 0
                for k in ("generation", "subvolume_id")
            )
            or row["cut_epoch"] != snapshots.snapshot_epoch(name)
            or row["cut_epoch"] > now
        ):
            raise ValueError("invalid or future acquired snapshot metadata")
        entries[name] = row
    accepted = entries.get(snapshot)
    if (
        not accepted
        or proof.get("proof_mode") not in {"full", "created"}
        or proof.get("archive") != fields["archive"]
        or re.fullmatch(r"[0-9a-f]{64}", proof.get("archive_id", "")) is None
        or (accepted["uuid"], accepted["generation"], accepted["subvolume_id"])
        != (proof["snapshot_uuid"], *snapshots.marker_order(fields))
        or fields.get("filesystem_uuid") != observed["filesystem_uuid"]
    ):
        raise ValueError("onchange acknowledgement does not bind the observed snapshot")
    if proof["proof_mode"] == "created":
        if (
            proof.get("producer") != REALM_PRODUCER_CONTRACT
            or re.fullmatch(r"[0-9a-f]{64}", proof.get("create_receipt_sha256", ""))
            is None
        ):
            raise ValueError("onchange creation acknowledgement is incomplete")
    elif re.fullmatch(r"[0-9a-f]{64}", proof.get("content_sha256", "")) is None:
        raise ValueError("onchange content acknowledgement is incomplete")
    newer = [
        row
        for row in entries.values()
        if (row["generation"], row["subvolume_id"]) > snapshots.marker_order(fields)
    ]
    if not newer:
        return {"status": "accepted-current-observed-acquired-generation", "pending": 0}
    age = now - min(row["cut_epoch"] for row in newer)
    if not 0 <= age <= budget:
        raise ValueError(
            f"pending onchange acquisition age {age}s is future or overdue"
        )
    return {
        "status": "pending-within-budget",
        "pending": len(newer),
        "oldest_pending_age_seconds": age,
    }


def audit_readiness(marker, coverage):
    policy_hash = policy_identity(coverage, require_borg_excludes=True)
    fields = markers.read_marker(marker)
    if fields is None:
        return {"ready": False, "reason": "awaiting-acknowledged-archive"}
    proof = json.loads(fields["coverage"])
    if proof["policy_sha256"] != policy_hash:
        return {"ready": False, "reason": "awaiting-current-policy-archive"}
    snapshot = fields["snapshot"]
    if Path(snapshot).name != snapshot:
        raise ValueError("invalid audit snapshot name")
    snapshots.snapshot_epoch(snapshot)
    return {"ready": True, "policy_sha256": policy_hash, "snapshot": snapshot}


def audit_latest(
    marker,
    snapshot_directory,
    coverage,
    *,
    mode="full",
    sample_bytes=1073741824,
    sample_files=128,
    sample_after=None,
    previous_receipt=None,
):
    started = time.monotonic()
    marker_bytes = Path(marker).read_bytes()
    fields = markers.read_marker(marker)
    proof = json.loads(fields["coverage"])
    if proof["policy_sha256"] != policy_identity(coverage, require_borg_excludes=True):
        raise ValueError("acknowledged archive uses another coverage policy")
    source = Path(snapshot_directory) / fields["snapshot"]
    details = snapshots.snapshot_details(source)
    if details != (
        proof["snapshot_uuid"],
        int(fields["generation"]),
        int(fields["subvolume_id"]),
    ):
        raise ValueError("acknowledged snapshot identity changed")
    archive = fields["archive"]
    if (
        archive != proof["archive"]
        or snapshots.archive_identity(archive, details[0]) != proof["archive_id"]
    ):
        raise ValueError("acknowledged archive identity changed")
    noncanonical, chrome_extension_caches = decode_policy(coverage)
    if (
        sample_after is None
        and mode == "sampled"
        and previous_receipt
        and Path(previous_receipt).exists()
    ):
        previous = json.loads(Path(previous_receipt).read_text())
        if (
            previous.get("audit_mode") == "independent_metadata_sampled"
            and previous.get("policy_sha256") == proof["policy_sha256"]
        ):
            sample_after = previous.get("sample_next_after")
            if sample_after is not None and not isinstance(sample_after, str):
                raise ValueError("invalid sampled-content cursor")
    result = verify(
        source,
        archive,
        noncanonical,
        chrome_extension_caches,
        content_mode=mode,
        sample_bytes=sample_bytes,
        sample_files=sample_files,
        sample_after=sample_after,
    )
    if mode == "sampled" and result["sampled_files"] == 0:
        raise ValueError(
            "metadata compared but no content sampled; prior receipt retained"
        )
    if (
        Path(marker).read_bytes() != marker_bytes
        or snapshots.snapshot_details(source) != details
        or snapshots.archive_identity(archive, details[0]) != proof["archive_id"]
    ):
        raise ValueError("acknowledged archive changed during full audit")
    return result | {
        "audit_mode": {
            "full": "independent_full",
            "metadata": "independent_metadata",
            "sampled": "independent_metadata_sampled",
        }[mode],
        "archive": archive,
        "archive_id": proof["archive_id"],
        "snapshot_uuid": details[0],
        "policy_sha256": proof["policy_sha256"],
        "audited_epoch": int(time.time()),
        "verification_seconds": round(time.monotonic() - started, 3),
    }


def audit_status(receipt, coverage, max_age, *, mode="full"):
    try:
        audit = json.loads(Path(receipt).read_text())
        age = int(time.time()) - audit["audited_epoch"]
        if (
            audit["audit_mode"]
            != {
                "full": "independent_full",
                "metadata": "independent_metadata",
                "sampled": "independent_metadata_sampled",
            }[mode]
            or audit["policy_sha256"]
            != policy_identity(coverage, require_borg_excludes=True)
            or age < 0
            or age > max_age
        ):
            raise ValueError(f"independent {mode} audit overdue")
    except FileNotFoundError as error:
        raise ValueError(f"independent {mode} audit has not completed") from error
    if mode == "sampled":
        counts = (
            "sampled_files",
            "sample_byte_budget",
            "sample_file_budget",
            "source_hashed_bytes",
            "archive_content_verified_bytes",
        )
        if (
            any(type(audit.get(key)) is not int or audit[key] < 0 for key in counts)
            or not 1 <= audit["sample_file_budget"] <= 128
            or audit["sample_byte_budget"] <= 0
            or audit["sampled_files"] == 0
            or audit["sampled_files"] > audit["sample_file_budget"]
            or audit["source_hashed_bytes"] > audit["sample_byte_budget"]
            or audit["source_hashed_bytes"] != audit["archive_content_verified_bytes"]
            or audit.get("content_coverage") != "partial"
            or audit.get("content_verification")
            != ("bounded_sample" if audit["sampled_files"] else "not_performed")
            or not re.fullmatch(
                r"[0-9a-f]{64}", str(audit.get("sample_content_sha256", ""))
            )
            or "content_sha256" in audit
        ):
            raise ValueError("invalid bounded content sample receipt")
        objects = audit.get("sample_objects")
        if not isinstance(objects, list) or len(objects) != audit["sampled_files"]:
            raise ValueError("invalid sampled object evidence")
        digest = hashlib.sha256()
        paths = set()
        total = 0
        for item in objects:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("path"), str)
                or item["path"] in paths
                or type(item.get("size")) is not int
                or item["size"] <= 0
                or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", "")))
            ):
                raise ValueError("invalid sampled object evidence")
            paths.add(item["path"])
            total += item["size"]
            digest.update(
                json.dumps([item["path"], item["sha256"]], ensure_ascii=True).encode()
            )
        if (
            total != audit["source_hashed_bytes"]
            or digest.hexdigest() != audit["sample_content_sha256"]
        ):
            raise ValueError("sampled object evidence does not match receipt")
    return age


def freshness(marker, budget, now):
    """The latest archived snapshot time and its age; raise when over budget."""
    epoch = snapshots.read_latest_epoch(marker)
    if epoch is None:
        raise ValueError("no archived snapshot freshness marker")
    age = now - epoch
    if age > budget:
        raise ValueError(f"latest archived snapshot is {age}s old")
    return epoch, age


def producer_succeeded(unit):
    """True when the systemd unit's last run succeeded."""
    return (
        snapshots.run("systemctl", "show", "--value", "--property=Result", unit).strip()
        == "success"
    )
