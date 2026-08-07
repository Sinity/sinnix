from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import SCHEMA


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


class Reducer:
    def __init__(
        self,
        snapshot_path: Path,
        token_path: Path,
        source: Callable[[], dict[str, Any]],
        state_path: Path | None = None,
        max_events: int = 256,
    ) -> None:
        self.snapshot_path = snapshot_path
        self.token_path = token_path
        self.state_path = state_path
        self.source = source
        self.events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self.sequence = self._load_sequence()
        self.previous_health: dict[str, str] = {}
        self._snapshot: dict[str, Any] = {}

    def _load_sequence(self) -> int:
        if self.state_path is None:
            return 0
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            return int(value.get("sequence", 0))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return 0

    def _save_sequence(self) -> None:
        if self.state_path is not None:
            atomic_json(self.state_path, {"sequence": self.sequence})

    def refresh(self) -> dict[str, Any]:
        observed_at = now_iso()
        try:
            report = self.source()
            if not isinstance(report, dict):
                raise ValueError("collector returned a non-object")
            source_health = {
                "status": "healthy",
                "source": "sinnix-observe",
                "observed_at": observed_at,
                "freshness": "current",
                "degradation": None,
            }
        except Exception as error:  # collector failures become source state
            report = {}
            source_health = {
                "status": "unavailable",
                "source": "sinnix-observe",
                "observed_at": observed_at,
                "freshness": "unknown",
                "degradation": str(error)[:240],
            }
        self.sequence += 1
        snapshot = {
            "schema": SCHEMA,
            "sequence": self.sequence,
            "observed_at": observed_at,
            "sources": {"sinnix-observe": source_health},
            "state": report if source_health["status"] == "healthy" else None,
            "degradation": source_health["degradation"],
        }
        atomic_json(self.snapshot_path, snapshot)
        self._snapshot = snapshot
        self._save_sequence()
        status = str(source_health["status"])
        if self.previous_health.get("sinnix-observe") != status:
            event = {
                "schema": SCHEMA,
                "sequence": self.sequence,
                "observed_at": observed_at,
                "type": "source_health",
                "source": "sinnix-observe",
                "status": status,
                "degradation": source_health["degradation"],
            }
            self.events.append(event)
            self.previous_health["sinnix-observe"] = status
        return snapshot

    def snapshot(self) -> dict[str, Any]:
        if self._snapshot:
            return self._snapshot
        try:
            value = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            self._snapshot = value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            self._snapshot = {}
        return self._snapshot

    def health(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "status": "healthy" if self.snapshot_path.exists() else "starting",
            "sequence": self.sequence,
            "observed_at": now_iso(),
        }

    def events_since(self, sequence: int | None) -> list[dict[str, Any]]:
        if sequence is None:
            return list(self.events)
        return [event for event in self.events if event["sequence"] > sequence]


def observe_source(
    command: list[str], timeout: float = 5.0
) -> Callable[[], dict[str, Any]]:
    def collect() -> dict[str, Any]:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={
                "PATH": os.environ.get("PATH", ""),
                "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", ""),
            },
        )
        if result.returncode != 0:
            raise RuntimeError(f"collector exited {result.returncode}")
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise ValueError("collector returned a non-object")
        return value

    return collect
