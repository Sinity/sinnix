from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from .audit import AuditService
from .beads import BeadsService
from .projects import ProjectService


class EventCursorError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


class OpaqueEventCursor:
    """A scope-bound cursor. It carries positions, never normalized event rows."""

    def __init__(self, *, principal: str, state_dir: Path) -> None:
        self.principal = principal
        self._key = hashlib.sha256(f"sinnix-events:{state_dir.resolve()}".encode()).digest()

    def _scope(self, projects: list[str]) -> str:
        return _digest({"principal": self.principal, "projects": sorted(projects)})

    def encode(self, state: Mapping[str, Any], projects: list[str]) -> str:
        body = {"v": 1, "scope": self._scope(projects), "state": dict(state)}
        payload = base64.urlsafe_b64encode(_canonical(body)).decode().rstrip("=")
        mac = hmac.new(self._key, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{mac}"

    def decode(self, value: str | None, projects: list[str]) -> dict[str, Any]:
        if value is None:
            return {
                "audit_sequence": 0,
                "runtime_offset": 0,
                "job_revisions": {},
                "owner_revisions": {},
            }
        if not isinstance(value, str) or "." not in value:
            raise EventCursorError("event cursor is malformed")
        payload, mac = value.rsplit(".", 1)
        expected = hmac.new(self._key, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, expected):
            raise EventCursorError("event cursor authentication failed")
        try:
            padded = payload + "=" * (-len(payload) % 4)
            body = json.loads(base64.urlsafe_b64decode(padded).decode())
        except (ValueError, json.JSONDecodeError, binascii.Error) as exc:
            raise EventCursorError("event cursor is not valid JSON") from exc
        if body.get("v") != 1 or body.get("scope") != self._scope(projects):
            raise EventCursorError("event cursor scope is stale or belongs to another principal")
        state = body.get("state")
        if not isinstance(state, dict):
            raise EventCursorError("event cursor state is malformed")
        return state


class NormalizedEventService:
    """Normalize owner evidence without creating a second event database."""

    def __init__(
        self,
        *,
        principal: str,
        state_dir: Path,
        projects: ProjectService,
        beads: BeadsService,
        audit: AuditService,
        transitions_path: Path,
        jobs: Callable[[int, str | None], Mapping[str, Any]] | None = None,
    ) -> None:
        self.principal = principal
        self.projects = projects
        self.beads = beads
        self.audit = audit
        self.transitions_path = transitions_path
        self.jobs = jobs
        self.cursor = OpaqueEventCursor(principal=principal, state_dir=state_dir)

    def _event(
        self,
        *,
        event_id: str,
        kind: str,
        source: str,
        source_revision: str,
        data: Mapping[str, Any],
        exact: bool,
        subject_ref: str | None = None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "schema": "sinnix.gateway-event.v1",
            "principal": self.principal,
            "event_id": event_id,
            "kind": kind,
            "source": source,
            "source_revision": source_revision,
            "exact": exact,
            "observed_at": time.time(),
            "data": dict(data),
        }
        if subject_ref is not None:
            row["subject_ref"] = subject_ref
        return row

    def _runtime_events(self, offset: int, limit: int) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
        try:
            with self.transitions_path.open("rb") as handle:
                handle.seek(max(0, offset))
                payload = handle.read(256 * 1024)
        except OSError as exc:
            return [], offset, {"availability": "unavailable", "reason": str(exc)}
        events: list[dict[str, Any]] = []
        consumed = 0
        for raw in payload.splitlines(keepends=True):
            consumed += len(raw)
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, Mapping):
                continue
            revision = _digest(row)
            event_id = row.get("event_id") or f"offset:{offset + consumed - len(raw)}"
            events.append(
                self._event(
                    event_id=str(event_id),
                    kind="runtime_transition",
                    source="ops-reducer.transitions",
                    source_revision=revision,
                    data=row,
                    exact=row.get("schema") == "sinnix-health-transition-v1",
                )
            )
            if len(events) >= limit:
                break
        next_offset = offset + consumed
        if payload and not payload.endswith(b"\n"):
            next_offset = offset + consumed - len(payload.splitlines(keepends=True)[-1])
        return events, next_offset, {"availability": "available", "offset": next_offset}

    def read(
        self,
        *,
        limit: int = 100,
        cursor: str | None = None,
        project_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1_000:
            raise ValueError("event limit must be 1-1000")
        selected = sorted(project_ids or self.projects.config.projects)
        if not selected or any(project_id not in self.projects.config.projects for project_id in selected):
            raise ValueError("event project scope contains an unknown project")
        state = self.cursor.decode(cursor, selected)
        events: list[dict[str, Any]] = []
        sources: dict[str, dict[str, Any]] = {}
        audit_sequence = int(state.get("audit_sequence", 0))
        audit_rows = self.audit.events_since(audit_sequence, limit)
        for row in audit_rows:
            event_id = str(row["event_id"])
            payload = row.get("payload", {})
            owner = payload.get("owner") if isinstance(payload, Mapping) else None
            kind = "ops_receipt" if owner == "ops-reducer" or row.get("operation") == "machine.operate" else "gateway_receipt"
            event = self._event(
                event_id=event_id,
                kind=kind,
                source="gateway.audit",
                source_revision=str(row["entry_hash"]),
                data=row,
                exact=True,
                subject_ref=(payload.get("target_refs", [None])[0] if isinstance(payload, Mapping) and payload.get("target_refs") else None),
            )
            event.update({key: row[key] for key in ("operation", "outcome", "sequence")})
            events.append(event)
            audit_sequence = max(audit_sequence, int(row["sequence"]))
        sources["gateway.audit"] = {"availability": "available", "last_sequence": audit_sequence}

        owner_revisions = dict(state.get("owner_revisions", {}))
        for project_id in selected:
            project_ref = f"sinnix://projects/{project_id}"
            try:
                summary = self.projects.summary(project_id)
                git_revision = _digest(summary)
                sources[f"git:{project_id}"] = {"availability": "available", "revision": git_revision}
                changed = owner_revisions.get(f"git:{project_id}") != git_revision
                if changed and len(events) >= limit:
                    continue
                if changed:
                    events.append(self._event(event_id=f"git:{project_id}:{git_revision}", kind="git_revision", source="git.project", source_revision=git_revision, data={"project_id": project_id, "latest_commit": summary.get("latest_commit"), "changes": summary.get("changes")}, exact=False, subject_ref=project_ref))
                owner_revisions[f"git:{project_id}"] = git_revision
            except Exception as exc:
                sources[f"git:{project_id}"] = {"availability": "unavailable", "reason": str(exc)}
            try:
                authority = self.beads.task_authority_status(project_id)
                bead_revision = str(authority["revision"])
                sources[f"beads:{project_id}"] = {"availability": "available", "revision": bead_revision}
                changed = owner_revisions.get(f"beads:{project_id}") != bead_revision
                if changed and len(events) >= limit:
                    continue
                if changed:
                    events.append(self._event(event_id=f"beads:{project_id}:{bead_revision}", kind="owner_revision", source="beads.owner", source_revision=bead_revision, data={"project_id": project_id, "revision": bead_revision, "diff": authority.get("diff"), "change": "owner revision changed"}, exact=False, subject_ref=f"{project_ref}/task-authority"))
                owner_revisions[f"beads:{project_id}"] = bead_revision
            except Exception as exc:
                sources[f"beads:{project_id}"] = {"availability": "unavailable", "reason": str(exc)}

        job_revisions = dict(state.get("job_revisions", {}))
        if self.jobs is not None and len(events) < limit:
            try:
                page = self.jobs(min(100, limit), None)
                jobs = page.get("jobs", [])
                for job in jobs if isinstance(jobs, list) else []:
                    if not isinstance(job, Mapping) or not isinstance(job.get("job_id"), str):
                        continue
                    revision = _digest(job)
                    job_id = job["job_id"]
                    changed = job_revisions.get(job_id) != revision
                    if changed and len(events) >= limit:
                        continue
                    if changed:
                        events.append(self._event(event_id=f"job:{job_id}:{revision}", kind="job_state", source="sinnixd.jobs", source_revision=revision, data={"job_id": job_id, "state": job.get("state"), "phase": job.get("state", {}).get("phase") if isinstance(job.get("state"), Mapping) else None}, exact=False, subject_ref=f"sinnix://jobs/{job_id}"))
                    job_revisions[job_id] = revision
                sources["sinnixd.jobs"] = {"availability": "available", "count": len(jobs) if isinstance(jobs, list) else 0}
            except Exception as exc:
                sources["sinnixd.jobs"] = {"availability": "unavailable", "reason": str(exc)}
        remaining = max(0, limit - len(events))
        runtime_events, runtime_offset, runtime_source = (
            self._runtime_events(int(state.get("runtime_offset", 0)), remaining)
            if remaining
            else ([], int(state.get("runtime_offset", 0)), {"availability": "not_requested"})
        )
        events.extend(runtime_events)
        sources["ops-reducer.transitions"] = runtime_source
        events = events[:limit]
        next_state = {
            "audit_sequence": audit_sequence,
            "runtime_offset": runtime_offset,
            "owner_revisions": owner_revisions,
            "job_revisions": job_revisions,
        }
        next_cursor = self.cursor.encode(next_state, selected)
        encoded = _canonical(events)
        while len(encoded) > 262_144 and events:
            events.pop()
            encoded = _canonical(events)
        return {
            "schema": "sinnix.gateway-events.v1",
            "events": events,
            "limit": limit,
            "truncated": len(events) >= limit,
            "next_cursor": next_cursor,
            "sources": sources,
            "scope": {"principal": self.principal, "projects": selected},
            "cursor_policy": "opaque positions and owner revisions only; no event store",
        }
