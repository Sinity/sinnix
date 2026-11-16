#!/usr/bin/env python3
"""Archive hooks directly from a read-only native cut; retain failed cuts."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


def btrfs(*args: str) -> str:
    return subprocess.check_output(
        ["btrfs", *args], text=True, env={**os.environ, "LC_ALL": "C"}
    )


def identity(path: Path) -> dict[str, str]:
    fields = {}
    for line in btrfs("subvolume", "show", str(path)).splitlines():
        key, separator, value = line.strip().partition(":")
        if separator:
            fields[key] = value.strip()
    uuid.UUID(fields["UUID"])
    return fields


def verify_cut(cut: Path, origin: str, cut_uuid: str) -> None:
    if cut.absolute() != cut.resolve(strict=True):
        raise OSError(f"cut path changed or became an alias: {cut}")
    info = identity(cut)
    if (
        info["UUID"] != cut_uuid
        or info["Parent UUID"] != origin
        or "readonly" not in info["Flags"].split()
    ):
        raise OSError(f"cut identity or read-only state changed: {cut}")


def archive(state: Path, cuts: Path, command: list[str]) -> int:
    # Refuse aliases and overlapping roots before creating a native snapshot.
    for path in (state, cuts):
        if path.absolute() != path.resolve(strict=True) or not path.is_dir():
            raise OSError(f"cut paths must be canonical directories: {path}")
    if (
        state == Path("/")
        or state == cuts
        or state in cuts.parents
        or cuts in state.parents
    ):
        raise OSError("state and cut storage must be separate roots")
    if not command:
        raise ValueError("archive command is required")
    origin = identity(state)["UUID"]
    # Native snapshots omit nested subvolumes, so fail rather than lose files.
    if btrfs("subvolume", "list", "-o", str(state)).strip():
        raise OSError("Polylogue state contains nested subvolumes")
    cut = cuts / f"cut-{uuid.uuid4()}"
    btrfs("subvolume", "snapshot", "-r", str(state), str(cut))
    print(
        f"Polylogue hook source cut retained until archive succeeds: {cut}", flush=True
    )
    cut_uuid = identity(cut)["UUID"]
    verify_cut(cut, origin, cut_uuid)
    if (
        identity(state)["UUID"] != origin
        or btrfs("subvolume", "list", "-o", str(state)).strip()
    ):
        raise OSError(
            "Polylogue state identity or nested subvolumes changed during cut"
        )
    hooks = cut / "hooks"
    try:
        mode = hooks.lstat().st_mode
    except FileNotFoundError:
        mode = None
    if mode is not None:
        if not stat.S_ISDIR(mode):
            raise OSError(
                f"hook root must be a directory, not a symlink or file: {hooks}"
            )
        # An absent hooks tree is empty; an inaccessible tree is an error.
        with os.scandir(hooks):
            pass
    view = Path(tempfile.mkdtemp(prefix="view-", dir=cuts))
    owned_view = view.stat()
    try:
        source = view / state.relative_to("/")
        source.parent.mkdir(parents=True)
        if mode is None:
            (source / "hooks").mkdir(parents=True)
        else:
            # Borg follows an intermediate symlink and strips the prefix at /./.
            source.symlink_to(cut, target_is_directory=True)
        hook_input = f"{view}/./{state.relative_to('/')}/hooks"
        result = subprocess.run([*command, hook_input], check=False).returncode
        if result:
            return result if result > 0 else 128 - result
        # Borg owns archive durability. Only success releases this exact cut.
        verify_cut(cut, origin, cut_uuid)
        btrfs("subvolume", "delete", str(cut))
        return 0
    finally:
        current = view.lstat()
        if (current.st_dev, current.st_ino) != (
            owned_view.st_dev,
            owned_view.st_ino,
        ) or not stat.S_ISDIR(current.st_mode):
            raise OSError(f"private archive view replaced, refusing cleanup: {view}")
        shutil.rmtree(view)


def main() -> int:
    if len(sys.argv) < 5 or sys.argv[3] != "--":
        print(
            "usage: cut-polylogue-hooks.py STATE CUT_DIRECTORY -- COMMAND [ARG ...]",
            file=sys.stderr,
        )
        return 64
    try:
        return archive(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[4:])
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(
            f"could not archive Polylogue hooks from native cut: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
