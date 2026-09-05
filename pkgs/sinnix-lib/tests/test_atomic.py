"""The one publish: indivisible, private, and self-cleaning."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from sinnix_lib import atomic
from sinnix_lib.atomic import atomic_publish
from sinnix_lib.atomic_json import write_json_atomic


def test_publish_renames_a_complete_temporary_over_the_destination(
    tmp_path, monkeypatch
):
    """The new bytes reach the destination by rename, never by writing into it.

    Mutation: replace the helper's body with `destination.write_bytes(payload)`
    and os.replace is never called, so `observed` stays empty and this test
    fails on the first assertion -- a reader would have been able to see a
    half-written state file.
    """
    destination = tmp_path / "state.json"
    destination.write_bytes(b"old")
    observed: dict[str, object] = {}
    real_replace = os.replace

    def spy(source, target):
        observed["source"] = Path(source)
        observed["source_bytes"] = Path(source).read_bytes()
        observed["destination_bytes"] = Path(target).read_bytes()
        real_replace(source, target)

    monkeypatch.setattr(atomic.os, "replace", spy)
    assert atomic_publish(destination, b"new", fsync=False) is True

    assert observed["source"] != destination
    # The whole payload was in the temporary before anything was published.
    assert observed["source_bytes"] == b"new"
    # The destination still held the old bytes right up to the rename.
    assert observed["destination_bytes"] == b"old"
    assert destination.read_bytes() == b"new"
    assert [path.name for path in tmp_path.iterdir()] == ["state.json"]


def test_publish_removes_its_temporary_after_a_failed_write(tmp_path, monkeypatch):
    """A failed publish leaves no debris in the state directory.

    Mutation: drop the `finally: temporary.unlink(...)` from the helper and
    the directory listing below grows a `.state.json.<hex>.tmp` entry, so
    every failed write would leak a private file into gateway state.
    """
    destination = tmp_path / "state.json"
    destination.write_bytes(b"old")

    def explode(_descriptor):
        raise OSError("no space left on device")

    monkeypatch.setattr(atomic.os, "fsync", explode)
    with pytest.raises(OSError):
        atomic_publish(destination, b"new", fsync=True)

    assert [path.name for path in tmp_path.iterdir()] == ["state.json"]
    # A failed publish is also a publish that did not happen.
    assert destination.read_bytes() == b"old"


def test_publish_creates_the_destination_private(tmp_path):
    destination = tmp_path / "secret"
    atomic_publish(destination, b"key material", fsync=False)
    assert destination.stat().st_mode & 0o777 == 0o600
    assert destination.read_bytes() == b"key material"


def test_publish_syncs_the_file_and_its_directory_when_asked(tmp_path, monkeypatch):
    synced: list[int] = []
    real_fsync = os.fsync

    def record(descriptor):
        synced.append(os.fstat(descriptor).st_mode)
        real_fsync(descriptor)

    monkeypatch.setattr(atomic.os, "fsync", record)
    atomic_publish(tmp_path / "durable", b"payload", fsync=True)

    # One regular file, then the directory it was published into.
    assert len(synced) == 2
    assert not stat.S_ISDIR(synced[0])
    assert stat.S_ISDIR(synced[1])


def test_publish_does_not_sync_when_the_caller_says_it_need_not(tmp_path, monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(atomic.os, "fsync", lambda descriptor: calls.append(descriptor))
    atomic_publish(tmp_path / "cheap", b"payload", fsync=False)
    assert calls == []


def test_exclusive_publish_never_replaces_an_existing_destination(tmp_path):
    destination = tmp_path / "cursor-key"
    assert atomic_publish(destination, b"first", fsync=False, exclusive=True) is True
    assert atomic_publish(destination, b"second", fsync=False, exclusive=True) is False
    assert destination.read_bytes() == b"first"
    assert [path.name for path in tmp_path.iterdir()] == ["cursor-key"]


def test_write_json_atomic_syncs_the_file_and_its_directory_when_asked(
    tmp_path, monkeypatch
):
    """The JSON encoder passes durability through, it does not reimplement it.

    Mutation: hardcode ``fsync=False`` in ``write_json_atomic``'s call to
    ``atomic_publish`` and ``synced`` stays empty, so a caller that asked for
    a crash-durable state file would silently get an unsynced one.
    """
    synced: list[int] = []
    real_fsync = os.fsync

    def record(descriptor):
        synced.append(os.fstat(descriptor).st_mode)
        real_fsync(descriptor)

    monkeypatch.setattr(atomic.os, "fsync", record)
    write_json_atomic(tmp_path / "durable.json", {"a": 1}, fsync=True)

    assert len(synced) == 2
    assert not stat.S_ISDIR(synced[0])
    assert stat.S_ISDIR(synced[1])

    synced.clear()
    write_json_atomic(tmp_path / "cheap.json", {"a": 1})
    assert synced == []
