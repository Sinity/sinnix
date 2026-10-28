"""Holder visibility and the privilege boundary before scratch removal."""

import contextlib
import errno
import io
import json
import mmap
import os
import pwd
import runpy
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

MODULE = runpy.run_path(
    os.environ.get(
        "TMP_SWEEP_SOURCE", str(Path(__file__).parents[1] / "sinnix-tmp-sweep")
    )
)


class SweepTest(unittest.TestCase):
    def test_denied_environment_is_unknown_not_absent(self):
        def listing(path):
            return ["123"] if path == "/proc" else []

        missing = FileNotFoundError(errno.ENOENT, "gone")
        with (
            patch("os.listdir", side_effect=listing),
            patch("os.readlink", side_effect=missing),
            patch("builtins.open", side_effect=PermissionError(errno.EACCES, "denied")),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "cannot inspect /proc/123/environ"
            ):
                MODULE["held_directories"]({"/fixture/nix-shell.held"}, ["/fixture"])

    def test_vanished_process_is_normal_churn(self):
        def listing(path):
            return ["123"] if path == "/proc" else []

        missing = FileNotFoundError(errno.ENOENT, "gone")
        with (
            patch("os.listdir", side_effect=listing),
            patch("os.readlink", side_effect=missing),
            patch("builtins.open", side_effect=missing),
        ):
            self.assertEqual(
                MODULE["held_directories"]({"/fixture/nix-shell.held"}, ["/fixture"]),
                set(),
            )

    def test_only_old_dead_pid_scratch_is_selected(self):
        with tempfile.TemporaryDirectory() as root:
            names = [
                "sinnix-chatgpt-native.999999999.ABC123",
                "sinnix-chatgpt-download.999999999.ABC123",
                "sinnix-router-poll.999999999.ABC123",
                f"sinnix-chatgpt-native.{os.getpid()}.ABC123",
                "sinnix-chatgpt-native.999999999.NEW123",
                "sinnix-chatgpt-native.legacy.json",
                "sinnix-notes.999999999.ABC123",
                "codex",
                "claude-old",
                "polylogue-old",
                "wave-old",
            ]
            old = time.time() - 2 * 86400
            for name in names:
                path = Path(root, name)
                path.mkdir()
                os.utime(path, (old, old))
            os.utime(Path(root, names[4]), None)
            Path(root, "sinnix-router-poll.999999999.LINK12").symlink_to(
                Path(root, names[0]), target_is_directory=True
            )
            candidates, _ = MODULE["collect_candidates"](root, os.getuid())
            self.assertEqual(set(candidates), {str(Path(root, n)) for n in names[:3]})

    def test_allocator_visibility_failure_refuses_selection(self):
        with patch("os.stat", side_effect=PermissionError(errno.EACCES, "denied")):
            with self.assertRaises(PermissionError):
                MODULE["owned_scratch_ready"](
                    "sinnix-router-poll.999999999.ABC123", time.time() - 2 * 86400
                )

    @unittest.skipIf(os.getuid() == 0, "removal requires a non-root fixture owner")
    def test_sweep_removes_only_abandoned_owned_scratch(self):
        with tempfile.TemporaryDirectory() as root:
            dead = Path(root, "sinnix-router-poll.999999999.ABC123")
            held = Path(root, "sinnix-chatgpt-native.999999999.ABC123")
            live = Path(root, f"sinnix-chatgpt-download.{os.getpid()}.ABC123")
            protected = Path(root, "claude-recovery")
            for path in (dead, held, live, protected):
                path.mkdir()
                (path / "payload").write_text("fixture")
                os.utime(path, (1, 1))
            with (
                patch.dict(
                    MODULE["main"].__globals__,
                    {
                        "roots": lambda: [root],
                        "held_directories": lambda *_: {str(held)},
                    },
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(MODULE["main"](["sweep"]), 0)
            self.assertFalse(dead.exists())
            for path in (held, live, protected):
                self.assertEqual((path / "payload").read_text(), "fixture")

    @unittest.skipIf(os.getuid() == 0, "removal requires a non-root fixture owner")
    def test_allocator_is_rechecked_after_holder_scan(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "sinnix-router-poll.999999999.ABC123")
            path.mkdir()
            os.utime(path, (1, 1))
            with (
                patch.dict(
                    MODULE["main"].__globals__,
                    {
                        "roots": lambda: [root],
                        "held_directories": lambda *_: set(),
                    },
                ),
                patch.dict(
                    MODULE["main"].__globals__,
                    {
                        "owned_scratch_ready": unittest.mock.Mock(
                            side_effect=[True, False]
                        ),
                    },
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(MODULE["main"](["sweep"]), 0)
            self.assertTrue(path.exists())

    def run_main(
        self,
        *,
        root=False,
        scan_error=False,
        drop_error=False,
        changed=False,
        deletion_error=False,
    ):
        state = {"uid": 0 if root else 1000}
        events = []
        owner = pwd.struct_passwd(
            ("fixture", "x", 1000, 100, "", "/fixture", "/bin/sh")
        )
        path = "/fixture/nix-shell.leaked"
        info = SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o700,
            st_dev=1,
            st_ino=3 if changed else 2,
            st_uid=1000,
            st_mtime=0,
        )

        def scan(*_):
            events.append(("scan", state["uid"]))
            if scan_error:
                raise MODULE["VisibilityError"]("cannot inspect fixture")
            return set()

        def drop(uid, *_):
            events.append(("drop", uid))
            state["uid"] = uid

        def remove(path, *_):
            events.append(("remove", state["uid"]))
            self.assertEqual(state["uid"], 1000)
            if deletion_error:
                error = PermissionError(errno.EACCES, "denied")
                raise error
            return True

        globals_ = MODULE["main"].__globals__
        with (
            patch.dict(
                globals_,
                {
                    "roots": lambda: ["/fixture"],
                    "collect_candidates": lambda *_: ({path: (1, 2, 1000)}, 0),
                    "held_directories": scan,
                    "inspect_tree": lambda *_: (7, 1, False),
                    "paced_remove": remove,
                },
            ),
            patch("os.getuid", side_effect=lambda: state["uid"]),
            patch("os.geteuid", side_effect=lambda: state["uid"]),
            patch("os.getresuid", side_effect=lambda: (state["uid"],) * 3),
            patch("pwd.getpwnam", return_value=owner),
            patch(
                "os.initgroups",
                side_effect=PermissionError(errno.EPERM, "denied")
                if drop_error
                else None,
            ),
            patch("os.setresgid"),
            patch("os.setresuid", side_effect=drop),
            patch("os.stat", return_value=info),
            patch("os.lstat", return_value=info),
            patch("subprocess.run"),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            result = MODULE["main"](
                ["sweep"] + (["--owner", "fixture"] if root else [])
            )
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
        with (
            patch("os.getuid", return_value=0),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(MODULE["main"](["sweep"]), 64)


class ManagedSweepTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.remote_scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.remote_scratch.cleanup)
        self.remote_root = Path(self.remote_scratch.name)
        self.uid = os.getuid()

    def old(self, path):
        for child in path.rglob("*"):
            os.utime(child, (1, 1), follow_symlinks=False)
        os.utime(path, (1, 1))

    def inspect(self, path):
        return MODULE["inspect_tree"](str(path), self.uid, True)

    def git(self, path, *args):
        return subprocess.check_output(
            [
                "git",
                "-C",
                str(path),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                *args,
            ],
            stderr=subprocess.PIPE,
            text=True,
        )

    def repo(self, name):
        path = self.root / name
        path.mkdir()
        self.git(path, "init", "-q")
        (path / "file").write_text("fixture")
        self.git(path, "add", "file")
        self.git(path, "commit", "-qm", "fixture")
        remote = self.remote_root / name
        remote.mkdir()
        self.git(remote, "init", "--bare", "-q")
        self.git(path, "remote", "add", "origin", str(remote))
        self.git(path, "push", "-q", "origin", "HEAD:refs/heads/main")
        self.old(path)
        return path

    def test_old_new_and_nested_recent_files(self):
        path = self.root / "lane"
        (path / "deep").mkdir(parents=True)
        (path / "deep/file").write_text("fixture")
        with self.assertRaisesRegex(RuntimeError, "seven days"):
            self.inspect(path)
        self.old(path)
        self.assertEqual(self.inspect(path), (7, 3, False))
        (path / "deep/file").touch()
        with self.assertRaises(RuntimeError):
            self.inspect(path)

    def test_clean_dirty_unpushed_and_detached_git(self):
        path = self.repo("repo")
        self.assertTrue(self.inspect(path)[2])
        (path / "file").write_text("dirty")
        self.old(path)
        with self.assertRaisesRegex(RuntimeError, "working changes"):
            self.inspect(path)
        self.git(path, "add", "file")
        self.git(path, "commit", "-qm", "unpushed")
        self.old(path)
        with self.assertRaisesRegex(RuntimeError, "absent"):
            self.inspect(path)
        self.git(path, "checkout", "--detach", "-q")
        with self.assertRaises(RuntimeError):
            self.inspect(path)

    def test_every_nested_checkout_and_unknown_git_are_retained(self):
        parent = self.root / "parent"
        parent.mkdir()
        repo = self.repo("nested")
        repo.rename(parent / "repo")
        self.old(parent)
        self.assertTrue(self.inspect(parent)[2])
        (parent / "repo/file").write_text("dirty")
        self.old(parent)
        with self.assertRaises(RuntimeError):
            self.inspect(parent)
        (parent / "repo/.git").rename(parent / "repo/broken")
        (parent / "repo/.git").write_text("gitdir: /missing-fixture")
        self.old(parent)
        with self.assertRaises(subprocess.CalledProcessError):
            self.inspect(parent)

    def test_bare_repository_is_retained_for_owner_reconciliation(self):
        path = self.root / "bare"
        path.mkdir()
        self.git(path, "init", "--bare", "-q")
        self.old(path)
        with self.assertRaisesRegex(RuntimeError, "bare Git"):
            self.inspect(path)

    def test_unpushed_other_branch_is_retained(self):
        path = self.repo("repo")
        self.git(path, "checkout", "-qb", "unpublished")
        self.git(path, "commit", "--allow-empty", "-qm", "unpushed")
        self.git(path, "checkout", "-q", "-")
        self.old(path)
        with self.assertRaisesRegex(RuntimeError, "absent"):
            self.inspect(path)

    def test_reflog_only_commit_is_retained(self):
        path = self.repo("repo")
        self.git(path, "commit", "--allow-empty", "-qm", "reflog-only")
        self.git(path, "reset", "--hard", "refs/remotes/origin/main")
        self.old(path)
        with self.assertRaisesRegex(RuntimeError, "absent"):
            self.inspect(path)

    def test_force_pushed_remote_cannot_be_proven_by_stale_cached_refs(self):
        path = self.repo("repo")
        remote = self.remote_root / "repo"
        tree = self.git(remote, "rev-parse", "refs/heads/main^{tree}").strip()
        replacement = self.git(remote, "commit-tree", tree, "-m", "replacement").strip()
        self.git(remote, "update-ref", "refs/heads/main", replacement)
        self.old(path)
        with self.assertRaisesRegex(RuntimeError, "current remote heads"):
            self.inspect(path)

    def test_unreachable_remote_retains_checkout(self):
        path = self.repo("repo")
        self.git(path, "remote", "set-url", "origin", str(self.remote_root / "missing"))
        self.old(path)
        with self.assertRaises(subprocess.CalledProcessError):
            self.inspect(path)

    def test_unreferenced_commit_keeps_its_only_object_database(self):
        path = self.repo("repo")
        tree = self.git(path, "rev-parse", "HEAD^{tree}").strip()
        self.git(path, "commit-tree", tree, "-m", "unreferenced work")
        self.old(path)
        with self.assertRaisesRegex(RuntimeError, "unreachable Git objects"):
            self.inspect(path)

    def test_index_lock_is_unknown_work_even_when_status_is_clean(self):
        path = self.repo("repo")
        (path / ".git/index.lock").write_bytes(b"unfinished index")
        self.old(path)
        with self.assertRaisesRegex(RuntimeError, "index lock"):
            self.inspect(path)

    def test_callers_git_context_cannot_hide_another_checkouts_changes(self):
        decoy = self.repo("decoy")
        actual = self.repo("actual")
        (actual / "file").write_text("uncommitted work")
        self.old(actual)
        with patch.dict(
            os.environ, {"GIT_DIR": str(decoy / ".git"), "GIT_WORK_TREE": str(decoy)}
        ):
            with self.assertRaisesRegex(RuntimeError, "working changes"):
                self.inspect(actual)

    def test_mount_alias_inside_tree_is_retained(self):
        path = self.root / "lane"
        (path / "bind").mkdir(parents=True)
        self.old(path)
        with self.assertRaisesRegex(RuntimeError, "mount point"):
            MODULE["inspect_tree"](str(path), self.uid, True, {str(path / "bind")})

    def test_mount_above_codex_lane_is_retained(self):
        container = self.root / "codex"
        lane = container / "lane"
        lane.mkdir(parents=True)
        self.old(container)
        fn = MODULE["inspect_tree"]
        with patch.dict(fn.__globals__, {"MANAGED_ROOT": str(self.root)}):
            with self.assertRaisesRegex(RuntimeError, "mount point"):
                fn(str(lane), self.uid, True, {str(container)})

    def test_mountinfo_decodes_escaped_mount_names(self):
        record = r"1 2 0:5 / /realm/tmp/work/has\040space rw - btrfs source rw"
        with patch("builtins.open", return_value=io.StringIO(record)):
            self.assertEqual(MODULE["mount_points"](), {"/realm/tmp/work/has space"})

    def test_typed_and_shell_queue_paths_preserve_spaces_and_normalize_dotdot(self):
        root = "/realm/tmp/work/codex"
        paths = MODULE["queue_path_values"](
            {
                "argv": [root + "/lane with spaces/prompt"],
                "command": "bash -c "
                + repr("worker '" + root + "/other lane=value/prompt'; true"),
                "envs": {"TMPDIR": root + "/child/../normalized"},
            }
        )
        self.assertTrue(MODULE["queue_holds"](root + "/lane with spaces", paths))
        self.assertTrue(MODULE["queue_holds"](root + "/other lane=value", paths))
        self.assertTrue(MODULE["queue_holds"](root + "/normalized", paths))

    def test_general_aging_cannot_bypass_young_devshell_reservation(self):
        path = self.root / "nix-develop-fresh"
        path.mkdir()
        payload = path / "copied-old-input"
        payload.write_bytes(b"old input")
        os.utime(payload, (1, 1))
        candidates, _ = MODULE["collect_candidates"](str(self.root), self.uid)
        fn = MODULE["managed_candidates"]
        with patch.dict(fn.__globals__, {"MANAGED_ROOT": str(self.root)}):
            candidates.update(fn(str(self.root), self.uid))
        self.assertNotIn(str(path), candidates)

    def test_managed_candidates_only_two_levels_and_never_claude(self):
        (self.root / "codex/lane/deep").mkdir(parents=True)
        (self.root / "claude-keep").mkdir()
        (self.root / "codex/claude-keep").mkdir()
        (self.root / "file").touch()
        fn = MODULE["managed_candidates"]
        with patch.dict(fn.__globals__, {"MANAGED_ROOT": str(self.root)}):
            selected = fn(str(self.root), self.uid)
            self.assertEqual(
                set(selected), {str(self.root / "codex/lane"), str(self.root / "file")}
            )
            self.assertEqual(fn(str(self.root / "codex"), self.uid), {})

    def test_open_handle_in_codex_lane(self):
        path = self.root / "codex/lane"
        path.mkdir(parents=True)
        f = path / "open"
        f.touch()
        with f.open():
            # Restrict the proc fixture to this process; real held_paths reads its fd.
            listing = os.listdir
            with patch(
                "os.listdir",
                side_effect=lambda p: (
                    [str(os.getpid())] if p == "/proc" else listing(p)
                ),
            ):
                self.assertEqual(
                    MODULE["held_directories"]({str(path)}, [str(self.root)]),
                    {str(path)},
                )

    def test_mapping_holds_tree_after_descriptor_is_closed(self):
        path = self.root / "mapped"
        path.mkdir()
        payload = path / "payload"
        payload.write_bytes(b"mapped")
        with payload.open("rb") as handle:
            mapping = mmap.mmap(
                handle.fileno(), 0, access=mmap.ACCESS_READ, trackfd=False
            )
        self.addCleanup(mapping.close)
        listing = os.listdir
        with patch(
            "os.listdir",
            side_effect=lambda p: [str(os.getpid())] if p == "/proc" else listing(p),
        ):
            self.assertEqual(
                MODULE["held_directories"]({str(path)}, [str(self.root)]), {str(path)}
            )

    def test_running_queue_launch_protects_lane_without_open_file(self):
        launch = self.root / "launch.json"
        launch.write_text(
            json.dumps({"argv": ["worker", "/realm/tmp/work/codex/lane/prompt"]})
        )
        state = {
            "tasks": {
                "1": {
                    "status": {"Running": {}},
                    "command": "agentctl-run " + str(launch),
                }
            }
        }
        with patch("subprocess.check_output", return_value=json.dumps(state)):
            paths = MODULE["active_queue_paths"]()
        self.assertTrue(MODULE["queue_holds"]("/realm/tmp/work/codex/lane", paths))
        self.assertFalse(MODULE["queue_holds"]("/realm/tmp/work/codex/other", paths))
        launch.unlink()
        with patch("subprocess.check_output", return_value=json.dumps(state)):
            with self.assertRaises(FileNotFoundError):
                MODULE["active_queue_paths"]()

    def test_dry_run_reports_size_and_retains_dirty_and_queue_lanes(self):
        managed = self.root
        (managed / "codex/active").mkdir(parents=True)
        (managed / "old").mkdir()
        (managed / "old/payload").write_bytes(b"1234567")
        dirty = self.repo("dirty")
        (dirty / "file").write_text("uncommitted")
        self.old(managed)
        output = io.StringIO()
        fn = MODULE["main"]
        with (
            patch.dict(
                fn.__globals__,
                {
                    "MANAGED_ROOT": str(managed),
                    "roots": lambda: [str(managed)],
                    "held_directories": lambda *_: set(),
                    "drop_privileges": lambda *_: None,
                    "active_queue_paths": lambda: [
                        str(managed / "codex/active/prompt")
                    ],
                    "paced_remove": lambda *_: self.fail("dry-run removed a tree"),
                },
            ),
            patch("os.getuid", return_value=self.uid or 1000),
            patch("os.geteuid", return_value=self.uid or 1000),
            patch(
                "pwd.getpwnam",
                return_value=SimpleNamespace(pw_uid=self.uid, pw_dir=str(managed)),
            ),
            contextlib.redirect_stdout(output),
        ):
            if self.uid == 0:
                self.skipTest("requires non-root fixture owner")
            self.assertEqual(fn(["sweep", "--dry-run"]), 0)
        self.assertIn("reviewed=1 bytes=7 GB=0.000000", output.getvalue())
        self.assertIn("proposal requiring owner classification", output.getvalue())
        self.assertTrue((managed / "old/payload").exists())
        self.assertTrue((dirty / "file").exists())

    def test_real_mode_retains_old_unclassified_authored_evidence(self):
        path = self.root / "old-analysis"
        path.mkdir()
        report = path / "report.md"
        report.write_text("unique research evidence")
        self.old(path)
        fn = MODULE["main"]
        with (
            patch.dict(fn.__globals__, {
                "MANAGED_ROOT": str(self.root),
                "roots": lambda: [str(self.root)],
                "drop_privileges": lambda *_: None,
                "paced_remove": lambda *_: self.fail("removed unclassified evidence"),
            }),
            patch("subprocess.run"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            if self.uid == 0:
                self.skipTest("requires non-root fixture owner")
            self.assertEqual(fn(["sweep"]), 0)
        self.assertEqual(report.read_text(), "unique research evidence")

    def test_unknown_queue_retains_general_scratch_and_codex_lanes(self):
        (self.root / "codex/lane").mkdir(parents=True)
        (self.root / "general/payload").mkdir(parents=True)
        self.old(self.root)
        fn = MODULE["main"]
        def unavailable():
            raise PermissionError("queue unavailable")
        with (
            patch.dict(fn.__globals__, {
                "MANAGED_ROOT": str(self.root),
                "roots": lambda: [str(self.root)],
                "held_directories": lambda *_: set(),
                "drop_privileges": lambda *_: None,
                "active_queue_paths": unavailable,
                "paced_remove": lambda *_: self.fail("unknown queue removed scratch"),
            }),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            if self.uid == 0:
                self.skipTest("requires non-root fixture owner")
            self.assertEqual(fn(["sweep", "--dry-run"]), 0)
        self.assertTrue((self.root / "codex/lane").exists())
        self.assertTrue((self.root / "general/payload").exists())

    def test_paced_removal_obeys_entry_budget_and_preserves_symlink_target(self):
        path = self.root / "lane"
        path.mkdir()
        for n in range(4):
            (path / str(n)).touch()
        (path / "link").symlink_to(self.root / "keeper")
        (self.root / "keeper").write_text("keep")
        self.assertFalse(MODULE["paced_remove"](str(path), [2], time.monotonic() + 10))
        self.assertTrue(path.exists())
        self.assertTrue(MODULE["paced_remove"](str(path), [20], time.monotonic() + 10))
        self.assertEqual((self.root / "keeper").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
