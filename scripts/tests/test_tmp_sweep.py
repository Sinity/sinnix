"""Holder visibility and the privilege boundary before scratch removal."""
import contextlib
import errno
import io
import os
from pathlib import Path
import pwd
import runpy
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

MODULE = runpy.run_path(os.environ.get("TMP_SWEEP_SOURCE", str(Path(__file__).parents[1] / "sinnix-tmp-sweep")))

class SweepTest(unittest.TestCase):
    def test_denied_environment_is_unknown_not_absent(self):
        def listing(path):
            return ["123"] if path == "/proc" else []
        missing = FileNotFoundError(errno.ENOENT, "gone")
        with patch("os.listdir", side_effect=listing), patch("os.readlink", side_effect=missing), patch("builtins.open", side_effect=PermissionError(errno.EACCES, "denied")):
            with self.assertRaisesRegex(RuntimeError, "cannot inspect /proc/123/environ"):
                MODULE["held_directories"]({"/fixture/nix-shell.held"}, ["/fixture"])

    def test_vanished_process_is_normal_churn(self):
        def listing(path):
            return ["123"] if path == "/proc" else []
        missing = FileNotFoundError(errno.ENOENT, "gone")
        with patch("os.listdir", side_effect=listing), patch("os.readlink", side_effect=missing), patch("builtins.open", side_effect=missing):
            self.assertEqual(MODULE["held_directories"]({"/fixture/nix-shell.held"}, ["/fixture"]), set())

    def run_main(self, *, root=False, scan_error=False, drop_error=False, changed=False, deletion_error=False):
        state = {"uid": 0 if root else 1000}
        events = []
        owner = pwd.struct_passwd(("fixture", "x", 1000, 100, "", "/fixture", "/bin/sh"))
        path = "/fixture/nix-shell.leaked"
        info = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_dev=1, st_ino=3 if changed else 2, st_uid=1000)
        def scan(*_):
            events.append(("scan", state["uid"]))
            if scan_error:
                raise MODULE["VisibilityError"]("cannot inspect fixture")
            return set()
        def drop(uid, *_):
            events.append(("drop", uid))
            state["uid"] = uid
        def remove(path, *, onerror):
            events.append(("remove", state["uid"]))
            self.assertEqual(state["uid"], 1000)
            if deletion_error:
                error = PermissionError(errno.EACCES, "denied")
                onerror(None, path, (PermissionError, error, None))
        globals_ = MODULE["main"].__globals__
        with patch.dict(globals_, {"roots": lambda: ["/fixture"], "collect_candidates": lambda *_: ({path: (1, 2, 1000)}, 0), "held_directories": scan}), patch("os.getuid", side_effect=lambda: state["uid"]), patch("os.geteuid", side_effect=lambda: state["uid"]), patch("os.getresuid", side_effect=lambda: (state["uid"],) * 3), patch("pwd.getpwnam", return_value=owner), patch("os.initgroups", side_effect=PermissionError(errno.EPERM, "denied") if drop_error else None), patch("os.setresgid"), patch("os.setresuid", side_effect=drop), patch("os.stat", return_value=info), patch("shutil.rmtree", side_effect=remove), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = MODULE["main"](["sweep"] + (["--owner", "fixture"] if root else []))
        return result, events

    def test_privileged_scan_drops_all_uids_before_removal(self):
        result, events = self.run_main(root=True)
        self.assertEqual(result, 0)
        self.assertEqual(events, [("scan", 0), ("drop", 1000), ("remove", 1000)])

    def test_denied_scan_refuses_all_removal(self):
        result, events = self.run_main(root=True, scan_error=True)
        self.assertEqual(result, 1)
        self.assertEqual(events, [("scan", 0)])

    def test_failed_privilege_drop_refuses_removal(self):
        result, events = self.run_main(root=True, drop_error=True)
        self.assertEqual(result, 1)
        self.assertEqual(events, [("scan", 0)])

    def test_replaced_directory_is_retained(self):
        result, events = self.run_main(changed=True)
        self.assertEqual(result, 0)
        self.assertEqual(events, [("scan", 1000)])

    def test_removal_error_is_not_a_success(self):
        result, events = self.run_main(deletion_error=True)
        self.assertEqual(result, 1)
        self.assertEqual(events, [("scan", 1000), ("remove", 1000)])

    def test_root_without_nonroot_owner_is_refused(self):
        with patch("os.getuid", return_value=0), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(MODULE["main"](["sweep"]), 64)

if __name__ == "__main__":
    unittest.main()
