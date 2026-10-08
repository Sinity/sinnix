"""Current link audit catches absent local targets without probing offline stores."""

import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts' / 'sinnix-navigation-audit'


def test_audit_relative_reference_encoded_and_offline_links(tmp_path):
    (tmp_path / 'a b.md').write_text('present')
    document = tmp_path / 'README.md'
    document.write_text('[present](a%20b.md#part)\n[missing](absent.md)\n[ref][name]\n[name]: a%20b.md\n[offline](offline/x.md)\n`[code](not-a-link.md)`\n```\n[example](also-not-a-link.md)\n```\n')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'schema_version': 1, 'documents': [str(document)], 'external_roots': [str(tmp_path / 'offline')]}))
    result = subprocess.run([str(SCRIPT), '--manifest', str(manifest), '--json'], capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report['failures'] == 1
    assert sorted(row['status'] for row in report['links']) == ['external-unprobed', 'missing', 'ok', 'ok']
    document.write_text('[present](a%20b.md)\n')
    assert subprocess.run([str(SCRIPT), '--manifest', str(manifest)], capture_output=True).returncode == 0


def test_retired_managed_child_fails_without_rejecting_native_package_names(tmp_path):
    import os
    from sinnix_lib.layout import COLLECTION_PATHS, MACHINE_LANES, ROOTS

    realm = tmp_path / "realm"
    for name in ROOTS['/realm']:
        (realm / name).mkdir(parents=True, exist_ok=True)
    (realm / 'INVENTORY.md').write_text('Synthetic root')
    for relative in COLLECTION_PATHS.values():
        (realm / relative).mkdir(parents=True, exist_ok=True)
    for relative in MACHINE_LANES.values():
        (realm / 'device/sinnix-prime' / relative).mkdir(parents=True, exist_ok=True)
    (realm / 'library/model/native-package/embeddings').mkdir(parents=True)
    env = {**os.environ, 'LAKE_LINT_ROOT_PREFIX': str(tmp_path)}
    script = SCRIPT.with_name('lake-lint')
    assert subprocess.run([str(script)], env=env, capture_output=True).returncode == 0
    (realm / 'device/sinnix-prime/peripherals').mkdir()
    result = subprocess.run([str(script)], env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert 'RETIRED managed path recreated' in result.stdout


def test_external_collection_is_not_statted(tmp_path, monkeypatch):
    import os
    import runpy

    audit = runpy.run_path(str(SCRIPT))['audit']
    offline = tmp_path / 'offline'
    document = tmp_path / 'README.md'
    document.write_text('[external](offline/x.md)')
    original = os.lstat
    def guarded(path, *args, **kwargs):
        assert not Path(path).is_relative_to(offline)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(os, 'lstat', guarded)
    report = audit({'schema_version': 1, 'documents': [str(document)], 'external_roots': [str(offline)]})
    assert report['failures'] == 0
    assert report['links'][0]['status'] == 'external-unprobed'
