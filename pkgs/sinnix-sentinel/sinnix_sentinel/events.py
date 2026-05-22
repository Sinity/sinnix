"""Event log writer and check-list bookkeeping.

Wire-format contract (bash sentinel ``record_check`` / ``queue_action_event``
plus the jq pipeline at lines 817-881):

* ``/var/log/sinnix-sentinel/events.jsonl`` — append-only JSONL. Each line is
  a compact JSON object with ``timestamp``, ``source: "sinnix-sentinel"``,
  ``event``, ``severity``, plus event-specific fields.
* ``/run/sinnix/health.json`` — single-line top-level object:
  ``{"timestamp":..,"overall":..,"summary":{"ok":N,"warn":N,"fail":N},"checks":[...]}``.
* Health-event diffing keys are ``"<category>:<name>"`` (matches the bash jq
  ``def key(c): "\\((c.category // "unknown")):\\((c.name // "unnamed"))"``).
* ``severity`` mapping: fail->critical, warn->warning, anything else->normal.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_HEALTH_FILE = "/run/sinnix/health.json"
DEFAULT_EVENT_LOG = "/var/log/sinnix-sentinel/events.jsonl"


def health_file_path() -> Path:
    return Path(os.environ.get("SINNIX_HEALTH_FILE", DEFAULT_HEALTH_FILE))


def prev_health_file_path() -> Path:
    return Path(str(health_file_path()) + ".prev")


def event_log_path() -> Path:
    return Path(os.environ.get("SINNIX_EVENT_LOG", DEFAULT_EVENT_LOG))


def severity_for(status: str) -> str:
    if status == "fail":
        return "critical"
    if status == "warn":
        return "warning"
    return "normal"


@dataclass
class Check:
    category: str
    name: str
    status: str  # ok | warn | fail
    detail: str


@dataclass
class CheckSet:
    checks: List[Check] = field(default_factory=list)
    ok: int = 0
    warn: int = 0
    fail: int = 0

    def record(self, category: str, name: str, status: str, detail: str) -> Check:
        if status == "ok":
            self.ok += 1
        elif status == "warn":
            self.warn += 1
        elif status == "fail":
            self.fail += 1
        chk = Check(category=category, name=name, status=status, detail=detail)
        self.checks.append(chk)
        return chk

    def overall(self) -> str:
        if self.fail > 0:
            return "fail"
        if self.warn > 0:
            return "warn"
        return "ok"

    def to_health_json(self, timestamp: str) -> Dict[str, Any]:
        return {
            "timestamp": timestamp,
            "overall": self.overall(),
            "summary": {"ok": self.ok, "warn": self.warn, "fail": self.fail},
            "checks": [asdict(c) for c in self.checks],
        }


def _check_key(c: Dict[str, Any]) -> str:
    return f"{c.get('category', 'unknown')}:{c.get('name', 'unnamed')}"


def diff_health_events(
    timestamp: str,
    current: Dict[str, Any],
    previous: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Reproduce the bash jq pipeline (lines 817-881) for transition events."""

    events: List[Dict[str, Any]] = []
    if previous is None:
        events.append(
            {
                "timestamp": timestamp,
                "source": "sinnix-sentinel",
                "event": "health.initialized",
                "severity": severity_for(current.get("overall", "")),
                "overall": current.get("overall"),
                "summary": current.get("summary", {}),
            }
        )
        return events

    prev_overall = previous.get("overall", "unknown")
    cur_overall = current.get("overall", "unknown")
    if prev_overall != cur_overall:
        events.append(
            {
                "timestamp": timestamp,
                "source": "sinnix-sentinel",
                "event": "health.overall_transition",
                "severity": severity_for(cur_overall),
                "overall_before": prev_overall,
                "overall_after": cur_overall,
                "summary_before": previous.get("summary", {}),
                "summary_after": current.get("summary", {}),
            }
        )

    before = {_check_key(c): c for c in (previous.get("checks") or [])}
    after = {_check_key(c): c for c in (current.get("checks") or [])}
    for key, nxt in after.items():
        prev = before.get(key)
        if prev is None:
            continue
        if prev.get("status") == nxt.get("status"):
            continue
        events.append(
            {
                "timestamp": timestamp,
                "source": "sinnix-sentinel",
                "event": "health.check_transition",
                "severity": severity_for(nxt.get("status", "")),
                "category": nxt.get("category"),
                "name": nxt.get("name"),
                "status_before": prev.get("status"),
                "status_after": nxt.get("status"),
                "detail_before": prev.get("detail", ""),
                "detail_after": nxt.get("detail", ""),
            }
        )
    return events


def can_write_parent(path: Path) -> bool:
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return os.access(parent, os.W_OK)


def write_health(current: Dict[str, Any], path: Optional[Path] = None) -> bool:
    p = path if path is not None else health_file_path()
    if not can_write_parent(p):
        return False
    try:
        p.write_text(json.dumps(current) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


def append_events(
    events: List[Dict[str, Any]],
    path: Optional[Path] = None,
) -> bool:
    if not events:
        return True
    p = path if path is not None else event_log_path()
    if not can_write_parent(p):
        return False
    try:
        with p.open("a", encoding="utf-8") as fh:
            for ev in events:
                fh.write(json.dumps(ev) + "\n")
        return True
    except OSError:
        return False


def load_previous_health(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    p = path if path is not None else health_file_path()
    try:
        if not p.is_file():
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
