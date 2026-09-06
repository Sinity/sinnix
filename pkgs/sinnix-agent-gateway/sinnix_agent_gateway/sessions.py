from __future__ import annotations

import codecs
import os
import stat
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
    @staticmethod
    def default_sources(home: Path | None = None) -> tuple[SessionSource, ...]:
        home = Path.home() if home is None else home
        return (
            SessionSource("claude-code", home / ".claude" / "projects"),
            SessionSource("codex", home / ".codex" / "sessions"),
        )

    def __init__(
        self,
        config: GatewayConfig,
        principal: Principal,
        sources: tuple[SessionSource, ...] | None = None,
    ):
        self.config = config
        self.principal = principal
        configured_sources = sources or self.default_sources()
        self.sources = tuple(
            SessionSource(source.provider, source.root.resolve())
            for source in configured_sources
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
    def _files(source: SessionSource) -> list[tuple[Path, os.stat_result]]:
        if not source.root.is_dir():
            raise SessionError("session source directory is unavailable")
        files: list[tuple[Path, os.stat_result]] = []

        def unavailable(exc: OSError) -> None:
            raise SessionError("session source directory is unavailable") from exc

        for directory, _, names in os.walk(source.root, onerror=unavailable):
            for name in names:
                if not name.endswith(".jsonl"):
                    continue
                path = Path(directory) / name
                try:
                    info = path.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    unavailable(exc)
                if stat.S_ISREG(info.st_mode):
                    files.append((path, info))
        files.sort(key=lambda row: (-row[1].st_mtime_ns, str(row[0])))
        return files

    def inventory(self, provider: str) -> list[dict[str, Any]]:
        """Observe metadata once, newest first; transcript bytes remain live."""
        source = self._source(provider)
        return [
            {
                "reference": self._reference(source, path),
                "bytes": info.st_size,
                "mtime_ns": info.st_mtime_ns,
            }
            for path, info in self._files(source)
        ]

    def list(self, provider: str, limit: int = 100) -> dict[str, Any]:
        limit = max(1, min(limit, 500))
        rows = self.inventory(provider)
        return {
            "provider": provider,
            "sessions": rows[:limit],
            "truncated": len(rows) > limit,
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
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        content = decoder.decode(data, final=not truncated)
        consumed = len(data) - len(decoder.getstate()[0])
        if truncated and consumed == 0:
            raise SessionError(
                "max_bytes is too small to decode the next UTF-8 sequence; "
                "retry with at least 4"
            )
        return {
            "provider": source.provider,
            "reference": self._reference(source, path),
            "offset": offset,
            "bytes": consumed,
            "next_offset": offset + consumed if truncated else None,
            "truncated": truncated,
            "content": content,
        }

    def search(
        self, provider: str, query: str, max_results: int = 100
    ) -> dict[str, Any]:
        source = self._source(provider)
        if not query or len(query) > 1_000:
            raise SessionError("query must contain 1-1000 characters")
        max_results = max(1, min(max_results, 500))
        files = self._files(source)
        source_truncated = len(files) > 1_000
        scanned_bytes = 0
        matches: list[dict[str, Any]] = []
        scan_limit = 8 * 1_024 * 1_024
        for path, info in files[:1_000]:
            if scanned_bytes >= scan_limit:
                source_truncated = True
                break
            with path.open("rb") as handle:
                data = handle.read(min(64_000, scan_limit - scanned_bytes))
            if len(data) < info.st_size:
                source_truncated = True
            scanned_bytes += len(data)
            offset = 0
            for line_number, raw in enumerate(data.splitlines(keepends=True), 1):
                line_offset = offset
                offset += len(raw)
                match_offset = raw.find(query.encode("utf-8"))
                if match_offset < 0:
                    continue
                start = max(0, match_offset - 200)
                matches.append(
                    {
                        "reference": self._reference(source, path),
                        "line": line_number,
                        "offset": line_offset + start,
                        "text": raw[start:]
                        .decode("utf-8", errors="replace")
                        .rstrip("\r\n")[:2_000],
                    }
                )
                if len(matches) > max_results:
                    return {
                        "provider": provider,
                        "matches": matches[:max_results],
                        "scanned_bytes": scanned_bytes,
                        "truncated": True,
                    }
        return {
            "provider": provider,
            "matches": matches,
            "scanned_bytes": scanned_bytes,
            "truncated": source_truncated,
        }

    def timeline(
        self,
        provider: str,
        start_ns: int | None,
        end_ns: int | None,
        query: str | None,
        max_results: int,
    ) -> dict[str, Any]:
        source = self._source(provider)
        if start_ns is not None and start_ns < 0:
            raise SessionError("start time must not precede the Unix epoch")
        if end_ns is not None and end_ns < 0:
            raise SessionError("end time must not precede the Unix epoch")
        if start_ns is not None and end_ns is not None and start_ns > end_ns:
            raise SessionError("start time must not be after end time")
        if query is not None and (not query or len(query) > 1_000):
            raise SessionError("query must contain 1-1000 characters")
        max_results = max(1, min(max_results, 500))
        files = [
            (path, info)
            for path, info in self._files(source)
            if (start_ns is None or info.st_mtime_ns >= start_ns)
            and (end_ns is None or info.st_mtime_ns <= end_ns)
        ]
        source_truncated = False
        scanned_bytes = 0
        scan_limit = 8 * 1_024 * 1_024
        entries: list[dict[str, Any]] = []
        for path, info in files:
            entry = {
                "reference": self._reference(source, path),
                "bytes": info.st_size,
                "mtime_ns": info.st_mtime_ns,
            }
            if query is not None:
                if scanned_bytes >= scan_limit:
                    source_truncated = True
                    break
                with path.open("rb") as handle:
                    data = handle.read(min(64_000, scan_limit - scanned_bytes))
                scanned_bytes += len(data)
                text = data.decode("utf-8", errors="replace")
                matching_line = next(
                    (line for line in text.splitlines() if query in line),
                    None,
                )
                if matching_line is None:
                    if len(data) < info.st_size:
                        source_truncated = True
                    continue
                start = max(0, matching_line.index(query) - 200)
                entry["snippet"] = matching_line[start : start + 2_000]
                if len(data) < info.st_size:
                    source_truncated = True
            entries.append(entry)
            if len(entries) > max_results:
                source_truncated = True
                break
        return {
            "provider": provider,
            "entries": entries[:max_results],
            "scanned_bytes": scanned_bytes,
            "truncated": source_truncated,
        }
