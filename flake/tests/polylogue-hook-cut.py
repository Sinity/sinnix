"""Synthetic source-cut ownership and cache-continuity regressions."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cut = load("cut", sys.argv.pop(1))
sealer = load("sealer", sys.argv.pop(1))
ORIGIN = "bd4b5bed-7abc-1e48-b9ff-1a3df8651105"
CUT_UUID = "79daa3e5-d30a-44c8-8e50-f73316d27a95"


class CutTests(unittest.TestCase):
    def test_device_drift_requires_verified_origin_and_unchanged_metadata(self):
        old = {"dev": 1, "ino": 2, "ctime_ns": 3, "source_subvolume_uuid": ORIGIN}
        new = {**old, "dev": 4}
        self.assertTrue(sealer._same_source_record(old, new))
        for changed in (
            {"ctime_ns": 9},
            {"ino": 9},
            {"source_subvolume_uuid": CUT_UUID},
        ):
            self.assertFalse(sealer._same_source_record(old, {**new, **changed}))
        self.assertFalse(sealer._same_source_record({"dev": 1}, {"dev": 4}))
        self.assertFalse(sealer._same_source_record(None, new))

    def test_verified_device_drift_reuses_actual_staged_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, stage = root / "source", root / "stage"
            source.mkdir()
            stage.mkdir()
            (source / "journal").write_text("neutral")
            records = sealer._sync_once(source, stage, {}, ORIGIN)
            inode = (stage / "journal").stat().st_ino
            records["journal"]["dev"] += 1
            with patch.object(
                sealer,
                "_clone_file",
                side_effect=AssertionError("unchanged cut recopied"),
            ):
                sealer._sync_once(source, stage, records, ORIGIN)
            self.assertEqual((stage / "journal").stat().st_ino, inode)

    def test_cleanup_refuses_replacement_or_writable_cut(self):
        correct = {"UUID": CUT_UUID, "Parent UUID": ORIGIN, "Flags": "readonly"}
        for changed in ({"UUID": ORIGIN}, {"Parent UUID": CUT_UUID}, {"Flags": "-"}):
            with patch.object(cut, "identity", return_value={**correct, **changed}):
                with self.assertRaises(OSError):
                    cut.verify_cut(Path("cut"), ORIGIN, CUT_UUID)

    def run_seal(self, outcome, replacement=False, nested=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            state, cuts, stage = (root / name for name in ("state", "cuts", "stage"))
            for path in (state, cuts, stage):
                path.mkdir()
            commands = []
            cut_checks = 0

            def identity(path):
                nonlocal cut_checks
                if path == state:
                    return {"UUID": ORIGIN}
                cut_checks += 1
                return {
                    "UUID": ORIGIN if replacement and cut_checks == 3 else CUT_UUID,
                    "Parent UUID": ORIGIN,
                    "Flags": "readonly",
                }

            def btrfs(*args):
                commands.append(args)
                if args[:3] == ("subvolume", "list", "-o"):
                    return "nested" if nested else ""
                return ""

            loader = SimpleNamespace(
                exec_module=lambda module: setattr(module, "main", lambda **kw: outcome)
            )
            with (
                patch.object(cut, "identity", side_effect=identity),
                patch.object(cut, "btrfs", side_effect=btrfs),
                patch.object(
                    cut.importlib.util,
                    "spec_from_file_location",
                    return_value=SimpleNamespace(loader=loader),
                ),
                patch.object(
                    cut.importlib.util,
                    "module_from_spec",
                    return_value=SimpleNamespace(),
                ),
            ):
                if nested or replacement:
                    with self.assertRaises(OSError):
                        cut.seal(state, stage / "hooks", cuts, Path("sealer"))
                else:
                    self.assertEqual(
                        cut.seal(state, stage / "hooks", cuts, Path("sealer")), outcome
                    )
            return commands

    def test_failed_seal_retains_cut(self):
        commands = self.run_seal(1)
        self.assertTrue(
            any(args[:3] == ("subvolume", "snapshot", "-r") for args in commands)
        )
        self.assertFalse(any(args[:2] == ("subvolume", "delete") for args in commands))

    def test_success_deletes_only_verified_cut(self):
        commands = self.run_seal(0)
        snapshots = [args for args in commands if args[:2] == ("subvolume", "snapshot")]
        deletes = [args for args in commands if args[:2] == ("subvolume", "delete")]
        self.assertEqual(len(deletes), 1)
        self.assertEqual(deletes[0][-1], snapshots[0][-1])

    def test_replacement_after_seal_is_retained(self):
        self.assertFalse(
            any(
                args[:2] == ("subvolume", "delete")
                for args in self.run_seal(0, replacement=True)
            )
        )

    def test_nested_subvolume_refused_before_cut(self):
        self.assertFalse(
            any(
                args[:2] == ("subvolume", "snapshot")
                for args in self.run_seal(0, nested=True)
            )
        )


unittest.main()
