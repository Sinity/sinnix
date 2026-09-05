"""One UTC grammar in the records these two runners write.

The experiment manifest is the join key between a workload window and machine
telemetry, and Lynchpin reads it out of ``/realm/data/machine/experiments``
long after the run. Both runners emit ``%Y-%m-%dT%H:%M:%SZ`` -- the same
string ``sinnix_lib.ledger.utc_ts`` produces -- so a manifest, a boot-metric
index row and a ledger receipt compare as text without a per-producer parser.

The suite drives the real scripts: a runner that goes back to a local
``datetime.now(...).isoformat()`` writes an offset suffix and fails here.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[3]
EXPERIMENT_RUN = ROOT / "scripts" / "machine-experiment-run"
SYSLOG_INDEX = ROOT / "scripts" / "syslog-index"

UTC_TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

# The manifest's run_id is a directory name, not a joinable stamp: it is the
# compact form and stays that way.
RUN_ID = re.compile(r"\d{8}T\d{6}Z-[^-]+-[0-9a-f]{8}")


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, env=dict(os.environ), capture_output=True, text=True, timeout=120
    )


def test_experiment_manifest_stamps_one_utc_grammar(tmp_path: Path) -> None:
    root = tmp_path / "experiments"
    result = _run(
        [
            str(EXPERIMENT_RUN),
            "--root",
            str(root),
            "--workload",
            "grammar",
            "--",
            "true",
        ]
    )
    assert result.returncode == 0, result.stderr

    manifests = sorted(root.glob("*/manifest.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text())

    assert UTC_TS.fullmatch(manifest["started_at"])
    assert UTC_TS.fullmatch(manifest["ended_at"])
    assert RUN_ID.fullmatch(manifest["run_id"])

    started = json.loads((manifests[0].parent / "started.json").read_text())
    assert UTC_TS.fullmatch(started["started_at"])


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
