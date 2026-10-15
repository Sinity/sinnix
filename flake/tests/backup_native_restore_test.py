"""Synthetic boundaries of the native restore acceptance operation."""

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("restore_probe", sys.argv[1])
RESTORE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RESTORE)


class RestoreProof(unittest.TestCase):
    def setUp(self):
        self.content = b"complete historical source\n"
        self.payload = {
            "relative_path": "project/example/receipt.txt",
            "old_archive": "realm-realm.20260101T120000+0000",
            "old_archive_id": "a" * 64,
            "old_snapshot_uuid": "12345678-1234-1234-1234-123456789abc",
            "old_sha256": hashlib.sha256(self.content).hexdigest(),
            "old_bytes": len(self.content),
        }
        self.header = {
            "name": self.payload["old_archive"], "id": self.payload["old_archive_id"],
            "comment": "sinnix-snapshot-v1:" + self.payload["old_snapshot_uuid"],
        }
        self.calls = []

    def read(self, argv, seconds, limit):
        self.calls.append((argv, seconds, limit))
        if argv[1] == "list":
            return json.dumps({"archives": [self.header]}).encode()
        return self.content

    def test_complete_restore_keeps_archive_and_content_identities(self):
        proof = RESTORE.verify_target(self.payload, "old", self.read)
        self.assertEqual(proof["outcome"], "ok")
        self.assertEqual(proof["sha256"], self.payload["old_sha256"])
        self.assertEqual([call[0][1] for call in self.calls], ["list", "extract", "list"])
        self.assertEqual(self.calls[1][1:], (300, len(self.content) + 1))
        self.assertIn("--", self.calls[1][0])

    def test_changed_archive_refuses_before_reading_payload(self):
        self.header["id"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "archive identity changed"):
            RESTORE.verify_target(self.payload, "old", self.read)
        self.assertEqual(len(self.calls), 1)

    def test_wrong_source_uuid_refuses_before_reading_payload(self):
        self.header["comment"] = "sinnix-snapshot-v1:other"
        with self.assertRaisesRegex(ValueError, "archive identity changed"):
            RESTORE.verify_target(self.payload, "old", self.read)
        self.assertEqual(len(self.calls), 1)

    def test_partial_file_is_not_a_successful_restore(self):
        self.content = self.content[:-1]
        with self.assertRaisesRegex(ValueError, "complete source digest"):
            RESTORE.verify_target(self.payload, "old", self.read)

    def test_source_selection_is_validated_before_any_read(self):
        for path in ("/absolute", "../outside", "project/../outside", "project//ambiguous"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                RESTORE.verify_target(self.payload | {"relative_path": path}, "old", self.read)
        for field, value in (("old_sha256", "prefix"), ("old_bytes", 1024 * 1024 + 1), ("old_bytes", True)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                RESTORE.verify_target(self.payload | {field: value}, "old", self.read)
        self.assertEqual(self.calls, [])

    def test_oversized_receipt_is_rejected_before_loading_its_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversized.json"
            path.write_bytes(b"x" * (64 * 1024 + 1))
            with self.assertRaisesRegex(ValueError, "64 KiB"):
                RESTORE.load_target(path)

    def test_pipe_receipt_refuses_without_waiting_for_a_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pipe"
            os.mkfifo(path)
            with self.assertRaisesRegex(ValueError, "regular private receipt"):
                RESTORE.load_target(path)

    def test_owner_reference_and_job_scratch_reach_the_privileged_reader(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "owner"
            script.write_text(
                "#!/bin/bash\nexport BORG_REPO='file:///synthetic/repo'\n"
                "export BORG_PASSCOMMAND='/synthetic/cat /run/secret/synthetic'\n"
                "export BORG_CACHE_DIR='/synthetic/cache'\n"
            )
            responses = [f"{{ path={script} ; }}", "PATH=/synthetic/bin", ""]
            with patch.object(RESTORE.subprocess, "check_output", side_effect=responses), \
                 patch.object(RESTORE.pwd, "getpwnam", return_value=SimpleNamespace(pw_dir="/synthetic/root")), \
                 patch.dict(RESTORE.os.environ, {"TMPDIR": "/synthetic/task-scratch"}):
                shell, values = RESTORE.installed_owner()
            self.assertEqual(shell, "/bin/bash")
            self.assertEqual(values["BORG_PASSCOMMAND"], "/synthetic/cat /run/secret/synthetic")
            self.assertEqual(values["TMPDIR"], "/synthetic/task-scratch")
            self.assertEqual(values["HOME"], "/synthetic/root")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
