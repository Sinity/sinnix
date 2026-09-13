"""Synthetic runtime contracts; no live state, browser opens, or notifications."""

import concurrent.futures
import importlib.machinery
import importlib.util
import json
import os
import sqlite3
import subprocess
import tempfile
import threading
import time
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

SCRIPT = Path(
    os.environ.get(
        "ACTIVITY_SCRIPT", str(Path(__file__).parents[2] / "scripts/sinnix-activity")
    )
)
loader = importlib.machinery.SourceFileLoader("activity_runtime", str(SCRIPT))
spec = importlib.util.spec_from_loader("activity_runtime", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)


class Clock:
    def __init__(self):
        self.value = datetime(2026, 1, 10, 18, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, **kwargs):
        self.value += timedelta(**kwargs)


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "runtime"
        self.clock = Clock()
        self.zone = ZoneInfo("Europe/Warsaw")
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def runner(self, argv, **kwargs):
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "123\n", "")

    def runtime(self, **kwargs):
        return m.Runtime(
            self.root,
            clock=self.clock,
            zone=self.zone,
            runner=kwargs.get("runner", self.runner),
        )

    def choose(self, **kwargs):
        with self.runtime() as runtime:
            return runtime.choose("reading", **({"for_duration": "30m"} | kwargs))

    def test_empty_status_is_not_a_declaration(self):
        with self.runtime() as runtime:
            state = runtime.status()
            self.assertEqual((state["mode"], state["revision"]), ("unallocated", 0))
            self.assertEqual(runtime.history(), [])

    def test_declaration_survives_restart_and_projection_loss(self):
        chosen = self.choose()
        (self.root / "current.json").unlink()
        with self.runtime() as runtime:
            self.assertEqual(runtime.status()["checkpoint_id"], chosen["checkpoint_id"])
            self.assertEqual(
                json.loads((self.root / "current.json").read_text())["activity"],
                "reading",
            )

    def test_midnight_uses_local_date_and_timezone(self):
        with self.runtime() as runtime:
            state = runtime.choose("rest", until="00:00")
        self.assertEqual(state["reconsider_at"], "2026-01-10T23:00:00Z")
        self.assertIn("2026-01-11 00:00", state["reconsider_local"])

    def test_clock_rolls_to_tomorrow(self):
        self.assertEqual(
            m.boundary("10:00", self.clock(), self.zone),
            datetime(2026, 1, 11, 9, tzinfo=timezone.utc),
        )

    def test_explicit_past_time_is_not_silently_moved(self):
        with self.assertRaises(ValueError):
            m.boundary("2025-01-01T00:00:00Z", self.clock(), self.zone)

    def test_ambiguous_dst_uses_next_actual_occurrence(self):
        current = datetime(2026, 10, 25, 0, 45, tzinfo=timezone.utc)
        self.assertEqual(
            m.boundary("02:30", current, self.zone),
            datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc),
        )

    def test_nonexistent_dst_time_is_explicit_error(self):
        with self.assertRaises(ValueError):
            m.boundary(
                "02:30", datetime(2026, 3, 28, 23, tzinfo=timezone.utc), self.zone
            )

    def test_invalid_inputs_have_no_history(self):
        with self.runtime() as runtime:
            for args in (
                {"for_duration": "0m"},
                {"for_duration": "-3m"},
                {"until": "25:12"},
                {"until": "2026-02-01T12:00:00"},
            ):
                with self.subTest(args=args), self.assertRaises(ValueError):
                    runtime.choose("reading", **args)
            for value in ("", "  ", "a\nb", "x" * 257):
                with self.subTest(name=value), self.assertRaises(ValueError):
                    runtime.choose(value, open_ended=True)
            self.assertEqual(runtime.history(), [])

    def test_open_ended_can_be_inhabited_without_due(self):
        with self.runtime() as runtime:
            runtime.choose("leisure", open_ended=True)
        self.clock.advance(days=10)
        with self.runtime() as runtime:
            state = runtime.tick(True)
            self.assertEqual(state["mode"], "active")
            self.assertIsNone(state["reconsider_at"])
        self.assertEqual(self.calls, [])

    def test_choose_preserves_destination(self):
        self.choose(return_url="https://example.test/continue")
        self.assertEqual(self.choose()["return_url"], "https://example.test/continue")

    def test_invalid_destination_rejected(self):
        for value in (
            "file:///x",
            "javascript:alert(1)",
            "https://",
            "https://user:password@example.test",
            "https://example.test:bad",
            "https://example.test/ a",
        ):
            with self.subTest(url=value), self.assertRaises(ValueError):
                m.url(value)

    def test_open_does_not_acknowledge(self):
        self.choose(return_url="https://example.test/path?x=a&y=b")
        with self.runtime() as runtime:
            state = runtime.open()
            self.assertEqual(state["mode"], "active")
            self.assertIsNone(state["last_ack_at"])
        self.assertEqual(
            self.calls, [["xdg-open", "https://example.test/path?x=a&y=b"]]
        )

    def test_failed_open_is_an_error_not_an_ack(self):
        self.choose(return_url="https://example.test")
        with self.runtime(
            runner=lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "unavailable")
        ) as runtime:
            with self.assertRaises(RuntimeError):
                runtime.open()
            self.assertEqual(runtime.status()["mode"], "active")

    def test_acknowledgement_suppresses_without_completing_activity(self):
        self.choose()
        self.clock.advance(hours=1)
        with self.runtime() as runtime:
            state = runtime.mutate("ack")
            self.assertEqual(state["activity"], "reading")
            revision = state["revision"]
            self.assertEqual(runtime.mutate("ack")["revision"], revision)
            runtime.tick(True)
        self.assertEqual(self.calls, [])

    def test_pause_resume_preserves_acknowledgement(self):
        self.choose()
        with self.runtime() as runtime:
            runtime.mutate("ack")
            runtime.mutate("pause")
            self.assertEqual(runtime.mutate("resume")["mode"], "acknowledged")

    def test_pause_suppresses_due_and_resume_preserves_boundary(self):
        before = self.choose()
        with self.runtime() as runtime:
            runtime.mutate("pause")
        self.clock.advance(hours=1)
        with self.runtime() as runtime:
            self.assertEqual(runtime.tick(True)["mode"], "paused")
            state = runtime.mutate("resume")
            self.assertEqual(state["mode"], "due")
            self.assertEqual(state["reconsider_at"], before["reconsider_at"])
        self.assertEqual(self.calls, [])

    def test_extension_is_from_now_with_new_checkpoint_and_budget(self):
        before = self.choose()
        self.clock.advance(hours=1)
        with self.runtime() as runtime:
            runtime.tick(True)
            runtime.mutate("ack")
            state = runtime.mutate("extend", "15m")
            self.assertNotEqual(state["checkpoint_id"], before["checkpoint_id"])
            self.assertEqual(state["started_at"], before["started_at"])
            self.assertEqual(state["seconds_remaining"], 900)
            self.assertIsNone(state["last_ack_at"])
            with self.assertRaises(ValueError):
                runtime.mutate("extend", "0m")
        self.clock.advance(minutes=16)
        with self.runtime() as runtime:
            runtime.tick(True)
        self.assertEqual(len(self.calls), 2)

    def test_tick_dry_does_not_consume_budget(self):
        self.choose()
        self.clock.advance(minutes=31)
        with self.runtime() as runtime:
            revision = runtime.status()["revision"]
            runtime.tick()
            self.assertEqual(runtime.status()["revision"], revision)
            runtime.tick(True)
        self.assertEqual(len(self.calls), 1)

    def test_notifications_are_deduplicated_and_bounded(self):
        self.choose()
        for minutes in (31, 1, 31, 1, 1440, 1440):
            self.clock.advance(minutes=minutes)
            with self.runtime() as runtime:
                runtime.tick(True)
        self.assertEqual(len(self.calls), 3)
        with self.runtime() as runtime:
            results = [
                r for r in runtime.history() if r["kind"] == "notification_result"
            ]
        self.assertTrue(
            all(
                r["payload"]["outcome"] == "submitted"
                and r["payload"]["human_notice"] == "unknown"
                for r in results
            )
        )

    def test_resume_after_days_sends_one_not_three(self):
        self.choose()
        self.clock.advance(days=3)
        with self.runtime() as runtime:
            runtime.tick(True)
            runtime.tick(True)
        self.assertEqual(len(self.calls), 1)

    def test_failed_notification_is_logged_and_bounded(self):
        self.choose()
        self.clock.advance(minutes=31)

        def failed(*args, **kwargs):
            self.calls.append(args)
            raise FileNotFoundError("synthetic missing notify-send")

        with self.runtime(runner=failed) as runtime:
            result = runtime.tick(True)
            self.assertEqual(result["notification"]["outcome"], "failed")
            runtime.tick(True)
        self.assertEqual(len(self.calls), 1)

    def test_concurrent_writes_preserve_every_event(self):
        self.choose()

        def write(i):
            with self.runtime() as runtime:
                runtime.choose(str(i), for_duration="30m")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(write, range(20)))
        with self.runtime() as runtime:
            self.assertEqual(len(runtime.history()), 21)
            self.assertEqual(
                json.loads((self.root / "current.json").read_text())["revision"],
                runtime.status()["revision"],
            )

    def test_ack_waits_for_submission_then_prevents_future_submission(self):
        self.choose()
        self.clock.advance(minutes=31)
        started, release, acked = (
            threading.Event(),
            threading.Event(),
            threading.Event(),
        )

        def slow(argv, **kwargs):
            started.set()
            self.assertTrue(release.wait(3))
            return self.runner(argv, **kwargs)

        def notify():
            with self.runtime(runner=slow) as runtime:
                runtime.tick(True)

        def ack():
            with self.runtime() as runtime:
                runtime.mutate("ack")
                acked.set()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(notify)
            self.assertTrue(started.wait(3))
            second = pool.submit(ack)
            time.sleep(0.08)
            self.assertFalse(acked.is_set())
            release.set()
            first.result()
            second.result()
        with self.runtime() as runtime:
            runtime.tick(True)
        self.assertEqual(len(self.calls), 1)

    def test_import_preserves_reported_time_and_is_idempotent_without_rewind(self):
        path = Path(self.temp.name) / "checkpoint.json"
        path.write_text(
            json.dumps(
                {
                    "last_declared_allocation": {
                        "activity": "leisure",
                        "effective_from": "2026-01-09T20:00:00+01:00",
                        "reconsider_at": "2026-01-10T00:00:00+01:00",
                    },
                    "conversation_url": "https://example.test",
                    "return_checkpoint": {"id": "synthetic-departure"},
                }
            )
        )
        with self.runtime() as runtime:
            state = runtime.import_checkpoint(path)
            self.assertEqual(state["mode"], "due")
            self.assertNotEqual(
                runtime.history()[0]["recorded_at"],
                runtime.history()[0]["effective_at"],
            )
            runtime.choose("new", for_duration="15m")
            revision = runtime.status()["revision"]
            state = runtime.import_checkpoint(path)
            self.assertEqual((state["activity"], state["revision"]), ("new", revision))

    def test_malformed_import_does_not_mutate(self):
        path = Path(self.temp.name) / "checkpoint.json"
        for data in (
            {},
            {"last_declared_allocation": {}},
            {
                "last_declared_allocation": {
                    "activity": "x",
                    "reconsider_at": "invalid",
                },
                "return_checkpoint": {"id": "id"},
            },
        ):
            path.write_text(json.dumps(data))
            with self.runtime() as runtime:
                with self.assertRaises(ValueError):
                    runtime.import_checkpoint(path)
                self.assertEqual(runtime.history(), [])

    def test_corrupt_database_preserved(self):
        self.root.mkdir()
        database = self.root / "activity.sqlite3"
        original = b"this is not SQLite"
        database.write_bytes(original)
        with self.assertRaises(sqlite3.DatabaseError):
            self.runtime()
        self.assertEqual(database.read_bytes(), original)

    def test_foreign_database_is_not_reinitialized(self):
        self.root.mkdir()
        with (
            closing(sqlite3.connect(self.root / "activity.sqlite3")) as database,
            database,
        ):
            database.execute("CREATE TABLE unrelated(value TEXT)")
        with self.assertRaises(RuntimeError):
            self.runtime()
        with closing(sqlite3.connect(self.root / "activity.sqlite3")) as database:
            self.assertEqual(
                database.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall(),
                [("unrelated",)],
            )

    def test_corrupt_state_does_not_become_an_empty_day(self):
        self.choose()
        with (
            closing(sqlite3.connect(self.root / "activity.sqlite3")) as database,
            database,
        ):
            database.execute("UPDATE state SET data='[]'")
        with self.assertRaises(RuntimeError):
            self.runtime()

    def test_private_permissions(self):
        self.choose()
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        for filename in ("activity.sqlite3", "runtime.lock", "current.json"):
            self.assertEqual((self.root / filename).stat().st_mode & 0o777, 0o600)

    def test_projection_error_does_not_mask_committed_state(self):
        self.choose()
        with self.runtime() as runtime:
            with patch.object(
                m.os, "replace", side_effect=OSError("synthetic disk error")
            ):
                with self.assertRaisesRegex(OSError, "synthetic disk error"):
                    runtime.mutate("ack")
            self.assertEqual(runtime.status()["mode"], "acknowledged")


class NoteTests(unittest.TestCase):
    setUp = ActivityTests.setUp
    tearDown = ActivityTests.tearDown
    runtime = ActivityTests.runtime
    runner = ActivityTests.runner
    choose = ActivityTests.choose

    def test_note_before_any_allocation(self):
        with self.runtime() as r:
            out = r.note("unfinished thought")
            self.assertEqual(out["mode"], "unallocated")
            self.assertIsNone(out["activity"])
            self.assertEqual(out["capture"]["event_id"], 1)
        with self.runtime() as r:
            self.assertEqual(r.status()["mode"], "unallocated")
            self.assertEqual(r.notes()[0]["text"], "unfinished thought")

    def test_notes_never_change_activity_fields(self):
        self.choose()
        with self.runtime() as r:
            for command in (None, "pause", "resume", "ack"):
                if command:
                    r.mutate(command)
                before = r.status()
                r.note("a fragment")
                after = r.status()
                self.assertEqual(
                    {k: before[k] for k in m.FIELDS}, {k: after[k] for k in m.FIELDS}
                )
            self.assertEqual(
                r.db.execute("SELECT count(*) FROM notices").fetchone()[0], 0
            )
        self.assertEqual(self.calls, [])

    def test_note_literal_unicode_and_shell_characters(self):
        value = 'reader\'s $(printf not-run); & "quoted" — żółw 🐢\nsecond line'
        with self.runtime() as r:
            r.note(value)
            self.assertEqual(r.notes()[0]["text"], value)
            self.assertEqual(r.history()[0]["payload"]["text"], value)
        self.assertEqual(self.calls, [])

    def test_invalid_notes_do_not_write(self):
        with self.runtime() as r:
            for value in ("", "  \n", "\x00", "a" * 8193):
                with self.subTest(value=value[:20]), self.assertRaises(ValueError):
                    r.note(value)
            self.assertEqual(r.history(), [])

    def test_duplicates_are_explicit_separate_observations(self):
        with self.runtime() as r:
            r.note("same")
            r.note("same")
            self.assertEqual(len(r.notes()), 2)
            self.assertNotEqual(r.notes()[0]["event_id"], r.notes()[1]["event_id"])

    def test_notes_filter_and_limit(self):
        self.choose()
        with self.runtime() as r:
            for i in range(4):
                r.note(str(i))
            r.mutate("ack")
            self.assertEqual([n["text"] for n in r.notes(2)], ["3", "2"])
            for limit in (0, -1, 201):
                with self.assertRaises(ValueError):
                    r.notes(limit)

    def test_note_records_source_and_context_without_classifying(self):
        chosen = self.choose()
        with self.runtime() as r:
            r.actor = "synthetic-capture"
            before = r.status()
            out = r.note("perhaps")
            # Capturing appends an event and nothing else: the declared
            # activity, boundary, acknowledgement and budget all stand.
            self.assertEqual(out["capture"]["text"], "perhaps")
            self.assertEqual(
                {k: v for k, v in r.status().items() if k != "revision"},
                {k: v for k, v in before.items() if k != "revision"},
            )
            note = r.notes()[0]
            self.assertEqual(note["actor"], "synthetic-capture")
            self.assertEqual(note["checkpoint_id"], chosen["checkpoint_id"])
            self.assertEqual(note["activity"], chosen["activity"])
            self.assertEqual(note["text"], "perhaps")
            self.assertNotIn("mood", note)

    def test_note_command_roundtrip(self):
        env = os.environ | {"SINNIX_ACTIVITY_STATE_DIR": str(self.root)}
        command = [os.sys.executable, str(SCRIPT)]
        out = subprocess.run(
            command + ["--actor", "synthetic-cli", "note", "--", "--literal"],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(json.loads(out.stdout)["capture"]["text"], "--literal")
        saved = subprocess.run(
            command + ["notes", "--limit", "1", "--json"],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(json.loads(saved.stdout)[0]["text"], "--literal")


if __name__ == "__main__":
    unittest.main()
