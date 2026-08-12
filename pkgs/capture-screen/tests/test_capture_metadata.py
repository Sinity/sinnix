from __future__ import annotations

import io

from PIL import Image

from sinnix_capture_screen.capture import (
    build_frame_payload,
    encode_webp,
    frame_filename,
    image_to_phash_array,
)


def test_build_frame_payload_matches_bead_schema() -> None:
    payload = build_frame_payload(
        ts=1723459200.123,
        window_class="kitty",
        window_title="sinex",
        workspace="1",
        geometry={"x": 0, "y": 0, "width": 1920, "height": 1080},
        monitor="DP-3",
        sha256="deadbeef",
        trigger="hyprland-event",
    )
    # sinnix-9pd 3.2: {ts, window_class, window_title, workspace, geometry,
    # monitor, sha256} -- every required field present with the right value.
    assert payload["ts"] == 1723459200.123
    assert payload["window_class"] == "kitty"
    assert payload["window_title"] == "sinex"
    assert payload["workspace"] == "1"
    assert payload["geometry"] == {"x": 0, "y": 0, "width": 1920, "height": 1080}
    assert payload["monitor"] == "DP-3"
    assert payload["sha256"] == "deadbeef"
    assert payload["trigger"] == "hyprland-event"


def test_frame_filename_is_sortable_and_slugified() -> None:
    name = frame_filename(1723459200.5, "org.qutebrowser.qutebrowser", 7)
    assert name.startswith("1723459200.500-7-")
    assert name.endswith(".webp")
    assert " " not in name
    assert "/" not in name


def test_frame_filename_falls_back_to_unknown_for_missing_class() -> None:
    name = frame_filename(1.0, None, 1)
    assert "unknown" in name


def test_encode_webp_resizes_when_wider_than_max_width() -> None:
    im = Image.new("RGB", (3840, 2160), color=(10, 20, 30))
    webp_bytes = encode_webp(im, max_width=1920, quality=80)
    decoded = Image.open(io.BytesIO(webp_bytes))
    assert decoded.width == 1920
    assert decoded.height == 1080  # aspect ratio preserved


def test_encode_webp_leaves_narrower_images_untouched() -> None:
    im = Image.new("RGB", (800, 600), color=(1, 2, 3))
    webp_bytes = encode_webp(im, max_width=1920, quality=80)
    decoded = Image.open(io.BytesIO(webp_bytes))
    assert (decoded.width, decoded.height) == (800, 600)


def test_encode_webp_produces_actual_webp_bytes() -> None:
    im = Image.new("RGB", (16, 16), color=(255, 0, 0))
    webp_bytes = encode_webp(im)
    assert webp_bytes[:4] == b"RIFF"
    assert webp_bytes[8:12] == b"WEBP"


def test_image_to_phash_array_is_square_and_matches_requested_size() -> None:
    im = Image.new("RGB", (1920, 1080), color=(50, 100, 150))
    arr = image_to_phash_array(im, size=32)
    assert arr.shape == (32, 32)
