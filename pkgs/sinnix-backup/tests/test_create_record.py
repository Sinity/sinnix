"""Creation records and their verification against the Borg create command."""

import hashlib
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from sinnix_backup import audit, borg, coverage, create_record, snapshots

FS_UUID = "22222222-2222-2222-2222-222222222222"


class ProducerReceiptFixture(unittest.TestCase):
    def setUp(self):
        filesystem_probe = patch.object(
            snapshots, "filesystem_identity", return_value=FS_UUID
        )
        filesystem_probe.start()
        self.addCleanup(filesystem_probe.stop)

    def test_create_receipt_binds_exact_command_snapshot_archive_and_policy(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as scratch:
            root = Path(scratch)
            source = root / "mounted"
            source.mkdir()
            policy = {
                "noncanonical": [],
                "chrome_extension_caches": False,
                "borg_excludes": ["run/borgbackup-snapshot-inputs/realm/cache"],
                "producer_contract": create_record.REALM_PRODUCER_CONTRACT,
            }
            uuid_value = str(uuid.uuid4())
            archive = "realm-realm.20260402T033000+0200"
            archive_id = "a" * 64
            command = borg.snapshot_create_command(
                "/store/borg",
                source,
                archive,
                uuid_value,
                policy,
                borg.archive_timestamp(archive),
            )
            stats = {
                "archive": {
                    "command_line": command,
                    "name": archive,
                    "id": archive_id,
                    "stats": {
                        "original_size": 123,
                        "compressed_size": 80,
                        "deduplicated_size": 17,
                    },
                }
            }
            details = (uuid_value, 17, 117)
            with (
                patch.object(snapshots, "snapshot_details", return_value=details),
                patch.object(snapshots, "archive_identity", return_value=archive_id),
            ):
                receipt = create_record.record_create(source, archive, policy, stats)
                receipt_path = root / "receipt.json"
                receipt_path.write_text(json.dumps(receipt))
                proof = create_record.verify_created(
                    source, archive, uuid_value, policy, receipt_path
                )
                self.assertEqual(proof["proof_mode"], "created")
                self.assertEqual(proof["source_hashed_bytes"], 0)
                self.assertEqual(proof["archive_id"], archive_id)
                self.assertEqual(proof["filesystem_uuid"], FS_UUID)
                self.assertEqual(proof["created_epoch"], receipt["created_epoch"])
                for name, expected in (
                    ("original", 123),
                    ("compressed", 80),
                    ("deduplicated", 17),
                ):
                    self.assertEqual(receipt["create_" + name + "_bytes"], expected)
                    self.assertEqual(proof["create_" + name + "_bytes"], expected)
                legacy = {
                    key: value
                    for key, value in receipt.items()
                    if key
                    not in (
                        "create_compressed_bytes",
                        "create_deduplicated_bytes",
                        "created_epoch",
                    )
                }
                receipt_path.write_text(json.dumps(legacy))
                legacy_proof = create_record.verify_created(
                    source, archive, uuid_value, policy, receipt_path
                )
                self.assertNotIn("create_deduplicated_bytes", legacy_proof)
                self.assertNotIn("create_compressed_bytes", legacy_proof)
                self.assertNotIn("created_epoch", legacy_proof)
                for invalid in (-1, True, "17", 1.5, None):
                    receipt_path.write_text(
                        json.dumps(receipt | {"created_epoch": invalid})
                    )
                    with self.assertRaisesRegex(ValueError, "timestamp"):
                        create_record.verify_created(
                            source, archive, uuid_value, policy, receipt_path
                        )
                for name in ("original", "compressed", "deduplicated"):
                    for invalid in (-1, True, "17", 1.5, None):
                        bad = json.loads(json.dumps(stats))
                        bad["archive"]["stats"][name + "_size"] = invalid
                        with self.subTest(name=name, invalid=invalid):
                            with self.assertRaisesRegex(ValueError, "byte count"):
                                create_record.record_create(
                                    source, archive, policy, bad
                                )
                            receipt_path.write_text(
                                json.dumps(
                                    receipt | {"create_" + name + "_bytes": invalid}
                                )
                            )
                            with self.assertRaisesRegex(ValueError, "byte count"):
                                create_record.verify_created(
                                    source, archive, uuid_value, policy, receipt_path
                                )
                for altered in (
                    receipt | {"filesystem_uuid": str(uuid.uuid4())},
                    {
                        key: value
                        for key, value in receipt.items()
                        if key != "filesystem_uuid"
                    },
                ):
                    receipt_path.write_text(json.dumps(altered))
                    with self.assertRaisesRegex(ValueError, "receipt does not bind"):
                        create_record.verify_created(
                            source, archive, uuid_value, policy, receipt_path
                        )
                receipt_path.write_text(json.dumps(receipt))
                with patch.object(
                    snapshots, "filesystem_identity", return_value=str(uuid.uuid4())
                ):
                    with self.assertRaisesRegex(ValueError, "receipt does not bind"):
                        create_record.verify_created(
                            source, archive, uuid_value, policy, receipt_path
                        )
                bad_stats = json.loads(json.dumps(stats))
                bad_stats["archive"]["command_line"].extend(
                    [
                        "--exclude-if-present",
                        ".nobackup",
                    ]
                )
                with self.assertRaisesRegex(ValueError, "command differs"):
                    create_record.record_create(source, archive, policy, bad_stats)
                changed_policy = policy | {
                    "borg_excludes": [
                        "run/borgbackup-snapshot-inputs/realm/project/build/repo"
                    ],
                }
                with self.assertRaisesRegex(ValueError, "receipt does not bind"):
                    create_record.verify_created(
                        source, archive, uuid_value, changed_policy, receipt_path
                    )
                with self.assertRaises(FileNotFoundError):
                    create_record.verify_created(
                        source, archive, uuid_value, policy, root / "missing.json"
                    )

    def test_full_audit_receipt_overdue_until_independent_comparison_succeeds(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as scratch:
            root = Path(scratch)
            policy = {"noncanonical": [], "borg_excludes": []}
            receipt = root / "audit.json"
            with self.assertRaisesRegex(ValueError, "has not completed"):
                audit.audit_status(receipt, policy, 691200)
            marker = root / "latest"
            self.assertEqual(
                audit.audit_readiness(marker, policy),
                {"ready": False, "reason": "awaiting-acknowledged-archive"},
            )
            uuid_value = str(uuid.uuid4())
            archive_id = "a" * 64
            proof = {
                "policy_sha256": coverage.policy_identity(policy),
                "snapshot_uuid": uuid_value,
                "archive": "realm-fixture",
                "archive_id": archive_id,
            }
            marker.write_text(
                "snapshot=realm.20260402T010000+0000\narchive=realm-fixture\n"
                "generation=17\nsubvolume_id=117\n"
                f"coverage={json.dumps(proof)}\n"
            )
            self.assertTrue(audit.audit_readiness(marker, policy)["ready"])
            self.assertEqual(
                audit.audit_readiness(
                    marker, {"noncanonical": [], "borg_excludes": ["new-boundary"]}
                ),
                {"ready": False, "reason": "awaiting-current-policy-archive"},
            )
            self.assertFalse(receipt.exists())
            with (
                patch.object(
                    snapshots, "snapshot_details", return_value=(uuid_value, 17, 117)
                ),
                patch.object(snapshots, "archive_identity", return_value=archive_id),
                patch.object(
                    audit,
                    "verify",
                    return_value={
                        "content_sha256": "b" * 64,
                        "source_hashed_bytes": 123,
                        "archive_content_verified_bytes": 123,
                    },
                ),
            ):
                latest = audit.audit_latest(marker, root, policy)
            receipt.write_text(json.dumps(latest))
            self.assertEqual(latest["audit_mode"], "independent_full")
            self.assertEqual(latest["source_hashed_bytes"], 123)
            self.assertLessEqual(audit.audit_status(receipt, policy, 691200), 1)
            sampled = dict(
                latest,
                audit_mode="independent_metadata_sampled",
                content_coverage="partial",
                content_verification="bounded_sample",
                sampled_files=1,
                sample_byte_budget=128,
                sample_file_budget=1,
                sample_content_sha256=hashlib.sha256(
                    json.dumps(["neutral", "c" * 64], ensure_ascii=True).encode()
                ).hexdigest(),
                sample_objects=[{"path": "neutral", "sha256": "c" * 64, "size": 123}],
            )
            sampled.pop("content_sha256")
            receipt.write_text(json.dumps(sampled))
            with self.assertRaisesRegex(ValueError, "overdue"):
                audit.audit_status(receipt, policy, 691200)
            self.assertLessEqual(
                audit.audit_status(receipt, policy, 691200, mode="sampled"), 1
            )
            zero = dict(
                sampled,
                sampled_files=0,
                source_hashed_bytes=0,
                archive_content_verified_bytes=0,
                content_verification="not_performed",
                sample_objects=[],
                sample_content_sha256=hashlib.sha256().hexdigest(),
            )
            receipt.write_text(json.dumps(zero))
            with self.assertRaisesRegex(ValueError, "invalid bounded"):
                audit.audit_status(receipt, policy, 691200, mode="sampled")
            sampled["source_hashed_bytes"] = 129
            receipt.write_text(json.dumps(sampled))
            with self.assertRaisesRegex(ValueError, "invalid bounded"):
                audit.audit_status(receipt, policy, 691200, mode="sampled")
            latest["audited_epoch"] -= 691201
            receipt.write_text(json.dumps(latest))
            with self.assertRaisesRegex(ValueError, "overdue"):
                audit.audit_status(receipt, policy, 691200)


class DrainFixture(unittest.TestCase):
    def test_producer_timestamp_for_each_lane_and_collision(self):
        for lane in ("realm", "genome"):
            for suffix in ("", "-coverage-v3"):
                with self.subTest(lane=lane, suffix=suffix):
                    archive = f"{lane}-{lane}.20260402T033000+0200{suffix}"
                    command = borg.snapshot_create_command(
                        "/store/borg",
                        Path("/source"),
                        archive,
                        "fixture-uuid",
                        {"borg_excludes": []},
                        timestamp=borg.archive_timestamp(archive),
                    )
                    self.assertEqual(
                        command[command.index("--timestamp") + 1],
                        "2026-04-02T01:30:00",
                    )
        with self.assertRaisesRegex(ValueError, "no snapshot cut timestamp"):
            borg.snapshot_create_command(
                "/store/borg",
                Path("/source"),
                "genome-realm.20260402T033000+0200",
                "fixture-uuid",
                {"borg_excludes": []},
                timestamp=borg.archive_timestamp("genome-realm.20260402T033000+0200"),
            )
