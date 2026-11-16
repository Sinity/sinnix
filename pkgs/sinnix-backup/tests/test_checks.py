"""The Beads restore check and the weekly repository integrity check."""

import fcntl
import json
import os
import sys
from pathlib import Path

import pytest

from conftest import fixture_config_data, write_fixture_config
from fakes import FakeHost
from sinnix_backup import cli

COMMIT = "0123456789abcdefghijklmnopqrstuv"

# Every task store the fixture configuration declares, plus one store it
# does not name, which the check must find in the archive.
BEADS_STORES = {}
for store, database, project in (
    ("sinnix", "sinnix", None),
    ("sinex-next", "sxnext", "9a23622c-4af5-4f3a-99d9-467edd816653"),
    ("polylogue-next", "plnext", "d06821b6-158a-4b18-add6-6d26e936a97e"),
    ("lynchpin", "lynchpin", None),
    ("stashbox", "stashbox", None),
):
    metadata = {"dolt_database": database}
    if project:
        metadata["project_id"] = project
    root_path = "state/tasks/" + store + "/.beads"
    BEADS_STORES.update(
        {
            root_path + "/metadata.json": json.dumps(metadata),
            root_path + "/config.yaml": "issue-prefix: " + database,
            root_path + "/embeddeddolt/" + database + "/.dolt/HEAD": COMMIT,
            root_path + "/embeddeddolt/" + database + "/issue.json": json.dumps(
                {"id": database + "-task", "title": "Current task"}
            ),
        }
    )
# More than a pipe buffer of names follows the sinnix metadata file, so a
# membership test that stops reading early fails here as on the host.
for index in range(1500):
    BEADS_STORES["state/tasks/sinnix/.beads/dolt/sinnix/.dolt/noms/" + f"{index:064d}"] = ""
DECOY = {"project/sinex/.beads/issues.jsonl": '{"id":"stale-checkout-decoy"}\n'}


@pytest.fixture
def beads(backup_root, monkeypatch):
    """The relocated policy with a one-second lock wait, a realm repository and fakes."""
    data = fixture_config_data(backup_root)
    data["jobs"]["beads"]["lock_wait_seconds"] = 1
    config_path, config = write_fixture_config(backup_root, data)
    host = FakeHost(backup_root, config.lock_path)
    host.apply(monkeypatch)
    repository = config.repository("realm")
    repository.path.parent.mkdir(parents=True, exist_ok=True)
    host.borg("init", "--encryption=none", repository.url)
    return config_path, config, host


def add_realm_archive(host, config, root, name, files):
    source = root / "archive-sources" / name
    for relative, data in files.items():
        file = source / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(data)
    # Archive paths are relative to the snapshot root, as the realm drain stores them.
    tops = sorted({relative.split("/")[0] for relative in files})
    host.borg("create", f"{config.repository('realm').url}::realm-{name}", *tops, cwd=source)


def check(config_path):
    return cli.main(["check-beads-restore", "--config", str(config_path)])


def test_beads_restore_records_every_store_only_after_all_restore(beads, backup_root, capfd):
    config_path, config, host = beads
    log = Path(config.jobs["beads"]["log"])
    add_realm_archive(host, config, backup_root, "realm.20260402T010000+0000", {**DECOY, **BEADS_STORES})

    # A held Borg lock past the wait fails the check instead of reporting
    # success without a restore.
    with config.lock_path.open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        assert check(config_path) == 1
    assert "the Beads restore check did not run" in capfd.readouterr().err
    assert not log.exists()

    assert check(config_path) == 0
    printed = capfd.readouterr().out
    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert printed == log.read_text()
    evidence = {record["store"]: record for record in records}
    assert sorted(evidence) == sorted(
        "state/tasks/" + store + "/.beads"
        for store in ("sinnix", "sinex-next", "polylogue-next", "lynchpin", "stashbox")
    )
    sinex = evidence["state/tasks/sinex-next/.beads"]
    assert list(sinex) == ["ts", "type", "archive", "store", "dolt_commit", "issue", "ok"]
    assert sinex["ok"] is True
    assert sinex["type"] == "beads_restore_drill"
    assert sinex["archive"] == "realm-realm.20260402T010000+0000"
    assert sinex["issue"] == {"id": "sxnext-task", "title": "Current task"}
    assert sinex["dolt_commit"] == COMMIT
    assert "stale-checkout-decoy" not in log.read_text()
    assert list(Path(config.jobs["beads"]["restore_parent"]).glob("beads-restore.*")) == []

    # The latest archive lacks the stores: the check fails and logs nothing.
    add_realm_archive(host, config, backup_root, "realm.20260402T090000+0000", DECOY)
    assert check(config_path) == 1
    assert "is missing from realm-realm.20260402T090000+0000" in capfd.readouterr().err

    # One corrupt store fails the whole check, with no record for the others.
    add_realm_archive(
        host,
        config,
        backup_root,
        "realm.20260402T100000+0000",
        {
            **DECOY,
            **BEADS_STORES,
            "state/tasks/sinex-next/.beads/embeddeddolt/sxnext/.dolt/HEAD": "corrupt",
        },
    )
    assert check(config_path) == 1
    assert len(log.read_text().splitlines()) == 5
    assert list(Path(config.jobs["beads"]["restore_parent"]).glob("beads-restore.*")) == []


@pytest.fixture
def integrity(fixture_config, backup_root, monkeypatch):
    """Fakes, every checked repository initialized, and a sinnix-borg-check that logs the lock state."""
    config_path, config = fixture_config
    host = FakeHost(backup_root, config.lock_path)
    host.apply(monkeypatch)
    for entry in config.jobs["integrity"]["repositories"]:
        repository = config.repository(entry["repository"])
        repository.path.parent.mkdir(parents=True, exist_ok=True)
        host.borg("init", "--encryption=none", repository.url)
    tools = backup_root / "check-bin"
    tools.mkdir()
    check_log = backup_root / "logs/sinnix-borg-check"
    (tools / "sinnix-borg-check").write_text(
        f"""#!{sys.executable}
import fcntl, os
with open(os.environ["SINNIX_BORG_GLOBAL_LOCK"], "a") as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = "free"
    except BlockingIOError:
        state = "held"
with open({str(check_log)!r}, "a") as log:
    log.write(state + "\\n")
"""
    )
    (tools / "sinnix-borg-check").chmod(0o755)
    monkeypatch.setenv("PATH", f"{tools}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("INVOCATION_ID", "fixture-invocation")
    return config_path, config, host, check_log


def test_integrity_check_records_completion_then_releases_the_lock(integrity):
    config_path, config, host, check_log = integrity
    assert cli.main(["check-repositories", "--config", str(config_path)]) == 0
    record = json.loads(Path(config.jobs["integrity"]["record"]).read_text())
    assert list(record) == [
        "operation_kind",
        "run_id",
        "expected_jobs",
        "start_epoch",
        "deadline_epoch",
        "state",
        "updated_at",
    ]
    assert record["operation_kind"] == "integrity_check"
    assert record["run_id"] == "fixture-invocation"
    assert record["expected_jobs"] == config.jobs["integrity"]["expected_jobs"]
    assert record["deadline_epoch"] == record["start_epoch"] + 3 * 3600
    assert record["state"] == "completed"
    checks = [command for command in host.commands() if command[:2] == ["borg", "check"]]
    assert checks == [
        ["borg", "check", "--repository-only", "--max-duration", str(entry["seconds"]), config.repository(entry["repository"]).url]
        for entry in config.jobs["integrity"]["repositories"]
    ]
    assert check_log.read_text() == "free\n"


def test_integrity_check_failure_records_failed_and_skips_partial_check(integrity):
    config_path, config, host, check_log = integrity
    (config.repository("sinex-keys").path / "config").unlink()
    assert cli.main(["check-repositories", "--config", str(config_path)]) == 1
    record = json.loads(Path(config.jobs["integrity"]["record"]).read_text())
    assert record["state"] == "failed"
    assert not check_log.exists()


def test_integrity_check_skips_while_the_lock_is_held(integrity, capfd):
    config_path, config, host, check_log = integrity
    with config.lock_path.open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        assert cli.main(["check-repositories", "--config", str(config_path)]) == 0
    assert "skipping Borg repository check and keeping work queued" in capfd.readouterr().out
    assert not Path(config.jobs["integrity"]["record"]).exists()
    assert not check_log.exists()
