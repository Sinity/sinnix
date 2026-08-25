from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterator, Mapping

from sinnix_lib.lock import flock
from sinnix_mcp.execution import ExecutionProfile, OwnerExecution, OwnerRoute

from .capabilities import Capability, Principal
from .config import GatewayConfig, ProjectConfig


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


def _is_excluded(path: Path) -> bool:
    parts = path.parts
    if any(part.lower() in SENSITIVE_PARTS for part in parts):
        return True
    if any(part.startswith(".") and ".gateway-tmp-" in part for part in parts):
        return True
    if parts in LOCAL_ONLY_FILES:
        return True
    return any(parts[: len(prefix)] == prefix for prefix in LOCAL_ONLY_PATHS)


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
    project: ProjectConfig, parts: tuple[str, ...], *, create: bool
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
        if isinstance(exc, ProjectError):
            raise
        raise ProjectError("project path contains a symlink or is unavailable") from exc


def _temporary_name(target_name: str) -> str:
    return f".{target_name}.gateway-tmp-{os.urandom(16).hex()}"


def _open_temporary(parent: int, target_name: str) -> tuple[str, int]:
    for _ in range(8):
        name = _temporary_name(target_name)
        try:
            return name, os.open(
                name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0),
                0o600,
                dir_fd=parent,
            )
        except FileExistsError:
            continue
    raise ProjectError("could not allocate a private project temporary")


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
    temporary_name: str | None = None
    descriptor = -1
    try:
        temporary_name, descriptor = _open_temporary(parent, target_name)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            os.fchmod(handle.fileno(), mode & 0o777)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(
            temporary_name,
            target_name,
            src_dir_fd=parent,
            dst_dir_fd=parent,
        )
        os.fsync(parent)
        temporary_name = None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_name is not None:
            _unlink_at(parent, temporary_name)


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
        if self.principal.name == "observer" and not project.observer_read:
            raise ProjectError(f"project is unavailable to {self.principal.name}")
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
        return resolved

    def list(self) -> dict[str, Any]:
        self.principal.require(Capability.PROJECT_READ)
        can_write = Capability.PROJECT_WRITE in self.principal.capabilities
        rows = []
        for project in self.config.projects.values():
            if self.principal.name == "observer" and not project.observer_read:
                continue
            rows.append(
                {
                    "project_id": project.project_id,
                    "available": project.path.is_dir(),
                    "default_ref": project.default_ref,
                    "observer_read": project.observer_read,
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
            if not separator:
                raise ProjectError("git worktree returned malformed porcelain")
            if key in current:
                raise ProjectError("git worktree returned duplicate porcelain field")
            current[key] = value
        if current:
            records.append(current)
        return records

    def _checkout_rows(self, project: ProjectConfig) -> list[dict[str, Any]]:
        if project.checkout_discovery != "git-worktree":
            raise ProjectError("project checkout discovery is unsupported")
        configured_root = project.path.resolve(strict=True)
        output = self._run_bounded(
            ["git", "worktree", "list", "--porcelain"], project.path
        )
        rows: list[dict[str, Any]] = []
        for record in self._worktree_records(output):
            raw_path = record.get("worktree")
            head = record.get("HEAD")
            if raw_path is None or head is None:
                raise ProjectError("git worktree record is missing worktree or HEAD")
            path = Path(raw_path).resolve()
            if not path.is_dir():
                continue
            status = self._run_bounded(
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
            rows.append(
                {
                    "checkout_id": self._checkout_id(path, configured_root),
                    "path": str(path),
                    "head": head,
                    "branch": branch,
                    "upstream": upstream,
                    "dirty_sha256": hashlib.sha256(status.encode()).hexdigest(),
                    "lifecycle": "configured-root"
                    if path == configured_root
                    else "linked-worktree",
                }
            )
        rows.sort(key=lambda row: (row["checkout_id"] != "default", row["checkout_id"]))
        if not rows or rows[0]["checkout_id"] != "default":
            raise ProjectError("configured project root is not a live Git worktree")
        return rows

    def checkouts(self, project_id: str) -> dict[str, Any]:
        project = self._project(project_id)
        return {
            "project_id": project.project_id,
            "checkouts": self._checkout_rows(project),
        }

    def checkout(self, project_id: str, checkout_id: str) -> dict[str, Any]:
        project = self._project(project_id)
        for checkout in self._checkout_rows(project):
            if checkout["checkout_id"] == checkout_id:
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
            if not require_explicit:
                return project
            checkouts = self._checkout_rows(project)
            if len(checkouts) == 1:
                return project
            choices = ", ".join(row["checkout_id"] for row in checkouts)
            raise ProjectError(
                f"checkout_id is required; available checkouts: {choices}"
            )
        if not isinstance(checkout_id, str) or not checkout_id:
            raise ProjectError("checkout_id must be a non-empty string")
        for checkout in self._checkout_rows(project):
            if checkout["checkout_id"] == checkout_id:
                return replace(project, path=Path(checkout["path"]))
        raise ProjectError("unknown configured checkout")

    def tree(
        self,
        project_id: str,
        path: str = ".",
        max_entries: int = 500,
        checkout_id: str | None = None,
    ) -> dict[str, Any]:
        project = self.code_checkout(
            project_id, checkout_id, write=False, require_explicit=False
        )
        root = self._safe_path(project, path, existing=True)
        if not root.is_dir():
            raise ProjectError("tree path must be a directory")
        max_entries = max(1, min(max_entries, 2000))
        entries: list[dict[str, Any]] = []
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
                entries.append(
                    {
                        "path": str(relative),
                        "kind": "directory" if target.is_dir() else "file",
                        "bytes": target.stat().st_size if target.is_file() else None,
                    }
                )
                if len(entries) >= max_entries:
                    return {"entries": entries, "truncated": True}
        return {"entries": entries, "truncated": False}

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
        target = self._safe_path(project, path, existing=True)
        if not target.is_file() or target.is_symlink():
            raise ProjectError("path must identify a regular project file")
        max_bytes = max(1, min(max_bytes, self.config.max_result_bytes))
        if end_line is not None and end_line < start_line:
            raise ProjectError("end_line must be greater than or equal to start_line")
        content: list[str] = []
        used = 0
        truncated = False
        with target.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, 1):
                if line_number < start_line:
                    continue
                if end_line is not None and line_number > end_line:
                    break
                encoded = line.encode("utf-8")
                if used + len(encoded) > max_bytes:
                    remaining = max_bytes - used
                    if remaining:
                        content.append(
                            encoded[:remaining].decode("utf-8", errors="ignore")
                        )
                    truncated = True
                    break
                content.append(line)
                used += len(encoded)
        return {
            "project_id": project_id,
            "path": path,
            "start_line": start_line,
            "end_line": end_line,
            "content": "".join(content),
            "bytes": used,
            "truncated": truncated,
        }

    def _run_bounded_result(
        self, command: list[str], cwd: Path, timeout: int = 15
    ) -> tuple[str, bool]:
        safe_env = {
            "HOME": str(Path.home()),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PATH": os.environ.get("PATH", "/run/current-system/sw/bin"),
            "GIT_OPTIONAL_LOCKS": "0",
        }
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
        )
        text = result.stdout.decode("utf-8", errors="replace")
        if result.timed_out:
            raise ProjectError("project operation timed out")
        if result.output_exceeded:
            return text, True
        if result.exit_status not in (0, 1):
            diagnostic = result.stderr.decode("utf-8", errors="replace").strip()
            raise ProjectError(diagnostic or text.strip() or "project operation failed")
        return text, False

    def _run_bounded(self, command: list[str], cwd: Path, timeout: int = 15) -> str:
        return self._run_bounded_result(command, cwd, timeout)[0]

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
                if set(preconditions) - {"head", "dirty_sha256"}:
                    raise ProjectError(
                        "project mutation preconditions are not recognized"
                    )
                checkout = self.checkout(project_id, checkout_id)["checkout"]
                for name, expected in preconditions.items():
                    if not isinstance(expected, str) or checkout.get(name) != expected:
                        raise ProjectPreconditionError(
                            f"project checkout {name} no longer matches"
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
        max_matches = max(1, min(max_matches, 1000))
        output = self._run_bounded(
            ["rg", "--json", "--hidden", "--glob", "!.git/**", "--", query, "."],
            project.path,
        )
        matches: list[dict[str, Any]] = []
        for line in output.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("type") != "match":
                continue
            data = row["data"]
            path_value = data["path"]["text"]
            if _is_excluded(Path(path_value)):
                continue
            matches.append(
                {
                    "path": path_value,
                    "line": data.get("line_number"),
                    "text": data["lines"]["text"].rstrip("\n"),
                }
            )
            if len(matches) >= max_matches:
                break
        return {"matches": matches, "truncated": len(matches) >= max_matches}

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
            resolved_ref = self._run_bounded(
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
        command = ["git", "diff", "--no-ext-diff", "--no-textconv"]
        if resolved_ref is not None:
            command.append(resolved_ref)
        command.append("--")
        return {
            "project_id": project_id,
            "diff": self._run_bounded(command, project.path),
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
            resolved = self._run_bounded(
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
        merge_base = self._run_bounded(
            ["git", "merge-base", base, head], project.path
        ).strip()
        if not re.fullmatch(r"[0-9a-f]{40,64}", merge_base):
            raise ProjectError("commit range has no merge base")
        content, truncated = self._run_bounded_result(
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
            "truncated": truncated,
        }

    def summary(self, project_id: str) -> dict[str, Any]:
        project = self._project(project_id)
        status = self._run_bounded(
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
        head_id = self._run_bounded(
            ["git", "rev-parse", "--verify", "--quiet", "HEAD"], project.path
        ).strip()
        commit: dict[str, str] | None = None
        if head_id:
            latest = self._run_bounded(
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
                _atomic_publish(parent, parts[-1], content.encode(), 0o600)
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
            try:
                paths = self._patch_paths(root_path, patch_bytes)
                for relative in paths:
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
                    for relative, entry in changes:
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
