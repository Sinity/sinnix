"""Records of successful Borg creates and the check of a created archive."""

import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

from . import borg, markers, snapshots
from .coverage import decode_policy, policy_identity, verify

FULL_PROOF_INTERVAL = 7 * 24 * 3600
REALM_PRODUCER_CONTRACT = "realm-borg-create-v2"


def previous_proof(marker, policy_hash, now, snapshot_directory):
    fields = markers.read_marker(marker)
    if fields is None:
        return None
    try:
        proof = json.loads(fields["coverage"])
        full_epoch = proof["full_proof_epoch"]
        details = snapshots.snapshot_details(
            Path(snapshot_directory) / fields["snapshot"]
        )
        if (
            fields.get("filesystem_uuid")
            != snapshots.filesystem_identity(snapshot_directory)
            or proof["policy_sha256"] != policy_hash
            or proof["proof_mode"] not in ("full", "created")
            or not re.fullmatch(r"[0-9a-f]{64}", proof["full_proof_content_sha256"])
            or not isinstance(full_epoch, int)
            or isinstance(full_epoch, bool)
            or full_epoch > now
            or now - full_epoch >= FULL_PROOF_INTERVAL
            or proof["archive"] != fields["archive"]
            or details
            != (
                proof["snapshot_uuid"],
                int(fields["generation"]),
                int(fields["subvolume_id"]),
            )
        ):
            return None
        if (
            proof["proof_mode"] == "full"
            and proof["content_sha256"] != proof["full_proof_content_sha256"]
        ):
            return None
        if proof["proof_mode"] == "created" and not re.fullmatch(
            r"[0-9a-f]{64}", proof["previous_proof_sha256"]
        ):
            return None
        if (
            snapshots.archive_identity(proof["archive"], proof["snapshot_uuid"])
            != proof["archive_id"]
        ):
            return None
    except (KeyError, TypeError, ValueError, OSError, subprocess.CalledProcessError):
        return None
    return proof


def record_create(source, archive, coverage, create_stats):
    policy_hash = policy_identity(coverage, require_borg_excludes=True)
    if coverage.get("producer_contract") != REALM_PRODUCER_CONTRACT:
        raise ValueError("unrecognized producer contract")
    uuid, generation, subvolume_id = snapshots.snapshot_details(source)
    created = create_stats["archive"]
    command = created["command_line"]
    if (
        not isinstance(command, list)
        or not command
        or command
        != borg.snapshot_create_command(
            command[0],
            source,
            archive,
            uuid,
            coverage,
            borg.archive_timestamp(archive),
        )
        or created["name"] != archive
    ):
        raise ValueError("Borg create command differs from declared producer contract")
    archive_id = snapshots.archive_identity(archive, uuid)
    if created["id"] != archive_id:
        raise ValueError("created archive identity changed")
    byte_counts = {}
    for name in ("original", "compressed", "deduplicated"):
        value = created["stats"][name + "_size"]
        if type(value) is not int or value < 0:
            raise ValueError("invalid Borg creation byte count")
        byte_counts["create_" + name + "_bytes"] = value
    return {
        "producer_contract": REALM_PRODUCER_CONTRACT,
        "filesystem_uuid": snapshots.filesystem_identity(source),
        "snapshot_uuid": uuid,
        "generation": generation,
        "subvolume_id": subvolume_id,
        "archive": archive,
        "archive_id": archive_id,
        "policy_sha256": policy_hash,
        "command_line": command,
        "command_sha256": hashlib.sha256(json.dumps(command).encode()).hexdigest(),
        **byte_counts,
        "created_epoch": int(time.time()),
    }


def verify_created(source, archive, uuid, coverage, receipt_path):
    started = time.monotonic()
    policy_hash = policy_identity(coverage, require_borg_excludes=True)
    receipt = json.loads(Path(receipt_path).read_text())
    details = snapshots.snapshot_details(source)
    if (
        coverage.get("producer_contract") != REALM_PRODUCER_CONTRACT
        or receipt["producer_contract"] != REALM_PRODUCER_CONTRACT
        or receipt.get("filesystem_uuid") != snapshots.filesystem_identity(source)
        or details
        != (receipt["snapshot_uuid"], receipt["generation"], receipt["subvolume_id"])
        or uuid != details[0]
        or receipt["archive"] != archive
        or receipt["policy_sha256"] != policy_hash
        or not isinstance(receipt["command_line"], list)
        or not receipt["command_line"]
        or receipt["command_line"]
        != borg.snapshot_create_command(
            receipt["command_line"][0],
            source,
            archive,
            uuid,
            coverage,
            # Creations recorded before timestamps were passed still verify.
            borg.archive_timestamp(archive)
            if "--timestamp" in receipt["command_line"]
            else None,
        )
        or receipt["command_sha256"]
        != hashlib.sha256(json.dumps(receipt["command_line"]).encode()).hexdigest()
    ):
        raise ValueError("creation receipt does not bind this snapshot and policy")
    archive_id = snapshots.archive_identity(archive, uuid)
    if archive_id != receipt["archive_id"]:
        raise ValueError("creation receipt archive identity changed")
    # Old receipts predate retention of these counts. Absence means unknown,
    # never zero; later borg info reports current uniqueness, not create cost.
    byte_counts = {}
    for name in ("original", "compressed", "deduplicated"):
        key = "create_" + name + "_bytes"
        if key not in receipt and name != "original":
            continue
        value = receipt[key]
        if type(value) is not int or value < 0:
            raise ValueError("invalid Borg creation byte count")
        byte_counts[key] = value
    if "created_epoch" in receipt:
        value = receipt["created_epoch"]
        if type(value) is not int or value < 0:
            raise ValueError("invalid Borg creation receipt timestamp")
        byte_counts["created_epoch"] = value
    return {
        "archive": archive,
        "archive_id": archive_id,
        "snapshot_uuid": uuid,
        "generation": details[1],
        "subvolume_id": details[2],
        "policy_sha256": policy_hash,
        "proof_mode": "created",
        "filesystem_uuid": receipt["filesystem_uuid"],
        "producer": REALM_PRODUCER_CONTRACT,
        "create_receipt_sha256": hashlib.sha256(
            Path(receipt_path).read_bytes()
        ).hexdigest(),
        **byte_counts,
        "create_seconds": receipt.get("create_seconds", 0),
        "source_hashed_bytes": 0,
        "archive_content_verified_bytes": 0,
        "verification_seconds": round(time.monotonic() - started, 3),
    }


def choose_check_mode(latest_marker, snapshot_directory, coverage):
    """The check mode: created when a verified predecessor exists, else full."""
    return (
        "created"
        if previous_proof(
            latest_marker,
            policy_identity(coverage, require_borg_excludes=True),
            int(time.time()),
            snapshot_directory,
        )
        is not None
        else "full"
    )


def compare_archive(
    source,
    archive,
    snapshot_uuid,
    coverage,
    *,
    mode="full",
    latest_marker=None,
    snapshot_directory=None,
):
    started = time.monotonic()
    now = int(time.time())
    policy_hash = policy_identity(coverage, require_borg_excludes=mode == "created")
    if mode == "created":
        if not latest_marker or not snapshot_directory:
            raise ValueError("created proof requires a verified predecessor")
        previous = previous_proof(latest_marker, policy_hash, now, snapshot_directory)
        if previous is None:
            raise ValueError("created proof has no current verified predecessor")
        if snapshots.snapshot_details(source)[0] != snapshot_uuid:
            raise ValueError("snapshot UUID changed during created proof")
    archive_id = snapshots.archive_identity(archive, snapshot_uuid)
    if mode == "full":
        noncanonical, chrome_extension_caches = decode_policy(coverage)
        result = verify(
            source,
            archive,
            noncanonical,
            chrome_extension_caches,
        )
        full_epoch = now
        full_content_hash = result["content_sha256"]
    else:
        result = {
            "source_hashed_bytes": 0,
            "archive_content_verified_bytes": 0,
            "producer": "successful_borg_create_v1",
            "previous_archive_id": previous["archive_id"],
            "previous_proof_sha256": hashlib.sha256(
                json.dumps(previous, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        }
        full_epoch = previous["full_proof_epoch"]
        full_content_hash = previous["full_proof_content_sha256"]
        if (
            previous_proof(
                latest_marker,
                policy_hash,
                int(time.time()),
                snapshot_directory,
            )
            != previous
        ):
            raise ValueError("verified predecessor changed during created proof")
    if snapshots.archive_identity(archive, snapshot_uuid) != archive_id:
        raise ValueError("archive changed during verification")
    return result | {
        "snapshot_uuid": snapshot_uuid,
        "archive_id": archive_id,
        "archive": archive,
        "proof_mode": mode,
        "policy_sha256": policy_hash,
        "full_proof_epoch": full_epoch,
        "full_proof_content_sha256": full_content_hash,
        "verification_seconds": round(time.monotonic() - started, 3),
    }
