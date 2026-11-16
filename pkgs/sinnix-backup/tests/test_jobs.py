"""Direct-path, hourly and root-snapshot jobs against real Borg and fake host commands."""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

from fakes import FakeHost
from sinnix_backup import cli, markers


@pytest.fixture
def host(fixture_config, backup_root, monkeypatch):
    config_path, config = fixture_config
    fake = FakeHost(backup_root, config.lock_path)
    fake.apply(monkeypatch)
    # Jobs that create their repository use repokey encryption.
    config.passphrase_path.parent.mkdir(parents=True, exist_ok=True)
    config.passphrase_path.write_text("synthetic fixture passphrase\n")
    return fake


def run(config_path, command):
    return cli.main([command, "--config", str(config_path)])


def write_files(root, files):
    for relative, data in files.items():
        file = Path(root) / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(data)


def force_create_status(host, backup_root, monkeypatch, archive_prefix, status):
    """Make each successful `borg create ::<archive_prefix>...` exit with `status`."""
    tools = backup_root / "status-bin"
    tools.mkdir(exist_ok=True)
    (tools / "borg").write_text(
        f"""#!{sys.executable}
import subprocess, sys
args = sys.argv[1:]
code = subprocess.run([{str(host.bin / "borg")!r}, *args]).returncode
if code == 0 and args[:1] == ["create"] and any(arg.startswith({"::" + archive_prefix!r}) for arg in args):
    code = {status}
sys.exit(code)
"""
    )
    (tools / "borg").chmod(0o755)
    monkeypatch.setenv("PATH", f"{tools}{os.pathsep}{os.environ['PATH']}")


def creates(host, archive_prefix):
    return [
        command
        for command in host.commands()
        if command[:2] == ["borg", "create"] and any(arg.startswith("::" + archive_prefix) for arg in command)
    ]


def archive_name(command):
    return next(arg[2:] for arg in command if arg.startswith("::"))


def live_sources(config):
    settings = config.jobs["hourly"]
    tasks = Path(settings["tasks_root"])
    spool = Path(settings["sinex_spools"][0])
    write_files(tasks, {"sinnix/.beads/metadata.json": "{}", "migration-backups/copy": "old", "sinnix/dolt-server.log": "log"})
    write_files(spool, {"frame": "synthetic spool frame"})
    return tasks, spool


@pytest.mark.parametrize("status", [0, 100])
def test_hourly_live_accepts_only_the_changed_file_warning(fixture_config, host, backup_root, monkeypatch, capfd, status):
    config_path, config = fixture_config
    tasks, spool = live_sources(config)
    force_create_status(host, backup_root, monkeypatch, "live-small-", status)
    assert run(config_path, "hourly-live") == 0
    output = capfd.readouterr().out
    [command] = creates(host, "live-small-")
    archive = archive_name(command)
    assert command == [
        "borg",
        "create",
        "--compression",
        "auto,zstd,3",
        "--lock-wait",
        "60",
        "--stats",
        "--exclude",
        str(tasks).lstrip("/") + "/migration-backups",
        "--exclude",
        "**/dolt-server.log",
        "::" + archive,
        str(tasks),
        str(spool),
    ]
    marker = markers.read_marker(config.state_file("live-small.last-success"))
    assert list(marker) == ["archive", "epoch", "elapsed_seconds"]
    assert marker["archive"] == archive
    assert f"backup_phase=done label=live-small archive={archive} elapsed_seconds=" in output
    accepted = "live-small: accepted files that changed while read (Dolt journals and spools)"
    assert (accepted in output) == (status == 100)


@pytest.mark.parametrize("status", [1, 2, 101, 104])
def test_hourly_live_fails_on_any_other_status(fixture_config, host, backup_root, monkeypatch, status):
    config_path, config = fixture_config
    live_sources(config)
    force_create_status(host, backup_root, monkeypatch, "live-small-", status)
    assert run(config_path, "hourly-live") != 0
    assert not config.state_file("live-small.last-success").exists()


def hourly_persist_setup(config, host):
    host.borg("init", "--encryption=none", config.repository("persist").url)
    # The cut lives under /persist/.btrfs; a real snapshot omits it, so the
    # fixture source starts without that directory.
    write_files(config.jobs["hourly"]["persist_source"], {"etc/keep": "synthetic persist state"})
    return Path(config.jobs["hourly"]["persist_cut"]), config.source("persist").bind_path


def host_steps(host):
    return [
        command
        for command in host.commands()
        if command[0] in ("btrfs", "mount", "umount") or command[:2] == ["borg", "create"]
    ]


def test_hourly_persist_archives_the_cut_then_releases_it(fixture_config, host, capfd):
    config_path, config = fixture_config
    cut, bind = hourly_persist_setup(config, host)
    assert run(config_path, "hourly-persist") == 0
    [command] = creates(host, "hourly-persist-")
    archive = archive_name(command)
    assert host_steps(host) == [
        ["btrfs", "-q", "subvolume", "snapshot", "-r", config.jobs["hourly"]["persist_source"], str(cut)],
        ["mount", "--bind", str(cut), str(bind)],
        [
            "borg",
            "create",
            "--files-cache",
            "ctime,size,inode",
            "--files-changed",
            "ctime",
            "--compression",
            "auto,zstd,1",
            "--lock-wait",
            "60",
            "--stats",
            *(part for pattern in config.source("persist").coverage["borg_excludes"] for part in ("--exclude", pattern)),
            "::" + archive,
            f"{bind}/./",
        ],
        ["umount", str(bind)],
        ["btrfs", "-q", "subvolume", "delete", str(cut)],
    ]
    assert not cut.exists()
    assert str(bind) not in json.loads((host.state / "mounts.json").read_text())
    assert "etc/keep" in host.borg("list", "--short", f"{config.repository('persist').url}::{archive}").stdout.splitlines()
    marker = markers.read_marker(config.state_file("persist-hourly.last-success"))
    assert list(marker) == ["archive", "epoch", "elapsed_seconds"]
    assert marker["archive"] == archive
    assert f"backup_phase=done label=persist-hourly archive={archive}" in capfd.readouterr().out


def test_hourly_persist_releases_the_cut_after_a_failed_archive(fixture_config, host):
    config_path, config = fixture_config
    cut, bind = hourly_persist_setup(config, host)
    host.flag("fail-create").touch()
    assert run(config_path, "hourly-persist") != 0
    assert host_steps(host)[-2:] == [["umount", str(bind)], ["btrfs", "-q", "subvolume", "delete", str(cut)]]
    assert not cut.exists()
    assert not config.state_file("persist-hourly.last-success").exists()


def test_sinex_stores_archive_and_daily_marker(fixture_config, host):
    config_path, config = fixture_config
    [store] = config.jobs["sinex_store_paths"]
    write_files(store, {"store/objects/ab/cdef": "synthetic CAS", "spool/producer/frame": "synthetic spool frame"})
    assert run(config_path, "sinex-stores") == 0
    [command] = creates(host, "sinex-blobs-")
    archive = archive_name(command)
    assert command == ["borg", "create", "--compression", "auto,zstd,1", "--lock-wait", "60", "::" + archive, store]
    marker_path, policy = config.nightly.daily_markers["borgbackup-job-sinex-blobs.service"]
    marker = markers.read_marker(marker_path)
    assert list(marker) == ["archive", "epoch", "policy_sha256"]
    assert marker["archive"] == archive
    assert marker["policy_sha256"] == policy
    members = host.borg("list", "--short", f"{config.repository('sinex-blobs').url}::{archive}").stdout
    assert store.lstrip("/") + "/store/objects/ab/cdef" in members.splitlines()


@pytest.mark.parametrize("status", [1, 100])
def test_sinex_stores_accept_no_warning(fixture_config, host, backup_root, monkeypatch, status):
    config_path, config = fixture_config
    write_files(config.jobs["sinex_store_paths"][0], {"store/object": "synthetic CAS"})
    force_create_status(host, backup_root, monkeypatch, "sinex-blobs-", status)
    assert run(config_path, "sinex-stores") != 0
    assert not config.nightly.daily_markers["borgbackup-job-sinex-blobs.service"][0].exists()


ROOT_SNAPSHOT = "root.20260913T101010"


def test_root_snapshots_archive_then_delete(fixture_config, host, backup_root, monkeypatch, capfd):
    config_path, config = fixture_config
    device = backup_root / "root-device"
    write_files(
        device / ".snapshots" / ROOT_SNAPSHOT,
        {"etc/keep": "synthetic root state", "tmp/scratch": "excluded", "var/cache/item": "excluded"},
    )
    host.map_device(config.jobs["root_snapshots"]["device"], device)
    # The job mounts the device at a temporary directory; fix its path so the
    # snapshot inside the mounted copy has a subvolume identity.
    mount_root = backup_root / "root-mount"
    real_mkdtemp = tempfile.mkdtemp

    def mkdtemp(*args, **kwargs):
        if args or kwargs:
            return real_mkdtemp(*args, **kwargs)
        mount_root.mkdir()
        return str(mount_root)

    monkeypatch.setattr(tempfile, "mkdtemp", mkdtemp)
    snapshot = mount_root / ".snapshots" / ROOT_SNAPSHOT
    host.register(snapshot, generation=7)
    snapshot_uuid = host.identity(snapshot)
    archive = "root-" + ROOT_SNAPSHOT

    assert run(config_path, "root-snapshots") == 0
    assert creates(host, "root-") == [
        [
            "borg",
            "create",
            "--timestamp",
            "2026-09-13T10:10:10",
            "--compression",
            "auto,zstd,1",
            "--comment",
            "sinnix-snapshot-v1:" + snapshot_uuid,
            "--lock-wait",
            "60",
            *(part for path in config.source("root").coverage for part in ("--exclude", f"{snapshot}/{path}")),
            "::" + archive,
            f"{snapshot}/./",
        ]
    ]
    commands = host.commands()
    create_index = next(i for i, command in enumerate(commands) if command[:2] == ["borg", "create"])
    assert ["btrfs", "subvolume", "delete", str(snapshot)] in commands[create_index:]
    assert commands[-1] == ["umount", str(mount_root)]
    assert not mount_root.exists()
    repository = config.repository("root-snapshots").url
    assert "etc/keep" in host.borg("list", "--short", f"{repository}::{archive}").stdout.splitlines()

    # The next mount shows the snapshot again: its archive exists, so it is
    # checked and deleted without a second archive.
    capfd.readouterr()
    assert run(config_path, "root-snapshots") == 0
    assert f"Archive {archive} already exists; verifying snapshot {ROOT_SNAPSHOT}" in capfd.readouterr().out
    assert len(creates(host, "root-")) == 1
    assert host.commands().count(["btrfs", "subvolume", "delete", str(snapshot)]) == 2


def test_polylogue_state_archives_hooks_from_a_cut(fixture_config, host, monkeypatch):
    config_path, config = fixture_config
    settings = config.jobs["polylogue"]
    state = Path(settings["state_root"])
    hook = "hooks/codex-session-live.jsonl"
    original = '{"event":"written-before-create"}\n'
    write_files(
        state,
        {
            "blob/objects/cd/ef01": "synthetic blob",
            "source.db": "mutable database",
            ".salvage-internals-20261008/embeddings.db": "inert synthetic salvage",
            hook: original,
        },
    )
    vectors = Path(settings["paid_vector_root"])
    write_files(vectors, {"2026-07-10-synthetic-3.db": "synthetic purchased vectors"})
    host.register(state, generation=1)
    # Borg reads the cut while writers keep appending to the live hooks.
    host.flag("append-hooks").touch()
    monkeypatch.setenv("FAKE_HOOK_ROOT", str(state / "hooks"))
    monkeypatch.setenv("FAKE_HOOK_FILES", json.dumps(["codex-session-live.jsonl"]))

    assert run(config_path, "polylogue-state") == 0
    [command] = creates(host, "polylogue-state-")
    archive = archive_name(command)
    prefix = str(state).lstrip("/")
    assert command[:-1] == [
        "borg",
        "create",
        "--compression",
        "auto,zstd,1",
        "--lock-wait",
        "60",
        *(part for pattern in settings["state_excludes"] for part in ("--exclude", f"{prefix}/{pattern}")),
        "--exclude",
        f"{state}/hooks/**",
        "::" + archive,
        str(state),
        str(vectors),
    ]
    assert command[-1].endswith(f"/./{prefix}/hooks")
    location = f"{config.repository('polylogue-state').url}::{archive}"
    members = host.borg("list", "--short", location).stdout.splitlines()
    assert prefix + "/blob/objects/cd/ef01" in members
    assert not any(path.endswith("/source.db") for path in members)
    assert not any("/.salvage-internals-20261008" in path for path in members)
    [vector] = [path for path in members if path.endswith("/2026-07-10-synthetic-3.db")]
    assert host.borg("extract", "--stdout", location, vector).stdout == "synthetic purchased vectors"
    [archived_hook] = [path for path in members if path.endswith("/" + hook)]
    assert host.borg("extract", "--stdout", location, archived_hook).stdout == original
    assert (state / hook).read_text() == original + '{"event":"written-during-borg-create"}\n'
    assert list((Path(settings["hook_cut_directory"]) / "cuts").iterdir()) == []
    marker_path, policy = config.nightly.daily_markers["borgbackup-job-polylogue-state.service"]
    marker = markers.read_marker(marker_path)
    assert list(marker) == ["archive", "epoch", "policy_sha256"]
    assert marker["archive"] == archive
    assert marker["policy_sha256"] == policy
