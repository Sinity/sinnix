from __future__ import annotations

import json
import socket
import struct
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

from sinnix_mcp import RequestEnvelope

from .capabilities import Capability, Principal
from .config import GatewayConfig
from .projects import ProjectError, ProjectService
from .schemas import AgentLaunchRequest


MAX_FRAME_BYTES = 1_048_576


class JobError(ValueError):
    """The authoritative Sinnixd job owner rejected a gateway request."""


def _read_exact(connection: socket.socket, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise JobError("sinnixd closed the response before it completed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _receive_frame(connection: socket.socket) -> dict[str, Any]:
    length = struct.unpack("!I", _read_exact(connection, 4))[0]
    if not length or length > MAX_FRAME_BYTES:
        raise JobError("sinnixd returned an invalid response frame")
    try:
        value = json.loads(_read_exact(connection, length))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise JobError("sinnixd returned malformed JSON") from error
    if not isinstance(value, dict):
        raise JobError("sinnixd returned a non-object response")
    return value


def _send_frame(connection: socket.socket, value: Mapping[str, Any]) -> None:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    if len(payload) > MAX_FRAME_BYTES:
        raise JobError("sinnixd request exceeds the frame bound")
    connection.sendall(struct.pack("!I", len(payload)) + payload)


def socket_transport(socket_path: Path, request: RequestEnvelope) -> dict[str, Any]:
    """Send one bounded, typed request to the daemon's existing RPC endpoint."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(5)
            connection.connect(str(socket_path))
            _send_frame(
                connection,
                {
                    "jsonrpc": "2.0",
                    "id": request.request_id,
                    "method": "dispatch",
                    "params": request.to_dict(),
                },
            )
            response = _receive_frame(connection)
    except OSError as error:
        raise JobError("sinnixd is unavailable") from error
    if response.get("jsonrpc") != "2.0" or response.get("id") != request.request_id:
        raise JobError("sinnixd response does not match the request")
    result = response.get("result")
    if not isinstance(result, dict):
        raise JobError("sinnixd response has no result envelope")
    return result


class JobService:
    """Gateway-side authorization and forwarding for daemon-owned typed jobs."""

    def __init__(
        self,
        config: GatewayConfig,
        principal: Principal,
        *,
        projects: ProjectService | None = None,
        transport: Callable[[Path, RequestEnvelope], dict[str, Any]] = socket_transport,
    ) -> None:
        self.config = config
        self.principal = principal
        self.projects = projects or ProjectService(config, principal)
        self.transport = transport

    def _call(
        self,
        operation: str,
        arguments: Mapping[str, Any],
        *,
        principal: str | None = None,
    ) -> dict[str, Any]:
        request = RequestEnvelope(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            operation=operation,
            owner="systemd-jobs",
            principal=principal or self.principal.name,
            arguments=arguments,
        )
        response = self.transport(self.config.sinnixd_socket, request)
        if response.get("request_id") != request.request_id or response.get(
            "correlation_id"
        ) != request.correlation_id:
            raise JobError("sinnixd response identity does not match the request")
        if response.get("owner") != "systemd-jobs" or not isinstance(
            response.get("ok"), bool
        ):
            raise JobError("sinnixd response violates the job-owner contract")
        if response["ok"] is False:
            error = response.get("error")
            message = error.get("message") if isinstance(error, dict) else None
            raise JobError(
                message
                if isinstance(message, str) and message
                else "sinnixd rejected the job request"
            )
        payload = response.get("payload")
        if not isinstance(payload, dict) or payload.get("kind") != "inline":
            raise JobError("sinnixd job response must contain an inline payload")
        value = payload.get("value")
        if not isinstance(value, dict):
            raise JobError("sinnixd job payload must be an object")
        return value

    def _checkout_id(self, project_id: str, checkout_id: str | None) -> str:
        selected = checkout_id or "default"
        try:
            self.projects.checkout(project_id, selected)
        except ProjectError as error:
            raise JobError(str(error)) from error
        return selected

    def launch_agent(self, request: AgentLaunchRequest) -> dict[str, Any]:
        self.principal.require(Capability.JOB_START)
        if self.principal.name != "agent-control":
            raise JobError("attested agent jobs require the agent-control principal")
        checkout_id = self._checkout_id(request.project_id, request.checkout_id)
        return self._call(
            "job.agent.start",
            {
                "project_id": request.project_id,
                "checkout_id": checkout_id,
                "prompt": request.prompt,
                "backend": request.backend,
                "model": request.model,
                "effort": request.reasoning_effort,
                "credential_profile": request.credential_profile,
                "timeout_seconds": request.timeout_seconds,
                "result": "last-message",
            },
            principal="agent-control",
        )

    def start_shell(
        self,
        *,
        project_id: str,
        checkout_id: str,
        argv: Sequence[str],
        cwd: str,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        self.principal.require(Capability.SHELL_RUN)
        if self.principal.name != "operator":
            raise JobError("operator shell jobs require the operator principal")
        return self._call(
            "job.shell.start",
            {
                "project_id": project_id,
                "checkout_id": self._checkout_id(project_id, checkout_id),
                "argv": list(argv),
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
                "result": "exit-status",
            },
            principal="operator",
        )

    def run_shell(
        self,
        *,
        project_id: str,
        checkout_id: str,
        argv: Sequence[str],
        cwd: str,
        timeout_seconds: int,
        max_bytes: int,
    ) -> dict[str, Any]:
        started = self.start_shell(
            project_id=project_id,
            checkout_id=checkout_id,
            argv=argv,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )
        job_id = started.get("job_id")
        if not isinstance(job_id, str):
            raise JobError("sinnixd start response omitted the job ID")
        waited = self.wait(job_id, timeout_seconds=timeout_seconds)
        logs = self.logs(job_id, offset=0, max_bytes=max_bytes)
        return {"job": started, "wait": waited, "logs": logs}

    def list(self, limit: int) -> dict[str, Any]:
        self.principal.require(Capability.JOB_READ)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1_000:
            raise JobError("job list limit must be an integer between 1 and 1000")
        response = self._call("job.list", {})
        jobs = response.get("jobs")
        if not isinstance(jobs, list):
            raise JobError("sinnixd job list is malformed")
        return {**response, "jobs": jobs[:limit]}

    def status(self, job_id: str) -> dict[str, Any]:
        self.principal.require(Capability.JOB_READ)
        return self._call("job.get", {"job_id": job_id})

    def wait(self, job_id: str, *, timeout_seconds: int) -> dict[str, Any]:
        self.principal.require(Capability.JOB_READ)
        return self._call(
            "job.wait", {"job_id": job_id, "timeout_seconds": timeout_seconds}
        )

    def logs(self, job_id: str, *, offset: int, max_bytes: int) -> dict[str, Any]:
        self.principal.require(Capability.JOB_READ)
        return self._call(
            "job.logs",
            {"job_id": job_id, "offset": offset, "max_bytes": max_bytes},
        )

    def result(self, job_id: str, *, max_bytes: int) -> dict[str, Any]:
        self.principal.require(Capability.JOB_READ)
        return self._call("job.result", {"job_id": job_id, "max_bytes": max_bytes})

    def read_output(
        self, job_id: str, artifact: str, offset: int, max_bytes: int
    ) -> dict[str, Any]:
        if artifact == "log":
            return self.logs(job_id, offset=offset, max_bytes=max_bytes)
        if artifact == "result":
            if offset != 0:
                raise JobError("result artifacts do not support offsets")
            return self.result(job_id, max_bytes=max_bytes)
        raise JobError("job artifact must be log or result")

    def cancel(self, job_id: str) -> dict[str, Any]:
        self.principal.require(Capability.JOB_CANCEL)
        return self._call("job.cancel", {"job_id": job_id})
