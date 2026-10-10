"""External location diagnoses depend on mounts, before probing payloads."""

import errno
from pathlib import Path
import runpy
import stat
from types import SimpleNamespace

SCRIPT = Path(__file__).parents[3] / "scripts" / "sinnix-file-catalog"


def diagnosis_with_mounts(monkeypatch, mountinfo, path, *, exists=False):
    module = runpy.run_path(str(SCRIPT))
    read_text = Path.read_text
    calls = []

    def read(self, *args, **kwargs):
        if self == Path("/proc/self/mountinfo"):
            return mountinfo
        return read_text(self, *args, **kwargs)

    def observed(self, *args, **kwargs):
        assert self == path
        calls.append(self)
        if exists:
            return SimpleNamespace(st_mode=stat.S_IFREG | 0o600)
        raise FileNotFoundError(errno.ENOENT, "fixture absent", str(self))

    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(Path, "stat", observed)
    monkeypatch.setattr("os.path.ismount", lambda _: False)
    monkeypatch.setitem(module["location_diagnosis"].__globals__, "identity", lambda _: {})
    return module["location_diagnosis"](path, "file"), calls


def test_missing_file_below_mounted_child_is_missing_not_offline(monkeypatch):
    info = "1 0 8:1 / /mnt/fixture-disk rw - ext4 /dev/fixture rw\n"
    result, calls = diagnosis_with_mounts(monkeypatch, info, Path("/mnt/fixture-disk/absent"))
    assert result["status"] == "missing"
    assert len(calls) == 1


def test_offline_placeholder_is_not_probed_as_an_available_file(monkeypatch):
    info = "1 0 0:1 / / rw - tmpfs tmpfs rw\n"
    result, calls = diagnosis_with_mounts(monkeypatch, info, Path("/outer-realm/placeholder"), exists=True)
    assert result["status"] == "offline_mount"
    assert calls == []


def test_similarly_named_directory_is_not_an_external_root(monkeypatch):
    info = "1 0 0:1 / / rw - tmpfs tmpfs rw\n"
    result, calls = diagnosis_with_mounts(monkeypatch, info, Path("/mnt-fixture/absent"))
    assert result["status"] == "missing"
    assert len(calls) == 1


def test_unreadable_mount_table_is_inaccessible_without_probing_payload(monkeypatch):
    module = runpy.run_path(str(SCRIPT))

    def denied():
        raise PermissionError(errno.EACCES, "fixture denies mount visibility")

    def no_probe(*args, **kwargs):
        raise AssertionError("uncertain external source must not be probed")

    monkeypatch.setitem(module["location_diagnosis"].__globals__, "read_mountpoints", denied)
    monkeypatch.setattr(Path, "stat", no_probe)
    result = module["location_diagnosis"](Path("/outer-realm/fixture"), "file")
    assert result["status"] == "inaccessible"
    assert "cannot observe external mounts" in result["reason"]
