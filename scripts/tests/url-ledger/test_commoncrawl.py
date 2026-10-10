import argparse
import gzip
import importlib.machinery
import importlib.util
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[3] / "scripts" / "sinnix-url-ledger"
loader = importlib.machinery.SourceFileLoader("url_ledger_under_test", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
ledger = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ledger
loader.exec_module(ledger)


@pytest.mark.parametrize("directory", ["derived", "owner's derived"])
def test_local_build_accepts_quoted_artifact_paths(tmp_path, directory):
    """Real DuckDB must read and publish all artifacts at the chosen path."""
    state = tmp_path / "state"
    state.mkdir()
    url = "https://example.invalid/fixture"
    (state / "urls.jsonl").write_text(
        json.dumps(
            {
                "url": url,
                "visits": ["2026-01-01T00:00:00Z"],
                "visit_count": 1,
            }
        )
        + "\n"
    )
    derived = tmp_path / directory
    duckdb = shutil.which("duckdb")
    assert duckdb is not None
    args = argparse.Namespace(
        state_root=str(state),
        derived_root=str(derived),
        window_days=7,
        duckdb_bin=duckdb,
    )
    assert ledger.cmd_build(args) == 0
    stats = json.loads((derived / "coverage_stats.json").read_text())
    assert stats[0]["urls"] == 1
    literal = "'" + str(derived / "url_ledger.parquet").replace("'", "''") + "'"
    result = subprocess.run(
        [duckdb, "-json", "-c", f"SELECT normalized_url FROM read_parquet({literal})"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == [{"normalized_url": url}]


@pytest.mark.parametrize(
    "url",
    [
        "https://example.invalid/",
        "https://example.invalid/page",
        "https://example.invalid/page?item=1",
    ],
)
def test_query_uses_exact_key_in_shared_block(monkeypatch, url):
    provider = ledger.CommonCrawlProvider(collection_count=1)
    key = provider._surt(url)
    rows = [
        (key, "20260101000000", {"url": url}),
        (key + "extra", "20260202000000", {"url": url + "extra"}),
        (key + "/child", "20260303000000", {"url": url + "/child"}),
        (key, "20260404000000", {"url": url}),
    ]
    block = gzip.compress(
        "\n".join(
            f"{k} {timestamp} {json.dumps(payload)}" for k, timestamp, payload in rows
        ).encode()
    )
    monkeypatch.setattr(provider, "_load_collections", lambda: ["CC-TEST"])
    monkeypatch.setattr(provider, "_cluster_index", lambda _: Path("synthetic.idx"))
    monkeypatch.setattr(
        provider, "_blocks_for", lambda *_: [("synthetic.gz", 0, len(block))]
    )
    monkeypatch.setattr(
        ledger.urllib.request, "urlopen", lambda *_a, **_kw: io.BytesIO(block)
    )

    result = provider.query(url)
    assert result.status == "ok"
    assert result.snapshots == ["20260101000000", "20260404000000"]
    assert result.raw == [{"url": url}, {"url": url}]


def test_shared_prefix_without_exact_capture_is_empty(monkeypatch):
    provider = ledger.CommonCrawlProvider(collection_count=1)
    url = "https://example.invalid/page"
    key = provider._surt(url)
    block = gzip.compress(f'{key}extra 20260101000000 {{"url":"neighbor"}}\n'.encode())
    monkeypatch.setattr(provider, "_load_collections", lambda: ["CC-TEST"])
    monkeypatch.setattr(provider, "_cluster_index", lambda _: Path("synthetic.idx"))
    monkeypatch.setattr(
        provider, "_blocks_for", lambda *_: [("synthetic.gz", 0, len(block))]
    )
    monkeypatch.setattr(
        ledger.urllib.request, "urlopen", lambda *_a, **_kw: io.BytesIO(block)
    )

    result = provider.query(url)
    assert result.status == "ok"
    assert result.snapshots == []
    assert result.raw == []


@pytest.mark.parametrize("padding", [0, 300])
def test_query_keeps_captures_spanning_index_blocks(monkeypatch, tmp_path, padding):
    provider = ledger.CommonCrawlProvider(collection_count=1)
    url = "https://example.invalid/page"
    key = provider._surt(url)
    chunks = {}
    index = [
        f"invalid,example)/a{i:04} 20260101000000\tunused.gz\t0\t20\n"
        for i in range(padding)
    ]
    for number, start_key in enumerate([key[:-1], key, key]):
        timestamp = f"2026010{number + 1}000000"
        block = gzip.compress(f'{key} {timestamp} {{"part":{number}}}\n'.encode())
        offset = number * 1000
        chunks[f"bytes={offset}-{offset + len(block) - 1}"] = block
        index.append(f"{start_key} {timestamp}\tsynthetic.gz\t{offset}\t{len(block)}\n")
    index.append(f"{key}z 20260104000000\tsynthetic.gz\t9999\t20\n")
    index.extend(
        f"invalid,example)/z{i:04} 20260101000000\tunused.gz\t0\t20\n"
        for i in range(padding)
    )
    cluster = tmp_path / "cluster.idx"
    cluster.write_text("".join(index))
    monkeypatch.setattr(provider, "_load_collections", lambda: ["CC-TEST"])
    monkeypatch.setattr(provider, "_cluster_index", lambda _: cluster)
    monkeypatch.setattr(
        ledger.urllib.request,
        "urlopen",
        lambda request, **_kw: io.BytesIO(chunks[request.get_header("Range")]),
    )

    result = provider.query(url)
    assert result.snapshots == ["20260101000000", "20260102000000", "20260103000000"]
    assert result.raw == [{"part": 0}, {"part": 1}, {"part": 2}]


@pytest.mark.parametrize(
    "entry",
    [
        "",
        "invalid,example)/page\n",
        "invalid,example)/page\tx.gz\tbad\t10\n",
        "invalid,example)/page\tx.gz\t-1\t10\n",
        "invalid,example)/page\tx.gz\t0\t0\n",
    ],
)
def test_invalid_index_is_error_not_zero_captures(monkeypatch, tmp_path, entry):
    provider = ledger.CommonCrawlProvider(collection_count=1)
    cluster = tmp_path / "cluster.idx"
    cluster.write_text(entry)
    monkeypatch.setattr(provider, "_load_collections", lambda: ["CC-TEST"])
    monkeypatch.setattr(provider, "_cluster_index", lambda _: cluster)

    def unexpected_request(*_a, **_kw):
        pytest.fail("invalid index must not issue a block request")

    monkeypatch.setattr(ledger.urllib.request, "urlopen", unexpected_request)
    result = provider.query("https://example.invalid/page")
    assert result.status == "error"
    assert result.error
