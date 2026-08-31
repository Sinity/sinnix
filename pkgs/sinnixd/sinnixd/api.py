from __future__ import annotations

import json
import socket
import struct
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import BoundedSemaphore, Event
from typing import Any, Callable

from sinnix_mcp import (
    ErrorCode,
    ErrorEnvelope,
    RequestEnvelope,
    ResponseEnvelope,
    response_envelope_from_dict,
)

from .jobs import DEFAULT_WAIT_SECONDS, MAX_WAIT_SECONDS
from .service import SinnixdService

MAX_FRAME_BYTES = 1_048_576
CONNECTION_TIMEOUT_SECONDS = 5.0
WAIT_TRANSPORT_MARGIN_SECONDS = 5.0
DEFAULT_RESPONSE_BUDGET_SECONDS = 15.0
# Every daemon operation carries an explicit response budget; job.wait and
# plan.wait derive theirs from the requested wait window instead. The table
# must cover service.SUPPORTED_OPERATIONS exactly — a new operation without a
# declared budget fails the contract test, not silently the 5s connect
# fallback (sinnix-16in).
CONTROL_OPERATION_RESPONSE_TIMEOUT_SECONDS = {
    "runtime.status": DEFAULT_RESPONSE_BUDGET_SECONDS,
    "project.list": DEFAULT_RESPONSE_BUDGET_SECONDS,
    "project.reload": 60.0,
    "project.get": DEFAULT_RESPONSE_BUDGET_SECONDS,
    "project.operations": DEFAULT_RESPONSE_BUDGET_SECONDS,
    "plan.submit": 60.0,
    "plan.get": DEFAULT_RESPONSE_BUDGET_SECONDS,
    "plan.list": 60.0,
    "plan.result": DEFAULT_RESPONSE_BUDGET_SECONDS,
    "packet.status": 60.0,
    "packet.finalize": 420.0,
    # Listing runs git identity checks per record; at fleet scale it exceeds
    # a short default and was misreported as "sinnixd is unavailable" (dn4c).
    "workspace.list": 60.0,
    "workspace.get": 60.0,
    "workspace.adopt": 60.0,
    "workspace.reap": 60.0,
    "workspace.dispose": 60.0,
    "workspace.checkpoint": 120.0,
    "workspace.restore": 120.0,
    "workspace.recover": 300.0,
    "workspace.stack": 120.0,
    "workspace.restack": 300.0,
    "workspace.publish": 60.0,
    "workspace.review-status": 65.0,
    "workspace.land": 60.0,
    "workspace.finish": 185.0,
    "workspace.finish-integrated": 185.0,
    # Creation runs `git worktree add` and then the project's provision exec
    # hook (e.g. uv sync) before answering; `packet launch` dispatches it as
    # its own step, so provisioning must fit this budget.
    "workspace.create": 300.0,
    # Wave scheduling compiles every ready bead's packet before answering.
    "campaign.run": 300.0,
    "job.start": 60.0,
    "job.fire": 60.0,
    "job.shell.start": 60.0,
    "job.agent.start": 60.0,
    "job.admission.reset": DEFAULT_RESPONSE_BUDGET_SECONDS,
    "job.admission": DEFAULT_RESPONSE_BUDGET_SECONDS,
    "job.admission.explain": DEFAULT_RESPONSE_BUDGET_SECONDS,
    # Get and list reconcile live systemd state per non-terminal record; at
    # fleet scale a short budget times the client out mid-response and the
    # daemon logs a broken pipe for every retry (sinnix-16in evidence).
    "job.get": 60.0,
    "job.retry": 60.0,
    "job.resume": 60.0,
    "job.list": 90.0,
    "job.notify-exit": DEFAULT_RESPONSE_BUDGET_SECONDS,
    "job.logs": 60.0,
    "job.result": 60.0,
    "job.cancel": 60.0,
    "task.complete": 60.0,
    "campaign.status": 30.0,
}
WAIT_OPERATIONS = {"job.wait", "plan.wait"}
ACCEPT_POLL_SECONDS = 0.1
RESERVED_CONTROL_WORKERS = 2
MAX_JSON_RPC_ERROR_MESSAGE_BYTES = 1_024
JSON_RPC_INVALID_REQUEST = -32600
WAIT_CAPACITY_EXHAUSTED_MESSAGE = "job.wait capacity is exhausted"


class ProtocolError(ValueError):
    """Raised when a Unix-socket RPC frame is malformed or exceeds its bound."""


class SinnixdClientError(ValueError):
    """The canonical client could not obtain a valid daemon response."""


class ResponseBudgetExceeded(SinnixdClientError):
    """The daemon accepted the request but did not answer within its budget.

    Distinct from unavailability: the socket connected and the request was
    sent, so the daemon is alive and may still complete the work. Callers
    report the budget, not a false outage.
    """

    def __init__(self, operation: str, budget_seconds: float) -> None:
        self.operation = operation
        self.budget_seconds = budget_seconds
        super().__init__(
            f"response budget exceeded: operation={operation} "
            f"budget={budget_seconds:g}s (the daemon is alive; the request may "
            "still be executing)"
        )


@dataclass(frozen=True)
class JsonRpcErrorEnvelope:
    """A bounded JSON-RPC error frame accepted from the local daemon."""

    code: int
    message: str

    def __post_init__(self) -> None:
        if isinstance(self.code, bool) or not isinstance(self.code, int):
            raise ProtocolError("response error code must be an integer")
        if not isinstance(self.message, str):
            raise ProtocolError("response error message must be a string")
        try:
            message_bytes = self.message.encode()
        except UnicodeEncodeError as error:
            raise ProtocolError("response error message must be valid UTF-8") from error
        if not message_bytes or len(message_bytes) > MAX_JSON_RPC_ERROR_MESSAGE_BYTES:
            raise ProtocolError("response error message exceeds its bound")


def _read_exact(connection: socket.socket, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise ConnectionError("socket closed before a complete frame arrived")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def receive_frame(connection: socket.socket) -> dict[str, Any]:
    length = struct.unpack("!I", _read_exact(connection, 4))[0]
    if not length or length > MAX_FRAME_BYTES:
        raise ProtocolError(f"invalid frame length: {length}")
    try:
        value = json.loads(_read_exact(connection, length))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ProtocolError(f"invalid JSON frame: {error}") from error
    if not isinstance(value, dict):
        raise ProtocolError("request frame must be an object")
    return value


def send_frame(connection: socket.socket, value: dict[str, Any]) -> None:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    if len(payload) > MAX_FRAME_BYTES:
        raise ProtocolError("response frame exceeds its bound")
    connection.sendall(struct.pack("!I", len(payload)) + payload)


def _response_timeout_seconds(request: RequestEnvelope) -> float:
    if request.operation not in WAIT_OPERATIONS:
        return CONTROL_OPERATION_RESPONSE_TIMEOUT_SECONDS.get(
            request.operation, DEFAULT_RESPONSE_BUDGET_SECONDS
        )
    timeout_seconds = request.arguments.get("timeout_seconds", DEFAULT_WAIT_SECONDS)
    if (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or not 1 <= timeout_seconds <= MAX_WAIT_SECONDS
    ):
        return CONNECTION_TIMEOUT_SECONDS
    return timeout_seconds + WAIT_TRANSPORT_MARGIN_SECONDS


def _json_rpc_error_from_dict(value: Any) -> JsonRpcErrorEnvelope:
    if not isinstance(value, dict) or set(value) != {"code", "message"}:
        raise ProtocolError("response error has invalid fields")
    return JsonRpcErrorEnvelope(code=value["code"], message=value["message"])


def _response_from_json_rpc_error(
    request: RequestEnvelope, error: JsonRpcErrorEnvelope
) -> dict[str, Any]:
    if (
        error.code == JSON_RPC_INVALID_REQUEST
        and error.message == WAIT_CAPACITY_EXHAUSTED_MESSAGE
    ):
        return ResponseEnvelope(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            owner=request.owner,
            error=ErrorEnvelope(ErrorCode.RESOURCE_EXHAUSTED, error.message),
        ).to_dict()
    raise SinnixdClientError("sinnixd is unavailable")


def _response_result_from_json_rpc_frame(
    request: RequestEnvelope, response: dict[str, Any]
) -> dict[str, Any]:
    if response.get("jsonrpc") != "2.0" or response.get("id") != request.request_id:
        raise ProtocolError("response does not match the request")
    has_result = "result" in response
    has_error = "error" in response
    if has_result == has_error:
        raise ProtocolError("response requires exactly one of result or error")
    expected_fields = (
        {"jsonrpc", "id", "error"} if has_error else {"jsonrpc", "id", "result"}
    )
    if set(response) != expected_fields:
        raise ProtocolError("response has invalid fields")
    if has_error:
        return _response_from_json_rpc_error(
            request, _json_rpc_error_from_dict(response["error"])
        )
    result = response["result"]
    if not isinstance(result, dict):
        raise ProtocolError("response requires an object result")
    return result


@dataclass
class UnixSocketServer:
    socket_path: Path
    service: SinnixdService
    connection_timeout_seconds: float = CONNECTION_TIMEOUT_SECONDS
    # Wait connections block a dedicated thread each; with event-driven waits
    # those threads are parked on a condition, so a wide pool is cheap and
    # long waits no longer exhaust the slots that polling once did.
    max_workers: int = 18
    ready_event: Event | None = None

    @property
    def wait_worker_count(self) -> int:
        if self.max_workers <= RESERVED_CONTROL_WORKERS:
            raise ValueError(f"max_workers must exceed {RESERVED_CONTROL_WORKERS}")
        return self.max_workers - RESERVED_CONTROL_WORKERS

    def serve_once(self) -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            self._bind(listener)
            try:
                with ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="sinnixd-rpc"
                ) as executor:
                    self._accept_connection(listener, executor, BoundedSemaphore(1))
            finally:
                self.socket_path.unlink(missing_ok=True)

    def serve_forever(self, stop_event: Event | None = None) -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            self._bind(listener)
            listener.settimeout(ACCEPT_POLL_SECONDS)
            try:
                with (
                    ThreadPoolExecutor(
                        max_workers=RESERVED_CONTROL_WORKERS,
                        thread_name_prefix="sinnixd-control",
                    ) as control_executor,
                    ThreadPoolExecutor(
                        max_workers=self.wait_worker_count,
                        thread_name_prefix="sinnixd-wait",
                    ) as wait_executor,
                ):
                    control_permits = BoundedSemaphore(RESERVED_CONTROL_WORKERS)
                    wait_permits = BoundedSemaphore(self.wait_worker_count)
                    while stop_event is None or not stop_event.is_set():
                        try:
                            self._accept_connection(
                                listener,
                                control_executor,
                                control_permits,
                                wait_executor,
                                wait_permits,
                            )
                        except socket.timeout:
                            continue
            finally:
                self.socket_path.unlink(missing_ok=True)

    def _bind(self, listener: socket.socket) -> None:
        self.socket_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.socket_path.unlink(missing_ok=True)
        listener.bind(str(self.socket_path))
        self.socket_path.chmod(0o600)
        listener.listen()
        if self.ready_event is not None:
            self.ready_event.set()

    def _accept_connection(
        self,
        listener: socket.socket,
        executor: ThreadPoolExecutor,
        permits: BoundedSemaphore,
        wait_executor: ThreadPoolExecutor | None = None,
        wait_permits: BoundedSemaphore | None = None,
    ) -> None:
        if not permits.acquire(timeout=ACCEPT_POLL_SECONDS):
            return
        try:
            connection, _address = listener.accept()
        except OSError:
            permits.release()
            raise
        executor.submit(
            self._serve_connection, connection, permits, wait_executor, wait_permits
        )

    def _serve_connection(
        self,
        connection: socket.socket,
        permits: BoundedSemaphore,
        wait_executor: ThreadPoolExecutor | None = None,
        wait_permits: BoundedSemaphore | None = None,
    ) -> None:
        handed_off = False
        request_id: Any = None
        request: RequestEnvelope | None = None
        try:
            connection.settimeout(self.connection_timeout_seconds)
            raw = receive_frame(connection)
            request_id = raw.get("id")
            if raw.get("jsonrpc") != "2.0" or raw.get("method") != "dispatch":
                raise ProtocolError("request must be a JSON-RPC 2.0 dispatch call")
            params = raw.get("params")
            if not isinstance(request_id, str) or not isinstance(params, dict):
                raise ProtocolError("request requires string id and object params")
            request = RequestEnvelope(**params)
            if request.request_id != request_id:
                raise ProtocolError("JSON-RPC id must equal envelope request_id")
            if (
                request.operation == "job.wait"
                and wait_executor is not None
                and wait_permits is not None
            ):
                if not wait_permits.acquire(blocking=False):
                    raise ProtocolError("job.wait capacity is exhausted")
                connection.settimeout(_response_timeout_seconds(request))
                wait_executor.submit(
                    self._serve_wait_connection,
                    connection,
                    request_id,
                    request,
                    wait_permits,
                )
                handed_off = True
            else:
                self._send_response(connection, request_id, request)
        except (
            ConnectionError,
            OSError,
            ProtocolError,
            TypeError,
            ValueError,
        ) as error:
            # The client is told only that the daemon is unavailable, so this
            # line is the operator's only account of a refused request.
            print(
                f"request failed: operation={request.operation if request is not None else 'unknown'} "
                f"request_id={request_id}: {error!r}",
                file=sys.stderr,
                flush=True,
            )
            try:
                send_frame(
                    connection,
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32600, "message": str(error)},
                    },
                )
            except OSError:
                pass
        finally:
            permits.release()
            if not handed_off:
                connection.close()

    def _serve_wait_connection(
        self,
        connection: socket.socket,
        request_id: str,
        request: RequestEnvelope,
        permits: BoundedSemaphore,
    ) -> None:
        try:
            self._send_response(connection, request_id, request)
        except OSError:
            pass
        finally:
            connection.close()
            permits.release()

    def _send_response(
        self, connection: socket.socket, request_id: str, request: RequestEnvelope
    ) -> None:
        response = self.service.dispatch(request)
        send_frame(
            connection,
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": response.to_dict(),
            },
        )


def call(socket_path: Path, request: RequestEnvelope) -> dict[str, Any]:
    budget_seconds = _response_timeout_seconds(request)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        # Connect/send failures mean the daemon is unreachable and stay
        # OSError; once the request is in flight, running out the response
        # budget is a distinct typed condition (sinnix-16in).
        connection.settimeout(CONNECTION_TIMEOUT_SECONDS)
        connection.connect(str(socket_path))
        send_frame(
            connection,
            {
                "jsonrpc": "2.0",
                "id": request.request_id,
                "method": "dispatch",
                "params": request.to_dict(),
            },
        )
        connection.settimeout(budget_seconds)
        try:
            response = receive_frame(connection)
        except TimeoutError as error:
            raise ResponseBudgetExceeded(request.operation, budget_seconds) from error
    return _response_result_from_json_rpc_frame(request, response)


@dataclass(frozen=True)
class SinnixdClient:
    """Typed client for the daemon's bounded local request/response contract."""

    socket_path: Path
    transport: Callable[[Path, RequestEnvelope], dict[str, Any]] = call

    def dispatch(self, request: RequestEnvelope) -> ResponseEnvelope:
        try:
            raw = self.transport(self.socket_path, request)
        except (OSError, ProtocolError) as error:
            raise SinnixdClientError("sinnixd is unavailable") from error
        try:
            response = response_envelope_from_dict(raw)
        except ValueError as error:
            raise SinnixdClientError("sinnixd returned an invalid response") from error
        if (
            response.request_id != request.request_id
            or response.correlation_id != request.correlation_id
        ):
            raise SinnixdClientError("sinnixd response does not match the request")
        return response
