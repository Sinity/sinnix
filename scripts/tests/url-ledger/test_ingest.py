import argparse
import json
import os

import pytest

from test_commoncrawl import ledger


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://[2001:db8::1]/path", "http://[2001:db8::1]/path"),
        ("https://[2001:DB8::1]:443/path#fragment", "https://[2001:db8::1]/path"),
        ("https://[2001:db8::1]:8443/path", "https://[2001:db8::1]:8443/path"),
        ("http://[::1]:80/", "http://[::1]/"),
        ("https://example.invalid:invalid/path", None),
        ("https://example.invalid:65536/path", None),
        ("https://[2001:db8::1]:invalid/path", None),
    ],
)
def test_normalization_keeps_ipv6_authorities_and_refuses_invalid_ports(raw, expected):
    assert ledger.normalize_url(raw) == expected
    if expected is not None:
        assert ledger.normalize_url(expected) == expected


def arguments(tmp_path, records):
    history = tmp_path / 'history.ndjson'
    history.write_text('\n'.join(json.dumps(row) for row in records) + '\n')
    return argparse.Namespace(history_path=str(history), state_root=str(tmp_path / 'state'),
                              url_field='url', time_field='iso_time')


def test_malformed_shapes_do_not_discard_valid_history(tmp_path, capsys):
    valid = {'url': 'https://example.invalid/page', 'iso_time': '2026-01-01T00:00:00Z'}
    args = arguments(tmp_path, [None, [], 3, 'text', {'url': ['bad'], 'iso_time': 'now'},
                               {'url': valid['url'], 'iso_time': {}}, valid])
    assert ledger.cmd_ingest(args) == 0
    result = json.loads((tmp_path / 'state/urls.jsonl').read_text())
    assert result['url'] == valid['url']
    assert result['visits'] == [valid['iso_time']]
    assert '6 malformed skipped' in capsys.readouterr().out


def test_ingest_ignores_preexisting_temporary_symlink_and_publishes_private(tmp_path):
    args = arguments(tmp_path, [{'url': 'https://example.invalid/', 'iso_time': 'now'}])
    state = tmp_path / 'state'
    state.mkdir()
    unrelated = tmp_path / 'unrelated'
    unrelated.write_text('preserve')
    (state / 'urls.jsonl.tmp').symlink_to(unrelated)
    old_umask = os.umask(0)
    try:
        assert ledger.cmd_ingest(args) == 0
    finally:
        os.umask(old_umask)
    assert unrelated.read_text() == 'preserve'
    assert (state / 'urls.jsonl.tmp').is_symlink()
    assert (state / 'urls.jsonl').stat().st_mode & 0o777 == 0o600
    assert not list(state.glob('.urls.jsonl.atomic-tmp-*'))


def test_failed_ingest_publication_keeps_previous_output(tmp_path, monkeypatch):
    args = arguments(tmp_path, [{'url': 'https://example.invalid/', 'iso_time': 'now'}])
    state = tmp_path / 'state'
    state.mkdir()
    output = state / 'urls.jsonl'
    output.write_text('previous complete output')

    def refuse(*args, **kwargs):
        raise OSError('synthetic publication failure')

    monkeypatch.setattr(ledger.json, 'dumps', refuse)
    with pytest.raises(OSError, match='synthetic publication failure'):
        ledger.cmd_ingest(args)
    assert output.read_text() == 'previous complete output'
    assert not list(state.glob('.urls.jsonl.atomic-tmp-*'))


def test_visit_bounds_follow_instants_and_preserve_timestamp_spelling(tmp_path):
    # Lexically earlier local date is actually the later instant.
    earliest = "2026-01-01T01:00:00+02:00"
    latest = "2025-12-31T23:30:00Z"
    args = arguments(tmp_path, [
        {"url": "https://example.invalid/", "iso_time": latest},
        {"url": "https://example.invalid/", "iso_time": earliest},
    ])
    assert ledger.cmd_ingest(args) == 0
    row = json.loads((tmp_path / "state/urls.jsonl").read_text())
    assert row["visits"] == [earliest, latest]
    assert row["visit_count"] == 2
    assert row["first_visit"] == earliest
    assert row["last_visit"] == latest


def test_unparseable_visits_remain_evidence_without_claimed_time_bounds(tmp_path):
    stamps = ["2026-01-01T00:00:00Z", "unknown historical timestamp"]
    args = arguments(tmp_path, [{"url": "https://example.invalid/", "iso_time": stamp} for stamp in stamps])
    assert ledger.cmd_ingest(args) == 0
    row = json.loads((tmp_path / "state/urls.jsonl").read_text())
    assert set(row["visits"]) == set(stamps)
    assert row["visit_count"] == 2
    assert row["first_visit"] is None and row["last_visit"] is None


@pytest.mark.parametrize("failure", ["denied", "disappeared", "fifo", "directory"])
def test_unavailable_history_member_cannot_publish_partial_ingest(tmp_path, monkeypatch, capsys, failure):
    from pathlib import Path
    history = tmp_path / "history"
    history.mkdir()
    record = json.dumps({"url": "https://example.invalid/valid", "iso_time": "2026-01-01T00:00:00Z"}) + "\n"
    (history / "good.jsonl").write_text(record)
    blocked = history / "blocked.jsonl"
    if failure == "fifo":
        os.mkfifo(blocked)
    elif failure == "directory":
        blocked.mkdir()
    else:
        blocked.write_text(record)
        original = Path.stat
        def unavailable(path, *args, **kwargs):
            if path == blocked:
                if failure == "denied":
                    raise PermissionError("fixture permission denied")
                raise FileNotFoundError("fixture disappeared during discovery")
            return original(path, *args, **kwargs)
        monkeypatch.setattr(Path, "stat", unavailable)
    state = tmp_path / "state"
    state.mkdir()
    output = state / "urls.jsonl"
    output.write_bytes(b"previous complete state\n")
    result = ledger.main(["ingest", "--history-path", str(history), "--state-root", str(state)])
    assert result == 1
    assert output.read_bytes() == b"previous complete state\n"
    assert "blocked.jsonl" in capsys.readouterr().err


def test_history_discovery_keeps_valid_file_links_and_ignores_other_extensions(tmp_path):
    history = tmp_path / "history"
    history.mkdir()
    target = tmp_path / "retained.jsonl"
    target.write_text('{"url":"https://example.invalid/","iso_time":"2026-01-01T00:00:00Z"}\n')
    (history / "linked.jsonl").symlink_to(target)
    os.mkfifo(history / "unrelated.pipe")
    assert ledger.discover_history_paths(history) == [history / "linked.jsonl"]
