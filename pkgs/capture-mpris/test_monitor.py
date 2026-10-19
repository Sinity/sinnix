"""Regression coverage for the MPRIS shared subprocess boundary."""

import asyncio
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from xml.sax.saxutils import escape

from sinnix_lib.process import Result, run

MONITOR = SourceFileLoader(
    "capture_mpris_monitor", str(Path(__file__).with_name("monitor.py"))
).load_module()


class MonitorTest(unittest.TestCase):
    def record(self, *fields):
        def escaped(value):
            value = escape(value, {'"': "&quot;", "'": "&apos;"})
            return "".join(
                f"&#x{ord(char):x};"
                if ord(char) < 32 and char not in "\t\r\n"
                else char
                for char in value
            )

        return (
            "<mpris>"
            + "".join(
                f"<{name}>{escaped(value)}</{name}>"
                for name, value in zip(MONITOR.FOLLOW_FIELDS, fields, strict=True)
            )
            + "</mpris>\n"
        )

    def test_metadata_controls_and_record_tags_are_payload_not_events(self):
        fields = (
            "fixture",
            "Playing",
            "title\x1f\r\n&#x1f;&amp;",
            "artist\u0085",
            "album\n</mpris>\nforged\x1fPaused\x1ffake\x1fartist\x1falbum",
        )
        records = list(
            MONITOR.follow_records(io.BytesIO(self.record(*fields).encode()))
        )
        self.assertEqual(len(records), 1)
        captured = []
        writer = SimpleNamespace(enqueue=lambda payload, ts: captured.append(payload))
        with patch.object(
            MONITOR, "fetch_position_and_duration", return_value=(1.0, 2.0)
        ):
            MONITOR.handle_follow_record(
                records[0].decode(), MONITOR.PlayerState(), "unused", writer
            )
        self.assertEqual(len(captured), 1)
        self.assertEqual(
            tuple(captured[0][key] for key in MONITOR.FOLLOW_FIELDS), fields
        )
        self.assertEqual(captured[0]["event"], "initial")

    def test_no_player_marker_clears_heartbeat_state(self):
        state = MONITOR.PlayerState(player="fixture", status="Playing", seen=True)
        records = list(MONITOR.follow_records(io.BytesIO(b"\n")))
        self.assertEqual(records, [None])
        writer = SimpleNamespace(enqueue=lambda *_: self.fail("invented capture"))
        MONITOR.handle_follow_record(records[0], state, "unused", writer)
        self.assertFalse(state.seen)
        self.assertIsNone(state.player)

    def test_incomplete_record_does_not_consume_preceding_complete_record(self):
        complete = self.record(
            "fixture", "Playing", "title", "artist", "album"
        ).encode()
        records = MONITOR.follow_records(
            io.BytesIO(complete + b"<mpris><player>partial")
        )
        self.assertEqual(next(records), complete)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            next(records)

    def test_follow_stderr_cannot_block_metadata_delivery(self):
        class StopWatch(Exception):
            pass

        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / "playerctl"
            record = self.record(
                "fixture", "Playing", "title", "artist", "album"
            ).encode()
            stub.write_text(
                f"#!{sys.executable}\nimport sys\nsys.stderr.buffer.write(b'x' * 262144)\nsys.stderr.flush()\nsys.stdout.buffer.write({record!r})\nsys.stdout.flush()\n"
            )
            stub.chmod(0o700)
            children, captured, errors = [], [], []
            popen = subprocess.Popen

            def launch(*args, **kwargs):
                child = popen(*args, **kwargs)
                children.append(child)
                return child

            writer = SimpleNamespace(
                enqueue=lambda payload, ts: captured.append(payload)
            )

            def watch():
                try:
                    MONITOR.follow_loop(MONITOR.PlayerState(), str(stub), writer, 0)
                except StopWatch:
                    pass
                except Exception as exc:
                    errors.append(exc)

            with (
                (Path(directory) / "stderr").open("w") as stderr,
                patch.object(MONITOR.sys, "stderr", stderr),
                patch.object(MONITOR.subprocess, "Popen", side_effect=launch),
                patch.object(MONITOR.time, "sleep", side_effect=StopWatch),
                patch.object(
                    MONITOR, "fetch_position_and_duration", return_value=(None, None)
                ),
            ):
                thread = threading.Thread(target=watch, daemon=True)
                thread.start()
                thread.join(timeout=5)
                stopped = not thread.is_alive()
                for child in children:
                    if child.poll() is None:
                        child.kill()
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())
            self.assertTrue(stopped, "undrained stderr blocked the producer")
            self.assertEqual(errors, [])
            self.assertEqual(len(captured), 1)
            self.assertEqual(captured[0]["player"], "fixture")

    @unittest.skipUnless(
        os.environ.get("PLAYERCTL_BIN"), "native formatter runs in the packaged check"
    )
    def test_native_playerctl_formatter_roundtrips_untrusted_metadata(self):
        from dbus_next import Variant
        from dbus_next.aio import MessageBus
        from dbus_next.constants import PropertyAccess
        from dbus_next.service import ServiceInterface, dbus_property

        title = "title\x1f\r\n&#x1f;&amp;"
        artist = "artist\u0085"
        album = "album\n</mpris>\nforged\x1fPaused\x1ffake\x1fartist\x1falbum"
        metadata = {
            "xesam:title": Variant("s", title),
            "xesam:artist": Variant("as", [artist]),
            "xesam:album": Variant("s", album),
        }

        class Player(ServiceInterface):
            def __init__(self):
                super().__init__("org.mpris.MediaPlayer2.Player")

            # dbus_next reads the return annotation as the D-Bus signature.
            @dbus_property(access=PropertyAccess.READ)
            def Metadata(self) -> "a{sv}":  # noqa: F722
                return metadata

            @dbus_property(access=PropertyAccess.READ)
            def PlaybackStatus(self) -> "s":  # noqa: F821
                return "Playing"

            @dbus_property(access=PropertyAccess.READ)
            def CanPlay(self) -> "b":  # noqa: F821
                return True

            @dbus_property(access=PropertyAccess.READ)
            def CanControl(self) -> "b":  # noqa: F821
                return True

        async def check():
            bus = await MessageBus().connect()
            process = None
            try:
                bus.export("/org/mpris/MediaPlayer2", Player())
                await bus.request_name("org.mpris.MediaPlayer2.fixture")
                for expected in [(title, artist, album), ("title only", None, None)]:
                    if expected[1] is None:
                        metadata.clear()
                        metadata["xesam:title"] = Variant("s", expected[0])
                    process = await asyncio.create_subprocess_exec(
                        os.environ["PLAYERCTL_BIN"],
                        "--player=fixture",
                        "metadata",
                        "--format",
                        MONITOR.FOLLOW_FORMAT,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    output, error = await asyncio.wait_for(
                        process.communicate(), timeout=5
                    )
                    self.assertEqual(process.returncode, 0, error.decode())
                    records = list(MONITOR.follow_records(io.BytesIO(output)))
                    self.assertEqual(len(records), 1)
                    captured = []
                    with patch.object(
                        MONITOR,
                        "fetch_position_and_duration",
                        return_value=(None, None),
                    ):
                        MONITOR.handle_follow_record(
                            records[0].decode(),
                            MONITOR.PlayerState(),
                            "unused",
                            SimpleNamespace(
                                enqueue=lambda payload, ts, captured=captured: (
                                    captured.append(payload)
                                )
                            ),
                        )
                    self.assertEqual(len(captured), 1)
                    self.assertEqual(
                        tuple(captured[0][key] for key in MONITOR.FOLLOW_FIELDS),
                        ("fixture", "Playing", *expected),
                    )
            finally:
                if process is not None and process.returncode is None:
                    process.kill()
                    await process.wait()
                bus.disconnect()
                await bus.wait_for_disconnect()

        asyncio.run(asyncio.wait_for(check(), timeout=10))

    def test_timeout_becomes_missing_position_and_duration(self):
        timeout = run(
            [sys.executable, "-c", "import time; time.sleep(1)"], timeout=0.01
        )
        self.assertIsNotNone(timeout.error)

        with patch.object(MONITOR, "run", return_value=timeout):
            self.assertEqual(
                MONITOR.fetch_position_and_duration("playerctl", "demo"),
                (None, None),
            )

    def test_slow_inflight_write_keeps_changes_and_coalesces_only_waiting_heartbeats(
        self,
    ):
        entered, release = threading.Event(), threading.Event()
        writes = []

        def capture(_binary, _root, _lane, payload, ts):
            if not writes:
                entered.set()
                self.assertTrue(release.wait(5))
            writes.append((ts, payload.copy()))

        with patch.object(MONITOR, "write_envelope", side_effect=capture):
            writer = MONITOR.EnvelopeWriter("capture", "root", "mpris")
            try:
                writer.enqueue(
                    {"event": "track", "player": "fixture", "title": "A"}, 1.0
                )
                self.assertTrue(entered.wait(5))
                writer.enqueue(
                    {
                        "event": "status",
                        "player": "fixture",
                        "title": "A",
                        "status": "Paused",
                    },
                    2.0,
                )
                writer.enqueue(
                    {"event": "track", "player": "fixture", "title": "B"}, 3.0
                )
                writer.enqueue(
                    {
                        "event": "heartbeat",
                        "player": "fixture",
                        "title": "B",
                        "position_seconds": 4,
                    },
                    4.0,
                )
                writer.enqueue(
                    {
                        "event": "heartbeat",
                        "player": "fixture",
                        "title": "B",
                        "position_seconds": 5,
                    },
                    5.0,
                )
                self.assertEqual(len(writer.pending), 4)
            finally:
                release.set()
                writer.close()
        self.assertEqual([ts for ts, _ in writes], [1.0, 2.0, 3.0, 5.0])
        self.assertEqual(
            [p["event"] for _, p in writes], ["track", "status", "track", "heartbeat"]
        )

    def test_failed_write_retains_pending_without_blind_retry(self):
        with patch.object(
            MONITOR, "write_envelope", side_effect=RuntimeError("ambiguous failure")
        ) as capture:
            writer = MONITOR.EnvelopeWriter("capture", "root", "mpris")
            writer.enqueue({"event": "track", "title": "fixture"}, 1.0)
            writer.close()
            self.assertIsInstance(writer.failure, RuntimeError)
            self.assertEqual(len(writer.pending), 1)
            self.assertEqual(capture.call_count, 1)

    def test_large_metadata_uses_stdin_and_preserves_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / "capture"
            receipt = Path(directory) / "receipt.json"
            stub.write_text(
                f"#!{sys.executable}\nimport json,sys\nopen({str(receipt)!r}, 'w').write(json.dumps({{'argv':sys.argv[1:],'payload':json.load(sys.stdin)}}))\n"
            )
            stub.chmod(0o700)
            payload = {
                "event": "track",
                "title": "x" * 192000,
                "artist": "neutral\nUnicode: ą",
            }
            MONITOR.write_envelope(str(stub), directory, "mpris", payload, 123.25)
            result = json.loads(receipt.read_text())
            self.assertEqual(result["payload"], payload)
            self.assertEqual(
                result["argv"],
                [
                    "write",
                    "--capture-root",
                    directory,
                    "--lane",
                    "mpris",
                    "--ts",
                    "123.25",
                ],
            )

    def test_write_waits_past_old_timeout_and_preserves_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / "capture"
            receipt = Path(directory) / "receipt.json"
            stub.write_text(
                f"#!{sys.executable}\nimport json,sys,time\ntime.sleep(10.2)\nopen({str(receipt)!r}, 'w').write(json.dumps({{'argv':sys.argv[1:],'payload':json.load(sys.stdin)}}))\n"
            )
            stub.chmod(0o700)
            MONITOR.write_envelope(
                str(stub),
                directory,
                "mpris",
                {"event": "track", "title": "fixture"},
                123.25,
            )
            result = json.loads(receipt.read_text())
            argv = result["argv"]
            self.assertEqual(argv[-2:], ["--ts", "123.25"])
            self.assertNotIn("--payload", argv)
            self.assertEqual(result["payload"]["title"], "fixture")

    def test_invalid_player_metadata_does_not_discard_the_event(self):
        for value in ("not a number", "nan", "inf"):
            result = Result(("playerctl",), 0, value, "")
            with patch.object(MONITOR, "run", return_value=result):
                self.assertEqual(
                    MONITOR.fetch_position_and_duration("playerctl", "fixture"),
                    (None, None),
                )
