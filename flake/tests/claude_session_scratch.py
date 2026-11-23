"""A Claude Code session's scratch ends with the session, on synthetic trees."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HOOK = Path(sys.argv[1])
del sys.argv[1]
spec = importlib.util.spec_from_file_location("sessionend_scratch", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

ENDED = "11111111-2222-4333-8444-555555555555"
OTHER = "66666666-7777-4888-9999-aaaaaaaaaaaa"


class SessionScratch(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.base = self.root / f"claude-{os.getuid()}"
        hook.PARKING = self.root / "parking"
        self.trees = {}
        for session in (ENDED, OTHER):
            for group in ("-realm-project-x", "session-tmp"):
                tree = self.base / group / session / "scratchpad"
                tree.mkdir(parents=True)
                (tree / "draft").write_text("synthetic")
                self.trees.setdefault(session, []).append(tree.parent)

    def end(self, session=ENDED):
        return hook.on_session_end({"session_id": session}, self.base)

    def test_an_ended_session_loses_its_trees_and_no_other(self):
        self.assertTrue(self.end())
        hook.remove_ended(self.base, wait=0)
        self.assertFalse(any(tree.exists() for tree in self.trees[ENDED]))
        self.assertTrue(all(tree.exists() for tree in self.trees[OTHER]))
        self.assertEqual(list((self.base / ".ended").iterdir()), [])
        self.assertEqual(list((self.base / ".released").iterdir()), [])

    def test_a_parked_session_keeps_its_trees_once(self):
        hook.PARKING.mkdir()
        (hook.PARKING / ENDED).touch()
        self.assertFalse(self.end())
        hook.remove_ended(self.base, wait=0)
        self.assertTrue(all(tree.exists() for tree in self.trees[ENDED]))
        self.assertFalse((hook.PARKING / ENDED).exists())
        # Resumed and ended again without parking, it goes.
        self.assertTrue(self.end())
        hook.remove_ended(self.base, wait=0)
        self.assertFalse(any(tree.exists() for tree in self.trees[ENDED]))

    def test_a_process_still_in_the_session_keeps_it_until_the_next_end(self):
        for holder in (
            {"env": {**os.environ, "CLAUDE_CODE_SESSION_ID": ENDED}},
            {"cwd": self.trees[ENDED][1]},
        ):
            with self.subTest(holder=sorted(holder)):
                process = subprocess.Popen(["sleep", "60"], **holder)
                self.addCleanup(process.kill)
                self.end()
                hook.remove_ended(self.base, wait=0)
                self.assertTrue(all(tree.exists() for tree in self.trees[ENDED]))
                self.assertTrue((self.base / ".ended" / ENDED).exists())
                process.kill()
                process.wait()
        # The next session's end takes the straggler's session along.
        self.end(OTHER)
        hook.remove_ended(self.base, wait=0)
        for session in (ENDED, OTHER):
            self.assertFalse(any(tree.exists() for tree in self.trees[session]))

    def test_malformed_events_change_nothing(self):
        for payload in ({}, {"session_id": "../x"}, {"session_id": 7}):
            self.assertFalse(hook.on_session_end(payload, self.base))
        self.assertFalse((self.base / ".ended").exists())
        link = self.base / "linked"
        link.symlink_to(self.base / "-realm-project-x", target_is_directory=True)
        self.assertEqual(
            sorted(hook.session_trees(self.base, ENDED)), sorted(self.trees[ENDED])
        )

    def test_the_hook_returns_at_once_and_its_remover_finishes(self):
        environment = {**os.environ, "CLAUDE_CODE_TMPDIR": str(self.root)}
        environment.pop("CLAUDE_CODE_SESSION_ID", None)
        environment["SINNIX_PARKING_DIR"] = str(self.root / "parking")
        started = time.monotonic()
        subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps({"session_id": ENDED, "reason": "other"}),
            text=True,
            env=environment,
            check=True,
        )
        self.assertLess(time.monotonic() - started, 5)
        deadline = time.monotonic() + 20
        while any(t.exists() for t in self.trees[ENDED]) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(any(tree.exists() for tree in self.trees[ENDED]))
        self.assertTrue(all(tree.exists() for tree in self.trees[OTHER]))


if __name__ == "__main__":
    unittest.main()
