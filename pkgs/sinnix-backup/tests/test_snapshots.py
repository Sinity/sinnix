"""Snapshot names, Btrfs identities and the snapshot inventory over synthetic subvolumes."""

import errno
import json
import os
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sinnix_backup import snapshots

FS_UUID = "22222222-2222-2222-2222-222222222222"


class SnapshotInventoryFixture(unittest.TestCase):
    def test_empty_and_filtered_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(snapshots.snapshot_names(root, "realm.*"), [])
            old = "realm.20261015T020000+0200"
            new = "realm.20261016T020000+0200"
            for name in (new, old, "persist.20261016T020000+0200"):
                (root / name).mkdir()
            (root / "realm.20261014T020000+0200").symlink_to(root / old)
            (root / "realm.20261013T020000+0200").touch()
            self.assertEqual(snapshots.snapshot_names(root, "realm.*"), [old, new])

    def test_unavailable_root_is_not_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "snapshots"
            with self.assertRaises(FileNotFoundError):
                snapshots.snapshot_names(root, "realm.*")
            root.touch()
            with self.assertRaises(NotADirectoryError):
                snapshots.snapshot_names(root, "realm.*")
        with patch.object(
            os, "scandir", side_effect=PermissionError(errno.EACCES, "denied")
        ):
            with self.assertRaises(PermissionError):
                snapshots.snapshot_names("/synthetic/snapshots", "realm.*")

    def test_entry_lookup_error_is_not_omitted(self):
        entry = SimpleNamespace(name="realm.20261016T020000+0200")

        def unavailable(**kwargs):
            raise OSError(errno.EIO, "entry lookup failed")

        entry.stat = unavailable
        with patch.object(
            os, "scandir", return_value=nullcontext(iter([entry]))
        ):
            with self.assertRaises(OSError):
                snapshots.snapshot_names("/synthetic/snapshots", "realm.*")


class FilesystemIdentityFixture(unittest.TestCase):
    def test_exact_filesystem_uuid_is_required(self):
        mount = json.dumps(
            {"filesystems": [{"target": "/synthetic", "fstype": "btrfs"}]}
        )
        with patch.object(
            snapshots, "run", side_effect=[mount, f"Label: 'fixture'  uuid: {FS_UUID}\n"]
        ) as probe:
            self.assertEqual(
                snapshots.filesystem_identity("/synthetic/nested/snapshot"), FS_UUID
            )
            self.assertEqual(
                probe.call_args_list[0].args,
                (
                    "findmnt",
                    "--json",
                    "--output",
                    "TARGET,FSTYPE",
                    "--target",
                    "/synthetic/nested/snapshot",
                ),
            )
            self.assertEqual(
                probe.call_args_list[1].args,
                ("btrfs", "filesystem", "show", "--raw", "/synthetic"),
            )
        for output in ("", f"UUID: {FS_UUID}\n", f"Label: none uuid: {FS_UUID}\n" * 2):
            with patch.object(snapshots, "run", side_effect=[mount, output]):
                with self.assertRaisesRegex(
                    ValueError, "identify one Btrfs filesystem"
                ):
                    snapshots.filesystem_identity("/synthetic/nested/snapshot")
        for mounts in ([], [{"target": "/synthetic", "fstype": "ext4"}]):
            with patch.object(
                snapshots, "run", return_value=json.dumps({"filesystems": mounts})
            ):
                with self.assertRaisesRegex(ValueError, "identify one Btrfs mount"):
                    snapshots.filesystem_identity("/synthetic/nested/snapshot")

    def test_automount_trigger_does_not_hide_backing_filesystem(self):
        backing = {"target": "/synthetic", "fstype": "btrfs"}
        trigger = {"target": "/synthetic", "fstype": "autofs"}
        with patch.object(
            snapshots,
            "run",
            side_effect=[
                json.dumps({"filesystems": [trigger, backing]}),
                f"Label: 'fixture'  uuid: {FS_UUID}\n",
            ],
        ):
            self.assertEqual(snapshots.filesystem_identity("/synthetic/cut"), FS_UUID)
        for mounts in (
            [trigger],
            [trigger, backing, backing],
            [backing, trigger | {"target": "/other"}],
            [backing, trigger | {"fstype": "ext4"}],
        ):
            with patch.object(
                snapshots, "run", return_value=json.dumps({"filesystems": mounts})
            ):
                with self.assertRaisesRegex(ValueError, "identify one Btrfs mount"):
                    snapshots.filesystem_identity("/synthetic/cut")
