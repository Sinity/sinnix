"""Audit and acquisition freshness probes over synthetic snapshots and archives."""

import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sinnix_backup import audit, coverage, create_record, markers, snapshots


class OnchangeFreshnessFixture(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.snapshots = self.root / "snapshots"
        self.snapshots.mkdir()
        self.marker = self.root / "latest"
        self.policy = {"noncanonical": [], "borg_excludes": []}
        self.old = "genome.20260101T000000+0000"
        self.new = "genome.20260102T000000+0000"
        self.young = "genome.20260102T230000+0000"
        self.details = {
            self.old: ("11111111-1111-1111-1111-111111111111", 10, 1),
            self.new: ("22222222-2222-2222-2222-222222222222", 11, 2),
            self.young: ("33333333-3333-3333-3333-333333333333", 12, 3),
        }
        (self.snapshots / self.old).mkdir()
        self.filesystem = "44444444-4444-4444-4444-444444444444"
        self.source_uuid = "55555555-5555-5555-5555-555555555555"
        self.source = self.root / "source"
        self.source.mkdir()
        self.fields = {
            "snapshot": self.old,
            "archive": "genome-" + self.old,
            "filesystem_uuid": self.filesystem,
            "generation": "10",
            "subvolume_id": "1",
            "coverage": json.dumps(
                {
                    "policy_sha256": coverage.policy_identity(
                        self.policy, require_borg_excludes=True
                    ),
                    "proof_mode": "created",
                    "producer": create_record.REALM_PRODUCER_CONTRACT,
                    "create_receipt_sha256": "c" * 64,
                    "archive": "genome-" + self.old,
                    "archive_id": "a" * 64,
                    "snapshot_uuid": self.details[self.old][0],
                }
            ),
        }
        self.publish()
        self.now = int(datetime(2026, 1, 3, tzinfo=timezone.utc).timestamp())
        self.enterContext(
            patch.object(time, "time", side_effect=lambda: self.now)
        )
        self.enterContext(
            patch.object(snapshots, "filesystem_identity", return_value=self.filesystem)
        )
        self.enterContext(
            patch.object(
                snapshots,
                "snapshot_details",
                side_effect=lambda p: self.details[Path(p).name],
            )
        )
        self.enterContext(patch.object(snapshots, "run", side_effect=self.metadata))
        self.enterContext(
            patch.object(
                snapshots,
                "archive_identity",
                side_effect=AssertionError("health must not open Borg"),
            )
        )
        self.inventory = self.root / "acquisition-inventory.json"
        self.publish_inventory()

    def publish(self):
        payload = "".join(f"{key}={value}\n" for key, value in self.fields.items())
        self.marker.write_text(payload)
        receipts = snapshots.acknowledgement_directory(self.marker)
        receipts.mkdir(exist_ok=True)
        (receipts / self.old).write_text(payload)

    def metadata(self, *args):
        self.assertEqual(args[:3], ("btrfs", "subvolume", "show"))
        if Path(args[3]) == self.source:
            return f"UUID: {self.source_uuid}\n"
        return f"Parent UUID: {self.source_uuid}\n"

    def publish_inventory(self):
        observed = snapshots.observe_acquisitions(
            self.snapshots, "genome.*", self.policy, self.source
        )
        self.inventory.write_text(json.dumps(observed))

    def probe(self):
        return audit.acquisition_freshness(
            self.inventory,
            "genome.*",
            self.marker,
            self.policy,
            36 * 3600,
            self.source,
            18 * 3600,
        )

    def test_unchanged_old_cut_is_current_without_borg_io(self):
        self.assertEqual(
            self.probe(),
            {"status": "accepted-current-observed-acquired-generation", "pending": 0},
        )

    def test_pending_debt_ages_oldest_acquisition_not_old_archive_or_new_arrival(self):
        for name in (self.new, self.young):
            (self.snapshots / name).mkdir()
        self.publish_inventory()
        self.assertEqual(self.probe()["oldest_pending_age_seconds"], 24 * 3600)
        self.now += 13 * 3600
        with self.assertRaisesRegex(ValueError, "pending onchange acquisition"):
            self.probe()

    def test_operator_reader_needs_no_snapshot_or_secret_access(self):
        self.source.chmod(0)
        self.snapshots.chmod(0)
        try:
            with patch.object(
                snapshots,
                "run",
                side_effect=AssertionError("reader must not run Btrfs/Borg"),
            ):
                self.assertEqual(self.probe()["pending"], 0)
        finally:
            self.source.chmod(0o700)
            self.snapshots.chmod(0o700)

    def test_nested_receipt_permission_failure_is_not_healthy(self):
        # The parent can be readable while an old per-snapshot namespace is
        # still inaccessible. The reader must fail rather than accept latest.
        receipts = snapshots.acknowledgement_directory(self.marker)
        original_reader = markers.read_marker

        def guarded_reader(path):
            if Path(path).parent == receipts:
                raise PermissionError("nested receipt namespace unavailable")
            return original_reader(path)

        with patch.object(markers, "read_marker", side_effect=guarded_reader):
            with self.assertRaises(PermissionError):
                self.probe()

    def test_missing_unavailable_and_changed_inputs_fail(self):
        self.marker.unlink()
        with self.assertRaises(ValueError):
            self.probe()
        # Publishing immutable inventory precedes archive completion and does
        # not need another acquisition after the new accepted marker appears.
        self.publish_inventory()
        self.publish()
        self.assertEqual(self.probe()["pending"], 0)
        self.inventory.unlink()
        with self.assertRaises(FileNotFoundError):
            self.probe()
        with patch.object(
            snapshots, "snapshot_names", side_effect=PermissionError("unavailable")
        ):
            with self.assertRaises(PermissionError):
                self.publish_inventory()
        with patch.object(snapshots, "run", side_effect=OSError("source unavailable")):
            with self.assertRaises(OSError):
                self.publish_inventory()
        with patch.object(
            snapshots,
            "filesystem_identity",
            side_effect=[self.filesystem, "another-volume"],
        ):
            with self.assertRaises(ValueError):
                self.publish_inventory()

    def test_stale_future_corrupt_projection_or_identity_fails(self):
        original = json.loads(self.inventory.read_text())
        for key, value in (
            ("schema", "unknown"),
            ("source_uuid", "66666666-6666-6666-6666-666666666666"),
            ("policy_sha256", "b" * 64),
            (
                "observed_at",
                datetime.fromtimestamp(self.now + 1, timezone.utc).isoformat(),
            ),
            (
                "observed_at",
                datetime.fromtimestamp(self.now - 19 * 3600, timezone.utc).isoformat(),
            ),
        ):
            self.inventory.write_text(json.dumps(dict(original, **{key: value})))
            with self.assertRaises(ValueError):
                self.probe()
        self.inventory.write_text(json.dumps(original))
        future = "genome.20260104T000000+0000"
        self.details[future] = ("77777777-7777-7777-7777-777777777777", 13, 4)
        (self.snapshots / future).mkdir()
        self.publish_inventory()
        with self.assertRaisesRegex(ValueError, "future"):
            self.probe()

    def test_failed_native_producer_rejects_even_a_previous_fresh_projection(self):
        with patch.object(snapshots, "run", return_value="exit-code"):
            self.assertFalse(audit.producer_succeeded("btrbk.service"))

    def test_stale_policy_or_changed_receipt_binding_fails(self):
        proof = json.loads(self.fields["coverage"])
        for key, value in (
            ("policy_sha256", "b" * 64),
            ("snapshot_uuid", self.details[self.new][0]),
            ("create_receipt_sha256", "invalid"),
        ):
            altered = dict(proof, **{key: value})
            self.fields["coverage"] = json.dumps(altered)
            self.publish()
            with self.assertRaises(ValueError):
                self.probe()
        self.fields["coverage"] = json.dumps(proof)
        self.publish()
        (snapshots.acknowledgement_directory(self.marker) / self.old).unlink()
        with self.assertRaises(ValueError):
            self.probe()
