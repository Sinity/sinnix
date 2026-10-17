import argparse
import json
import runpy
from pathlib import Path

import pytest


@pytest.fixture
def score():
    return runpy.run_path(str(Path(__file__).resolve().parents[3] / 'scripts/sinnix-score'))


def test_regular_interpolation_is_unchanged(score):
    assert score['resample_uniform']([0., 1., 2.], [0., 2., 4.], 2.) == [0., 1., 2., 3.]


@pytest.mark.parametrize('times,values,rate', [
    ([0., 1e-9, 1.], [1., 2., 3.], 1e9),
    ([0., 1.], [1., 2.], float('inf')),
    ([0., float('inf')], [1., 2.], 1.),
    ([0., 1.], [1., float('nan')], 1.),
    ([0., 0., 1.], [1., 2., 3.], 2.),
    ([0., 1.], [1.], 2.),
])
def test_unprocessable_grid_is_refused_before_allocation(score, times, values, rate):
    with pytest.raises(score['UnscorableTrace']):
        score['resample_uniform'](times, values, rate)


def trace(path, mode, bad):
    if mode == 'ppg':
        lines = ['ts,value'] + [f'{i if bad else i * 33333333},1' for i in range(80)]
        lines += [f'{1000000000000 if bad else 80 * 33333333},1']
    else:
        lines = ['ts,type,x,y,z'] + [f'{i if bad else i * 10000000},accel,0,0,1' for i in range(80)]
        lines += [f'{1000000000000 if bad else 800000000},accel,0,0,1']
    path.write_text('\n'.join(lines) + '\n')
    path.with_name(path.name + '.json').write_text(json.dumps({'mode': mode}))


@pytest.mark.parametrize('mode', ['ppg', 'imu', 'imu_sway'])
def test_native_run_records_refusal_continues_and_does_not_repeat(score, tmp_path, mode):
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    bad, good = outbox / 'a.csv', outbox / 'b.csv'
    trace(bad, mode, True)
    trace(good, mode, False)
    original = bad.read_bytes()
    root = tmp_path / 'scores'
    glob = score['cmd_run'].__globals__
    glob.update(SCORES=root, LEDGER=root / 'scored.jsonl')
    args = argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True)
    assert score['cmd_run'](args) == 0
    records = [json.loads(x) for x in next(root.glob('20*.jsonl')).read_text().splitlines()]
    assert [x['file'] for x in records] == ['a.csv', 'b.csv']
    assert records[0]['ok'] is False
    assert 'resampled-sample limit' in records[0]['reason']
    assert 'resampled-sample limit' not in str(records[1])
    assert bad.read_bytes() == original
    before = (root / 'scored.jsonl').read_bytes()
    assert score['cmd_run'](args) == 0
    assert (root / 'scored.jsonl').read_bytes() == before


@pytest.mark.parametrize('window', [0, 1, 2, 3, 8, 17, 31, 32])
def test_moving_average_preserves_centered_and_clamped_windows(score, window):
    import math

    values = [100.0 + math.sin(i / 3) - i / 100 for i in range(31)]
    if window <= 1 or window > len(values):
        expected = values
    else:
        expected = []
        for i in range(len(values)):
            lo = max(0, min(i - window // 2, len(values) - window))
            expected.append(sum(values[lo:lo + window]) / window)
    assert score['moving_average'](values, window) == pytest.approx(expected, abs=1e-10)


def test_moving_average_work_is_linear_for_wide_windows(score):
    class CountedSignal:
        def __init__(self, count):
            self.values = [float(i % 11) for i in range(count)]
            self.reads = 0

        def __len__(self):
            return len(self.values)

        def __getitem__(self, key):
            if isinstance(key, slice):
                self.reads += len(range(*key.indices(len(self))))
            else:
                self.reads += 1
            return self.values[key]

    values = CountedSignal(4096)
    output = score['moving_average'](values, 2048)
    assert len(output) == len(values)
    assert values.reads <= 3 * len(values)



def test_moving_average_retains_small_signal_after_large_value_leaves(score):
    import math

    values = [1e16, 1.0, 1.0, -1e16, 2.0, 3.0, 4.0]
    window = 2
    expected = []
    for i in range(len(values)):
        lo = max(0, min(i - window // 2, len(values) - window))
        expected.append(math.fsum(values[lo:lo + window]) / window)
    assert score['moving_average'](values, window) == expected


def test_ignored_csv_rows_do_not_accumulate_in_memory(score, tmp_path):
    import tracemalloc

    path = tmp_path / 'ignored.csv'
    with path.open('w') as stream:
        stream.write('ts,value,unused\n')
        for _ in range(2000):
            stream.write('invalid,1,' + 'x' * 4096 + '\n')
    tracemalloc.start()
    try:
        result = score['score_ppg'](path)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result['ok'] is False
    assert 'only 0 samples' in result['reason']
    assert peak < 512 * 1024


@pytest.mark.parametrize('mode', ['ppg', 'imu', 'imu_sway'])
def test_timestamp_overflow_is_recorded_without_stalling_later_files(score, tmp_path, mode):
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    bad, good = outbox / 'a.csv', outbox / 'b.csv'
    columns = ',1' if mode == 'ppg' else ',accel,0,0,1'
    header = 'ts,value' if mode == 'ppg' else 'ts,type,x,y,z'
    bad.write_text(header + '\n' + '9' * 400 + columns + '\n')
    bad.with_name(bad.name + '.json').write_text(json.dumps({'mode': mode}))
    trace(good, mode, False)
    original = bad.read_bytes()
    root = tmp_path / 'scores'
    score['cmd_run'].__globals__.update(SCORES=root, LEDGER=root / 'scored.jsonl')
    args = argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True)
    assert score['cmd_run'](args) == 0
    records = [json.loads(line) for line in next(root.glob('20*.jsonl')).read_text().splitlines()]
    assert [r['file'] for r in records] == ['a.csv', 'b.csv']
    assert records[0]['ok'] is False
    assert 'numeric range' in records[0]['reason']
    assert bad.read_bytes() == original
    before = (root / 'scored.jsonl').read_bytes()
    assert score['cmd_run'](args) == 0
    assert (root / 'scored.jsonl').read_bytes() == before


@pytest.mark.parametrize('body', [b'[]', b'null', b'{', b'\xff', b'{"recorded_at":17}', b'{"send_token":[]}', b'{"epoch":NaN}', b'{"epoch":Infinity}', b'{"epoch":-Infinity}', b'{"epoch":1e999}'])
def test_invalid_sidecar_refuses_continues_and_retries_only_after_repair(score, tmp_path, body):
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    bad, good = outbox / 'a.csv', outbox / 'b.csv'
    trace(bad, 'imu', False)
    trace(good, 'imu', False)
    sidecar = bad.with_name(bad.name + '.json')
    sidecar.write_bytes(body)
    original = bad.read_bytes()
    root = tmp_path / 'scores'
    tokens = []
    score['cmd_run'].__globals__.update(SCORES=root, LEDGER=root / 'scored.jsonl', emit_receipt=lambda *args: tokens.append(args[4]))
    args = argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=False)
    assert score['cmd_run'](args) == 0
    records_path = next(root.glob('20*.jsonl'))
    records = [json.loads(line) for line in records_path.read_text().splitlines()]
    assert [r['file'] for r in records] == ['a.csv', 'b.csv']
    assert records[0]['ok'] is False and 'sidecar' in records[0]['reason']
    assert len(tokens) == 2 and tokens[0] is None
    before = records_path.read_bytes()
    assert score['cmd_run'](args) == 0
    assert records_path.read_bytes() == before and len(tokens) == 2
    sidecar.write_text(json.dumps({'mode': 'imu', 'send_token': 'repaired'}))
    assert score['cmd_run'](args) == 0
    records = [json.loads(line) for line in records_path.read_text().splitlines()]
    assert [r['file'] for r in records] == ['a.csv', 'b.csv', 'a.csv']
    assert records[-1]['ok'] is True
    assert 'sidecar' not in (records[-1].get('reason') or '')
    assert tokens[-1] == 'repaired' and bad.read_bytes() == original


def test_receipt_uses_the_same_metadata_snapshot_as_scoring(score, tmp_path):
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    path = outbox / 'a.csv'
    trace(path, 'imu', False)
    sidecar = path.with_name(path.name + '.json')
    sidecar.write_text(json.dumps({'mode': 'imu', 'send_token': 'first'}))
    root = tmp_path / 'scores'
    tokens = []
    original = score['score_blob']
    def change_after_scoring(*args, **kwargs):
        result = original(*args, **kwargs)
        sidecar.write_text(json.dumps({'mode': 'imu', 'send_token': 'second'}))
        return result
    score['cmd_run'].__globals__.update(SCORES=root, LEDGER=root / 'scored.jsonl', score_blob=change_after_scoring, emit_receipt=lambda *args: tokens.append(args[4]))
    assert score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=False)) == 0
    assert tokens == ['first']


@pytest.mark.parametrize('kind', ['fifo', 'directory', 'broken-link'])
def test_special_sidecars_are_refused_without_blocking(score, tmp_path, kind):
    import os
    import subprocess

    path = tmp_path / 'trace.csv'
    trace(path, 'imu', False)
    sidecar = path.with_name(path.name + '.json')
    sidecar.unlink()
    if kind == 'fifo':
        os.mkfifo(sidecar)
    elif kind == 'directory':
        sidecar.mkdir()
    else:
        sidecar.symlink_to(tmp_path / 'missing.json')
    script = Path(__file__).resolve().parents[3] / 'scripts/sinnix-score'
    result = subprocess.run([str(script), 'one', str(path)], capture_output=True, text=True, timeout=3)
    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record['ok'] is False and 'sidecar' in record['reason']
    assert sidecar.lstat()


def test_sidecar_absence_and_regular_link_remain_distinct_from_unavailability(score, tmp_path):
    path = tmp_path / 'trace.csv'
    path.write_text('ts,value\n')
    absent = score['read_sidecar'](path)
    assert absent.error is None and absent.signature == 'absent'
    target = tmp_path / 'metadata.json'
    target.write_text('{"mode":"imu"}')
    sidecar = path.with_name(path.name + '.json')
    sidecar.symlink_to(target)
    linked = score['read_sidecar'](path)
    assert linked.error is None and linked.values == {'mode': 'imu'}
    assert linked.signature.startswith('sha256:') and sidecar.is_symlink()


def test_legacy_scores_remain_history_without_automatic_reprocessing(score, tmp_path):
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    path = outbox / 'legacy.csv'
    trace(path, 'imu', False)
    root = tmp_path / 'scores'
    root.mkdir()
    ledger = root / 'scored.jsonl'
    legacy = json.dumps({'file': path.name, 'bytes': path.stat().st_size, 'ok': True}) + '\n'
    ledger.write_text(legacy)
    def no_replay(*args, **kwargs):
        raise AssertionError('legacy result must not launch new scoring')
    score['cmd_run'].__globals__.update(SCORES=root, LEDGER=ledger, score_blob=no_replay, read_sidecar=no_replay)
    assert score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True)) == 0
    assert ledger.read_text() == legacy
    assert not list(root.glob('20*.jsonl'))


@pytest.mark.parametrize('row', ['{', '[]', 'null', '{"file":"a.csv","bytes":true}', '{"file":"a.csv","bytes":-1}', '{"file":"a.csv","bytes":"12"}', '{"file":"a.csv","bytes":12,"sidecar_signature":[]}'])
def test_invalid_ledger_refuses_before_scoring(score, tmp_path, row):
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    trace(outbox / 'a.csv', 'ppg', False)
    root = tmp_path / 'scores'
    root.mkdir()
    ledger = root / 'scored.jsonl'
    ledger.write_text(row + '\n')
    before = ledger.read_bytes()
    score['cmd_run'].__globals__.update(SCORES=root, LEDGER=ledger)
    with pytest.raises(ValueError, match='ledger record 1 is invalid'):
        score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True))
    assert ledger.read_bytes() == before
    assert set(root.iterdir()) == {ledger, root / '.score.lock'}


def test_ledger_streams_and_preserves_legacy_keys(score, tmp_path, monkeypatch):
    ledger = tmp_path / 'scored.jsonl'
    ledger.write_text('{"file":"a.csv","bytes":12}\n{"file":"b.csv","bytes":0,"sidecar_signature":"absent"}\n')
    score['cmd_run'].__globals__['LEDGER'] = ledger
    def forbid(*args, **kwargs):
        raise AssertionError('whole-file read')
    monkeypatch.setattr(Path, 'read_text', forbid)
    with score['ledger_seen']() as seen:
        assert ('a.csv', 12, None) in seen and ('b.csv', 0, 'absent') in seen
        assert ('a.csv', 12, '') not in seen and ('b.csv', 0, None) not in seen


@pytest.mark.parametrize('kind', ['directory', 'fifo', 'broken-link'])
def test_unavailable_ledger_is_not_empty_history(score, tmp_path, kind):
    import os
    ledger = tmp_path / 'scored.jsonl'
    if kind == 'directory':
        ledger.mkdir()
    elif kind == 'fifo':
        os.mkfifo(ledger)
    else:
        ledger.symlink_to(tmp_path / 'missing')
    score['cmd_run'].__globals__['LEDGER'] = ledger
    with pytest.raises((OSError, ValueError)):
        with score['ledger_seen']():
            pass
    assert ledger.lstat()


def test_ledger_absence_and_regular_link(score, tmp_path):
    ledger = tmp_path / 'scored.jsonl'
    score['cmd_run'].__globals__['LEDGER'] = ledger
    with score['ledger_seen']() as seen:
        assert ('a.csv', 12, None) not in seen
    target = tmp_path / 'history'
    target.write_text('{"file":"a.csv","bytes":12}\n')
    ledger.symlink_to(target)
    with score['ledger_seen']() as seen:
        assert ('a.csv', 12, None) in seen
    assert ledger.is_symlink()


def test_ledger_open_denial_propagates(score, tmp_path, monkeypatch):
    ledger = tmp_path / 'scored.jsonl'
    ledger.write_text('')
    score['cmd_run'].__globals__['LEDGER'] = ledger
    def deny(*args, **kwargs):
        raise PermissionError('synthetic denied ledger')
    monkeypatch.setitem(score['cmd_run'].__globals__, 'open', deny)
    with pytest.raises(PermissionError, match='synthetic denied ledger'):
        with score['ledger_seen']():
            pass


def test_scorer_waits_for_other_process_owner_before_reading_ledger(score, tmp_path):
    import fcntl
    import threading
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    trace(outbox / 'a.csv', 'imu', False)
    root = tmp_path / 'scores'
    root.mkdir()
    called = threading.Event()
    errors = []
    glob = score['cmd_run'].__globals__
    original = glob['score_blob']
    def observed(*args, **kwargs):
        called.set()
        return original(*args, **kwargs)
    glob.update(SCORES=root, LEDGER=root / 'scored.jsonl', score_blob=observed)
    def run():
        try:
            assert score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True)) == 0
        except BaseException as error:
            errors.append(error)
    with (root / '.score.lock').open('a') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX)
        thread = threading.Thread(target=run)
        thread.start()
        try:
            assert not called.wait(0.25), 'competing scorer bypassed the active owner'
            assert not (root / 'scored.jsonl').exists()
        finally:
            fcntl.flock(owner, fcntl.LOCK_UN)
            thread.join(3)
    assert not thread.is_alive() and not errors
    assert called.is_set()
    assert score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True)) == 0
    assert len((root / 'scored.jsonl').read_text().splitlines()) == 1


def test_scorer_releases_owner_after_failure(score, tmp_path):
    import fcntl
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    root = tmp_path / 'scores'
    def fail():
        raise ValueError('synthetic ledger failure')
    score['cmd_run'].__globals__.update(SCORES=root, LEDGER=root / 'scored.jsonl', ledger_seen=fail)
    with pytest.raises(ValueError, match='synthetic ledger failure'):
        score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True))
    with (root / '.score.lock').open('a') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_history_memory_does_not_retain_all_ledger_keys(score, tmp_path):
    import tracemalloc
    ledger = tmp_path / 'scored.jsonl'
    with ledger.open('w') as output:
        for n in range(25000):
            output.write(json.dumps({'file': f'trace-{n:08d}.csv', 'bytes': n, 'sidecar_signature': 'sha256:' + str(n).zfill(64)}) + '\n')
    score['cmd_run'].__globals__['LEDGER'] = ledger
    tracemalloc.start()
    try:
        with score['ledger_seen']() as history:
            assert ('trace-00024999.csv', 24999, 'sha256:' + str(24999).zfill(64)) in history
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 1024 * 1024, f'history retained {peak} Python bytes'


def test_disk_history_preserves_full_key_and_integer_semantics(score, tmp_path):
    ledger = tmp_path / 'scored.jsonl'
    rows = [dict(file='unicode-ą.csv', bytes=2**80), dict(file='a.csv', bytes=0, sidecar_signature=''), dict(file='a.csv', bytes=1, sidecar_signature='absent')]
    ledger.write_text(''.join(json.dumps(row) + '\n' for row in rows + rows))
    score['cmd_run'].__globals__['LEDGER'] = ledger
    with score['ledger_seen']() as seen:
        assert ('unicode-ą.csv', 2**80, None) in seen
        assert ('unicode-ą.csv', 2**80 + 1, None) not in seen
        assert ('a.csv', 0, '') in seen and ('a.csv', 0, None) not in seen
        assert ('a.csv', 1, 'absent') in seen and ('a.csv', 1, '') not in seen
        assert ('a.csv', 2, 'absent') not in seen
        database = seen.database
    with pytest.raises(score['sqlite3'].ProgrammingError):
        database.execute('SELECT 1')


def test_history_connection_closes_after_processing_failure(score, tmp_path):
    score['cmd_run'].__globals__['LEDGER'] = tmp_path / 'missing'
    with pytest.raises(RuntimeError, match='synthetic processing failure'):
        with score['ledger_seen']() as seen:
            database = seen.database
            raise RuntimeError('synthetic processing failure')
    with pytest.raises(score['sqlite3'].ProgrammingError):
        database.execute('SELECT 1')


def test_history_storage_failure_stops_before_scores_or_receipts(score, tmp_path, monkeypatch):
    root = tmp_path / 'scores'
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    trace(outbox / 'a.csv', 'imu', False)
    glob = score['cmd_run'].__globals__
    def full(*args, **kwargs):
        raise score['sqlite3'].OperationalError('synthetic database or disk is full')
    monkeypatch.setattr(score['sqlite3'], 'connect', full)
    calls = []
    glob.update(SCORES=root, LEDGER=root / 'scored.jsonl', emit_receipt=lambda *args: calls.append(args))
    with pytest.raises(score['sqlite3'].OperationalError, match='disk is full'):
        score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=False))
    assert set(root.iterdir()) == {root / '.score.lock'} and not calls


def test_discovery_does_not_stat_unrelated_outbox_entries(score, tmp_path, monkeypatch):
    import os
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    trace(outbox / 'a.csv', 'imu', False)
    scores = tmp_path / 'scores'
    glob = score['cmd_run'].__globals__
    glob.update(SCORES=scores, LEDGER=scores / 'scored.jsonl')
    original_entries, original_stat = score['_directory_paths'], os.stat
    unrelated_stats = []
    def entries(path):
        if path == outbox:
            yield from (outbox / f'ignored-{n}.bin' for n in range(10000))
        yield from original_entries(path)
    def observed_stat(path, *args, **kwargs):
        if not isinstance(path, int):
            candidate = Path(os.fsdecode(path))
            if candidate.parent == outbox and candidate.suffix not in ('.csv', '.m4a'):
                unrelated_stats.append(candidate.name)
        return original_stat(path, *args, **kwargs)
    glob['_directory_paths'] = entries
    monkeypatch.setattr(os, 'stat', observed_stat)
    assert score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True)) == 0
    assert not unrelated_stats, f'{len(unrelated_stats)} unnecessary metadata lookups'
    assert len((scores / 'scored.jsonl').read_text().splitlines()) == 1


@pytest.mark.parametrize('kind', ['file', 'broken-link'])
def test_unusable_outbox_is_not_absent(score, tmp_path, kind):
    outbox = tmp_path / 'outbox'
    if kind == 'file':
        outbox.write_text('not a directory')
    else:
        outbox.symlink_to(tmp_path / 'missing')
    scores = tmp_path / 'scores'
    score['cmd_run'].__globals__.update(SCORES=scores, LEDGER=scores / 'scored.jsonl')
    with pytest.raises((OSError, ValueError)):
        score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True))
    assert not scores.exists()


def test_outbox_access_error_is_not_absent(score, tmp_path, monkeypatch):
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    scores = tmp_path / 'scores'
    score['cmd_run'].__globals__.update(SCORES=scores, LEDGER=scores / 'scored.jsonl')
    original = Path.stat
    def denied(path, *args, **kwargs):
        if path == outbox:
            raise PermissionError('synthetic outbox denial')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', denied)
    with pytest.raises(PermissionError, match='synthetic outbox denial'):
        score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True))
    assert not scores.exists()


@pytest.mark.parametrize('kind', ['directory', 'fifo', 'broken-link'])
def test_unusable_candidate_stops_before_processing(score, tmp_path, kind):
    import os
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    path = outbox / 'a.csv'
    if kind == 'directory':
        path.mkdir()
    elif kind == 'fifo':
        os.mkfifo(path)
    else:
        path.symlink_to(outbox / 'missing')
    scores = tmp_path / 'scores'
    calls = []
    score['cmd_run'].__globals__.update(SCORES=scores, LEDGER=scores / 'scored.jsonl', score_blob=lambda *args: calls.append(args))
    with pytest.raises((OSError, ValueError)):
        score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True))
    assert not calls and set(scores.iterdir()) == {scores / '.score.lock'}


def test_missing_and_empty_outbox_remain_distinct(score, tmp_path, capsys):
    outbox = tmp_path / 'outbox'
    scores = tmp_path / 'scores'
    score['cmd_run'].__globals__.update(SCORES=scores, LEDGER=scores / 'scored.jsonl')
    args = argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True)
    assert score['cmd_run'](args) == 0
    assert 'no outbox' in capsys.readouterr().out and not scores.exists()
    outbox.mkdir()
    assert score['cmd_run'](args) == 0
    assert 'scored 0' in capsys.readouterr().out


@pytest.mark.parametrize('mode', ['ppg', 'imu', 'imu_sway'])
def test_direct_fifo_trace_refuses_without_waiting_for_a_writer(score, tmp_path, mode):
    import os
    import subprocess
    import sys
    path = tmp_path / 'trace.csv'
    os.mkfifo(path)
    path.with_name(path.name + '.json').write_text(json.dumps({'mode': mode}))
    result = subprocess.run([sys.executable, score['__file__'], 'one', str(path)], capture_output=True, text=True, timeout=3,
                            env=dict(os.environ, SINNIX_PHONE_LAKE=str(tmp_path / 'lake'), SINNIX_PHONE_STATE_DIR=str(tmp_path / 'state')))
    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record['ok'] is False and 'regular file' in record['reason']
    assert path.lstat()


def test_interoception_streams_events_and_keeps_first_nearest_run(score, tmp_path):
    import tracemalloc
    events = tmp_path / 'events'
    events.mkdir()
    stamp = '2026-10-18T00:00:00Z'
    selected = {'kind': 'instrument_run', 'instrument': 'interoception', 'started_at': stamp, 'counted': [10], 'window_ms': [10000], 'epoch': 'first'}
    with (events / 'events-a.jsonl').open('w') as output:
        output.write(json.dumps(selected) + '\n')
        for _ in range(5000):
            output.write(json.dumps({'kind': 'unrelated', 'payload': 'x' * 512}) + '\n')
        output.write(json.dumps(selected | {'epoch': 'later', 'counted': [1]}) + '\n')
    (events / 'events-z.jsonl').write_text(json.dumps(selected | {'epoch': 'other-file', 'counted': [1]}) + '\n')
    score['cmd_run'].__globals__['EVENTS'] = events
    started_at = score['parse_stamp'](stamp)  # Exclude one-time datetime parser imports.
    tracemalloc.start()
    try:
        result = score['score_interoception'](tmp_path / 'trace.csv', {'ok': True, 'trustworthy': True, 'hr_bpm': 60}, started_at)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result['accuracy'] == 1.0 and result['epoch'] == 'first'
    assert peak < 512 * 1024, f'event lookup retained {peak} Python bytes'


def test_interoception_unusable_event_home_is_not_no_runs(score, tmp_path):
    events = tmp_path / 'events'
    events.write_text('not a directory')
    score['cmd_run'].__globals__['EVENTS'] = events
    with pytest.raises((OSError, ValueError)):
        score['score_interoception'](tmp_path / 'trace.csv', {'ok': True, 'trustworthy': True, 'hr_bpm': 60}, 0)


def test_event_source_closes_when_candidate_timestamp_fails(score, tmp_path, monkeypatch):
    import builtins
    events = tmp_path / 'events'
    events.mkdir()
    (events / 'events-a.jsonl').write_text(json.dumps({'kind': 'instrument_run', 'instrument': 'interoception', 'started_at': 17}) + '\n')
    opened = []
    def tracked(*args, **kwargs):
        handle = builtins.open(*args, **kwargs)
        opened.append(handle)
        return handle
    glob = score['cmd_run'].__globals__
    glob['EVENTS'] = events
    monkeypatch.setitem(glob, 'open', tracked)
    with pytest.raises(ValueError, match='timestamp'):
        score['score_interoception'](tmp_path / 'trace.csv', {'ok': True, 'trustworthy': True, 'hr_bpm': 60}, 0)
    assert opened and all(handle.closed for handle in opened)


def test_event_window_and_existing_malformed_line_policy(score, tmp_path):
    import os
    import time
    events = tmp_path / 'events'
    events.mkdir()
    stamp = '2026-10-18T00:00:00Z'
    good = {'kind': 'instrument_run', 'instrument': 'interoception', 'started_at': stamp, 'counted': [10], 'window_ms': [10000], 'epoch': 'current'}
    old = events / 'events-old.jsonl'
    old.write_text(json.dumps(good | {'epoch': 'old', 'counted': [0]}) + '\n')
    os.utime(old, (time.time() - 10 * 86400,) * 2)
    (events / 'events-new.jsonl').write_text('{malformed\n' + json.dumps(good) + '\n')
    score['cmd_run'].__globals__['EVENTS'] = events
    result = score['score_interoception'](tmp_path / 'trace.csv', {'ok': True, 'trustworthy': True, 'hr_bpm': 60}, score['parse_stamp'](stamp))
    assert result['accuracy'] == 1.0 and result['epoch'] == 'current'


def test_event_missing_empty_and_broken_home(score, tmp_path):
    events = tmp_path / 'events'
    score['cmd_run'].__globals__['EVENTS'] = events
    args = (tmp_path / 'trace.csv', {'ok': True, 'trustworthy': True, 'hr_bpm': 60}, 0)
    assert score['score_interoception'](*args) is None
    events.mkdir()
    assert score['score_interoception'](*args) is None
    events.rmdir()
    events.symlink_to(tmp_path / 'missing')
    with pytest.raises(FileNotFoundError):
        score['score_interoception'](*args)


def test_csv_source_closes_when_consumer_raises(score, tmp_path, monkeypatch):
    import builtins
    path = tmp_path / 'a.csv'
    path.write_text('header\n0,1\n')
    opened = []
    def tracked(*args, **kwargs):
        handle = builtins.open(*args, **kwargs)
        opened.append(handle)
        return handle
    monkeypatch.setitem(score['cmd_run'].__globals__, 'open', tracked)
    with pytest.raises(RuntimeError, match='synthetic consumer failure'):
        with score['csv_rows'](path) as rows:
            assert next(rows) == ['0', '1']
            raise RuntimeError('synthetic consumer failure')
    assert opened and all(handle.closed for handle in opened)


@pytest.mark.parametrize('trace_stamp', [None, '', 'not-a-time'])
def test_unknown_trace_time_cannot_pair_with_unknown_event_time(score, tmp_path, trace_stamp):
    events = tmp_path / 'events'
    events.mkdir()
    (events / 'events-a.jsonl').write_text(json.dumps({'kind': 'instrument_run', 'instrument': 'interoception', 'counted': [10], 'window_ms': [10000]}) + '\n')
    score['cmd_run'].__globals__['EVENTS'] = events
    result = score['score_interoception'](tmp_path / 'trace.csv', {'ok': True, 'trustworthy': True, 'hr_bpm': 60}, score['parse_stamp'](trace_stamp))
    assert result is None


def test_valid_epoch_zero_remains_distinct_from_unknown_time(score, tmp_path):
    events = tmp_path / 'events'
    events.mkdir()
    stamp = '1970-01-01T00:00:00Z'
    (events / 'events-a.jsonl').write_text(json.dumps({'kind': 'instrument_run', 'instrument': 'interoception', 'started_at': stamp, 'counted': [10], 'window_ms': [10000]}) + '\n')
    score['cmd_run'].__globals__['EVENTS'] = events
    assert score['parse_stamp'](stamp) == 0.0
    result = score['score_interoception'](tmp_path / 'trace.csv', {'ok': True, 'trustworthy': True, 'hr_bpm': 60}, score['parse_stamp'](stamp))
    assert result['accuracy'] == 1.0


def test_unknown_matching_event_time_refuses_correlation(score, tmp_path):
    events = tmp_path / 'events'
    events.mkdir()
    (events / 'events-a.jsonl').write_text(json.dumps({'kind': 'instrument_run', 'instrument': 'interoception', 'counted': [10], 'window_ms': [10000]}) + '\n')
    score['cmd_run'].__globals__['EVENTS'] = events
    with pytest.raises(ValueError, match='timestamp'):
        score['score_interoception'](tmp_path / 'trace.csv', {'ok': True, 'trustworthy': True, 'hr_bpm': 60}, 0.0)


def test_current_and_historical_timestamp_formats_keep_the_same_instant(score):
    assert score['parse_stamp']('2026-10-18T00:00:00Z') == score['parse_stamp']('20261018T000000Z')
    assert score['parse_stamp']('19700101T000000Z') == 0.0
    assert score['parse_stamp']('not-a-time') is None
    assert score['parse_stamp'](17) is None


def numeric_interoception(score, tmp_path, counted, windows, reference=60):
    events = tmp_path / 'events'
    events.mkdir()
    (events / 'events-a.jsonl').write_text(json.dumps({'kind': 'instrument_run', 'instrument': 'interoception', 'started_at': '1970-01-01T00:00:00Z', 'counted': counted, 'window_ms': windows}) + '\n')
    score['cmd_run'].__globals__['EVENTS'] = events
    return score['score_interoception'](tmp_path / 'trace.csv', {'ok': True, 'trustworthy': True, 'hr_bpm': reference}, 0.0)


@pytest.mark.parametrize('counted,windows', [
    ([float('nan')], [10000]), ([float('inf')], [10000]), ([-1], [10000]),
    ([True], [10000]), (['10'], [10000]), ({'a': 10}, [10000]),
    ([10], [float('nan')]), ([10], [float('inf')]), ([10], [True]),
    ([10, 10], [0, 10000]), ([10, 10], [-1, 10000]),
    ([10], ['10000']), ([10, 20], [10000]), (None, [10000]),
])
def test_malformed_interoception_measurements_refuse_a_result(score, tmp_path, counted, windows):
    with pytest.raises(ValueError, match='interoception'):
        numeric_interoception(score, tmp_path, counted, windows)


@pytest.mark.parametrize('reference', [float('nan'), float('inf'), 0, -1, True, None])
def test_invalid_interoception_reference_refuses_a_result(score, tmp_path, reference):
    with pytest.raises(ValueError, match='interoception'):
        numeric_interoception(score, tmp_path, [10], [10000], reference)


@pytest.mark.parametrize('counts,windows,expected', [([0], [10000], 0.0), ([100], [10000], -8.0), ([25, 35, 45], [25000, 35000, 45000], 1.0)])
def test_valid_interoception_keeps_zero_overcounts_and_native_windows(score, tmp_path, counts, windows, expected):
    result = numeric_interoception(score, tmp_path, counts, windows)
    assert result['accuracy'] == expected and result['windows'] == len(counts)
    assert result['counted'] == counts


def test_interoception_mean_does_not_overflow_finite_measurements(score, tmp_path):
    import math
    result = numeric_interoception(score, tmp_path, [1e308, 1e308], [1000, 1000])
    assert math.isfinite(result['accuracy']) and result['accuracy'] == -1e308


def test_empty_interoception_run_is_not_a_measured_zero(score, tmp_path):
    assert numeric_interoception(score, tmp_path, [], []) is None


@pytest.mark.parametrize('entry', ['one', 'run'])
@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_internal_result_cannot_escape_json_publication(score, tmp_path, capsys, entry, bad):
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    path = outbox / 'a.csv'
    trace(path, 'imu', False)
    def bad_result(*args, **kwargs):
        return {'ok': True, 'file': path.name, 'internal_bug': bad}
    score['cmd_run'].__globals__['score_blob'] = bad_result
    root = tmp_path / 'scores'
    receipts = []
    score['cmd_run'].__globals__.update(SCORES=root, LEDGER=root / 'scored.jsonl', emit_receipt=lambda *args: receipts.append(args))
    with pytest.raises(ValueError, match='JSON'):
        if entry == 'one':
            score['cmd_one'](argparse.Namespace(file=str(path)))
        else:
            score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=False))
    assert not capsys.readouterr().out and not receipts
    if entry == 'run':
        assert set(root.iterdir()) == {root / '.score.lock'}
    else:
        assert not root.exists()


def test_disk_order_preserves_path_order_and_duplicates(score):
    paths = [Path('/a-b/x'), Path('/a/b'), Path('/a/é'), Path('/a/\udc80'),
             Path('/a/a'), Path('/a/b')]
    with score['_ordered_paths'](iter(paths)) as ordered:
        assert list(ordered) == sorted(paths)


def test_inventory_failure_closes_private_database_before_yield(score, monkeypatch):
    import sqlite3
    connect = sqlite3.connect
    opened = []
    def track(*args, **kwargs):
        database = connect(*args, **kwargs)
        opened.append(database)
        return database
    monkeypatch.setattr(sqlite3, 'connect', track)
    def unavailable():
        yield Path('/a/first.csv')
        raise PermissionError('inventory unavailable')
    with pytest.raises(PermissionError, match='inventory unavailable'):
        with score['_ordered_paths'](unavailable()):
            pytest.fail('partial inventory became available')
    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        opened[0].execute('SELECT 1')


def test_candidate_inventory_keeps_lexical_publication_order(score, tmp_path):
    root = tmp_path / 'scores'
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    for name in ['z.csv', 'a.csv', 'm.csv']:
        (outbox / name).write_text('synthetic')
    score['cmd_run'].__globals__.update(
        SCORES=root, LEDGER=root / 'scored.jsonl',
        score_blob=lambda path, sidecar: {'ok': True, 'file': path.name},
    )
    score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=2, no_receipt=True))
    records = [json.loads(line) for line in next(root.glob('20*.jsonl')).read_text().splitlines()]
    assert [record['file'] for record in records] == ['a.csv', 'm.csv']


def test_reached_limit_does_not_touch_next_inventory_entry(score, tmp_path):
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    first, later = outbox / 'a.csv', outbox / 'b.csv'
    first.write_text('synthetic')
    later.write_text('synthetic')
    def process(path, sidecar):
        later.unlink()
        return {'ok': True, 'file': path.name}
    root = tmp_path / 'scores'
    score['cmd_run'].__globals__.update(SCORES=root, LEDGER=root/'scored.jsonl', score_blob=process)
    assert score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=1, no_receipt=True)) == 0
    assert len((root/'scored.jsonl').read_text().splitlines()) == 1


def test_directory_inventory_does_not_materialize_path_iterdir(score, tmp_path, monkeypatch):
    path = tmp_path / 'a.csv'
    path.write_text('synthetic')
    def forbidden(*args, **kwargs):
        raise AssertionError('Path.iterdir retains a whole directory')
    monkeypatch.setattr(Path, 'iterdir', forbidden)
    assert list(score['_candidate_paths'](tmp_path)) == [path]


def test_same_size_payload_replacement_gets_its_own_score(score, tmp_path):
    import hashlib
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    path = outbox / 'a.csv'
    first, second = b'ts,value\n0,1\n1,2\n', b'ts,value\n0,9\n1,8\n'
    assert len(first) == len(second)
    path.write_bytes(first)
    root = tmp_path / 'scores'
    score['cmd_run'].__globals__.update(SCORES=root, LEDGER=root / 'scored.jsonl')
    args = argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True)
    assert score['cmd_run'](args) == 0
    assert score['cmd_run'](args) == 0
    path.write_bytes(second)
    assert score['cmd_run'](args) == 0
    rows = [json.loads(line) for line in (root/'scored.jsonl').read_text().splitlines()]
    assert [row['payload_sha256'] for row in rows] == [hashlib.sha256(first).hexdigest(), hashlib.sha256(second).hexdigest()]
    records = [json.loads(line) for line in next(root.glob('20*.jsonl')).read_text().splitlines()]
    assert [record['payload_sha256'] for record in records] == [row['payload_sha256'] for row in rows]


def test_scoring_uses_private_snapshot_when_original_changes(score, tmp_path):
    import hashlib
    outbox = tmp_path / 'outbox'
    outbox.mkdir()
    original = outbox / 'a.csv'
    payload = b'ts,value\n0,1\n1,2\n'
    original.write_bytes(payload)
    root = tmp_path / 'scores'
    observed = []
    def process(path, sidecar):
        original.write_bytes(b'ts,value\n0,9\n1,8\n')
        observed.append((path, path.read_bytes(), path.stat().st_mode & 0o777))
        return {'ok': True, 'file': path.name}
    score['cmd_run'].__globals__.update(SCORES=root, LEDGER=root/'scored.jsonl', score_blob=process)
    assert score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True)) == 0
    assert observed[0][0] != original
    assert observed[0][1:] == (payload, 0o600)
    assert not observed[0][0].exists()
    row = json.loads((root/'scored.jsonl').read_text())
    assert row['payload_sha256'] == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize('digest', ['', 'x'*64, 'a'*63, 42])
def test_bad_payload_binding_refuses_before_scoring(score, tmp_path, digest):
    root = tmp_path/'scores'
    root.mkdir()
    ledger = root/'scored.jsonl'
    ledger.write_text(json.dumps({'file':'a.csv','bytes':1,'payload_sha256':digest})+'\n')
    score['cmd_run'].__globals__['LEDGER'] = ledger
    with pytest.raises(ValueError, match='ledger record 1 is invalid'):
        with score['ledger_seen']():
            pytest.fail('invalid content binding accepted')


def test_unchanged_payload_does_not_read_or_snapshot_again(score, tmp_path):
    outbox = tmp_path/'outbox'
    outbox.mkdir()
    (outbox/'a.csv').write_text('ts,value\n0,1\n1,2\n')
    root = tmp_path/'scores'
    glob = score['cmd_run'].__globals__
    glob.update(SCORES=root, LEDGER=root/'scored.jsonl')
    args = argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True)
    assert score['cmd_run'](args) == 0
    def forbidden(*args, **kwargs):
        raise AssertionError('unchanged content was reread')
    glob['_payload_hash'] = forbidden
    assert score['cmd_run'](args) == 0
    assert len((root/'scored.jsonl').read_text().splitlines()) == 1


def test_replaced_inode_same_content_is_rehashed_without_scoring_or_copying(score, tmp_path, monkeypatch):
    outbox = tmp_path/'outbox'
    outbox.mkdir()
    path = outbox/'a.csv'
    path.write_text('ts,value\n0,1\n1,2\n')
    root = tmp_path/'scores'
    glob = score['cmd_run'].__globals__
    glob.update(SCORES=root, LEDGER=root/'scored.jsonl')
    args = argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True)
    assert score['cmd_run'](args) == 0
    replacement = tmp_path/'replacement'
    replacement.write_bytes(path.read_bytes())
    replacement.replace(path)
    calls = []
    hash_payload = glob['_payload_hash']
    def observed(source):
        calls.append(True)
        return hash_payload(source)
    def forbidden(*args, **kwargs):
        raise AssertionError('already scored bytes were copied or scored again')
    glob.update(_payload_hash=observed, score_blob=forbidden)
    monkeypatch.setattr(score['tempfile'], 'TemporaryDirectory', forbidden)
    assert score['cmd_run'](args) == 0
    assert calls == [True]
    rows = [json.loads(line) for line in (root/'scored.jsonl').read_text().splitlines()]
    assert len(rows) == 2 and rows[1]['kind'] == 'payload_observation'
    glob['_payload_hash'] = forbidden
    assert score['cmd_run'](args) == 0
    assert calls == [True]


def test_changed_boot_requires_content_validation(score, tmp_path):
    outbox = tmp_path/'outbox'
    outbox.mkdir()
    (outbox/'a.csv').write_text('ts,value\n0,1\n1,2\n')
    root = tmp_path/'scores'
    glob = score['cmd_run'].__globals__
    glob.update(SCORES=root, LEDGER=root/'scored.jsonl', _boot_id=lambda:'first-boot')
    args = argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True)
    assert score['cmd_run'](args) == 0
    calls = []
    hash_payload = glob['_payload_hash']
    def observed(source):
        calls.append(True)
        return hash_payload(source)
    glob.update(_boot_id=lambda:'second-boot', _payload_hash=observed)
    assert score['cmd_run'](args) == 0
    assert calls == [True]
    rows = [json.loads(line) for line in (root/'scored.jsonl').read_text().splitlines()]
    assert len(rows) == 2 and rows[1]['kind'] == 'payload_observation'
    assert score['cmd_run'](args) == 0
    assert calls == [True]


def test_hashing_mutable_payload_refuses_before_publication(score, tmp_path):
    outbox = tmp_path/'outbox'
    outbox.mkdir()
    path = outbox/'a.csv'
    path.write_text('ts,value\n0,1\n1,2\n')
    root = tmp_path/'scores'
    glob = score['cmd_run'].__globals__
    original = glob['_payload_hash']
    def changed(source):
        digest = original(source)
        path.write_text('ts,value\n0,9\n1,8\n')
        return digest
    glob.update(SCORES=root, LEDGER=root/'scored.jsonl', _payload_hash=changed)
    with pytest.raises(ValueError, match='changed while hashing'):
        score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True))
    assert set(root.iterdir()) == {root/'.score.lock'}


def test_private_payload_snapshot_is_removed_on_processing_failure(score, tmp_path):
    outbox = tmp_path/'outbox'
    outbox.mkdir()
    (outbox/'a.csv').write_text('ts,value\n0,1\n1,2\n')
    root = tmp_path/'scores'
    snapshots = []
    def failed(path, sidecar):
        snapshots.append(path)
        raise RuntimeError('processing failed')
    score['cmd_run'].__globals__.update(SCORES=root, LEDGER=root/'scored.jsonl', score_blob=failed)
    with pytest.raises(RuntimeError, match='processing failed'):
        score['cmd_run'](argparse.Namespace(outbox=str(outbox), limit=0, no_receipt=True))
    assert snapshots and not snapshots[0].exists()
    assert set(root.iterdir()) == {root/'.score.lock'}


def test_observation_cannot_invent_a_missing_score(score, tmp_path):
    ledger = tmp_path/'scored.jsonl'
    ledger.write_text(json.dumps({'kind':'payload_observation','file':'a.csv','bytes':17,
                                 'payload_sha256':'a'*64,'payload_observation':'b'*64,
                                 'sidecar_signature':'absent'})+'\n')
    score['cmd_run'].__globals__['LEDGER'] = ledger
    with pytest.raises(ValueError, match='no earlier content-bound score'):
        with score['ledger_seen']():
            pytest.fail('observation invented an inspection')


def test_unlinked_snapshot_is_readable_by_child_and_closes_after_use(score, tmp_path):
    import os
    import subprocess
    import sys
    path = tmp_path/'voice-synthetic.m4a'
    path.write_bytes(b'synthetic audio bytes')
    score['cmd_run'].__globals__['LEDGER'] = tmp_path/'missing-ledger'
    with score['ledger_seen']() as seen:
        with score['_score_input'](path, 'absent', seen, 'synthetic-boot') as payload:
            assert payload.path.name == path.name and payload.path.is_symlink()
            descriptor = os.readlink(payload.path)
            assert os.readlink(descriptor).endswith(' (deleted)')
            assert payload.path.stat().st_mode & 0o777 == 0o600
            child = subprocess.run([sys.executable, '-c',
                                    'import pathlib,sys;sys.stdout.buffer.write(pathlib.Path(sys.argv[1]).read_bytes())',
                                    str(payload.path)], capture_output=True, timeout=5)
            assert child.returncode == 0 and child.stdout == b'synthetic audio bytes'
        assert not os.path.exists(descriptor) and not payload.path.exists()


IMU_REFERENCE_RESULTS = {'regular': {'score_tremor': {'ok': True,
                              'peak_hz': 7.96,
                              'peak_magnitude': 0.02498,
                              'band_power_4_12': 0.00096,
                              'band_fraction': 1.0,
                              'samples': 2000,
                              'sample_rate_hz': 100.0,
                              'duration_s': 20.0},
             'score_sway': {'ok': True,
                            'units': 'm/s^2 (acceleration, not displacement)',
                            'path_length': 1.6152,
                            'path_length_per_s': 0.0808,
                            'ellipse_area_95': 0.003618,
                            'duration_s': 20.0,
                            'sample_rate_hz': 100.0,
                            'samples': 2000}},
 'jitter': {'score_tremor': {'ok': True,
                             'peak_hz': 7.95,
                             'peak_magnitude': 0.02419,
                             'band_power_4_12': 0.000926,
                             'band_fraction': 1.0,
                             'samples': 2000,
                             'sample_rate_hz': 99.9,
                             'duration_s': 20.0},
            'score_sway': {'ok': True,
                           'units': 'm/s^2 (acceleration, not displacement)',
                           'path_length': 1.6155,
                           'path_length_per_s': 0.08082,
                           'ellipse_area_95': 0.00362,
                           'duration_s': 20.0,
                           'sample_rate_hz': 99.9,
                           'samples': 2000}},
 'malformed': {'score_tremor': {'ok': True,
                                'peak_hz': 7.96,
                                'peak_magnitude': 0.02498,
                                'band_power_4_12': 0.00096,
                                'band_fraction': 1.0,
                                'samples': 2000,
                                'sample_rate_hz': 100.0,
                                'duration_s': 20.0},
               'score_sway': {'ok': True,
                              'units': 'm/s^2 (acceleration, not displacement)',
                              'path_length': 1.6152,
                              'path_length_per_s': 0.0808,
                              'ellipse_area_95': 0.003618,
                              'duration_s': 20.0,
                              'sample_rate_hz': 100.0,
                              'samples': 2000}},
 'short': {'score_tremor': {'ok': False, 'reason': 'only 20 accelerometer samples'},
           'score_sway': {'ok': False, 'reason': 'only 20 accelerometer samples'}}}

@pytest.mark.parametrize('case', ['regular', 'jitter', 'malformed', 'short'])
def test_imu_spill_preserves_existing_numerical_results(score, tmp_path, case):
    import math
    path = tmp_path/'imu.csv'
    with path.open('w') as source:
        source.write('ts,type,x,y,z\n')
        for i in range(20 if case == 'short' else 2000):
            stamp = i*10000000+(i%5)*10000 if case == 'jitter' else i*10000000
            source.write(f'{stamp},accel,{.02*math.sin(i*.03)},{.025*math.cos(i*.05)},{9.81+.1*math.sin(i*.5)}\n')
            if case == 'malformed':
                source.write('invalid,accel,no,signal,here\n')
    for name in ['score_tremor', 'score_sway']:
        assert score['score_trace'](score[name], path) == IMU_REFERENCE_RESULTS[case][name]


def test_imu_source_keeps_exact_rows_and_releases_private_spill(score, tmp_path, monkeypatch):
    import os
    path = tmp_path/'imu.csv'
    with path.open('w') as source:
        source.write('ts,type,x,y,z\n')
        for i in range(4100):
            source.write(f'{i*10000000},accel,{i},2,3\n')
    opened = []
    original = score['tempfile'].TemporaryFile
    def tracked(*args, **kwargs):
        handle = original(*args, **kwargs)
        opened.append(handle)
        return handle
    monkeypatch.setattr(score['tempfile'], 'TemporaryFile', tracked)
    with score['_imu_series'](path) as (times, vectors, rate, duration):
        assert len(times) == len(vectors) == 4100
        assert [times[i] for i in [0, 2047, 2048, 4099, -1]] == [0, 20.47, 20.48, 40.99, 40.99]
        assert list(vectors[2047:2050]) == [(2047.,2.,3.),(2048.,2.,3.),(2049.,2.,3.)]
        assert list(times[-3:][::-1]) == [40.99,40.98,40.97]
        assert rate == pytest.approx(100) and duration == 40.99
        assert os.fstat(opened[0].fileno()).st_mode & 0o777 == 0o600
        assert os.readlink(f'/proc/self/fd/{opened[0].fileno()}').endswith(' (deleted)')
    assert opened and all(handle.closed for handle in opened)


def test_imu_source_failure_closes_spill_without_modifying_trace(score, tmp_path, monkeypatch):
    path = tmp_path/'imu.csv'
    path.write_text('ts,type,x,y,z\n0,accel,1,2,3\n')
    before = path.read_bytes()
    opened = []
    original = score['tempfile'].TemporaryFile
    def tracked(*args, **kwargs):
        handle = original(*args, **kwargs)
        opened.append(handle)
        def failed(*args, **kwargs):
            raise OSError('synthetic storage exhaustion')
        handle.write = failed
        return handle
    monkeypatch.setattr(score['tempfile'], 'TemporaryFile', tracked)
    with pytest.raises(OSError, match='storage exhaustion'):
        with score['_imu_series'](path):
            pytest.fail('storage failure became a measurement')
    assert opened and all(handle.closed for handle in opened)
    assert path.read_bytes() == before


@pytest.mark.parametrize('kind', ['backward', 'duplicate', 'nan-x', 'inf-z'])
def test_imu_spill_preserves_invalid_channel_and_timestamp_rules(score, tmp_path, kind):
    path = tmp_path/'imu.csv'
    with path.open('w') as source:
        source.write('ts,type,x,y,z\n')
        for i in range(80):
            stamp = i*10000000
            if i == 40 and kind in ('backward', 'duplicate'):
                stamp = (38 if kind == 'backward' else 39)*10000000
            x = 'nan' if i == 40 and kind == 'nan-x' else '1'
            z = 'inf' if i == 40 and kind == 'inf-z' else '1'
            source.write(f'{stamp},accel,{x},0,{z}\n')
    tremor = score['score_trace'](score['score_tremor'], path)
    sway = score['score_trace'](score['score_sway'], path)
    assert not tremor['ok']
    assert sway['ok'] == (kind == 'inf-z')  # Sway uses the horizontal channels.
    if kind in ('backward', 'duplicate'):
        assert 'strictly increase' in tremor['reason'] and 'strictly increase' in sway['reason']
    else:
        assert 'non-finite' in tremor['reason']
