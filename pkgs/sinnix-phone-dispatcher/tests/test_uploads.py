"""Phone-pushed bulk capture uploads: sha256 verification before rename, and
re-upload-of-an-identical-chunk is a success (never a 409, since the phone
legitimately retries when an ok is lost on the way back).

Mutations that would fail this: renaming the part file into place BEFORE the
sha256 comparison (instead of after) fails
test_sha_mismatch_does_not_land_the_file; validating a lane path as one string
instead of segment by segment fails test_a_traversing_path_is_rejected.
"""

from __future__ import annotations

import hashlib
import os
import stat
import multiprocessing
from http import HTTPStatus

import pytest
import sinnix_phone_dispatcher.uploads as uploads_mod


def test_repair_serializes_with_late_upload_process(monkeypatch, tmp_path):
    monkeypatch.setattr(uploads_mod, "EVENTS_DIR", tmp_path)
    original = b'{"n":0}\n'
    replacement = b'{"n":1}\n'
    target = tmp_path / "events-20200101.jsonl"
    target.write_bytes(original)
    source = tmp_path / "source"
    source.write_bytes(replacement)
    ctx = multiprocessing.get_context("fork")
    started, finished = ctx.Event(), ctx.Event()
    parent, child = ctx.Pipe(duplex=False)
    def upload():
        started.set()
        status, payload = uploads_mod.append_events("20200101", 0, original + b'{"n":2}\n', None)
        child.send(int(status))
        finished.set()
    process = ctx.Process(target=upload)
    real_replace = uploads_mod.os.replace
    finished_before_replace = []
    def replace(pending, destination):
        process.start()
        assert started.wait(5)
        finished_before_replace.append(finished.wait(0.2))
        real_replace(pending, destination)
    monkeypatch.setattr(uploads_mod.os, "replace", replace)
    try:
        result = uploads_mod.repair_event_day("20200101", source, hashlib.sha256(original).hexdigest())
        process.join(5)
        assert not process.is_alive()
        assert parent.poll(1)
        assert parent.recv() == int(HTTPStatus.CONFLICT)
        assert finished_before_replace == [False]
        assert result["changed"]
        assert target.read_bytes() == replacement
        assert next((tmp_path / ".repairs").iterdir()).read_bytes() == original
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        parent.close()
        child.close()


def _lanes(tmp_path):
    return {"ambient": tmp_path / "ambient"}


def test_sha_mismatch_does_not_land_the_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", _lanes(tmp_path))
    progress = tmp_path / "ambient-progress"
    monkeypatch.setattr(uploads_mod, "AMBIENT_PROGRESS_MARKER", progress)
    body = b"chunk bytes"

    status, payload = uploads_mod.store_upload("ambient", "clip.m4a", body, "0" * 64)

    assert status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert payload["ok"] is False
    assert not (tmp_path / "ambient" / "clip.m4a").exists()
    assert not progress.exists()


def test_correct_sha_lands_the_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", _lanes(tmp_path))
    progress = tmp_path / "ambient-progress"
    monkeypatch.setattr(uploads_mod, "AMBIENT_PROGRESS_MARKER", progress)
    body = b"chunk bytes"
    digest = hashlib.sha256(body).hexdigest()

    status, payload = uploads_mod.store_upload("ambient", "clip.m4a", body, digest)

    assert status == HTTPStatus.OK
    assert payload["ok"] is True
    assert payload["duplicate"] is False
    target = tmp_path / "ambient" / "clip.m4a"
    assert target.read_bytes() == body
    assert target.stat().st_mode & 0o777 == 0o660
    assert not list(target.parent.glob(".*.atomic-tmp-*"))
    assert progress.is_file()


def test_progress_marker_failure_does_not_acknowledge_a_landed_chunk(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", _lanes(tmp_path))
    monkeypatch.setattr(
        uploads_mod,
        "AMBIENT_PROGRESS_MARKER",
        tmp_path / "missing" / "ambient-progress",
    )
    body = b"chunk bytes"

    status, payload = uploads_mod.store_upload(
        "ambient", "clip.m4a", body, hashlib.sha256(body).hexdigest()
    )

    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert payload["ok"] is False
    assert (tmp_path / "ambient" / "clip.m4a").read_bytes() == body


def test_reuploading_the_identical_chunk_is_a_success_duplicate(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", _lanes(tmp_path))
    progress = tmp_path / "ambient-progress"
    monkeypatch.setattr(uploads_mod, "AMBIENT_PROGRESS_MARKER", progress)
    body = b"chunk bytes"
    digest = hashlib.sha256(body).hexdigest()
    uploads_mod.store_upload("ambient", "clip.m4a", body, digest)
    marked_at = progress.stat().st_mtime

    status, payload = uploads_mod.store_upload("ambient", "clip.m4a", body, digest)

    assert status == HTTPStatus.OK
    assert payload["duplicate"] is True
    assert progress.stat().st_mtime == marked_at


def test_unknown_lane_is_rejected(tmp_path) -> None:
    status, payload = uploads_mod.store_upload("unknown-lane", "clip.m4a", b"x", None)
    assert status == HTTPStatus.NOT_FOUND
    assert payload["ok"] is False


def test_unacceptable_file_name_is_rejected(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", _lanes(tmp_path))
    status, payload = uploads_mod.store_upload("ambient", "../escape.m4a", b"x", None)
    assert status == HTTPStatus.BAD_REQUEST
    assert payload["ok"] is False


def test_a_lane_subdirectory_is_preserved(monkeypatch, tmp_path) -> None:
    """The camera mirror keeps DCIM's own shape -- Camera/, Screenshots/,
    Pictures/ -- because the rsync that filled the lane did."""
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", {"camera": tmp_path / "camera"})
    body = b"jpeg bytes"

    status, payload = uploads_mod.store_upload(
        "camera", "Camera/IMG_0001.jpg", body, hashlib.sha256(body).hexdigest()
    )

    assert status == HTTPStatus.OK
    assert (tmp_path / "camera" / "Camera" / "IMG_0001.jpg").read_bytes() == body


@pytest.mark.parametrize(
    "name",
    [
        "../escape.jpg",
        "Camera/../../escape.jpg",
        "a/b/c/d/e/deep.jpg",
        "Camera/",
        "/abs.jpg",
        "Camera/IMG_0001.jpg\n",
        "Camera\n/IMG_0001.jpg",
    ],
)
def test_a_traversing_path_is_rejected(monkeypatch, tmp_path, name) -> None:
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", {"camera": tmp_path / "camera"})

    status, payload = uploads_mod.store_upload("camera", name, b"x", None)

    assert status == HTTPStatus.BAD_REQUEST
    assert payload["ok"] is False
    assert not (tmp_path / "escape.jpg").exists()


def test_repair_closed_day_preserves_original(monkeypatch, tmp_path):
    monkeypatch.setattr(uploads_mod, "EVENTS_DIR", tmp_path)
    target = tmp_path / "events-20200101.jsonl"
    target.write_bytes(b"broken record\n")
    original = target.read_bytes()
    source = tmp_path / "device.jsonl"
    source.write_bytes(b'{"kind":"power","ts":"2020-01-01T12:00:00Z"}\n')
    result = uploads_mod.repair_event_day(
        "20200101", source, hashlib.sha256(original).hexdigest()
    )
    from pathlib import Path

    assert target.read_bytes() == source.read_bytes()
    assert Path(result["backup"]).read_bytes() == original
    assert (
        uploads_mod.repair_event_day("20200101", source, result["sha256"])["changed"]
        is False
    )


def test_repair_rejects_changed_destination_and_invalid_source(monkeypatch, tmp_path):
    monkeypatch.setattr(uploads_mod, "EVENTS_DIR", tmp_path)
    target = tmp_path / "events-20200101.jsonl"
    target.write_bytes(b"old\n")
    source = tmp_path / "device.jsonl"
    source.write_bytes(b"{}\n")
    with pytest.raises(ValueError, match="destination changed"):
        uploads_mod.repair_event_day("20200101", source, "0" * 64)
    source.write_bytes(b"broken\n")
    with pytest.raises(ValueError):
        uploads_mod.repair_event_day(
            "20200101", source, hashlib.sha256(b"old\n").hexdigest()
        )
    assert target.read_bytes() == b"old\n"
    assert not (tmp_path / ".repairs").exists()


def test_repair_rejects_active_or_future_day(tmp_path):
    with pytest.raises(ValueError, match="closed UTC day"):
        uploads_mod.repair_event_day("99991231", tmp_path / "source", "0" * 64)


def test_a_read_back_mismatch_is_not_acknowledged(monkeypatch, tmp_path) -> None:
    """Anti-vacuity: the ack must come from the retained file, so a store that
    keeps different bytes than it was handed must answer ok:false."""
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", _lanes(tmp_path))
    monkeypatch.setattr(
        uploads_mod, "AMBIENT_PROGRESS_MARKER", tmp_path / "ambient-progress"
    )
    real = uploads_mod.atomic_publish

    def lossy(target, body, **kw):
        return real(target, body[:-1], **kw)

    monkeypatch.setattr(uploads_mod, "atomic_publish", lossy)
    body = b"chunk bytes"
    status, payload = uploads_mod.store_upload(
        "ambient", "clip.m4a", body, hashlib.sha256(body).hexdigest()
    )
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR and payload["ok"] is False
    assert not (tmp_path / "ambient-progress").exists()


@pytest.mark.parametrize("kind", ["fifo", "directory", "symlink"])
def test_repair_refuses_nonregular_capture_destination(monkeypatch, tmp_path, kind):
    monkeypatch.setattr(uploads_mod, "EVENTS_DIR", tmp_path)
    target = tmp_path / "events-20200101.jsonl"
    source = tmp_path / "source.jsonl"
    source.write_bytes(b"{}\n")
    if kind == "fifo":
        os.mkfifo(target)
    elif kind == "directory":
        target.mkdir()
    else:
        retained = tmp_path / "retained.jsonl"
        retained.write_bytes(b"old\n")
        target.symlink_to(retained)
    real_open = os.open

    def checked_open(path, flags, *args, **kwargs):
        if path == target:
            assert flags & os.O_NONBLOCK and flags & os.O_NOFOLLOW
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(uploads_mod.os, "open", checked_open)
    with pytest.raises(OSError):
        uploads_mod.repair_event_day("20200101", source, hashlib.sha256(b"old\n").hexdigest())
    assert source.read_bytes() == b"{}\n" and not (tmp_path / ".repairs").exists()
    if kind == "symlink":
        assert retained.read_bytes() == b"old\n"


def test_retained_digest_refuses_a_symlink(tmp_path):
    retained = tmp_path / "retained"
    retained.write_bytes(b"fixture")
    alias = tmp_path / "alias"
    alias.symlink_to(retained)
    with pytest.raises(OSError):
        uploads_mod._retained_digest(alias)
    assert retained.read_bytes() == b"fixture"


@pytest.mark.parametrize("fail_directory", [False, True])
def test_existing_upload_is_not_acknowledged_after_failed_sync(monkeypatch, tmp_path, fail_directory):
    lanes = {"camera": tmp_path / "camera"}
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", lanes)
    target = lanes["camera"] / "fixture.jpg"
    target.parent.mkdir(parents=True)
    body = b"retained fixture"
    target.write_bytes(body)
    real_sync = os.fsync

    def fail(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode) is fail_directory:
            raise OSError("synthetic sync failure")
        real_sync(fd)

    monkeypatch.setattr(uploads_mod.os, "fsync", fail)
    status, result = uploads_mod.store_upload("camera", "fixture.jpg", body, None)
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR and result["ok"] is False
    assert target.read_bytes() == body
    monkeypatch.setattr(uploads_mod.os, "fsync", real_sync)
    status, result = uploads_mod.store_upload("camera", "fixture.jpg", body, None)
    assert status == HTTPStatus.OK and result["duplicate"] is True


def test_changed_upload_during_sync_is_not_acknowledged(monkeypatch, tmp_path):
    lanes = {"camera": tmp_path / "camera"}
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", lanes)
    target = lanes["camera"] / "fixture.jpg"
    target.parent.mkdir(parents=True)
    body = b"retained fixture"
    target.write_bytes(body)
    real_sync = os.fsync

    def change(fd):
        real_sync(fd)
        if stat.S_ISREG(os.fstat(fd).st_mode):
            target.write_bytes(b"replacement fixture")

    monkeypatch.setattr(uploads_mod.os, "fsync", change)
    status, result = uploads_mod.store_upload("camera", "fixture.jpg", body, None)
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR and result["ok"] is False
    assert target.read_bytes() == b"replacement fixture"


def test_repair_sync_failure_preserves_previous_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(uploads_mod, "EVENTS_DIR", tmp_path)
    target = tmp_path / "events-20200101.jsonl"
    previous = b"old fixture\n"
    target.write_bytes(previous)
    source = tmp_path / "source.jsonl"
    source.write_bytes(b"{}\n")
    real_sync = os.fsync

    def fail_directory(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("synthetic directory sync failure")
        real_sync(fd)

    monkeypatch.setattr(uploads_mod.os, "fsync", fail_directory)
    with pytest.raises(OSError):
        uploads_mod.repair_event_day("20200101", source, hashlib.sha256(previous).hexdigest())
    assert target.read_bytes() == previous and source.read_bytes() == b"{}\n"
    assert next((tmp_path / ".repairs").iterdir()).read_bytes() == previous
