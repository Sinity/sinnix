"""Borg environment, the shared Borg lock, and the drain's `borg create` command."""

from __future__ import annotations

import fcntl
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import BackupConfig, Repository

MACHINE_ID = Path("/etc/machine-id")
# Part of the recorded create command that a create check compares exactly,
# so it is fixed here rather than read from configuration.
CREATE_LOCK_WAIT = "60"
CUT_NAME = re.compile(r"^[^.]+\.(\d{8}T\d{6}[+-]\d{4})$")


class BorgError(RuntimeError):
    def __init__(self, args: list[str], returncode: int):
        super().__init__(f"borg {args[0] if args else ''} exited with status {returncode}")
        self.returncode = returncode


def host_identity(environment: dict[str, str]) -> str:
    """A stable BORG_HOST_ID, so Borg recognizes and removes its own stale locks.

    Borg's uuid.getnode() fallback can change between invocations.
    """
    preset = environment.get("BORG_HOST_ID")
    if preset:
        return preset
    try:
        machine_id = MACHINE_ID.read_text().strip()
    except OSError as error:
        raise ValueError("machine identity is unavailable; refusing to start Borg") from error
    if re.fullmatch(r"[0-9a-f]{32}", machine_id) is None:
        raise ValueError("invalid machine identity; refusing to start Borg")
    return f"{os.uname().nodename}@{machine_id}"


def borg_environment(
    config: BackupConfig,
    repository: Repository,
    *,
    cache_directory: Path | None = None,
    files_cache_suffix: str | None = None,
) -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(
        BORG_REPO=repository.url,
        BORG_PASSCOMMAND=f"cat {config.passphrase_path}",
        BORG_CACHE_DIR=str(cache_directory or config.cache_directory),
    )
    environment["BORG_HOST_ID"] = host_identity(environment)
    if files_cache_suffix is not None:
        environment["BORG_FILES_CACHE_SUFFIX"] = files_cache_suffix
    return environment


def run_borg(
    args: list[str],
    env: dict[str, str],
    *,
    accepted: Iterable[int] = (0,),
    capture: bool = False,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run `borg <args>`; a status outside `accepted` raises BorgError.

    With `capture`, stdout is returned as text; stderr always goes to the
    journal.
    """
    result = subprocess.run(
        ["borg", *args],
        env=env,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        cwd=cwd,
    )
    if result.returncode not in tuple(accepted):
        raise BorgError(args, result.returncode)
    return result


def initialize_repository(repository: Repository, env: dict[str, str], lock: "BorgLock") -> None:
    """Create the repository directory and, under the lock, the repository itself."""
    repository.path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(repository.path, 0o700)
    if not repository.initialized:
        with lock.held():
            run_borg(["init", "--encryption", "repokey-blake2", repository.url], env)


class BorgLock:
    """The global Borg lock every archive, check and manual Borg command shares.

    Unit ordering cannot serialize commands started outside systemd, so jobs
    coordinate through this flock. Child processes do not inherit it.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._descriptor: int | None = None

    @property
    def taken(self) -> bool:
        return self._descriptor is not None

    def _open(self) -> int:
        return os.open(self.path, os.O_WRONLY | os.O_CREAT, 0o600)

    def try_take(self) -> bool:
        """Take the lock without waiting; False when another process holds it."""
        if self.taken:
            return True
        descriptor = self._open()
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(descriptor)
            return False
        self._descriptor = descriptor
        return True

    def wait(self, timeout_seconds: float | None = None) -> bool:
        """Take the lock, waiting up to `timeout_seconds` (forever when None)."""
        if self.taken:
            return True
        if timeout_seconds is None:
            descriptor = self._open()
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            self._descriptor = descriptor
            return True
        deadline = time.monotonic() + timeout_seconds
        while not self.try_take():
            if time.monotonic() >= deadline:
                return False
            time.sleep(1)
        return True

    def release(self) -> None:
        if self._descriptor is not None:
            fcntl.flock(self._descriptor, fcntl.LOCK_UN)
            os.close(self._descriptor)
            self._descriptor = None

    def held(self) -> "_Held":
        """Context manager: wait for the lock unless this object already holds it."""
        return _Held(self)

    def __enter__(self) -> "BorgLock":
        self.wait()
        return self

    def __exit__(self, *_: Any) -> None:
        self.release()


class _Held:
    def __init__(self, lock: BorgLock):
        self.lock = lock
        self.owned = False

    def __enter__(self) -> BorgLock:
        if not self.lock.taken:
            self.lock.wait()
            self.owned = True
        return self.lock

    def __exit__(self, *_: Any) -> None:
        if self.owned:
            self.lock.release()


def cut_timestamp(snapshot: str) -> str:
    """The UTC creation time a btrbk long-iso snapshot name records.

    Archives carry the source cut time, so retention follows source time even
    when a backlog is archived much later.
    """
    match = CUT_NAME.fullmatch(snapshot)
    if match is None:
        raise ValueError(f"invalid snapshot timestamp: {snapshot}")
    moment = datetime.strptime(match[1], "%Y%m%dT%H%M%S%z").astimezone(timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S")


def archive_timestamp(archive: str) -> str:
    """The cut timestamp named by a realm or genome archive."""
    match = re.match(
        r"^(?P<label>realm|genome)-(?P<cut>(?P=label)\.\d{8}T\d{6}[+-]\d{4})(?:-|$)",
        archive,
    )
    if match is None:
        raise ValueError("archive has no snapshot cut timestamp")
    return cut_timestamp(match["cut"])


def snapshot_create_command(
    binary: str,
    source: Path | str,
    archive: str,
    snapshot_uuid: str,
    coverage: dict[str, Any],
    timestamp: str | None,
) -> list[str]:
    """The drain's `borg create` command; the only place it is built.

    The drain runs it with binary "borg". A create check rebuilds it from a
    recorded command's binary to compare exactly; records made before cut
    timestamps were passed have `timestamp=None`.
    """
    return [
        binary,
        "create",
        "--json",
        "--quick-stats",
        *(["--timestamp", timestamp] if timestamp is not None else []),
        "--files-cache",
        "ctime,size,inode",
        "--files-changed",
        "ctime",
        "--compression",
        "auto,zstd,1",
        "--lock-wait",
        CREATE_LOCK_WAIT,
        "--comment",
        "sinnix-snapshot-v1:" + snapshot_uuid,
        *(
            part
            for pattern in coverage["borg_excludes"]
            for part in ("--exclude", pattern)
        ),
        "::" + archive,
        str(source).rstrip("/") + "/./",
    ]
