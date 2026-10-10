import argparse
import gzip
import hashlib
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


@pytest.mark.parametrize(
    "failure", ["input", "sql", "validation", "rows", "publication", "write"]
)
def test_failed_build_preserves_complete_previous_publication(
    tmp_path, failure, monkeypatch
):
    state = tmp_path / "state"
    state.mkdir()
    inputs = state / "urls.jsonl"
    inputs.write_text(
        json.dumps(
            {"url": "https://example.invalid/first", "visits": [], "visit_count": 0}
        )
        + "\n"
    )
    derived = tmp_path / "derived"
    args = argparse.Namespace(
        state_root=str(state),
        derived_root=str(derived),
        window_days=7,
        duckdb_bin=shutil.which("duckdb"),
    )
    assert ledger.cmd_build(args) == 0
    # Bind every prior artifact before injecting a failure into the next build.
    previous = ledger.published_generation(derived)
    pointer = (derived / "current.json").read_bytes()
    before = {p.name: p.read_bytes() for p in previous.iterdir() if p.is_file()}
    if failure == "input":
        inputs.write_text("not JSON\n")
    elif failure == "sql":
        inputs.write_text(
            json.dumps(
                {
                    "url": "https://example.invalid/second",
                    "visits": [],
                    "visit_count": 0,
                }
            )
            + "\n"
        )
        executable = tmp_path / "failed-duckdb"
        executable.write_text("#!/bin/sh\nexit 42\n")
        executable.chmod(0o700)
        args.duckdb_bin = str(executable)
    elif failure in {"validation", "rows"}:
        original = ledger._build_products

        def corrupt(build_args):
            result = original(build_args)
            root = Path(build_args.derived_root)
            if failure == "validation":
                (root / "coverage_stats.json").write_text('[{"urls": 999}]')
            else:
                subprocess.run(
                    [
                        build_args.duckdb_bin,
                        str(root / "url_ledger.duckdb"),
                        "-c",
                        "COPY (SELECT * REPLACE ('https://example.invalid/wrong' AS normalized_url) FROM url_ledger) TO "
                        + ledger.sql_path(root / "url_ledger.parquet")
                        + " (FORMAT PARQUET)",
                    ],
                    check=True,
                    capture_output=True,
                )
            return result

        monkeypatch.setattr(ledger, "_build_products", corrupt)
    elif failure == "publication":
        original = ledger.atomic_publish

        def refuse(path, *args, **kwargs):
            if Path(path).name == "current.json":
                raise OSError("synthetic publication failure")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(ledger, "atomic_publish", refuse)
    elif failure == "write":

        def exhausted(*_args, **_kwargs):
            raise OSError("synthetic exhausted storage")

        monkeypatch.setattr(ledger.shutil, "copyfile", exhausted)
    authored = inputs.read_bytes()
    try:
        result = ledger.cmd_build(args)
    except ValueError:
        result = 1
    assert result != 0
    assert inputs.read_bytes() == authored
    assert {p.name: p.read_bytes() for p in previous.iterdir() if p.is_file()} == before
    assert (derived / "current.json").read_bytes() == pointer


def test_selected_generation_survives_replacement_and_flat_preimages_remain(tmp_path):
    derived = tmp_path / "derived"
    state = derived / "state"
    state.mkdir(parents=True)
    inputs = state / "urls.jsonl"

    def write(url):
        inputs.write_text(
            json.dumps(
                {"url": url, "visits": ["2026-01-01T00:00:00Z"], "visit_count": 1}
            )
            + "\n"
        )

    write("https://example.invalid/first")
    args = argparse.Namespace(
        state_root=str(state),
        derived_root=str(derived),
        window_days=7,
        duckdb_bin=shutil.which("duckdb"),
    )
    assert ledger._build_products(args) == 0
    flat = {name: (derived / name).read_bytes() for name in ledger.PRODUCTS}
    assert ledger.cmd_build(args) == 0
    first = ledger.published_generation(derived)
    for name in ledger.PRODUCTS:
        assert not (derived / name).exists()
        assert (
            list((derived / "history").glob(f"flat-*/{name}"))[0].read_bytes()
            == flat[name]
        )
    write("https://example.invalid/second")
    authored = inputs.read_bytes()
    assert ledger.cmd_build(args) == 0
    second = ledger.published_generation(derived)
    assert first != second
    for path, expected in [(first, "first"), (second, "second")]:
        rows = ledger._query_json(
            args.duckdb_bin,
            path / "url_ledger.duckdb",
            "SELECT normalized_url FROM url_ledger",
        )
        assert rows == [{"normalized_url": f"https://example.invalid/{expected}"}]
        assert (
            json.loads((path / "coverage.jsonl").read_text())["normalized_url"]
            == rows[0]["normalized_url"]
        )
        assert path.stat().st_mode & 0o777 == 0o700
    assert inputs.read_bytes() == authored
    assert (derived / "current.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("pointer", ['{"generation":"../outside"}', "[]", "null"])
def test_reader_refuses_invalid_publication_pointer(tmp_path, pointer):
    (tmp_path / "current.json").write_text(pointer)
    assert ledger.cmd_published(argparse.Namespace(derived_root=str(tmp_path))) != 0


def test_post_commit_durability_failure_keeps_complete_generation(
    tmp_path, monkeypatch, capsys
):
    state = tmp_path / "state"
    state.mkdir()
    (state / "urls.jsonl").write_text(
        json.dumps(
            {
                "url": "https://example.invalid/fixture",
                "visits": [],
                "visit_count": 0,
            }
        )
        + "\n"
    )
    root = tmp_path / "derived"
    args = argparse.Namespace(
        state_root=str(state),
        derived_root=str(root),
        window_days=7,
        duckdb_bin=shutil.which("duckdb"),
    )
    assert ledger.cmd_build(args) == 0
    previous = ledger.published_generation(root)
    before = {p.name: p.read_bytes() for p in previous.iterdir()}
    original = ledger.atomic_publish

    def committed_then_failed(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if Path(path).name == "current.json":
            raise OSError("synthetic directory fsync failure after rename")
        return result

    monkeypatch.setattr(ledger, "atomic_publish", committed_then_failed)
    assert ledger.cmd_build(args) == 0
    current = ledger.published_generation(root)
    assert current != previous
    assert ledger._validate_products(current, args.duckdb_bin) == 1
    assert {p.name: p.read_bytes() for p in previous.iterdir()} == before
    assert (
        "publication committed; durability confirmation failed"
        in capsys.readouterr().err
    )


def test_reader_refuses_valid_digest_with_wrong_manifest_shape(tmp_path):
    name = "a" * 32
    generation = tmp_path / "generations" / name
    generation.mkdir(parents=True)
    payload = b"[]\n"
    (generation / "manifest.json").write_bytes(payload)
    (tmp_path / "current.json").write_text(
        json.dumps(
            {
                "generation": name,
                "manifest_sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    )
    assert ledger.cmd_published(argparse.Namespace(derived_root=str(tmp_path))) == 1


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
    (state / "resolution.jsonl").write_text(
        json.dumps(
            {
                "url": url,
                "provider": "wayback",
                "status": "ok",
                "snapshots": ["2026-01-02T00:00:00Z"],
            }
        )
        + "\n"
    )
    duckdb = shutil.which("duckdb")
    assert duckdb is not None
    args = argparse.Namespace(
        state_root=str(state),
        derived_root=str(derived),
        window_days=7,
        duckdb_bin=duckdb,
    )
    assert ledger.cmd_build(args) == 0
    derived = ledger.published_generation(derived)
    stats = json.loads((derived / "coverage_stats.json").read_text())
    assert stats[0]["urls"] == 1
    assert stats[0]["visits_with_snapshot_within_window"] == 1
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
