"""Verify the evaluated native mail channel with isolated local stores."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

config = Path(os.environ["MAIL_CONFIG"]).read_text()
channel = config.split("Channel capture-mail\n", 1)[1]
directives = [line.strip() for line in channel.splitlines() if line.strip()]
assert "Sync Pull" in directives, (
    "the evaluated mail channel is not explicitly pull-only"
)
assert "Create Near" in directives
assert "Expunge None" in directives
assert "TLSType IMAPS" in config
assert 'PassCmd "cat ' in config
assert "fixture@example.invalid" in config
unit = json.loads(os.environ["MAIL_UNIT"])
timer = json.loads(os.environ["MAIL_TIMER"])
assert timer["OnCalendar"] == "*:0/15", timer
assert unit["UMask"] == "0077"
assert unit["Type"] == "oneshot"

with tempfile.TemporaryDirectory() as scratch:
    root = Path(scratch)
    far, near = root / "far", root / "near"
    for directory in (far, near):
        for leaf in ("new", "cur", "tmp"):
            (directory / "INBOX" / leaf).mkdir(parents=True)

    def message(directory, name, body):
        path = directory / "INBOX" / "new" / name
        path.write_bytes(
            f"From: fixture@example.invalid\nTo: other@example.invalid\n"
            f"Message-ID: <{name}@example.invalid>\nSubject: Fixture\n\n{body}\n".encode()
        )
        return path.read_bytes()

    def payload(data):
        # isync adds its own delivery identity header to copied messages.
        # Compare every original header/body byte while ignoring that field.
        header, separator, body = data.partition(b"\n\n")
        return (
            b"\n".join(
                line for line in header.split(b"\n") if not line.startswith(b"X-TUID: ")
            )
            + separator
            + body
        )

    def messages(directory):
        return {
            path: payload(path.read_bytes())
            for leaf in ("new", "cur")
            for path in (directory / "INBOX" / leaf).iterdir()
            if path.is_file()
        }

    # Retain the generated channel's policy directives exactly. Replace only
    # transport/store addresses and folder selection for the local fixture.
    local_channel = "\n".join(
        line
        for line in channel.splitlines()
        if not line.strip().startswith(("Far ", "Near ", "Patterns "))
    )
    fixture = root / "mbsyncrc"
    fixture.write_text(
        f"MaildirStore fixture-far\nPath {far}/\nInbox {far}/INBOX\nSubfolders Verbatim\n\n"
        f"MaildirStore fixture-near\nPath {near}/\nInbox {near}/INBOX\nSubfolders Verbatim\n\n"
        "Channel capture-mail\nFar :fixture-far:\nNear :fixture-near:\nPatterns INBOX\n"
        + local_channel
        + "\n"
    )

    def sync():
        subprocess.run(
            ["mbsync", "-c", str(fixture), "capture-mail"], check=True, timeout=15
        )

    original = message(far, "original", "remote original")
    sync()
    assert list(messages(near).values()) == [original]
    far_before = messages(far)
    local = message(near, "local-only", "must never upload")
    copied = next(path for path, value in messages(near).items() if value == original)
    copied.rename(copied.with_name(copied.name.split(":2,")[0] + ":2,S"))
    sync()
    assert messages(far) == far_before, (
        "local message or flag changes reached the far store"
    )
    assert local not in messages(far).values()
    for path in messages(far):
        path.unlink()
    sync()
    assert original in messages(near).values(), (
        "upstream deletion removed retained mail"
    )
    assert local in messages(near).values()
print("evaluated mail policy and isolated pull/flags/deletion preservation passed")
