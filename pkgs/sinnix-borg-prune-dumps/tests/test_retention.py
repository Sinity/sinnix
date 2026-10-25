import datetime as dt
import hashlib
import importlib.machinery
import io
import json
import os
import subprocess
import types
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[3] / "scripts/sinnix-borg-prune-dumps"
loader = importlib.machinery.SourceFileLoader("dump_retention", str(SCRIPT))
subject = types.ModuleType(loader.name)
loader.exec_module(subject)
NOW = dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc).timestamp()


def dump(root, day, prefix="telemetry", suffix=".sqlite.zst"):
    file = root / f"{prefix}-202609{day:02d}T000000Z{suffix}"
    file.write_bytes(f"synthetic recovery point {day}".encode())
    os.utime(file, (NOW - 30 * 86400, NOW - 30 * 86400))
    return file


def test_plan_keeps_seven_and_preserves_unclassified_files(tmp_path):
    for day in range(1, 11):
        dump(tmp_path, day)
    (tmp_path / "legacy-257.sqlite.zst").write_bytes(b"preserved legacy")
    (tmp_path / "telemetry-20260911T000000Z.sqlite.zst.tmp").write_bytes(b"partial")
    (tmp_path / "telemetry-20260912T000000Z.sqlite.zst").symlink_to("missing")
    (tmp_path / "telemetry-20260913T000000Z.sqlite.zst").touch()
    with opened(tmp_path) as directory:
        rows = subject.candidates(directory, subject.STREAMS["machine-telemetry"], NOW)
    assert [name for name, _ in rows] == [f"telemetry-202609{day:02d}T000000Z.sqlite.zst" for day in range(1, 4)]


class opened:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY)
        return self.fd

    def __exit__(self, *args):
        os.close(self.fd)


def test_recently_modified_old_dump_is_kept(tmp_path):
    files = [dump(tmp_path, day) for day in range(1, 10)]
    os.utime(files[0], (NOW, NOW))
    with opened(tmp_path) as directory:
        rows = subject.candidates(directory, subject.STREAMS["machine-telemetry"], NOW)
    assert [name for name, _ in rows] == [files[1].name]


def test_postgres_environments_keep_their_own_seven(tmp_path):
    for env in ["sinex_prod", "sinex_dev"]:
        for day in range(1, 9):
            dump(tmp_path, day, env, ".dump")
    with opened(tmp_path) as directory:
        rows = subject.candidates(directory, subject.STREAMS["sinex-postgres"], NOW)
    assert len(rows) == 2
    assert all("20260901" in name for name, _ in rows)


@pytest.mark.parametrize("failure", ["mismatch", "changed-file", "changed-archive", "restore-error"])
def test_failed_proof_never_removes_dump(tmp_path, failure):
    file = dump(tmp_path, 1)
    expected = subject.identity(file.stat())

    def restore(size):
        assert size == expected[2]
        if failure == "restore-error":
            raise ValueError("restore failed")
        if failure == "changed-file":
            file.write_bytes(b"changed during restore")
        if failure == "mismatch":
            return "0" * 64
        return hashlib.sha256(b"synthetic recovery point 1").hexdigest()

    def check():
        if failure == "changed-archive":
            raise ValueError("archive replaced")

    with opened(tmp_path) as directory, pytest.raises(ValueError):
        subject.expire(directory, file.name, expected, restore, check, True)
    assert file.exists()


def test_replaced_symlink_is_not_followed(tmp_path):
    file = dump(tmp_path, 1)
    expected = subject.identity(file.stat())
    file.unlink()
    file.symlink_to("preserved")
    (tmp_path / "preserved").write_bytes(b"source")
    with opened(tmp_path) as directory, pytest.raises(OSError):
        subject.expire(directory, file.name, expected, lambda _: "", lambda: None, True)
    assert (tmp_path / "preserved").read_bytes() == b"source"


def test_native_borg_preview_then_apply_and_identity_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(subject.time, "time", lambda: NOW)
    realm = tmp_path / "realm"
    root = realm / "state/db-dumps"
    stream = root / "machine-telemetry"
    stream.mkdir(parents=True)
    for day in range(1, 10):
        dump(stream, day)
    monkeypatch.setenv("BORG_REPO", str(tmp_path / "repository"))
    monkeypatch.setenv("BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK", "yes")
    monkeypatch.setenv("BORG_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SINNIX_BORG_GLOBAL_LOCK_HELD", "1")
    subprocess.run(["borg", "init", "--encryption=none"], check=True)
    name = "realm-realm.20261025T060000+0100"
    uuid = "11111111-2222-3333-4444-555555555555"
    subprocess.run(["borg", "create", "--comment", "sinnix-snapshot-v1:" + uuid, "::" + name, "state"], cwd=realm, check=True)
    archive_id = json.loads(subprocess.check_output(["borg", "list", "--json"]))["archives"][0]["id"]
    subject.run(root, name, archive_id, uuid, False)
    assert len(list(stream.iterdir())) == 9
    subject.run(root, name, archive_id, uuid, True)
    assert len(list(stream.iterdir())) == 7
    with pytest.raises(ValueError):
        subject.archive_identity(name, "0" * 64, uuid)
    with pytest.raises(ValueError):
        subject.restored_digest(name, "state/db-dumps/missing", 1)


def test_missing_owner_lock_refuses_before_reading_archive(tmp_path, monkeypatch):
    monkeypatch.delenv("SINNIX_BORG_GLOBAL_LOCK_HELD", raising=False)
    with pytest.raises(ValueError, match="global Borg lock"):
        subject.run(tmp_path, "ignored", "ignored", "ignored", True)


def test_complete_stdout_with_failed_borg_exit_is_not_a_proof(monkeypatch):
    class FailedRestore:
        stdout = io.BytesIO(b"complete bytes")

        def wait(self):
            return 1

        def poll(self):
            return 1

    monkeypatch.setattr(subject.subprocess, "Popen", lambda *args, **kwargs: FailedRestore())
    with pytest.raises(ValueError, match="successfully"):
        subject.restored_digest("archive", "file", len(b"complete bytes"))
