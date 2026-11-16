"""Synthetic real-Borg coverage fixtures: metadata, ACLs, policy identity and content samples."""

import errno
import hashlib
import io
import json
import os
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import tracemalloc
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sinnix_backup import audit, coverage, create_record, markers, snapshots

os.environ.setdefault("BORG_HOST_ID", "backup-fixture@stable")


class CoverageMemoryFixture(unittest.TestCase):
    def test_streamed_large_inventory_stays_below_memory_budget(self):
        # Exercise verify's actual walk, metadata and content passes without
        # creating tens of thousands of real files or hashing private data.
        directory_count, files_per_directory = 100, 300
        empty_hash = __import__("hashlib").sha256(b"").hexdigest()
        real_path = Path

        class VirtualPath:
            def __init__(self, relative="."):
                self.relative = relative

            @property
            def name(self):
                return self.relative.rsplit("/", 1)[-1]

            def __truediv__(self, path):
                return VirtualPath(str(path))

            def __lt__(self, other):
                return self.relative < other.relative

            def lstat(self):
                directory = "/" not in self.relative
                return SimpleNamespace(
                    st_mode=(0o40700 if directory else 0o100600),
                    st_uid=1000,
                    st_gid=1000,
                    st_mtime_ns=0,
                    st_size=0,
                    st_ino=2**63 + 123,
                    st_dev=2**63 + 456,
                    st_rdev=0,
                )

            def iterdir(self):
                if self.relative == ".":
                    return (VirtualPath(f"dir-{i:03d}") for i in range(directory_count))
                return (
                    VirtualPath(f"{self.relative}/file-{i:03d}-" + "x" * 100)
                    for i in range(files_per_directory)
                )

            def open(self, mode):
                return io.BytesIO(b"")

        def paths():
            yield VirtualPath()
            for directory in VirtualPath().iterdir():
                yield directory
                yield from directory.iterdir()

        def items(command, parser):
            metadata = "dump-archive" in command
            for path in paths():
                st = path.lstat()
                if metadata:
                    yield {
                        "path": path.relative,
                        "mode": st.st_mode,
                        "uid": st.st_uid,
                        "gid": st.st_gid,
                        "mtime": st.st_mtime_ns,
                        "size": 0,
                    }
                elif "/" in path.relative:
                    yield {
                        "path": path.relative,
                        "healthy": True,
                        "size": 0,
                        "sha256": empty_hash,
                    }

        with (
            patch.object(
                coverage,
                "Path",
                new=lambda path: (
                    VirtualPath() if path == "synthetic-source" else real_path(path)
                ),
            ),
            patch.object(coverage, "command_items", new=items),
            patch.object(os, "listxattr", new=lambda path, **kw: []),
        ):
            tracemalloc.start()
            try:
                result = coverage.verify("synthetic-source", "synthetic-archive", [])
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
        self.assertEqual(result["canonical_entries"], 30101)
        self.assertEqual(result["source_hashed_bytes"], 0)
        print(f"streamed coverage Python peak: {peak} bytes for 30101 entries")
        self.assertLess(peak, 8 * 1024 * 1024)


FS_UUID = "22222222-2222-2222-2222-222222222222"


class CoverageFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix="backup-coverage-", dir=os.environ.get("TMPDIR")
        )
        self.root = Path(self.temp.name)
        self.env = os.environ.copy()
        os.environ.update(
            BORG_REPO=str(self.root / "repo"),
            BORG_CACHE_DIR=str(self.root / "cache"),
            BORG_SECURITY_DIR=str(self.root / "security"),
            BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK="yes",
        )
        os.environ.pop("BORG_PASSCOMMAND", None)
        self.borg("init", "--encryption=none")
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "same-name").write_text("old version")
        (self.source / "old-only").write_text("unique historical bytes")
        self.snapshot_uuid = str(uuid.uuid4())
        filesystem_probe = patch.object(
            snapshots, "filesystem_identity", return_value=FS_UUID
        )
        filesystem_probe.start()
        self.addCleanup(filesystem_probe.stop)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)
        self.temp.cleanup()

    def borg(self, *args):
        return subprocess.check_output(["borg", *args], text=True)

    def archive(self, name="snapshot", *options):
        self.borg(
            "create",
            "--comment",
            "sinnix-snapshot-v1:" + self.snapshot_uuid,
            *options,
            "::" + name,
            str(self.source) + "/./",
        )

    def test_archive_identity_filters_literal_names_without_prefix_substitution(self):
        self.archive("literal[1]")
        self.archive("literal1")
        self.assertNotEqual(
            snapshots.archive_identity("literal[1]", self.snapshot_uuid),
            snapshots.archive_identity("literal1", self.snapshot_uuid),
        )

    def test_newest_archive_cannot_release_an_unarchived_historical_version(self):
        queue = self.root / "unacknowledged-queue"
        queue.mkdir()
        old = "realm.20260401T010000+0000"
        new = "realm.20260402T010000+0000"
        (queue / old).mkdir()
        (queue / old / "unique-history").write_text("only in the older snapshot")
        (queue / new).mkdir()
        (self.source / "old-only").unlink()
        (self.source / "same-name").write_text("new version")
        archive = "realm-" + new
        self.archive(archive)
        proof = coverage.verify(self.source, archive, []) | {
            "snapshot_uuid": self.snapshot_uuid,
            "archive_id": snapshots.archive_identity(archive, self.snapshot_uuid),
            "archive": archive,
        }
        marker = self.root / "unacknowledged-latest"
        marker.write_text(
            f"archive={archive}\nsnapshot={new}\nfilesystem_uuid={FS_UUID}\n"
            f"generation=20\nsubvolume_id=102\ncoverage={json.dumps(proof)}\n"
        )
        details = {
            old: (str(uuid.uuid4()), 10, 101),
            new: (self.snapshot_uuid, 20, 102),
        }
        with patch.object(
            snapshots, "snapshot_details", side_effect=lambda path: details[path.name]
        ):
            self.assertEqual(
                snapshots.verified_prune_plan(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                ),
                [],
            )
            policy = {"noncanonical": [], "borg_excludes": []}
            proof.update(
                proof_mode="full", policy_sha256=coverage.policy_identity(policy, True)
            )
            fields = markers.read_marker(marker)
            fields["coverage"] = json.dumps(proof)
            marker.write_text(
                "".join(f"{key}={value}\n" for key, value in fields.items())
            )
            self.assertEqual(
                snapshots.acknowledged_snapshot(
                    queue, "realm.*", marker, "realm", "-coverage-v3", policy
                ),
                new,
            )
            changed_policy = {"noncanonical": ["changed-policy"], "borg_excludes": []}
            with self.assertRaisesRegex(ValueError, "active policy"):
                snapshots.acknowledged_snapshot(
                    queue, "realm.*", marker, "realm", "-coverage-v3", changed_policy
                )

    def test_each_released_snapshot_has_its_own_archive_and_receipt(self):
        queue = self.root / "queue"
        queue.mkdir()
        old = "realm.20260402T010000+0000"
        new = "realm.20260402T070000+0000"
        (queue / old).mkdir()
        (queue / new).mkdir()
        old_uuid = self.snapshot_uuid
        old_archive = "realm-" + old
        self.archive(old_archive)
        old_proof = coverage.verify(self.source, old_archive, []) | {
            "snapshot_uuid": old_uuid,
            "archive_id": snapshots.archive_identity(old_archive, old_uuid),
            "archive": old_archive,
        }
        self.snapshot_uuid = str(uuid.uuid4())
        (self.source / "old-only").unlink()
        (self.source / "same-name").write_text("new version")
        archive = "realm-" + new
        self.archive(archive)
        proof = coverage.verify(self.source, archive, []) | {
            "snapshot_uuid": self.snapshot_uuid,
            "archive_id": snapshots.archive_identity(archive, self.snapshot_uuid),
            "archive": archive,
        }
        marker = self.root / "latest"

        def receipt(name, native, proof_fields):
            return (
                f"archive={proof_fields['archive']}\nsnapshot={name}\nfilesystem_uuid={FS_UUID}\n"
                f"generation={native[1]}\nsubvolume_id={native[2]}\ncoverage={json.dumps(proof_fields)}\n"
            )

        details = {old: (old_uuid, 10, 101), new: (self.snapshot_uuid, 20, 102)}
        marker.write_text(receipt(new, details[new], proof))
        acknowledgements = snapshots.acknowledgement_directory(marker)
        acknowledgements.mkdir()
        with patch.object(
            snapshots, "snapshot_details", side_effect=lambda path: details[path.name]
        ):
            self.assertEqual(
                snapshots.queued_snapshots(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                ),
                [new, old],
            )
            self.assertEqual(
                snapshots.verified_prune_plan(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                ),
                [],
            )
            (acknowledgements / old).write_text(receipt(old, details[old], old_proof))
            self.assertEqual(
                snapshots.queued_snapshots(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                ),
                [new],
            )
            self.assertEqual(
                snapshots.verified_prune_plan(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                ),
                [(old, *details[old])],
            )
            (acknowledgements / new).write_bytes(marker.read_bytes())
            self.assertEqual(
                snapshots.queued_snapshots(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                ),
                [],
            )
            self.assertFalse(snapshots.should_advance_marker(queue, marker, old))
            rolled_back = "realm.20260401T233000+0000"
            (queue / rolled_back).mkdir()
            details[rolled_back] = (str(uuid.uuid4()), 30, 103)
            self.assertEqual(
                snapshots.queued_snapshots(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                ),
                [rolled_back],
            )
            self.assertTrue(snapshots.should_advance_marker(queue, marker, rolled_back))
            (acknowledgements / old).write_text(
                receipt(old, details[old], old_proof).replace(
                    old_proof["archive_id"], "a" * 64
                )
            )
            with self.assertRaisesRegex(ValueError, "archive identity changed"):
                snapshots.verified_prune_plan(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                )
            with self.assertRaisesRegex(ValueError, "archive identity changed"):
                snapshots.queued_snapshots(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                )
            (acknowledgements / old).write_text(receipt(old, details[old], old_proof))
            details[old] = (str(uuid.uuid4()), 10, 101)
            with self.assertRaisesRegex(ValueError, "snapshot identity changed"):
                snapshots.verified_prune_plan(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                )

    def test_missing_cutoff_cannot_prune_or_suppress_new_archival(self):
        queue = self.root / "replacement-queue"
        queue.mkdir()
        current = "realm.20260403T010000+0000"
        cutoff = "realm.20260402T070000+0000"
        (queue / current).mkdir()
        archive = "realm-" + cutoff
        marker = self.root / "missing-cutoff"
        marker.write_text(
            f"archive={archive}\nsnapshot={cutoff}\nfilesystem_uuid={FS_UUID}\ngeneration=200\nsubvolume_id=102\n"
            f"coverage={json.dumps({'snapshot_uuid': self.snapshot_uuid, 'archive': archive, 'archive_id': 'a' * 64})}\n"
        )
        # Lower generations can belong to a replacement filesystem. Neither
        # the old marker nor an existing Borg archive orders its snapshots.
        with (
            patch.object(
                snapshots, "snapshot_details", return_value=(str(uuid.uuid4()), 10, 101)
            ),
            patch.object(snapshots, "archive_identity", return_value="a" * 64),
        ):
            with self.assertRaisesRegex(ValueError, "snapshot is unavailable"):
                snapshots.verified_prune_plan(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                )
            self.assertEqual(
                snapshots.queued_snapshots(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                ),
                [current],
            )

    def test_cutoff_on_another_filesystem_never_authorizes_pruning(self):
        queue = self.root / "replacement-filesystem"
        queue.mkdir()
        current = "realm.20260403T010000+0000"
        (queue / current).mkdir()
        marker = self.root / "foreign-cutoff"
        archive = "realm-" + current
        marker.write_text(
            f"archive={archive}\nsnapshot={current}\nfilesystem_uuid={uuid.uuid4()}\n"
            "generation=20\nsubvolume_id=102\n"
            f"coverage={json.dumps({'snapshot_uuid': self.snapshot_uuid, 'archive': archive, 'archive_id': 'a' * 64})}\n"
        )
        with patch.object(
            snapshots, "snapshot_details", return_value=(self.snapshot_uuid, 20, 102)
        ):
            self.assertEqual(
                snapshots.queued_snapshots(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                ),
                [current],
            )
            with self.assertRaisesRegex(ValueError, "filesystem identity changed"):
                snapshots.verified_prune_plan(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                )
        # An older marker is history, not authority over current generations.
        marker.write_text(
            marker.read_text().replace(
                next(
                    line
                    for line in marker.read_text().splitlines(True)
                    if line.startswith("filesystem_uuid=")
                ),
                "",
            )
        )
        self.assertEqual(
            snapshots.verified_prune_plan(
                queue, "realm.*", marker, "realm", "-coverage-v3"
            ),
            [],
        )
        with patch.object(
            snapshots, "snapshot_details", return_value=(self.snapshot_uuid, 20, 102)
        ):
            self.assertEqual(
                snapshots.queued_snapshots(
                    queue, "realm.*", marker, "realm", "-coverage-v3"
                ),
                [current],
            )

    def test_inventory_failure_cleans_private_scratch(self):
        real_temp = tempfile.TemporaryDirectory
        created = []

        def scratch(**kwargs):
            temp = real_temp(dir=self.root, **kwargs)
            created.append(Path(temp.name))
            self.assertEqual(Path(temp.name).stat().st_mode & 0o777, 0o700)
            return temp

        with (
            patch.object(tempfile, "TemporaryDirectory", new=scratch),
            patch.object(
                coverage.CoverageInventory,
                "add",
                side_effect=sqlite3.OperationalError("database or disk is full"),
            ),
        ):
            with self.assertRaisesRegex(sqlite3.OperationalError, "disk is full"):
                coverage.verify(self.source, "unused", [])
        self.assertEqual(len(created), 1)
        self.assertFalse(created[0].exists())

    def test_duplicate_metadata_cannot_satisfy_coverage(self):
        self.archive()
        original = coverage.command_items

        def duplicate(command, parser):
            for item in original(command, parser):
                yield item
                if "dump-archive" in command:
                    yield item

        with patch.object(coverage, "command_items", new=duplicate):
            with self.assertRaisesRegex(ValueError, "duplicate archive path"):
                coverage.verify(self.source, "snapshot", [])

    def test_exact_versions_and_metadata(self):
        os.link(self.source / "same-name", self.source / "hardlink")
        (self.source / "symlink").symlink_to("same-name")
        self.archive()
        result = coverage.verify(self.source, "snapshot", [])
        self.assertEqual(result["canonical_entries"], 5)
        self.assertEqual(
            len(snapshots.archive_identity("snapshot", self.snapshot_uuid)), 64
        )
        with self.assertRaisesRegex(ValueError, "UUID"):
            snapshots.archive_identity("snapshot", str(uuid.uuid4()))
        old_stat = (self.source / "same-name").stat()
        (self.source / "same-name").write_text("new version")
        # Keep size and mtime identical: only reading archived/source bytes
        # can detect this change, not a listing or metadata-only comparison.
        os.utime(
            self.source / "same-name", ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns)
        )
        with self.assertRaisesRegex(ValueError, "content mismatch"):
            coverage.verify(self.source, "snapshot", [])

    def test_routine_child_deadline_kills_and_reaps_blocked_reader(self):
        token = coverage._COMMAND_TIMEOUT.set(0.05)
        started = time.monotonic()
        try:
            with self.assertRaisesRegex(ValueError, "exceeded.*budget"):
                list(
                    coverage.command_items(
                        [sys.executable, "-c", "import time; time.sleep(10)"],
                        lambda stream: iter(stream),
                    )
                )
            self.assertLess(time.monotonic() - started, 2)
        finally:
            coverage._COMMAND_TIMEOUT.reset(token)

    def test_slow_metadata_parser_does_not_hold_native_repository_lock(self):
        # Exceed the pipe capacity so the old streaming path keeps Borg alive
        # while the consumer pauses. A second writer must still acquire it.
        for i in range(1536):
            (self.source / (f"record-{i:04d}-" + "x" * 100)).write_bytes(b"neutral")
        self.archive()
        commands = [
            (
                ["borg", "debug", "dump-archive", "::snapshot", "/dev/stdout"],
                lambda stream: coverage.JsonStream(stream).items(),
            ),
            (
                [
                    "borg",
                    "list",
                    "--json-lines",
                    "--format",
                    "{path}{sha256}{health}{size}",
                    "::snapshot",
                ],
                lambda stream: (json.loads(line) for line in stream),
            ),
        ]
        for i, (command, parser) in enumerate(commands):
            with self.subTest(command=command[1]):
                items = coverage.command_items(command, parser)
                try:
                    self.assertIsInstance(next(items), dict)
                    self.archive(f"while-parser-paused-{i}", "--lock-wait", "1")
                finally:
                    items.close()

    def test_metadata_coverage_does_not_hash_payloads_or_claim_content_equality(self):
        self.archive()
        original = coverage.command_items

        def metadata_only(command, parser):
            self.assertNotIn("{path}{sha256}{health}{size}", command)
            yield from original(command, parser)

        with (
            patch.object(coverage, "command_items", new=metadata_only),
            patch.object(
                hashlib,
                "file_digest",
                side_effect=AssertionError("payload read"),
            ),
        ):
            result = coverage.verify(
                self.source, "snapshot", [], content_mode="metadata"
            )
        self.assertEqual(result["content_verification"], "not_performed")
        self.assertEqual(result["source_hashed_bytes"], 0)
        self.assertNotIn("content_sha256", result)

    def test_sample_has_exact_byte_file_bounds_and_continuation(self):
        self.archive()
        first = coverage.verify(
            self.source,
            "snapshot",
            [],
            content_mode="sampled",
            sample_bytes=24,
            sample_files=1,
        )
        self.assertEqual(first["sampled_files"], 1)
        self.assertEqual(first["source_hashed_bytes"], len("unique historical bytes"))
        self.assertEqual(first["sample_next_after"], "old-only")
        self.assertEqual(first["sample_objects"][0]["path"], "old-only")
        second = coverage.verify(
            self.source,
            "snapshot",
            [],
            content_mode="sampled",
            sample_bytes=24,
            sample_files=1,
            sample_after=first["sample_next_after"],
        )
        self.assertEqual(second["sample_next_after"], "same-name")
        self.assertEqual(second["sample_start_after"], "old-only")
        self.assertEqual(second["source_hashed_bytes"], len("old version"))
        self.assertEqual(second["content_coverage"], "partial")
        self.assertNotIn("content_sha256", second)
        no_fit = coverage.verify(
            self.source,
            "snapshot",
            [],
            content_mode="sampled",
            sample_bytes=1,
            sample_files=1,
        )
        self.assertEqual(no_fit["source_hashed_bytes"], 0)
        self.assertEqual(no_fit["sampled_files"], 0)

    def test_oversized_only_population_never_claims_sampled_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = coverage.CoverageInventory(root / "inventory.sqlite")
            try:
                for name in ("large-a", "large-b"):
                    path = root / name
                    with path.open("wb") as stream:
                        stream.truncate(1073741825)
                    inventory.add(name, path.stat())
                with patch.object(
                    coverage,
                    "command_items",
                    side_effect=AssertionError("no selected content"),
                ):
                    result = coverage.verify_content_sample(
                        root,
                        "unused",
                        inventory,
                        byte_budget=1073741824,
                        file_budget=128,
                    )
                self.assertEqual(result["sampled_files"], 0)
                self.assertEqual(result["content_verification"], "not_performed")
                self.assertEqual(
                    result["sample_excluded_population"]["over_byte_budget_files"], 2
                )
                self.assertIn("other_retained_archives", result["sample_excludes"])
                self.assertNotIn("content_sha256", result)
            finally:
                inventory.db.close()

    def test_sampling_wraps_eof_and_skips_oversized_prefix_without_stalling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = coverage.CoverageInventory(root / "inventory.sqlite")
            try:
                for i in range(8):
                    path = root / f"a-large-{i}"
                    path.write_bytes(b"x" * 100)
                    inventory.add(path.name, path.stat())
                path = root / "z-small"
                path.write_bytes(b"ok")
                inventory.add(path.name, path.stat())

                def items(command, parser):
                    yield {
                        "path": path.name,
                        "size": 2,
                        "healthy": True,
                        "sha256": hashlib.sha256(b"ok").hexdigest(),
                    }

                with patch.object(coverage, "command_items", new=items):
                    first = coverage.verify_content_sample(
                        root, "unused", inventory, byte_budget=2, file_budget=1
                    )
                    wrapped = coverage.verify_content_sample(
                        root,
                        "unused",
                        inventory,
                        byte_budget=2,
                        file_budget=1,
                        after="z-small",
                    )
                self.assertEqual(first["sampled_files"], 1)
                self.assertEqual(
                    first["sample_excluded_population"]["over_byte_budget_files"], 8
                )
                self.assertTrue(wrapped["sample_cursor_wrapped"])
                self.assertEqual(wrapped["sampled_files"], 1)
            finally:
                inventory.db.close()

    def test_sample_matches_literal_glob_and_newline_names(self):
        for name in ("a1", "a[1]", "b\n[1]ą"):
            (self.source / name).write_text("neutral")
        self.archive()
        for after, expected in (("a1", "a[1]"), ("a[1]", "b\n[1]ą")):
            result = coverage.verify(
                self.source,
                "snapshot",
                [],
                content_mode="sampled",
                sample_bytes=100,
                sample_files=1,
                sample_after=after,
            )
            self.assertEqual(result["sampled_files"], 1)
            self.assertEqual(result["sample_next_after"], expected)
            self.assertEqual(result["sample_objects"][0]["path"], expected)
            self.assertEqual(result["source_hashed_bytes"], 7)

    def test_sample_refuses_changed_bytes_while_metadata_remains_weaker(self):
        self.archive()
        path = self.source / "same-name"
        previous = path.stat()
        path.write_text("new version")
        os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
        result = coverage.verify(self.source, "snapshot", [], content_mode="metadata")
        self.assertEqual(result["content_verification"], "not_performed")
        with self.assertRaisesRegex(ValueError, "sampled archive content mismatch"):
            coverage.verify(self.source, "snapshot", [], content_mode="sampled")

    def test_created_proof_requires_current_full_anchor_and_borg_reads_changed_bytes(
        self,
    ):
        policy = {"noncanonical": [], "borg_excludes": []}
        archive = "first"
        self.archive(archive)
        full_content_hash = coverage.verify(self.source, archive, [])["content_sha256"]
        previous = {
            "archive": archive,
            "archive_id": snapshots.archive_identity(archive, self.snapshot_uuid),
            "snapshot_uuid": self.snapshot_uuid,
            "proof_mode": "full",
            "full_proof_epoch": int(time.time()),
            "content_sha256": full_content_hash,
            "full_proof_content_sha256": full_content_hash,
            "policy_sha256": coverage.policy_identity(policy),
        }
        snapshot_directory = self.root / "snapshots"
        snapshot_directory.mkdir()
        (snapshot_directory / "realm.20260402T010000+0000").mkdir()
        marker = self.root / "latest"
        marker.write_text(
            "archive=first\nsnapshot=realm.20260402T010000+0000\n"
            f"filesystem_uuid={FS_UUID}\ngeneration=20\nsubvolume_id=102\n"
            f"coverage={json.dumps(previous)}\n"
        )
        details = (self.snapshot_uuid, 20, 102)
        with patch.object(snapshots, "snapshot_details", return_value=details):
            self.assertEqual(
                create_record.previous_proof(
                    marker,
                    previous["policy_sha256"],
                    int(time.time()),
                    snapshot_directory,
                ),
                previous,
            )
            old_stat = (self.source / "same-name").stat()
            (self.source / "same-name").write_text("new version")
            os.utime(
                self.source / "same-name",
                ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns),
            )
            self.archive("second")
            self.assertEqual(
                self.borg("extract", "--stdout", "::second", "same-name"),
                "new version",
            )
            created = create_record.compare_archive(
                self.source,
                "second",
                self.snapshot_uuid,
                policy,
                mode="created",
                latest_marker=marker,
                snapshot_directory=snapshot_directory,
            )
            self.assertEqual(created["proof_mode"], "created")
            self.assertEqual(created["previous_archive_id"], previous["archive_id"])
            self.assertEqual(created["source_hashed_bytes"], 0)
            changed_policy = {"noncanonical": ["old-only"]}
            self.assertIsNone(
                create_record.previous_proof(
                    marker,
                    coverage.policy_identity(changed_policy),
                    int(time.time()),
                    snapshot_directory,
                )
            )
            changed_excludes = {
                "noncanonical": [],
                "borg_excludes": ["bind/project/build"],
            }
            self.assertIsNone(
                create_record.previous_proof(
                    marker,
                    coverage.policy_identity(changed_excludes),
                    int(time.time()),
                    snapshot_directory,
                )
            )
            self.assertIsNone(
                create_record.previous_proof(
                    marker,
                    previous["policy_sha256"],
                    previous["full_proof_epoch"] + create_record.FULL_PROOF_INTERVAL,
                    snapshot_directory,
                )
            )
            marker.write_text(
                marker.read_text().replace(previous["archive_id"], "a" * 64)
            )
            self.assertIsNone(
                create_record.previous_proof(
                    marker,
                    previous["policy_sha256"],
                    int(time.time()),
                    snapshot_directory,
                )
            )
            with self.assertRaisesRegex(ValueError, "no current verified predecessor"):
                create_record.compare_archive(
                    self.source,
                    "second",
                    self.snapshot_uuid,
                    policy,
                    mode="created",
                    latest_marker=marker,
                    snapshot_directory=snapshot_directory,
                )

    def test_archive_identity_uses_exact_repository_listing_entry(self):
        listing = json.dumps(
            {
                "archives": [
                    {
                        "archive": "snapshot-old",
                        "id": "a" * 64,
                        "comment": "sinnix-snapshot-v1:" + self.snapshot_uuid,
                    },
                    {
                        "archive": "snapshot",
                        "id": "b" * 64,
                        "comment": "sinnix-snapshot-v1:" + self.snapshot_uuid,
                    },
                ]
            }
        )
        with patch.object(snapshots, "run", return_value=listing) as command:
            self.assertEqual(
                snapshots.archive_identity("snapshot", self.snapshot_uuid), "b" * 64
            )
            command.assert_called_once_with(
                "borg",
                "list",
                "--json",
                "--format",
                "{comment}",
                "--glob-archives",
                "snapshot",
            )
            with self.assertRaisesRegex(ValueError, "UUID"):
                snapshots.archive_identity("absent", self.snapshot_uuid)
        self.assertEqual(coverage.decode_policy(["run"]), (["run"], False))
        self.assertEqual(
            coverage.decode_policy(
                {"noncanonical": ["run"], "chrome_extension_caches": True}
            ),
            (["run"], True),
        )

    def test_borg_checkpoint_parts_are_not_source_items_or_complete_file_proof(self):
        self.archive("checkpointed")
        original = coverage.command_items
        partial = {"path": "same-name.borg_part_1", "part": 1}

        def with_part(command, parser):
            if command[1:3] == ["debug", "dump-archive"]:
                yield partial
            yield from original(command, parser)

        with patch.object(coverage, "command_items", side_effect=with_part):
            self.assertEqual(
                coverage.verify(self.source, "checkpointed", [])["canonical_entries"],
                3,
            )

        def part_without_complete_file(command, parser):
            if command[1:3] == ["debug", "dump-archive"]:
                yield partial
                yield from (
                    item
                    for item in original(command, parser)
                    if item.get("path") != "same-name"
                )
            else:
                yield from original(command, parser)

        with patch.object(
            coverage, "command_items", side_effect=part_without_complete_file
        ):
            with self.assertRaisesRegex(ValueError, "canonical content missing"):
                coverage.verify(self.source, "checkpointed", [])

    def test_extended_attributes(self):
        try:
            os.setxattr(
                self.source / "same-name", "user.fixture", b"synthetic\x00value"
            )
        except OSError as error:
            if error.errno == errno.ENOTSUP:
                self.skipTest("fixture filesystem does not support xattrs")
            raise
        self.archive()
        coverage.verify(self.source, "snapshot", [])
        os.setxattr(self.source / "same-name", "user.fixture", b"changed")
        with self.assertRaisesRegex(ValueError, "extended metadata"):
            coverage.verify(self.source, "snapshot", [])

    def test_posix_acls_compare_through_borgs_own_fields(self):
        # Borg keeps POSIX ACLs in its own acl_access/acl_default item fields
        # and emits no xattrs entry for them, so a verifier that compares raw
        # listxattr output against the archived xattrs mismatches forever on
        # any ACL'd path. The Nix build sandbox cannot create an ACL
        # ("setfacl: Operation not supported"), so the comparison is exercised
        # directly rather than through a fixture that would silently skip.
        acl_markers, ordinary = coverage.partition_acl_xattrs(
            ["system.posix_acl_access", "user.fixture", "system.posix_acl_default"]
        )
        self.assertEqual(
            acl_markers, {b"system.posix_acl_access", b"system.posix_acl_default"}
        )
        self.assertEqual(ordinary, ["user.fixture"])
        text = "user::rwx\nuser:neutral:r--:1000\ngroup::r-x\nmask::r-x\nother::---"
        expected = {
            (1, None): 7,
            (2, 1000): 4,
            (4, None): 5,
            (16, None): 5,
            (32, None): 0,
        }
        raw = struct.pack("<I", 2) + b"".join(
            struct.pack(
                "<HHI", tag, perm, identity if identity is not None else 0xFFFFFFFF
            )
            for (tag, identity), perm in expected.items()
        )
        self.assertEqual(coverage.source_acl_entries(raw), expected)
        self.assertEqual(coverage.archived_acl_entries(text), expected)
        self.assertEqual(
            coverage.archived_acl_entries(text.replace("neutral", "renamed")), expected
        )
        encoded = (
            "\x7f"
            + text.replace("neutral", "invalid-\udcff")
            .encode("utf-8", "surrogateescape")
            .hex()
        )
        self.assertEqual(coverage.archived_acl_entries(encoded), expected)

    def test_changed_acl_principal_or_permission_cannot_satisfy_coverage(self):
        self.archive()
        path = self.source / "same-name"
        source_entries = [
            (1, 6, 0xFFFFFFFF),
            (2, 4, 1000),
            (4, 4, 0xFFFFFFFF),
            (16, 4, 0xFFFFFFFF),
            (32, 4, 0xFFFFFFFF),
        ]
        raw = struct.pack("<I", 2) + b"".join(
            struct.pack("<HHI", *entry) for entry in source_entries
        )
        archived = {"uid": 1000, "permission": "r--"}
        original_items = coverage.command_items
        original_list = os.listxattr
        original_get = os.getxattr

        def items(command, parser):
            for item in original_items(command, parser):
                if "debug" in command and coverage.archive_path(item) == "same-name":
                    item = {
                        **item,
                        "acl_access": f"user::rw-\nuser:neutral:{archived['permission']}:{archived['uid']}\ngroup::r--\nmask::r--\nother::r--",
                    }
                yield item

        def names(candidate, **kw):
            return (
                ["system.posix_acl_access"]
                if Path(candidate) == path
                else original_list(candidate, **kw)
            )

        def value(candidate, name, **kw):
            return (
                raw
                if Path(candidate) == path
                and os.fsencode(name) == b"system.posix_acl_access"
                else original_get(candidate, name, **kw)
            )

        with (
            patch.object(coverage, "command_items", items),
            patch.object(os, "listxattr", names),
            patch.object(os, "getxattr", value),
        ):
            coverage.verify(self.source, "snapshot", [])
            archived["uid"] = 1001
            with self.assertRaisesRegex(ValueError, "ACL mismatch"):
                coverage.verify(self.source, "snapshot", [])
            archived.update(uid=1000, permission="---")
            with self.assertRaisesRegex(ValueError, "ACL mismatch"):
                coverage.verify(self.source, "snapshot", [])

    def test_masked_named_acl_accepts_borg_permission_padding(self):
        # Captured from a neutral native Borg archive with a named rwx entry
        # restricted by an r-- mask. Preserve the stored permission, not its
        # effective masked value; formatting whitespace carries no semantics.
        text = "user::rw-\nuser:1001:rwx\t:1001\ngroup::r--\nmask::r--\nother::r--"
        expected = {
            (1, None): 6,
            (2, 1001): 7,
            (4, None): 4,
            (16, None): 4,
            (32, None): 4,
        }
        self.assertEqual(coverage.archived_acl_entries(text), expected)
        self.assertNotEqual(
            coverage.archived_acl_entries(text.replace("rwx\t", "r--\t")), expected
        )

    def test_default_only_acl_uses_mode_for_borg_access_entries(self):
        entries = [
            (1, 7, 0xFFFFFFFF),
            (2, 4, 1000),
            (4, 5, 0xFFFFFFFF),
            (16, 5, 0xFFFFFFFF),
            (32, 5, 0xFFFFFFFF),
        ]
        raw = struct.pack("<I", 2) + b"".join(
            struct.pack("<HHI", *entry) for entry in entries
        )
        item = {
            "acl_access": "user::rwx\ngroup::r-x\nother::r-x",
            "acl_default": "user::rwx\nuser:neutral:r--:1000\ngroup::r-x\nmask::r-x\nother::r-x",
        }
        with patch.object(os, "getxattr", return_value=raw):
            coverage.verify_acl_metadata(
                self.source, 0o755, {b"system.posix_acl_default"}, item
            )
            with self.assertRaisesRegex(ValueError, "ACL mismatch"):
                coverage.verify_acl_metadata(
                    self.source,
                    0o755,
                    {b"system.posix_acl_default"},
                    {**item, "acl_default": ""},
                )

    def test_metadata_contract_changes_the_policy_proof_identity(self):
        policy = {"noncanonical": [], "borg_excludes": []}
        legacy = hashlib.sha256(
            json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertNotEqual(coverage.policy_identity(policy), legacy)
        with patch.object(coverage, "METADATA_CONTRACT", "older-weaker-contract"):
            older = coverage.policy_identity(policy)
        self.assertNotEqual(coverage.policy_identity(policy), older)

    def test_malformed_acl_refuses_instead_of_waiving_metadata(self):
        for raw in [
            b"",
            struct.pack("<I", 3),
            struct.pack("<IHHI", 2, 2, 4, 0xFFFFFFFF),
        ]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                coverage.source_acl_entries(raw)
        for text in [
            "user:unknown:rwx",
            "user::rwx\nuser::rwx",
            "user::rwx\ngroup::r-x\nother::r-X",
            "user::rwx\nuser:neutral:r--:1000\ngroup::r-x\nother::---",
        ]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                coverage.archived_acl_entries(text)

    def test_nested_subvolume_stub_mtime_is_not_coverage(self):
        # Snapshotting a subvolume replaces each nested subvolume with an
        # inode-2 stub whose mtime follows the live subvolume, not the frozen
        # snapshot: sampled seconds apart on this host it advanced with the
        # wall clock, so it can never match what Borg archived. A build sandbox
        # cannot create a btrfs subvolume, so the exemption is exercised
        # directly rather than through a fixture that would have to skip.
        self.assertEqual(
            coverage.metadata_keys_for("ordinary/path", frozenset()),
            ("mode", "uid", "gid", "mtime"),
        )
        stub = ".btrfs/snapshot/persist.20260913T023000+0200"
        self.assertEqual(
            coverage.metadata_keys_for(stub, frozenset({stub})),
            ("mode", "uid", "gid"),
        )
        # Ownership and mode remain compared for a stub: only the mtime is
        # meaningless, and dropping the rest would stop proving anything.
        self.assertIn("mode", coverage.metadata_keys_for(stub, frozenset({stub})))
        self.assertIn("uid", coverage.metadata_keys_for(stub, frozenset({stub})))

    def test_unix_sockets_are_not_coverage(self):
        # Borg dispatches on file type and skips a socket outright, so
        # requiring one to be covered makes the lane permanently unprovable
        # while waiving no bytes. A FIFO in the same directory is archived and
        # exemption: it names one file type, not "anything unusual".
        import socket as socket_module

        sock = socket_module.socket(socket_module.AF_UNIX)
        try:
            sock.bind(str(self.source / "live.sock"))
        except OSError as error:
            sock.close()
            self.skipTest(f"fixture filesystem cannot host a unix socket: {error}")
        try:
            self.archive()
            result = coverage.verify(self.source, "snapshot", [])
            self.assertEqual(result["unarchivable_entries"], ["live.sock"])
            modes = coverage.is_unarchivable_type
            self.assertTrue(modes(os.lstat(self.source / "live.sock").st_mode))
            # Ordinary content is untouched by the exemption: this is a
            # file-type rule, not a blanket waiver for anything unusual.
            self.assertFalse(modes(os.lstat(self.source / "same-name").st_mode))
            self.assertFalse(modes(os.lstat(self.source).st_mode))
        finally:
            sock.close()

    def test_fifos_are_covered_not_rejected(self):
        # Borg archives a FIFO (as metadata alone) but the verifier used to
        # reject the type outright, which made the realm lane unprovable over
        # a single netdata timer FIFO.
        os.mkfifo(self.source / "timer.fifo")
        self.archive()
        before = coverage.verify(self.source, "snapshot", [])
        # It is covered, not exempted: the socket exemption must not have
        # swallowed it, and it counts toward the canonical entry total.
        self.assertNotIn("timer.fifo", before.get("unarchivable_entries", []))
        self.assertEqual(
            before["canonical_entries"],
            sum(1 for _ in self.source.rglob("*")) + 1,
        )
        # Its metadata is still proved: a changed mode must be caught.
        os.chmod(self.source / "timer.fifo", 0o600)
        with self.assertRaisesRegex(ValueError, "mode mismatch"):
            coverage.verify(self.source, "snapshot", [])

    def test_non_utf8_filenames_are_covered(self):
        # Borg's debug JSON cannot hold a non-UTF-8 name as text and encodes it
        # as DEL plus hex. Comparing that raw against fsdecode'd walk keys never
        # matches, which stalled the realm lane on a Facebook export whose name
        # carries a Latin-1 byte.
        raw = os.fsencode(self.source) + b"/Micha\xe9 Basiura_0.json"
        try:
            with open(raw, "wb") as handle:
                handle.write(b"exported bytes")
        except (OSError, UnicodeError) as error:
            self.skipTest(f"fixture filesystem rejects the name: {error}")
        self.archive()
        result = coverage.verify(self.source, "snapshot", [])
        self.assertEqual(
            result["canonical_entries"],
            sum(1 for _ in self.source.rglob("*")) + 1,
        )
        # The decode is exact, not a normalisation that would let a different
        # name pass: the surrogate-escaped form round-trips to the same bytes.
        decoded = coverage.archive_path({"path": "\x7f" + raw.rsplit(b"/", 1)[1].hex()})
        self.assertEqual(os.fsencode(decoded), raw.rsplit(b"/", 1)[1])

    def test_unclassified_exclusion_is_not_coverage(self):
        hidden = self.source / "project" / "build"
        hidden.mkdir(parents=True)
        (hidden / "irreplaceable").write_text("unknown producer material")
        self.archive("glob", "--exclude", "**/build")
        with self.assertRaisesRegex(ValueError, "largest roots: project/build=2"):
            coverage.verify(self.source, "glob", [])
        (hidden / ".nobackup").touch()
        self.archive("marker", "--exclude-if-present", ".nobackup")
        with self.assertRaisesRegex(ValueError, "canonical content missing"):
            coverage.verify(self.source, "marker", [])

    def test_chrome_extension_cache_requires_a_valid_extension_id(self):
        base = "home/sinity/.config/chrome-ws/Default/Storage/ext"
        valid = "a" * 32
        invalid = "a" * 31 + "q"
        for extension in (valid, invalid):
            path = self.source / base / extension / "def/GPUCache"
            path.mkdir(parents=True)
            (path / "data").write_text("derived")
        self.archive(
            "extension-caches",
            "--exclude",
            str(self.source / base / valid / "def/GPUCache").lstrip("/"),
            "--exclude",
            str(self.source / base / invalid / "def/GPUCache").lstrip("/"),
        )
        with self.assertRaisesRegex(ValueError, "canonical content missing"):
            coverage.verify(self.source, "extension-caches", [], True)
        shutil.rmtree(self.source / base / invalid)
        self.archive(
            "valid-extension-cache",
            "--exclude",
            str(self.source / base / valid / "def/GPUCache").lstrip("/"),
        )
        result = coverage.verify(self.source, "valid-extension-cache", [], True)
        self.assertIn(f"{base}/{valid}/def/GPUCache", result["noncanonical_roots"])
        cache_path = self.source / base / valid / "def/GPUCache"
        shutil.rmtree(cache_path)
        target = self.source / "operator-data"
        target.mkdir()
        (target / "entry").write_text("durable")
        cache_path.symlink_to(target, target_is_directory=True)
        self.archive("symlink-cache", "--exclude", str(cache_path).lstrip("/"))
        with self.assertRaisesRegex(ValueError, "canonical content missing"):
            coverage.verify(self.source, "symlink-cache", [], True)

    def test_cache_api_storage_stays_canonical(self):
        cache_api = (
            self.source
            / "home/sinity/.config/chrome-ws/Default/WebStorage/7/CacheStorage"
        )
        cache_api.mkdir(parents=True)
        (cache_api / "entry").write_text("site data")
        self.archive(
            "missing-cache-api",
            "--exclude",
            str(cache_api).lstrip("/"),
        )
        with self.assertRaisesRegex(ValueError, "canonical content missing"):
            coverage.verify(self.source, "missing-cache-api", [], True)

    def test_service_worker_storage_stays_canonical(self):
        storage = (
            self.source
            / "home/sinity/.config/chrome-ws/Default/Service Worker/CacheStorage"
        )
        storage.mkdir(parents=True)
        (storage / "entry").write_text("site data")
        self.archive("missing-service-worker", "--exclude", str(storage).lstrip("/"))
        with self.assertRaisesRegex(ValueError, "canonical content missing"):
            coverage.verify(self.source, "missing-service-worker", [], True)

    def test_optguide_model_file_stays_canonical(self):
        model = (
            self.source
            / "home/sinity/.config/chrome-ws/OptGuideOnDeviceModel/1/cache.bin"
        )
        model.parent.mkdir(parents=True)
        model.write_bytes(b"model cache")
        self.archive("missing-optguide", "--exclude", str(model).lstrip("/"))
        with self.assertRaisesRegex(ValueError, "canonical content missing"):
            coverage.verify(self.source, "missing-optguide", [], True)

    def test_declared_scratch_and_nested_stub(self):
        scratch = self.source / "tmp"
        scratch.mkdir()
        (scratch / "derived").write_text("scratch")
        (self.source / "dedicated-subvolume-stub").mkdir()
        self.archive("scratch", "--exclude", str(scratch).lstrip("/"))
        self.assertEqual(
            coverage.verify(self.source, "scratch", ["tmp"])["canonical_entries"], 4
        )

    def test_exact_realm_pytest_cache_is_disposable(self):
        cache = self.source / ".pytest_cache"
        cache.mkdir()
        (cache / "v").write_text("derived")
        project_cache = self.source / "project/.pytest_cache"
        project_cache.mkdir(parents=True)
        (project_cache / "v").write_text("derived")
        models = self.source / "library/models"
        models.mkdir(parents=True)
        (models / "weights").write_text("re-acquirable")
        other = self.source / "project/sample/.pytest_cache"
        other.mkdir(parents=True)
        (other / "precious").write_text("unknown producer")
        self.archive(
            "caches",
            "--exclude",
            str(cache).lstrip("/"),
            "--exclude",
            str(other).lstrip("/"),
            "--exclude",
            str(project_cache).lstrip("/"),
            "--exclude",
            str(models).lstrip("/"),
        )
        with self.assertRaisesRegex(ValueError, "canonical content missing"):
            coverage.verify(
                self.source,
                "caches",
                [".pytest_cache", "project/.pytest_cache", "library/models"],
            )
        self.archive(
            "named-caches-only",
            "--exclude",
            str(cache).lstrip("/"),
            "--exclude",
            str(project_cache).lstrip("/"),
            "--exclude",
            str(models).lstrip("/"),
        )
        result = coverage.verify(
            self.source,
            "named-caches-only",
            [".pytest_cache", "project/.pytest_cache", "library/models"],
        )
        self.assertIn(".pytest_cache", result["noncanonical_roots"])
        self.assertIn("project/.pytest_cache", result["noncanonical_roots"])
        self.assertIn("library/models", result["noncanonical_roots"])

    def test_missing_old_file_and_failed_borg_read(self):
        older = self.root / "older"
        shutil.copytree(self.source, older)
        (self.source / "old-only").unlink()
        self.archive("newer")
        with self.assertRaises(ValueError):
            coverage.verify(older, "newer", [])
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            coverage.verify(older, "absent", [])

    def test_independent_audit_refuses_changed_bytes_without_success_receipt(self):
        archive = "realm-audit-fixture"
        self.archive(archive)
        policy = {"noncanonical": [], "borg_excludes": []}
        marker = self.root / "latest"
        proof = {
            "archive": archive,
            "archive_id": snapshots.archive_identity(archive, self.snapshot_uuid),
            "snapshot_uuid": self.snapshot_uuid,
            "policy_sha256": coverage.policy_identity(policy),
        }
        marker.write_text(
            f"snapshot={self.source.name}\narchive={archive}\n"
            "generation=17\nsubvolume_id=117\n"
            f"coverage={json.dumps(proof)}\n"
        )
        receipt = self.root / "audit-success.json"
        old_stat = (self.source / "same-name").stat()
        (self.source / "same-name").write_text("new version")
        os.utime(
            self.source / "same-name",
            ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns),
        )
        with (
            patch.object(
                snapshots, "snapshot_details", return_value=(self.snapshot_uuid, 17, 117)
            ),
            self.assertRaisesRegex(ValueError, "content mismatch"),
        ):
            audit.audit_latest(marker, self.root, policy)
        self.assertFalse(receipt.exists())
