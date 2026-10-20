#!/usr/bin/env python3
# @sinnix-package: skip
"""Exercise cleanup only against disposable repositories and synthetic proc."""

import contextlib
import io
import os
import runpy
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = runpy.run_path(
    os.environ.get(
        "WORKTREE_REAP_SOURCE", str(Path(__file__).parents[1] / "sinnix-worktree-reap")
    )
)


class CleanupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix="reaper fixtures ", dir=os.environ.get("TMPDIR", "/realm/tmp/work")
        )
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env_patch = patch.dict(
            os.environ,
            {"HOME": str(self.root), "XDG_CONFIG_HOME": str(self.root / "config")},
        )
        env_patch.start()
        self.addCleanup(env_patch.stop)
        self.processes = [Path("/proc") / str(os.getpid())]
        original_iterdir = Path.iterdir

        def visible_processes(path):
            return (
                iter(self.processes)
                if path == Path("/proc")
                else original_iterdir(path)
            )

        process_patch = patch.object(Path, "iterdir", visible_processes)
        process_patch.start()
        self.addCleanup(process_patch.stop)
        self.repo = self.root / "repo"
        subprocess.run(
            ["git", "init", "-b", "main", str(self.repo)],
            capture_output=True,
            check=True,
        )
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("commit", "--allow-empty", "-m", "initial")

    def git(self, *args, root=None):
        return subprocess.run(
            ["git", "-C", str(root or self.repo), *args],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    def tree(self, branch="completed"):
        tree = self.root / f"tree {branch}"
        self.git("worktree", "add", "-b", branch, str(tree))
        return tree

    def reap(self):
        with contextlib.redirect_stdout(io.StringIO()):
            MODULE["reap_repo"](self.repo, "0s")

    def test_integrated_tree_and_branch_are_removed(self):
        tree = self.tree()
        self.reap()
        self.assertFalse(tree.exists())
        self.assertNotIn("refs/heads/completed", self.git("show-ref"))

    def test_cherry_picked_tree_is_removed_but_unmerged_work_remains(self):
        tree = self.tree()
        (tree / "change").write_text("integrated\n")
        self.git("add", ".", root=tree)
        self.git("commit", "-m", "change", root=tree)
        (self.repo / "other").write_text("target advanced\n")
        self.git("add", ".")
        self.git("commit", "-m", "target advanced")
        self.git("cherry-pick", self.git("rev-parse", "HEAD", root=tree))
        unmerged = self.tree("unmerged")
        (unmerged / "only-here").write_text("keep\n")
        self.git("add", ".", root=unmerged)
        self.git("commit", "-m", "unfinished", root=unmerged)
        self.reap()
        self.assertFalse(tree.exists())
        self.assertTrue(unmerged.exists())

    def test_squash_merged_worktree_is_removed(self):
        tree = self.tree()
        for name in ("one", "two"):
            (tree / name).write_text(name + "\n")
            self.git("add", ".", root=tree)
            self.git("commit", "-m", name, root=tree)
        self.git("merge", "--squash", "completed")
        self.git("commit", "-m", "squashed")
        self.reap()
        self.assertFalse(tree.exists())

    def test_default_age_floor_retains_new_checkout(self):
        tree = self.tree()
        with contextlib.redirect_stdout(io.StringIO()):
            MODULE["reap_repo"](self.repo)
        self.assertTrue(tree.exists())

    def test_dirty_untracked_and_ignored_files_are_retained(self):
        (self.repo / ".gitignore").write_text("ignored\n")
        (self.repo / "tracked").write_text("initial\n")
        self.git("add", ".")
        self.git("commit", "-m", "files")
        for name in ("tracked", "untracked", "ignored"):
            tree = self.tree(name)
            (tree / name).write_text("unsaved\n")
        self.reap()
        for name in ("tracked", "untracked", "ignored"):
            self.assertEqual(
                (self.root / f"tree {name}" / name).read_text(), "unsaved\n"
            )

    def test_live_and_manual_locks_are_retained_dead_and_reused_are_released(self):
        live = self.tree("live")
        manual = self.tree("manual")
        dead = self.tree("dead")
        reused = self.tree("reused")
        start = MODULE["process_start"](os.getpid())
        self.git(
            "worktree",
            "lock",
            "--reason",
            f"claude agent test (pid {os.getpid()} start {start})",
            str(live),
        )
        self.git("worktree", "lock", "--reason", "operator hold", str(manual))
        self.git(
            "worktree",
            "lock",
            "--reason",
            "claude agent test (pid 999999999 start 1)",
            str(dead),
        )
        self.git(
            "worktree",
            "lock",
            "--reason",
            f"claude agent test (pid {os.getpid()} start 0)",
            str(reused),
        )
        self.reap()
        self.assertTrue(live.exists())
        self.assertTrue(manual.exists())
        self.assertFalse(dead.exists())
        self.assertFalse(reused.exists())

    def test_unreadable_lock_owner_does_not_unlock_or_remove(self):
        tree = self.tree()
        self.git(
            "worktree",
            "lock",
            "--reason",
            "claude agent test (pid 1 start 1)",
            str(tree),
        )
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                self.reap()
        self.assertTrue(tree.exists())
        self.assertIn("locked", self.git("worktree", "list", "--porcelain"))

    def test_stat_handles_spaces_and_parentheses_and_absent_owner(self):
        proc = self.root / "proc"
        process = proc / "123"
        process.mkdir(parents=True)
        (process / "stat").write_text(
            "123 (a name ) with spaces) S " + "0 " * 18 + "456 0"
        )
        self.assertEqual(MODULE["process_start"](123, proc), "456")
        self.assertIsNone(MODULE["process_start"](124, proc))
        (process / "stat").unlink()
        with self.assertRaises(RuntimeError):
            MODULE["process_start"](123, proc)

    def test_process_entering_after_discovery_is_retained(self):
        tree = self.tree()
        calls = 0
        proc = None
        original = MODULE["candidates"]

        def discover(*args):
            nonlocal calls, proc
            calls += 1
            if calls == 2:
                proc = subprocess.Popen(["sleep", "30"], cwd=tree)
                self.processes.append(Path("/proc") / str(proc.pid))
            return original(*args)

        try:
            with patch.dict(MODULE["reap_repo"].__globals__, {"candidates": discover}):
                self.reap()
            self.assertGreaterEqual(calls, 2)
            self.assertTrue(tree.exists())
        finally:
            if proc:
                proc.terminate()
                proc.wait()

    def test_ignored_file_written_during_checks_is_retained(self):
        (self.repo / ".gitignore").write_text("ignored\n")
        self.git("add", ".")
        self.git("commit", "-m", "ignore generated file")
        tree = self.tree()
        calls = 0
        original = MODULE["candidates"]

        def discover(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                (tree / "ignored").write_text("valuable new data\n")
            return original(*args)

        with patch.dict(MODULE["reap_repo"].__globals__, {"candidates": discover}):
            self.reap()
        self.assertEqual((tree / "ignored").read_text(), "valuable new data\n")

    def test_unreadable_process_cwd_fails_closed(self):
        tree = self.tree()
        real_run = subprocess.run

        def run(args, **kwargs):
            if args[0] == "/run/wrappers/bin/sudo":
                raise subprocess.CalledProcessError(1, args, stderr="sudo denied")
            return real_run(args, **kwargs)

        with (
            patch("os.readlink", side_effect=PermissionError("denied")),
            patch("subprocess.run", side_effect=run),
        ):
            with self.assertRaisesRegex(RuntimeError, "cannot inspect"):
                self.reap()
        self.assertTrue(tree.exists())

    def test_privileged_cwd_read_preserves_spaces(self):
        result = subprocess.CompletedProcess([], 0, stdout="/a path/held\0", stderr="")
        with (
            patch("os.readlink", side_effect=PermissionError("denied")),
            patch("subprocess.run", return_value=result) as command,
        ):
            self.assertEqual(
                MODULE["process_cwd"](Path("/proc/123")), Path("/a path/held")
            )
        self.assertEqual(
            command.call_args.args[0],
            ("/run/wrappers/bin/sudo", "-n", "readlink", "-z", "--", "/proc/123/cwd"),
        )

    def test_pid_gone_during_privileged_read_is_normal_churn(self):
        error = subprocess.CalledProcessError(1, ["readlink"], stderr="gone")
        with (
            patch("os.readlink", side_effect=PermissionError("denied")),
            patch("subprocess.run", side_effect=error),
        ):
            with self.assertRaises(FileNotFoundError):
                MODULE["process_cwd"](Path("/proc/999999999"))

    def test_privileged_read_rejects_non_pid_targets(self):
        with self.assertRaises(ValueError):
            MODULE["process_cwd"](Path("/fixture/123"))

    def test_unknown_directory_and_mode_are_preserved(self):
        unknown = self.root / "ordinary directory"
        unknown.mkdir()
        file = unknown / "receipt"
        file.write_text("keep\n")
        file.chmod(0o444)
        # main's two roots are redirected to fixtures, with no project repos.
        original = Path.iterdir

        def entries(path):
            return (
                iter([unknown]) if path == Path("/realm/worktree") else original(path)
            )

        with (
            patch.object(Path, "glob", return_value=iter([])),
            patch.object(Path, "iterdir", entries),
        ):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(MODULE["main"](), 0)
        self.assertIn("retain (unknown directory", out.getvalue())
        self.assertEqual(file.read_text(), "keep\n")
        self.assertEqual(file.stat().st_mode & 0o777, 0o444)

    def test_command_failure_is_visible_and_nonzero(self):
        failure = subprocess.CalledProcessError(1, ["git"], stderr="fixture failure")
        with (
            patch.object(Path, "glob", return_value=iter([self.repo])),
            patch.object(Path, "iterdir", return_value=iter([])),
        ):
            with (
                patch("subprocess.run", side_effect=failure),
                contextlib.redirect_stderr(io.StringIO()) as out,
            ):
                self.assertEqual(MODULE["main"](), 1)
        self.assertIn("fixture failure", out.getvalue())


if __name__ == "__main__":
    unittest.main()
