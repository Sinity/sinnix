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
    def guard(original):
        def guarded(path, *args, **kwargs):
            if isinstance(path, (str, os.PathLike)):
                assert not Path(path).is_relative_to(offline)
            return original(path, *args, **kwargs)
        return guarded
    monkeypatch.setattr(os, 'lstat', guard(os.lstat))
    monkeypatch.setattr(os, 'stat', guard(os.stat))
    report = audit({'schema_version': 1, 'documents': [str(document)], 'external_roots': [str(offline)]})
    assert report['failures'] == 0
    assert report['links'][0]['status'] == 'external-unprobed'


def test_mounted_child_links_are_probed_and_missing_links_fail(tmp_path, monkeypatch):
    import runpy

    external = tmp_path / "external"
    mounted = external / "fixture-disk"
    mounted.mkdir(parents=True)
    (mounted / "present.md").write_text("present")
    document = tmp_path / "README.md"
    document.write_text("[present](external/fixture-disk/present.md)\n[absent](external/fixture-disk/absent.md)\n")
    read_text = Path.read_text

    def read(self, *args, **kwargs):
        if self == Path("/proc/self/mountinfo"):
            return f"1 0 8:1 / {mounted} rw - ext4 /dev/fixture rw\n"
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    audit = runpy.run_path(str(SCRIPT))["audit"]
    report = audit({"schema_version": 1, "documents": [str(document)], "external_roots": [str(external)]})
    assert report["failures"] == 1
    assert [row["status"] for row in report["links"]] == ["ok", "missing"]


def test_mountinfo_tab_escape_matches_a_real_link(tmp_path, monkeypatch):
    import runpy

    external = tmp_path / "external\troot"
    external.mkdir()
    (external / "present.md").write_text("present")
    document = tmp_path / "README.md"
    document.write_text("[present](external%09root/present.md)\n")
    escaped = str(external).replace("\t", r"\011")
    read_text = Path.read_text

    def read(self, *args, **kwargs):
        if self == Path("/proc/self/mountinfo"):
            return f"1 0 8:1 / {escaped} rw - ext4 /dev/fixture rw\n"
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    report = runpy.run_path(str(SCRIPT))["audit"]({"schema_version": 1, "documents": [str(document)], "external_roots": [str(external)]})
    assert report["links"][0]["status"] == "ok"


def test_unreadable_document_does_not_abort_other_entrances(tmp_path, monkeypatch):
    import runpy
    denied = tmp_path / "denied.md"
    denied.write_text("fixture")
    readable = tmp_path / "README.md"
    readable.write_text("[present](denied.md)")
    original = Path.read_text
    def read(path, *args, **kwargs):
        if path == denied:
            raise PermissionError("synthetic read denial")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read)
    result = runpy.run_path(str(SCRIPT))["audit"]({"schema_version": 1, "documents": [str(denied), str(readable)]})
    assert result["failures"] == 1
    assert [row["status"] for row in result["links"]] == ["denied-document", "ok"]


def test_lookup_errors_do_not_claim_absent_targets(tmp_path, monkeypatch):
    import errno
    import runpy
    document = tmp_path / "README.md"
    document.write_text("[denied](denied)\n[error](error)\n[missing](missing)")
    original = Path.stat
    def observed(path, *args, **kwargs):
        if path == tmp_path / "denied":
            raise PermissionError(errno.EACCES, "synthetic denial")
        if path == tmp_path / "error":
            raise OSError(errno.EIO, "synthetic lookup failure")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "stat", observed)
    result = runpy.run_path(str(SCRIPT))["audit"]({"schema_version": 1, "documents": [str(document)]})
    assert result["failures"] == 3
    assert [row["status"] for row in result["links"]] == ["denied", "inaccessible", "missing"]


def test_offline_entrance_is_not_probed(tmp_path, monkeypatch):
    import runpy
    external = tmp_path / "external"
    document = external / "README.md"
    def no_probe(*args, **kwargs):
        raise AssertionError("offline entrance must not be statted")
    monkeypatch.setattr(Path, "stat", no_probe)
    result = runpy.run_path(str(SCRIPT))["audit"]({"schema_version": 1, "documents": [str(document)], "external_roots": [str(external)]})
    assert result["failures"] == 0
    assert result["links"] == [{"document": str(document), "status": "external-unprobed"}]


def test_wrong_type_and_invalid_encoding_entrances_are_explicit(tmp_path):
    import runpy
    document = tmp_path / "broken.md"
    document.write_bytes(b"\xff")
    result = runpy.run_path(str(SCRIPT))["audit"]({"schema_version": 1, "documents": [str(tmp_path), str(document)]})
    assert result["failures"] == 2
    assert [row["status"] for row in result["links"]] == ["wrong-type-document", "inaccessible-document"]


def test_malformed_links_do_not_abort_remaining_targets(tmp_path):
    import runpy
    document = tmp_path / "README.md"
    document.write_text("[bad URL](http://[invalid)\n[null path](no%00file.md)\n[present](README.md)")
    result = runpy.run_path(str(SCRIPT))["audit"]({"schema_version": 1, "documents": [str(document)]})
    assert result["failures"] == 2
    assert [row["status"] for row in result["links"]] == ["invalid-link", "invalid-link", "ok"]


def test_null_document_does_not_abort_other_entrances(tmp_path):
    import runpy
    document = tmp_path / "README.md"
    document.write_text("[present](README.md)")
    invalid = str(document) + "\0bad"
    result = runpy.run_path(str(SCRIPT))["audit"]({"schema_version": 1, "documents": [invalid, str(document)]})
    assert result["failures"] == 1
    assert [row["status"] for row in result["links"]] == ["invalid-document", "ok"]


def test_invalid_utf8_link_cannot_match_replacement_filename(tmp_path):
    import runpy
    (tmp_path / "\ufffd.md").write_text("neutral fixture")
    (tmp_path / "caf\u00e9.md").write_text("neutral fixture")
    document = tmp_path / "README.md"
    document.write_text("[invalid](%FF.md)\n[unicode](caf%C3%A9.md)\n[present](README.md)")
    result = runpy.run_path(str(SCRIPT))["audit"]({"schema_version": 1, "documents": [str(document)]})
    assert result["failures"] == 1
    assert [row["status"] for row in result["links"]] == ["invalid-link", "ok", "ok"]


def test_percent_encoded_backslash_is_filename_content(tmp_path):
    import runpy

    (tmp_path / "literal\\(name).md").write_text("present")
    (tmp_path / "escaped(name).md").write_text("present")
    document = tmp_path / "README.md"
    document.write_text(
        "[literal](literal%5C%28name%29.md)\n"
        "[escaped](escaped\\(name\\).md)\n"
    )
    audit = runpy.run_path(str(SCRIPT))["audit"]
    report = audit({"schema_version": 1, "documents": [str(document)]})
    assert [row["status"] for row in report["links"]] == ["ok", "ok"]
    assert report["links"][0]["destination"] == str(tmp_path / "literal\\(name).md")


def test_automount_placeholder_is_not_probed(tmp_path, monkeypatch):
    import runpy

    external = tmp_path / "external"
    offline = external / "offline"
    document = tmp_path / "README.md"
    document.write_text("[offline](external/offline/item.md)\n")
    original_read = Path.read_text
    original_stat = Path.stat

    def read(path, *args, **kwargs):
        if path == Path("/proc/self/mountinfo"):
            return (
                "1 0 8:1 / / rw - ext4 /dev/root rw\n"
                f"2 1 0:2 / {offline} rw - autofs systemd-1 rw\n"
            )
        return original_read(path, *args, **kwargs)

    def guarded_stat(path, *args, **kwargs):
        assert not path.is_relative_to(offline), "offline payload must not be probed"
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(Path, "stat", guarded_stat)
    audit = runpy.run_path(str(SCRIPT))["audit"]
    report = audit({"schema_version": 1, "documents": [str(document)], "external_roots": [str(external)]})
    assert report["links"][0]["status"] == "external-unprobed"


def test_unknown_mount_state_fails_external_checks_without_probing_payload(tmp_path, monkeypatch):
    import runpy

    external = tmp_path / 'external'
    remote = external / 'README.md'
    document = tmp_path / 'README.md'
    document.write_text('[local](README.md)\n[external](external/payload.md)')
    original_stat = Path.stat
    original_read = Path.read_text

    def no_external_stat(path, *args, **kwargs):
        assert not path.is_relative_to(external), 'unknown mount payload must not be probed'
        return original_stat(path, *args, **kwargs)

    for failure in ('denied', 'malformed'):
        def read(path, *args, **kwargs):
            if path == Path('/proc/self/mountinfo'):
                if failure == 'denied':
                    raise PermissionError('synthetic mountinfo denial')
                return 'malformed mountinfo record\n'
            assert not path.is_relative_to(external), 'unknown mount document must not be read'
            return original_read(path, *args, **kwargs)

        monkeypatch.setattr(Path, 'stat', no_external_stat)
        monkeypatch.setattr(Path, 'read_text', read)
        result = runpy.run_path(str(SCRIPT))['audit']({
            'schema_version': 1, 'documents': [str(remote), str(document)],
            'external_roots': [str(external)],
        })
        assert result['failures'] == 2
        assert [row['status'] for row in result['links']] == ['inaccessible-document', 'ok', 'inaccessible']
        assert all('cannot observe external mounts' in row['reason']
                   for row in result['links'] if row['status'] != 'ok')


def test_symlink_parent_target_uses_filesystem_traversal(tmp_path):
    import runpy

    real = tmp_path / "real"
    (real / "child").mkdir(parents=True)
    (tmp_path / "alias").symlink_to(real / "child", target_is_directory=True)
    (real / "present.md").write_text("actual destination")
    (tmp_path / "absent.md").write_text("lexical decoy")
    document = tmp_path / "README.md"
    document.write_text(
        "[present](alias/../present.md)\n[absent](alias/../absent.md)\n"
    )
    report = runpy.run_path(str(SCRIPT))["audit"]({
        "schema_version": 1, "documents": [str(document)],
    })
    assert [row["status"] for row in report["links"]] == ["ok", "missing"]
    assert report["failures"] == 1


def test_symlink_parent_document_reads_actual_entrance(tmp_path):
    import runpy

    real = tmp_path / "real"
    (real / "child").mkdir(parents=True)
    (tmp_path / "alias").symlink_to(real / "child", target_is_directory=True)
    (real / "README.md").write_text("[present](present.md)")
    (real / "present.md").write_text("actual destination")
    (tmp_path / "README.md").write_text("[decoy](missing.md)")
    document = tmp_path / "alias" / ".." / "README.md"
    report = runpy.run_path(str(SCRIPT))["audit"]({
        "schema_version": 1, "documents": [str(document)],
    })
    assert report["failures"] == 0
    assert [row["target"] for row in report["links"]] == ["present.md"]


def test_missing_symlink_parent_document_cannot_use_lexical_decoy(tmp_path):
    import runpy

    real = tmp_path / "real"
    (real / "child").mkdir(parents=True)
    (tmp_path / "alias").symlink_to(real / "child", target_is_directory=True)
    (tmp_path / "README.md").write_text("lexical decoy")
    document = tmp_path / "alias" / ".." / "README.md"
    report = runpy.run_path(str(SCRIPT))["audit"]({
        "schema_version": 1, "documents": [str(document)],
    })
    assert report["failures"] == 1
    assert [row["status"] for row in report["links"]] == ["missing-document"]


def test_parent_components_keep_offline_mount_policy(tmp_path, monkeypatch):
    import runpy

    external = tmp_path / "external"
    document = tmp_path / "README.md"
    document.write_text("[offline](middle/../external/payload.md)")
    remote_document = tmp_path / "middle" / ".." / "external" / "README.md"
    original_stat = Path.stat

    def no_external_probe(path, *args, **kwargs):
        assert path not in (remote_document, document.parent / "middle/../external/payload.md")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", no_external_probe)
    result = runpy.run_path(str(SCRIPT))["audit"]({
        "schema_version": 1, "documents": [str(remote_document), str(document)],
        "external_roots": [str(external)],
    })
    assert result["failures"] == 0
    assert [row["status"] for row in result["links"]] == ["external-unprobed"] * 2
