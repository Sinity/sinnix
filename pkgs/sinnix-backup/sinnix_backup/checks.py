"""The weekly repository integrity check and the Beads restore check."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from . import markers
from .borg import BorgLock, borg_environment, run_borg
from .config import BackupConfig
from .jobs import STATE_GROUP, take_or_skip

# Each weekly pass ends three hours after it starts, before the next archive window.
INTEGRITY_SECONDS = 3 * 3600
BEADS_METADATA = re.compile(r"^state/tasks/[^/]+/\.beads/metadata\.json$")
DOLT_DATABASE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
DOLT_COMMIT = re.compile(r"^[0-9a-v]{32}$")


def local_timestamp() -> str:
    """`date -Iseconds`: local time with its UTC offset."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def compact_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def check_repositories(config: BackupConfig) -> int:
    """Check repository segments within a time budget per repository, then run sinnix-borg-check.

    `--max-duration` makes each pass incremental: successive weekly runs
    cycle through a repository without holding its lock for a day.
    """
    settings = config.jobs["integrity"]
    env = borg_environment(config, config.repository("persist"))
    lock = BorgLock(config.lock_path)
    if not take_or_skip(lock, "Borg repository check"):
        return 0
    try:
        run_id = os.environ.get("INVOCATION_ID") or f"borg-check-{int(time.time())}"
        start = int(time.time())
        deadline = start + INTEGRITY_SECONDS

        def write_record(state: str) -> None:
            markers.make_directory(config.state_directory, 0o750, STATE_GROUP)
            record = {
                "operation_kind": "integrity_check",
                "run_id": run_id,
                "expected_jobs": settings["expected_jobs"],
                "start_epoch": start,
                "deadline_epoch": deadline,
                "state": state,
                "updated_at": local_timestamp(),
            }
            markers.publish_marker(
                Path(settings["record"]), compact_json(record) + "\n"
            )

        # Any failure before completion records "failed"; a later
        # sinnix-borg-check failure leaves the completed record in place.
        try:
            write_record("running")
            for entry in settings["repositories"]:
                run_borg(
                    [
                        "check",
                        "--repository-only",
                        "--max-duration",
                        str(entry["seconds"]),
                        config.repository(entry["repository"]).url,
                    ],
                    env,
                )
        except BaseException:
            write_record("failed")
            raise
        write_record("completed")
    finally:
        # sinnix-borg-check takes the same lock in its own process; holding
        # it here would make that check always skip.
        lock.release()
    return subprocess.run(
        ["sinnix-borg-check"],
        env={**env, "SINNIX_BORG_GLOBAL_LOCK": str(config.lock_path)},
    ).returncode


def _restore_record(
    restore_root: Path,
    store: str,
    project_uuid: str | None,
    archive: str,
    env: dict[str, str],
) -> dict[str, Any]:
    """Check one restored store and read its latest commit and first task offline."""
    beads = restore_root / store

    def fail(reason: str) -> ValueError:
        return ValueError(f"Beads store {store} from {archive}: {reason}")

    metadata_path = beads / "metadata.json"
    if not metadata_path.is_file() or metadata_path.stat().st_size == 0:
        raise fail("metadata.json is missing or empty")
    metadata = json.loads(metadata_path.read_text())
    if not isinstance(metadata, dict):
        raise fail("metadata.json is not an object")
    config_path = beads / "config.yaml"
    if not config_path.is_file() or config_path.stat().st_size == 0:
        raise fail("config.yaml is missing or empty")
    database = metadata.get("dolt_database")
    if not isinstance(database, str) or DOLT_DATABASE_NAME.fullmatch(database) is None:
        raise fail("metadata.json names no valid Dolt database")
    if project_uuid and metadata.get("project_id") != project_uuid:
        raise fail("metadata.json names another project")
    # A server-mode store keeps its databases under dolt/, an embedded one
    # under embeddeddolt/.
    database_root = beads / (
        "dolt" if metadata.get("dolt_mode") == "server" else "embeddeddolt"
    )
    if not (database_root / database / ".dolt").is_dir():
        raise fail("the Dolt database did not restore")
    # A restored server configuration can name a live port, so the database
    # opens from a separate data directory without that configuration.
    offline_root = restore_root / "offline" / store
    offline_root.mkdir(parents=True, exist_ok=True)
    (database_root / database).rename(offline_root / database)

    def first_row(query: str) -> Any:
        output = subprocess.run(
            [
                "dolt",
                "--data-dir",
                str(offline_root),
                "--use-db",
                database,
                "sql",
                "-q",
                query,
                "-r",
                "json",
            ],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout
        return json.loads(output)["rows"][0]

    commit = first_row("SELECT commit_hash FROM dolt_log LIMIT 1").get("commit_hash")
    if not isinstance(commit, str) or DOLT_COMMIT.fullmatch(commit) is None:
        raise fail("the Dolt log has no valid commit")
    issue = first_row("SELECT id, title FROM issues ORDER BY id LIMIT 1")
    if issue.get("id") in (None, "") or issue.get("title") in (None, ""):
        raise fail("the issues table has no readable task")
    return {
        "ts": local_timestamp(),
        "type": "beads_restore_drill",
        "archive": archive,
        "store": store,
        "dolt_commit": commit,
        "issue": issue,
        "ok": True,
    }


def check_beads_restore(config: BackupConfig) -> int:
    """Restore every Beads store from the latest realm archive and read each one offline.

    Declared stores must be in the archive; every other store the archive
    holds under state/tasks is checked too. The log gets records only after
    every store restored.
    """
    settings = config.jobs["beads"]
    repository = config.repository("realm")
    env = borg_environment(config, repository)
    wait = settings["lock_wait_seconds"]
    lock = BorgLock(config.lock_path)
    if not lock.wait(wait):
        print(
            f"another Borg operation held the lock for {wait} s; the Beads restore check did not run",
            file=sys.stderr,
        )
        return 1
    try:
        archives = sorted(
            run_borg(
                ["list", "--short", "--glob-archives", "realm-*", repository.url],
                env,
                capture=True,
            ).stdout.splitlines()
        )
        if not archives:
            print(
                "no realm Borg archive is available for the Beads restore check",
                file=sys.stderr,
            )
            return 1
        archive = archives[-1]
        location = f"{repository.url}::{archive}"
        declared = {
            store["path"]: store["project_uuid"] for store in settings["stores"]
        }
        # Only store metadata files are listed: a listing of every file under
        # state/tasks holds millions of names in memory.
        members = run_borg(
            [
                "list",
                "--short",
                "--pattern",
                r"+ re:^state/tasks/[^/]+/\.beads/metadata\.json$",
                *(
                    part
                    for path in declared
                    for part in ("--pattern", f"+ pf:{path}/metadata.json")
                ),
                "--pattern",
                "- re:.*",
                location,
                "state/tasks",
                *(path for path in declared if not path.startswith("state/tasks/")),
            ],
            env,
            capture=True,
        ).stdout.splitlines()
        archived = set(members)
        stores = sorted(
            set(declared)
            | {
                member.removesuffix("/metadata.json")
                for member in members
                if BEADS_METADATA.match(member)
            }
        )
        for store in stores:
            if f"{store}/metadata.json" not in archived:
                print(f"Beads store {store} is missing from {archive}", file=sys.stderr)
                return 1
        # The stores together are a few gigabytes, too much for the /tmp tmpfs.
        restore_parent = Path(settings["restore_parent"])
        restore_parent.mkdir(parents=True, exist_ok=True)
        restore_root = Path(
            tempfile.mkdtemp(prefix="beads-restore.", dir=restore_parent)
        )
        try:
            run_borg(["extract", location, *stores], env, cwd=restore_root)
            records = [
                _restore_record(restore_root, store, declared.get(store), archive, env)
                for store in stores
            ]
        finally:
            shutil.rmtree(restore_root)
        log = Path(settings["log"])
        markers.make_directory(log.parent, 0o755)
        text = "".join(compact_json(record) + "\n" for record in records)
        with log.open("a") as stream:
            stream.write(text)
        print(text, end="")
        return 0
    finally:
        lock.release()
