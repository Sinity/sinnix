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
from http import HTTPStatus

import pytest
import sinnix_phone_dispatcher.uploads as uploads_mod


def _lanes(tmp_path):
    return {"ambient": tmp_path / "ambient"}


def test_sha_mismatch_does_not_land_the_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", _lanes(tmp_path))
    body = b"chunk bytes"

    status, payload = uploads_mod.store_upload("ambient", "clip.m4a", body, "0" * 64)

    assert status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert payload["ok"] is False
    assert not (tmp_path / "ambient" / "clip.m4a").exists()


def test_correct_sha_lands_the_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", _lanes(tmp_path))
    body = b"chunk bytes"
    digest = hashlib.sha256(body).hexdigest()

    status, payload = uploads_mod.store_upload("ambient", "clip.m4a", body, digest)

    assert status == HTTPStatus.OK
    assert payload["ok"] is True
    assert payload["duplicate"] is False
    assert (tmp_path / "ambient" / "clip.m4a").read_bytes() == body


def test_reuploading_the_identical_chunk_is_a_success_duplicate(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", _lanes(tmp_path))
    body = b"chunk bytes"
    digest = hashlib.sha256(body).hexdigest()
    uploads_mod.store_upload("ambient", "clip.m4a", body, digest)

    status, payload = uploads_mod.store_upload("ambient", "clip.m4a", body, digest)

    assert status == HTTPStatus.OK
    assert payload["duplicate"] is True


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
    ],
)
def test_a_traversing_path_is_rejected(monkeypatch, tmp_path, name) -> None:
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", {"camera": tmp_path / "camera"})

    status, payload = uploads_mod.store_upload("camera", name, b"x", None)

    assert status == HTTPStatus.BAD_REQUEST
    assert payload["ok"] is False
    assert not (tmp_path / "escape.jpg").exists()


def test_newest_in_lane_reports_the_watermark(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", {"camera": tmp_path / "camera"})
    nested = tmp_path / "camera" / "Camera"
    nested.mkdir(parents=True)
    (nested / "old.jpg").write_bytes(b"old")
    os.utime(nested / "old.jpg", (1_000_000, 1_000_000))
    (nested / "new.jpg").write_bytes(b"new")
    os.utime(nested / "new.jpg", (2_000_000, 2_000_000))

    status, payload = uploads_mod.newest_in_lane("camera")

    assert status == HTTPStatus.OK
    assert payload["files"] == 2
    assert payload["newest_mtime_ms"] == 2_000_000_000


def test_newest_in_an_unknown_lane_is_a_404() -> None:
    assert uploads_mod.newest_in_lane("nope")[0] == HTTPStatus.NOT_FOUND
