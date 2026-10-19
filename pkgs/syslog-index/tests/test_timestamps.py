"""syslog-index stamps the estate's one UTC grammar.

Every producer emits ``%Y-%m-%dT%H:%M:%SZ`` -- the same string
``sinnix_lib.ledger.utc_ts`` produces -- so an index row and a ledger receipt
compare as text without a per-producer parser. The suite drives the real
script: going back to a local ``datetime.now(...).isoformat()`` writes an
offset suffix and fails here.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[3]
SYSLOG_INDEX = ROOT / "scripts" / "syslog-index"

UTC_TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, env=dict(os.environ), capture_output=True, text=True, timeout=120
    )


def test_syslog_index_stamps_one_utc_grammar_document_wide(tmp_path: Path) -> None:
    """The index manifest's ``created_at`` and each row's ``mtime`` agree.

    They are read side by side -- "is this row older than the index that
    names it" is a text comparison -- so one grammar covers the document.
    """
    source = tmp_path / "syslog" / "boot-metrics" / "2026-01-01"
    source.mkdir(parents=True)
    (source / "metric.txt").write_text("sample\n")
    output = tmp_path / "index"

    result = _run(
        [
            str(SYSLOG_INDEX),
            "--root",
            str(tmp_path / "syslog"),
            "--output",
            str(output),
        ]
    )
    assert result.returncode == 0, result.stderr

    manifest = json.loads((output / "manifest.json").read_text())
    assert UTC_TS.fullmatch(manifest["created_at"])

    rows = [
        json.loads(line)
        for line in (output / "boot-metrics.jsonl").read_text().splitlines()
    ]
    assert rows
    stamps = [file["mtime"] for row in rows for file in row["files"]]
    assert stamps
    assert [stamp for stamp in stamps if not UTC_TS.fullmatch(stamp)] == []
