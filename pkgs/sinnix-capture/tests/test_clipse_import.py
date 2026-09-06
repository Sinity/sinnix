"""clipse import: every history item becomes a lane record with its own
recorded time and explicit provenance; images land in the blob store."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from sinnix_capture.cli import main


def _records(root: Path, lane: str) -> list[dict]:
    rows = []
    for path in sorted((root / lane).glob(f"{lane}-*.jsonl")):
        if path.name == f"{lane}-index.jsonl":
            continue
        rows += [json.loads(line) for line in path.read_text().splitlines() if line]
    return sorted(rows, key=lambda r: r["seq"])


def test_import_clipse_text_images_and_orphans(tmp_path: Path) -> None:
    tmp_files = tmp_path / "tmp_files"
    tmp_files.mkdir()
    png = b"\x89PNG fake"
    (tmp_files / "1-1.png").write_bytes(png)
    orphan = b"\x89PNG orphan"
    (tmp_files / "2-2.png").write_bytes(orphan)
    os.utime(tmp_files / "2-2.png", (1_700_000_000, 1_700_000_000))
    history = tmp_path / "clipboard_history.json"
    history.write_text(json.dumps({"clipboardHistory": [
        {"value": "newer", "recorded": "2026-09-06 20:35:08.131643087", "filePath": "null", "pinned": False},
        {"value": "\U0001f4f7 1-1.png", "recorded": "2026-09-04 10:15:20.211316017",
         "filePath": str(tmp_files / "1-1.png"), "pinned": True},
        {"value": "older", "recorded": "2026-02-01 20:32:19.722087027", "filePath": "null", "pinned": False},
    ]}))
    root = tmp_path / "root"

    assert main([
        "import-clipse", "--capture-root", str(root), "--lane", "clipboard",
        "--history", str(history), "--tmp-files", str(tmp_files),
    ]) == 0

    rows = _records(root, "clipboard")
    assert [r["payload"].get("text", r["payload"]["category"]) for r in rows] == [
        "older", "binary", "newer", "binary",
    ]
    assert all(r["payload"]["source"] == "clipse-import" for r in rows)
    assert rows[0]["ts"] < rows[1]["ts"] < rows[2]["ts"]
    assert rows[0]["schema"] == "sinnix-capture-v1"
    image = rows[1]
    assert image["payload"]["sha256"] == hashlib.sha256(png).hexdigest()
    assert image["payload"]["pinned"] is True
    assert Path(image["raw_ref"]).read_bytes() == png
    assert rows[3]["payload"]["orphan"] is True
    assert Path(rows[3]["raw_ref"]).read_bytes() == orphan
    # Records are filed under their recorded day, not the import day.
    assert (root / "clipboard" / "clipboard-20260201.jsonl").exists()
    index = [json.loads(l) for l in (root / "clipboard" / "clipboard-index.jsonl").read_text().splitlines()]
    assert [e["seq"] for e in index] == [1, 2, 3, 4]
