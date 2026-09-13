from __future__ import annotations

import json
import os
import subprocess
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from sinnix_lib.atomic_json import write_json_atomic
from sinnix_lib.ledger import utc_ts

from . import SCHEMA
from .anchor import expire_anchor, reduce_anchor_event
from .hyprland import HyprlandState, Socket2Adapter, reduce_socket_event


class Reducer:
    def __init__(
        self,
        snapshot_path: Path,
        token_path: Path,
        source: Callable[[], dict[str, Any]],
        state_path: Path | None = None,
        max_events: int = 256,
        section_source: Callable[[str], dict[str, Any]] | None = None,
        ambient_source: Callable[[], dict[str, Any]] | None = None,
        agent_jobs_source: Callable[[], dict[str, Any]] | None = None,
        clodex_usage_source: Callable[[], tuple[dict[str, Any], dict[str, Any]]]
        | None = None,
    ) -> None:
        self.snapshot_path = snapshot_path
        self.token_path = token_path
        self.state_path = state_path
        self.source = source
        self.section_source = section_source
        self.events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self.sequence = self._load_state()
        self.previous_health: dict[str, str] = {}
        self._snapshot: dict[str, Any] = {}
        self.ambient_source = ambient_source
        self.agent_jobs_source = agent_jobs_source
        self.clodex_usage_source = clodex_usage_source
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
            # Durability: file and directory. The sequence is what makes event
            # ids monotonic across restarts, so a crash that loses it hands
            # subscribers ids they have already seen.
            write_json_atomic(
                self.state_path,
                {"sequence": self.sequence},
                mode=0o600,
                fsync=True,
            )

    def refresh(self) -> dict[str, Any]:
        observed_at = utc_ts()
        agent_jobs, agent_jobs_health = self._agent_jobs_snapshot(observed_at)
        clodex, clodex_health = self._clodex_snapshot(observed_at)
        try:
            report = self.source()
            if not isinstance(report, dict):
                raise ValueError("collector returned a non-object")
            report = dict(report)
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
        previous = self.snapshot()
        section_health = dict(report.pop("sections", {}))
        old_sections = previous.get("sections", {})
        old_state = previous.get("state") or {}
        if source_health["status"] != "healthy":
            for key, old_health in old_sections.items():
                if old_health.get("source") == "sinnix-observe":
                    section_health[key] = {
                        **old_health,
                        "available": False,
                        "degradation": source_health["degradation"],
                    }
        for key in report:
            if key not in {"schema", "generated_at", "window", "sources"}:
                section_health.setdefault(
                    key,
                    {
                        "available": True,
                        "observed_at": observed_at,
                        "degradation": None,
                    },
                )
        for key, health in section_health.items():
            health["source"] = "sinnix-observe"
            if not health.get("available") and key in old_state:
                report[key] = old_state[key]
                health["observed_at"] = old_sections.get(key, {}).get("observed_at")
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
                **(
                    {"clodex": clodex_health}
                    if self.clodex_usage_source is not None
                    else {}
                ),
                "ambient-intelligence": ambient_health,
            },
            "state": {
                **report,
                "agentctl": agent_jobs,
                **({"clodex": clodex} if self.clodex_usage_source is not None else {}),
                "ambient_intelligence": ambient,
                "session_anchor": anchor,
                "hyprland_automation": hyprland,
            },
            "sections": section_health,
            "degradation": source_health["degradation"],
        }
        for key, health in (
            ("agentctl", agent_jobs_health),
            ("clodex", clodex_health),
            ("ambient_intelligence", ambient_health),
        ):
            snapshot["sections"][key] = {
                **health,
                "available": health["status"] == "healthy",
            }
        for key in ("session_anchor", "hyprland_automation"):
            snapshot["sections"][key] = {
                "available": True,
                "observed_at": observed_at,
                "source": "desktop-events",
                "degradation": None,
            }
        # Durability: file and directory. status.json is the hub's published
        # view of the host, so after a crash it must resolve to the newest
        # observation rather than to the previous cycle's.
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

    def _clodex_snapshot(
        self, observed_at: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if self.clodex_usage_source is None:
            return {}, {
                "status": "disabled",
                "source": "clodex-inference-accounting",
                "observed_at": observed_at,
                "freshness": "unknown",
                "degradation": "no accounting collector configured",
            }
        try:
            value, health = self.clodex_usage_source()
            return value, {**health, "observed_at": observed_at}
        except Exception as error:
            return {}, {
                "status": "unavailable",
                "source": "clodex-inference-accounting",
                "observed_at": observed_at,
                "freshness": "unknown",
                "degradation": str(error)[:240],
            }

    def _agent_jobs_snapshot(
        self, observed_at: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        empty = {"groups": {}, "jobs": [], "truncated": False}
        if self.agent_jobs_source is None:
            return (
                empty,
                {
                    "status": "disabled",
                    "source": "agentctl",
                    "observed_at": observed_at,
                    "freshness": "unknown",
                    "degradation": "no agentctl client configured",
                },
            )
        try:
            value = self.agent_jobs_source()
            if (
                not isinstance(value, dict)
                or not isinstance(value.get("jobs"), list)
                or not isinstance(value.get("groups"), dict)
            ):
                raise ValueError("job plane collector returned an invalid payload")
            value = {
                **value,
                "jobs": [
                    {
                        **job,
                        "expected_target": {
                            "kind": "job",
                            "launch_reference": job["reference"],
                            "attempt": job["attempt"],
                        },
                    }
                    if isinstance(job.get("reference"), str)
                    and isinstance(job.get("attempt"), int)
                    else job
                    for job in value["jobs"]
                ],
            }
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
                empty,
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

    def observe(self, section: str) -> dict[str, Any]:
        """Detailed read through the observation owner; never called by refresh."""
        allowed = {
            "pressure",
            "blocked_tasks",
            "storage",
            "units",
            "slices",
            "runtime_inventory",
            "gateway",
            "browser",
            "ingestion",
            "workloads",
            "drift",
        }
        if section not in allowed:
            raise ValueError("unknown observation section")
        if self.section_source is None:
            raise RuntimeError("detailed observation source unavailable")
        return self.section_source(section)

    def page_snapshot(self, sections: tuple[str, ...]) -> dict[str, Any]:
        snapshot = self.snapshot()
        value = {
            **snapshot,
            "state": dict(snapshot.get("state") or {}),
            "sections": dict(snapshot.get("sections") or {}),
        }
        for section in sections:
            try:
                report = self.observe(section)
                for key, item in report.items():
                    if key in {"schema", "generated_at", "window", "sources"}:
                        continue
                    if isinstance(item, dict) and "rows" in item and "cursor" in item:
                        item = item["rows"]
                    value["state"][key] = item
                    value["sections"][key] = {
                        "available": True,
                        "observed_at": report.get("generated_at"),
                        "source": "sinnix-observe",
                        "degradation": None,
                    }
            except Exception as error:
                value["sections"][section] = {
                    "available": False,
                    "observed_at": None,
                    "degradation": str(error)[:240],
                }
        return value

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
            "observed_at": utc_ts(),
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
