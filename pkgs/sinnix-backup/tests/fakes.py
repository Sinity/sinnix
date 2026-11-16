"""Fake host commands for package tests: Btrfs, mounts and systemd, with real Borg.

Only Btrfs, mounts, systemctl and dolt are replaced; Borg is the real binary.
Every fake call (and every Borg call) is appended as a JSON argument list to
`logs/commands` under the fake root. Subvolume identities live in JSON files
there, so `btrfs subvolume show` answers like the real command.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

FAKE_COMMAND = r"""#!PYTHON
import fcntl, json, os, pathlib, shutil, subprocess, sys, uuid
root = pathlib.Path(os.environ["FAKE_ROOT"])
state = root / "fake"
command = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]


def load(name):
    path = state / name
    return json.loads(path.read_text()) if path.exists() else {}


def save(name, value):
    (state / name).write_text(json.dumps(value))


def flag(name):
    return (state / name).exists()


def check_global_lock(held):
    # A separately opened descriptor models another Borg process.
    with open(os.environ["FAKE_LOCK"], "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            assert held, (command, args, "ran outside the locked section")
        else:
            assert not held, (command, args, "ran inside the locked section")


with (root / "logs/commands").open("a") as log:
    log.write(json.dumps([command, *args]) + "\n")

if command == "borg":
    if args[0] == "create" and any(arg.startswith(("::realm-", "::persist-", "::genome-")) for arg in args):
        check_global_lock(True)
    if args[0] == "create" and flag("fail-create"):
        sys.exit(2)
    if args[0] == "create" and flag("append-hooks") and any(arg.startswith("::polylogue-state-") for arg in args):
        hooks = pathlib.Path(os.environ["FAKE_HOOK_ROOT"])
        if hooks.is_dir():
            for relative in json.loads(os.environ.get("FAKE_HOOK_FILES", "[]")):
                with (hooks / relative).open("a") as stream:
                    stream.write('{"event":"written-during-borg-create"}\n')
    if args[0] == "debug" and flag("fail-read"):
        sys.exit(2)
    if args[:2] == ["list", "--json"] and (flag("fail-read") or flag("fail-proof-list")):
        sys.exit(2)
    os.execv(REAL_BORG, [REAL_BORG, *args])

if command == "systemctl":
    if args[0] == "stop":
        sys.exit(0)
    unit = args[-1]
    if flag("fail-unit-" + unit):
        sys.exit(1)
    argv = load("units.json").get(unit)
    if argv is None:
        sys.exit(0)
    sys.exit(subprocess.run(argv, env=os.environ).returncode)

if command == "findmnt":
    print(json.dumps({"filesystems": [{"target": args[-1], "fstype": "btrfs"}]}))
    sys.exit(0)

if command == "mountpoint":
    sys.exit(0 if args[-1] in load("mounts.json") else 1)

identities = load("identities.json")
generations = load("generations.json")
if command == "mount":
    source, target = args[-2:]
    source = load("devices.json").get(source, source)
    subprocess.run(["cp", "-a", source + "/.", target], check=True)
    mounts = load("mounts.json")
    mounts[target] = source
    save("mounts.json", mounts)
    if source in identities:
        identities[target] = identities[source]
        generations[target] = generations[source]
elif command == "umount":
    target = pathlib.Path(args[-1])
    mounts = load("mounts.json")
    mounts.pop(str(target), None)
    save("mounts.json", mounts)
    shutil.rmtree(target)
    target.mkdir()
    identities.pop(str(target), None)
    generations.pop(str(target), None)
elif command == "btrfs":
    while args and args[0] == "-q":
        args = args[1:]
    parents = load("parents.json")
    if args[:3] == ["filesystem", "show", "--raw"]:
        print("Label: 'fixture'  uuid: 22222222-2222-2222-2222-222222222222")
    elif args[:2] == ["subvolume", "list"]:
        pass
    elif args[:3] == ["subvolume", "snapshot", "-r"]:
        source, target = args[3:]
        shutil.copytree(source, target, symlinks=True)
        identities[target] = str(uuid.uuid4())
        generations[target] = generations.get(source, 1)
        parents[target] = identities.get(source, "-")
        save("parents.json", parents)
    elif args[:2] == ["subvolume", "show"]:
        path = args[2]
        print("Parent UUID: " + parents.get(path, "-"))
        print("Flags: " + ("readonly" if path in parents else "-"))
        print("UUID: " + identities[path])
        print("Gen at creation: " + str(generations[path]))
        ids = load("subvolume-ids.json")
        print("Subvolume ID: " + str(ids.get(path, 100 + generations[path])))
    elif args[:2] == ["property", "get"]:
        print("ro=true")
    elif args[:2] == ["subvolume", "sync"]:
        check_global_lock(False)
    elif args[:2] == ["subvolume", "delete"]:
        check_global_lock(True)
        assert args[2] in identities, args
        if flag("fail-delete"):
            sys.exit(1)
        shutil.rmtree(args[2])
    else:
        sys.exit(64)
elif command == "dolt":
    repo = pathlib.Path(args[args.index("--data-dir") + 1]) / args[args.index("--use-db") + 1]
    head = repo / ".dolt/HEAD"
    issue = repo / "issue.json"
    if not head.is_file() or not issue.is_file():
        sys.exit(1)
    commit = head.read_text().strip()
    if len(commit) != 32 or any(c not in "0123456789abcdefghijklmnopqrstuv" for c in commit):
        sys.exit(1)
    query = args[args.index("-q") + 1]
    if "FROM dolt_log" in query:
        print(json.dumps({"rows": [{"commit_hash": commit}]}))
    elif "FROM issues" in query:
        print(json.dumps({"rows": [json.loads(issue.read_text())]}))
    else:
        sys.exit(1)
save("identities.json", identities)
save("generations.json", generations)
"""

FAKED = (
    "findmnt",
    "mountpoint",
    "mount",
    "umount",
    "btrfs",
    "borg",
    "systemctl",
    "dolt",
)


class FakeHost:
    """A scratch root whose `bin/` shadows host commands for the code under test."""

    def __init__(self, root: Path, lock_path: Path):
        self.root = Path(root)
        self.state = self.root / "fake"
        self.bin = self.root / "fake-bin"
        for directory in (self.state, self.bin, self.root / "logs"):
            directory.mkdir(parents=True, exist_ok=True)
        (self.root / "logs/commands").touch()
        real_borg = shutil.which("borg")
        assert real_borg, "real borg must be on PATH"
        self.real_borg = real_borg
        script = FAKE_COMMAND.replace("PYTHON", sys.executable).replace(
            "REAL_BORG", repr(real_borg)
        )
        for name in FAKED:
            (self.bin / name).write_text(script)
            (self.bin / name).chmod(0o755)
        self.env = {
            "FAKE_ROOT": str(self.root),
            "FAKE_LOCK": str(lock_path),
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "BORG_BASE_DIR": str(self.root / "borg-home"),
            "BORG_SECURITY_DIR": str(self.root / "borg-security"),
            "BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK": "yes",
            "BORG_HOST_ID": "backup-fixture@stable",
        }

    def apply(self, monkeypatch) -> None:
        """Put the fakes into this process's environment (for in-process `cli.main`)."""
        for key, value in self.env.items():
            monkeypatch.setenv(key, value)

    def _update(self, name: str, changes: dict) -> None:
        path = self.state / name
        value = json.loads(path.read_text()) if path.exists() else {}
        value.update(changes)
        path.write_text(json.dumps(value))

    def register(
        self, path: Path, *, generation: int | None = None, identity: str | None = None
    ) -> None:
        """Give an existing directory a subvolume identity and creation generation."""
        generations = (
            json.loads((self.state / "generations.json").read_text())
            if (self.state / "generations.json").exists()
            else {}
        )
        self._update("identities.json", {str(path): identity or str(uuid.uuid4())})
        self._update(
            "generations.json",
            {
                str(path): generation
                if generation is not None
                else max(generations.values(), default=0) + 1
            },
        )

    def snapshot(self, directory: Path, name: str, files: dict[str, str]) -> Path:
        """Create a read-only snapshot directory with `files` and a newer generation."""
        path = Path(directory) / name
        path.mkdir(parents=True)
        for relative, data in files.items():
            file = path / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(data)
        self.register(path)
        return path

    def identity(self, path: Path) -> str:
        return json.loads((self.state / "identities.json").read_text())[str(path)]

    def set_generation(self, path: Path, generation: int) -> None:
        self._update("generations.json", {str(path): generation})

    def set_subvolume_ids(self, ids: dict[Path, int]) -> None:
        self._update(
            "subvolume-ids.json", {str(path): value for path, value in ids.items()}
        )

    def map_device(self, device: str, directory: Path) -> None:
        """Make `mount ... <device> <target>` copy `directory` instead."""
        self._update("devices.json", {device: str(directory)})

    def set_units(self, units: dict[str, list[str]]) -> None:
        """Make `systemctl start <unit>` run an argument list; other units succeed."""
        self._update("units.json", units)

    def flag(self, name: str) -> Path:
        """A flag file the fakes read: fail-create, fail-read, fail-proof-list,
        fail-delete, append-hooks, fail-unit-<unit>."""
        return self.state / name

    def commands(self) -> list[list[str]]:
        return [
            json.loads(line)
            for line in (self.root / "logs/commands").read_text().splitlines()
        ]

    def borg(self, *args: str, **kwargs) -> subprocess.CompletedProcess[str]:
        """Run the real Borg directly (not logged), for test setup and inspection."""
        # Repositories the jobs create use the fixture passphrase (conftest).
        env = {
            **os.environ,
            **self.env,
            "BORG_PASSPHRASE": "synthetic fixture passphrase",
        }
        result = subprocess.run(
            [self.real_borg, *args], env=env, text=True, capture_output=True, **kwargs
        )
        assert result.returncode == 0, (args, result.stderr)
        return result
