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
    original_iterdir, original_stat = Path.iterdir, os.stat
    unrelated_stats = []
    def entries(path):
        if path == outbox:
            yield from (outbox / f'ignored-{n}.bin' for n in range(10000))
        yield from original_iterdir(path)
    def observed_stat(path, *args, **kwargs):
        if not isinstance(path, int):
            candidate = Path(os.fsdecode(path))
            if candidate.parent == outbox and candidate.suffix not in ('.csv', '.m4a'):
                unrelated_stats.append(candidate.name)
        return original_stat(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'iterdir', entries)
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
