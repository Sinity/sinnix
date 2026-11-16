"""Keeps the operator state current at a bounded cost.

Slow facts (Beads, hosted checks, usage limits) are refreshed one at a time on
a background thread, each on its own period. Reading the state never waits on
them: ``current`` assembles the latest collected values and says how old each
source is.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sinnix_lib.atomic_json import read_json, write_json_atomic

from . import claims, engine, sessions, sources
from .history import JobLog, TaskRunnerHistory
from .text import summary_lines

AGENTCTL_CONFIG = Path("/etc/sinnix/agentctl.json")
TASK_RUNNER_HISTORY = Path.home() / ".local/state/devkit/history.db"
STATE_CACHE_SECONDS = 5.0


class Source:
    """One collector, the period it is refreshed on, and its latest answer."""

    def __init__(self, name: str, period: float, collect: Callable[[], Any]) -> None:
        self.name = name
        self.period = period
        self.collect = collect
        self.value: Any = None
        self.observed: float | None = None
        self.attempted: float | None = None
        self.error: str | None = None
        self.seconds: float | None = None
        self.failures = 0

    def due(self, now: float) -> float:
        """How overdue this source is, as a fraction of its period.

        Each consecutive failure doubles the wait, up to eight periods, so a
        source that keeps timing out cannot occupy the refresh thread.
        """
        if self.attempted is None:
            return float("inf")
        return (now - self.attempted) / (self.period * min(8, 2**self.failures))

    def refresh(self) -> None:
        started = time.monotonic()
        self.attempted = started
        try:
            self.value = self.collect()
            self.observed = time.time()
            self.error = None
            self.failures = 0
        except Exception as error:  # a failed source keeps its last value
            self.error = f"{type(error).__name__}: {error}"[:240]
            self.failures += 1
        self.seconds = time.monotonic() - started

    def health(self, now: float) -> dict[str, Any]:
        return {
            "observed_at": sources.utc(self.observed) if self.observed else None,
            "age_seconds": round(now - self.observed) if self.observed else None,
            "period_seconds": self.period,
            "last_cost_seconds": round(self.seconds, 2)
            if self.seconds is not None
            else None,
            "error": self.error,
        }


class OperatorState:
    def __init__(
        self,
        memory_path: Path,
        *,
        jobs: Callable[[], dict[str, Any]],
        units: Callable[[], list[dict[str, Any]]] = lambda: [],
        agentctl_config: Path = AGENTCTL_CONFIG,
        claims_path: Path = claims.STORE,
    ) -> None:
        self.memory_path = memory_path
        self.claims_path = claims_path
        self.jobs = jobs
        self.units = units
        self.lock = threading.Lock()
        memory = read_json(memory_path, {})
        self.memory: dict[str, Any] = memory if isinstance(memory, dict) else {}
        self.cached: tuple[float, dict[str, Any]] | None = None
        try:
            self.projects = sources.registered_projects(agentctl_config)
        except (OSError, ValueError):
            self.projects = []  # a host without agentctl still has limits and load
        config = read_json(agentctl_config, {})
        self.job_log = JobLog(
            Path(config.get("event_spool") or "/realm/state/agentctl/events.jsonl")
        )
        self.task_runner = TaskRunnerHistory(TASK_RUNNER_HISTORY)
        self.slugs: dict[str, str | None] = {}
        self.sources: dict[str, Source] = {}
        self._declare_sources()
        self.thread: threading.Thread | None = None

    # ------------------------------------------------------------ sources

    def _add(self, name: str, period: float, collect: Callable[[], Any]) -> None:
        self.sources[name] = Source(name, period, collect)

    def _declare_sources(self) -> None:
        self._add("job-log", 10, self.job_log.refresh)
        self._add("machine-load", 10, sources.machine_load)
        self._add("path-claims", 10, lambda: claims.active(self.claims_path))
        self._add("agent-sessions", 30, sessions.collect)
        self._add("deployment", 60, self._deployment)
        self._add("claude-usage", 600, sources.claude_usage)
        self._add("codex-usage", 300, sources.codex_usage)
        self._add("plannotator", 120, lambda: sources.plannotator_inbox(self.projects))
        self._add("task-runner-history", 900, self.task_runner.refresh)
        for project in self.projects:
            name, root = project["id"], project["root"]
            if (Path(root) / ".beads").exists():
                self._add(
                    f"beads-waiting:{name}",
                    60,
                    lambda root=root: sources.beads_waiting(root),
                )
                self._add(
                    f"beads-counts:{name}",
                    300,
                    lambda root=root: sources.beads_counts(root),
                )
                self._add(
                    f"beads-closed:{name}",
                    3600,
                    lambda name=name, root=root: sources.closed_bead_samples(
                        name, root, datetime.now(timezone.utc)
                    ),
                )
            if (Path(root) / ".git").exists():
                self._add(
                    f"git:{name}", 120, lambda root=root: sources.git_changes(root)
                )
                self._add(
                    f"git-fetch:{name}", 900, lambda root=root: sources.git_fetch(root)
                )
                self._add(
                    f"hosted-checks:{name}",
                    300,
                    lambda name=name, root=root: self._hosted(name, root),
                )

    def _slug(self, name: str, root: str) -> str | None:
        if name not in self.slugs:
            self.slugs[name] = sources.github_slug(root)
        return self.slugs[name]

    def _hosted(self, name: str, root: str) -> dict[str, Any]:
        if self._slug(name, root) is None:
            return {
                "merged": [],
                "default_check": {
                    "state": "none",
                    "failing": [],
                    "reason": "no GitHub remote",
                },
            }
        branch = sources.default_branch(root)
        return sources.hosted_checks(root, branch.partition("/")[2] or branch)

    def _deployment(self) -> dict[str, Any]:
        for project in self.projects:
            if (Path(project["root"]) / ".git").exists():
                self._slug(project["id"], project["root"])
        return sources.deployment(self.projects, self.slugs)

    def refresh_next(self) -> bool:
        """Refresh the most overdue source. False when none is due."""
        now = time.monotonic()
        source = max(self.sources.values(), key=lambda item: item.due(now))
        if source.due(now) < 1:
            return False
        source.refresh()
        with self.lock:
            self.cached = None
        return True

    def refresh_all(self) -> None:
        """Every source once, in turn: the terminal command without a hub."""
        for source in self.sources.values():
            source.refresh()

    def start(self) -> None:
        def loop() -> None:
            while True:
                try:
                    worked = self.refresh_next()
                except Exception:  # the loop outlives any one source
                    worked = False
                time.sleep(0.2 if worked else 2.0)

        self.thread = threading.Thread(target=loop, name="operator-state", daemon=True)
        self.thread.start()

    # ------------------------------------------------------------ state

    def _value(self, name: str, default: Any = None) -> Any:
        source = self.sources.get(name)
        return default if source is None or source.value is None else source.value

    def _jobs(self) -> dict[str, Any]:
        """The job snapshot, with how long each running job's log has been quiet."""
        try:
            snapshot = dict(self.jobs() or {})
        except Exception:
            return {"jobs": [], "groups": {}}
        now = time.time()
        rows = []
        for job in snapshot.get("jobs") or []:
            if (
                isinstance(job, dict)
                and job.get("phase") == "running"
                and job.get("log_path")
            ):
                try:
                    job = {
                        **job,
                        "log_idle_seconds": round(
                            now - os.stat(job["log_path"]).st_mtime
                        ),
                    }
                except OSError:
                    pass
            rows.append(job)
        return {**snapshot, "jobs": rows}

    def inputs(self) -> dict[str, Any]:
        beads: dict[str, Any] = {}
        git: dict[str, Any] = {}
        pulls: dict[str, Any] = {}
        closed: list[dict[str, Any]] = []
        for project in self.projects:
            name = project["id"]
            waiting = self.sources.get(f"beads-waiting:{name}")
            if waiting is not None:
                beads[name] = {
                    **(self._value(f"beads-counts:{name}", {})),
                    **({"human": waiting.value} if waiting.value is not None else {}),
                    "error": waiting.error,
                }
                closed += self._value(f"beads-closed:{name}", [])
            if f"git:{name}" in self.sources:
                git[name] = {
                    **self._value(f"git:{name}", {}),
                    "error": self.sources[f"git:{name}"].error,
                }
                pulls[name] = {
                    **self._value(f"hosted-checks:{name}", {}),
                    "error": self.sources[f"hosted-checks:{name}"].error,
                }
        jobs = self._jobs()
        # Recent queue rows give enqueue-to-start waits the older log lacks.
        waits = {
            pool: list(values) for pool, values in self.job_log.wait_seconds.items()
        }
        if not waits:
            for job in jobs.get("jobs") or []:
                queued = engine.parse_time(job.get("enqueued_at"))
                started = engine.parse_time(job.get("started_at"))
                if queued and started and started >= queued:
                    waits.setdefault(str(job.get("group")), []).append(
                        (started - queued).total_seconds()
                    )
        limits = dict(self._value("machine-load", {}))
        for key, name in (("claude", "claude-usage"), ("codex", "codex-usage")):
            limits[key] = self._value(name) or {
                "error": self.sources[name].error or "not read yet"
            }
        now = time.time()
        return {
            "projects": self.projects,
            "jobs": jobs,
            "beads": beads,
            "plannotator": self._value(
                "plannotator", {"installed": False, "items": []}
            ),
            "git": git,
            "pulls": pulls,
            "deployed": self._value("deployment", {}),
            "units": self.units(),
            "claims": self._value("path-claims", []),
            "agent_sessions": self._value("agent-sessions"),
            "closed_beads": closed,
            "limits": limits,
            "job_history": {
                "run_seconds": {
                    key: list(values)
                    for key, values in self.job_log.run_seconds.items()
                },
                "task_runner_seconds": {
                    key: list(values)
                    for key, values in self.task_runner.run_seconds.items()
                },
                "wait_seconds": waits,
                "recent": list(self.job_log.recent),
                "counts": {
                    "job_log": {
                        "finished_jobs": self.job_log.finished_count,
                        "duration_samples_kept": self.job_log.sample_count(),
                        "operations": len(self.job_log.run_seconds),
                        "since": self.job_log.first_at,
                    },
                    "task_runner": {
                        "passed_runs": self.task_runner.rows,
                        "commands": len(self.task_runner.run_seconds),
                        "error": self.task_runner.error,
                    },
                    "closed_tasks": {
                        "samples": len(closed),
                        "with_claim_time": sum(
                            1 for s in closed if s["claimed_seconds"] is not None
                        ),
                        "with_size": sum(1 for s in closed if s["size"]),
                        "with_size_label": sum(
                            1 for s in closed if s["size_from_label"]
                        ),
                        "labelled_human": sum(1 for s in closed if s["human"]),
                        "window_days": sources.CLOSED_BEADS_DAYS,
                    },
                },
            },
            "sources": {
                name: source.health(now)
                for name, source in sorted(self.sources.items())
            },
        }

    def current(self) -> dict[str, Any]:
        with self.lock:
            now = time.monotonic()
            if self.cached is not None and now - self.cached[0] < STATE_CACHE_SECONDS:
                return self.cached[1]
            before = json.dumps(self.memory, sort_keys=True)
            state = engine.compute(
                self.inputs(), self.memory, datetime.now(timezone.utc)
            )
            if json.dumps(self.memory, sort_keys=True) != before:
                self._save()
            self.cached = (now, state)
            return state

    def summary(self) -> dict[str, Any]:
        """The compact projection the desktop bar and panel read."""
        state = self.current()
        return {
            "schema": state["schema"],
            "generated_at": state["generated_at"],
            "last_looked_at": state["last_looked_at"],
            "counts": state["counts"],
            "lines": summary_lines(state),
        }

    def mark_looked(self, shown_generated_at: str | None = None) -> dict[str, Any]:
        """Advance "last looked" to the state the operator was shown."""
        moment = engine.parse_time(shown_generated_at) or datetime.now(timezone.utc)
        moment = min(moment, datetime.now(timezone.utc))
        with self.lock:
            previous = engine.parse_time(self.memory.get("last_looked_at"))
            if previous is None or moment > previous:
                self.memory["last_looked_at"] = engine.iso(moment)
                self._save()
            self.cached = None
            return {"last_looked_at": self.memory.get("last_looked_at")}

    def _save(self) -> None:
        try:
            write_json_atomic(self.memory_path, self.memory, mode=0o600)
        except OSError:
            pass
