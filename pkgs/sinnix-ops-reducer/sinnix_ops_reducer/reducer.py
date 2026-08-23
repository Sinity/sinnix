from __future__ import annotations

import json
import os
import subprocess
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sinnix_lib.atomic_json import write_json_atomic

from . import SCHEMA
from .anchor import expire_anchor, reduce_anchor_event
from .hyprland import HyprlandState, Socket2Adapter, reduce_socket_event


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Reducer:
    def __init__(
        self,
        snapshot_path: Path,
        token_path: Path,
        source: Callable[[], dict[str, Any]],
        state_path: Path | None = None,
        max_events: int = 256,
        ambient_source: Callable[[], dict[str, Any]] | None = None,
        agent_jobs_source: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.snapshot_path = snapshot_path
        self.token_path = token_path
        self.state_path = state_path
        self.source = source
        self.events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self.sequence = self._load_state()
        self.previous_health: dict[str, str] = {}
        self._snapshot: dict[str, Any] = {}
        self.ambient_source = ambient_source
        self.agent_jobs_source = agent_jobs_source
        self.anchor_event_path: Path | None = None
        self.anchor: dict[str, Any] | None = None
        self.hyprland_state = HyprlandState()
        self.hyprland_event_path: Path | None = None
        self.hyprland_socket = Socket2Adapter()

    def _load_state(self) -> int:
        if self.state_path is None:
            return 0
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            return int(value.get("sequence", 0))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return 0

    def _save_sequence(self) -> None:
        if self.state_path is not None:
            write_json_atomic(
                self.state_path,
                {"sequence": self.sequence},
                mode=0o600,
                fsync=True,
            )

    def refresh(self) -> dict[str, Any]:
        observed_at = now_iso()
        agent_jobs, agent_jobs_health = self._agent_jobs_snapshot(observed_at)
        try:
            report = self.source()
            if not isinstance(report, dict):
                raise ValueError("collector returned a non-object")
            report = dict(report)
            report["agentctl"] = agent_jobs
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
        ambient, ambient_health = self._ambient_snapshot(observed_at)
        anchor = self._anchor_snapshot(observed_at)
        hyprland = self._hyprland_snapshot()
        snapshot = {
            "schema": SCHEMA,
            "sequence": self.sequence,
            "observed_at": observed_at,
            "sources": {
                "sinnix-observe": source_health,
                "agentctl": agent_jobs_health,
                "ambient-intelligence": ambient_health,
            },
            "state": {
                **report,
                "ambient_intelligence": ambient,
                "session_anchor": anchor,
                "hyprland_automation": hyprland,
            }
            if source_health["status"] == "healthy"
            else None,
            "degradation": source_health["degradation"],
        }
        write_json_atomic(self.snapshot_path, snapshot, mode=0o600, fsync=True)
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

    def _agent_jobs_snapshot(
        self, observed_at: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if self.agent_jobs_source is None:
            return (
                {"jobs": [], "truncated": False},
                {
                    "status": "disabled",
                    "source": "agentctl",
                    "observed_at": observed_at,
                    "freshness": "unknown",
                    "degradation": "no AgentCTL client configured",
                },
            )
        try:
            value = self.agent_jobs_source()
            if not isinstance(value, dict) or not isinstance(value.get("jobs"), list):
                raise ValueError("AgentCTL collector returned an invalid jobs payload")
            return (
                value,
                {
                    "status": "healthy",
                    "source": "agentctl",
                    "observed_at": observed_at,
                    "freshness": "current",
                    "degradation": None,
                },
            )
        except Exception as error:
            return (
                {"jobs": [], "truncated": False},
                {
                    "status": "unavailable",
                    "source": "agentctl",
                    "observed_at": observed_at,
                    "freshness": "unknown",
                    "degradation": str(error)[:240],
                },
            )

    def _hyprland_snapshot(self) -> dict[str, Any]:
        self.hyprland_socket.poll(self.hyprland_state)
        if self.hyprland_event_path is not None and self.hyprland_event_path.exists():
            try:
                for line in self.hyprland_event_path.read_text(
                    encoding="utf-8"
                ).splitlines()[-32:]:
                    reduce_socket_event(self.hyprland_state, line)
                self.hyprland_event_path.unlink(missing_ok=True)
            except OSError:
                pass
        return {
            "fullscreen_game": self.hyprland_state.fullscreen_game,
            "static_content": self.hyprland_state.static_content,
            "diagnostics": self.hyprland_state.diagnostics,
        }

    def _anchor_snapshot(self, observed_at: str) -> dict[str, Any] | None:
        now = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if self.anchor_event_path is not None and self.anchor_event_path.exists():
            try:
                event = json.loads(self.anchor_event_path.read_text(encoding="utf-8"))
                self.anchor = reduce_anchor_event(event, now, previous=self.anchor)
                self.anchor_event_path.unlink(missing_ok=True)
            except (OSError, json.JSONDecodeError):
                pass
        self.anchor = expire_anchor(self.anchor, now)
        return self.anchor

    def _ambient_snapshot(
        self, observed_at: str
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        if self.ambient_source is None:
            return None, {
                "status": "disabled",
                "source": "lynchpin-ambient-intelligence",
                "observed_at": observed_at,
                "freshness": "unknown",
                "degradation": "no product configured",
            }
        try:
            value = self.ambient_source()
            return value, {
                "status": "healthy",
                "source": "lynchpin-ambient-intelligence",
                "observed_at": observed_at,
                "freshness": "current",
                "degradation": None,
            }
        except Exception as error:
            return None, {
                "status": "unavailable",
                "source": "lynchpin-ambient-intelligence",
                "observed_at": observed_at,
                "freshness": "unknown",
                "degradation": str(error)[:240],
            }

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
