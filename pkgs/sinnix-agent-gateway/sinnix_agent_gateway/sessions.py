from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .capabilities import Capability, Principal
from .config import GatewayConfig


class SessionError(ValueError):
    pass


@dataclass(frozen=True)
class SessionSource:
    provider: str
    root: Path


class SessionLogService:
    def __init__(
        self,
        config: GatewayConfig,
        principal: Principal,
        sources: tuple[SessionSource, ...] | None = None,
    ):
        self.config = config
        self.principal = principal
        self.sources = sources or (
            SessionSource("claude-code", Path.home() / ".claude" / "projects"),
            SessionSource("codex", Path.home() / ".codex"),
        )

    def _source(self, provider: str) -> SessionSource:
        self.principal.require(Capability.SESSION_READ)
        for source in self.sources:
            if source.provider == provider:
                return source
        raise SessionError("provider must be claude-code or codex")

    @staticmethod
    def _reference(source: SessionSource, path: Path) -> str:
        return f"{source.provider}:{path.relative_to(source.root)}"

    def _path_from_reference(self, reference: str) -> tuple[SessionSource, Path]:
        provider, separator, relative = reference.partition(":")
        if not separator or not relative:
            raise SessionError("reference must use provider:relative-path form")
        source = self._source(provider)
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise SessionError("reference must remain within its provider root")
        try:
            path = (source.root / candidate).resolve(strict=True)
            root = source.root.resolve(strict=True)
        except FileNotFoundError as exc:
            raise SessionError("session source is unavailable") from exc
        if root not in path.parents or path.suffix != ".jsonl" or not path.is_file():
            raise SessionError("reference does not identify a session JSONL file")
        return source, path

    @staticmethod
    def _files(source: SessionSource, limit: int) -> tuple[list[Path], bool]:
        if not source.root.is_dir():
            return [], False
        files: list[Path] = []
        exhausted = False
        for directory, _, names in os.walk(source.root):
            for name in names:
                if not name.endswith(".jsonl"):
                    continue
                files.append(Path(directory) / name)
                if len(files) > limit:
                    exhausted = True
                    break
            if exhausted:
                break
        files.sort(key=lambda path: path.stat().st_mtime_ns, reverse=True)
        return files[:limit], exhausted

    def list(self, provider: str, limit: int = 100) -> dict[str, Any]:
        source = self._source(provider)
        limit = max(1, min(limit, 500))
        files, truncated = self._files(source, limit)
        return {
            "provider": provider,
            "sessions": [
                {
                    "reference": self._reference(source, path),
                    "bytes": path.stat().st_size,
                    "mtime_ns": path.stat().st_mtime_ns,
                }
                for path in files
            ],
            "truncated": truncated,
        }

    def read(
        self, reference: str, offset: int = 0, max_bytes: int = 64_000
    ) -> dict[str, Any]:
        source, path = self._path_from_reference(reference)
        if offset < 0:
            raise SessionError("offset must not be negative")
        max_bytes = max(1, min(max_bytes, self.config.max_result_bytes))
        with path.open("rb") as handle:
            handle.seek(offset)
            data = handle.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        data = data[:max_bytes]
        return {
            "provider": source.provider,
            "reference": self._reference(source, path),
            "offset": offset,
            "bytes": len(data),
            "truncated": truncated,
            "content": data.decode("utf-8", errors="replace"),
        }

    def search(
        self, provider: str, query: str, max_results: int = 100
    ) -> dict[str, Any]:
        source = self._source(provider)
        if not query or len(query) > 1_000:
            raise SessionError("query must contain 1-1000 characters")
        max_results = max(1, min(max_results, 500))
        files, source_truncated = self._files(source, 1_000)
        scanned_bytes = 0
        matches: list[dict[str, Any]] = []
        scan_limit = 8 * 1_024 * 1_024
        for path in files:
            if scanned_bytes >= scan_limit:
                source_truncated = True
                break
            with path.open("rb") as handle:
                data = handle.read(min(64_000, scan_limit - scanned_bytes))
            if len(data) < path.stat().st_size:
                source_truncated = True
            scanned_bytes += len(data)
            text = data.decode("utf-8", errors="replace")
            for line_number, line in enumerate(text.splitlines(), 1):
                if query not in line:
                    continue
                matches.append(
                    {
                        "reference": self._reference(source, path),
                        "line": line_number,
                        "text": line[:2_000],
                    }
                )
                if len(matches) >= max_results:
                    return {
                        "provider": provider,
                        "matches": matches,
                        "scanned_bytes": scanned_bytes,
                        "truncated": True,
                    }
        return {
            "provider": provider,
            "matches": matches,
            "scanned_bytes": scanned_bytes,
            "truncated": source_truncated,
        }
