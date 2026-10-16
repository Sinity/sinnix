import hashlib
import json
import os
import subprocess
import sys

from sinnix_phone_dispatcher import event_status
from sinnix_phone_dispatcher.cli import main


def _line(ts='2026-05-01T12:00:00Z', **fields):
    return (json.dumps({'ts': ts, **fields}) + '\n').encode()


def test_large_tail_reads_only_bounded_payload_and_preserves_source(tmp_path, monkeypatch):
    path = tmp_path / 'events.jsonl'
    path.write_bytes(_line(body='x' * (5 * 1024 * 1024)) + _line(kind='chunk_closed', chunk='fixture.m4a'))
    original_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    original_open = os.fdopen
    reads = []
    class Reader:
        def __init__(self, handle): self.handle = handle
        def __enter__(self): return self
        def __exit__(self, *args): self.handle.close()
        def fileno(self): return self.handle.fileno()
        def seek(self, *args): return self.handle.seek(*args)
        def read(self, size):
            reads.append(size)
            return self.handle.read(size)
    with monkeypatch.context() as patch:
        patch.setattr(os, 'fdopen', lambda *args, **kwargs: Reader(original_open(*args, **kwargs)))
        result = event_status.read_event_status(path)
    assert max(reads) <= event_status.MAX_TAIL_BYTES
    assert sum(reads) <= event_status.MAX_TAIL_BYTES + 1
    assert result['state'] == 'observed' and result['chunk'] == 'fixture.m4a'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original_digest


def test_exact_boundary_keeps_first_complete_record_and_orders_timezone(tmp_path, monkeypatch):
    first = _line('2026-05-02T00:10:00+02:00', kind='chunk_closed', chunk='fixture.m4a')
    second = _line('2026-05-01T23:30:00Z', kind='chunk_upload_ok')
    path = tmp_path / 'events.jsonl'
    path.write_bytes(b'old prefix\n' + first + second)
    monkeypatch.setattr(event_status, 'MAX_TAIL_BYTES', len(first) + len(second))
    result = event_status.read_event_status(path)
    assert result['ts'] == '2026-05-01T23:30:00Z'
    assert result['chunk'] == 'fixture.m4a'
    assert result['upload'] == 'chunk_upload_ok'


def test_partial_utf8_head_and_in_flight_tail_are_not_records(tmp_path, monkeypatch):
    record = _line(kind='chunk_upload_failed', reason='network\nretry\x1b')
    path = tmp_path / 'events.jsonl'
    path.write_bytes(('ł' * 20 + '\n').encode() + record)
    monkeypatch.setattr(event_status, 'MAX_TAIL_BYTES', len(record) + 2)
    result = event_status.read_event_status(path)
    assert result['state'] == 'observed'
    assert '\n' not in result['upload'] and '\x1b' not in result['upload']
    monkeypatch.setattr(event_status, 'MAX_TAIL_BYTES', 1024)
    path.write_bytes(record + b'{"ts":"2026-05-02T00:00:00Z"')
    result = event_status.read_event_status(path)
    assert result['ts'] == '2026-05-01T12:00:00Z'
    assert result['skipped_records'] == 1  # The in-flight tail.


def test_oversized_and_invalid_records_do_not_hide_readable_status(tmp_path):
    path = tmp_path / 'events.jsonl'
    path.write_bytes(_line(kind='chunk_closed', chunk='fixture.m4a') +
                     _line('2026-05-02T00:00:00Z', body='x' * event_status.MAX_RECORD_BYTES) +
                     b'\xff\n' + b'{"ts":"2026-05-03T00:00:00"}\n')
    result = event_status.read_event_status(path)
    assert result['ts'] == '2026-05-01T12:00:00Z'
    assert result['skipped_records'] == 3


def test_source_states_are_explicit(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'events.jsonl'
    assert event_status.read_event_status(None)['state'] == 'missing'
    assert event_status.read_event_status(path)['state'] == 'missing'
    path.touch()
    assert event_status.read_event_status(path)['state'] == 'empty'
    path.write_bytes(b'not JSON\n')
    assert event_status.read_event_status(path)['state'] == 'no_readable_records'
    path.write_bytes(_line(kind='chunk_upload_ok'))
    assert main(['event-status', '--file', str(path)]) == 0
    assert json.loads(capsys.readouterr().out)['upload'] == 'chunk_upload_ok'
    def denied(*args, **kwargs): raise PermissionError('synthetic denied source')
    monkeypatch.setattr(os, 'open', denied)
    assert event_status.read_event_status(path)['state'] == 'unavailable'


def test_fifo_status_returns_without_a_writer(tmp_path):
    path = tmp_path / 'events.jsonl'
    os.mkfifo(path)
    result = subprocess.run(
        [sys.executable, '-c',
         'import json,sys; from pathlib import Path; '
         'from sinnix_phone_dispatcher.event_status import read_event_status; '
         'print(json.dumps(read_event_status(Path(sys.argv[1]))))', str(path)],
        capture_output=True, text=True, timeout=5, check=True,
    )
    payload = json.loads(result.stdout)
    assert payload['state'] == 'unavailable'
    assert 'not a regular file' in payload['reason']
    assert path.is_fifo()


def test_directory_status_is_unavailable(tmp_path):
    assert event_status.read_event_status(tmp_path)['state'] == 'unavailable'


def test_regular_file_symlink_keeps_status_readable(tmp_path):
    target = tmp_path / 'retained.jsonl'
    target.write_bytes(_line(kind='chunk_upload_ok'))
    path = tmp_path / 'events.jsonl'
    path.symlink_to(target)
    assert event_status.read_event_status(path)['upload'] == 'chunk_upload_ok'
