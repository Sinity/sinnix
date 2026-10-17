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
