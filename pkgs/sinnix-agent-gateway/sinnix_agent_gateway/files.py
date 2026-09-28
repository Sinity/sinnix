from __future__ import annotations

import ctypes
import errno
import hashlib
import os
import shutil
import stat
from pathlib import Path
from typing import Any

from sinnix_lib.atomic import atomic_publish

from .capabilities import Capability, Principal
from .config import GatewayConfig


class FileError(ValueError):
    pass


_SECRET_ROOTS = (
    Path("/run/agenix"),
    Path("/persist/home/sinity/.ssh"),
    Path.home() / ".ssh",
    Path.home() / ".gnupg",
    Path.home() / ".config" / "age",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def move_source_refusal(source: Path, destination: Path) -> str | None:
    """Readiness hint, not an authorization grant or replacement for rename.

    Moving a directory across parents updates its '..' entry and can require
    write access to that directory even when both parents are writable.
    """
    try:
        parent = source.parent.stat()
        current = source.lstat()
        uid = os.geteuid()
        if not os.access(source.parent, os.W_OK | os.X_OK, effective_ids=True):
            return "source parent is not writable/searchable"
        if parent.st_mode & stat.S_ISVTX and uid not in (
            0,
            parent.st_uid,
            current.st_uid,
        ):
            return "source parent sticky-bit ownership forbids removal"
        if (
            stat.S_ISDIR(current.st_mode)
            and source.parent != destination.parent
            and not os.access(source, os.W_OK, effective_ids=True)
        ):
            return "source directory is not writable for a cross-parent rename"
    except OSError as exc:
        return f"source move access cannot be established: {exc}"
    return None


def rename_noreplace(source: Path, destination: Path) -> None:
    """One Linux atomic rename; never emulate it using a hard link and unlink."""
    try:
        function = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError as exc:
        raise FileError(
            "atomic no-replace rename unavailable; no transfer attempted"
        ) from exc
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    function.restype = ctypes.c_int
    if function(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(source))


def _copy_exclusive(source: Path, destination: Path) -> None:
    """Copy a regular file without ever replacing an existing destination."""
    try:
        destination_fd = os.open(
            destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
    except FileExistsError as exc:
        raise FileError("destination already exists") from exc
    try:
        with (
            source.open("rb") as input_handle,
            os.fdopen(destination_fd, "wb") as output_handle,
        ):
            destination_fd = -1
            shutil.copyfileobj(input_handle, output_handle)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        if destination_fd != -1:
            os.close(destination_fd)


class HostFileService:
    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal

    def _resolve(self, path: str, *, existing: bool) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = Path.home() / candidate
        try:
            resolved = candidate.resolve(strict=existing)
        except FileNotFoundError as exc:
            raise FileError("path does not exist") from exc
        if not existing:
            try:
                resolved.parent.resolve(strict=True)
            except FileNotFoundError as exc:
                raise FileError("parent directory does not exist") from exc
        if self.principal.name != "operator" and any(
            resolved == root or root in resolved.parents for root in _SECRET_ROOTS
        ):
            raise FileError("path is unavailable to this principal")
        return resolved

    def _destination(self, path: str) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = Path.home() / candidate
        if candidate.is_symlink():
            raise FileError("mutating symlinks is not supported")
        if candidate.exists():
            raise FileError("destination already exists")
        return self._resolve(path, existing=False)

    def stat(self, path: str) -> dict[str, Any]:
        self.principal.require(Capability.FILE_READ)
        target = self._resolve(path, existing=True)
        details = target.stat()
        return {
            "path": str(target),
            "kind": (
                "directory"
                if target.is_dir()
                else "file"
                if target.is_file()
                else "other"
            ),
            "bytes": details.st_size,
            "mode": oct(details.st_mode & 0o777),
            "mtime_ns": details.st_mtime_ns,
            "sha256": _sha256(target) if target.is_file() else None,
        }

    def write(
        self,
        operation: str,
        path: str,
        *,
        content: str | None = None,
        destination: str | None = None,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        self.principal.require(Capability.FILE_WRITE)
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = Path.home() / candidate
        if candidate.is_symlink():
            raise FileError("mutating symlinks is not supported")
        existing = operation in {"append", "remove", "copy", "move"}
        target = self._resolve(path, existing=existing)
        if operation == "mkdir":
            target.mkdir(mode=0o700)
            return {"operation": operation, "path": str(target), "created": True}
        if operation == "remove":
            if not target.is_file():
                raise FileError("remove supports regular files only")
            before_hash = _sha256(target)
            if expected_sha256 is not None and expected_sha256 != before_hash:
                raise FileError("expected_sha256 does not match the current file")
            target.unlink()
            return {
                "operation": operation,
                "path": str(target),
                "removed": True,
                "previous_sha256": before_hash,
            }
        if operation in {"copy", "move"}:
            if not target.is_file():
                raise FileError(f"{operation} supports regular files only")
            if destination is None:
                raise FileError("destination is required")
            before_hash = _sha256(target)
            if expected_sha256 is not None and expected_sha256 != before_hash:
                raise FileError("expected_sha256 does not match the current file")
            destination_path = self._destination(destination)
            if operation == "copy":
                _copy_exclusive(target, destination_path)
            else:
                refusal = move_source_refusal(target, destination_path)
                if refusal is not None:
                    raise FileError(refusal)
                try:
                    rename_noreplace(target, destination_path)
                except FileExistsError as exc:
                    raise FileError("destination already exists") from exc
                except OSError as exc:
                    if exc.errno != errno.EXDEV:
                        raise FileError(
                            f"atomic move failed without overwriting destination: {exc}"
                        ) from exc
                    # Cross-filesystem transfer cannot be globally atomic.
                    # Preserve both objects and report it if source removal
                    # fails; do not blindly remove the only complete copy.
                    _copy_exclusive(target, destination_path)
                    shutil.copystat(target, destination_path, follow_symlinks=False)
                    if (
                        _sha256(destination_path) != before_hash
                        or _sha256(target) != before_hash
                    ):
                        raise FileError(
                            "source changed during cross-filesystem copy; source and destination retained for reconciliation"
                        ) from None
                    try:
                        target.unlink()
                    except OSError as unlink_error:
                        raise FileError(
                            "cross-filesystem copy exists but source removal failed; both paths retained for reconciliation"
                        ) from unlink_error
            return {
                "operation": operation,
                "path": str(target),
                "destination": str(destination_path),
                "sha256": before_hash,
                "removed": operation == "move",
            }
        if operation not in {"create", "replace", "append"}:
            raise FileError(
                "operation must be create, replace, append, mkdir, remove, "
                "copy, or move"
            )
        if content is None:
            raise FileError("content is required")
        encoded = content.encode()
        if len(encoded) > self.config.max_result_bytes:
            raise FileError("content exceeds configured bound")
        before_hash = _sha256(target) if target.exists() else None
        if expected_sha256 is not None and expected_sha256 != before_hash:
            raise FileError("expected_sha256 does not match the current file")
        if operation == "append":
            with target.open("ab") as handle:
                handle.write(encoded)
        elif operation == "create":
            if not atomic_publish(
                target, encoded, fsync=True, mode=0o600, exclusive=True
            ):
                raise FileError("destination already exists")
        else:
            atomic_publish(target, encoded, fsync=True, mode=0o600)
        return {
            "operation": operation,
            "path": str(target),
            "bytes": len(encoded),
            "previous_sha256": before_hash,
            "sha256": _sha256(target),
        }
