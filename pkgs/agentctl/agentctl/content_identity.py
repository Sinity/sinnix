"""Bounded content observations for execution endpoints, never interval attestations."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any


def content_manifest(root: Path, *, max_files: int = 50_000,
                     max_bytes: int = 100_000_000) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    omissions: list[dict[str, str]] = []
    used = 0
    try:
        listed = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root, check=True, capture_output=True, timeout=15).stdout
        paths = sorted(set(os.fsdecode(p) for p in listed.split(b"\0") if p))
        for index, relative in enumerate(paths):
            if index >= max_files:
                omissions.append({"reason": "path limit reached", "remaining": str(len(paths) - index)})
                break
            path = root / relative
            if Path(relative).is_absolute() or ".." in Path(relative).parts:
                omissions.append({"path": relative, "reason": "unsafe path"})
                continue
            try:
                if any((root / parent).is_symlink() for parent in Path(relative).parents
                       if parent != Path(".")):
                    omissions.append({"path": relative, "reason": "symlink parent"})
                    continue
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode):
                    data = os.fsencode(os.readlink(path))
                    kind = "symlink"
                elif stat.S_ISREG(info.st_mode):
                    if used + info.st_size > max_bytes:
                        omissions.append({"path": relative, "reason": "byte limit"})
                        continue
                    with path.open("rb") as stream:
                        data = stream.read(max_bytes - used + 1)
                    kind = "file"
                else:
                    omissions.append({"path": relative, "reason": "unsupported type"})
                    continue
                if used + len(data) > max_bytes:
                    omissions.append({"path": relative, "reason": "byte limit"})
                    continue
                after = path.lstat()
                if (info.st_ino, info.st_mtime_ns, info.st_size, info.st_mode) != (
                        after.st_ino, after.st_mtime_ns, after.st_size, after.st_mode):
                    omissions.append({"path": relative, "reason": "changed during read"})
                    continue
                used += len(data)
                records.append({"path": relative, "mode": stat.S_IMODE(info.st_mode),
                    "kind": kind, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            except FileNotFoundError:
                records.append({"path": relative, "kind": "absent", "mode": None, "sha256": None})
            except OSError as exc:
                omissions.append({"path": relative, "reason": type(exc).__name__})
    except (OSError, subprocess.SubprocessError) as exc:
        omissions.append({"reason": type(exc).__name__})
    identity = {"schema_version": 1, "scope": "Git tracked and nonignored untracked paths; symlink text only",
                "files": records, "omissions": omissions, "ignored_paths": "outside captured scope",
                "coherence": "individual file endpoint checks; no atomic whole-tree attestation"}
    return {**identity, "sha256": hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
            "coverage": "partial" if omissions else "complete_declared_scope",
            "bytes_hashed": used, "max_files": max_files, "max_bytes": max_bytes}
