from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Any

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

    def _read_file(self, path: Path, offset: int, max_bytes: int) -> dict[str, Any]:
        if not path.is_file():
            raise FileError("path is not a regular file")
        if offset < 0:
            raise FileError("offset must not be negative")
        max_bytes = max(1, min(max_bytes, self.config.max_result_bytes))
        with path.open("rb") as handle:
            handle.seek(offset)
            data = handle.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        data = data[:max_bytes]
        return {
            "path": str(path),
            "offset": offset,
            "bytes": len(data),
            "truncated": truncated,
            "sha256": _sha256(path),
            "mime_type": mimetypes.guess_type(path.name)[0]
            or "application/octet-stream",
            "content": data.decode("utf-8", errors="replace"),
        }

    def read(
        self,
        operation: str,
        path: str,
        *,
        offset: int = 0,
        max_bytes: int = 64_000,
        max_entries: int = 200,
    ) -> dict[str, Any]:
        self.principal.require(Capability.FILE_READ)
        target = self._resolve(path, existing=True)
        if operation == "stat":
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
        if operation == "read":
            return self._read_file(target, offset, max_bytes)
        if operation == "list":
            if not target.is_dir():
                raise FileError("path is not a directory")
            max_entries = max(1, min(max_entries, 2_000))
            entries = []
            for child in sorted(target.iterdir(), key=lambda item: item.name):
                try:
                    details = child.stat()
                except OSError:
                    continue
                entries.append(
                    {
                        "name": child.name,
                        "kind": (
                            "directory"
                            if child.is_dir()
                            else "file"
                            if child.is_file()
                            else "other"
                        ),
                        "bytes": details.st_size if child.is_file() else None,
                        "symlink": child.is_symlink(),
                    }
                )
                if len(entries) >= max_entries:
                    return {"path": str(target), "entries": entries, "truncated": True}
            return {"path": str(target), "entries": entries, "truncated": False}
        raise FileError("operation must be stat, read, or list")

    def write(
        self,
        operation: str,
        path: str,
        *,
        content: str | None = None,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        self.principal.require(Capability.FILE_WRITE)
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = Path.home() / candidate
        if candidate.is_symlink():
            raise FileError("mutating symlinks is not supported")
        existing = operation in {"append", "remove"}
        target = self._resolve(path, existing=existing)
        if operation == "mkdir":
            target.mkdir(mode=0o700)
            return {"operation": operation, "path": str(target), "created": True}
        if operation == "remove":
            if target.is_dir():
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
        if operation not in {"replace", "append"}:
            raise FileError("operation must be replace, append, mkdir, or remove")
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
        else:
            temporary = target.with_name(f".{target.name}.gateway-tmp")
            temporary.write_bytes(encoded)
            temporary.chmod(0o600)
            temporary.replace(target)
        return {
            "operation": operation,
            "path": str(target),
            "bytes": len(encoded),
            "previous_sha256": before_hash,
            "sha256": _sha256(target),
        }
