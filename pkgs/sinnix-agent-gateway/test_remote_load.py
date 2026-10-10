"""The remote tunnel's load contract: prompt answers, bounded waits, logs, drain.

The OpenAI tunnel drops any response later than about 120 s after it polled
the command. These tests pin the gateway behaviour that keeps answers inside
that deadline under concurrent use, and the record left for each call.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from http.client import HTTPConnection
from pathlib import Path
from typing import Any

import anyio
import pytest
from conftest import DirectJobs, call
from mcp.shared.inbound import (
    CLIENT_CAPABILITIES_META_KEY,
    MODERN_PROTOCOL_VERSIONS,
    PROTOCOL_VERSION_META_KEY,
)
from sinnix_agent_gateway import calllog, serving, tooling
from sinnix_agent_gateway import projects as projects_module
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.projects import ProjectService
from test_actions_jobs import DONE, make_server

MODERN_PROTOCOL = MODERN_PROTOCOL_VERSIONS[-1]
EMPTY_PAGE = {
    "jobs": [],
    "total": 0,
    "truncated": False,
    "next_cursor": None,
    "snapshot": {},
}


@dataclass
class GatedJobs(DirectJobs):
    """A job owner whose gated operations block until the test releases them."""

    gates: dict[str, threading.Event] = field(default_factory=dict)
    entered: dict[str, threading.Event] = field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:
        inner = super().__getattr__(name)
        operation = self._operations[name]
        gate = self.gates.get(operation)
        if gate is None:
            return inner

        def gated(**arguments: Any) -> Any:
            self.entered.setdefault(operation, threading.Event()).set()
            gate.wait(20)
            return inner(**arguments)

        return gated


def git(path: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(path), *arguments], check=True, capture_output=True
    )


def project_with_worktrees(tmp_path: Path, count: int) -> tuple[Path, list[Path]]:
    project = tmp_path / "project"
    project.mkdir()
    git(project, "init", "--quiet", "-b", "master")
    git(project, "config", "user.name", "Fixture")
    git(project, "config", "user.email", "fixture@example.invalid")
    (project / "README.md").write_text("fixture\n")
    git(project, "add", "README.md")
    git(project, "commit", "--quiet", "-m", "initial fixture")
    linked = []
    for index in range(count):
        path = tmp_path / f"linked-{index}"
        git(project, "worktree", "add", "--quiet", "-b", f"lane-{index}", str(path))
        linked.append(path.resolve())
    return project, linked


def test_one_checkout_read_hashes_only_that_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails if a single-checkout read content-hashes every linked worktree.

    Hashing each of a project's ~130 worktrees made one call take minutes.
    """
    project, linked = project_with_worktrees(tmp_path, 3)
    projects = ProjectService(
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={"fixture": ProjectConfig(project_id="fixture", path=project)},
        ),
        Principal.for_name("operator"),
    )
    hashed: list[Path] = []
    real = projects_module._content_revision
    monkeypatch.setattr(
        projects_module,
        "_content_revision",
        lambda root: hashed.append(Path(root)) or real(root),
    )
    target = next(
        row
        for row in projects.checkout_candidates("fixture")
        if row["path"] == str(linked[1])
    )

    row = projects.checkout("fixture", target["checkout_id"])["checkout"]

    assert row["path"] == str(linked[1]) and row["branch"] == "lane-1"
    assert hashed == [linked[1]]
    hashed.clear()
    assert projects.checkout_candidate("fixture", target["checkout_id"]) == target
    assert hashed == []


def test_checkout_listing_skips_a_worktree_removed_during_the_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails if one worktree vanishing mid-listing fails the whole read.

    Batch workers remove worktrees continually; 61 projects.get calls in one
    night failed with "cannot change to '/realm/worktree/…'".
    """
    project, linked = project_with_worktrees(tmp_path, 2)
    projects = ProjectService(
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={"fixture": ProjectConfig(project_id="fixture", path=project)},
        ),
        Principal.for_name("operator"),
    )
    listed = ProjectService._checkout_candidates

    def list_then_remove(self: ProjectService, config: Any) -> Any:
        candidates = listed(self, config)
        shutil.rmtree(linked[0])
        return candidates

    monkeypatch.setattr(ProjectService, "_checkout_candidates", list_then_remove)

    rows = projects.checkouts("fixture")["checkouts"]

    assert [row["path"] for row in rows] == [str(project), str(linked[1])]


def test_a_blocking_shell_start_does_not_stall_concurrent_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails if shell.run runs its owner call on the event loop.

    While the job owner is blocked, a concurrent jobs.list must still answer.
    With the owner on the loop, nothing else runs until it returns.
    """
    server, runtime, _ = make_server(tmp_path, "operator", monkeypatch)
    jobs = GatedJobs()
    release = threading.Event()
    jobs.gates["job.shell.start"] = release
    jobs.responses["job.shell.start"] = {**DONE, "job_id": "51"}
    jobs.responses["job.list"] = EMPTY_PAGE
    runtime.jobs = jobs  # type: ignore[assignment]
    released_at: list[float] = []

    def release_later() -> None:
        released_at.append(time.monotonic())
        release.set()

    timer = threading.Timer(3.0, release_later)
    listed_at: list[float] = []

    async def scenario() -> None:
        async with anyio.create_task_group() as group:
            group.start_soon(
                server.call_tool,
                "shell.run",
                {
                    "checkout": {"project": "fixture"},
                    "argv": ["true"],
                    "idempotency_key": "load-1",
                },
            )
            entered = jobs.entered.setdefault("job.shell.start", threading.Event())
            timer.start()
            await anyio.to_thread.run_sync(entered.wait, 10)
            result = await server.call_tool("jobs.list", {})
            assert result.structured_content["result"]["outcome"] == "ok"
            listed_at.append(time.monotonic())

    try:
        anyio.run(scenario)
    finally:
        timer.cancel()
        release.set()
    assert listed_at and released_at
    assert listed_at[0] < released_at[0]


def test_a_remote_read_answers_with_a_typed_deadline_inside_its_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails if a slow remote read runs past the budget instead of answering."""
    server, runtime, _ = make_server(tmp_path, "operator", monkeypatch)
    runtime.transport = tooling.REMOTE_TRANSPORT
    monkeypatch.setattr(tooling, "REMOTE_READ_BUDGET_SECONDS", 0.5)
    jobs = GatedJobs()
    release = threading.Event()
    jobs.gates["job.list"] = release
    jobs.responses["job.list"] = EMPTY_PAGE
    runtime.jobs = jobs  # type: ignore[assignment]

    started = time.monotonic()
    try:
        response = call(server, "jobs.list", {})
    finally:
        release.set()
    elapsed = time.monotonic() - started

    assert response["result"]["outcome"] != "ok"
    assert response["error"]["code"] == "deadline"
    assert response["error"]["details"]["budget_seconds"] == 0.5
    assert elapsed < 5


def test_a_remote_wait_is_capped_below_the_tunnel_deadline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Fails if a 300 s remote wait reaches the owner uncapped."""
    server, runtime, fake = make_server(tmp_path, "operator", monkeypatch)
    runtime.transport = tooling.REMOTE_TRANSPORT
    fake.responses["job.wait"] = {**DONE, "timed_out": True}

    waited = call(
        server, "jobs.wait", {"target": {"job_id": 41}, "timeout_seconds": 300}
    )

    assert waited["result"]["outcome"] == "ok", waited
    assert waited["data"]["outcome"] == "terminal"
    assert fake.calls[-1].arguments == {
        "job_id": 41,
        "timeout_seconds": tooling.REMOTE_WAIT_CAP_SECONDS,
    }
    line = next(
        json.loads(text)
        for text in capsys.readouterr().err.splitlines()
        if '"gateway.call"' in text
    )
    assert line["clamped"] == {
        "timeout_seconds": {
            "requested": 300,
            "used": tooling.REMOTE_WAIT_CAP_SECONDS,
        }
    }

    runtime.transport = "stdio"
    call(server, "jobs.wait", {"target": {"job_id": 41}, "timeout_seconds": 300})
    assert fake.calls[-1].arguments["timeout_seconds"] == 300


def test_each_remote_call_leaves_one_redacted_journal_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Fails if a remote call is unlogged or its log carries a secret value."""
    server, runtime, fake = make_server(tmp_path, "operator", monkeypatch)
    runtime.transport = tooling.REMOTE_TRANSPORT
    fake.responses["job.shell.start"] = {**DONE, "job_id": "52"}
    secret = "sk-" + "a1b2c3d4" * 4

    started = call(
        server,
        "shell.run",
        {
            "checkout": {"project": "fixture"},
            "argv": ["curl", "-H", f"Authorization: {secret}", "--token=" + secret],
            "cwd": "sub",
            "idempotency_key": "log-1",
        },
    )

    assert started["result"]["outcome"] == "ok", started
    stderr = capsys.readouterr().err
    assert secret not in stderr
    lines = [json.loads(text) for text in stderr.splitlines() if "gateway.call" in text]
    assert len(lines) == 1
    line = lines[0]
    assert line["action"] == "shell.run" and line["outcome"] == "ok"
    assert line["effect"] == "run" and line["code"] is None
    assert line["arguments"]["cwd"] == "sub"
    assert line["cwd"] == "sub"
    assert line["queue_ms"] is None or isinstance(line["queue_ms"], int)
    assert line["arguments"]["checkout"] == {"project": "fixture"}
    assert calllog.REDACTED in json.dumps(line["arguments"]["argv"])
    assert line["receipt_id"] == started["receipt"]["receipt_id"]
    assert isinstance(line["duration_ms"], int) and line["budget"] == "none"
    assert line["tunnel_deadline"] == "met"

    runtime.transport = "stdio"
    call(server, "jobs.list", {})
    assert "gateway.call" not in capsys.readouterr().err


def test_the_drain_deadline_ends_a_process_that_will_not_stop(
    tmp_path: Path,
) -> None:
    """Fails if a stop signal can leave the server running past its deadline."""
    import uvicorn

    exits: list[int] = []
    exited = threading.Event()
    server = serving.DrainingServer(
        uvicorn.Config(lambda *_: None, timeout_graceful_shutdown=1),
        exit_deadline_seconds=0.2,
        hard_exit=lambda code: (exits.append(code), exited.set()),
    )

    server.handle_exit(signal.SIGTERM, None)
    server.handle_exit(signal.SIGTERM, None)

    assert server.should_exit is True
    assert exited.wait(5)
    time.sleep(0.3)
    assert exits == [0]


class _UnixHTTP(HTTPConnection):
    def __init__(self, path: Path) -> None:
        super().__init__("localhost", timeout=30)
        self.path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(str(self.path))


def test_disconnected_unix_request_cannot_steal_another_calls_response(
    tmp_path, tmp_path_factory
):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"stateDir": str(tmp_path / "state"), "projects": {}}))
    socket_path = tmp_path_factory.mktemp("uds") / "mcp.sock"
    entered, release, completed = (
        tmp_path / name for name in ("entered", "release", "completed")
    )
    # Only the file probe is injected. Serving, HTTP/MCP dispatch, request
    # correlation, timeout handling and responses use the production stack.
    injection = """
import os, time
from pathlib import Path
from sinnix_agent_gateway.actions import waits
original = waits._probe
root = Path(os.environ['GATEWAY_PROBE_FIXTURE'])
def probe(runtime, condition):
    (root / 'entered').write_text(str(os.getpid()))
    deadline = time.monotonic() + 15
    while not (root / 'release').exists():
        if time.monotonic() > deadline:
            raise RuntimeError('fixture release missing')
        time.sleep(0.01)
    result = original(runtime, condition)
    (root / 'completed').write_text(str(os.getpid()))
    return result
waits._probe = probe
from sinnix_agent_gateway.cli import main
main()
"""

    def request(rid, name, arguments):
        connection = _UnixHTTP(socket_path)
        connection.request(
            "POST",
            "/mcp",
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "method": "tools/call",
                    "params": {
                        "name": name,
                        "arguments": arguments,
                        "_meta": {
                            PROTOCOL_VERSION_META_KEY: MODERN_PROTOCOL,
                            CLIENT_CAPABILITIES_META_KEY: {},
                        },
                    },
                }
            ),
            {
                "Host": "localhost:8000",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": MODERN_PROTOCOL,
                "Mcp-Method": "tools/call",
                "Mcp-Name": name,
                "X-Request-Id": f"isolation-fixture/{rid}",
            },
        )
        return connection

    def await_fact(predicate, process):
        deadline = time.monotonic() + 20
        while not predicate():
            assert process.poll() is None, stderr_path.read_text()
            assert time.monotonic() < deadline, "fixture did not reach expected phase"
            time.sleep(0.01)

    def catalog(rid):
        connection = request(rid, "gateway.catalog", {"limit": 1})
        try:
            response = connection.getresponse()
            body = response.read()
            assert response.status == 200, body
            result = json.loads(body)
            assert result["id"] == rid, result
            assert (
                result["result"]["structuredContent"]["result"]["outcome"] == "ok"
            ), result
            data = result["result"]["structuredContent"]["data"]
            assert len(data["actions"]) == 1
            assert len(data["catalog_sha256"]) == 64
        finally:
            connection.close()

    stderr_path = tmp_path / "stderr.log"
    with (
        stderr_path.open("wb") as stderr,
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                injection,
                "--config",
                str(config),
                "serve-http",
                "--socket",
                str(socket_path),
            ],
            env={**os.environ, "GATEWAY_PROBE_FIXTURE": str(tmp_path)},
            stdout=subprocess.DEVNULL,
            stderr=stderr,
        ) as process,
    ):
        try:
            await_fact(socket_path.exists, process)
            abandoned = request(
                101,
                "wait.for",
                {
                    "condition": {
                        "kind": "file_exists",
                        "target": {"path": str(tmp_path / "absent")},
                    },
                    "timeout_seconds": 1,
                },
            )
            await_fact(entered.exists, process)  # Proves real work was in flight.
            assert entered.read_text() == str(process.pid)
            abandoned.close()
            catalog(102)
            assert not completed.exists(), "concurrent call did not precede late work"
            # Let the original call's response budget expire before its owner
            # completes. This thread cannot satisfy a later HTTP request.
            await_fact(
                lambda: '"action":"wait.for"' in stderr_path.read_text(), process
            )
            release.write_text("release")
            await_fact(completed.exists, process)
            assert completed.read_text() == str(process.pid)
            catalog(103)
            assert process.poll() is None
        finally:
            release.write_text("release")
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=serving.EXIT_DEADLINE_SECONDS + 2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise

    calls = [
        json.loads(line)
        for line in stderr_path.read_text().splitlines()
        if line.startswith("{")
    ]
    calls = [row for row in calls if row.get("event") == "gateway.call"]
    assert {row["request_id"] for row in calls} == {
        "isolation-fixture/101",
        "isolation-fixture/102",
        "isolation-fixture/103",
    }
    abandoned_call = next(
        row for row in calls if row["request_id"] == "isolation-fixture/101"
    )
    assert abandoned_call["duration_ms"] >= 1000
    assert abandoned_call["action"] == "wait.for"
    assert all(
        row["action"] == "gateway.catalog" for row in calls if row is not abandoned_call
    )


def test_serve_http_logs_the_tunnel_request_id_and_drains_on_sigterm(
    tmp_path: Path,
    tmp_path_factory,
) -> None:
    """Fails if SIGTERM waits on an in-flight call, or calls lose correlation.

    A 60 s wait is in flight when the server is told to stop; the process must
    be gone well inside the unit's 10 s stop timeout.
    """
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"stateDir": str(tmp_path / "state"), "projects": {}})
    )
    socket_path = tmp_path_factory.mktemp("uds") / "mcp.sock"
    stderr_path = tmp_path / "stderr.log"
    command = [
        sys.executable,
        "-c",
        "from sinnix_agent_gateway.cli import main; main()",
        "--config",
        str(config_path),
        "serve-http",
        "--socket",
        str(socket_path),
    ]

    def tool_call(
        rid: int, name: str, arguments: dict[str, Any], request_id: str = ""
    ) -> tuple[int, bytes]:
        """One self-contained 2026-07-28 request, as the tunnel sends them."""
        connection = _UnixHTTP(socket_path)
        headers = {
            "Host": "localhost:8000",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": MODERN_PROTOCOL,
            "Mcp-Method": "tools/call",
            "Mcp-Name": name,
        }
        if request_id:
            headers["X-Request-Id"] = request_id
        payload = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments,
                "_meta": {
                    PROTOCOL_VERSION_META_KEY: MODERN_PROTOCOL,
                    CLIENT_CAPABILITIES_META_KEY: {},
                },
            },
        }
        try:
            connection.request("POST", "/mcp", json.dumps(payload), headers)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    with (
        stderr_path.open("wb") as stderr,
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=stderr) as process,
    ):
        try:
            deadline = time.monotonic() + 20
            while not socket_path.exists():
                assert process.poll() is None, stderr_path.read_text()
                assert time.monotonic() < deadline, "MCP socket did not appear"
                time.sleep(0.05)
            status, body = tool_call(
                1, "gateway.catalog", {"limit": 1}, request_id="wfr_fixture/abcd"
            )
            assert status == 200 and '"outcome":"ok"' in body.decode(), body

            def long_wait() -> None:
                try:
                    tool_call(
                        2,
                        "wait.for",
                        {
                            "condition": {
                                "kind": "file_exists",
                                "target": {"path": str(tmp_path / "never")},
                            },
                            "timeout_seconds": 60,
                        },
                    )
                except OSError:
                    pass

            waiter = threading.Thread(target=long_wait, daemon=True)
            waiter.start()
            time.sleep(1.0)
            stopped = time.monotonic()
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=serving.EXIT_DEADLINE_SECONDS + 2)
            assert time.monotonic() - stopped < serving.EXIT_DEADLINE_SECONDS + 1
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    events = [
        json.loads(text)
        for text in stderr_path.read_text().splitlines()
        if text.startswith("{")
    ]
    catalog = next(
        event
        for event in events
        if event.get("event") == "gateway.call" and event["action"] == "gateway.catalog"
    )
    assert catalog["request_id"] == "wfr_fixture/abcd"
    assert isinstance(catalog["queue_ms"], int)
    assert any(
        event.get("event") == "gateway.shutdown" and event["phase"] == "draining"
        for event in events
    )


def test_call_correlation_comes_from_the_calls_own_http_request() -> None:
    """Fails if a call's request id depends on which task runs the tool.

    A 2025 session runs tools outside the ASGI request task, so a live
    session call logged request_id null. The id and arrival time now come
    from the HTTP request the SDK hands the tool context.
    """
    from types import SimpleNamespace

    from starlette.requests import Request

    scope = {
        "type": "http",
        "headers": [(b"x-request-id", b"wfr_run/7"), (b"mcp-session-id", b"s-1")],
        calllog._RECEIVED: 12.5,
    }
    context = SimpleNamespace(request_context=SimpleNamespace(request=Request(scope)))

    http = calllog.http_request(context)

    assert http == calllog.HttpRequest(
        received=12.5, request_id="wfr_run/7", session_id="s-1"
    )
    assert calllog.http_request(None) is None
    assert calllog.http_request(SimpleNamespace(request_context=None)) is None


def test_a_remote_shell_still_running_is_logged_as_running(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Red if the call log writes `ok` for a shell whose work is unfinished.

    A lane full of long jobs showed up in the journal as a column of `ok`
    calls about 30 s long; the running state is what a reader needs.
    """
    server, runtime, fake = make_server(tmp_path, "operator", monkeypatch)
    runtime.transport = tooling.REMOTE_TRANSPORT
    running = {
        **DONE,
        "job_id": "53",
        "group": "shell-long",
        "state": {"phase": "running", "terminal": False, "exit_code": None},
    }
    fake.responses["job.shell.start"] = running

    started = call(
        server,
        "shell.run",
        {
            "checkout": {"project": "fixture"},
            "argv": ["claude", "-p", "long"],
            "idempotency_key": "log-running",
        },
    )

    assert started["result"]["outcome"] == "ok", started
    assert started["data"]["outcome"] == "running"
    (line,) = [
        json.loads(text)
        for text in capsys.readouterr().err.splitlines()
        if "gateway.call" in text
    ]
    assert line["outcome"] == "running"
    assert (line["job_id"], line["group"]) == (53, "shell-long")

    fake.responses["job.shell.start"] = {**DONE, "job_id": "54", "group": "shell-quick"}
    call(
        server,
        "shell.run",
        {
            "checkout": {"project": "fixture"},
            "argv": ["true"],
            "idempotency_key": "log-done",
        },
    )
    (done,) = [
        json.loads(text)
        for text in capsys.readouterr().err.splitlines()
        if "gateway.call" in text
    ]
    assert done["outcome"] == "ok" and done["job_id"] == 54


def test_a_catalog_call_does_not_stall_the_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red if the catalog builds or hashes every action schema on the event loop.

    That held the loop for about a second per `gateway.catalog`, and every
    concurrent call waited as long (the `gateway.loop_stall` lines of
    2026-09-29).
    """
    from sinnix_agent_gateway.app import create_server

    server = create_server(
        GatewayConfig(state_dir=tmp_path / "state", projects={}), "operator"
    )
    stalls: list[dict[str, Any]] = []

    async def scenario() -> None:
        async with anyio.create_task_group() as group:
            group.start_soon(
                lambda: calllog.watch_event_loop(
                    interval=0.02, threshold=0.25, sink=stalls.append
                )
            )
            await anyio.sleep(0.05)
            for query in ("shell", "jobs", "files"):
                result = await server.call_tool(
                    "gateway.catalog",
                    {
                        "query": query,
                        "include_schemas": True,
                        "include_mcp_tools": False,
                    },
                )
                assert result.structured_content["result"]["outcome"] == "ok"
            await anyio.sleep(0.05)
            group.cancel_scope.cancel()

    anyio.run(scenario)
    assert stalls == []
