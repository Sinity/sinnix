from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Any, BinaryIO, Iterator, Mapping, TextIO

from sinnix_lib.atomic import atomic_publish_at
from sinnix_lib.lock import flock

from .capabilities import Capability, Principal
from .config import GatewayConfig, ProjectConfig
from .owner_execution import ExecutionProfile, OwnerExecution, OwnerRoute


class ProjectError(ValueError):
    pass


class ProjectPreconditionError(ProjectError):
    pass


SENSITIVE_PARTS = frozenset(
    {
        ".git",
        ".ssh",
        ".gnupg",
        ".env",
        "credentials",
        "cookies",
        "secret",
        "secrets",
    }
)

LOCAL_ONLY_PATHS = (
    (".agent",),
    (".claude",),
    (".beads", "dolt-server-config.yaml"),
    (".beads", "interactions.jsonl"),
    ("dots", "codex", "skills", ".system"),
)
LOCAL_ONLY_FILES = frozenset({(".mcp.json",)})
_DIRECTORY_OPEN_FLAGS = (
    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
)
# A search row may legitimately contain a source line larger than the normal
# response budget.  It is still bounded independently so malformed producer
# output cannot grow the streaming decoder without limit.
_SEARCH_ROW_MAX_BYTES = 1_048_576


def _is_excluded(path: Path) -> bool:
    parts = path.parts
    if any(part.lower() in SENSITIVE_PARTS for part in parts):
        return True
    if any(
        part.startswith(".") and (".gateway-tmp-" in part or ".atomic-tmp-" in part)
        for part in parts
    ):
        return True
    if parts in LOCAL_ONLY_FILES:
        return True
    return any(parts[: len(prefix)] == prefix for prefix in LOCAL_ONLY_PATHS)


def _file_sha256(path: Path) -> str:
    info = path.stat()
    identity = _stat_identity(info)
    return _cached_file_sha256(str(path), identity)


def _stat_identity(info: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


@lru_cache(maxsize=32_768)
def _cached_file_sha256(
    path: str, identity: tuple[int, int, int, int, int, int]
) -> str:
    """Reuse a digest only while the kernel's file identity remains unchanged."""
    return _compute_file_sha256(Path(path), identity)


def _compute_file_sha256(
    path: Path, identity: tuple[int, int, int, int, int, int]
) -> str:
    digest = hashlib.sha256()
    with _open_source_file(path) as handle:
        if _stat_identity(os.fstat(handle.fileno())) != identity:
            raise ProjectPreconditionError("project file changed while being read")
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
        if _stat_identity(os.fstat(handle.fileno())) != identity:
            raise ProjectPreconditionError("project file changed while being read")
    return digest.hexdigest()


@contextmanager
def _source_path(root: Path, relative: Path) -> Iterator[Path]:
    """Pin a Git-listed entry's parents without following directory symlinks."""
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ProjectError("source path must remain inside the project")
    parent = _open_pinned_directory(
        ProjectConfig(project_id="source", path=root),
        relative.parts[:-1],
        create=False,
        missing_ok=True,
    )
    try:
        yield Path(f"/proc/self/fd/{parent}") / relative.name
    finally:
        os.close(parent)


def _open_source_file(path: Path) -> BinaryIO:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise ProjectPreconditionError(
            "project source changed or is unavailable"
        ) from exc
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ProjectError("project source is no longer a regular file")
    return os.fdopen(descriptor, "rb")


def _content_revision(root: Path) -> str:
    """Hash tracked and non-ignored checkout files with unambiguous framing."""
    digest = hashlib.sha256()
    digest.update(b"sinnix-project-content-revision-v2\0")
    listing = subprocess.run(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=True,
    ).stdout
    paths = sorted(set(filter(None, listing.split(b"\0"))))
    for relative in paths:
        if _is_excluded(Path(os.fsdecode(relative))):
            continue
        try:
            with _source_path(root, Path(os.fsdecode(relative))) as path:
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode):
                    target = os.fsencode(os.readlink(path))
                    digest.update(b"symlink\0")
                    digest.update(len(relative).to_bytes(8, "big"))
                    digest.update(relative)
                    digest.update(stat.S_IMODE(info.st_mode).to_bytes(4, "big"))
                    digest.update(len(target).to_bytes(8, "big"))
                    digest.update(target)
                    continue
                if not stat.S_ISREG(info.st_mode):
                    continue
                file_digest = _cached_file_sha256(str(path), _stat_identity(info))
                digest.update(b"file\0")
                digest.update(len(relative).to_bytes(8, "big"))
                digest.update(relative)
                digest.update(stat.S_IMODE(info.st_mode).to_bytes(4, "big"))
                digest.update(info.st_size.to_bytes(8, "big"))
                digest.update(bytes.fromhex(file_digest))
        except FileNotFoundError:
            digest.update(b"missing\0")
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
    return digest.hexdigest()


def _mutation_parts(project: ProjectConfig, relative: str) -> tuple[str, ...]:
    try:
        candidate = Path(relative)
    except TypeError as exc:
        raise ProjectError(
            "path must be relative and remain inside the project"
        ) from exc
    if candidate.is_absolute() or not candidate.parts or ".." in candidate.parts:
        raise ProjectError("path must be relative and remain inside the project")
    if _is_excluded(candidate):
        raise ProjectError("path is excluded by project policy")
    return candidate.parts


def _open_pinned_directory(
    project: ProjectConfig,
    parts: tuple[str, ...],
    *,
    create: bool,
    missing_ok: bool = False,
) -> int:
    """Traverse one project directory with pinned, no-follow descriptors."""
    try:
        current = os.open(project.path, _DIRECTORY_OPEN_FLAGS)
    except OSError as exc:
        raise ProjectError("project checkout directory is unavailable") from exc
    try:
        for part in parts:
            try:
                child = os.open(part, _DIRECTORY_OPEN_FLAGS, dir_fd=current)
            except FileNotFoundError:
                if not create:
                    if missing_ok:
                        raise
                    raise ProjectError("path does not exist") from None
                try:
                    os.mkdir(part, 0o700, dir_fd=current)
                except FileExistsError:
                    pass
                else:
                    os.fsync(current)
                child = os.open(part, _DIRECTORY_OPEN_FLAGS, dir_fd=current)
            os.close(current)
            current = child
        return current
    except (OSError, ProjectError) as exc:
        os.close(current)
        if isinstance(exc, ProjectError) or (
            missing_ok and isinstance(exc, FileNotFoundError)
        ):
            raise
        raise ProjectError("project path contains a symlink or is unavailable") from exc


def _temporary_name(target_name: str) -> str:
    return f".{target_name}.gateway-tmp-{os.urandom(16).hex()}"


def _unlink_at(parent: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=parent)
    except FileNotFoundError:
        pass
    else:
        os.fsync(parent)


def _atomic_publish(
    parent: int, target_name: str, content: bytes, mode: int = 0o600
) -> None:
    atomic_publish_at(parent, target_name, content, fsync=True, mode=mode)


def _atomic_publish_symlink(parent: int, target_name: str, target: str) -> None:
    temporary_name: str | None = None
    try:
        for _ in range(8):
            candidate = _temporary_name(target_name)
            try:
                os.symlink(target, candidate, dir_fd=parent)
            except FileExistsError:
                continue
            temporary_name = candidate
            break
        if temporary_name is None:
            raise ProjectError("could not allocate a private project temporary")
        os.replace(
            temporary_name,
            target_name,
            src_dir_fd=parent,
            dst_dir_fd=parent,
        )
        os.fsync(parent)
        temporary_name = None
    finally:
        if temporary_name is not None:
            _unlink_at(parent, temporary_name)


class ProjectService:
    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal

    def _project(self, project_id: str, *, write: bool = False) -> ProjectConfig:
        self.principal.require(
            Capability.PROJECT_WRITE if write else Capability.PROJECT_READ
        )
        try:
            project = self.config.projects[project_id]
        except KeyError as exc:
            raise ProjectError(f"unknown project: {project_id}") from exc
        if not project.path.is_dir():
            raise ProjectError(f"project checkout is unavailable: {project_id}")
        return project

    @staticmethod
    def _safe_path(project: ProjectConfig, relative: str, *, existing: bool) -> Path:
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ProjectError("path must be relative and remain inside the project")
        if _is_excluded(candidate):
            raise ProjectError("path is excluded by project policy")
        target = project.path / candidate
        try:
            resolved = target.resolve(strict=existing)
        except FileNotFoundError as exc:
            raise ProjectError("path does not exist") from exc
        root = project.path.resolve(strict=True)
        if resolved != root and root not in resolved.parents:
            raise ProjectError("path resolves outside the project")
        resolved_relative = resolved.relative_to(root)
        if resolved != root and _is_excluded(resolved_relative):
            raise ProjectError("path is excluded by project policy")
        return resolved

    def list(self) -> dict[str, Any]:
        self.principal.require(Capability.PROJECT_READ)
        can_write = Capability.PROJECT_WRITE in self.principal.capabilities
        rows = []
        for project in self.config.projects.values():
            candidates: list[dict[str, Any]] = []
            repository_kind: str | None = None
            checkout_discovery_error: str | None = None
            if project.path.is_dir():
                try:
                    repository_kind = self._repository_kind(project)
                    candidates = self._checkout_candidates(project)
                except ProjectError as exc:
                    # Listing still identifies a configured but unavailable
                    # or not-yet-initialized project; checkout-specific tools
                    # report the owner error when asked to read it.
                    checkout_discovery_error = str(exc)
            rows.append(
                {
                    "project_id": project.project_id,
                    "available": project.path.is_dir(),
                    "default_ref": project.default_ref,
                    "repository_path": str(project.path.resolve()),
                    "repository_kind": repository_kind,
                    "default_checkout_path": (
                        str(self._default_checkout_path(project))
                        if repository_kind is not None
                        and self._default_checkout_path(project) is not None
                        else None
                    ),
                    "checkout_discovery_error": checkout_discovery_error,
                    "default_checkout_id": next(
                        (
                            row["checkout_id"]
                            for row in candidates
                            if row["checkout_id"] == "default"
                        ),
                        None,
                    ),
                    "checkouts": candidates,
                    "writable": can_write,
                }
            )
        return {"projects": sorted(rows, key=lambda row: row["project_id"])}

    @staticmethod
    def _checkout_id(path: Path, configured_root: Path) -> str:
        if path == configured_root:
            return "default"
        digest = hashlib.sha256(str(path).encode()).hexdigest()[:16]
        return f"worktree-{digest}"

    def _repository_kind(self, project: ProjectConfig) -> str:
        result = self._run_spooled(
            ["git", "rev-parse", "--is-bare-repository"], project.path
        ).strip()
        if result not in {"true", "false"}:
            raise ProjectError("git did not identify the configured repository")
        return "bare" if result == "true" else "worktree"

    def _default_checkout_path(self, project: ProjectConfig) -> Path | None:
        if project.default_checkout is not None:
            return project.default_checkout.resolve()
        if self._repository_kind(project) == "bare":
            return None
        return project.path.resolve()

    @staticmethod
    def _worktree_records(output: str) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        current: dict[str, str] = {}
        for line in output.splitlines():
            if not line:
                if current:
                    records.append(current)
                    current = {}
                continue
            key, separator, value = line.partition(" ")
            # `bare`, `detached`, `locked`, and `prunable` are valid marker
            # records. Git emits some of them without a trailing value.
            if not separator and key not in {"bare", "detached", "locked", "prunable"}:
                raise ProjectError("git worktree returned malformed porcelain")
            if key in current:
                raise ProjectError("git worktree returned duplicate porcelain field")
            current[key] = value
        if current:
            records.append(current)
        return records

    def _checkout_candidates(self, project: ProjectConfig) -> list[dict[str, Any]]:
        if project.checkout_discovery != "git-worktree":
            raise ProjectError("project checkout discovery is unsupported")
        configured_root = project.path.resolve(strict=True)
        repository_kind = self._repository_kind(project)
        default_path = self._default_checkout_path(project)
        common_directory = Path(
            self._run_spooled(
                ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                project.path,
            ).removesuffix("\n")
        ).resolve()
        output = self._run_spooled(
            ["git", "worktree", "list", "--porcelain"], project.path
        )
        candidates: list[dict[str, Any]] = []
        for record in self._worktree_records(output):
            # The bare marker describes the object store, which has no
            # checkout HEAD or working files. It never enters status/hash
            # readers below.
            if "bare" in record or "prunable" in record:
                continue
            raw_path = record.get("worktree")
            head = record.get("HEAD")
            if raw_path is None or head is None:
                raise ProjectError("git worktree record is missing worktree or HEAD")
            path = Path(raw_path).resolve()
            if not path.is_dir():
                continue
            # Git can keep advertising a worktree after its path is replaced.
            # Verify the live checkout against the configured object store.
            try:
                actual_common = Path(
                    self._run_spooled(
                        [
                            "git",
                            "rev-parse",
                            "--path-format=absolute",
                            "--git-common-dir",
                        ],
                        path,
                    ).removesuffix("\n")
                ).resolve()
                actual_root = Path(
                    self._run_spooled(
                        ["git", "rev-parse", "--show-toplevel"], path
                    ).removesuffix("\n")
                ).resolve()
            except (ProjectError, OSError, subprocess.CalledProcessError):
                continue
            if actual_common != common_directory or actual_root != path:
                continue
            candidates.append(
                {
                    "checkout_id": self._checkout_id(
                        path, default_path or configured_root
                    ),
                    "path": str(path),
                    "head": head,
                    "lifecycle": "configured-default"
                    if default_path is not None and path == default_path
                    else "configured-root"
                    if path == configured_root
                    else "linked-worktree",
                }
            )
        candidates.sort(
            key=lambda row: (row["checkout_id"] != "default", row["checkout_id"])
        )
        if default_path is not None and not any(
            row["checkout_id"] == "default" for row in candidates
        ):
            raise ProjectError(
                "configured default checkout is not a live worktree of the repository"
            )
        if repository_kind != "bare" and not any(
            row["checkout_id"] == "default" for row in candidates
        ):
            raise ProjectError("configured project root is not a live Git worktree")
        return candidates

    def _checkout_rows(
        self,
        project: ProjectConfig,
        *,
        candidates: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        selected = (
            candidates if candidates is not None else self._checkout_candidates(project)
        )
        for candidate in selected:
            path = Path(candidate["path"])
            try:
                rows.append(self._checkout_row(project, candidate))
            except (ProjectError, subprocess.CalledProcessError):
                # Batch workers create and remove linked worktrees all the
                # time. One removed after the listing is simply no longer a
                # checkout; it must not fail a read of the others.
                if path.is_dir():
                    raise
        return rows

    def _checkout_row(
        self, project: ProjectConfig, candidate: dict[str, Any]
    ) -> dict[str, Any]:
        path = Path(candidate["path"])
        status = self._run_spooled(
            ["git", "-C", str(path), "status", "--porcelain=v2", "--branch"],
            project.path,
        )
        branch = None
        upstream = None
        for line in status.splitlines():
            if line.startswith("# branch.head "):
                branch = line.removeprefix("# branch.head ")
            elif line.startswith("# branch.upstream "):
                upstream = line.removeprefix("# branch.upstream ")
        return {
            **candidate,
            "branch": branch,
            "upstream": upstream,
            "dirty_sha256": _content_revision(path),
        }

    def checkouts(self, project_id: str) -> dict[str, Any]:
        project = self._project(project_id)
        candidates = self._checkout_candidates(project)
        default_checkout = self._default_checkout_path(project)
        return {
            "project_id": project.project_id,
            "repository": {
                "kind": self._repository_kind(project),
                "path": str(project.path.resolve()),
                "default_ref": project.default_ref,
                "default_checkout_path": (
                    str(default_checkout) if default_checkout is not None else None
                ),
            },
            "checkouts": self._checkout_rows(project, candidates=candidates),
        }

    def checkout_candidates(self, project_id: str) -> list[dict[str, Any]]:
        """Return live checkout identities without status or content reads."""
        project = self._project(project_id)
        return self._checkout_candidates(project)

    def checkout_candidate(self, project_id: str, checkout_id: str) -> dict[str, Any]:
        """Return one live checkout identity without status or content reads."""
        for candidate in self.checkout_candidates(project_id):
            if candidate["checkout_id"] == checkout_id:
                return candidate
        raise ProjectError("unknown configured checkout")

    def checkout(self, project_id: str, checkout_id: str) -> dict[str, Any]:
        project = self._project(project_id)
        # Status and the content revision read every file of a checkout, so
        # only the requested one is read: a project with a hundred linked
        # worktrees otherwise costs minutes per call.
        selected = [
            candidate
            for candidate in self._checkout_candidates(project)
            if candidate["checkout_id"] == checkout_id
        ]
        for checkout in self._checkout_rows(project, candidates=selected):
            return {
                "project_id": project.project_id,
                "available": True,
                "checkout": checkout,
            }
        raise ProjectError("unknown configured checkout")

    def code_checkout(
        self,
        project_id: str,
        checkout_id: str | None,
        *,
        write: bool,
        require_explicit: bool,
    ) -> ProjectConfig:
        project = self._project(project_id, write=write)
        if checkout_id is None:
            checkouts = self._checkout_candidates(project)
            default_path = self._default_checkout_path(project)
            default_row = next(
                (row for row in checkouts if row["checkout_id"] == "default"), None
            )
            if default_path is not None and default_row is not None:
                return replace(project, path=Path(default_row["path"]))
            if self._repository_kind(project) == "bare":
                choices = ", ".join(row["checkout_id"] for row in checkouts)
                detail = f"; available checkouts: {choices}" if choices else ""
                raise ProjectError(
                    "bare repository has no configured default checkout; pass an explicit checkout_id"
                    + detail
                )
            if not require_explicit:
                return project
            if len(checkouts) == 1:
                return replace(project, path=Path(checkouts[0]["path"]))
            choices = ", ".join(row["checkout_id"] for row in checkouts)
            raise ProjectError(
                f"checkout_id is required; available checkouts: {choices}"
            )
        if not isinstance(checkout_id, str) or not checkout_id:
            raise ProjectError("checkout_id must be a non-empty string")
        for checkout in self._checkout_candidates(project):
            if checkout["checkout_id"] == checkout_id:
                return replace(project, path=Path(checkout["path"]))
        raise ProjectError("unknown configured checkout")

    def tree(
        self,
        project_id: str,
        path: str = ".",
        max_entries: int = 500,
        checkout_id: str | None = None,
        start_after: str | None = None,
    ) -> dict[str, Any]:
        project = self.code_checkout(
            project_id, checkout_id, write=False, require_explicit=False
        )
        root = self._safe_path(project, path, existing=True)
        if not root.is_dir():
            raise ProjectError("tree path must be a directory")
        if max_entries < 1:
            raise ProjectError("max_entries must be positive")
        entries: list[dict[str, Any]] = []
        cursor_found = start_after is None
        for current, dirs, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            dirs[:] = sorted(
                name
                for name in dirs
                if not _is_excluded((current_path / name).relative_to(project.path))
                and not (current_path / name).is_symlink()
            )
            for name in [*dirs, *sorted(files)]:
                target = current_path / name
                relative = target.relative_to(project.path)
                if target.is_symlink() or _is_excluded(relative):
                    continue
                if not cursor_found:
                    if relative.as_posix() == start_after:
                        cursor_found = True
                    continue
                entries.append(
                    {
                        "path": str(relative),
                        "kind": "directory" if target.is_dir() else "file",
                        "bytes": target.stat().st_size if target.is_file() else None,
                    }
                )
                if len(entries) > max_entries:
                    return {
                        "entries": entries[:max_entries],
                        "truncated": True,
                        "next_start_after": entries[max_entries - 1]["path"],
                    }
        if not cursor_found:
            raise ProjectError("start_after does not identify a listed entry")
        return {"entries": entries, "truncated": False, "next_start_after": None}

    def read(
        self,
        project_id: str,
        path: str,
        start_line: int = 1,
        end_line: int | None = None,
        max_bytes: int = 64_000,
        checkout_id: str | None = None,
    ) -> dict[str, Any]:
        project = self.code_checkout(
            project_id, checkout_id, write=False, require_explicit=False
        )
        before = _content_revision(project.path)
        result = self._read_file(project, path, start_line, end_line, max_bytes)
        if before != _content_revision(project.path):
            raise ProjectPreconditionError("project changed while file was read")
        return {
            "project_id": project_id,
            **result,
            "checkout_revision": before,
        }

    def read_many(
        self,
        project_id: str,
        requests: list[dict[str, Any]],
        checkout_id: str | None = None,
    ) -> dict[str, Any]:
        project = self.code_checkout(
            project_id, checkout_id, write=False, require_explicit=False
        )
        before = _content_revision(project.path)
        files = [
            self._read_file(
                project,
                request["path"],
                request["start_line"],
                request["end_line"],
                request["max_bytes"],
            )
            for request in requests
        ]
        if before != _content_revision(project.path):
            raise ProjectPreconditionError("project changed while files were read")
        return {
            "project_id": project_id,
            "files": [{**file, "checkout_revision": before} for file in files],
            "checkout_revision": before,
        }

    def _read_file(
        self,
        project: ProjectConfig,
        path: str,
        start_line: int,
        end_line: int | None,
        max_bytes: int,
    ) -> dict[str, Any]:
        target = self._safe_path(project, path, existing=True)
        if not target.is_file() or target.is_symlink():
            raise ProjectError("path must identify a regular project file")
        if max_bytes < 1:
            raise ProjectError("max_bytes must be positive")
        if end_line is not None and end_line < start_line:
            raise ProjectError("end_line must be greater than or equal to start_line")
        content: list[str] = []
        used = 0
        truncated = False
        with _source_path(
            project.path, target.relative_to(project.path.resolve())
        ) as source_path:
            with io.TextIOWrapper(
                _open_source_file(source_path), encoding="utf-8", errors="replace"
            ) as handle:
                for line_number, line in enumerate(handle, 1):
                    if line_number < start_line:
                        continue
                    if end_line is not None and line_number > end_line:
                        break
                    encoded = line.encode("utf-8")
                    if used + len(encoded) > max_bytes:
                        remaining = max_bytes - used
                        if remaining:
                            fragment = encoded[:remaining].decode(
                                "utf-8", errors="ignore"
                            )
                            content.append(fragment)
                            used += len(fragment.encode("utf-8"))
                        truncated = True
                        break
                    content.append(line)
                    used += len(encoded)
            return {
                "path": path,
                "start_line": start_line,
                "end_line": end_line,
                "content": "".join(content),
                "bytes": used,
                "truncated": truncated,
                "content_sha256": _file_sha256(source_path),
            }

    def export(
        self,
        project_id: str,
        checkout_id: str | None = None,
        max_files: int | None = None,
        max_bytes: int | None = None,
        start_after: str | None = None,
        expected_revision: str | None = None,
    ) -> dict[str, Any]:
        """Stream the Git source set into a policy-filtered ZIP artifact."""
        project = self.code_checkout(
            project_id, checkout_id, write=False, require_explicit=False
        )
        if (start_after is None) != (expected_revision is None):
            raise ProjectError(
                "start_after and expected_revision must be supplied together"
            )
        if max_files is not None and max_files < 1:
            raise ProjectError("max_files must be positive")
        if max_bytes is not None and max_bytes < 1:
            raise ProjectError("max_bytes must be positive")
        paths = self._export_paths(project)
        before = self._export_revision(project.path, paths)
        if expected_revision is not None and expected_revision != before:
            raise ProjectPreconditionError(
                "project changed since the previous export page"
            )
        if start_after is not None:
            cursor = Path(start_after)
            if cursor not in paths:
                raise ProjectError("start_after does not identify an exported file")
            paths = paths[paths.index(cursor) + 1 :]
        selected: list[Path] = []
        total = 0
        for relative in paths:
            with _source_path(project.path, relative) as path:
                size = (
                    len(os.fsencode(os.readlink(path)))
                    if path.is_symlink()
                    else path.lstat().st_size
                )
                if max_files is not None and len(selected) >= max_files:
                    break
                if max_bytes is not None and total + size > max_bytes:
                    if not selected:
                        raise ProjectError(
                            f"file {relative.as_posix()} is {size} bytes; increase max_bytes"
                        )
                    break
                selected.append(relative)
                total += size
        truncated = len(selected) < len(paths)
        capture = self.config.state_dir / "captures" / uuid.uuid4().hex
        capture.mkdir(mode=0o700, parents=True)
        archive = capture / "project-export.zip"
        manifest_name = "MANIFEST.json"
        suffix = 1
        selected_names = {path.as_posix() for path in selected}
        while manifest_name in selected_names:
            manifest_name = f"MANIFEST.{suffix}.json"
            suffix += 1
        try:
            rows = []
            with zipfile.ZipFile(
                archive, "w", compression=zipfile.ZIP_DEFLATED
            ) as bundle:
                for relative in selected:
                    with _source_path(project.path, relative) as path:
                        digest = hashlib.sha256()
                        size = 0
                        info = zipfile.ZipInfo(relative.as_posix())
                        info.create_system = 3
                        mode = stat.S_IMODE(path.lstat().st_mode)
                        is_link = path.is_symlink()
                        info.external_attr = (
                            (stat.S_IFLNK if is_link else stat.S_IFREG) | mode
                        ) << 16
                        info.compress_type = (
                            zipfile.ZIP_STORED if is_link else zipfile.ZIP_DEFLATED
                        )
                        source = (
                            io.BytesIO(os.fsencode(os.readlink(path)))
                            if is_link
                            else _open_source_file(path)
                        )
                        with source, bundle.open(info, "w") as target:
                            if is_link:
                                link_bytes = os.fsencode(os.readlink(path))
                                target.write(link_bytes)
                                digest.update(link_bytes)
                                size += len(link_bytes)
                            else:
                                while chunk := source.read(1_048_576):
                                    size += len(chunk)
                                    digest.update(chunk)
                                    target.write(chunk)
                        rows.append(
                            {
                                "path": relative.as_posix(),
                                "bytes": size,
                                "sha256": digest.hexdigest(),
                                "mode": mode,
                                "kind": "symlink" if is_link else "file",
                            }
                        )
                after_paths = self._export_paths(project)
                after = self._export_revision(project.path, after_paths)
                if before != after:
                    raise ProjectPreconditionError(
                        "project changed while export was collected"
                    )
                manifest = {
                    "schema": "sinnix.project-export.v1",
                    "project_id": project_id,
                    "checkout_id": checkout_id or "default",
                    "checkout_revision": before,
                    "files": rows,
                    "file_count": len(rows),
                    "bytes": sum(row["bytes"] for row in rows),
                    "truncated": truncated,
                    "start_after": start_after,
                    "next_start_after": rows[-1]["path"] if truncated else None,
                    "manifest_path": manifest_name,
                }
                bundle.writestr(
                    manifest_name, json.dumps(manifest, sort_keys=True, indent=2) + "\n"
                )
        except Exception:
            shutil.rmtree(capture)
            raise
        return {"directory": capture, "archive": archive, "manifest": manifest}

    def _export_paths(self, project: ProjectConfig) -> list[Path]:
        """Include tracked and nonignored untracked files, subject to project policy."""
        output = self._run_spooled(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            project.path,
        )
        paths = set()
        for name in output.split("\0"):
            if not name:
                continue
            relative = Path(name)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or _is_excluded(relative)
            ):
                continue
            try:
                with _source_path(project.path, relative) as path:
                    if path.is_symlink() or path.is_file():
                        paths.add(relative)
            except FileNotFoundError:
                continue
        return sorted(paths, key=lambda path: path.as_posix())

    @staticmethod
    def _export_revision(root: Path, paths: list[Path]) -> str:
        digest = hashlib.sha256()
        for relative in paths:
            with _source_path(root, relative) as path:
                name = relative.as_posix().encode()
                digest.update(len(name).to_bytes(8, "big"))
                digest.update(name)
                info = path.lstat()
                mode = stat.S_IMODE(info.st_mode)
                digest.update(mode.to_bytes(4, "big"))
                if stat.S_ISLNK(info.st_mode):
                    target = os.fsencode(os.readlink(path))
                    digest.update(b"symlink\0")
                    digest.update(len(target).to_bytes(8, "big"))
                    digest.update(target)
                    continue
                digest.update(b"file\0")
                with _open_source_file(path) as handle:
                    for chunk in iter(lambda: handle.read(1_048_576), b""):
                        digest.update(chunk)
        return digest.hexdigest()

    def _run_spooled(self, command: list[str], cwd: Path, timeout: int = 15) -> str:
        with self._spooled_output(command, cwd, timeout) as output:
            return output.read()

    @contextmanager
    def _spooled_output(
        self, command: list[str], cwd: Path, timeout: int = 15
    ) -> Iterator[TextIO]:
        """Keep owner output on disk until consumers select the requested rows."""
        if command and command[0] == "git":
            # Read-only views must not execute a repository's monitor hook.
            command = ["git", "-c", "core.fsmonitor=false", *command[1:]]
        safe_env = {
            "HOME": str(Path.home()),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PATH": os.environ.get("PATH", "/run/current-system/sw/bin"),
            "GIT_OPTIONAL_LOCKS": "0",
        }
        captures = self.config.state_dir / "captures"
        captures.mkdir(mode=0o700, parents=True, exist_ok=True)
        captures.chmod(0o700)
        with tempfile.TemporaryDirectory(
            prefix="sinnix-gateway-project-read-", dir=captures
        ) as directory:
            spool = Path(directory) / "stdout"
            with spool.open("xb") as handle:
                spool.chmod(0o600)
                result = OwnerExecution(safe_env).run(
                    command,
                    ExecutionProfile(
                        route=OwnerRoute("project-read"),
                        cwd=cwd,
                        timeout_seconds=timeout,
                        max_stdout_bytes=self.config.max_result_bytes,
                        max_stderr_bytes=self.config.max_result_bytes,
                        environment={"GIT_OPTIONAL_LOCKS": "0"},
                    ),
                    stdout_chunk_callback=handle.write,
                )
            if result.timed_out:
                raise ProjectError("project operation timed out")
            if result.output_exceeded:
                raise ProjectError("project operation exceeded its output bound")
            if result.exit_status not in (0, 1):
                diagnostic = result.stderr.decode("utf-8", errors="replace").strip()
                raise ProjectError(diagnostic or "project operation failed")
            with spool.open(encoding="utf-8", errors="replace") as output:
                yield output

    @contextmanager
    def _locked_mutation(
        self,
        project_id: str,
        checkout_id: str | None,
        preconditions: Mapping[str, Any] | None,
    ) -> Iterator[ProjectConfig]:
        lock_name = hashlib.sha256(project_id.encode()).hexdigest() + ".lock"
        with flock(self.config.state_dir / "project-mutations" / lock_name):
            project = self.code_checkout(
                project_id, checkout_id, write=True, require_explicit=True
            )
            if preconditions is not None:
                if checkout_id is None:
                    raise ProjectPreconditionError(
                        "preconditioned mutation requires checkout_id"
                    )
                if set(preconditions) - {
                    "head",
                    "dirty_sha256",
                    "file_sha256",
                    "file_path",
                }:
                    raise ProjectError(
                        "project mutation preconditions are not recognized"
                    )
                checkout = self.checkout(project_id, checkout_id)["checkout"]
                for name, expected in preconditions.items():
                    if name in {"file_sha256", "file_path"}:
                        continue
                    if not isinstance(expected, str) or checkout.get(name) != expected:
                        raise ProjectPreconditionError(
                            f"project checkout {name} no longer matches"
                        )
                file_path = preconditions.get("file_path")
                expected_file_sha = preconditions.get("file_sha256")
                if file_path is not None or expected_file_sha is not None:
                    if not isinstance(file_path, str) or not isinstance(
                        expected_file_sha, str
                    ):
                        raise ProjectError("file_sha256 requires file_path")
                    target = self._safe_path(project, file_path, existing=True)
                    if _file_sha256(target) != expected_file_sha:
                        raise ProjectPreconditionError(
                            f"project file {file_path} no longer matches"
                        )
            yield project

    def search(
        self,
        project_id: str,
        query: str,
        max_matches: int = 200,
        checkout_id: str | None = None,
    ) -> dict[str, Any]:
        project = self.code_checkout(
            project_id, checkout_id, write=False, require_explicit=False
        )
        if not query or len(query) > 1000:
            raise ProjectError("query must contain 1-1000 characters")
        if max_matches < 1:
            raise ProjectError("max_matches must be positive")
        matches: list[dict[str, Any]] = []

        def collect(row: Any) -> bool | None:
            match = self._search_match(row)
            if match is None:
                return None
            matches.append(match)
            # Keep one surplus row solely to report a truthful truncation flag;
            # terminate rg before it scans the rest of a large checkout.
            return len(matches) <= max_matches

        safe_env = {
            "HOME": str(Path.home()),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PATH": os.environ.get("PATH", "/run/current-system/sw/bin"),
            "GIT_OPTIONAL_LOCKS": "0",
        }
        result = OwnerExecution(safe_env).run_jsonl(
            ["rg", "--json", "--hidden", "--glob", "!.git/**", "--", query, "."],
            ExecutionProfile(
                route=OwnerRoute("project-read"),
                cwd=project.path,
                timeout_seconds=15,
                max_stdout_bytes=self.config.max_result_bytes,
                max_stderr_bytes=self.config.max_result_bytes,
                environment={"GIT_OPTIONAL_LOCKS": "0"},
            ),
            collect,
            max_row_bytes=max(self.config.max_result_bytes, _SEARCH_ROW_MAX_BYTES),
        )
        if result.timed_out:
            raise ProjectError("project operation timed out")
        if result.output_exceeded:
            raise ProjectError("project operation exceeded its output bound")
        if result.failure_class is not None or result.exit_status not in (0, 1):
            diagnostic = result.stderr.decode("utf-8", errors="replace").strip()
            raise ProjectError(diagnostic or "project operation failed")
        return {
            "matches": matches[:max_matches],
            "truncated": len(matches) > max_matches,
        }

    @staticmethod
    def _search_matches(output: TextIO, max_matches: int) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for line in output:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            match = ProjectService._search_match(row)
            if match is not None:
                matches.append(match)
            if len(matches) > max_matches:
                break
        return matches

    @staticmethod
    def _search_match(row: Any) -> dict[str, Any] | None:
        if not isinstance(row, dict) or row.get("type") != "match":
            return None
        data = row["data"]
        path_data = data["path"]
        path_value = path_data.get("text")
        if path_value is None:
            path_value = os.fsdecode(base64.b64decode(path_data["bytes"]))
        if _is_excluded(Path(path_value)):
            return None
        line_data = data["lines"]
        text = line_data.get("text")
        if text is None:
            text = base64.b64decode(line_data["bytes"]).decode("utf-8", "replace")
        return {
            "path": path_value,
            "line": data.get("line_number"),
            "text": text.rstrip("\n"),
        }

    def diff(
        self, project_id: str, ref: str | None = None, checkout_id: str | None = None
    ) -> dict[str, Any]:
        project = self.code_checkout(
            project_id, checkout_id, write=False, require_explicit=False
        )
        resolved_ref = None
        if ref is not None:
            if ref.startswith("-") or not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", ref):
                raise ProjectError("invalid git ref")
            resolved_ref = self._run_spooled(
                [
                    "git",
                    "rev-parse",
                    "--verify",
                    "--end-of-options",
                    f"{ref}^{{commit}}",
                ],
                project.path,
            ).strip()
            if not re.fullmatch(r"[0-9a-f]{40,64}", resolved_ref):
                raise ProjectError("git ref did not resolve to a commit")
        name_command = ["git", "diff", "--no-renames", "--name-only", "-z"]
        if resolved_ref is not None:
            name_command.append(resolved_ref)
        name_command.append("--")
        changed = self._run_spooled(name_command, project.path).encode(
            "utf-8", "surrogateescape"
        )
        allowed = [
            os.fsdecode(raw)
            for raw in changed.split(b"\0")
            if raw and not _is_excluded(Path(os.fsdecode(raw)))
        ]
        if allowed:
            command = [
                "git",
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--no-renames",
            ]
            if resolved_ref is not None:
                command.append(resolved_ref)
            command.append("--")
            command.extend(f":(literal){path}" for path in allowed)
            output = self._run_spooled(command, project.path)
        else:
            output = ""
        return {
            "project_id": project_id,
            "diff": output,
            "truncated": False,
        }

    def commit_range(
        self,
        project_id: str,
        checkout_id: str,
        base_revision: str,
        head_revision: str,
    ) -> dict[str, Any]:
        """Read one exact, immutable Git range through the selected checkout."""
        project = self.code_checkout(
            project_id, checkout_id, write=False, require_explicit=True
        )

        def resolve(revision: str) -> str:
            if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
                raise ProjectError("commit revision is malformed")
            resolved = self._run_spooled(
                [
                    "git",
                    "rev-parse",
                    "--verify",
                    "--end-of-options",
                    f"{revision}^{{commit}}",
                ],
                project.path,
            ).strip()
            if not re.fullmatch(r"[0-9a-f]{40,64}", resolved):
                raise ProjectError("commit revision did not resolve to a commit")
            return resolved

        base = resolve(base_revision)
        head = resolve(head_revision)
        merge_base = self._run_spooled(
            ["git", "merge-base", base, head], project.path
        ).strip()
        if not re.fullmatch(r"[0-9a-f]{40,64}", merge_base):
            raise ProjectError("commit range has no merge base")
        content = self._run_spooled(
            ["git", "diff", "--no-ext-diff", "--no-textconv", f"{base}..{head}", "--"],
            project.path,
        )
        return {
            "base_revision": base,
            "head_revision": head,
            "range": f"{base}..{head}",
            "relation": "base_is_ancestor" if merge_base == base else "diverged",
            "merge_base": merge_base,
            "diff": content,
            "truncated": False,
        }

    def summary(
        self, project_id: str, checkout_id: str | None = None
    ) -> dict[str, Any]:
        project = self.code_checkout(
            project_id, checkout_id, write=False, require_explicit=False
        )
        status = self._run_spooled(
            ["git", "status", "--porcelain=v2", "--branch"], project.path
        )
        branch: dict[str, Any] = {
            "head": None,
            "upstream": None,
            "ahead": 0,
            "behind": 0,
        }
        changes = {"staged": 0, "unstaged": 0, "untracked": 0, "conflicted": 0}
        for line in status.splitlines():
            if line.startswith("# branch.head "):
                branch["head"] = line.removeprefix("# branch.head ")
                continue
            if line.startswith("# branch.upstream "):
                branch["upstream"] = line.removeprefix("# branch.upstream ")
                continue
            if line.startswith("# branch.ab "):
                for value in line.removeprefix("# branch.ab ").split():
                    if value.startswith("+"):
                        branch["ahead"] = int(value[1:])
                    elif value.startswith("-"):
                        branch["behind"] = int(value[1:])
                continue
            if line.startswith(("1 ", "2 ")):
                fields = line.split(maxsplit=2)
                xy = fields[1]
                if xy[0] != ".":
                    changes["staged"] += 1
                if xy[1] != ".":
                    changes["unstaged"] += 1
                continue
            if line.startswith("u "):
                changes["conflicted"] += 1
                continue
            if line.startswith("? "):
                changes["untracked"] += 1
        head_id = self._run_spooled(
            ["git", "rev-parse", "--verify", "--quiet", "HEAD"], project.path
        ).strip()
        commit: dict[str, str] | None = None
        if head_id:
            latest = self._run_spooled(
                ["git", "log", "-1", "--format=%H%x09%cI%x09%s"], project.path
            ).rstrip("\n")
            commit_id, committed_at, subject = latest.split("\t", maxsplit=2)
            commit = {
                "id": commit_id,
                "committed_at": committed_at,
                "subject": subject[:4_096],
                "subject_truncated": len(subject) > 4_096,
            }
        return {
            "project_id": project.project_id,
            "default_ref": project.default_ref,
            "branch": branch,
            "changes": changes,
            "latest_commit": commit,
        }

    def summary_revision(self, project_id: str) -> str:
        """Return the semantic inputs that determine ``summary``."""
        project = self._project(project_id)
        status = self._run_spooled(
            ["git", "status", "--porcelain=v2", "--branch"], project.path
        )
        head = next(
            (
                line.removeprefix("# branch.oid ")
                for line in status.splitlines()
                if line.startswith("# branch.oid ")
            ),
            "",
        )
        return hashlib.sha256(
            json.dumps(
                {"head": head, "status": status},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    def write(
        self,
        project_id: str,
        path: str,
        content: str,
        checkout_id: str | None = None,
        preconditions: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._locked_mutation(project_id, checkout_id, preconditions) as project:
            parts = _mutation_parts(project, path)
            parent = _open_pinned_directory(project, parts[:-1], create=True)
            try:
                try:
                    current = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    mode = 0o644
                else:
                    if not stat.S_ISREG(current.st_mode):
                        raise ProjectError("path must identify a regular project file")
                    mode = stat.S_IMODE(current.st_mode)
                _atomic_publish(parent, parts[-1], content.encode(), mode)
            finally:
                os.close(parent)
        return {"project_id": project_id, "path": path, "bytes": len(content.encode())}

    @staticmethod
    def _owner_result(
        command: list[str],
        cwd: Path,
        *,
        stdin_bytes: bytes | None = None,
        environment: Mapping[str, str] | None = None,
        timeout: int = 20,
        max_output_bytes: int = 64_000,
    ) -> bytes:
        safe_env = {
            "HOME": str(Path.home()),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PATH": os.environ.get("PATH", "/run/current-system/sw/bin"),
            "GIT_OPTIONAL_LOCKS": "0",
        }
        if environment:
            safe_env.update(environment)
        result = OwnerExecution(safe_env).run(
            command,
            ExecutionProfile(
                route=OwnerRoute("project-apply-patch"),
                cwd=cwd,
                timeout_seconds=timeout,
                max_stdout_bytes=max_output_bytes,
                max_stderr_bytes=max_output_bytes,
                stdin_bytes=stdin_bytes,
                environment=environment,
            ),
        )
        if result.timed_out:
            raise ProjectError("project operation timed out")
        if result.output_exceeded:
            raise ProjectError("project operation exceeded its output bound")
        if result.failure_class is not None or result.exit_status != 0:
            diagnostic = result.stderr.decode("utf-8", errors="replace").strip()
            output = result.stdout.decode("utf-8", errors="replace").strip()
            raise ProjectError(diagnostic or output or "project operation failed")
        return result.stdout

    def _patch_paths(self, root: Path, patch: bytes) -> tuple[str, ...]:
        output = self._owner_result(
            ["git", "apply", "--numstat", "-z", "--whitespace=nowarn", "-"],
            root,
            stdin_bytes=patch,
        )
        paths: list[str] = []
        for row in output.split(b"\0"):
            if not row:
                continue
            fields = row.split(b"\t", 2)
            if len(fields) != 3:
                raise ProjectError("git apply returned malformed path metadata")
            paths.append(os.fsdecode(fields[2]))
        return tuple(dict.fromkeys(paths))

    def _index_entry(
        self, root: Path, index: Path, relative: str
    ) -> tuple[int, str] | None:
        output = self._owner_result(
            ["git", "ls-files", "--stage", "-z", "--", relative],
            root,
            environment={"GIT_INDEX_FILE": str(index)},
        )
        if not output:
            return None
        row = output.rstrip(b"\0").split(b"\0")[-1]
        metadata, raw_path = row.split(b"\t", 1)
        mode, object_id, stage = metadata.split()
        if stage != b"0" or os.fsdecode(raw_path) != relative:
            raise ProjectError("git apply returned an unsupported index entry")
        return int(mode, 8), os.fsdecode(object_id)

    def _index_blob(self, root: Path, index: Path, object_id: str) -> bytes:
        return self._owner_result(
            ["git", "cat-file", "blob", object_id],
            root,
            environment={"GIT_INDEX_FILE": str(index)},
            max_output_bytes=self.config.max_result_bytes,
        )

    def _seed_index_entry(
        self,
        root: Path,
        index: Path,
        parent: int,
        target_name: str,
        relative: str,
    ) -> None:
        try:
            metadata = os.stat(target_name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        if stat.S_ISLNK(metadata.st_mode):
            content = os.readlink(target_name, dir_fd=parent).encode(
                "utf-8", errors="surrogateescape"
            )
            mode = 0o120000
        elif stat.S_ISREG(metadata.st_mode):
            descriptor = os.open(
                target_name,
                os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                dir_fd=parent,
            )
            try:
                with os.fdopen(descriptor, "rb") as handle:
                    content = handle.read(self.config.max_result_bytes + 1)
            except BaseException:
                raise
            if len(content) > self.config.max_result_bytes:
                raise ProjectError("patched project file exceeds configured bound")
            mode = 0o100755 if metadata.st_mode & 0o111 else 0o100644
        else:
            raise ProjectError("git patch target has an unsupported file type")
        object_id = (
            self._owner_result(
                ["git", "hash-object", "-w", "--stdin"],
                root,
                stdin_bytes=content,
            )
            .decode()
            .strip()
        )
        if not re.fullmatch(r"[0-9a-f]{40,64}", object_id):
            raise ProjectError("git returned a malformed patch seed object")
        self._owner_result(
            [
                "git",
                "update-index",
                "--add",
                "--cacheinfo",
                format(mode, "o"),
                object_id,
                relative,
            ],
            root,
            environment={"GIT_INDEX_FILE": str(index)},
        )

    def _index_tree(self, root: Path, index: Path) -> str:
        tree = (
            self._owner_result(
                ["git", "write-tree"],
                root,
                environment={"GIT_INDEX_FILE": str(index)},
            )
            .decode()
            .strip()
        )
        if not re.fullmatch(r"[0-9a-f]{40,64}", tree):
            raise ProjectError("git returned a malformed temporary tree")
        return tree

    def _changed_tree_paths(
        self, root: Path, before_tree: str, after_tree: str
    ) -> tuple[str, ...]:
        output = self._owner_result(
            [
                "git",
                "diff",
                "--name-only",
                "-z",
                "--no-renames",
                before_tree,
                after_tree,
                "--",
            ],
            root,
            max_output_bytes=self.config.max_result_bytes,
        )
        return tuple(os.fsdecode(path) for path in output.split(b"\0") if path)

    def _publish_index_entry(
        self,
        project: ProjectConfig,
        relative: str,
        entry: tuple[int, bytes] | None,
        *,
        pinned_parent: int | None = None,
    ) -> None:
        parts = _mutation_parts(project, relative)
        parent = (
            pinned_parent
            if pinned_parent is not None
            else _open_pinned_directory(project, parts[:-1], create=entry is not None)
        )
        try:
            if entry is None:
                _unlink_at(parent, parts[-1])
                return
            mode, content = entry
            if stat.S_ISREG(mode):
                _atomic_publish(parent, parts[-1], content, mode)
            elif stat.S_ISLNK(mode):
                _atomic_publish_symlink(
                    parent,
                    parts[-1],
                    content.decode("utf-8", errors="surrogateescape"),
                )
            else:
                raise ProjectError("git apply produced an unsupported file type")
        finally:
            if pinned_parent is None:
                os.close(parent)

    def apply_patch(
        self,
        project_id: str,
        patch: str,
        checkout_id: str | None = None,
        preconditions: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if len(patch.encode()) > self.config.max_result_bytes:
            raise ProjectError("patch exceeds configured bound")
        with self._locked_mutation(project_id, checkout_id, preconditions) as project:
            patch_bytes = patch.encode()
            root = _open_pinned_directory(project, (), create=False)
            root_path = Path(f"/proc/self/fd/{root}")
            pinned_parents: dict[tuple[str, ...], int] = {}

            def pin_parent(relative: str) -> None:
                parts = _mutation_parts(project, relative)
                parent_parts = parts[:-1]
                if parent_parts not in pinned_parents:
                    try:
                        pinned_parents[parent_parts] = _open_pinned_directory(
                            project, parent_parts, create=False
                        )
                    except ProjectError as exc:
                        if str(exc) != "path does not exist":
                            raise

            try:
                paths = self._patch_paths(root_path, patch_bytes)
                for relative in paths:
                    pin_parent(relative)
                with tempfile.TemporaryDirectory(
                    prefix="sinnix-gateway-apply-"
                ) as staging:
                    index = Path(staging) / "index"
                    environment = {"GIT_INDEX_FILE": str(index)}
                    try:
                        self._owner_result(
                            ["git", "read-tree", "HEAD"],
                            root_path,
                            environment=environment,
                        )
                    except ProjectError as exc:
                        if not any(
                            marker in str(exc)
                            for marker in (
                                "bad revision",
                                "ambiguous argument",
                                "Not a valid object name HEAD",
                            )
                        ):
                            raise
                    for relative in paths:
                        parts = _mutation_parts(project, relative)
                        parent = pinned_parents.get(parts[:-1])
                        if parent is not None:
                            self._seed_index_entry(
                                root_path,
                                index,
                                parent,
                                parts[-1],
                                relative,
                            )
                    before_tree = self._index_tree(root_path, index)
                    self._owner_result(
                        ["git", "apply", "--cached", "--whitespace=nowarn", "-"],
                        root_path,
                        stdin_bytes=patch_bytes,
                        environment=environment,
                    )
                    after_tree = self._index_tree(root_path, index)
                    changed_paths = self._changed_tree_paths(
                        root_path, before_tree, after_tree
                    )
                    missing_seeds = tuple(
                        path for path in changed_paths if path not in paths
                    )
                    if missing_seeds:
                        # Git's numstat reports only a rename destination. The
                        # private first application reveals its source too;
                        # seed that source from the working tree before any
                        # publication, then apply against those actual bytes.
                        self._owner_result(
                            ["git", "read-tree", before_tree],
                            root_path,
                            environment=environment,
                        )
                        for relative in missing_seeds:
                            pin_parent(relative)
                            parts = _mutation_parts(project, relative)
                            parent = pinned_parents.get(parts[:-1])
                            if parent is not None:
                                self._seed_index_entry(
                                    root_path, index, parent, parts[-1], relative
                                )
                        before_tree = self._index_tree(root_path, index)
                        self._owner_result(
                            ["git", "apply", "--cached", "--whitespace=nowarn", "-"],
                            root_path,
                            stdin_bytes=patch_bytes,
                            environment=environment,
                        )
                        after_tree = self._index_tree(root_path, index)
                    paths = self._changed_tree_paths(root_path, before_tree, after_tree)
                    for relative in paths:
                        _mutation_parts(project, relative)
                    after = {
                        relative: self._index_entry(root_path, index, relative)
                        for relative in paths
                    }
                    changes: list[tuple[str, tuple[int, bytes] | None]] = []
                    for relative in paths:
                        entry = after[relative]
                        changes.append(
                            (
                                relative,
                                None
                                if entry is None
                                else (
                                    entry[0],
                                    self._index_blob(root_path, index, entry[1]),
                                ),
                            )
                        )
                    # Create replacements before retiring their sources. A
                    # failed destination write must not delete the only copy.
                    for relative, entry in sorted(
                        changes, key=lambda change: change[1] is None
                    ):
                        parts = _mutation_parts(project, relative)
                        self._publish_index_entry(
                            project,
                            relative,
                            entry,
                            pinned_parent=pinned_parents.get(parts[:-1]),
                        )
            finally:
                for parent in pinned_parents.values():
                    os.close(parent)
                os.close(root)
        return {"project_id": project_id, "applied": True}
