"""Frame grab (grim), WebP encoding, phash-array glue, and metadata/JSONL
payload shape.

See daemon.py's module docstring for why this shells out to `grim` rather
than driving Noctalia's own screenshot IPC or a hyprland-toplevel-export
client. `capture_frame_bytes`/`encode_webp`/`write_frame` are thin IO
wrappers; `build_frame_payload` and `frame_filename` are pure and
pytest-covered directly.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

PHASH_IMAGE_SIZE = 32  # hash_size(8) * high_freq_factor(4), see hashing.phash64


def run_grim(
    grim_bin: str, monitor: str, geometry: str | None, *, timeout: float = 5.0
) -> tuple[bytes | None, str | None]:
    """Capture one PNG frame to stdout via grim (wlr-screencopy protocol).

    `geometry`, when given, is a grim `-g "X,Y WxH"`-style string cropping
    to a single window's bounding box -- the per-window framing mechanism
    (3.1) in the absence of a hyprland-toplevel-export protocol on this
    Hyprland version. grim rejects `-o` together with `-g` ("-o and -g are
    mutually exclusive"), and `-g` is already in the global compositor
    coordinate space Hyprland's `at`/`size` report, so a geometry crop
    replaces the output selector rather than narrowing it.

    Returns `(png_bytes, None)` on success and `(None, reason)` on failure,
    where `reason` carries grim's own stderr. Callers MUST log the reason:
    swallowing it is what let the `-o`/`-g` conflict above degrade this
    lane silently for its entire deployed lifetime."""
    if geometry:
        cmd = [grim_bin, "-g", geometry, "-"]
    else:
        cmd = [grim_bin, "-o", monitor, "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout, check=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", "replace").strip()
        return None, f"exit {exc.returncode}: {stderr or '(no stderr)'}"
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s"
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not proc.stdout:
        return None, "grim produced no output"
    return proc.stdout, None


def load_image(png_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png_bytes)).convert("RGB")


def image_to_phash_array(im: Image.Image, size: int = PHASH_IMAGE_SIZE) -> np.ndarray:
    gray = im.convert("L").resize((size, size), Image.LANCZOS)
    return np.asarray(gray, dtype=np.float64)


def encode_webp(im: Image.Image, *, max_width: int = 1920, quality: int = 80) -> bytes:
    if im.width > max_width:
        new_height = max(1, round(im.height * (max_width / im.width)))
        im = im.resize((max_width, new_height), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="WEBP", quality=quality)
    return buf.getvalue()


def frame_filename(ts: float, window_class: str | None, seq: int) -> str:
    """Deterministic, sortable frame filename: `<ts>-<seq>-<class-slug>.webp`."""
    slug = "".join(
        c if (c.isalnum() or c in "-_") else "-" for c in (window_class or "unknown")
    ).strip("-")
    slug = slug[:40] or "unknown"
    return f"{ts:.3f}-{seq}-{slug}.webp"


def build_frame_payload(
    *,
    ts: float,
    window_class: str | None,
    window_title: str | None,
    workspace: str | None,
    geometry: dict[str, Any],
    monitor: str | None,
    sha256: str,
    trigger: str,
) -> dict[str, Any]:
    """The exact metadata shape from sinnix-9pd 3.2: {ts, window_class,
    window_title, workspace, geometry, monitor, sha256} plus `trigger`
    (which of the three trigger classes fired this capture -- not required
    by the bead but cheap and useful for later analysis)."""
    return {
        "ts": ts,
        "window_class": window_class,
        "window_title": window_title,
        "workspace": workspace,
        "geometry": geometry,
        "monitor": monitor,
        "sha256": sha256,
        "trigger": trigger,
    }


def write_frame(
    *,
    payload: dict[str, Any],
    webp_bytes: bytes,
    capture_root: Path,
    lane: str,
    sinnix_capture_bin: str,
    filename: str,
) -> Path | None:
    """Persist the WebP frame under `{capture_root}/{lane}/frames/` and
    record its metadata envelope via `sinnix-capture write --raw-ref
    <frame_path>` (the shared JSONL envelope writer every capture lane
    uses). Returns the frame path on success, None if the writer failed
    (logged to stderr, never silently dropped)."""
    frames_dir = capture_root / lane / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frame_path = frames_dir / filename
    frame_path.write_bytes(webp_bytes)
    proc = subprocess.run(
        [
            sinnix_capture_bin,
            "write",
            "--capture-root",
            str(capture_root),
            "--lane",
            lane,
            "--raw-ref",
            str(frame_path),
        ],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        print(
            f"sinnix-capture-screen: write failed (exit {proc.returncode}): {proc.stderr.strip()}",
            file=sys.stderr,
        )
        return None
    return frame_path
