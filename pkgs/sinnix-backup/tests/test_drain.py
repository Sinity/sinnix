"""Snapshot drains against real Borg with fake Btrfs, mounts and systemd.

The scenario test runs the drains, the jobs that read their archives and the
nightly sequence in one order, so later steps see the archives, markers and
retained snapshots earlier steps left.
"""

from __future__ import annotations

import copy
import fcntl
import json
import os
import select
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import sinnix_backup
from conftest import fixture_config_data, write_fixture_config
from fakes import FakeHost
from sinnix_backup import borg, cli, drain, markers, snapshots
from sinnix_backup.config import SnapshotSource

# Every task store the fixture configuration declares, plus one tracker it
# does not name, which the restore check must find in the archive.
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
            root_path
            + "/embeddeddolt/"
            + database
            + "/.dolt/HEAD": "0123456789abcdefghijklmnopqrstuv",
            root_path + "/embeddeddolt/" + database + "/issue.json": json.dumps(
                {"id": database + "-task", "title": "Current task"}
            ),
        }
    )
# Real stores list tens of thousands of archive entries. More than a pipe
# buffer of names follows the sinnix metadata file, so a membership test that
# stops reading early fails here as on the host.
for index in range(1500):
    BEADS_STORES[
        "state/tasks/sinnix/.beads/dolt/sinnix/.dolt/noms/" + f"{index:064d}"
    ] = ""

BUSY = "full avg10=20.00 avg60=20.00 avg300=20.00 total=1\n"
SETTLED = "full avg10=0.00 avg60=0.00 avg300=0.00 total=1\n"

# Runs a drain in a child process (started by the fake systemctl) with the
# fixture's I/O pressure file in place of /proc/pressure/io.
CHILD_DRAIN = (
    "import pathlib, sys\n"
    "from sinnix_backup import cli, drain\n"
    "drain.IO_PRESSURE = pathlib.Path(sys.argv[1])\n"
    "sys.exit(cli.main(sys.argv[2:]))\n"
)


def borg_output(*args: str) -> str:
    """Run Borg through the fake command directory, so the call is logged."""
    return subprocess.run(
        ["borg", *args], check=True, text=True, stdout=subprocess.PIPE
    ).stdout


def test_retire_verified_snapshot_before_older_backlog(backup_root, monkeypatch):
    config_path, config = write_fixture_config(backup_root)
    host = FakeHost(backup_root, config.lock_path)
    host.apply(monkeypatch)
    monkeypatch.setenv("TMPDIR", str(config.scratch_directory))
    pressure = backup_root / "io-pressure"
    pressure.write_text(SETTLED)
    monkeypatch.setattr(drain, "IO_PRESSURE", pressure)
    source = config.source("realm")
    repo = config.repository("realm").path
    repo.parent.mkdir(parents=True, exist_ok=True)
    borg_output("init", "--encryption=none", str(repo))
    source.snapshot_directory.mkdir(parents=True)
    dates = ("20260401", "20260402", "20260403", "20260404")
    cuts = [f"realm.{date}T000000+0000" for date in dates]
    previous = host.snapshot(source.snapshot_directory, cuts[0], {"file": "previous"})
    package_parent = str(Path(sinnix_backup.__file__).resolve().parent.parent)
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(filter(None, [package_parent, os.environ.get("PYTHONPATH")])),
    )
    command = [
        sys.executable, "-c", CHILD_DRAIN, str(pressure),
        "drain", "realm", "--config", str(config_path),
    ]
    lock = borg.BorgLock(config.lock_path)
    with lock:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
        try:
            assert process.stdout is not None
            ready, _, _ = select.select([process.stdout], [], [], 15)
            assert ready
            assert "waiting to drain realm" in process.stdout.readline()
            assert process.poll() is None
        finally:
            lock.release()
            try:
                output, _ = process.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                raise
    assert process.returncode == 0, output
    for name in cuts[1:]:
        host.snapshot(source.snapshot_directory, name, {"file": name})
    assert cli.main(["drain", "realm", "--config", str(config_path)]) == 0
    commands = host.commands()
    newest = next(
        i for i, cmd in enumerate(commands)
        if cmd[:2] == ["borg", "create"] and "::realm-" + cuts[-1] in cmd
    )
    older = next(
        i for i, cmd in enumerate(commands)
        if cmd[:2] == ["borg", "create"] and "::realm-" + cuts[1] in cmd
    )
    retired = commands.index(["btrfs", "subvolume", "delete", str(previous)])
    assert newest < retired < older
    assert (source.snapshot_directory / cuts[-1]).exists()


def test_backlog_restart_collision_and_exclusions(backup_root, monkeypatch, capfd):
    root = backup_root
    data = fixture_config_data(root)
    # The production wait is three hours; one second shows the same failure
    # while the lock stays held.
    data["jobs"]["beads"]["lock_wait_seconds"] = 1
    config_path, config = write_fixture_config(root, data)
    host = FakeHost(root, config.lock_path)
    host.apply(monkeypatch)
    monkeypatch.setenv("TMPDIR", str(config.scratch_directory))
    package_parent = str(Path(sinnix_backup.__file__).resolve().parent.parent)
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(filter(None, [package_parent, os.environ.get("PYTHONPATH")])),
    )
    state = config.state_directory
    realm = config.source("realm")
    realm_directory = realm.snapshot_directory
    for label in ("realm", "persist", "genome"):
        config.source(label).snapshot_directory.mkdir(parents=True, exist_ok=True)
    Path(config.jobs["local_dumps_root"]).mkdir(parents=True, exist_ok=True)

    # Btrfs is fake here, so its post-delete I/O pressure is too. It starts
    # busy; one wait settles it.
    pressure = root / "io-pressure"
    pressure.write_text(BUSY)
    monkeypatch.setattr(drain, "IO_PRESSURE", pressure)
    removal = root / "remove-archive-during-settle.json"
    sleeps: list[int] = []

    def settle(seconds):
        assert seconds == 5, seconds
        # A separately opened descriptor models another Borg reader.
        with open(config.lock_path, "a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise AssertionError(
                    "pressure wait ran inside the locked section"
                ) from None
        sleeps.append(seconds)
        if removal.exists():
            request = json.loads(removal.read_text())
            removal.unlink()
            with open(config.lock_path, "a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                host.borg("delete", request["repo"] + "::" + request["archive"])
        pressure.write_text(SETTLED)

    monkeypatch.setattr(
        drain,
        "time",
        SimpleNamespace(time=time.time, monotonic=time.monotonic, sleep=settle),
    )

    for name in ("realm", "persist", "sinex-blobs", "polylogue-state"):
        path = config.repository(name).path
        path.parent.mkdir(parents=True, exist_ok=True)
        borg_output("init", "--encryption=none", str(path))

    def snapshot(name, files, label="realm"):
        return host.snapshot(config.source(label).snapshot_directory, name, files)

    def run(*command, ok=True, path=config_path):
        code = cli.main([*command, "--config", str(path)])
        captured = capfd.readouterr()
        assert (code == 0) == ok, captured.out + captured.err
        return captured

    realm_repo = str(config.repository("realm").path)

    def extract(name, path):
        return borg_output("extract", "--stdout", realm_repo + "::realm-" + name, path)

    old = snapshot(
        "realm.20260402T010000+0000",
        {"old-only": "historical", "same-name": "old"},
    )
    new = snapshot(
        "realm.20260402T033000+0200",
        {
            "same-name": "new",
            "inbox/download": "canonical",
            "tmp/scratch": "scratch",
            "project/sinex/.beads/issues.jsonl": '{"id":"stale-checkout-decoy"}\n',
            **BEADS_STORES,
            "project/build/precious": "source build material",
            "project/dist/precious": "source distribution material",
            "project/node_modules/precious": "source package material",
            "project/target/precious": "source target material",
            "project/.venv/precious": "source environment material",
            "project/.direnv/precious": "source environment state",
            "project/.ruff_cache/precious": "source cache material",
            "project/sample/.pytest_cache/precious": "source test material",
            "project/.cache/precious": "source hidden material",
            "project/compiled.pyc": "source bytecode material",
            "project/inbox/monero/precious": "source inbox material",
            "project/.Trash-1000/precious": "nested trash material",
            "project/tagged/CACHEDIR.TAG": "Signature: 8a477f597d28d172789f06886806bc55\n",
            "project/tagged/precious": "source content beside cache tag",
            "project/marked/.nobackup": "",
            "project/marked/precious": "source content beside backup marker",
            "state/cache/polylogue-backup-hooks/state/polylogue/hooks/sealed.ndjson": "synthetic sealed hook",
        },
    )
    latest_marker = state / "realm.latest-archived"
    assert not latest_marker.exists()
    # A shared directory lock pins only the old audit source. Archiving still
    # completes; deletion resumes after release.
    pin = os.open(old, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(pin, fcntl.LOCK_SH)
        result = run("drain", "realm")
        assert old.exists()
        assert new.exists()
        assert "held by an independent audit" in result.out
    finally:
        os.close(pin)
    run("drain", "realm")
    # Both cuts are archived long after capture, newest first. Borg records
    # source time and selects the newer daily cut although the older cut was
    # archived last.
    repo = realm_repo
    inventory = json.loads(borg_output("list", "--json", repo))["archives"]
    for cut in (old, new):
        entry = next(a for a in inventory if a["name"] == "realm-" + cut.name)
        recorded = datetime.fromisoformat(entry["time"])
        assert int(
            recorded.replace(tzinfo=timezone.utc).timestamp()
        ) == snapshots.snapshot_epoch(cut.name)
    selection = subprocess.run(
        [
            "borg",
            "prune",
            "--dry-run",
            "--list",
            "--keep-daily",
            "1",
            "--glob-archives",
            "realm-*",
            repo,
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    kept = [line for line in selection.stderr.splitlines() if "Keeping archive" in line]
    assert any("realm-" + new.name in line for line in kept), selection.stderr
    assert not any("realm-" + old.name in line for line in kept), selection.stderr
    assert not old.exists()
    assert new.exists()
    assert "snapshot=" + new.name in latest_marker.read_text()
    # Publishing the latest marker does not overwrite the separate
    # last-success marker during a historical backlog.
    completion = state / "realm.last-success"
    assert "snapshot=" + old.name in completion.read_text()
    first_check = json.loads(markers.read_marker(latest_marker)["coverage"])
    assert first_check["proof_mode"] == "created"
    assert first_check["source_hashed_bytes"] == 0
    assert first_check["create_receipt_sha256"]
    # Local dump expiry reads the acknowledged archive itself.
    local_expiry = run("expire-dumps")
    assert '"outcome": "ok"' in local_expiry.out
    assert '"removed_logical_bytes": 0' in local_expiry.out
    assert (
        "realm-" + old.name in borg_output("list", "--short", realm_repo).splitlines()
    )
    assert extract(new.name, "same-name") == "new"
    assert extract(old.name, "old-only") == "historical"
    assert extract(old.name, "same-name") == "old"
    realm_members = borg_output(
        "list", "--short", realm_repo + "::realm-" + new.name
    ).splitlines()
    assert not any(
        path.endswith(
            "state/cache/polylogue-backup-hooks/state/polylogue/hooks/sealed.ndjson"
        )
        for path in realm_members
    )
    for relative, content in {
        "project/build/precious": "source build material",
        "project/dist/precious": "source distribution material",
        "project/node_modules/precious": "source package material",
        "project/target/precious": "source target material",
        "project/.venv/precious": "source environment material",
        "project/.direnv/precious": "source environment state",
        "project/.ruff_cache/precious": "source cache material",
        "project/sample/.pytest_cache/precious": "source test material",
        "project/.cache/precious": "source hidden material",
        "project/compiled.pyc": "source bytecode material",
        "project/inbox/monero/precious": "source inbox material",
        "project/.Trash-1000/precious": "nested trash material",
        "project/tagged/precious": "source content beside cache tag",
        "project/marked/precious": "source content beside backup marker",
    }.items():
        assert extract(new.name, relative) == content
    commands = host.commands()
    realm_creates = [
        entry
        for entry in commands
        if entry[:2] == ["borg", "create"]
        and any(arg.startswith("::realm-") for arg in entry)
    ]
    assert realm_creates
    for entry in realm_creates:
        assert entry[entry.index("--files-cache") + 1] == "ctime,size,inode"
        assert entry[entry.index("--files-changed") + 1] == "ctime"
        assert "--exclude-caches" not in entry
        assert "--exclude-if-present" not in entry
        assert [
            entry[index + 1] for index, arg in enumerate(entry) if arg == "--exclude"
        ] == realm.coverage["borg_excludes"]
    deleted = [
        entry[-1] for entry in commands if entry[:3] == ["btrfs", "subvolume", "delete"]
    ]
    assert deleted == [str(old)]
    assert len(sleeps) == 1

    # A maintenance reader can change which archives exist during pressure
    # settling. The next snapshot is checked again under the lock rather than
    # trusting the earlier prune plan.
    first = snapshot("realm.20260301T000000+0000", {"first": "retained"})
    second = snapshot("realm.20260302T000000+0000", {"second": "retained"})
    host.set_generation(first, 1)
    host.set_generation(second, 1)
    host.set_subvolume_ids({first: 97, second: 98})
    pins = [os.open(path, os.O_RDONLY | os.O_DIRECTORY) for path in (first, second)]
    try:
        for descriptor in pins:
            fcntl.flock(descriptor, fcntl.LOCK_SH)
        run("drain", "realm")
    finally:
        for descriptor in pins:
            os.close(descriptor)
    pressure.write_text(BUSY)
    removal.write_text(json.dumps({"repo": repo, "archive": "realm-" + second.name}))
    run("drain", "realm", ok=False)
    assert not first.exists()
    assert second.exists()
    # Remove the now invalid acknowledgement and recreate its archive through
    # the normal drain before continuing.
    (state / "realm.latest-archived.by-snapshot" / second.name).unlink()
    run("drain", "realm")
    assert not second.exists()

    rollback = snapshot(
        "realm.20260401T233000+0000",
        {"unique": "new bytes after clock rollback"},
    )
    run("drain", "realm")
    assert rollback.exists()
    assert "snapshot=" + rollback.name in latest_marker.read_text()
    created_check = json.loads(markers.read_marker(latest_marker)["coverage"])
    assert created_check["proof_mode"] == "created"
    assert created_check["source_hashed_bytes"] == 0
    assert created_check["create_receipt_sha256"]
    assert extract(rollback.name, "unique") == "new bytes after clock rollback"

    interrupted = snapshot(
        "realm.20260402T080000+0000",
        {
            "same-name": "interrupted proof",
            "project/sinex/.beads/issues.jsonl": '{"id":"stale-checkout-decoy"}\n',
            **BEADS_STORES,
        },
    )
    before = latest_marker.read_bytes()
    host.flag("fail-proof-list").touch()
    run("drain", "realm", ok=False)
    assert latest_marker.read_bytes() == before
    assert interrupted.exists()
    host.flag("fail-proof-list").unlink()
    run("drain", "realm")
    resumed_fields = markers.read_marker(latest_marker)
    assert json.loads(resumed_fields["coverage"])["proof_mode"] == "created"
    # Existing acknowledgements are checked before archive creation, so the
    # failed identity read leaves no new archive to collide with.
    assert resumed_fields["archive"] == "realm-" + interrupted.name
    # A create record can survive a crash before the acknowledgement. The
    # next run reuses that exact archive instead of creating another one.
    acknowledged = markers.read_marker(latest_marker)
    latest_marker.write_bytes(before)
    creates_before = sum(
        1 for entry in host.commands() if entry[:2] == ["borg", "create"]
    )
    run("drain", "realm")
    repeated = markers.read_marker(latest_marker)
    assert repeated["archive"] == acknowledged["archive"]
    assert (
        json.loads(repeated["coverage"])["create_receipt_sha256"]
        == json.loads(acknowledged["coverage"])["create_receipt_sha256"]
    )
    assert (
        sum(1 for entry in host.commands() if entry[:2] == ["borg", "create"])
        == creates_before
    )

    # Retained Sinex stores keep both content-addressed objects and producer
    # state; Polylogue state leaves out its mutable databases.
    sinex_root = Path(config.jobs["sinex_store_paths"][0])
    polylogue_root = Path(config.jobs["polylogue"]["state_root"])
    vector_root = Path(config.jobs["polylogue"]["paid_vector_root"])
    sinex_object = sinex_root / "store/objects/ab/cdef"
    sinex_frame = sinex_root / "spool/producer/frame"
    polylogue_blob = polylogue_root / "blob/objects/cd/ef01"
    for file, content in {
        sinex_object: "synthetic CAS",
        sinex_frame: "synthetic spool frame",
        polylogue_blob: "synthetic blob",
        polylogue_root / "source.db": "mutable database",
        polylogue_root
        / ".salvage-internals-20261008/embeddings.db": "inert synthetic salvage",
        polylogue_root
        / "hooks/codex-session-live.jsonl": '{"event":"sealed-before-create"}\n',
        polylogue_root
        / "hooks/carriers/codex/2026-09-27/4242.ndjson": '{"event":"carrier-before-create"}\n',
        vector_root / "2026-07-10-synthetic-3.db": "synthetic purchased vectors",
    }.items():
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)
    host.register(polylogue_root, generation=1)
    run("sinex-stores")
    hook_files = ["codex-session-live.jsonl", "carriers/codex/2026-09-27/4242.ndjson"]
    monkeypatch.setenv("FAKE_HOOK_ROOT", str(polylogue_root / "hooks"))
    monkeypatch.setenv("FAKE_HOOK_FILES", json.dumps(hook_files))
    host.flag("append-hooks").touch()
    run("polylogue-state")
    host.flag("append-hooks").unlink()
    polylogue_repo = str(config.repository("polylogue-state").path)
    sinex_repo = str(config.repository("sinex-blobs").path)
    for repo_path, base, file, excluded in (
        (sinex_repo, sinex_root, sinex_object, None),
        (sinex_repo, sinex_root, sinex_frame, None),
        (polylogue_repo, polylogue_root, polylogue_blob, "source.db"),
    ):
        names = borg_output("list", "--short", repo_path).splitlines()
        assert len(names) == 1
        entries = borg_output(
            "list", "--short", repo_path + "::" + names[0]
        ).splitlines()
        ending = f"{base.name}/{file.relative_to(base)}"
        member = next(path for path in entries if path.endswith(ending))
        if repo_path == polylogue_repo:
            assert not any("/.salvage-internals-20261008" in path for path in entries)
        contents = borg_output(
            "extract", "--stdout", repo_path + "::" + names[0], member
        )
        assert contents == file.read_text()
        if excluded:
            assert not any(path.endswith("/" + excluded) for path in entries)
    polylogue_archive = borg_output("list", "--short", polylogue_repo).splitlines()[0]
    # The purchased vectors travel in the nightly Polylogue state archive.
    vector_members = [
        path
        for path in borg_output(
            "list", "--short", polylogue_repo + "::" + polylogue_archive
        ).splitlines()
        if path.endswith(f"{vector_root.name}/2026-07-10-synthetic-3.db")
    ]
    assert len(vector_members) == 1
    assert (
        borg_output(
            "extract",
            "--stdout",
            polylogue_repo + "::" + polylogue_archive,
            vector_members[0],
        )
        == "synthetic purchased vectors"
    )
    for relative, original in (
        ("hooks/codex-session-live.jsonl", '{"event":"sealed-before-create"}\n'),
        (
            "hooks/carriers/codex/2026-09-27/4242.ndjson",
            '{"event":"carrier-before-create"}\n',
        ),
    ):
        members = [
            path
            for path in borg_output(
                "list", "--short", polylogue_repo + "::" + polylogue_archive
            ).splitlines()
            if path.endswith("/" + relative)
        ]
        assert len(members) == 1
        archived = borg_output(
            "extract", "--stdout", polylogue_repo + "::" + polylogue_archive, members[0]
        )
        assert archived == original
        assert (
            polylogue_root / relative
        ).read_text() == original + '{"event":"written-during-borg-create"}\n'
    # Repeated archives read the read-only cut directly. No staged hook copy
    # remains, and each successful command deletes its cut.
    hook = polylogue_root / "hooks/codex-session-live.jsonl"
    stable_payload = hook.read_bytes()
    cuts = Path(config.jobs["polylogue"]["hook_cut_directory"]) / "cuts"
    for _ in range(2):
        time.sleep(1.1)
        run("polylogue-state")
        assert hook.read_bytes() == stable_payload
        assert list(cuts.iterdir()) == []
    shutil.rmtree(polylogue_root / "hooks")
    time.sleep(1.1)
    run("polylogue-state")
    archive_names = borg_output("list", "--short", polylogue_repo).splitlines()
    assert len(archive_names) == 4
    empty_hooks_archive = archive_names[-1]
    empty_hook_members = [
        path
        for path in borg_output(
            "list", "--short", polylogue_repo + "::" + empty_hooks_archive
        ).splitlines()
        if "/hooks/" in path
    ]
    assert empty_hook_members == []
    # A Borg lock held past the wait fails the check instead of reporting
    # success without a restore.
    realm_root = root / "realm"
    with open(config.lock_path, "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        run("check-beads-restore", ok=False)
    assert not any(realm_root.rglob("borg_beads_drill.jsonl"))
    run("check-beads-restore")
    log = next(realm_root.rglob("borg_beads_drill.jsonl"))
    records = {
        record["store"]: record
        for record in map(json.loads, log.read_text().splitlines())
    }
    assert sorted(records) == sorted(
        "state/tasks/" + store + "/.beads"
        for store in ("sinnix", "sinex-next", "polylogue-next", "lynchpin", "stashbox")
    )
    sinex = records["state/tasks/sinex-next/.beads"]
    assert sinex["ok"]
    assert sinex["issue"] == {"id": "sxnext-task", "title": "Current task"}
    assert sinex["dolt_commit"] == "0123456789abcdefghijklmnopqrstuv"
    assert "stale-checkout-decoy" not in log.read_text()

    snapshot(
        "realm.20260402T090000+0000",
        {"project/sinex/.beads/issues.jsonl": '{"id":"stale-checkout-decoy"}\n'},
    )
    run("drain", "realm")
    run("check-beads-restore", ok=False)
    snapshot(
        "realm.20260402T100000+0000",
        {
            "project/sinex/.beads/issues.jsonl": '{"id":"stale-checkout-decoy"}\n',
            **BEADS_STORES,
            "state/tasks/sinex-next/.beads/embeddeddolt/sxnext/.dolt/HEAD": "corrupt",
        },
    )
    run("drain", "realm")
    run("check-beads-restore", ok=False)
    assert len(log.read_text().splitlines()) == 5

    older = snapshot("realm.20260403T010000+0000", {"old-only": "older bytes"})
    middle = snapshot("realm.20260403T020000+0000", {"same-name": "middle"})
    fresh = snapshot("realm.20260403T030000+0000", {"same-name": "fresh"})
    run("drain", "realm")
    assert not older.exists()
    assert not middle.exists()
    assert fresh.exists()
    assert "snapshot=" + fresh.name in latest_marker.read_text()
    archives = borg_output("list", "--short", realm_repo).splitlines()
    assert "realm-" + fresh.name in archives
    assert "realm-" + older.name in archives
    assert "realm-" + middle.name in archives
    assert extract(older.name, "old-only") == "older bytes"
    assert extract(middle.name, "same-name") == "middle"

    # A newer creation generation advances freshness despite an older clock
    # name. Deletion resumes only from each snapshot's own acknowledgement,
    # without creating another archive.
    leftover = snapshot("realm.20260403T013000+0000", {"old-only": "leftover"})
    host.flag("fail-delete").touch()
    run("drain", "realm", ok=False)
    assert leftover.exists()
    host.flag("fail-delete").unlink()
    run("drain", "realm")
    assert leftover.exists()
    assert not fresh.exists()
    assert "snapshot=" + leftover.name in latest_marker.read_text()

    pending = snapshot("realm.20260404T010000+0000", {"old-only": "pending"})
    newer = snapshot("realm.20260404T013000+0000", {"same-name": "newer"})
    host.flag("fail-create").touch()
    run("drain", "realm", ok=False)
    assert pending.exists()
    assert newer.exists()
    host.flag("fail-create").unlink()
    host.flag("fail-read").touch()
    run("drain", "realm", ok=False)
    assert pending.exists()
    assert newer.exists()
    host.flag("fail-read").unlink()
    run("drain", "realm")
    assert not pending.exists()
    assert newer.exists()
    assert extract(newer.name, "same-name") == "newer"

    resumed = snapshot("realm.20260405T010000+0000", {"same-name": "resumable"})
    host.flag("fail-delete").touch()
    run("drain", "realm", ok=False)
    assert resumed.exists()
    assert "snapshot=" + resumed.name in latest_marker.read_text()
    host.flag("fail-delete").unlink()
    run("drain", "realm")
    assert resumed.exists()
    assert extract(resumed.name, "same-name") == "resumable"

    stale = snapshot(
        "realm.20260405T020000+0000",
        {
            "inbox/download/media": "canonical download",
            ".pytest_cache/v/cache": "derived pytest data",
            "project/.pytest_cache/v/cache": "derived pytest data",
            "library/models/weights": "re-acquirable weights",
        },
    )
    stale_name = "realm-" + stale.name
    stale_uuid = host.identity(stale)
    transient = stale / "inbox/download/media.borg_part_1"
    transient.write_text("stale archive entry")
    for suffix in ("", "-coverage-v2"):
        borg_output(
            "create",
            "--comment",
            "sinnix-snapshot-v1:" + stale_uuid,
            realm_repo + "::" + stale_name + suffix,
            str(stale) + "/./",
        )
    transient.unlink()
    run("drain", "realm")
    assert stale.exists()
    realm_archives = borg_output("list", "--short", realm_repo).splitlines()
    assert stale_name in realm_archives
    assert stale_name + "-coverage-v2" in realm_archives
    assert stale_name + "-coverage-v3" in realm_archives
    assert (
        borg_output(
            "extract",
            "--stdout",
            realm_repo + "::" + stale_name + "-coverage-v3",
            "inbox/download/media",
        )
        == "canonical download"
    )

    older_gap = snapshot("realm.20260406T023000+0000", {"same-name": "older"})
    gap = snapshot(
        "realm.20260406T030000+0000", {"project/build/precious": "canonical"}
    )
    gap_uuid = host.identity(gap)
    for suffix in ("", "-coverage-v2"):
        borg_output(
            "create",
            "--comment",
            "sinnix-snapshot-v1:" + gap_uuid,
            "--exclude",
            str(gap / "project/build").lstrip("/"),
            realm_repo + "::realm-" + gap.name + suffix,
            str(gap) + "/./",
        )
    host.flag("fail-create").touch()
    result = run("drain", "realm", ok=False)
    assert "borg create failed" in result.err
    assert gap.exists()
    assert older_gap.exists()
    gap_archives = borg_output("list", "--short", realm_repo).splitlines()
    assert "realm-" + gap.name in gap_archives
    assert "realm-" + gap.name + "-coverage-v2" in gap_archives
    assert "realm-" + gap.name + "-coverage-v3" not in gap_archives
    host.flag("fail-create").unlink()
    run("drain", "realm")
    assert gap.exists()
    assert not older_gap.exists()

    collision = snapshot("realm.20260406T033000+0000", {"same-name": "collision"})
    for suffix in ("", "-coverage-v2"):
        borg_output(
            "create",
            repo + "::realm-" + collision.name + suffix,
            str(collision) + "/./",
        )
    run("drain", "realm")
    assert collision.exists()
    collision_archives = borg_output("list", "--short", repo).splitlines()
    assert "realm-" + collision.name in collision_archives
    assert "realm-" + collision.name + "-coverage-v2" in collision_archives
    assert "realm-" + collision.name + "-coverage-v3" in collision_archives
    run("drain", "persist")
    chrome = "home/sinity/.config/chrome-ws"
    persist = snapshot(
        "persist.20260402T040000+0000",
        {
            f"{chrome}/Default/Shared Dictionary/cache/derived": "rebuildable",
            f"{chrome}/Default/WebStorage/7/CacheStorage/site-entry": "site data",
        },
        label="persist",
    )
    persist_repo = str(config.repository("persist").path)
    persist_marker = state / "persist.latest-archived"
    old_name = "persist-" + persist.name
    snapshot_uuid = host.identity(persist)
    tagged = persist / chrome / "Default/WebStorage/7/CacheStorage/.nobackup"
    tagged.write_text("")
    borg_output(
        "create",
        "--comment",
        "sinnix-snapshot-v1:" + snapshot_uuid,
        "--exclude",
        str(persist / chrome / "Default/WebStorage/7/CacheStorage").lstrip("/"),
        persist_repo + "::" + old_name,
        str(persist) + "/./",
    )
    borg_output(
        "create",
        "--comment",
        "sinnix-snapshot-v1:" + snapshot_uuid,
        "--exclude-if-present",
        ".nobackup",
        persist_repo + "::" + old_name + "-coverage-v2",
        str(persist) + "/./",
    )
    host.flag("fail-create").touch()
    run("drain", "persist", ok=False)
    assert persist.exists()
    assert not persist_marker.exists()
    assert borg_output("list", "--short", persist_repo).splitlines() == [
        old_name,
        old_name + "-coverage-v2",
    ]
    host.flag("fail-create").unlink()
    run("drain", "persist")
    assert persist.exists()
    archived = borg_output("list", "--short", persist_repo).splitlines()
    assert old_name in archived
    assert old_name + "-coverage-v2" in archived
    assert old_name + "-coverage-v3" in archived
    assert markers.read_marker(persist_marker)["archive"] == old_name + "-coverage-v3"
    # When the check completed but the marker write was lost, the next run
    # checks v3 again instead of creating v4.
    persist_marker.unlink()
    run("drain", "persist")
    assert borg_output("list", "--short", persist_repo).splitlines() == archived
    assert not any(
        command[:3] == ["borg", "debug", "dump-archive"]
        and command[3] == "::" + old_name
        for command in host.commands()
    )
    kept_path = f"{chrome}/Default/WebStorage/7/CacheStorage/site-entry"
    assert (
        borg_output(
            "extract",
            "--stdout",
            persist_repo + "::" + old_name + "-coverage-v3",
            kept_path,
        )
        == "site data"
    )
    # A realm drain whose snapshot directory is empty refuses: the latest
    # acknowledged snapshot is unavailable, so nothing changes.
    missing = copy.deepcopy(data)
    missing["sources"]["realm"]["snapshot_directory"] = str(root / "realm-empty")
    missing["sources"]["realm"]["bind_path"] = str(root / "bind/realm-empty")
    (root / "realm-empty").mkdir()
    (root / "missing").mkdir()
    missing_path, _ = write_fixture_config(root / "missing", missing)
    marker_before = latest_marker.read_bytes()
    snapshots_before = sorted(realm_directory.iterdir())
    refused = run("drain", "realm", ok=False, path=missing_path)
    assert "verified acknowledgement snapshot is unavailable" in refused.err
    assert latest_marker.read_bytes() == marker_before
    assert sorted(realm_directory.iterdir()) == snapshots_before
    # A separate disk's source shares the repository's data chunks but owns
    # its own acknowledgements and snapshot lifetime.
    genome_old = snapshot(
        "genome.20260401T010000+0000",
        {
            "genotype/original": "supplied input",
            "outputs/analysis": "historical result",
            "cache/reference": "downloaded cache",
            "cache/personal-derived": "retained private derived data",
            ".direnv/environment": "rebuildable environment",
        },
        label="genome",
    )
    run("drain", "genome")
    genome_new = snapshot(
        "genome.20260402T010000+0000",
        {
            "genotype/original": "supplied input",
            "outputs/analysis": "updated result",
            "vendor/report": "irreplaceable report",
            "unfetchable/retained": "unavailable upstream",
        },
        label="genome",
    )
    run("drain", "genome")
    assert not genome_old.exists()
    assert genome_new.exists()
    for cut, expected in [
        (genome_old, "historical result"),
        (genome_new, "updated result"),
    ]:
        assert (
            borg_output(
                "extract", "--stdout", repo + "::genome-" + cut.name, "outputs/analysis"
            )
            == expected
        )
    members = borg_output(
        "list", "--short", repo + "::genome-" + genome_old.name
    ).splitlines()
    assert "genotype/original" in members
    assert "cache/personal-derived" in members
    assert "cache/reference" not in members
    assert not any(x.startswith(".direnv/") for x in members)
    run("drain", "genome")
    assert genome_new.exists(), (
        "the latest audit source on a separate disk survives runs with no work"
    )

    # The nightly sequence: a failed drain unit does not stop later units, and
    # a boot catch-up reuses the completed acquisition.
    for marker, _policy in config.nightly.daily_markers.values():
        marker.unlink(missing_ok=True)
    coordinator_steps = [
        "machine-telemetry-sqlite-backup.service",
        "polylogue-sqlite-backup.service",
        "btrbk.service",
        "borgbackup-job-polylogue-state.service",
        "borgbackup-job-sinex-blobs.service",
        "borgbackup-job-realm.service",
        "borgbackup-job-genome.service",
        "borgbackup-job-persist.service",
        "sinex-backup.service",
        "borgbackup-root-snapshots.service",
        "borgbackup-maintenance.service",
        "borgbackup-coverage-audit-realm.service",
        "borgbackup-local-dumps.service",
    ]
    expected_starts = [["start", unit] for unit in coordinator_steps]
    archive_starts = expected_starts[3:]
    expected_calls = [
        ["systemctl", *call]
        for call in expected_starts[:3]
        + [["stop", "borgbackup-verify.service"]]
        + archive_starts
    ]
    host.set_units(
        {
            f"borgbackup-job-{label}.service": [
                sys.executable,
                "-c",
                CHILD_DRAIN,
                str(pressure),
                "drain",
                label,
                "--config",
                str(config_path),
            ]
            for label in ("realm", "persist", "genome")
        }
    )
    queued_persist = snapshot(
        "persist.20260406T010000+0000",
        {"unique": "persist after retry"},
        label="persist",
    )
    queued_realm = snapshot(
        "realm.20260407T010000+0000", {"unique": "realm after persist failure"}
    )
    queued_genome = snapshot(
        "genome.20260407T010000+0000",
        {"outputs/retained": "genome after retry"},
        label="genome",
    )
    host.flag("fail-unit-borgbackup-job-genome.service").touch()
    host.flag("fail-unit-borgbackup-job-persist.service").touch()
    run("nightly", ok=False)
    assert queued_persist.exists()
    assert queued_realm.exists()
    assert queued_genome.exists()
    calls = [entry for entry in host.commands() if entry[0] == "systemctl"]
    assert calls[-len(expected_calls) :] == expected_calls, (
        "failed drain units do not stop later independent jobs"
    )
    assert not any(
        call[1] == "stop" and "borgbackup-coverage-audit-realm.service" in call
        for call in calls
    )
    host.flag("fail-unit-borgbackup-job-persist.service").unlink()
    host.flag("fail-unit-borgbackup-job-genome.service").unlink()
    previous_calls = len(calls)
    run("nightly")
    assert queued_persist.exists()
    restarted_calls = [entry for entry in host.commands() if entry[0] == "systemctl"][
        previous_calls:
    ]
    assert not any(call[-1] in coordinator_steps[:3] for call in restarted_calls)
    assert restarted_calls[-len(archive_starts) :] == [
        ["systemctl", *call] for call in archive_starts
    ], (
        "a boot catch-up after an interrupted archive phase reuses the completed dumps and snapshots"
    )


def test_choose_archive_name():
    def source(label, replacement_suffix, create_check):
        return SnapshotSource(
            label=label,
            repository=label,
            snapshot_directory=Path("/unused"),
            name_glob=f"{label}.*",
            bind_path=Path("/unused"),
            archive_prefix=label,
            replacement_suffix=replacement_suffix,
            coverage={"borg_excludes": []},
            create_check=create_check,
            files_cache_suffix=None,
            local_snapshots=None,
        )

    realm = source("realm", "-coverage-v3", True)
    persist = source("persist", "-coverage-v2", False)
    genome = source("genome", "", True)
    cut = "realm.20260402T010000+0000"
    plain = "realm-" + cut
    assert drain.choose_archive_name(realm, cut, set()) == plain
    assert drain.choose_archive_name(realm, cut, {plain}) == plain + "-coverage-v3"
    # A create-checked source never resumes a coverage retry archive.
    assert (
        drain.choose_archive_name(
            realm, cut, {plain, plain + "-coverage-v3", plain + "-coverage-v4"}
        )
        == plain + "-coverage-v3"
    )
    cut = "persist.20260402T010000+0000"
    plain = "persist-" + cut
    assert drain.choose_archive_name(persist, cut, set()) == plain
    assert drain.choose_archive_name(persist, cut, {plain}) == plain + "-coverage-v2"
    assert (
        drain.choose_archive_name(persist, cut, {plain + "-coverage-v3"})
        == plain + "-coverage-v3"
    )
    assert (
        drain.choose_archive_name(
            persist,
            cut,
            {
                plain,
                plain + "-coverage-v2",
                plain + "-coverage-v3",
                plain + "-coverage-v4",
            },
        )
        == plain + "-coverage-v4"
    )
    cut = "genome.20260402T010000+0000"
    assert drain.choose_archive_name(genome, cut, {"genome-" + cut}) == "genome-" + cut


def test_stable_host_identity_and_explicit_override(
    tmp_path, monkeypatch, fixture_config
):
    identity = tmp_path / "machine-id"
    monkeypatch.setattr(borg, "MACHINE_ID", identity)
    monkeypatch.delenv("BORG_HOST_ID", raising=False)
    identity.write_text("0123456789abcdef0123456789abcdef\n")
    first, second = borg.host_identity({}), borg.host_identity({})
    assert first == second
    assert first.endswith("@0123456789abcdef0123456789abcdef")
    _, config = fixture_config
    for label in ("realm", "persist", "genome"):
        source = config.source(label)
        repository = config.repository(source.repository)
        env = borg.borg_environment(
            config, repository, files_cache_suffix=source.files_cache_suffix
        )
        assert env["BORG_HOST_ID"] == first
        assert env["BORG_REPO"] == repository.url
        assert env["BORG_PASSCOMMAND"] == f"cat {config.passphrase_path}"
        assert env["BORG_CACHE_DIR"] == str(config.cache_directory)
        assert env.get("BORG_FILES_CACHE_SUFFIX") == source.files_cache_suffix
    identity.unlink()
    assert (
        borg.host_identity({"BORG_HOST_ID": "explicit-fixture@stable"})
        == "explicit-fixture@stable"
    )
    with pytest.raises(ValueError):
        borg.host_identity({})
    identity.write_text("invalid\n")
    with pytest.raises(ValueError):
        borg.host_identity({})


def test_local_snapshots_are_kept_by_count_whether_or_not_archived(
    backup_root, monkeypatch, capfd
):
    """Breaks if deletion waits for an archive, deletes a newer cut, deletes a
    snapshot a backup holds, or touches a source that is not counted."""
    config_path, config = write_fixture_config(backup_root)
    host = FakeHost(backup_root, config.lock_path)
    host.apply(monkeypatch)
    realm = config.source("realm")
    assert realm.local_snapshots is not None
    assert config.source("genome").local_snapshots is None
    keep = realm.local_snapshots
    realm.snapshot_directory.mkdir(parents=True)
    cuts = [
        host.snapshot(realm.snapshot_directory, f"realm.202604{day:02d}T000000+0000", {})
        for day in range(1, keep + 4)
    ]
    held = os.open(cuts[1], os.O_RDONLY | os.O_DIRECTORY)
    fcntl.flock(held, fcntl.LOCK_SH)
    try:
        deleted = drain.retain_newest(config, realm)
    finally:
        os.close(held)
    # Nothing was ever archived; the oldest go anyway, except the held one.
    assert deleted == [cuts[0].name, cuts[2].name]
    assert [path.exists() for path in cuts] == [False, True, False] + [True] * keep
    assert "in use by a backup" in capfd.readouterr().out
    with borg.BorgLock(config.lock_path):
        assert drain.retain_newest(config, realm) == []
    assert cuts[1].exists() and "A Borg job is running" in capfd.readouterr().out
    assert drain.retain_newest(config, realm) == [cuts[1].name]
    assert sorted(p.name for p in realm.snapshot_directory.iterdir()) == [
        path.name for path in cuts[3:]
    ]


def test_a_drain_skips_a_queued_snapshot_deleted_by_count(backup_root, monkeypatch):
    config_path, config = write_fixture_config(backup_root)
    host = FakeHost(backup_root, config.lock_path)
    host.apply(monkeypatch)
    monkeypatch.setenv("TMPDIR", str(config.scratch_directory))
    pressure = backup_root / "io-pressure"
    pressure.write_text(SETTLED)
    monkeypatch.setattr(drain, "IO_PRESSURE", pressure)
    source = config.source("realm")
    repo = config.repository("realm").path
    repo.parent.mkdir(parents=True, exist_ok=True)
    borg_output("init", "--encryption=none", str(repo))
    source.snapshot_directory.mkdir(parents=True)
    older = host.snapshot(source.snapshot_directory, "realm.20260401T000000+0000", {"f": "1"})
    newest = host.snapshot(source.snapshot_directory, "realm.20260402T000000+0000", {"f": "2"})
    archive = drain.archive_snapshot

    def archive_then_count(config, source, snapshot, lock):
        archive(config, source, snapshot, lock)
        if snapshot == newest.name:
            shutil.rmtree(older)  # the count-based deletion ran meanwhile

    monkeypatch.setattr(drain, "archive_snapshot", archive_then_count)
    assert cli.main(["drain", "realm", "--config", str(config_path)]) == 0
    assert newest.exists()
    created = [cmd for cmd in host.commands() if cmd[:2] == ["borg", "create"]]
    assert len(created) == 1
    assert any("::realm-" + newest.name in part for part in created[0])
