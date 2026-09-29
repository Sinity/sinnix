"""One structured journal line per remote gateway call.

The OpenAI tunnel-client logs only a terminal line per command (forwarded,
upstream error, or response deadline reached) keyed by its ``request_id`` and
the control plane's ``cmd_request_id``. It forwards the latter to this server
as ``X-Request-Id``, so every line here joins to the tunnel's line for the same
command, and the ``wfr_…`` prefix groups the calls of one ChatGPT run.

Lines go to stderr, which systemd sends to the journal of the MCP unit.
Argument values pass through the gateway's redaction before they are written;
the full request and response stay in the audit and result stores.
"""

from __future__ import annotations

import contextvars
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

import anyio

from .redaction import REDACTED, env_name_is_secret, redact

# The control plane's response deadline for one command, measured from the
# tunnel-client's poll: consecutive dropped calls in one ChatGPT run are spaced
# 120-125 s apart. The tunnel exposes no setting for it.
TUNNEL_RESPONSE_DEADLINE_SECONDS = 120

_STRING_LIMIT = 160
_ITEM_LIMIT = 16
_SUMMARY_LIMIT = 4_096


@dataclass(frozen=True)
class HttpRequest:
    """What the ASGI layer knows about the request carrying a call."""

    received: float
    request_id: str | None
    session_id: str | None
    task_id: int


_HTTP_REQUEST: contextvars.ContextVar[HttpRequest | None] = contextvars.ContextVar(
    "sinnix_gateway_http_request", default=None
)


def current_http_request() -> HttpRequest | None:
    """The HTTP request this task is serving, if the call runs inside it.

    Per-request (2026-07-28) calls, which the tunnel sends, run in the ASGI
    request task. A 2025 session runs tools in a task spawned from its first
    request, which would inherit that request's context; such calls report
    no request rather than another one's.
    """
    request = _HTTP_REQUEST.get()
    if request is None or request.task_id != anyio.get_current_task().id:
        return None
    return request


class RequestContextMiddleware:
    """Expose arrival time and correlation headers to the call that follows."""

    def __init__(self, app: Callable[..., Any]):
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        token = _HTTP_REQUEST.set(
            HttpRequest(
                received=time.monotonic(),
                request_id=_bounded(headers.get("x-request-id")),
                session_id=_bounded(headers.get("mcp-session-id")),
                task_id=anyio.get_current_task().id,
            )
        )
        try:
            await self.app(scope, receive, send)
        finally:
            _HTTP_REQUEST.reset(token)


def _bounded(value: str | None, limit: int = 256) -> str | None:
    return value[:limit] if value else None


def summarize(value: Any, *, depth: int = 0) -> Any:
    """A bounded, redacted copy of call arguments for the journal."""
    if depth > 6:
        return "…"
    if isinstance(value, Mapping):
        items = list(value.items())
        summary = {
            str(key): REDACTED
            if env_name_is_secret(str(key))
            else summarize(item, depth=depth + 1)
            for key, item in items[:32]
        }
        if len(items) > 32:
            summary["…"] = f"+{len(items) - 32} keys"
        return summary
    if isinstance(value, (list, tuple)):
        shown = [summarize(item, depth=depth + 1) for item in value[:_ITEM_LIMIT]]
        if len(value) > _ITEM_LIMIT:
            shown.append(f"…+{len(value) - _ITEM_LIMIT} items")
        return shown
    if isinstance(value, str):
        clean = redact(value)
        return clean if len(clean) <= _STRING_LIMIT else clean[:_STRING_LIMIT] + "…"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return type(value).__name__


def _summary_text(arguments: Mapping[str, Any]) -> Any:
    summary = summarize(arguments)
    encoded = json.dumps(summary, sort_keys=True, separators=(",", ":"))
    if len(encoded) <= _SUMMARY_LIMIT:
        return summary
    return encoded[:_SUMMARY_LIMIT] + "…"


def emit(record: Mapping[str, Any]) -> None:
    sys.stderr.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    sys.stderr.flush()


def _ms(start: float | None, end: float | None) -> int | None:
    if start is None or end is None:
        return None
    return max(0, int((end - start) * 1000))


@dataclass
class CallRecord:
    """Timing and correlation of one tool call, written once when it ends."""

    action: str
    effect: str
    arguments: Mapping[str, Any]
    started: float = field(default_factory=time.monotonic)
    http: HttpRequest | None = field(default_factory=current_http_request)
    thread_started: float | None = None
    budget_seconds: float | None = None
    budget_exceeded: bool = False
    clamped: dict[str, Any] = field(default_factory=dict)

    def mark_thread_started(self) -> None:
        self.thread_started = time.monotonic()

    def finish(
        self,
        *,
        outcome: str,
        response: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        finished = time.monotonic()
        received = self.http.received if self.http is not None else None
        error = (response or {}).get("error") or {}
        receipt = (response or {}).get("receipt") or {}
        total_ms = _ms(received if received is not None else self.started, finished)
        record: dict[str, Any] = {
            "event": "gateway.call",
            "action": self.action,
            "effect": self.effect,
            "outcome": outcome,
            "code": error.get("code") if isinstance(error, Mapping) else None,
            "request_id": self.http.request_id if self.http else None,
            "session_id": self.http.session_id if self.http else None,
            "arguments": _summary_text(self.arguments),
            # Time between the HTTP request reaching this server and the tool
            # starting: event-loop or transport queueing inside the gateway.
            "queue_ms": _ms(received, self.started),
            # Time a synchronous handler waited for a worker thread.
            "thread_wait_ms": _ms(self.started, self.thread_started),
            "duration_ms": _ms(self.started, finished),
            "total_ms": total_ms,
            "budget_s": self.budget_seconds,
            "budget": (
                "none"
                if self.budget_seconds is None
                else "exceeded"
                if self.budget_exceeded
                else "within"
            ),
            # The tunnel's own queueing before it reaches this server is not
            # visible here; the tunnel's line for request_id is authoritative.
            "tunnel_deadline": (
                "exceeded"
                if total_ms is not None
                and total_ms >= TUNNEL_RESPONSE_DEADLINE_SECONDS * 1000
                else "met"
            ),
            "receipt_id": receipt.get("receipt_id")
            if isinstance(receipt, Mapping)
            else None,
        }
        if self.clamped:
            record["clamped"] = self.clamped
        return record


async def watch_event_loop(
    *, interval: float = 0.5, threshold: float = 1.0, sink: Callable = emit
) -> None:
    """Report every stretch in which the event loop could not run.

    A blocked loop stalls every concurrent call at once, which the tunnel
    reports only as a burst of dropped responses.
    """
    while True:
        before = time.monotonic()
        await anyio.sleep(interval)
        stall = time.monotonic() - before - interval
        if stall >= threshold:
            sink({"event": "gateway.loop_stall", "stall_ms": int(stall * 1000)})
