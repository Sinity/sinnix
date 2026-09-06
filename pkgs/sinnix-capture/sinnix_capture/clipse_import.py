"""One-shot import of a clipse history into a selection lane.

clipse keeps ``clipboard_history.json`` (``{"clipboardHistory": [...]}``,
newest first, each item ``value``/``recorded``/``filePath``/``pinned``) and
copies image payloads into ``tmp_files/``. Every item becomes one
sinnix-capture-v1 record with the same payload shape the live lane writes,
stamped with the item's own recorded time and ``"source": "clipse-import"``,
so consumers can tell imported history from live capture without a second
schema. Text goes inline, images into the content-addressed blob store.
Image files no history item references are imported too, dated by their
mtime and marked ``orphan``.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from .selection import store_blob
from .writer import CaptureWriter

SOURCE = "clipse-import"
TEXT_MIME = "text/plain;charset=utf-8"
IMAGE_MIME = "image/png"


@dataclass
class ImportReport:
    text: int = 0
    images: int = 0
    orphan_images: int = 0
    skipped: int = 0


def parse_recorded(value: str) -> float:
    """clipse timestamps are naive local time with nanosecond fractions."""
    head, _, fraction = value.partition(".")
    base = time.mktime(time.strptime(head, "%Y-%m-%d %H:%M:%S"))
    if fraction:
        base += float("0." + fraction[:9])
    return base


def _image_payload(content: bytes, digest: str, **extra: object) -> dict:
    return {
        "category": "binary",
        "mime": IMAGE_MIME,
        "sha256": digest,
        "size": len(content),
        "source_window": {"class": None, "title": None},
        "source": SOURCE,
        **extra,
    }


def import_clipse(
    *,
    capture_root: Path,
    lane: str,
    history_path: Path,
    tmp_files: Path | None = None,
) -> ImportReport:
    history = json.loads(history_path.read_text(encoding="utf-8"))
    items = history.get("clipboardHistory") if isinstance(history, dict) else history
    if not isinstance(items, list):
        raise ValueError("clipse history has no clipboardHistory list")
    writer = CaptureWriter(capture_root, lane)
    lane_dir = Path(capture_root) / lane
    report = ImportReport()
    referenced: set[Path] = set()

    # Oldest first so sequence numbers follow recorded time.
    for item in sorted(items, key=lambda entry: str(entry.get("recorded", ""))):
        try:
            ts = parse_recorded(str(item["recorded"]))
        except (KeyError, ValueError):
            report.skipped += 1
            continue
        file_path = item.get("filePath")
        pinned = bool(item.get("pinned", False))
        if file_path and file_path != "null":
            image = Path(file_path)
            try:
                content = image.read_bytes()
            except OSError:
                report.skipped += 1
                continue
            referenced.add(image.resolve())
            digest = hashlib.sha256(content).hexdigest()
            raw_ref = str(store_blob(lane_dir, content, digest))
            writer.write(
                _image_payload(content, digest, pinned=pinned, original_path=str(image)),
                raw_ref=raw_ref,
                ts=ts,
            )
            report.images += 1
            continue
        text = item.get("value")
        if not isinstance(text, str):
            report.skipped += 1
            continue
        encoded = text.encode("utf-8")
        writer.write(
            {
                "category": "text",
                "mime": TEXT_MIME,
                "text": text,
                "size": len(encoded),
                "source_window": {"class": None, "title": None},
                "source": SOURCE,
                "pinned": pinned,
            },
            ts=ts,
        )
        report.text += 1

    if tmp_files is not None and tmp_files.is_dir():
        for image in sorted(tmp_files.iterdir()):
            if not image.is_file() or image.resolve() in referenced:
                continue
            content = image.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            raw_ref = str(store_blob(lane_dir, content, digest))
            writer.write(
                _image_payload(content, digest, orphan=True, original_path=str(image)),
                raw_ref=raw_ref,
                ts=image.stat().st_mtime,
            )
            report.orphan_images += 1
    return report
