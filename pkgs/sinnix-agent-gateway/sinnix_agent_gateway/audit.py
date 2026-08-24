from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from typing import Any, Mapping

from .capabilities import Capability, Principal
from .config import GatewayConfig
from .redaction import redact

GENESIS_HASH = "0" * 64


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class AuditService:
    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal
        config.initialize_state()
        self.path = config.state_dir / "audit" / "events.sqlite3"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.execute("pragma busy_timeout=30000")
        connection.execute("pragma journal_mode=wal")
        connection.execute("pragma synchronous=full")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists events (
                  sequence integer primary key autoincrement,
                  event_id text not null unique,
                  occurred_at real not null,
                  profile text not null,
                  operation text not null,
                  outcome text not null,
                  payload_json text not null,
                  previous_hash text not null,
                  entry_hash text not null unique
                )
                """
            )
            connection.execute(
                """
                create table if not exists idempotency (
                  principal text not null,
                  action text not null,
                  idempotency_key text not null,
                  request_sha256 text not null,
                  state text not null,
                  response_json text,
                  receipt_id text,
                  created_at real not null,
                  updated_at real not null,
                  primary key(principal, action, idempotency_key)
                )
                """
            )
        self.path.chmod(0o600)

    def append(
        self, operation: str, outcome: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        event_id = str(uuid.uuid4())
        occurred_at = time.time()
        clean_payload = json.loads(redact(json.dumps(payload or {}, sort_keys=True)))
        correlation_id = clean_payload.get("correlation_id") or clean_payload.get(
            "job_id"
        )
        if correlation_id:
            clean_payload["correlation_id"] = str(correlation_id)
        with self._connect() as connection:
            connection.execute("begin immediate")
            previous = connection.execute(
                "select entry_hash from events order by sequence desc limit 1"
            ).fetchone()
            previous_hash = previous[0] if previous else GENESIS_HASH
            body = {
                "event_id": event_id,
                "occurred_at": occurred_at,
                # The hash-chain field name remains stable so existing audit
                # entries verify. Its values are principal names.
                "profile": self.principal.name,
                "operation": operation,
                "outcome": outcome,
                "payload": clean_payload,
                "previous_hash": previous_hash,
            }
            entry_hash = hashlib.sha256(
                previous_hash.encode() + _canonical(body)
            ).hexdigest()
            connection.execute(
                "insert into events(event_id, occurred_at, profile, operation, outcome, payload_json, previous_hash, entry_hash) values (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    occurred_at,
                    self.principal.name,
                    operation,
                    outcome,
                    json.dumps(clean_payload, sort_keys=True),
                    previous_hash,
                    entry_hash,
                ),
            )
            sequence = connection.execute("select last_insert_rowid()").fetchone()[0]
            connection.execute("commit")
        return {"sequence": sequence, "event_id": event_id, "entry_hash": entry_hash}

    def claim_idempotency(
        self, action: str, idempotency_key: str, request_sha256: str
    ) -> tuple[str, dict[str, Any] | None]:
        """Atomically reserve one mutation identity or return its completed response."""
        if not action or not idempotency_key:
            raise ValueError("action and idempotency key are required")
        now = time.time()
        with self._connect() as connection:
            connection.execute("begin immediate")
            row = connection.execute(
                "select request_sha256,state,response_json from idempotency where principal = ? and action = ? and idempotency_key = ?",
                (self.principal.name, action, idempotency_key),
            ).fetchone()
            if row is None:
                connection.execute(
                    "insert into idempotency(principal,action,idempotency_key,request_sha256,state,response_json,receipt_id,created_at,updated_at) values (?, ?, ?, ?, 'in_progress', null, null, ?, ?)",
                    (
                        self.principal.name,
                        action,
                        idempotency_key,
                        request_sha256,
                        now,
                        now,
                    ),
                )
                connection.execute("commit")
                return "new", None
            if row[0] != request_sha256:
                connection.execute("commit")
                return "conflict", None
            if row[1] != "complete" or row[2] is None:
                connection.execute("commit")
                return "in_progress", None
            try:
                response = json.loads(row[2])
            except json.JSONDecodeError as exc:
                connection.execute("rollback")
                raise ValueError("stored idempotency response is malformed") from exc
            connection.execute("commit")
            return "replay", response

    def complete_idempotency(
        self,
        action: str,
        idempotency_key: str,
        request_sha256: str,
        response: Mapping[str, Any],
    ) -> None:
        receipt = response.get("receipt")
        receipt_id = receipt.get("receipt_id") if isinstance(receipt, Mapping) else None
        if not isinstance(receipt_id, str):
            raise ValueError("idempotency response requires a receipt")
        with self._connect() as connection:
            connection.execute("begin immediate")
            updated = connection.execute(
                "update idempotency set state = 'complete', response_json = ?, receipt_id = ?, updated_at = ? where principal = ? and action = ? and idempotency_key = ? and request_sha256 = ? and state = 'in_progress'",
                (
                    json.dumps(response, sort_keys=True, separators=(",", ":")),
                    receipt_id,
                    time.time(),
                    self.principal.name,
                    action,
                    idempotency_key,
                    request_sha256,
                ),
            ).rowcount
            if updated != 1:
                connection.execute("rollback")
                raise ValueError("idempotency reservation is unavailable")
            connection.execute("commit")

    def receipt(self, receipt_id: str) -> dict[str, Any]:
        """Return one principal-scoped audit event as a canonical receipt."""
        self.principal.require(Capability.AUDIT_READ)
        try:
            receipt_id = str(uuid.UUID(receipt_id))
        except ValueError as exc:
            raise ValueError("invalid receipt ID") from exc
        with self._connect() as connection:
            row = connection.execute(
                "select sequence,event_id,occurred_at,profile,operation,outcome,payload_json,previous_hash,entry_hash from events where event_id = ?",
                (receipt_id,),
            ).fetchone()
        if row is None:
            raise ValueError("unknown receipt")
        if row[3] != self.principal.name:
            raise ValueError("receipt is unavailable to this principal")
        return {
            "schema": "sinnix.gateway-audit-receipt.v1",
            "receipt_id": row[1],
            "sequence": row[0],
            "occurred_at": row[2],
            "principal": row[3],
            "operation": row[4],
            "outcome": row[5],
            "payload": json.loads(row[6]),
            "previous_hash": row[7],
            "entry_hash": row[8],
        }

    def tail(self, limit: int = 100) -> dict[str, Any]:
        self.principal.require(Capability.AUDIT_READ)
        limit = max(1, min(limit, 1000))
        with self._connect() as connection:
            rows = connection.execute(
                "select sequence,event_id,occurred_at,profile,operation,outcome,payload_json,previous_hash,entry_hash from events where profile = ? order by sequence desc limit ?",
                (self.principal.name, limit),
            ).fetchall()
        events = [
            {
                "sequence": row[0],
                "event_id": row[1],
                "occurred_at": row[2],
                "principal": row[3],
                "operation": row[4],
                "outcome": row[5],
                "payload": json.loads(row[6]),
                "previous_hash": row[7],
                "entry_hash": row[8],
            }
            for row in reversed(rows)
        ]
        return {"events": events}

    def events_since(self, sequence: int, limit: int = 100) -> list[dict[str, Any]]:
        """Read existing audit rows after an opaque sequence position."""
        self.principal.require(Capability.AUDIT_READ)
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            raise ValueError("audit sequence must be non-negative")
        limit = max(1, min(limit, 1_000))
        with self._connect() as connection:
            rows = connection.execute(
                "select sequence,event_id,occurred_at,profile,operation,outcome,payload_json,previous_hash,entry_hash from events where profile = ? and sequence > ? order by sequence asc limit ?",
                (self.principal.name, sequence, limit),
            ).fetchall()
        return [
            {
                "sequence": row[0],
                "event_id": row[1],
                "occurred_at": row[2],
                "principal": row[3],
                "operation": row[4],
                "outcome": row[5],
                "payload": json.loads(row[6]),
                "previous_hash": row[7],
                "entry_hash": row[8],
            }
            for row in rows
        ]

    def verify(self) -> dict[str, Any]:
        self.principal.require(Capability.AUDIT_READ)
        previous_hash = GENESIS_HASH
        checked = 0
        with self._connect() as connection:
            cursor = connection.execute(
                "select sequence,event_id,occurred_at,profile,operation,outcome,payload_json,previous_hash,entry_hash from events order by sequence"
            )
            for row in cursor:
                body = {
                    "event_id": row[1],
                    "occurred_at": row[2],
                    "profile": row[3],
                    "operation": row[4],
                    "outcome": row[5],
                    "payload": json.loads(row[6]),
                    "previous_hash": row[7],
                }
                expected = hashlib.sha256(
                    row[7].encode() + _canonical(body)
                ).hexdigest()
                if row[7] != previous_hash or row[8] != expected:
                    return {"valid": False, "checked": checked, "broken_at": row[0]}
                previous_hash = row[8]
                checked += 1
        return {"valid": True, "checked": checked, "head_hash": previous_hash}
