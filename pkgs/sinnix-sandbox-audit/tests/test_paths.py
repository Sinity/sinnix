import json
import os
import subprocess
import sys
import shutil
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts/sinnix-sandbox-audit'


def run_audit(tmp_path, path, props, audit_failure=False, inventory=None, find_failure=False, systemctl_failure=False, journal=None):
    fake = tmp_path / 'bin'
    fake.mkdir()
    systemctl = fake / 'systemctl'
    systemctl.write_text(f'#!{sys.executable}\n' + ('raise SystemExit(5)\n' if systemctl_failure else '') + '''import json,os,sys
if 'show' not in sys.argv:raise SystemExit(0 if os.environ.get('TEST_TIMER') == 'yes' else 1)
print(json.loads(os.environ['TEST_PROPERTIES']).get(sys.argv[sys.argv.index('-p')+1], 'not-found' if sys.argv[sys.argv.index('-p')+1] == 'LoadState' else ''))
''')
    systemctl.chmod(0o700)
    audit = fake / 'auditctl'
    audit.write_text('#!/bin/sh\n' + ('exit 1\n' if audit_failure else 'echo "enabled 1"\n'))
    audit.chmod(0o700)
    if find_failure:
        finder = fake / 'find'
        actual_find = shutil.which('find')
        finder.write_text(f'#!{sys.executable}\n' + f'''import os,sys
if sys.argv[1] == {(path if find_failure is True else str(find_failure))!r}:raise SystemExit(1)
os.execv({actual_find!r},[{actual_find!r},*sys.argv[1:]])
''')
        finder.chmod(0o700)
    if journal is not None:
        journalctl = fake / 'journalctl'
        journalctl.write_text(f'#!{sys.executable}\n' +
                              f'import sys\nprint({journal[0]!r})\nsys.exit({journal[1]})\n')
        journalctl.chmod(0o700)
    source = tmp_path / 'inventory.json'
    source.write_text(inventory if inventory is not None else json.dumps({'surfaces': {'fixture': {'unit': 'fixture.service', 'manager': 'system', 'captures': [{'path': path}]}}}))
    captures = tmp_path / 'captures'
    captures.mkdir(exist_ok=True)
    output = tmp_path / 'out.jsonl'
    env = {**os.environ, 'PATH': str(fake)+':'+os.environ['PATH'], 'TEST_PROPERTIES': json.dumps(props), 'TEST_TIMER': 'yes' if journal is not None else 'no', 'SINNIX_RUNTIME_INVENTORY': str(source), 'SINNIX_CAPTURES_ROOT': str(captures), 'SINNIX_SANDBOX_AUDIT_OUT': str(output)}
    result = subprocess.run(['bash', str(SCRIPT), '--quiet'], env=env, capture_output=True, text=True)
    rows = [json.loads(line) for line in output.read_text().splitlines()] if output.exists() else []
    return result, rows


@pytest.mark.parametrize('path,system,home,private_tmp,blocked', [
    ('/realm/audit-fixture', 'full', 'yes', 'no', False),
    ('/etc/audit-fixture', 'full', 'no', 'no', True),
    ('/etc/audit-fixture', 'yes', 'no', 'no', False),
    ('/usr/audit-fixture', 'yes', 'no', 'no', True),
    ('/home/audit-fixture', 'no', 'read-only', 'no', True),
    ('/realm/audit-fixture', 'no', 'read-only', 'no', False),
    ('/realm/audit-fixture', 'strict', 'no', 'no', True),
    ('/tmp/audit-fixture', 'strict', 'no', 'yes', False),
    ('/proc/audit-fixture', 'strict', 'no', 'no', False),
    ('/usr/local/audit-fixture', 'no', 'no', 'no', False),
])
def test_only_protected_subtrees_are_reported(tmp_path, path, system, home, private_tmp, blocked):
    result, rows = run_audit(tmp_path, path, {'ProtectSystem': system, 'ProtectHome': home, 'PrivateTmp': private_tmp})
    assert result.returncode == 0, result.stderr
    assert any(row['kind']=='confined-from-own-output' for row in rows) is blocked


@pytest.mark.parametrize('rw,state', [('/', ''), ('/realm/', ''), ('', 'first second')])
def test_writable_paths_and_multiple_state_directories(tmp_path, rw, state):
    path = '/var/lib/second/audit-fixture' if state else '/realm/audit-fixture'
    result, rows = run_audit(tmp_path, path, {'ProtectSystem':'strict', 'ReadWritePaths':rw, 'StateDirectory':state})
    assert result.returncode == 0, result.stderr
    assert not any(row['kind']=='confined-from-own-output' for row in rows)


def test_unreadable_audit_status_is_explicit_and_other_checks_continue(tmp_path):
    result, rows = run_audit(tmp_path, '/realm/audit-fixture', {'ProtectSystem':'strict'}, audit_failure=True)
    assert result.returncode == 0, result.stderr
    assert any(row['kind']=='audit-unavailable' for row in rows)
    assert any(row['kind']=='confined-from-own-output' for row in rows)


@pytest.mark.parametrize('inventory', ['not JSON', '{"surfaces": []}'])
def test_invalid_inventory_fails_without_claiming_clean(tmp_path, inventory):
    result, rows = run_audit(tmp_path, '/realm/audit-fixture', {}, inventory=inventory)
    assert result.returncode != 0
    assert 'invalid runtime inventory' in result.stderr
    assert not rows


@pytest.mark.parametrize('unreadable', [False, True])
def test_empty_and_unreadable_directories_are_distinct(tmp_path, unreadable):
    lane = tmp_path / 'lane'
    lane.mkdir()
    result, rows = run_audit(tmp_path, str(lane), {}, find_failure=unreadable)
    assert result.returncode == 0, result.stderr
    assert any(row['kind']=='lane-empty' for row in rows) is not unreadable
    assert any(row['kind']=='lane-unavailable' for row in rows) is unreadable


@pytest.mark.parametrize('failed_target', ['lane', 'root', None])
def test_undeclared_lane_scan_failures_are_not_abandonment(tmp_path, failed_target):
    captures = tmp_path / 'captures'
    lane = captures / 'undeclared'
    lane.mkdir(parents=True)
    target = lane if failed_target == 'lane' else captures
    result, rows = run_audit(tmp_path, '/synthetic/missing-capture', {},
                             find_failure=target if failed_target else False)
    assert result.returncode == 0, result.stderr
    abandoned = [row for row in rows if row['kind'] == 'lane-abandoned']
    unavailable = [row for row in rows if row['kind'] == 'lane-unavailable']
    if failed_target:
        assert not abandoned
        assert [row['path'] for row in unavailable] == [str(target)]
    else:
        assert [row['path'] for row in abandoned] == [str(lane)]
        assert not unavailable


@pytest.mark.parametrize("case", ["denied-parent", "wrong-parent", "missing", "empty-file"])
def test_capture_lookup_errors_are_not_missing(tmp_path, case):
    parent = tmp_path / "parent"
    if case == "wrong-parent":
        parent.write_text("fixture")
    else:
        parent.mkdir()
    lane = parent / "lane"
    if case == "denied-parent":
        lane.write_text("retained")
        parent.chmod(0)
    elif case == "empty-file":
        lane.touch()
    try:
        result, rows = run_audit(tmp_path, str(lane), {})
        assert result.returncode == 0, result.stderr
        actual = [row["kind"] for row in rows if row["path"] == str(lane)]
        expected = {"denied-parent": "lane-unavailable", "wrong-parent": "lane-unavailable",
                    "missing": "lane-missing", "empty-file": "lane-empty"}[case]
        assert actual == [expected]
    finally:
        if case == "denied-parent":
            parent.chmod(0o700)


def test_unavailable_systemd_refuses_publication(tmp_path):
    output = tmp_path / "out.jsonl"
    previous = '{"kind":"previous-verified-finding"}\n'
    output.write_text(previous)
    result, rows = run_audit(tmp_path, '/synthetic/capture', {}, systemctl_failure=True)
    assert result.returncode != 0
    assert 'cannot inspect system unit fixture.service property ProtectSystem' in result.stderr
    assert output.read_text() == previous
    assert 'no findings' not in result.stdout


@pytest.mark.parametrize("journal,expected", [(('', 0), 'never-succeeded'),
                                             (('Finished fixture service', 0), None),
                                             (('partial journal output', 5), 'journal-unavailable')])
def test_unreadable_journal_is_not_failed_execution(tmp_path, journal, expected):
    result, rows = run_audit(tmp_path, '/synthetic/missing-capture',
                             {'LoadState': 'loaded'}, journal=journal)
    assert result.returncode == 0, result.stderr
    diagnoses = [r['kind'] for r in rows if r['kind'] in ('never-succeeded', 'journal-unavailable')]
    assert diagnoses == ([expected] if expected else [])
