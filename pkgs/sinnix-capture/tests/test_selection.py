"""Selection-lane contract: MIME choice, blob layout, and the two gates.

Every capture here runs through ``main(["selection", ...])`` -- the same
entry point the clipboard and PRIMARY lane units invoke -- against fake
list/paste/window commands, so the assertions cover the subcommand end to
end rather than its helpers in isolation.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

import pytest
from sinnix_capture.cli import main
from sinnix_capture.selection import pick_mime

# The preference order this lane promises, spelled out independently of the
# table the implementation reads: any permutation of that table has to break
# one of the adjacent pairs below.
EXPECTED_PREFERENCE = [
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/bmp",
    "image/tiff",
    "image/webp",
    "text/uri-list",
    "text/plain;charset=utf-8",
    "text/plain",
    "STRING",
    "UTF8_STRING",
]


def _fake_command(tmp_path: Path, name: str, body: str) -> str:
    """A command string running `body` under this interpreter."""
    script = tmp_path / f"{name}.py"
    script.write_text(body)
    return f"{sys.executable} {script}"


def _emit_file(source: Path, argv_log: Path | None = None) -> str:
    log = (
        f"pathlib.Path({str(argv_log)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        if argv_log is not None
        else ""
    )
    return (
        "import json, pathlib, sys\n"
        f"{log}"
        f"sys.stdout.buffer.write(pathlib.Path({str(source)!r}).read_bytes())\n"
    )


class Lane:
    """A capture root plus the fake commands one lane invocation needs."""

    def __init__(self, tmp_path: Path, lane: str = "clipboard") -> None:
        self.root = tmp_path / "captures"
        self.lane = lane
        self.lane_dir = self.root / lane
        self.types_file = tmp_path / "types"
        self.content_file = tmp_path / "content"
        self.window_file = tmp_path / "window.json"
        self.paste_argv = tmp_path / "paste-argv.json"
        self.types_file.write_text("text/plain;charset=utf-8\n")
        self.content_file.write_bytes(b"hello from the fixture")
        self.window_file.write_text('{"class": "kitty", "title": "test terminal"}')
        self.list_command = _fake_command(tmp_path, "list", _emit_file(self.types_file))
        self.paste_command = _fake_command(
            tmp_path, "paste", _emit_file(self.content_file, argv_log=self.paste_argv)
        )
        self.window_command = _fake_command(
            tmp_path, "window", _emit_file(self.window_file)
        )

    def run(self, *extra: str) -> int:
        return main(
            [
                "selection",
                "--capture-root",
                str(self.root),
                "--lane",
                self.lane,
                "--list-command",
                self.list_command,
                "--paste-command",
                self.paste_command,
                "--window-command",
                self.window_command,
                *extra,
            ]
        )

    def records(self) -> list[dict]:
        return [
            json.loads(line)
            for path in sorted(self.lane_dir.glob(f"{self.lane}-2*.jsonl"))
            for line in path.read_text().splitlines()
        ]


@pytest.fixture
def lane(tmp_path: Path) -> Lane:
    return Lane(tmp_path)


@pytest.mark.parametrize(
    ("preferred", "over"),
    list(zip(EXPECTED_PREFERENCE, EXPECTED_PREFERENCE[1:], strict=False)),
)
def test_preference_order_holds_for_every_adjacent_pair(
    preferred: str, over: str
) -> None:
    # Offered in the losing order, so a match by offer order rather than by
    # preference would pick the wrong one.
    assert pick_mime(f"{over}\n{preferred}\n") == preferred


def test_an_unrecognized_type_falls_back_to_the_first_offered() -> None:
    assert pick_mime("application/x-vendor\ntext/rtf\n") == "application/x-vendor"


def test_nothing_offered_picks_nothing() -> None:
    assert pick_mime("\n\n") is None


def test_the_chosen_mime_is_what_the_paste_command_is_asked_for(lane: Lane) -> None:
    lane.types_file.write_text("text/plain\nimage/png\n")
    lane.content_file.write_bytes(b"\x89PNG\r\n\x1a\n binary payload")

    assert lane.run() == 0

    assert json.loads(lane.paste_argv.read_text()) == ["image/png"]
    assert lane.records()[0]["payload"]["mime"] == "image/png"


def test_text_selection_lands_inline_with_window_attribution(lane: Lane) -> None:
    assert lane.run() == 0

    (record,) = lane.records()
    assert record["lane"] == "clipboard"
    assert record["raw_ref"] is None
    assert record["payload"] == {
        "category": "text",
        "mime": "text/plain;charset=utf-8",
        "text": "hello from the fixture",
        "size": len(b"hello from the fixture"),
        "source_window": {"class": "kitty", "title": "test terminal"},
    }


def test_an_unreadable_window_command_still_captures(tmp_path: Path) -> None:
    lane = Lane(tmp_path)
    lane.window_command = f"{sys.executable} -c 'raise SystemExit(1)'"

    assert lane.run() == 0

    assert lane.records()[0]["payload"]["source_window"] == {
        "class": None,
        "title": None,
    }


def test_binary_selection_lands_in_a_two_character_shard(lane: Lane) -> None:
    body = b"\x89PNG\r\n\x1a\n not really a png"
    lane.types_file.write_text("image/png\n")
    lane.content_file.write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()

    assert lane.run() == 0

    blob = lane.lane_dir / "blobs" / digest[:2] / digest
    assert blob.read_bytes() == body
    assert blob.stat().st_mode & 0o777 == 0o600
    (record,) = lane.records()
    assert record["raw_ref"] == str(blob)
    assert record["payload"] == {
        "category": "binary",
        "mime": "image/png",
        "sha256": digest,
        "size": len(body),
        "source_window": {"class": "kitty", "title": "test terminal"},
    }
    # The lane directory holds the daily file, the index, the counter and the
    # blob tree -- no staging leftovers beside the blob.
    assert sorted(p.name for p in (lane.lane_dir / "blobs" / digest[:2]).iterdir()) == [
        digest
    ]


def test_identical_content_is_stored_once_under_its_hash(lane: Lane) -> None:
    body = b"\x89PNG\r\n\x1a\n repeated"
    lane.types_file.write_text("image/png\n")
    lane.content_file.write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()

    assert lane.run() == 0
    assert lane.run() == 0

    shard = lane.lane_dir / "blobs" / digest[:2]
    assert [p.name for p in shard.iterdir()] == [digest]
    # Two captures of the same image are two records pointing at one blob.
    assert [r["raw_ref"] for r in lane.records()] == [str(shard / digest)] * 2


def test_dedup_state_drops_an_immediate_repeat(lane: Lane, tmp_path: Path) -> None:
    state = tmp_path / "state" / "last-selection"

    assert lane.run("--dedup-state", str(state)) == 0
    assert lane.run("--dedup-state", str(state)) == 0
    assert len(lane.records()) == 1

    # A different selection is not a repeat, and the one after it is again.
    lane.content_file.write_bytes(b"something else entirely")
    assert lane.run("--dedup-state", str(state)) == 0
    assert lane.run("--dedup-state", str(state)) == 0
    assert [r["payload"]["text"] for r in lane.records()] == [
        "hello from the fixture",
        "something else entirely",
    ]


def test_without_dedup_state_repeated_content_still_lands(lane: Lane) -> None:
    assert lane.run() == 0
    assert lane.run() == 0
    assert len(lane.records()) == 2


def test_debounce_yields_to_a_newer_trigger(lane: Lane, tmp_path: Path) -> None:
    trigger = tmp_path / "state" / "last-trigger"
    trigger.parent.mkdir(parents=True)

    # A capture whose settle window is claimed by a later trigger writes
    # nothing; the invocation still holding the trigger at wake-up writes.
    assert lane.run("--debounce-ms", "60", "--debounce-state", str(trigger)) == 0
    assert len(lane.records()) == 1

    original_sleep = __import__("time").sleep

    def steal(seconds: float) -> None:
        original_sleep(seconds)
        trigger.write_text("a newer selection")

    monkey = pytest.MonkeyPatch()
    monkey.setattr("sinnix_capture.selection.time.sleep", steal)
    try:
        assert lane.run("--debounce-ms", "0", "--debounce-state", str(trigger)) == 0
    finally:
        monkey.undo()
    assert len(lane.records()) == 1


def test_debounce_requires_a_trigger_file(lane: Lane) -> None:
    assert lane.run("--debounce-ms", "10") == 2


def test_an_empty_selection_is_not_a_capture(lane: Lane) -> None:
    lane.content_file.write_bytes(b"")

    assert lane.run() == 0
    assert lane.records() == []


def test_nothing_on_offer_is_not_a_capture(lane: Lane) -> None:
    lane.types_file.write_text("")

    assert lane.run() == 0
    assert lane.records() == []


def test_the_watch_payload_is_drained_before_anything_else(
    lane: Lane, monkeypatch: pytest.MonkeyPatch
) -> None:
    # wl-paste --watch writes the new selection to stdin. Leaving it unread
    # while asking the same owner for a second transfer deadlocks both sides.
    payload = io.BytesIO(b"x" * 131072)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(payload))

    assert lane.run() == 0

    assert payload.read() == b""
    assert len(lane.records()) == 1
