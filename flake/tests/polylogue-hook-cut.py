"""Exercise Borg's archive paths and exact native-cut cleanup ownership."""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("cut", sys.argv.pop(1))
cut = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cut)
ORIGIN = "bd4b5bed-7abc-1e48-b9ff-1a3df8651105"
CUT_UUID = "79daa3e5-d30a-44c8-8e50-f73316d27a95"
NATIVE = os.environ.get("NATIVE_BTRFS") == "1"


class CutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.environment = patch.dict(
            os.environ,
            {
                "BORG_BASE_DIR": str(self.root / "borg-home"),
                "BORG_CACHE_DIR": str(self.root / "borg-cache"),
                "BORG_SECURITY_DIR": str(self.root / "borg-security"),
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.state = self.root / "realm/state/polylogue"
        self.state.parent.mkdir(parents=True)
        self.cuts = self.root / "cuts"
        self.cuts.mkdir()
        if NATIVE:
            cut.btrfs("subvolume", "create", str(self.state))
        else:
            self.state.mkdir()
            self.native = patch.object(cut, "btrfs", side_effect=self.btrfs)
            self.identities = patch.object(cut, "identity", side_effect=self.identity)
            self.native.start()
            self.identities.start()
        self.commands = []
        self.hooks = self.state / "hooks"
        self.hooks.mkdir()
        (self.hooks / "event").write_bytes(b"synthetic original\n")
        (self.hooks / "link").symlink_to("event")
        self.repo = self.root / "repo"
        subprocess.run(
            ["borg", "init", "--encryption=none", str(self.repo)], check=True
        )

    def tearDown(self):
        if not NATIVE:
            self.native.stop()
            self.identities.stop()
        else:
            # The fixture owns only this temporary root. Delete recorded native
            # subvolumes deepest first, never host data or historical cuts.
            for path in sorted(
                self.root.rglob("*"), key=lambda p: len(p.parts), reverse=True
            ):
                if path.is_dir() and not path.is_symlink():
                    probe = subprocess.run(
                        ["btrfs", "subvolume", "show", str(path)], capture_output=True
                    )
                    if probe.returncode == 0:
                        cut.btrfs("subvolume", "delete", str(path))
        self.tmp.cleanup()

    def identity(self, path):
        return {
            "UUID": ORIGIN if path == self.state else CUT_UUID,
            "Parent UUID": ORIGIN,
            "Flags": "readonly",
        }

    def btrfs(self, *args):
        self.commands.append(args)
        if args[:2] == ("subvolume", "snapshot"):
            shutil.copytree(args[-2], args[-1], symlinks=True)
        if args[:2] == ("subvolume", "delete"):
            shutil.rmtree(args[-1])
        return ""

    def create(self, command=None):
        return cut.archive(
            self.state,
            self.cuts,
            command
            or [
                "borg",
                "create",
                "--exclude",
                f"{self.state}/hooks/**",
                f"{self.repo}::fixture",
                str(self.state),
            ],
        )

    def test_borg_paths_bytes_and_source_mutation(self):
        real_run = subprocess.run

        def mutate_then_run(argv, **kwargs):
            if argv[0] == "borg":
                (self.hooks / "event").write_bytes(b"synthetic changed after cut\n")
            return real_run(argv, **kwargs)

        with patch.object(cut.subprocess, "run", side_effect=mutate_then_run):
            self.assertEqual(self.create(), 0)
        prefix = str(self.state).lstrip("/") + "/hooks"
        listing = subprocess.check_output(
            ["borg", "list", "--short", f"{self.repo}::fixture"], text=True
        ).splitlines()
        self.assertEqual(
            set(listing),
            {str(self.state).lstrip("/"), prefix, prefix + "/event", prefix + "/link"},
        )
        restored = subprocess.check_output(
            ["borg", "extract", "--stdout", f"{self.repo}::fixture", prefix + "/event"]
        )
        self.assertEqual(restored, b"synthetic original\n")
        self.assertEqual(list(self.cuts.iterdir()), [])

    def test_absent_hooks_archives_empty_directory(self):
        shutil.rmtree(self.hooks)
        self.assertEqual(self.create(), 0)
        listing = subprocess.check_output(
            ["borg", "list", "--short", f"{self.repo}::fixture"], text=True
        ).splitlines()
        self.assertEqual(
            set(listing), {str(self.state).lstrip("/"), str(self.hooks).lstrip("/")}
        )

    def test_command_failure_retains_cut_removes_view(self):
        self.assertEqual(self.create([sys.executable, "-c", "raise SystemExit(7)"]), 7)
        self.assertEqual(len(list(self.cuts.glob("cut-*"))), 1)
        self.assertEqual(list(self.cuts.glob("view-*")), [])

    def test_interruption_retains_cut(self):
        real_run = subprocess.run

        def interrupt_borg(argv, **kwargs):
            if argv[0] == "borg":
                raise KeyboardInterrupt
            return real_run(argv, **kwargs)

        with patch.object(cut.subprocess, "run", side_effect=interrupt_borg):
            with self.assertRaises(KeyboardInterrupt):
                self.create()
        self.assertEqual(len(list(self.cuts.glob("cut-*"))), 1)
        self.assertEqual(list(self.cuts.glob("view-*")), [])

    def test_bad_paths_refused_before_snapshot(self):
        alias = self.root / "alias"
        alias.symlink_to(self.state, target_is_directory=True)
        for state, cuts in (
            (alias, self.cuts),
            (self.root / "absent", self.cuts),
            (self.state, self.state),
        ):
            with self.assertRaises(OSError):
                cut.archive(state, cuts, ["true"])
        self.assertEqual(list(self.cuts.iterdir()), [])

    def test_hook_root_symlink_refused(self):
        shutil.rmtree(self.hooks)
        self.hooks.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            self.create()
        self.assertEqual(len(list(self.cuts.glob("cut-*"))), 1)

    def test_unavailable_hook_root_is_error(self):
        real_scandir = os.scandir

        def denied(path):
            if isinstance(path, Path) and path.parent.parent == self.cuts:
                raise PermissionError("synthetic denied")
            return real_scandir(path)

        with patch.object(cut.os, "scandir", side_effect=denied):
            with self.assertRaises(PermissionError):
                self.create()
        self.assertEqual(len(list(self.cuts.glob("cut-*"))), 1)

    def test_nested_subvolume_refused(self):
        if NATIVE:
            cut.btrfs("subvolume", "create", str(self.hooks / "nested"))
            with self.assertRaises(OSError):
                self.create()
        else:
            with patch.object(cut, "btrfs", return_value="nested"):
                with self.assertRaises(OSError):
                    self.create()
        self.assertEqual(list(self.cuts.iterdir()), [])

    def test_changed_cut_refuses_deletion(self):
        real_verify = cut.verify_cut
        probe = self.cuts / "identity-probe"
        probe.mkdir()
        for change in ({"UUID": ORIGIN}, {"Parent UUID": CUT_UUID}, {"Flags": "-"}):
            with patch.object(
                cut,
                "identity",
                return_value={
                    "UUID": CUT_UUID,
                    "Parent UUID": ORIGIN,
                    "Flags": "readonly",
                    **change,
                },
            ):
                with self.assertRaises(OSError):
                    real_verify(probe, ORIGIN, CUT_UUID)
        probe.rmdir()
        checks = 0

        def verify(*args):
            nonlocal checks
            checks += 1
            if checks == 2:
                raise OSError("synthetic replacement or writable cut")
            return real_verify(*args)

        with patch.object(cut, "verify_cut", side_effect=verify):
            with self.assertRaises(OSError):
                self.create()
        self.assertEqual(len(list(self.cuts.glob("cut-*"))), 1)


unittest.main()
