#!/usr/bin/env python3
"""Seal hooks from a verified read-only state cut; retain failed cuts for recovery."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
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
    info = identity(cut)
    if (
        info["UUID"] != cut_uuid
        or info["Parent UUID"] != origin
        or "readonly" not in info["Flags"].split()
    ):
        raise OSError(f"cut identity or read-only state changed: {cut}")


def seal(state: Path, destination: Path, cuts: Path, sealer: Path) -> int:
    # Refuse path aliases, including symlinked ancestors, before native mutations.
    for path in (state, destination.parent, cuts):
        if path.absolute() != path.resolve(strict=True):
            raise OSError(f"cut paths must be canonical: {path}")
    origin = identity(state)["UUID"]
    # A snapshot omits nested subvolumes. Check the entire dedicated state root
    # before and after creation, rather than silently losing a hook carrier.
    if btrfs("subvolume", "list", "-o", str(state)).strip():
        raise OSError("Polylogue state contains nested subvolumes")
    cut = cuts / f"cut-{uuid.uuid4()}"
    btrfs("subvolume", "snapshot", "-r", str(state), str(cut))
    print(f"Polylogue hook source cut retained until seal succeeds: {cut}", flush=True)
    cut_uuid = identity(cut)["UUID"]
    verify_cut(cut, origin, cut_uuid)
    if (
        identity(state)["UUID"] != origin
        or btrfs("subvolume", "list", "-o", str(state)).strip()
    ):
        raise OSError(
            "Polylogue state identity or nested subvolumes changed during cut"
        )
    spec = importlib.util.spec_from_file_location("polylogue_hook_sealer", sealer)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_argv = sys.argv
    try:
        sys.argv = [str(sealer), str(cut / "hooks"), str(destination)]
        result = module.main(source_identity=origin)
    finally:
        sys.argv = original_argv
    if result:
        return result
    # The durable cache and manifest now own the cut's hook payload. Delete only
    # this invocation's verified provisional cut, never historical restore points.
    verify_cut(cut, origin, cut_uuid)
    btrfs("subvolume", "delete", str(cut))
    return 0


def main() -> int:
    if len(sys.argv) != 5:
        print(
            "usage: cut-polylogue-hooks.py STATE DESTINATION_HOOKS CUT_DIRECTORY SEALER",
            file=sys.stderr,
        )
        return 64
    try:
        return seal(*map(Path, sys.argv[1:]))
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"could not cut and seal Polylogue hooks: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
