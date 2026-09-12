"""Safe primitives for explicit filesystem relocation workflows.

This service deliberately does not classify, delete, or recursively relocate
content.  It records the identity of user-selected regular files and delegates
the actual exclusive transfer to :class:`HostFileService`.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import stat
import uuid
from pathlib import Path
from typing import Any

from .artifacts import ArtifactService
from .files import FileError, HostFileService


class OrganizationError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def file_identity(path: Path) -> dict[str, Any]:
    """Return the complete identity required before moving a regular file."""
    details = path.lstat()
    if stat.S_ISLNK(details.st_mode):
        kind = "symlink"
    elif stat.S_ISREG(details.st_mode):
        kind = "file"
    elif stat.S_ISDIR(details.st_mode):
        kind = "directory"
    else:
        kind = "other"
    identity: dict[str, Any] = {
        "kind": kind,
        "device": details.st_dev,
        "inode": details.st_ino,
        "size": details.st_size,
        "mtime_ns": details.st_mtime_ns,
        "sha256": None,
    }
    if kind == "file":
        identity["sha256"] = _sha256(path)
    elif kind == "directory":
        identity.update(_tree_identity(path, details.st_dev))
    return identity


def _tree_identity(root: Path, device: int) -> dict[str, Any]:
    """Hash every entry's identity, regular bytes, and symlink target.

    A directory rename is only safe when this snapshot still describes exactly
    the same tree and it never crosses a mounted filesystem boundary.
    """
    rows: list[dict[str, Any]] = []

    def visit(path: Path, relative: str) -> None:
        try:
            children = sorted(path.iterdir(), key=lambda child: child.name)
        except OSError as exc:
            raise OrganizationError(f"cannot inspect directory tree: {exc}") from exc
        for child in children:
            try:
                details = child.lstat()
            except OSError as exc:
                raise OrganizationError(
                    f"cannot inspect directory tree: {exc}"
                ) from exc
            child_relative = f"{relative}/{child.name}" if relative else child.name
            if details.st_dev != device:
                raise OrganizationError(
                    "directory tree crosses a filesystem boundary; directory moves are refused"
                )
            if stat.S_ISLNK(details.st_mode):
                row: dict[str, Any] = {
                    "path": child_relative,
                    "kind": "symlink",
                    "device": details.st_dev,
                    "inode": details.st_ino,
                    "size": details.st_size,
                    "mtime_ns": details.st_mtime_ns,
                    "target": os.readlink(child),
                }
            elif stat.S_ISREG(details.st_mode):
                row = {
                    "path": child_relative,
                    "kind": "file",
                    "device": details.st_dev,
                    "inode": details.st_ino,
                    "size": details.st_size,
                    "mtime_ns": details.st_mtime_ns,
                    "sha256": _sha256(child),
                }
            elif stat.S_ISDIR(details.st_mode):
                row = {
                    "path": child_relative,
                    "kind": "directory",
                    "device": details.st_dev,
                    "inode": details.st_ino,
                    "size": details.st_size,
                    "mtime_ns": details.st_mtime_ns,
                }
            else:
                raise OrganizationError(
                    "directory tree contains a special file; directory moves are refused"
                )
            rows.append(row)
            if row["kind"] == "directory":
                visit(child, child_relative)

    visit(root, "")
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return {
        "tree_entries": len(rows),
        "tree_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def identity_matches(path: Path, expected: dict[str, Any]) -> bool:
    try:
        current = file_identity(path)
    except OSError:
        return False
    return current == expected


class OrganizationService:
    """Plan artifact persistence and regular-file transfer at one seam."""

    plan_schema = "sinnix.gateway-files-plan.v1"

    def __init__(self, files: HostFileService, artifacts: ArtifactService):
        self.files = files
        self.artifacts = artifacts

    def persist_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        plan["plan_digest"] = canonical_digest(plan)
        return self.artifacts.register_json(
            plan,
            kind="files-plan",
            owner_id="organization",
            source="files.plan",
            target={"plan_digest": plan["plan_digest"]},
        )

    def load_plan(self, reference: str) -> dict[str, Any]:
        prefix = "sinnix://artifacts/"
        if not reference.startswith(prefix):
            raise OrganizationError("plan_ref is not a plan artifact reference")
        try:
            artifact_id = str(uuid.UUID(reference[len(prefix) :]))
            metadata = self.artifacts._metadata(artifact_id)
            if metadata.get("kind") != "files-plan":
                raise OrganizationError("artifact is not a filesystem plan")
            payload = json.loads(Path(metadata["_source"]).read_text())
        except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
            raise OrganizationError(
                "plan artifact is unavailable or malformed"
            ) from exc
        if not isinstance(payload, dict):
            raise OrganizationError("artifact is not a filesystem plan")
        digest = payload.get("plan_digest")
        candidate = dict(payload)
        candidate.pop("plan_digest", None)
        if not isinstance(digest, str) or digest != canonical_digest(candidate):
            raise OrganizationError("plan artifact digest is invalid")
        return payload

    def move_regular_file(
        self, source: Path, destination: Path, expected_sha256: str
    ) -> dict[str, Any]:
        """Use the existing exclusive link-or-copy transfer implementation."""
        try:
            return self.files.write(
                "move",
                str(source),
                destination=str(destination),
                expected_sha256=expected_sha256,
            )
        except FileError as exc:
            raise OrganizationError(str(exc)) from exc

    def move_directory_same_filesystem(self, source: Path, destination: Path) -> None:
        """Linux renameat2 with NOREPLACE, never a recursive copy fallback."""
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = libc.renameat2
        except AttributeError as exc:
            raise OrganizationError(
                "renameat2 is unavailable; directory moves are unsupported"
            ) from exc
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(
            -100,
            os.fsencode(source),
            -100,
            os.fsencode(destination),
            1,  # RENAME_NOREPLACE
        )
        if result != 0:
            error = ctypes.get_errno()
            raise OrganizationError(
                f"renameat2 directory move failed: {os.strerror(error)}"
            )
