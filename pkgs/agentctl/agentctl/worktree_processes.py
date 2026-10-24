"""One process-holder census shared by a checkout cleanup pass."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def scan() -> list[tuple[int, str, str]]:
    rows = []
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            before = (process / "stat").read_text().rsplit(")", 1)[1].split()[19]
            paths = []
            for name in ("cwd", "exe"):
                try:
                    paths.append((name, os.readlink(process / name)))
                except (FileNotFoundError, ProcessLookupError):
                    pass
            for fd in (process / "fd").iterdir():
                try:
                    paths.append(("fd", os.readlink(fd)))
                except (FileNotFoundError, ProcessLookupError):
                    pass
            for line in (process / "maps").read_text().splitlines():
                fields = line.split(None, 5)
                if len(fields) == 6 and fields[5].startswith("/"):
                    paths.append(("mapping", fields[5]))
            after = (process / "stat").read_text().rsplit(")", 1)[1].split()[19]
            if before != after:
                raise RuntimeError(f"process {process.name} changed during inspection")
            rows.extend((int(process.name), kind, path) for kind, path in paths)
        except (FileNotFoundError, ProcessLookupError):
            continue
    return rows


def users(paths: list[Path]) -> dict[Path, list[str]]:
    try:
        rows = scan()
    except PermissionError:
        result = subprocess.run(
            ["sudo", "-n", sys.executable, str(Path(__file__).resolve())],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        rows = json.loads(result.stdout)
    roots = {path: str(path.resolve()) for path in paths}
    found: dict[Path, list[str]] = {path: [] for path in paths}
    for pid, kind, held in rows:
        held = held.removesuffix(" (deleted)")
        for path, root in roots.items():
            if held == root or held.startswith(root + "/"):
                found[path].append(f"pid {pid} {kind} {held}")
    return found


if __name__ == "__main__":
    print(json.dumps(scan()))
