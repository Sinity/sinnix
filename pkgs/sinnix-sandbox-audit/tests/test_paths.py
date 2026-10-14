import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts/sinnix-sandbox-audit'


def run_audit(tmp_path, path, props, audit_failure=False, inventory=None):
    fake = tmp_path / 'bin'
    fake.mkdir()
    systemctl = fake / 'systemctl'
    systemctl.write_text(f'#!{sys.executable}\n' + '''import json,os,sys
if 'show' not in sys.argv:raise SystemExit(1)
print(json.loads(os.environ['TEST_PROPERTIES']).get(sys.argv[sys.argv.index('-p')+1],''))
''')
    systemctl.chmod(0o700)
    audit = fake / 'auditctl'
    audit.write_text('#!/bin/sh\n' + ('exit 1\n' if audit_failure else 'echo "enabled 1"\n'))
    audit.chmod(0o700)
    source = tmp_path / 'inventory.json'
    source.write_text(inventory if inventory is not None else json.dumps({'surfaces': {'fixture': {'unit': 'fixture.service', 'manager': 'system', 'captures': [{'path': path}]}}}))
    captures = tmp_path / 'captures'
    captures.mkdir()
    output = tmp_path / 'out.jsonl'
    env = {**os.environ, 'PATH': str(fake)+':'+os.environ['PATH'], 'TEST_PROPERTIES': json.dumps(props), 'SINNIX_RUNTIME_INVENTORY': str(source), 'SINNIX_CAPTURES_ROOT': str(captures), 'SINNIX_SANDBOX_AUDIT_OUT': str(output)}
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
