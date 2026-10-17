"""Exercise the packaged shell helper with synthetic FUSE tools, never real mounts."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

STUBS = r"""gocryptfs() {
  printf '%s\n' "$*" >> "$FIXTURE/init-log"
  if [ "$1" = -init ]; then
    local scratch=("$TMPDIR"/crypt-folder.*)
    test -d "${scratch[0]}" || return 97
    if [ "${INIT_STATUS:-0}" != 0 ]; then return "$INIT_STATUS"; fi
    touch "$2/gocryptfs.conf"
  else
    printf '%s' "$2" > "$FIXTURE/mount-path"
    stat -c %a "$2" > "$FIXTURE/mount-mode"
    touch "$FIXTURE/mounted"
  fi
}
rsync() { return "${COPY_STATUS:-0}"; }
mountpoint() { test -e "$FIXTURE/mounted"; }
fusermount() {
  if [ "${UNMOUNT_FAIL:-0}" = 1 ]; then return 9; fi
  command rm "$FIXTURE/mounted"
}
mkdir() {
  case "$*" in *'/tmp/encrypt-mount-'*) return 98;; esac
  command mkdir "$@"
}
find() {
  if [ "${FIND_FAIL:-0}" = 1 ]; then return 7; fi
  command find "$@"
}
export -f gocryptfs rsync mountpoint fusermount mkdir find
exec "$CRYPT_FOLDER" "$@"
"""


class CryptFolder(unittest.TestCase):
    def run_case(self, kind="normal", **overrides):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / ("source\n" if kind == "newline" else "source")
            source.mkdir()
            (source / "original").write_text("keep source bytes")
            scratch = root / "scratch"
            scratch.mkdir()
            encrypted = source / "encrypted" if kind == "nested" else root / "encrypted"
            if kind == "symlink":
                encrypted = root / "alias"
                encrypted.symlink_to(source / "encrypted")
            env = dict(os.environ, FIXTURE=str(root), TMPDIR=str(scratch), **overrides)
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    STUBS,
                    "fixture",
                    "encrypt",
                    str(source),
                    str(encrypted),
                ],
                env=env,
                capture_output=True,
                text=True,
            )
            report = {
                "exit": result.returncode,
                "initialized": (root / "init-log").exists(),
                "scratch_children": len(list(scratch.iterdir())),
                "stderr": result.stderr,
            }
            if (root / "mount-path").exists():
                report["mount_inside_private_scratch"] = (
                    Path((root / "mount-path").read_text()).parent == scratch
                )
                report["mount_mode"] = (root / "mount-mode").read_text().strip()
            self.assertEqual((source / "original").read_text(), "keep source bytes")
            return report

    def test_private_mount_and_cleanup(self):
        result = self.run_case()
        self.assertEqual(result["exit"], 0, result)
        self.assertTrue(result["mount_inside_private_scratch"])
        self.assertEqual(result["mount_mode"], "700")
        self.assertEqual(result["scratch_children"], 0)

    def test_nested_destination_refused_before_initialization(self):
        result = self.run_case("nested")
        self.assertNotEqual(result["exit"], 0)
        self.assertFalse(result["initialized"])

    def test_trailing_newline_source_name(self):
        result = self.run_case("newline")
        self.assertEqual(result["exit"], 0, result)

    def test_symlinked_nested_destination_refused(self):
        result = self.run_case("symlink")
        self.assertNotEqual(result["exit"], 0)
        self.assertFalse(result["initialized"])

    def test_inventory_failure_refused_before_initialization(self):
        result = self.run_case(FIND_FAIL="1")
        self.assertNotEqual(result["exit"], 0)
        self.assertFalse(result["initialized"])

    def test_initialization_failure_cleans_private_scratch(self):
        result = self.run_case(INIT_STATUS="7")
        self.assertEqual(result["exit"], 7, result)
        self.assertEqual(result["scratch_children"], 0)

    def test_copy_failure_preserved_and_cleaned(self):
        result = self.run_case(COPY_STATUS="6")
        self.assertEqual(result["exit"], 6, result)
        self.assertEqual(result["scratch_children"], 0)

    def test_unmount_failure_visible_and_mount_retained(self):
        result = self.run_case(UNMOUNT_FAIL="1")
        self.assertNotEqual(result["exit"], 0)
        self.assertEqual(result["scratch_children"], 1)


unittest.main()
