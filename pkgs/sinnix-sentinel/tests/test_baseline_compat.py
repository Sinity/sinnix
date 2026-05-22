"""Wire-format compatibility tests for the baselines.json round-trip.

The bash sentinel writes baselines as ``{key: [str, ...]}`` via ``jq``.
These tests guard the Python reader/writer against drift: a bash-produced
file must load identically, and writing it back must preserve the shape
(string-typed samples, jq-compatible) so the live bash sentinel can read
it on the next tick without crashing.
"""

from __future__ import annotations

import json
from pathlib import Path

from sinnix_sentinel.baseline import (
    DEFAULT_MAX_SAMPLES,
    baseline_append,
    read_baselines,
    write_baselines,
)

FIXTURE = Path(__file__).parent / "fixtures" / "baselines_sample.json"


def test_reads_bash_produced_fixture(tmp_path):
    target = tmp_path / "baselines.json"
    target.write_bytes(FIXTURE.read_bytes())

    data = read_baselines(target)

    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    # Same keys, same length series, samples preserved as strings.
    assert set(data.keys()) == set(raw.keys())
    for k, samples in raw.items():
        assert data[k] == [str(s) for s in samples]
        assert all(isinstance(s, str) for s in data[k])


def test_round_trip_preserves_shape(tmp_path):
    target = tmp_path / "baselines.json"
    target.write_bytes(FIXTURE.read_bytes())

    data = read_baselines(target)
    write_baselines(data, target)

    reloaded = json.loads(target.read_text(encoding="utf-8"))
    original = json.loads(FIXTURE.read_text(encoding="utf-8"))
    # Same keys; same string samples.
    assert reloaded == original


def test_write_uses_string_samples_and_compact_json(tmp_path):
    target = tmp_path / "baselines.json"
    write_baselines({"mem_avail_gb": ["50", "49"]}, target)
    text = target.read_text(encoding="utf-8")
    # Compact (no spaces) and trailing newline (matches bash printf '%s\n').
    assert text.endswith("\n")
    assert " " not in text.replace("\n", "")
    payload = json.loads(text)
    assert payload == {"mem_avail_gb": ["50", "49"]}
    assert all(isinstance(s, str) for s in payload["mem_avail_gb"])


def test_baseline_append_trims_to_max_samples(tmp_path):
    target = tmp_path / "baselines.json"
    write_baselines({"k": [str(i) for i in range(DEFAULT_MAX_SAMPLES)]}, target)
    baseline_append("k", 999, path=target)
    data = read_baselines(target)
    assert len(data["k"]) == DEFAULT_MAX_SAMPLES
    assert data["k"][-1] == "999"
    assert data["k"][0] == "1"  # oldest dropped


def test_missing_file_returns_empty(tmp_path):
    target = tmp_path / "absent.json"
    assert read_baselines(target) == {}


def test_corrupt_file_returns_empty(tmp_path):
    target = tmp_path / "corrupt.json"
    target.write_text("not json {{{", encoding="utf-8")
    assert read_baselines(target) == {}


def test_append_then_bash_compatible(tmp_path):
    """After Python append, a jq-like read (json.loads) returns string samples."""
    target = tmp_path / "baselines.json"
    baseline_append("mem_avail_gb", 50, path=target)
    baseline_append("mem_avail_gb", 49, path=target)
    raw = json.loads(target.read_text(encoding="utf-8"))
    assert raw["mem_avail_gb"] == ["50", "49"]
