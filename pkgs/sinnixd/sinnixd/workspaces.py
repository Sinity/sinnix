from __future__ import annotations

import re
import hashlib
import io
import os
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from sinnix_lib.atomic_json import modify_json, read_json, write_json_atomic
from sinnix_lib.lock import flock

from .projects import ProjectAdapter, ProjectCatalog, RegisteredCheckout


WORKSPACE_SCHEMA_VERSION = 1
CHECKPOINT_SCHEMA_VERSION = 1
MAX_CHECKPOINT_BYTES = 64 * 1024 * 1024
MAX_UNTRACKED_FILES = 4096
_NAME = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?\Z")


class WorkspaceError(ValueError):
    """A workspace request violates declared Git authority or preservation rules."""


@dataclass(frozen=True)
class WorkspaceRecord:
    workspace_id: str
    project_id: str
    name: str
    path: Path
    branch: str
    base: str
    created_at: str
    managed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": WORKSPACE_SCHEMA_VERSION,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "name": self.name,
            "path": str(self.path),
            "branch": self.branch,
            "base": self.base,
            "created_at": self.created_at,
            "managed": self.managed,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> WorkspaceRecord:
        required = {
            "schema_version", "workspace_id", "project_id", "name", "path", "branch", "base", "created_at", "managed"
        }
        if set(value) != required or value.get("schema_version") != WORKSPACE_SCHEMA_VERSION:
            raise WorkspaceError("workspace record schema is invalid")
        strings = {key: value.get(key) for key in required - {"schema_version", "managed"}}
        if any(not isinstance(item, str) or not item for item in strings.values()) or not isinstance(value.get("managed"), bool):
            raise WorkspaceError("workspace record fields are invalid")
        return cls(
            workspace_id=strings["workspace_id"],
            project_id=strings["project_id"],
            name=strings["name"],
            path=Path(strings["path"]),
            branch=strings["branch"],
            base=strings["base"],
            created_at=strings["created_at"],
            managed=value["managed"],
        )


@dataclass(frozen=True)
class CheckpointRecord:
    checkpoint_id: str
    workspace_id: str
    project_id: str
    head: str
    branch: str
    created_at: str
    staged_sha256: str
    unstaged_sha256: str
    untracked_sha256: str
    untracked_files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "checkpoint_id": self.checkpoint_id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "head": self.head,
            "branch": self.branch,
            "created_at": self.created_at,
            "staged_sha256": self.staged_sha256,
            "unstaged_sha256": self.unstaged_sha256,
            "untracked_sha256": self.untracked_sha256,
            "untracked_files": list(self.untracked_files),
        }


class WorkspaceStore:
    def __init__(self, root: Path) -> None:
        self.root = root / "workspaces"
        self.index = self.root / "index.json"
        self.checkpoints_root = self.root / "checkpoints"

    def records(self) -> tuple[WorkspaceRecord, ...]:
        payload = read_json(self.index, {"schema_version": WORKSPACE_SCHEMA_VERSION, "workspaces": []})
        if not isinstance(payload, Mapping) or payload.get("schema_version") != WORKSPACE_SCHEMA_VERSION:
            raise WorkspaceError("workspace index schema is invalid")
        rows = payload.get("workspaces")
        if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
            raise WorkspaceError("workspace index rows are invalid")
        return tuple(WorkspaceRecord.from_dict(row) for row in rows)

    def put(self, record: WorkspaceRecord) -> None:
        default = {"schema_version": WORKSPACE_SCHEMA_VERSION, "workspaces": []}
        with modify_json(self.index, default, mode=0o600) as payload:
            if not isinstance(payload, dict) or payload.get("schema_version") != WORKSPACE_SCHEMA_VERSION:
                raise WorkspaceError("workspace index schema is invalid")
            rows = payload.get("workspaces")
            if not isinstance(rows, list):
                raise WorkspaceError("workspace index rows are invalid")
            existing = [WorkspaceRecord.from_dict(row) for row in rows]
            if any(item.workspace_id == record.workspace_id for item in existing):
                raise WorkspaceError("workspace ID already exists")
            if any(item.project_id == record.project_id and (item.name == record.name or item.path == record.path) for item in existing):
                raise WorkspaceError("workspace name or path is already registered")
            rows.append(record.to_dict())

    def remove(self, workspace_id: str) -> WorkspaceRecord:
        default = {"schema_version": WORKSPACE_SCHEMA_VERSION, "workspaces": []}
        with modify_json(self.index, default, mode=0o600) as payload:
            if not isinstance(payload, dict) or payload.get("schema_version") != WORKSPACE_SCHEMA_VERSION:
                raise WorkspaceError("workspace index schema is invalid")
            rows = payload.get("workspaces")
            if not isinstance(rows, list):
                raise WorkspaceError("workspace index rows are invalid")
            records = [WorkspaceRecord.from_dict(row) for row in rows]
            removed = next((record for record in records if record.workspace_id == workspace_id), None)
            if removed is None:
                raise KeyError(f"unknown workspace: {workspace_id}")
            payload["workspaces"] = [
                record.to_dict() for record in records if record.workspace_id != workspace_id
            ]
        shutil.rmtree(self.checkpoints_root / workspace_id, ignore_errors=True)
        return removed

    def checkpoint_path(self, workspace_id: str, checkpoint_id: str) -> Path:
        return self.checkpoints_root / workspace_id / checkpoint_id

    def put_checkpoint(self, record: CheckpointRecord, staged: bytes, unstaged: bytes, untracked: bytes) -> None:
        root = self.checkpoint_path(record.workspace_id, record.checkpoint_id)
        root.mkdir(mode=0o700, parents=True)
        for name, content in (("staged.patch", staged), ("unstaged.patch", unstaged), ("untracked.tar", untracked)):
            self._write_private(root / name, content)
        write_json_atomic(root / "record.json", record.to_dict(), mode=0o600, fsync=True)

    def checkpoint(self, workspace_id: str, checkpoint_id: str) -> tuple[CheckpointRecord, Path]:
        root = self.checkpoint_path(workspace_id, checkpoint_id)
        value = read_json(root / "record.json")
        if not isinstance(value, Mapping) or value.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
            raise WorkspaceError("checkpoint record is unavailable or invalid")
        files = value.get("untracked_files")
        fields = (
            "checkpoint_id", "workspace_id", "project_id", "head", "branch", "created_at",
            "staged_sha256", "unstaged_sha256", "untracked_sha256",
        )
        if any(not isinstance(value.get(field), str) or not value[field] for field in fields):
            raise WorkspaceError("checkpoint record fields are invalid")
        if not isinstance(files, list) or any(not isinstance(item, str) or not item for item in files):
            raise WorkspaceError("checkpoint untracked manifest is invalid")
        return CheckpointRecord(*(value[field] for field in fields), tuple(files)), root

    @staticmethod
    def _write_private(path: Path, content: bytes) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)


class GitWorkspaces:
    def __init__(self, projects: ProjectCatalog, store: WorkspaceStore) -> None:
        self.projects = projects
        self.store = store

    @property
    def mutation_lock(self) -> Path:
        return self.store.root / "mutation.lock"

    def list(self, project_id: str | None = None) -> dict[str, Any]:
        records = self.store.records()
        if project_id is not None:
            self.projects.get(project_id)
            records = tuple(record for record in records if record.project_id == project_id)
        return {"workspaces": [self._status(record) for record in records]}

    def get(self, workspace_id: str) -> dict[str, Any]:
        record = self._record(workspace_id)
        return self._status(record)

    def create(self, *, project_id: str, name: str, branch: str, base: str | None) -> dict[str, Any]:
        project = self._project(project_id)
        policy = project.workspace
        assert policy is not None
        self._validate_name(name)
        self._validate_branch(project.root, branch)
        resolved_base = base or policy.default_base
        self._verify_ref(project.root, resolved_base, "base")
        path = policy.root / name
        self._validate_target(policy.root, path)
        with flock(self.mutation_lock):
            if path.exists() or any(record.project_id == project_id and record.name == name for record in self.store.records()):
                raise WorkspaceError("workspace target or name already exists")
            branch_exists = self._git(project.root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0
            arguments = ["worktree", "add"]
            if not branch_exists:
                arguments.extend(["-b", branch])
            arguments.append(str(path))
            arguments.append(branch if branch_exists else resolved_base)
            result = self._git(project.root, *arguments, check=False)
            if result.returncode != 0:
                raise WorkspaceError(result.stderr.strip() or "git worktree add failed")
            checkout = self._checkout_by_path(project_id, path)
            record = self._new_record(project, name, checkout, resolved_base, managed=True)
            try:
                self.store.put(record)
            except BaseException:
                self._git(project.root, "worktree", "remove", str(path), check=False)
                if not branch_exists:
                    self._git(project.root, "branch", "-D", branch, check=False)
                raise
        return self._status(record)

    def adopt(self, *, project_id: str, checkout_id: str, name: str) -> dict[str, Any]:
        project = self._project(project_id)
        self._validate_name(name)
        with flock(self.mutation_lock):
            checkout = self.projects.checkout(project_id, checkout_id)
            if checkout.path == project.root:
                raise WorkspaceError("the configured project root cannot be adopted as a managed workspace")
            branch = self._branch(checkout.path)
            record = self._new_record(project, name, checkout, checkout.head, managed=False, branch=branch)
            self.store.put(record)
        return self._status(record)

    def reap(self, workspace_id: str) -> dict[str, Any]:
        with flock(self.mutation_lock):
            record = self._record(workspace_id)
            status = self._status(record)
            if status["state"] == "missing":
                self.store.remove(workspace_id)
                return {"workspace_id": workspace_id, "reaped": True, "relationship_only": True}
            if not record.managed:
                raise WorkspaceError("adopted workspaces cannot be reaped")
            if status["dirty"] or not status["identity_matches"]:
                raise WorkspaceError("workspace is dirty or its branch identity changed")
            project = self._project(record.project_id)
            assert project.workspace is not None
            head = status["head"]
            if not isinstance(head, str) or self._git(
                project.root,
                "merge-base",
                "--is-ancestor",
                head,
                project.workspace.default_base,
                check=False,
            ).returncode != 0:
                raise WorkspaceError("workspace HEAD is not contained in the declared base")
            removed = self._git(project.root, "worktree", "remove", str(record.path), check=False)
            if removed.returncode != 0:
                raise WorkspaceError(removed.stderr.strip() or "git worktree remove failed")
            self.store.remove(workspace_id)
            return {
                "workspace_id": workspace_id,
                "reaped": True,
                "relationship_only": False,
                "retained_branch": record.branch,
            }

    def checkpoint(self, workspace_id: str) -> dict[str, Any]:
        with flock(self.mutation_lock):
            record = self._record(workspace_id)
            checkout, project = self._available(record)
            assert project.workspace is not None
            staged = self._git_bytes(checkout.path, "diff", "--cached", "--binary", "HEAD", "--")
            unstaged = self._git_bytes(checkout.path, "diff", "--binary", "--")
            untracked_files = self._untracked(checkout.path)
            if untracked_files and not project.workspace.checkpoint_untracked:
                raise WorkspaceError("project policy forbids checkpointing untracked files")
            untracked = self._archive_untracked(checkout.path, untracked_files)
            if sum(map(len, (staged, unstaged, untracked))) > MAX_CHECKPOINT_BYTES:
                raise WorkspaceError("checkpoint exceeds the configured byte bound")
            checkpoint = CheckpointRecord(
                checkpoint_id=str(uuid4()),
                workspace_id=record.workspace_id,
                project_id=record.project_id,
                head=checkout.head,
                branch=record.branch,
                created_at=datetime.now(UTC).isoformat(),
                staged_sha256=self._digest(staged),
                unstaged_sha256=self._digest(unstaged),
                untracked_sha256=self._digest(untracked),
                untracked_files=untracked_files,
            )
            self.store.put_checkpoint(checkpoint, staged, unstaged, untracked)
            return checkpoint.to_dict()

    def restore(self, workspace_id: str, checkpoint_id: str) -> dict[str, Any]:
        with flock(self.mutation_lock):
            record = self._record(workspace_id)
            checkout, project = self._available(record)
            checkpoint, root = self.store.checkpoint(workspace_id, checkpoint_id)
            if checkpoint.workspace_id != record.workspace_id or checkpoint.project_id != record.project_id:
                raise WorkspaceError("checkpoint authority does not match workspace")
            if checkout.head != checkpoint.head or record.branch != checkpoint.branch:
                raise WorkspaceError("checkpoint source HEAD or branch no longer matches workspace")
            if self._git(checkout.path, "status", "--porcelain", "--untracked-files=all").stdout:
                raise WorkspaceError("checkpoint restore requires a clean workspace")
            self._identity_check(project, checkout.path)
            staged = self._verified_artifact(root / "staged.patch", checkpoint.staged_sha256)
            unstaged = self._verified_artifact(root / "unstaged.patch", checkpoint.unstaged_sha256)
            untracked = self._verified_artifact(root / "untracked.tar", checkpoint.untracked_sha256)
            self._apply_patch(checkout.path, staged, index=True)
            self._apply_patch(checkout.path, unstaged, index=False)
            self._extract_untracked(checkout.path, untracked, checkpoint.untracked_files)
            return {"workspace_id": workspace_id, "checkpoint_id": checkpoint_id, "restored": True}

    def _status(self, record: WorkspaceRecord) -> dict[str, Any]:
        row = record.to_dict()
        try:
            checkout = self._checkout_by_path(record.project_id, record.path)
            branch = self._branch(checkout.path)
            dirty = bool(self._git(checkout.path, "status", "--porcelain", "--untracked-files=all").stdout)
            row.update(
                {
                    "state": "available",
                    "checkout_id": checkout.checkout_id,
                    "head": checkout.head,
                    "current_branch": branch,
                    "dirty": dirty,
                    "identity_matches": branch == record.branch,
                }
            )
        except (FileNotFoundError, KeyError, WorkspaceError):
            row.update({"state": "missing", "checkout_id": None, "head": None, "current_branch": None, "dirty": None, "identity_matches": False})
        return row

    def _record(self, workspace_id: str) -> WorkspaceRecord:
        for record in self.store.records():
            if record.workspace_id == workspace_id:
                return record
        raise KeyError(f"unknown workspace: {workspace_id}")

    def _project(self, project_id: str) -> ProjectAdapter:
        project = self.projects.get(project_id)
        if project.workspace is None:
            raise WorkspaceError(f"project {project_id!r} does not declare workspace policy")
        return project

    def _available(self, record: WorkspaceRecord) -> tuple[RegisteredCheckout, ProjectAdapter]:
        project = self._project(record.project_id)
        checkout = self._checkout_by_path(record.project_id, record.path)
        if self._branch(checkout.path) != record.branch:
            raise WorkspaceError("workspace branch identity changed")
        return checkout, project

    def _identity_check(self, project: ProjectAdapter, path: Path) -> None:
        assert project.workspace is not None
        result = subprocess.run(project.workspace.identity_check, cwd=path, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise WorkspaceError("workspace identity check failed")

    @classmethod
    def _git_bytes(cls, path: Path, *arguments: str) -> bytes:
        try:
            result = subprocess.run(["git", "-C", str(path), *arguments], capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as error:
            raise WorkspaceError("Git checkpoint operation failed") from error
        if result.returncode != 0:
            raise WorkspaceError(result.stderr.decode(errors="replace").strip() or "Git checkpoint operation failed")
        return result.stdout

    @classmethod
    def _untracked(cls, path: Path) -> tuple[str, ...]:
        raw = cls._git_bytes(path, "ls-files", "-z", "--others", "--exclude-standard")
        try:
            files = tuple(item.decode() for item in raw.split(b"\0") if item)
        except UnicodeDecodeError as error:
            raise WorkspaceError("untracked checkpoint paths must be UTF-8") from error
        if len(files) > MAX_UNTRACKED_FILES or any(Path(item).is_absolute() or ".." in Path(item).parts for item in files):
            raise WorkspaceError("untracked checkpoint manifest exceeds its safety bounds")
        return files

    @staticmethod
    def _archive_untracked(root: Path, files: tuple[str, ...]) -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for relative in files:
                source = root / relative
                try:
                    metadata = source.lstat()
                except OSError as error:
                    raise WorkspaceError("untracked checkpoint file disappeared") from error
                if not source.is_file() or source.is_symlink() or metadata.st_size > MAX_CHECKPOINT_BYTES:
                    raise WorkspaceError("untracked checkpoint entries must be bounded regular files")
                archive.add(source, arcname=relative, recursive=False)
                if buffer.tell() > MAX_CHECKPOINT_BYTES:
                    raise WorkspaceError("untracked checkpoint archive exceeds its byte bound")
        return buffer.getvalue()

    @staticmethod
    def _extract_untracked(root: Path, content: bytes, expected: tuple[str, ...]) -> None:
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:") as archive:
            members = archive.getmembers()
            if tuple(member.name for member in members) != expected:
                raise WorkspaceError("checkpoint archive does not match its manifest")
            for member in members:
                target = (root / member.name).resolve(strict=False)
                if root.resolve() not in target.parents or member.issym() or member.islnk() or not member.isfile():
                    raise WorkspaceError("checkpoint archive contains an unsafe entry")
            archive.extractall(root, members=members, filter="data")

    @classmethod
    def _apply_patch(cls, root: Path, content: bytes, *, index: bool) -> None:
        if not content:
            return
        arguments = ["git", "-C", str(root), "apply"]
        if index:
            arguments.append("--index")
        result = subprocess.run(arguments, input=content, capture_output=True, timeout=30)
        if result.returncode != 0:
            raise WorkspaceError(result.stderr.decode(errors="replace").strip() or "checkpoint patch failed")

    @staticmethod
    def _verified_artifact(path: Path, digest: str) -> bytes:
        try:
            content = path.read_bytes()
        except OSError as error:
            raise WorkspaceError("checkpoint artifact is unavailable") from error
        if GitWorkspaces._digest(content) != digest:
            raise WorkspaceError("checkpoint artifact digest mismatch")
        return content

    @staticmethod
    def _digest(content: bytes) -> str:
        return "sha256:" + hashlib.sha256(content).hexdigest()

    def _checkout_by_path(self, project_id: str, path: Path) -> RegisteredCheckout:
        resolved = path.resolve(strict=True)
        for checkout in self.projects.checkouts(project_id):
            if checkout.path == resolved:
                return checkout
        raise WorkspaceError("path is not a registered linked worktree")

    @staticmethod
    def _new_record(
        project: ProjectAdapter,
        name: str,
        checkout: RegisteredCheckout,
        base: str,
        *,
        managed: bool,
        branch: str | None = None,
    ) -> WorkspaceRecord:
        return WorkspaceRecord(
            workspace_id=str(uuid4()),
            project_id=project.project_id,
            name=name,
            path=checkout.path,
            branch=branch or GitWorkspaces._branch(checkout.path),
            base=base,
            created_at=datetime.now(UTC).isoformat(),
            managed=managed,
        )

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise WorkspaceError("workspace name must be a lowercase path-safe identifier up to 64 characters")

    @staticmethod
    def _validate_target(root: Path, path: Path) -> None:
        resolved_root = root.resolve(strict=False)
        resolved_path = path.resolve(strict=False)
        if resolved_path.parent != resolved_root:
            raise WorkspaceError("workspace target escapes the declared workspace root")

    @staticmethod
    def _git(path: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["git", "-C", str(path), *arguments], capture_output=True, text=True, timeout=10, check=False
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise WorkspaceError("Git workspace operation failed") from error
        if check and result.returncode != 0:
            raise WorkspaceError(result.stderr.strip() or "Git workspace operation failed")
        return result

    @classmethod
    def _validate_branch(cls, root: Path, branch: str) -> None:
        if not isinstance(branch, str) or not branch:
            raise WorkspaceError("workspace branch must be non-empty")
        result = cls._git(root, "check-ref-format", "--branch", branch, check=False)
        if result.returncode != 0 or branch.startswith("-"):
            raise WorkspaceError("workspace branch is invalid")

    @classmethod
    def _verify_ref(cls, root: Path, ref: str, label: str) -> None:
        if not isinstance(ref, str) or not ref or ref.startswith("-"):
            raise WorkspaceError(f"workspace {label} is invalid")
        if cls._git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False).returncode != 0:
            raise WorkspaceError(f"workspace {label} does not resolve to a commit")

    @classmethod
    def _branch(cls, path: Path) -> str:
        branch = cls._git(path, "symbolic-ref", "--quiet", "--short", "HEAD", check=False).stdout.strip()
        if not branch:
            raise WorkspaceError("detached worktrees cannot be managed workspaces")
        return branch
