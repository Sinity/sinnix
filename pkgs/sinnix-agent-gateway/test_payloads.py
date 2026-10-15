from __future__ import annotations

import hashlib
import json
import tracemalloc

import pytest

from sinnix_agent_gateway import payloads


def test_json_retention_preserves_canonical_bytes_hash_and_deduplication(tmp_path):
    root = tmp_path / "payloads"
    value = {"unicode": "界😀\n", "nested": [True, None, 1.25, {"two": 2}]}
    expected = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    first = payloads.retain_json(root, value)
    inode = first.stat().st_ino
    link = tmp_path / "observation.json"
    second = payloads.retain_json(root, value, link=link)
    assert first == second == root / hashlib.sha256(expected).hexdigest()
    assert first.read_bytes() == link.read_bytes() == expected
    assert first.stat().st_ino == link.stat().st_ino == inode
    assert first.stat().st_mode & 0o777 == 0o600
    assert list(root.iterdir()) == [first]


def test_failed_json_encoding_cannot_publish_partial_payload(tmp_path):
    root = tmp_path / "payloads"
    previous = payloads.retain_json(root, {"kept": True})
    with pytest.raises(TypeError):
        payloads.retain_json(root, ["x" * 64] * 10000 + [object()], link=tmp_path / "partial")
    assert list(root.iterdir()) == [previous]
    assert not (tmp_path / "partial").exists()
    assert json.loads(previous.read_bytes()) == {"kept": True}


def test_failed_atomic_publication_cleans_staging(tmp_path, monkeypatch):
    root = tmp_path / "payloads"
    def fail(*args, **kwargs):
        raise OSError("synthetic publication failure")
    monkeypatch.setattr(payloads, "atomic_publish_at", fail)
    with pytest.raises(OSError, match="synthetic"):
        payloads.retain_json(root, {"rows": ["x"] * 1000})
    assert list(root.iterdir()) == []


def test_large_row_retention_avoids_complete_serialized_copies(tmp_path):
    value = {"rows": ["x" * 64] * 100000}
    tracemalloc.start()
    try:
        retained = payloads.retain_json(tmp_path / "payloads", value)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert retained.stat().st_size == 6700010
    assert peak < 1_000_000
