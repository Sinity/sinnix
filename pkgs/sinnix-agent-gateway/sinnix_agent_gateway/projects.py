from __future__ import annotations

import json
import os
import re
import select
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from .capabilities import Capability, Principal
from .config import GatewayConfig, ProjectConfig


class ProjectError(ValueError):
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


def _is_excluded(path: Path) -> bool:
    parts = path.parts
    if any(part.lower() in SENSITIVE_PARTS for part in parts):
        return True
    if parts in LOCAL_ONLY_FILES:
        return True
    return any(parts[: len(prefix)] == prefix for prefix in LOCAL_ONLY_PATHS)


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
        if self.principal.profile.startswith("remote-"):
            allowed = project.remote_write if write else project.remote_read
            if not allowed:
                raise ProjectError(
                    f"project is unavailable to {self.principal.profile}"
                )
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
            if self.principal.profile.startswith("remote-") and not project.remote_read:
                continue
            rows.append(
                {
                    "project_id": project.project_id,
                    "available": project.path.is_dir(),
                    "default_ref": project.default_ref,
                    "remote_read": project.remote_read,
                    "remote_write": can_write and project.remote_write,
                }
            )
        return {"projects": sorted(rows, key=lambda row: row["project_id"])}

    def tree(
        self, project_id: str, path: str = ".", max_entries: int = 500
    ) -> dict[str, Any]:
        project = self._project(project_id)
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
    ) -> dict[str, Any]:
        project = self._project(project_id)
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

    def _run_bounded(self, command: list[str], cwd: Path, timeout: int = 15) -> str:
        safe_env = {
            "HOME": str(Path.home()),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PATH": os.environ.get("PATH", "/run/current-system/sw/bin"),
        }
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=safe_env,
            start_new_session=True,
        )
        assert process.stdout is not None
        deadline = time.monotonic() + timeout
        data = bytearray()
        bounded = False
        try:
            while len(data) <= self.config.max_result_bytes:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                ready, _, _ = select.select([process.stdout], [], [], remaining)
                if not ready:
                    raise subprocess.TimeoutExpired(command, timeout)
                chunk = os.read(
                    process.stdout.fileno(),
                    min(65_536, self.config.max_result_bytes + 1 - len(data)),
                )
                if not chunk:
                    break
                data.extend(chunk)
            bounded = len(data) > self.config.max_result_bytes
            if bounded:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    result_code = process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    result_code = process.wait()
            else:
                result_code = process.wait(
                    timeout=max(0.1, deadline - time.monotonic())
                )
        except subprocess.TimeoutExpired as exc:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise ProjectError("project operation timed out") from exc
        text = data[: self.config.max_result_bytes].decode("utf-8", errors="replace")
        if not bounded and result_code not in (0, 1):
            raise ProjectError(text.strip() or "project operation failed")
        return text

    def search(
        self, project_id: str, query: str, max_matches: int = 200
    ) -> dict[str, Any]:
        project = self._project(project_id)
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

    def diff(self, project_id: str, ref: str | None = None) -> dict[str, Any]:
        project = self._project(project_id)
        if ref is not None and not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", ref):
            raise ProjectError("invalid git ref")
        command = ["git", "diff", "--no-ext-diff", "--"]
        if ref is not None:
            command = ["git", "diff", "--no-ext-diff", ref, "--"]
        return {
            "project_id": project_id,
            "diff": self._run_bounded(command, project.path),
        }

    def write(self, project_id: str, path: str, content: str) -> dict[str, Any]:
        project = self._project(project_id, write=True)
        target = self._safe_path(project, path, existing=False)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temp = target.with_name(f".{target.name}.gateway-tmp")
        temp.write_text(content)
        temp.chmod(0o600)
        temp.replace(target)
        return {"project_id": project_id, "path": path, "bytes": len(content.encode())}

    def apply_patch(self, project_id: str, patch: str) -> dict[str, Any]:
        project = self._project(project_id, write=True)
        if len(patch.encode()) > self.config.max_result_bytes:
            raise ProjectError("patch exceeds configured bound")
        safe_env = {
            "HOME": str(Path.home()),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PATH": os.environ.get("PATH", "/run/current-system/sw/bin"),
        }
        result = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "-"],
            cwd=project.path,
            input=patch.encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
            env=safe_env,
        )
        output = result.stdout[: self.config.max_result_bytes].decode(errors="replace")
        if result.returncode != 0:
            raise ProjectError(output.strip() or "patch was rejected")
        return {"project_id": project_id, "applied": True}
