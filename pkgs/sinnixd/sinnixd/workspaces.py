from __future__ import annotations

import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import tarfile
import tempfile
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

from sinnix_lib.atomic_json import modify_json, read_json, write_json_atomic
from sinnix_lib.lock import flock

from .projects import (
    ProjectAdapter,
    ProjectCatalog,
    ProjectConfigError,
    RegisteredCheckout,
    parse_worktree_records,
)

WORKSPACE_SCHEMA_VERSION = 1
CHECKPOINT_SCHEMA_VERSION = 1
MAX_CHECKPOINT_BYTES = 64 * 1024 * 1024
MAX_UNTRACKED_FILES = 4096
MAX_PROVISION_OUTPUT_BYTES = 64 * 1024
TESTMON_SEED_PATH = ".cache/testmon/testmondata"
_FICLONE = 0x40049409  # linux/fs.h FICLONE: reflink clone on supporting filesystems
_NAME = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?\Z")


class WorkspaceError(ValueError):
    """A workspace request violates declared Git authority or preservation rules."""


DEAD_PACKET_COLLISION_NOTE = "packet-dead-collision-recovered"
MISSING_WORKTREE_GC_NOTE = "workspace-missing-worktree-gc"


@dataclass(frozen=True)
class WorkspaceRecord:
    workspace_id: str
    project_id: str
    name: str
    path: Path
    branch: str
    base: str
    created_at: str
    provision_notes: tuple[dict[str, str], ...] = ()

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
            "provision_notes": [dict(note) for note in self.provision_notes],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> WorkspaceRecord:
        required = {
            "schema_version",
            "workspace_id",
            "project_id",
            "name",
            "path",
            "branch",
            "base",
            "created_at",
        }
        if (
            not required.issubset(value)
            or value.get("schema_version") != WORKSPACE_SCHEMA_VERSION
        ):
            raise WorkspaceError("workspace record schema is invalid")
        strings = {key: value.get(key) for key in required - {"schema_version"}}
        if any(not isinstance(item, str) or not item for item in strings.values()):
            raise WorkspaceError("workspace record fields are invalid")
        raw_notes = value.get("provision_notes", [])
        if not isinstance(raw_notes, list) or any(
            not isinstance(note, Mapping)
            or set(note)
            not in (
                {"kind", "path"},
                {"kind", "path", "output"},
            )
            or any(
                not isinstance(item, str) or (not item and key != "output")
                for key, item in note.items()
            )
            for note in raw_notes
        ):
            raise WorkspaceError("workspace provision notes are invalid")
        return cls(
            workspace_id=strings["workspace_id"],
            project_id=strings["project_id"],
            name=strings["name"],
            path=Path(strings["path"]),
            branch=strings["branch"],
            base=strings["base"],
            created_at=strings["created_at"],
            provision_notes=tuple(dict(note) for note in raw_notes),
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
        self.disposals = self.root / "disposals.jsonl"

    def records(self) -> tuple[WorkspaceRecord, ...]:
        payload = read_json(
            self.index, {"schema_version": WORKSPACE_SCHEMA_VERSION, "workspaces": []}
        )
        if (
            not isinstance(payload, Mapping)
            or payload.get("schema_version") != WORKSPACE_SCHEMA_VERSION
        ):
            raise WorkspaceError("workspace index schema is invalid")
        rows = payload.get("workspaces")
        if not isinstance(rows, list) or any(
            not isinstance(row, Mapping) for row in rows
        ):
            raise WorkspaceError("workspace index rows are invalid")
        return tuple(WorkspaceRecord.from_dict(row) for row in rows)

    def put(self, record: WorkspaceRecord) -> None:
        default = {"schema_version": WORKSPACE_SCHEMA_VERSION, "workspaces": []}
        with modify_json(self.index, default, mode=0o600) as payload:
            if (
                not isinstance(payload, dict)
                or payload.get("schema_version") != WORKSPACE_SCHEMA_VERSION
            ):
                raise WorkspaceError("workspace index schema is invalid")
            rows = payload.get("workspaces")
            if not isinstance(rows, list):
                raise WorkspaceError("workspace index rows are invalid")
            existing = [WorkspaceRecord.from_dict(row) for row in rows]
            if any(item.workspace_id == record.workspace_id for item in existing):
                raise WorkspaceError("workspace ID already exists")
            if any(
                item.project_id == record.project_id
                and (item.name == record.name or item.path == record.path)
                for item in existing
            ):
                raise WorkspaceError("workspace name or path is already registered")
            rows.append(record.to_dict())

    def remove(self, workspace_id: str) -> WorkspaceRecord:
        removed = self.remove_many((workspace_id,))
        if not removed:
            raise KeyError(f"unknown workspace: {workspace_id}")
        return removed[0]

    def remove_many(self, workspace_ids: Sequence[str]) -> tuple[WorkspaceRecord, ...]:
        ids = set(workspace_ids)
        if not ids:
            return ()
        default = {"schema_version": WORKSPACE_SCHEMA_VERSION, "workspaces": []}
        with modify_json(self.index, default, mode=0o600) as payload:
            if (
                not isinstance(payload, dict)
                or payload.get("schema_version") != WORKSPACE_SCHEMA_VERSION
            ):
                raise WorkspaceError("workspace index schema is invalid")
            rows = payload.get("workspaces")
            if not isinstance(rows, list):
                raise WorkspaceError("workspace index rows are invalid")
            records = [WorkspaceRecord.from_dict(row) for row in rows]
            removed = tuple(record for record in records if record.workspace_id in ids)
            payload["workspaces"] = [
                record.to_dict() for record in records if record.workspace_id not in ids
            ]
        for record in removed:
            shutil.rmtree(
                self.checkpoints_root / record.workspace_id, ignore_errors=True
            )
        return removed

    def checkpoint_path(self, workspace_id: str, checkpoint_id: str) -> Path:
        return self.checkpoints_root / workspace_id / checkpoint_id

    def record_disposal_evidence(self, value: Mapping[str, Any]) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(
            self.disposals,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
            0o600,
        )
        try:
            os.write(
                descriptor,
                (
                    json.dumps(dict(value), sort_keys=True, separators=(",", ":"))
                    + "\n"
                ).encode(),
            )
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def put_checkpoint(
        self, record: CheckpointRecord, staged: bytes, unstaged: bytes, untracked: bytes
    ) -> None:
        root = self.checkpoint_path(record.workspace_id, record.checkpoint_id)
        root.mkdir(mode=0o700, parents=True)
        for name, content in (
            ("staged.patch", staged),
            ("unstaged.patch", unstaged),
            ("untracked.tar", untracked),
        ):
            self._write_private(root / name, content)
        write_json_atomic(
            root / "record.json", record.to_dict(), mode=0o600, fsync=True
        )

    def checkpoint(
        self, workspace_id: str, checkpoint_id: str
    ) -> tuple[CheckpointRecord, Path]:
        root = self.checkpoint_path(workspace_id, checkpoint_id)
        value = read_json(root / "record.json")
        if (
            not isinstance(value, Mapping)
            or value.get("schema_version") != CHECKPOINT_SCHEMA_VERSION
        ):
            raise WorkspaceError("checkpoint record is unavailable or invalid")
        files = value.get("untracked_files")
        fields = (
            "checkpoint_id",
            "workspace_id",
            "project_id",
            "head",
            "branch",
            "created_at",
            "staged_sha256",
            "unstaged_sha256",
            "untracked_sha256",
        )
        if any(
            not isinstance(value.get(field), str) or not value[field]
            for field in fields
        ):
            raise WorkspaceError("checkpoint record fields are invalid")
        if not isinstance(files, list) or any(
            not isinstance(item, str) or not item for item in files
        ):
            raise WorkspaceError("checkpoint untracked manifest is invalid")
        return CheckpointRecord(*(value[field] for field in fields), tuple(files)), root

    def checkpoints(
        self, workspace_id: str
    ) -> tuple[tuple[CheckpointRecord, Path], ...]:
        root = self.checkpoints_root / workspace_id
        if not root.exists():
            return ()
        if not root.is_dir():
            raise WorkspaceError("workspace checkpoint directory is invalid")
        try:
            entries = tuple(sorted(root.iterdir()))
        except OSError as error:
            raise WorkspaceError("workspace checkpoints are unavailable") from error
        checkpoints = []
        for entry in entries:
            if not entry.is_dir():
                raise WorkspaceError("workspace checkpoint directory is invalid")
            checkpoint, checkpoint_root = self.checkpoint(workspace_id, entry.name)
            if checkpoint.checkpoint_id != entry.name:
                raise WorkspaceError("workspace checkpoint identity is invalid")
            checkpoints.append((checkpoint, checkpoint_root))
        return tuple(checkpoints)

    @staticmethod
    def _write_private(path: Path, content: bytes) -> None:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)


def _stop_type_daemon(worktree: Path) -> None:
    """Shut down the workspace's mypy daemon before the worktree disappears.

    dmypy holds a type cache worth well over a gigabyte and is reparented to
    the user manager, so it outlives both the run that started it and the
    directory it describes. Stopping it here is what makes keeping it cheap:
    the cache stays warm for as long as the workspace is gated repeatedly, and
    is released the moment the workspace is gone.
    """
    daemon = worktree / ".venv/bin/dmypy"
    if not daemon.is_file():
        return
    try:
        subprocess.run(
            [str(daemon), "stop"],
            cwd=worktree,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        pass


class GitWorkspaces:
    def __init__(self, projects: ProjectCatalog, store: WorkspaceStore) -> None:
        self.projects = projects
        self.store = store

    @property
    def mutation_lock(self) -> Path:
        return self.store.root / "mutation.lock"

    def list(self, project_id: str | None = None) -> dict[str, Any]:
        with flock(self.mutation_lock):
            records = self.store.records()
            if project_id is not None:
                self.projects.get(project_id)
                records = tuple(
                    record for record in records if record.project_id == project_id
                )
            statuses = [self._list_status(record) for record in records]
            self._gc_missing_locked(records)
            return {"workspaces": statuses}

    def get(self, workspace_id: str) -> dict[str, Any]:
        record = self._record(workspace_id)
        return self._status(record)

    def resolve_id(self, reference: str) -> str:
        """Return the canonical workspace ID for an ID or workspace name."""
        matches = [
            record
            for record in self.store.records()
            if reference in {record.workspace_id, record.name}
        ]
        if len(matches) != 1:
            qualifier = "ambiguous" if matches else "unknown"
            raise KeyError(f"{qualifier} workspace: {reference}")
        return matches[0].workspace_id

    def delivery_snapshot(
        self,
        workspace_id: str,
        start_head: str,
        *,
        scope: Sequence[str] = (),
        merge_base: bool = False,
    ) -> dict[str, Any]:
        """Read one exact-head Git fact set for a delivery precondition."""
        record = self._record(workspace_id)
        checkout, _project = self._available(record)
        before = self._git(checkout.path, "rev-parse", "HEAD").stdout.strip()
        if before != checkout.head:
            raise WorkspaceError("workspace HEAD changed during delivery snapshot")
        range_start = (
            self._git(checkout.path, "merge-base", start_head, before).stdout.strip()
            if merge_base
            else start_head
        )
        descendant = (
            self._git(
                checkout.path,
                "merge-base",
                "--is-ancestor",
                range_start,
                before,
                check=False,
            ).returncode
            == 0
        )
        changes = self._name_status(checkout.path, range_start, before)
        dirty = self._porcelain_status(checkout.path)
        after = self._git(checkout.path, "rev-parse", "HEAD").stdout.strip()
        if after != before:
            raise WorkspaceError("workspace HEAD changed during delivery snapshot")
        paths = tuple(path for change in changes for path in change["paths"])
        return {
            "workspace_id": workspace_id,
            "checkout_id": checkout.checkout_id,
            "start_head": range_start,
            "head": before,
            "descendant": descendant,
            "dirty": bool(dirty),
            "status": dirty,
            "changes": changes,
            "in_scope": all(self._scope_contains(path, scope) for path in paths)
            if scope
            else True,
        }

    def checkout(self, workspace_id: str) -> RegisteredCheckout:
        record = self._record(workspace_id)
        checkout, _project = self._available(record)
        return checkout

    def resolve_checkout(self, project_id: str, reference: str) -> RegisteredCheckout:
        self._project(project_id)
        records = tuple(
            record for record in self.store.records() if record.project_id == project_id
        )
        matches = [
            record
            for record in records
            if reference in {record.workspace_id, record.name}
        ]
        if not matches:
            for record in records:
                try:
                    checkout, _project = self._available(record)
                except (FileNotFoundError, KeyError, WorkspaceError):
                    continue
                if checkout.checkout_id == reference:
                    matches.append(record)
        if len(matches) != 1:
            qualifier = "ambiguous" if matches else "unknown"
            raise KeyError(f"{qualifier} workspace: {project_id}.{reference}")
        checkout, _project = self._available(matches[0])
        return checkout

    def drop(
        self,
        workspace_id: str,
        *,
        force: bool = False,
        expected_head: str | None = None,
        integration_target: str | None = None,
    ) -> dict[str, Any]:
        """Delete a workspace, its worktree, its branch, and its record.

        Without ``force`` the workspace must be clean, hold its declared branch
        identity, and prove its content is published: contained in the declared
        base, equal to ``expected_head`` for a merged review, tree-equivalent to
        ``integration_target``, or squash-equivalent to a base commit. ``force``
        is the operator's acknowledgement that the content is expendable.
        """
        with flock(self.mutation_lock):
            record = self._record(workspace_id)
            if self._path_state(record) == "missing":
                self._gc_missing_locked((record,))
                return {
                    "workspace_id": record.workspace_id,
                    "dropped": True,
                    "relationship_only": True,
                    "state": "missing",
                    "note": MISSING_WORKTREE_GC_NOTE,
                }
            status = self._status(record)
            checkout, project = self._available(record)
            assert project.workspace is not None
            publication_evidence: dict[str, Any] | None = None
            if not force:
                if status["state"] != "available" or not status["identity_matches"]:
                    raise WorkspaceError(
                        "workspace is unavailable or its branch identity changed"
                    )
                if status["dirty"]:
                    raise WorkspaceError("workspace must be clean before it is dropped")
                if expected_head is not None and checkout.head != expected_head:
                    raise WorkspaceError(
                        "merged review head no longer matches workspace HEAD"
                    )
                if integration_target is not None:
                    publication_evidence = self._integration_evidence(
                        project, checkout.head, integration_target
                    )
                elif (
                    expected_head is None
                    and not self._head_is_contained_in_declared_base(
                        project, checkout.head
                    )
                ):
                    publication_evidence = self._squash_equivalent_evidence(
                        project, record, checkout.head
                    )
                    if publication_evidence is None:
                        raise WorkspaceError(
                            "workspace has unpublished committed content"
                        )
                self._verify_disposable_checkpoints(workspace_id)
            elif not self._head_is_contained_in_declared_base(project, checkout.head):
                publication_evidence = {
                    "kind": "operator-acknowledged",
                    "default_base": project.workspace.default_base,
                    "branch_head": checkout.head,
                }
            if publication_evidence is not None:
                self.store.record_disposal_evidence(
                    {
                        "workspace_id": workspace_id,
                        "branch": record.branch,
                        "head": checkout.head,
                        **publication_evidence,
                    }
                )
            removed = self._remove_worktree(project, record, checkout)
            if removed.returncode != 0:
                raise WorkspaceError(
                    removed.stderr.strip() or "git worktree remove failed"
                )
            self._git(project.root, "branch", "-D", record.branch, check=False)
            self.store.remove(record.workspace_id)
            return {
                "workspace_id": record.workspace_id,
                "dropped": True,
                "relationship_only": False,
                "head": checkout.head,
                "deleted_branch": record.branch,
                **(
                    {"publication_evidence": publication_evidence}
                    if publication_evidence is not None
                    else {}
                ),
            }

    def _integration_evidence(
        self, project: ProjectAdapter, head: str, target_ref: str
    ) -> dict[str, Any]:
        """Prove a workspace's tree contribution is present in a declared-base commit."""
        self._verify_ref(project.root, target_ref, "integration target")
        assert project.workspace is not None
        if (
            self._git(
                project.root,
                "merge-base",
                "--is-ancestor",
                target_ref,
                project.workspace.default_base,
                check=False,
            ).returncode
            != 0
        ):
            raise WorkspaceError(
                "integration target is not contained in the declared default base"
            )
        if not self._tree_equivalent(project.root, target_ref, head):
            raise WorkspaceError(
                "workspace changes are not fully represented by the integration target"
            )
        return {
            "kind": "tree-equivalent-integration",
            "integration_target": self._git(
                project.root, "rev-parse", f"{target_ref}^{{commit}}"
            ).stdout.strip(),
        }

    def create(
        self,
        *,
        project_id: str,
        name: str,
        branch: str,
        base: str | None,
        recover_dead: bool = False,
        is_live: Callable[[Path], bool] | None = None,
    ) -> dict[str, Any]:
        with flock(self.mutation_lock):
            return self._create_locked(
                project_id=project_id,
                name=name,
                branch=branch,
                base=base,
                recover_dead=recover_dead,
                is_live=is_live,
            )

    def _create_locked(
        self,
        *,
        project_id: str,
        name: str,
        branch: str,
        base: str | None,
        recover_dead: bool = False,
        is_live: Callable[[Path], bool] | None = None,
    ) -> dict[str, Any]:
        project = self._project(project_id)
        policy = project.workspace
        assert policy is not None
        self._validate_name(name)
        self._validate_branch(project.root, branch)
        resolved_base = base or policy.default_base
        self._verify_ref(project.root, resolved_base, "base")
        resolved_base = self._git(
            project.root, "rev-parse", f"{resolved_base}^{{commit}}"
        ).stdout.strip()
        path = policy.root / name
        self._validate_target(policy.root, path)
        policy.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        existing = next(
            (
                record
                for record in self.store.records()
                if record.project_id == project_id
                and (record.name == name or record.path == path)
            ),
            None,
        )
        recovery_note: dict[str, Any] | None = None
        if path.exists() or existing is not None:
            if not recover_dead:
                raise WorkspaceError("workspace target or name already exists")
            recovery_note = self._recover_dead_collision_locked(
                project,
                name=name,
                branch=branch,
                base=resolved_base,
                path=path,
                record=existing,
                is_live=is_live,
            )
        branch_exists = (
            self._git(
                project.root,
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}",
                check=False,
            ).returncode
            == 0
        )
        staging_path = Path(tempfile.mkdtemp(prefix=f".{name}.", dir=policy.root))
        staging_path.rmdir()
        created_path = staging_path
        arguments = ["worktree", "add"]
        if not branch_exists:
            arguments.extend(["-b", branch])
        arguments.append(str(staging_path))
        arguments.append(branch if branch_exists else resolved_base)
        result = self._git(project.root, *arguments, check=False)
        if result.returncode != 0:
            self._cleanup_created_worktree(project, staging_path)
            raise WorkspaceError(result.stderr.strip() or "git worktree add failed")
        try:
            if path.exists():
                raise WorkspaceError("workspace target appeared during creation")
            moved = self._git(
                project.root,
                "worktree",
                "move",
                str(staging_path),
                str(path),
                check=False,
            )
            if moved.returncode != 0:
                raise WorkspaceError(moved.stderr.strip() or "git worktree move failed")
            created_path = path
            checkout = self._checkout_by_path(project_id, path)
            notes = self._provision(project, path)
            record = self._new_record(
                project,
                name,
                checkout,
                resolved_base,
                provision_notes=notes,
            )
        except BaseException:
            self._cleanup_created_worktree(project, created_path)
            if not branch_exists:
                self._git(project.root, "branch", "-D", branch, check=False)
            raise
        try:
            self.store.put(record)
        except BaseException:
            self._cleanup_created_worktree(project, path)
            if not branch_exists:
                self._git(project.root, "branch", "-D", branch, check=False)
            raise
        result = self._status(record)
        if recovery_note is not None:
            result["notes"] = [recovery_note]
        return result

    def _recover_dead_collision_locked(
        self,
        project: ProjectAdapter,
        *,
        name: str,
        branch: str,
        base: str,
        path: Path,
        record: WorkspaceRecord | None,
        is_live: Callable[[Path], bool] | None,
    ) -> dict[str, Any]:
        """Remove one proven packet orphan while the create lock is held."""
        if record is not None and (
            record.name != name or record.path != path or record.branch != branch
        ):
            raise WorkspaceError("workspace target or name already exists")
        if is_live is not None and is_live(path):
            raise WorkspaceError("workspace collision has a live job")

        if record is not None:
            status = self._status(record)
            if status["state"] == "available":
                if status["dirty"] or not status["identity_matches"]:
                    raise WorkspaceError("workspace collision contains work")
                head = status["head"]
                if not isinstance(head, str) or not self._head_is_contained_in_ref(
                    project, head, base
                ):
                    raise WorkspaceError(
                        "workspace collision contains unpublished work"
                    )
                removed = self._remove_worktree(project, record)
                if removed.returncode != 0:
                    raise WorkspaceError(
                        removed.stderr.strip() or "dead workspace cleanup failed"
                    )
            elif status["state"] != "missing":
                raise WorkspaceError("workspace collision cannot be inspected")
            else:
                worktree = self._worktree_record(project, path)
                if path.exists() and worktree is None:
                    raise WorkspaceError("workspace collision cannot be inspected")
                if worktree is not None:
                    self._cleanup_created_worktree(project, path)
            self._delete_branch_if_present(project, record.branch)
            self.store.remove(record.workspace_id)
            return {
                "kind": DEAD_PACKET_COLLISION_NOTE,
                "workspace_id": record.workspace_id,
                "name": name,
                "branch": record.branch,
            }

        worktree = self._worktree_record(project, path)
        if worktree is None:
            raise WorkspaceError("workspace target or name already exists")
        raw_branch = worktree.get("branch")
        expected_branch = f"refs/heads/{branch}"
        if raw_branch != expected_branch:
            raise WorkspaceError("workspace collision branch identity changed")
        if "locked" not in worktree:
            try:
                dirty = bool(
                    self._git(
                        path, "status", "--porcelain", "--untracked-files=all"
                    ).stdout
                )
            except WorkspaceError:
                raise WorkspaceError(
                    "workspace collision cannot be inspected"
                ) from None
            if dirty:
                raise WorkspaceError("workspace collision is still provisioning")
        head = self._git(project.root, "rev-parse", branch, check=False)
        if head.returncode != 0 or not self._head_is_contained_in_ref(
            project, head.stdout.strip(), base
        ):
            raise WorkspaceError("workspace collision contains unpublished work")
        self._cleanup_created_worktree(project, path)
        self._delete_branch_if_present(project, branch)
        return {
            "kind": DEAD_PACKET_COLLISION_NOTE,
            "workspace_id": None,
            "name": name,
            "branch": branch,
        }

    def _worktree_record(
        self, project: ProjectAdapter, path: Path
    ) -> dict[str, str] | None:
        output = self._git(project.root, "worktree", "list", "--porcelain")
        for record in parse_worktree_records(output.stdout):
            if record.get("worktree") == str(path):
                return record
        return None

    def _head_is_contained_in_ref(
        self, project: ProjectAdapter, head: str, target_ref: str
    ) -> bool:
        if not head:
            return False
        return (
            self._git(
                project.root,
                "merge-base",
                "--is-ancestor",
                head,
                target_ref,
                check=False,
            ).returncode
            == 0
        )

    def _delete_branch_if_present(self, project: ProjectAdapter, branch: str) -> None:
        result = self._git(project.root, "branch", "-D", branch, check=False)
        if (
            result.returncode != 0
            and self._git(
                project.root,
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}",
                check=False,
            ).returncode
            == 0
        ):
            raise WorkspaceError(
                result.stderr.strip() or "dead workspace branch cleanup failed"
            )

    def _cleanup_created_worktree(self, project: ProjectAdapter, path: Path) -> None:
        """Best-effort rollback for a worktree created by this transaction."""
        if not path.exists() and self._worktree_record(project, path) is None:
            return
        try:
            result = self._git(
                project.root,
                "worktree",
                "remove",
                "--force",
                "--force",
                str(path),
                check=False,
            )
        except WorkspaceError:
            # A provision hook may have left a descendant with the worktree as
            # its cwd. Git can then time out while removing the entry; remove
            # the path directly and let worktree prune discard the stale
            # administrative record below.
            result = None
        if (
            result is not None
            and result.returncode == 0
            and not path.exists()
            and self._worktree_record(project, path) is None
        ):
            return
        if path.exists():
            try:
                shutil.rmtree(path)
            except OSError as error:
                raise WorkspaceError("created workspace rollback failed") from error
        self._git(project.root, "worktree", "prune", "--expire", "now", check=False)
        if path.exists() or self._worktree_record(project, path) is not None:
            raise WorkspaceError(
                (result.stderr.strip() if result is not None else "")
                or "created workspace rollback failed"
            )

    def _tree_equivalent(self, root: Path, target_ref: str, source_ref: str) -> bool:
        target_tree = self._git(
            root, "rev-parse", f"{target_ref}^{{tree}}", check=False
        )
        merged_tree = self._git(
            root, "merge-tree", "--write-tree", target_ref, source_ref, check=False
        )
        return (
            target_tree.returncode == 0
            and merged_tree.returncode == 0
            and target_tree.stdout.strip() == merged_tree.stdout.strip()
        )

    def _head_is_contained_in_declared_base(
        self, project: ProjectAdapter, head: str
    ) -> bool:
        assert project.workspace is not None
        return (
            self._git(
                project.root,
                "merge-base",
                "--is-ancestor",
                head,
                project.workspace.default_base,
                check=False,
            ).returncode
            == 0
        )

    def _squash_equivalent_evidence(
        self, project: ProjectAdapter, record: WorkspaceRecord, head: str
    ) -> dict[str, Any] | None:
        assert project.workspace is not None
        changed = self._name_status(project.root, record.base, head)
        paths = tuple(path for change in changed for path in change["paths"])
        if not paths:
            equivalent = (
                self._git(
                    project.root,
                    "diff",
                    "--quiet",
                    project.workspace.default_base,
                    head,
                    "--",
                    check=False,
                ).returncode
                == 0
            )
        else:
            equivalent = all(
                self._git(
                    project.root,
                    "diff",
                    "--quiet",
                    project.workspace.default_base,
                    head,
                    "--",
                    path,
                    check=False,
                ).returncode
                == 0
                for path in paths
            )
        if not equivalent:
            return None
        return {
            "kind": "content-equality",
            "default_base": project.workspace.default_base,
            "branch_head": head,
            "branch_owned_paths": list(paths),
        }

    def _verify_disposable_checkpoints(self, workspace_id: str) -> None:
        for checkpoint, root in self.store.checkpoints(workspace_id):
            staged = self._verified_artifact(
                root / "staged.patch", checkpoint.staged_sha256
            )
            unstaged = self._verified_artifact(
                root / "unstaged.patch", checkpoint.unstaged_sha256
            )
            untracked = self._verified_artifact(
                root / "untracked.tar", checkpoint.untracked_sha256
            )
            try:
                with tarfile.open(fileobj=io.BytesIO(untracked), mode="r:") as archive:
                    archive_members = archive.getmembers()
            except tarfile.TarError as error:
                raise WorkspaceError("checkpoint archive is invalid") from error
            if staged or unstaged or checkpoint.untracked_files or archive_members:
                raise WorkspaceError(
                    "workspace checkpoint retains content that must be preserved"
                )

    def checkpoint(self, workspace_id: str) -> dict[str, Any]:
        with flock(self.mutation_lock):
            record = self._record(workspace_id)
            checkout, project = self._available(record)
            assert project.workspace is not None
            staged = self._git_bytes(
                checkout.path, "diff", "--cached", "--binary", "HEAD", "--"
            )
            unstaged = self._git_bytes(checkout.path, "diff", "--binary", "--")
            untracked_files = self._untracked(checkout.path)
            if untracked_files and not project.workspace.checkpoint_untracked:
                raise WorkspaceError(
                    "project policy forbids checkpointing untracked files"
                )
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

    def restore(
        self, workspace_id: str, checkpoint_id: str, *, recreate: bool = False
    ) -> dict[str, Any]:
        """Apply a checkpoint, recreating the worktree first when it is gone."""
        with flock(self.mutation_lock):
            recreated = False
            if (
                recreate
                and self._status(self._record(workspace_id))["state"] == "missing"
            ):
                self._recreate_worktree_locked(workspace_id, checkpoint_id)
                recreated = True
            try:
                restored = self._restore_locked(workspace_id, checkpoint_id)
            except BaseException:
                if recreated:
                    record = self._record(workspace_id)
                    self._remove_worktree(
                        self._project(record.project_id), record, "--force"
                    )
                raise
            if not recreated:
                return restored
            return {
                **restored,
                "recreated": True,
                "path": str(self._record(workspace_id).path),
            }

    def _restore_locked(self, workspace_id: str, checkpoint_id: str) -> dict[str, Any]:
        record = self._record(workspace_id)
        checkout, project = self._available(record)
        checkpoint, root = self.store.checkpoint(workspace_id, checkpoint_id)
        if (
            checkpoint.workspace_id != record.workspace_id
            or checkpoint.project_id != record.project_id
        ):
            raise WorkspaceError("checkpoint authority does not match workspace")
        if checkout.head != checkpoint.head or record.branch != checkpoint.branch:
            raise WorkspaceError(
                "checkpoint source HEAD or branch no longer matches workspace"
            )
        if self._git(
            checkout.path, "status", "--porcelain", "--untracked-files=all"
        ).stdout:
            raise WorkspaceError("checkpoint restore requires a clean workspace")
        self._identity_check(project, checkout.path)
        staged = self._verified_artifact(
            root / "staged.patch", checkpoint.staged_sha256
        )
        unstaged = self._verified_artifact(
            root / "unstaged.patch", checkpoint.unstaged_sha256
        )
        untracked = self._verified_artifact(
            root / "untracked.tar", checkpoint.untracked_sha256
        )
        self._apply_patch(checkout.path, staged, index=True)
        self._apply_patch(checkout.path, unstaged, index=False)
        self._extract_untracked(checkout.path, untracked, checkpoint.untracked_files)
        return {
            "workspace_id": workspace_id,
            "checkpoint_id": checkpoint_id,
            "restored": True,
        }

    def _recreate_worktree_locked(self, workspace_id: str, checkpoint_id: str) -> None:
        record = self._record(workspace_id)
        checkpoint, _root = self.store.checkpoint(workspace_id, checkpoint_id)
        if (
            checkpoint.project_id != record.project_id
            or checkpoint.branch != record.branch
        ):
            raise WorkspaceError("checkpoint authority does not match workspace")
        project = self._project(record.project_id)
        branch_head = self._git(
            project.root, "rev-parse", "--verify", f"{record.branch}^{{commit}}"
        ).stdout.strip()
        if branch_head != checkpoint.head:
            raise WorkspaceError("workspace branch no longer matches checkpoint HEAD")
        assert project.workspace is not None
        self._validate_target(project.workspace.root, record.path)
        result = self._git(
            project.root,
            "worktree",
            "add",
            str(record.path),
            record.branch,
            check=False,
        )
        if result.returncode != 0:
            raise WorkspaceError(
                result.stderr.strip() or "Git workspace recreation failed"
            )

    @staticmethod
    def _path_state(record: WorkspaceRecord) -> str:
        """Classify a stored path without asking Git to inspect its identity."""
        try:
            if not record.path.is_absolute():
                return "invalid"
            if not record.path.exists():
                return "missing"
            if not record.path.is_dir():
                return "invalid"
        except (OSError, RuntimeError):
            return "invalid"
        return "present"

    @staticmethod
    def _unverified_status(
        record: WorkspaceRecord, state: str, *, identity_matches: bool | None = None
    ) -> dict[str, Any]:
        row = record.to_dict()
        row.update(
            {
                "state": state,
                "checkout_id": None,
                "head": None,
                "current_branch": None,
                "dirty": None,
                "identity_matches": identity_matches,
            }
        )
        return row

    def _list_status(self, record: WorkspaceRecord) -> dict[str, Any]:
        path_state = self._path_state(record)
        return self._unverified_status(
            record, "available" if path_state == "present" else path_state
        )

    def _gc_missing_locked(
        self, records: Sequence[WorkspaceRecord]
    ) -> tuple[WorkspaceRecord, ...]:
        candidates = tuple(
            record for record in records if self._path_state(record) == "missing"
        )
        if not candidates:
            return ()
        workspace_ids = tuple(record.workspace_id for record in candidates)
        removed = self.store.remove_many(workspace_ids)
        if removed:
            self.store.record_disposal_evidence(
                {
                    "kind": MISSING_WORKTREE_GC_NOTE,
                    "reason": "worktree-path-missing",
                    "workspace_ids": [record.workspace_id for record in removed],
                    "paths": [str(record.path) for record in removed],
                }
            )
        return removed

    def _status(self, record: WorkspaceRecord) -> dict[str, Any]:
        row = record.to_dict()
        if self._path_state(record) == "missing":
            return self._unverified_status(record, "missing", identity_matches=False)
        try:
            checkout = self._checkout_by_path(record.project_id, record.path)
            branch = self._branch(checkout.path)
            dirty = bool(
                self._git(
                    checkout.path, "status", "--porcelain", "--untracked-files=all"
                ).stdout
            )
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
        except (FileNotFoundError, KeyError, OSError, RuntimeError, WorkspaceError):
            row.update(
                {
                    "state": "missing",
                    "checkout_id": None,
                    "head": None,
                    "current_branch": None,
                    "dirty": None,
                    "identity_matches": False,
                }
            )
        return row

    @classmethod
    def _porcelain_status(cls, path: Path) -> list[dict[str, Any]]:
        raw = cls._git_bytes(
            path, "status", "--porcelain=v1", "-z", "--untracked-files=all"
        )
        records = [item for item in raw.split(b"\0") if item]
        result: list[dict[str, Any]] = []
        index = 0
        while index < len(records):
            entry = records[index]
            if len(entry) < 4 or entry[2:3] != b" ":
                raise WorkspaceError("Git status porcelain is malformed")
            status = entry[:2].decode("ascii", errors="strict")
            paths = [cls._decode_git_path(entry[3:])]
            index += 1
            if "R" in status or "C" in status:
                if index == len(records):
                    raise WorkspaceError("Git status rename porcelain is malformed")
                paths.append(cls._decode_git_path(records[index]))
                index += 1
            result.append({"status": status, "paths": paths})
        return result

    @classmethod
    def _name_status(
        cls, path: Path, start_head: str, head: str
    ) -> list[dict[str, Any]]:
        raw = cls._git_bytes(
            path,
            "diff",
            "--name-status",
            "-z",
            "--find-renames",
            start_head,
            head,
            "--",
        )
        records = [item for item in raw.split(b"\0") if item]
        result: list[dict[str, Any]] = []
        index = 0
        while index < len(records):
            status = records[index].decode("ascii", errors="strict")
            if not status or status[0] not in "ACDMRTUXB":
                raise WorkspaceError("Git diff name-status porcelain is malformed")
            index += 1
            count = 2 if status[0] in {"R", "C"} else 1
            if len(records) - index < count:
                raise WorkspaceError("Git diff rename porcelain is malformed")
            result.append(
                {
                    "status": status,
                    "paths": [
                        cls._decode_git_path(item)
                        for item in records[index : index + count]
                    ],
                }
            )
            index += count
        return result

    @staticmethod
    def _decode_git_path(value: bytes) -> str:
        try:
            path = value.decode()
        except UnicodeDecodeError as error:
            raise WorkspaceError("Git path is not UTF-8") from error
        if not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise WorkspaceError("Git path is unsafe")
        return path

    @staticmethod
    def _scope_contains(path: str, scope: Sequence[str]) -> bool:
        for entry in scope:
            if (
                not isinstance(entry, str)
                or not entry
                or entry.startswith("/")
                or ".." in Path(entry).parts
            ):
                raise WorkspaceError("delivery scope is unsafe")
            if entry.endswith("/"):
                if path.startswith(entry):
                    return True
            elif path == entry:
                return True
        return False

    def _record(self, workspace_id: str) -> WorkspaceRecord:
        # Every identifier the list output prints resolves here: UUID first,
        # then unique name, then unique branch. Ambiguity refuses with the
        # candidate UUIDs instead of acting on a first match (sinnix-vb1u).
        records = list(self.store.records())
        for record in records:
            if record.workspace_id == workspace_id:
                return record
        matches = [record for record in records if record.name == workspace_id]
        if not matches:
            matches = [record for record in records if record.branch == workspace_id]
        if len(matches) == 1:
            return matches[0]
        if matches:
            candidates = ", ".join(
                f"{record.workspace_id} ({record.project_id}:{record.name})"
                for record in matches
            )
            raise WorkspaceError(
                f"ambiguous workspace reference {workspace_id!r}; "
                f"candidates: {candidates}"
            )
        raise KeyError(f"unknown workspace: {workspace_id}")

    def _project(self, project_id: str) -> ProjectAdapter:
        project = self.projects.get(project_id)
        if project.workspace is None:
            raise WorkspaceError(
                f"project {project_id!r} does not declare workspace policy"
            )
        return project

    def _available(
        self, record: WorkspaceRecord
    ) -> tuple[RegisteredCheckout, ProjectAdapter]:
        project = self._project(record.project_id)
        checkout = self._checkout_by_path(record.project_id, record.path)
        if self._branch(checkout.path) != record.branch:
            raise WorkspaceError("workspace branch identity changed")
        return checkout, project

    def _remove_worktree(
        self,
        project: ProjectAdapter,
        record: WorkspaceRecord,
        *arguments: str | RegisteredCheckout,
    ) -> subprocess.CompletedProcess[str]:
        checkout = next(
            (item for item in arguments if isinstance(item, RegisteredCheckout)), None
        )
        flags = tuple(item for item in arguments if isinstance(item, str))
        if checkout is None:
            checkout = self._checkout_by_path(record.project_id, record.path)
        if checkout.path != record.path:
            raise WorkspaceError("registered checkout does not match workspace record")
        self._canonicalize_gitfile_symlink(checkout)
        _stop_type_daemon(record.path)
        return self._git(
            project.root, "worktree", "remove", *flags, str(record.path), check=False
        )

    @staticmethod
    def _canonicalize_gitfile_symlink(checkout: RegisteredCheckout) -> None:
        """Replace only the exact registered-worktree gitdir symlink with a Git gitfile."""
        gitfile = checkout.path / ".git"
        try:
            metadata = gitfile.lstat()
        except FileNotFoundError as error:
            raise WorkspaceError("workspace .git file is missing") from error
        except OSError as error:
            raise WorkspaceError("workspace .git file is unavailable") from error
        if stat.S_ISDIR(metadata.st_mode):
            raise WorkspaceError("workspace .git path is a directory, not a gitfile")
        if not stat.S_ISLNK(metadata.st_mode):
            if not stat.S_ISREG(metadata.st_mode):
                raise WorkspaceError("workspace .git path is not a regular gitfile")
            return

        try:
            target = gitfile.resolve(strict=True)
            worktrees_root = (checkout.git_common_dir / "worktrees").resolve(
                strict=True
            )
        except FileNotFoundError as error:
            raise WorkspaceError("workspace .git symlink is broken") from error
        except OSError as error:
            raise WorkspaceError("workspace .git symlink is unavailable") from error
        try:
            target.relative_to(worktrees_root)
        except ValueError as error:
            raise WorkspaceError(
                "workspace .git symlink target is outside the repository worktrees area"
            ) from error
        expected = GitWorkspaces._registered_worktree_gitdir(checkout, worktrees_root)
        if target != expected:
            raise WorkspaceError(
                "workspace .git symlink target does not match its registered worktree gitdir"
            )

        descriptor, temporary = tempfile.mkstemp(prefix=".git.", dir=gitfile.parent)
        try:
            with os.fdopen(descriptor, "w") as handle:
                handle.write(f"gitdir: {expected}\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o644)
            os.replace(temporary, gitfile)
        except OSError as error:
            raise WorkspaceError(
                "could not canonicalize workspace .git symlink"
            ) from error
        finally:
            Path(temporary).unlink(missing_ok=True)

    @staticmethod
    def _registered_worktree_gitdir(
        checkout: RegisteredCheckout, worktrees_root: Path
    ) -> Path:
        expected_gitfile = checkout.path / ".git"
        try:
            entries = tuple(worktrees_root.iterdir())
        except OSError as error:
            raise WorkspaceError("repository worktrees area is unavailable") from error
        matches: list[Path] = []
        for candidate in entries:
            reference = candidate / "gitdir"
            try:
                raw_gitfile = reference.read_text().strip()
            except OSError:
                continue
            if not raw_gitfile:
                continue
            registered_gitfile = Path(os.path.normpath(os.path.abspath(raw_gitfile)))
            if registered_gitfile != expected_gitfile:
                continue
            try:
                candidate_target = candidate.resolve(strict=True)
            except OSError as error:
                raise WorkspaceError(
                    "registered worktree gitdir is unavailable"
                ) from error
            if (
                candidate_target.parent != worktrees_root
                or not candidate_target.is_dir()
            ):
                raise WorkspaceError(
                    "registered worktree gitdir is outside the repository worktrees area"
                )
            matches.append(candidate_target)
        if len(matches) != 1:
            raise WorkspaceError(
                "registered worktree gitdir is unavailable or ambiguous"
            )
        return matches[0]

    def _identity_check(self, project: ProjectAdapter, path: Path) -> None:
        assert project.workspace is not None
        result = subprocess.run(
            project.workspace.identity_check,
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise WorkspaceError("workspace identity check failed")

    @classmethod
    def _git_bytes(cls, path: Path, *arguments: str) -> bytes:
        try:
            result = subprocess.run(
                ["git", "-C", str(path), *arguments], capture_output=True, timeout=30
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise WorkspaceError("Git checkpoint operation failed") from error
        if result.returncode != 0:
            raise WorkspaceError(
                result.stderr.decode(errors="replace").strip()
                or "Git checkpoint operation failed"
            )
        return result.stdout

    @classmethod
    def _untracked(cls, path: Path) -> tuple[str, ...]:
        raw = cls._git_bytes(path, "ls-files", "-z", "--others", "--exclude-standard")
        try:
            files = tuple(item.decode() for item in raw.split(b"\0") if item)
        except UnicodeDecodeError as error:
            raise WorkspaceError("untracked checkpoint paths must be UTF-8") from error
        if len(files) > MAX_UNTRACKED_FILES or any(
            Path(item).is_absolute() or ".." in Path(item).parts for item in files
        ):
            raise WorkspaceError(
                "untracked checkpoint manifest exceeds its safety bounds"
            )
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
                    raise WorkspaceError(
                        "untracked checkpoint file disappeared"
                    ) from error
                if (
                    not source.is_file()
                    or source.is_symlink()
                    or metadata.st_size > MAX_CHECKPOINT_BYTES
                ):
                    raise WorkspaceError(
                        "untracked checkpoint entries must be bounded regular files"
                    )
                archive.add(source, arcname=relative, recursive=False)
                if buffer.tell() > MAX_CHECKPOINT_BYTES:
                    raise WorkspaceError(
                        "untracked checkpoint archive exceeds its byte bound"
                    )
        return buffer.getvalue()

    @staticmethod
    def _extract_untracked(
        root: Path, content: bytes, expected: tuple[str, ...]
    ) -> None:
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:") as archive:
            members = archive.getmembers()
            if tuple(member.name for member in members) != expected:
                raise WorkspaceError("checkpoint archive does not match its manifest")
            for member in members:
                target = (root / member.name).resolve(strict=False)
                if (
                    root.resolve() not in target.parents
                    or member.issym()
                    or member.islnk()
                    or not member.isfile()
                ):
                    raise WorkspaceError("checkpoint archive contains an unsafe entry")
            archive.extractall(root, members=members, filter="data")

    @classmethod
    def _apply_patch(cls, root: Path, content: bytes, *, index: bool) -> None:
        if not content:
            return
        arguments = ["git", "-C", str(root), "apply"]
        if index:
            arguments.append("--index")
        result = subprocess.run(
            arguments, input=content, capture_output=True, timeout=30
        )
        if result.returncode != 0:
            raise WorkspaceError(
                result.stderr.decode(errors="replace").strip()
                or "checkpoint patch failed"
            )

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
        try:
            checkouts = self.projects.checkouts(project_id)
        except ProjectConfigError as error:
            raise WorkspaceError("registered worktrees cannot be inspected") from error
        for checkout in checkouts:
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
        branch: str | None = None,
        provision_notes: tuple[dict[str, str], ...] = (),
    ) -> WorkspaceRecord:
        return WorkspaceRecord(
            workspace_id=str(uuid4()),
            project_id=project.project_id,
            name=name,
            path=checkout.path,
            branch=branch or GitWorkspaces._branch(checkout.path),
            base=base,
            created_at=datetime.now(UTC).isoformat(),
            provision_notes=provision_notes,
        )

    @staticmethod
    def _clone_file(source: Path | str, destination: Path | str) -> None:
        # Provisioned seeds must own their bytes: a hardlink shares the inode,
        # so a workspace writing its seed (testmon's SQLite graph, caches)
        # would mutate the main checkout's copy. Reflink when the filesystem
        # supports it, otherwise pay for a real copy.
        with open(source, "rb") as source_file, open(destination, "wb") as clone:
            try:
                fcntl.ioctl(clone.fileno(), _FICLONE, source_file.fileno())
            except OSError:
                shutil.copyfileobj(source_file, clone, 1024 * 1024)
        shutil.copystat(source, destination)

    @staticmethod
    def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=1)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    @staticmethod
    def _run_provision_exec(project: ProjectAdapter, target: Path) -> dict[str, str]:
        assert project.workspace is not None
        command = project.environment.command_for(project.workspace.provision_exec)
        environment = project.environment.values()
        output = bytearray()

        def drain(stream: Any) -> None:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    return
                remaining = MAX_PROVISION_OUTPUT_BYTES - len(output)
                if remaining > 0:
                    output.extend(chunk[:remaining])

        try:
            process = subprocess.Popen(
                command,
                cwd=target,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as error:
            raise WorkspaceError("workspace provision exec could not start") from error
        assert process.stdout is not None
        reader = threading.Thread(target=drain, args=(process.stdout,), daemon=True)
        reader.start()
        timed_out = False
        try:
            try:
                returncode = process.wait(
                    timeout=project.workspace.provision_exec_timeout_seconds
                )
            except subprocess.TimeoutExpired:
                timed_out = True
                GitWorkspaces._terminate_process_group(process)
                returncode = process.returncode
        except BaseException:
            GitWorkspaces._terminate_process_group(process)
            raise
        finally:
            reader.join(timeout=5)
            if reader.is_alive():
                process.stdout.close()
                reader.join(timeout=1)
        text = bytes(output).decode("utf-8", errors="replace")
        if timed_out:
            detail = f": {text}" if text else ""
            raise WorkspaceError(
                "workspace provision exec timed out after "
                f"{project.workspace.provision_exec_timeout_seconds} seconds{detail}"
            )
        if returncode != 0:
            detail = f": {text}" if text else ""
            raise WorkspaceError(
                f"workspace provision exec failed with exit status {returncode}{detail}"
            )
        return {
            "kind": "exec",
            "path": " ".join(project.workspace.provision_exec),
            "output": text,
        }

    @staticmethod
    def _provision(project: ProjectAdapter, target: Path) -> tuple[dict[str, str], ...]:
        assert project.workspace is not None
        notes: list[dict[str, str]] = []
        for relative in project.workspace.provision_copy:
            source = project.root / relative
            destination = target / relative
            if not source.exists():
                notes.append({"kind": "missing-source", "path": relative})
                continue
            if source.is_symlink():
                raise WorkspaceError(
                    f"workspace provision source is a symlink: {relative}"
                )
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if source.is_file():
                GitWorkspaces._clone_file(source, destination)
            elif source.is_dir():
                if destination.exists():
                    shutil.rmtree(destination)
                shutil.copytree(
                    source, destination, copy_function=GitWorkspaces._clone_file
                )
            else:
                raise WorkspaceError(
                    f"workspace provision source is not a regular file or directory: {relative}"
                )
        if project.workspace.provision_exec:
            exec_note = GitWorkspaces._run_provision_exec(project, target)
            notes.append(exec_note)
            if TESTMON_SEED_PATH in project.workspace.provision_copy and any(
                marker in exec_note["output"]
                for marker in (
                    "testmon provision: absent",
                    "testmon provision: invalid",
                )
            ):
                notes.append(
                    {
                        "kind": "missing-compatible-seed",
                        "path": TESTMON_SEED_PATH,
                    }
                )
        return tuple(notes)

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise WorkspaceError(
                "workspace name must be a lowercase path-safe identifier up to 64 characters"
            )

    @staticmethod
    def _validate_target(root: Path, path: Path) -> None:
        resolved_root = root.resolve(strict=False)
        resolved_path = path.resolve(strict=False)
        if resolved_path.parent != resolved_root:
            raise WorkspaceError("workspace target escapes the declared workspace root")

    @staticmethod
    def _git(
        path: Path, *arguments: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["git", "-C", str(path), *arguments],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise WorkspaceError("Git workspace operation failed") from error
        if check and result.returncode != 0:
            raise WorkspaceError(
                result.stderr.strip() or "Git workspace operation failed"
            )
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
        if (
            cls._git(
                root,
                "rev-parse",
                "--verify",
                "--quiet",
                f"{ref}^{{commit}}",
                check=False,
            ).returncode
            != 0
        ):
            raise WorkspaceError(f"workspace {label} does not resolve to a commit")

    @classmethod
    def _branch(cls, path: Path) -> str:
        branch = cls._git(
            path, "symbolic-ref", "--quiet", "--short", "HEAD", check=False
        ).stdout.strip()
        if not branch:
            raise WorkspaceError("detached worktrees cannot be managed workspaces")
        return branch
