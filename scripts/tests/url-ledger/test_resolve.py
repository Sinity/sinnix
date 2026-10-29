"""Resolver checkpoint replay and provider sequencing, with no network access."""

import argparse
import hashlib
import json
from types import SimpleNamespace

import pytest
from test_commoncrawl import ledger

URL = "https://example.invalid/first"
OTHER = "https://example.invalid/second"


def checkpoint(tmp_path, records):
    state = tmp_path / "state"
    state.mkdir()
    path = state / "resolution.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in records) + "\n")
    return state, path


def fake_run(
    tmp_path,
    monkeypatch,
    state,
    urls,
    *,
    refresh=False,
    max_requests=100,
    max_seconds=0,
    query_seconds=0,
):
    (state / "urls.jsonl").write_text(
        "".join(json.dumps({"url": url}) + "\n" for url in urls)
    )
    calls, waits = [], []
    clock = [0.0]
    beta_statuses = iter(["error", "unavailable", "ok"])

    class Provider:
        default_delay_seconds = 99

        def __init__(self, name):
            self.name = name

        def query(self, url):
            calls.append((self.name, url))
            clock[0] += query_seconds
            status = next(beta_statuses) if self.name == "beta" else "ok"
            return ledger.ProviderResult(
                status=status,
                snapshots=["2025-01-01T00:00:00Z"],
                raw={"synthetic": self.name},
                error="synthetic retry" if status == "error" else None,
            )

    class Limiter:
        def __init__(self, delay):
            self.delay = delay

        def wait(self):
            waits.append(self.delay)

    monkeypatch.setattr(
        ledger,
        "PROVIDERS",
        {name: (lambda name=name: Provider(name)) for name in ["alpha", "beta"]},
    )
    monkeypatch.setattr(ledger, "RateLimiter", Limiter)
    monkeypatch.setattr(
        ledger, "http_get", lambda *_a, **_k: pytest.fail("network forbidden")
    )
    monkeypatch.setattr(
        ledger,
        "time",
        SimpleNamespace(
            monotonic=lambda: clock[0],
            gmtime=lambda: None,
            strftime=lambda fmt, *_: (
                "2026-01-01" if fmt == "%Y-%m-%d" else "2026-01-01T00:00:00Z"
            ),
        ),
    )
    args = argparse.Namespace(
        state_root=str(state),
        cdx_raw_root=str(tmp_path / "raw"),
        provider=["alpha", "beta"],
        common_crawl_collections=3,
        memento_base_url="https://example.invalid/memento",
        rate_limit_seconds={"alpha": 0.1, "beta": 0.2},
        max_seconds=max_seconds,
        max_requests=max_requests,
        refresh=refresh,
    )
    return args, calls, waits


@pytest.mark.parametrize(
    "statuses,expected",
    [
        (["ok", "error"], "error"),
        (["error", "ok"], "ok"),
        (["unavailable", "unknown"], "unknown"),
        (["unknown", "unavailable"], "unavailable"),
    ],
)
def test_status_view_replays_latest_record_without_response_payload(
    tmp_path, statuses, expected
):
    records = [
        {
            "url": URL,
            "provider": "alpha",
            "status": status,
            "snapshots": ["2025-01-01T00:00:00Z"],
            "raw_cache": "synthetic",
        }
        for status in statuses
    ]
    state, path = checkpoint(tmp_path, records)
    path.write_text("\nmalformed JSON\n" + path.read_text())
    assert ledger.load_resolution_statuses(state) == {(URL, "alpha"): expected}
    assert ledger.load_resolution_state(state)[(URL, "alpha")] == records[-1]


@pytest.mark.parametrize(
    "refresh,expected",
    [
        (False, [("beta", URL), ("beta", URL), ("alpha", OTHER)]),
        (True, [("alpha", URL), ("beta", URL), ("alpha", URL)]),
    ],
)
def test_duplicates_refresh_budget_rates_and_complete_append_are_preserved(
    tmp_path, monkeypatch, refresh, expected
):
    state, path = checkpoint(
        tmp_path,
        [
            {"url": URL, "provider": "alpha", "status": "error"},
            {"url": URL, "provider": "alpha", "status": "ok", "snapshots": ["old"]},
        ],
    )
    before = path.read_bytes()
    args, calls, waits = fake_run(
        tmp_path, monkeypatch, state, [URL, URL, OTHER], refresh=refresh, max_requests=3
    )
    assert ledger.cmd_resolve(args) == 0
    assert calls == expected
    assert waits == [0.1 if name == "alpha" else 0.2 for name, _ in expected]
    assert path.read_bytes().startswith(before)
    appended = [
        json.loads(line) for line in path.read_bytes()[len(before) :].splitlines()
    ]
    beta_statuses = iter(["error", "unavailable"])
    for row, (name, url) in zip(appended, expected, strict=True):
        status = next(beta_statuses) if name == "beta" else "ok"
        relative = (
            f"2026-01-01/{name}/{hashlib.sha256(url.encode()).hexdigest()[:16]}.json"
        )
        assert row == {
            "url": url,
            "provider": name,
            "status": status,
            "snapshot_count": 1,
            "snapshots": ["2025-01-01T00:00:00Z"],
            "queried_at": "2026-01-01T00:00:00Z",
            "raw_cache": relative,
            "error": "synthetic retry" if status == "error" else None,
        }
        assert json.loads((tmp_path / "raw" / relative).read_text()) == {
            "url": url,
            "provider": name,
            "raw": {"synthetic": name},
        }


def test_latest_terminal_to_error_retries_then_terminal_duplicate_skips(
    tmp_path, monkeypatch
):
    state, path = checkpoint(
        tmp_path,
        [
            {"url": URL, "provider": "alpha", "status": "ok"},
            {"url": URL, "provider": "alpha", "status": "error"},
            {"url": URL, "provider": "beta", "status": "unavailable"},
        ],
    )
    before = path.read_bytes()
    args, calls, waits = fake_run(tmp_path, monkeypatch, state, [URL, URL])
    assert ledger.cmd_resolve(args) == 0
    assert calls == [("alpha", URL)]
    assert waits == [0.1]
    assert len(path.read_bytes()[len(before) :].splitlines()) == 1


@pytest.mark.parametrize("refresh", [False, True])
@pytest.mark.parametrize("bad_status", [[], {}])
def test_unhashable_status_is_only_rejected_when_its_key_is_queried(
    tmp_path, monkeypatch, refresh, bad_status
):
    state, path = checkpoint(
        tmp_path,
        [
            {"url": OTHER, "provider": "alpha", "status": bad_status},
            {"url": URL, "provider": "alpha", "status": "ok"},
            {"url": URL, "provider": "beta", "status": "unavailable"},
        ],
    )
    assert ledger.load_resolution_statuses(state)[(OTHER, "alpha")] == bad_status
    args, calls, _ = fake_run(tmp_path, monkeypatch, state, [URL], refresh=refresh)
    assert ledger.cmd_resolve(args) == 0
    # Re-select the malformed key. Membership must still precede --refresh,
    # including falsy list/dict statuses.
    (state / "urls.jsonl").write_text(json.dumps({"url": OTHER}) + "\n")
    previous_calls = list(calls)
    with pytest.raises(TypeError, match="unhashable"):
        ledger.cmd_resolve(args)
    assert calls == previous_calls


@pytest.mark.parametrize("record", [None, [], 3])
def test_nonobject_checkpoint_records_keep_existing_rejection(tmp_path, record):
    state, _ = checkpoint(tmp_path, [record])
    for load in [ledger.load_resolution_state, ledger.load_resolution_statuses]:
        with pytest.raises(AttributeError):
            load(state)


def test_time_budget_stops_at_same_provider_boundary(tmp_path, monkeypatch, capsys):
    state, path = checkpoint(tmp_path, [])
    before = path.read_bytes()
    args, calls, waits = fake_run(
        tmp_path, monkeypatch, state, [URL, OTHER], max_seconds=5, query_seconds=4
    )
    assert ledger.cmd_resolve(args) == 0
    assert calls == [("alpha", URL), ("beta", URL)]
    assert waits == [0.1, 0.2]
    assert path.read_bytes().startswith(before)
    assert len(path.read_bytes()[len(before) :].splitlines()) == 2
    assert "stopped on time budget (5s)" in capsys.readouterr().out
