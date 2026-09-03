from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
import sinnixd.cli as cli_module
import sinnixd.jobs as jobs_module
import sinnixd.projects as projects
import sinnixd.queue_run as queue_run
import sinnixd.runner as runner_module
from sinnix_mcp import (
    ErrorCode,
    OpaquePayload,
    RequestEnvelope,
    ResponseEnvelope,
)
from sinnix_mcp.execution import ExecutionResult
from sinnixd.api import (
    CONTROL_OPERATION_RESPONSE_TIMEOUT_SECONDS,
    MAX_JSON_RPC_ERROR_MESSAGE_BYTES,
    WAIT_OPERATIONS,
    WAIT_TRANSPORT_MARGIN_SECONDS,
    ProtocolError,
    ResponseBudgetExceeded,
    SinnixdClient,
    SinnixdClientError,
    UnixSocketServer,
    _response_timeout_seconds,
    call,
    receive_frame,
    send_frame,
)
from sinnixd.environment import build_environment
from sinnixd.jobs import (
    DEFAULT_TIMEOUT_SECONDS,
    GenericJobs,
    GenericJobSpec,
    GenericJobStore,
    JobResultError,
    JobResultLimitError,
    UserSystemdJobs,
    scheduled_operation_id,
)
from sinnixd.limits import MAX_DECLARED_OPERATION_TIMEOUT_SECONDS
from sinnixd.projects import (
    ProjectCatalog,
    ProjectConfigError,
    parse_worktree_records,
    validate_agent_environment_descriptors,
)
from sinnixd.runner import (
    RunnerError,
    _exec_shell,
    _load,
    _require_environment,
    _revalidate_checkout,
    _run_agent,
    _seal_packet_result,
)
from sinnixd.service import SUPPORTED_OPERATIONS, SinnixdService
from sinnixd.workspaces import (
    WorkspaceError,
    WorkspaceRecord,
)

if TYPE_CHECKING:
    from conftest import FakePueue


@pytest.fixture(autouse=True)
def _fake_pueue(fake_pueue: FakePueue) -> FakePueue:
    """Every test in this module runs against the in-memory pueue fake."""
    return fake_pueue


@pytest.mark.parametrize(("ok", "expected"), ((True, 0), (False, 1)))
def test_agentctl_exit_status_matches_response_envelope(
    ok: bool,
    expected: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    response = {"schema": 1, "ok": ok}
    monkeypatch.setattr(sys, "argv", ["agentctl", "status"])
    monkeypatch.setattr(cli_module, "call", lambda socket_path, request: response)

    assert cli_module.main() == expected
    assert json.loads(capsys.readouterr().out) == response


def test_canonical_client_validates_typed_response_identity() -> None:
    request = RequestEnvelope(
        request_id=str(uuid4()),
        correlation_id=str(uuid4()),
        operation="runtime.status",
        owner="sinnixd",
        principal="observer",
    )
    response = ResponseEnvelope(
        request_id=request.request_id,
        correlation_id=request.correlation_id,
        owner="sinnixd",
        payload=OpaquePayload.bounded({"status": "ready"}),
    )
    client = SinnixdClient(
        Path("/run/user/fixture/sinnixd.sock"),
        lambda _path, _request: response.to_dict(),
    )

    assert client.dispatch(request) == response

    mismatched = SinnixdClient(
        Path("/run/user/fixture/sinnixd.sock"),
        lambda _path, _request: ResponseEnvelope(
            request_id=str(uuid4()),
            correlation_id=request.correlation_id,
            owner="sinnixd",
            payload=OpaquePayload.bounded({}),
        ).to_dict(),
    )
    with pytest.raises(SinnixdClientError, match="does not match"):
        mismatched.dispatch(request)


def test_retired_descriptor_sections_load_without_effect(tmp_path: Path) -> None:
    """Operator descriptors still declare `cache` and `[owner_adapters]`.

    Anti-vacuity: rejecting either as an unknown field would take every
    project declaring them out of service.
    """
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        + """
[owner_adapters.polylogue_archive]
namespace = "polylogue.archive"
owner = "polylogue-archive"
authority = "owner"
lifecycle = "read_only"
protocol_versions = [1]
source_scoped = true
source_ref = "sinnix://polylogue/archive"
exec = ["polylogue-agentctl-adapter"]
"""
    )

    project = ProjectCatalog([tmp_path]).get("fixture")

    assert "cache" not in project.operation("check").catalog_row()
    assert "owner_adapters" not in project.catalog_row()


def test_runtime_status_lists_the_dispatchable_operations(tmp_path: Path) -> None:
    """Anti-vacuity: status exposes the operation surface, not only version and owners."""
    service = SinnixdService(ProjectCatalog([]), jobs=generic_jobs(tmp_path))

    response = service.dispatch(request("runtime.status", "sinnixd"))

    assert response.ok and response.payload is not None
    assert response.payload.inline["operations"] == sorted(SUPPORTED_OPERATIONS)


@pytest.mark.parametrize(
    ("shape", "error"),
    (
        ("mismatched-id", "response does not match the request"),
        ("unexpected-response-field", "response has invalid fields"),
        ("unexpected-error-field", "response error has invalid fields"),
        ("oversized-error-message", "response error message exceeds its bound"),
    ),
)
def test_call_preserves_request_matching_and_rejects_malformed_json_rpc_errors(
    tmp_path: Path, shape: str, error: str
) -> None:
    request_value = request("runtime.status", "sinnixd")
    socket_path = tmp_path / "sinnixd.sock"

    def reply(raw: dict[str, object]) -> dict[str, object]:
        if shape == "mismatched-id":
            return {
                "jsonrpc": "2.0",
                "id": "not-the-request-id",
                "result": {"ok": True},
            }
        if shape == "unexpected-response-field":
            return {
                "jsonrpc": "2.0",
                "id": raw["id"],
                "result": {"ok": True},
                "extra": "rejected",
            }
        message = (
            "server-secret"
            if shape == "unexpected-error-field"
            else "x" * (MAX_JSON_RPC_ERROR_MESSAGE_BYTES + 1)
        )
        error_value: dict[str, object] = {"code": -32600, "message": message}
        if shape == "unexpected-error-field":
            error_value["data"] = "must-not-be-accepted"
        return {"jsonrpc": "2.0", "id": raw["id"], "error": error_value}

    thread = start_rpc_reply_server(socket_path, reply)

    with pytest.raises(ProtocolError, match=error):
        call(socket_path, request_value)

    thread.join(timeout=1)
    assert not thread.is_alive()


def test_canonical_client_redacts_unrecognized_json_rpc_errors(tmp_path: Path) -> None:
    request_value = request("runtime.status", "sinnixd")
    socket_path = tmp_path / "sinnixd.sock"
    thread = start_rpc_reply_server(
        socket_path,
        lambda raw: {
            "jsonrpc": "2.0",
            "id": raw["id"],
            "error": {"code": -32600, "message": "server-secret-must-not-escape"},
        },
    )

    with pytest.raises(SinnixdClientError, match="^sinnixd is unavailable$") as raised:
        SinnixdClient(socket_path).dispatch(request_value)
    assert raised.value.code is ErrorCode.OWNER_UNAVAILABLE
    assert raised.value.operation == "runtime.status"
    assert raised.value.effect == "none"

    thread.join(timeout=1)
    assert not thread.is_alive()


def test_error_envelope_preserves_operation_and_no_effect_for_validation(
    tmp_path: Path,
) -> None:
    service = SinnixdService(ProjectCatalog([]), jobs=generic_jobs(tmp_path))

    response = service.dispatch(request("workspace.create", "git-workspaces"))

    assert response.error is not None
    assert response.error.code is ErrorCode.INVALID_ARGUMENT
    assert response.error.details.inline == {
        "operation": "workspace.create",
        "effect": "none",
    }


def test_client_redaction_keeps_timeout_effect_and_hides_exception_text() -> None:
    request_value = request("job.start", "systemd-jobs")
    error = ResponseBudgetExceeded("job.start", 15.0)

    response = cli_module._client_error_response(request_value, error)

    assert response["error"] == {
        "schema": 1,
        "code": "RESPONSE_BUDGET_EXCEEDED",
        "message": "sinnixd response budget exceeded",
        "details": {
            "kind": "inline",
            "value": {"operation": "job.start", "effect": "possible"},
        },
    }
    assert "daemon is alive" not in json.dumps(response)


def test_a_refused_request_is_reported_to_the_daemon_log(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """The client is told only that the daemon is unavailable, by design.

    That confidentiality is deliberate (the test above proves a server message
    must not escape), so the daemon's own log is the operator's only account of
    a refused request. Without it a refusal leaves nothing to act on anywhere.

    Anti-vacuity: remove the stderr report from the connection handler and the
    failing request appears in no reachable place at all.
    """
    service = SinnixdService(ProjectCatalog([]), jobs=generic_jobs(tmp_path))
    socket_path = tmp_path / "sinnixd.sock"
    stop_event = threading.Event()
    server = UnixSocketServer(socket_path, service, connection_timeout_seconds=1.0)
    thread = start_server(server, stop_event=stop_event)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(5)
            connection.connect(str(socket_path))
            send_frame(
                connection, {"jsonrpc": "2.0", "id": "x", "method": "not-dispatch"}
            )
            receive_frame(connection)
    finally:
        stop_event.set()
        thread.join(timeout=5)

    log = capfd.readouterr().err
    assert "request failed:" in log
    assert "correlation_id=unknown" in log


def test_agentctl_job_list_exposes_service_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, RequestEnvelope] = {}

    def fake_call(socket_path, request_value):
        captured["request"] = request_value
        return {"schema": 1, "ok": True}

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agentctl",
            "job",
            "list",
            "--limit",
            "250",
            "--project",
            "polylogue",
            "--phase",
            "queued",
            "--phase",
            "running",
            "--active",
        ],
    )
    monkeypatch.setattr(cli_module, "call", fake_call)

    assert cli_module.main() == 0
    outbound = captured["request"]
    assert outbound.operation == "job.list"
    assert outbound.owner == "systemd-jobs"
    assert dict(outbound.arguments) == {
        "limit": 250,
        "project_id": "polylogue",
        "phases": ["queued", "running"],
        "kinds": [],
        "active_only": True,
    }


def test_agentctl_job_list_accepts_active_only_alias() -> None:
    arguments = cli_module.parser().parse_args(["job", "list", "--active-only"])

    assert arguments.active is True


def test_agentctl_workspace_drop_maps_to_a_typed_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, RequestEnvelope] = {}

    def fake_call(socket_path, request_value):
        captured["request"] = request_value
        return {"schema": 1, "ok": True}

    monkeypatch.setattr(sys, "argv", ["agentctl", "workspace", "drop", "workspace-1"])
    monkeypatch.setattr(cli_module, "call", fake_call)

    assert cli_module.main() == 0
    outbound = captured["request"]
    assert outbound.operation == "workspace.drop"
    assert outbound.owner == "git-workspaces"
    assert outbound.principal == "agent-control"
    assert dict(outbound.arguments) == {"workspace_id": "workspace-1"}


def test_agentctl_job_start_maps_parameters_json_to_the_typed_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, RequestEnvelope] = {}

    def fake_call(socket_path, request_value):
        captured["request"] = request_value
        return {"schema": 1, "ok": True}

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agentctl",
            "job",
            "start",
            "fixture",
            "parameterized",
            "--parameters-json",
            '{"package":["xtask","sinexd"],"full":true}',
        ],
    )
    monkeypatch.setattr(cli_module, "call", fake_call)

    assert cli_module.main() == 0
    assert dict(captured["request"].arguments) == {
        "project_id": "fixture",
        "operation": "parameterized",
        "workspace_id": None,
        "parameters": {"package": ["xtask", "sinexd"], "full": True},
    }


def test_agentctl_job_start_wait_follows_terminal_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    responses: list[dict[str, Any]] = [
        {
            "schema": 1,
            "ok": True,
            "payload": {"value": {"job_id": "job-1", "timeout_seconds": 7200}},
        },
        {
            "schema": 1,
            "ok": True,
            "payload": {
                "value": {
                    "job_id": "job-1",
                    "state": {"phase": "succeeded", "terminal": True},
                }
            },
        },
        {"schema": 1, "ok": True, "payload": {"value": {"status": "succeeded"}}},
    ]
    requests: list[RequestEnvelope] = []

    def fake_call(socket_path, request_value):
        requests.append(request_value)
        return responses.pop(0)

    monkeypatch.setattr(
        sys,
        "argv",
        ["agentctl", "job", "start", "lynchpin", "converge", "--wait"],
    )
    monkeypatch.setattr(cli_module, "call", fake_call)

    assert cli_module.main() == 0
    assert [request.operation for request in requests] == [
        "job.start",
        "job.wait",
        "job.result",
    ]
    printed = json.loads(capsys.readouterr().out)
    assert printed["payload"]["value"]["status"] == "succeeded"


def test_agentctl_job_start_wait_reports_failure_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses: list[dict[str, Any]] = [
        {
            "schema": 1,
            "ok": True,
            "payload": {"value": {"job_id": "job-1", "timeout_seconds": 60}},
        },
        {
            "schema": 1,
            "ok": True,
            "payload": {
                "value": {
                    "job_id": "job-1",
                    "state": {"phase": "failed", "terminal": True},
                }
            },
        },
    ]

    def fake_call(socket_path, request_value):
        return responses.pop(0)

    monkeypatch.setattr(
        sys,
        "argv",
        ["agentctl", "job", "start", "lynchpin", "converge", "--wait"],
    )
    monkeypatch.setattr(cli_module, "call", fake_call)

    assert cli_module.main() == 1


def write_adapter(root: Path, *, project_id: str = "fixture") -> None:
    (root / "modules").mkdir(parents=True)
    (root / "flake.nix").write_text("{}")
    (root / ".agentctl").mkdir()
    (root / ".agentctl" / "project.toml").write_text(
        f"""schema = 1

[project]
id = "{project_id}"
display_name = "{project_id.title()}"
root_markers = ["flake.nix", "modules"]

[environment]
kind = "fixture"
command = ["fixture-env", "--command"]
preflight = ["devtools", "status", "--stderr"]
inherit = ["HOME"]
unset = ["PYTHONPATH"]

[workspace]
provider = "git-worktree"
root = "{root / "worktrees"}"
default_base = "origin/master"
identity_check = ["git", "diff", "--quiet"]
checkpoint_untracked = true
verification_operations = ["check"]

[conflicts]
exact_files = ["fixture.lock"]
generated_surfaces = ["generated.json"]

[conflicts.semantic_slots]
fixture-registry = ["registry/*.toml"]

[operations.check]
description = "Run fixture checks"
exec = ["fixture-check"]
pool = "normal"
result = "exit"
cache = "tree+environment"

[operations.service]
description = "Run a fixture development service"
exec = ["fixture-service"]
pool = "normal"
result = "exit"
cache = "none"

[operations.parameterized]
description = "Run fixture checks with declared parameters"
exec = ["fixture-check"]
pool = "normal"
result = "json"
cache = "tree+environment"

[operations.parameterized.parameters.full]
type = "bool"
flag = "--full"

[operations.parameterized.parameters.package]
type = "string-list"
flag = "--package"
max_items = 4
max_length = 32

[operations.generic_extended_parameters]
description = "Exercise generic bounded operation parameter kinds"
exec = ["fixture-check"]
pool = "normal"
result = "exit"
cache = "tree+environment"

[operations.generic_extended_parameters.parameters.profile]
type = "enum"
flag = "--profile"
values = ["balanced", "strict"]

[operations.generic_extended_parameters.parameters.attempts]
type = "integer"
flag = "--attempts"
min = 1
max = 16

[operations.generic_extended_parameters.parameters.feature]
type = "string-list"
flag = "--features"
max_items = 4
max_length = 32
grammar = "safe-token"

[operations.generic_extended_parameters.parameters.package]
type = "enum-list"
flag = "--package"
values = ["sinexd", "xtask"]
max_items = 4

[operations.sinex_all_sources]
description = "Run Sinex's all-sources foreground operation"
exec = ["xtask", "run", "all-sources"]
pool = "normal"
result = "exit"
cache = "tree+environment"

[operations.sinex_all_sources.parameters.instance_id]
type = "string"
flag = "--instance-id"
max_length = 128
grammar = "safe-token"

[operations.sinex_all_sources.parameters.reconcile]
type = "bool"
flag = "--reconcile"

[operations.sinex_all_sources.parameters.service_name]
type = "string"
flag = "--service-name"
max_length = 128
grammar = "safe-token"

[operations.sinex_all_sources.parameters.include_default_excluded]
type = "bool"
flag = "--include-default-excluded"

[operations.verify_closure]
description = "Verify a fixture closure for one required bead"
exec = ["xtask", "verify", "closure"]
pool = "normal"
result = "exit"
cache = "tree+environment"

[operations.verify_closure.parameters.bead_id]
type = "string"
position = 1
required = true
max_length = 128
grammar = "safe-token"

[operations.verify_closure.parameters.json]
type = "bool"
flag = "--json"

[operations.verify_closure.parameters.dry_run]
type = "bool"
flag = "--dry-run"

[operations.pytest_receipt]
description = "Run fixture pytest receipt"
exec = ["fixture-pytest"]
pool = "normal"
result = "pytest"
cache = "tree+environment"
"""
    )
    initialize_git_checkout(root)


@pytest.mark.parametrize(
    "fragment",
    (
        "unknown = true\n",
        '[operations.parameterized.parameters.broken]\ntype = "integer"\nflag = "--broken"\nmin = 1\n',
        '[operations.parameterized.parameters.unbounded]\ntype = "string-list"\nflag = "--unbounded"\nmax_items = 4\n',
        '[operations.parameterized.parameters.unknown_string]\ntype = "string"\nflag = "--string"\nmax_length = 4\ngrammar = "shell"\n',
        '[operations.parameterized.parameters.boolean_integer]\ntype = "integer"\nflag = "--integer"\nmin = true\nmax = 4\n',
        '[operations.parameterized.parameters.empty_enum]\ntype = "enum"\nflag = "--enum"\nvalues = []\n',
        '[operations.parameterized.parameters.duplicate_enum]\ntype = "enum"\nflag = "--enum"\nvalues = ["same", "same"]\n',
        '[operations.parameterized.parameters.unbounded_enum_list]\ntype = "enum-list"\nflag = "--enum-list"\nvalues = ["one"]\n',
        '[operations.parameterized.parameters.duplicate_flag]\ntype = "string"\nflag = "--full"\nmax_length = 4\n',
        '[operations.verify_closure.parameters.ambiguous]\ntype = "string"\nflag = "--ambiguous"\nposition = 2\nrequired = true\nmax_length = 4\n',
        '[operations.verify_closure.parameters.optional]\ntype = "string"\nposition = 2\nrequired = false\nmax_length = 4\n',
        '[operations.verify_closure.parameters.duplicate_position]\ntype = "string"\nposition = 1\nrequired = true\nmax_length = 4\n',
        '[operations.verify_closure.parameters.gapped_position]\ntype = "string"\nposition = 3\nrequired = true\nmax_length = 4\n',
        '[operations.verify_closure.parameters.list_position]\ntype = "string-list"\nposition = 2\nrequired = true\nmax_items = 1\nmax_length = 4\n',
    ),
)
def test_project_operation_parameter_schema_is_closed_and_bounded(
    tmp_path: Path, fragment: str
) -> None:
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(descriptor.read_text() + fragment)

    with pytest.raises(ProjectConfigError):
        ProjectCatalog([tmp_path])


def test_project_operation_parameter_count_supports_broad_typed_clis(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    parameters = "".join(
        f'\n[operations.broad.parameters.option_{index}]\ntype = "bool"\nflag = "--option-{index}"\n'
        for index in range(17)
    )
    descriptor.write_text(
        descriptor.read_text()
        + '\n[operations.broad]\ndescription = "Expose a broad typed CLI"\nexec = ["fixture-check"]\npool = "normal"\nresult = "exit"\ncache = "none"\n'
        + parameters
    )

    project = ProjectCatalog([tmp_path]).get("fixture")

    assert len(project.operation("broad").parameters) == 17


def test_project_operation_parameter_count_remains_bounded(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    parameters = "".join(
        f'\n[operations.too_broad.parameters.option_{index}]\ntype = "bool"\nflag = "--option-{index}"\n'
        for index in range(33)
    )
    descriptor.write_text(
        descriptor.read_text()
        + '\n[operations.too_broad]\ndescription = "Exceed the typed CLI bound"\nexec = ["fixture-check"]\npool = "normal"\nresult = "exit"\ncache = "none"\n'
        + parameters
    )

    with pytest.raises(ProjectConfigError, match="must be a bounded table"):
        ProjectCatalog([tmp_path])


@pytest.mark.parametrize(
    "value",
    ("true", '"3600"', "0", "-1", str(MAX_DECLARED_OPERATION_TIMEOUT_SECONDS + 1)),
)
def test_declared_operation_timeout_must_be_a_positive_bounded_integer(
    tmp_path: Path, value: str
) -> None:
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'description = "Run fixture checks"\n',
            f'description = "Run fixture checks"\ntimeout_seconds = {value}\n',
        )
    )

    with pytest.raises(ProjectConfigError, match="operations.check.timeout_seconds"):
        ProjectCatalog([tmp_path])


def test_declared_operation_timeout_defaults_and_survives_launch_recovery(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'description = "Run fixture checks"\n',
            f'description = "Run fixture checks"\ntimeout_seconds = {MAX_DECLARED_OPERATION_TIMEOUT_SECONDS}\n',
        )
    )
    catalog = ProjectCatalog([tmp_path])
    check = catalog.get("fixture").operation("check")
    assert check.timeout_seconds == MAX_DECLARED_OPERATION_TIMEOUT_SECONDS
    assert (
        catalog.get("fixture").operation("parameterized").timeout_seconds
        == DEFAULT_TIMEOUT_SECONDS
    )
    assert (
        check.catalog_row()["timeout_seconds"] == MAX_DECLARED_OPERATION_TIMEOUT_SECONDS
    )

    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(catalog, jobs=jobs)
    response = service.dispatch(
        request(
            "job.start", "systemd-jobs", {"project_id": "fixture", "operation": "check"}
        )
    )
    assert response.ok and response.payload is not None
    launched = response.payload.inline
    assert launched["timeout_seconds"] == MAX_DECLARED_OPERATION_TIMEOUT_SECONDS

    record = jobs.store.load(launched["job_id"])
    assert record.spec.timeout_seconds == MAX_DECLARED_OPERATION_TIMEOUT_SECONDS
    recovered = GenericJobs(systemd, jobs.store, wait_poll_seconds=0.001)
    assert (
        recovered.get(launched["job_id"])["timeout_seconds"]
        == MAX_DECLARED_OPERATION_TIMEOUT_SECONDS
    )
    assert (
        GenericJobSpec(
            kind="foreground-command",
            command=("fixture",),
            working_directory=str(tmp_path),
            environment={},
        ).timeout_seconds
        == DEFAULT_TIMEOUT_SECONDS
    )


def test_concurrent_start_and_get_do_not_take_historical_terminal_locks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Live failure harness: concurrent client routes finish without waiting on terminal-record lock files."""
    write_adapter(tmp_path)
    store = GenericJobStore(tmp_path / "state")
    terminal_ids: set[str] = set()
    for _ in range(64):
        record = store.create(
            GenericJobSpec(
                kind="foreground-command",
                command=("fixture",),
                working_directory=str(tmp_path),
                environment={},
            )
        )
        terminal_ids.add(record.job_id)
        store.save(
            GenericJobs._with_state(
                record, {"phase": "failed", "terminal": True, "observed_at": "fixture"}
            )
        )
    active = store.create(
        GenericJobSpec(
            kind="foreground-command",
            command=("fixture",),
            working_directory=str(tmp_path),
            environment={},
        )
    )
    systemd = FakeSystemdJobs()
    jobs = GenericJobs(systemd, store, wait_poll_seconds=0.001)
    project = ProjectCatalog([tmp_path]).get("fixture")
    original_locked = store.locked
    original_list = store.list
    acquired: list[str] = []

    @contextmanager
    def counted_locked(job_id: str):
        acquired.append(job_id)
        with original_locked(job_id):
            yield

    monkeypatch.setattr(store, "locked", counted_locked)
    monkeypatch.setattr(
        store,
        "list",
        lambda: (_ for _ in ()).throw(
            AssertionError("start/get must not scan the terminal corpus")
        ),
    )
    started: list[dict[str, object]] = []
    failures: list[BaseException] = []

    def start_service() -> None:
        try:
            started.append(
                jobs.start_declared(
                    project=project,
                    operation=project.operation("service"),
                    correlation_id="concurrent",
                    parameters={},
                )
            )
        except BaseException as error:
            failures.append(error)

    start_thread = threading.Thread(target=start_service)
    get_thread = threading.Thread(target=lambda: jobs.get(active.job_id))
    start_thread.start()
    get_thread.start()
    start_thread.join(1)
    get_thread.join(1)

    assert not failures
    assert not start_thread.is_alive() and not get_thread.is_alive()
    assert started and started[0]["state"]["terminal"] is False
    assert not terminal_ids.intersection(acquired)
    monkeypatch.setattr(store, "list", original_list)


def test_declared_missing_unit_without_cancellation_evidence_stays_missing(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: a task pueue has forgotten is not inferred cancelled."""
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))

    started = service.dispatch(
        request(
            "job.start", "systemd-jobs", {"project_id": "fixture", "operation": "check"}
        )
    )
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    assert started.payload.inline["state"]["phase"] == "queued"

    task_id = fake_task_id(service.jobs, job_id)
    fake_pueue.remove([task_id])

    missing = service.dispatch(request("job.get", "systemd-jobs", {"job_id": job_id}))
    assert missing.ok and missing.payload is not None
    assert missing.payload.inline["state"]["phase"] == "missing"
    assert missing.payload.inline["state"]["terminal"]
    assert "launch_evidence" not in missing.payload.inline["state"]
    record = service.jobs.store.load(job_id)
    assert record.cancel_requested_at is None
    assert "cancellation" not in record.state

    result = service.dispatch(request("job.result", "systemd-jobs", {"job_id": job_id}))
    assert not result.ok
    assert result.error is not None
    assert result.error.code.value == "RESULT_INVALID"
    assert result.error.message == "job exit result is unavailable"


def test_typed_runner_keeps_the_one_hour_timeout_identity_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "SINNIXD_TIMEOUT_SECONDS", str(MAX_DECLARED_OPERATION_TIMEOUT_SECONDS)
    )

    with pytest.raises(RunnerError, match="typed-job timeout identity is invalid"):
        _require_environment(
            "00000000-0000-0000-0000-000000000001",
            "sinnixd-job-00000000-0000-0000-0000-000000000001.service",
            {
                "kind": "operator-shell",
                "principal": "operator",
                "checkout": {"project_id": "fixture", "checkout_id": "default"},
            },
        )


def test_project_operation_result_must_have_an_executable_declared_contract(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: descriptor result metadata cannot be accepted and ignored."""
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace('result = "json"', 'result = "agent"')
    )

    with pytest.raises(
        ProjectConfigError, match="operations.parameterized.result is invalid"
    ):
        ProjectCatalog([tmp_path])


@pytest.mark.parametrize(
    "fragment",
    [
        '\n[operations.parameterized.verdict]\nsuccess = ["same"]\nrefusal = ["same"]\n',
        '\n[operations.check.verdict]\nsuccess = ["OK"]\n',
        '\n[operations.parameterized.verdict]\nunknown = ["OK"]\n',
    ],
)
def test_project_operation_verdict_schema_rejects_overlap_unknown_or_non_json(
    tmp_path: Path, fragment: str
) -> None:
    """Anti-vacuity: verdict declarations must be bounded to one JSON category."""
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(descriptor.read_text() + fragment)

    with pytest.raises(ProjectConfigError, match="verdict"):
        ProjectCatalog([tmp_path])


def request(
    operation: str,
    owner: str,
    arguments: dict[str, object] | None = None,
    principal: str = "operator",
    *,
    idempotency_key: str | None = None,
) -> RequestEnvelope:
    return RequestEnvelope(
        request_id=str(uuid4()),
        correlation_id=str(uuid4()),
        operation=operation,
        owner=owner,
        principal=principal,
        arguments=arguments or {},
        idempotency_key=idempotency_key,
    )


@dataclass
class FakeSystemdJobs:
    """Fakes the timer surface UserSystemdJobs still owns; pueue owns jobs."""

    scheduled: list[dict[str, object]] = field(default_factory=list)
    timers: set[str] = field(default_factory=set)

    def schedule_timer(
        self, *, unit: str, on_calendar: str, command: tuple[str, ...]
    ) -> None:
        self.scheduled.append(
            {"unit": unit, "on_calendar": on_calendar, "command": command}
        )
        self.timers.add(unit)

    def timer_exists(self, unit: str) -> bool:
        return unit in self.timers

    def unschedule_timer(self, unit: str) -> None:
        self.timers.discard(unit)


def generic_jobs(tmp_path: Path, systemd: FakeSystemdJobs | None = None) -> GenericJobs:
    return GenericJobs(
        systemd or FakeSystemdJobs(),
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
    )


def fake_task_id(jobs: GenericJobs, job_id: str) -> int:
    record = jobs.store.load(job_id)
    assert record.queue_task_id is not None, f"job {job_id} never reached pueue"
    return record.queue_task_id


def queue_launch_input(jobs: GenericJobs, job_id: str) -> dict[str, object]:
    """The private queue_run launch input written for a job's current attempt."""
    path = jobs.store.inputs_root / f"{job_id}.queue-launch.json"
    return json.loads(path.read_text())


def initialize_git_checkout(root: Path) -> None:
    for arguments in (
        ("git", "init", "--quiet", str(root)),
        ("git", "-C", str(root), "add", "."),
        (
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--quiet",
            "--allow-empty",
            "-m",
            "fixture",
        ),
    ):
        subprocess.run(arguments, check=True)
    subprocess.run(
        ["git", "-C", str(root), "update-ref", "refs/remotes/origin/master", "HEAD"],
        check=True,
    )


def replace_worktree_gitfile_with_symlink(
    worktree: Path, target: Path | None = None
) -> Path:
    """Model the managed-worktree layout that Git refuses to remove directly."""
    gitfile = worktree / ".git"
    if target is None:
        content = gitfile.read_text().strip()
        assert content.startswith("gitdir: ")
        target = Path(content.removeprefix("gitdir: "))
    gitfile.unlink()
    gitfile.symlink_to(target)
    return target


def test_worktree_porcelain_parser_accepts_flags_and_rejects_unknown_shapes() -> None:
    parsed = parse_worktree_records(
        "worktree /repo\nHEAD "
        + "a" * 40
        + "\ndetached\nlocked operator reason\nprunable stale\n\n"
    )

    assert parsed == (
        {
            "worktree": "/repo",
            "HEAD": "a" * 40,
            "detached": "",
            "locked": "operator reason",
            "prunable": "stale",
        },
    )
    with pytest.raises(ProjectConfigError):
        parse_worktree_records("worktree /repo\nunknown value\n\n")


def native_runner(path: Path) -> None:
    path.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "last= prompt=\n"
        'if [ -n "${RUNNER_ARGS:-}" ]; then printf \'%s\\n\' "$@" > "$RUNNER_ARGS"; fi\n'
        "while [ $# -gt 0 ]; do\n"
        "  case $1 in --last-file) last=$2; shift 2 ;; --prompt-file) prompt=$2; shift 2 ;; *) shift ;; esac\n"
        "done\n"
        'test -f "$prompt"\n'
        'printf native-fixture-result > "$last"\n'
        "printf native-fixture-log\n"
    )
    path.chmod(0o700)


@dataclass
class FakeOwnerAdapters:
    response: ResponseEnvelope
    calls: list[dict[str, object]] = field(default_factory=list)

    def call(self, *, project, adapter, request) -> ResponseEnvelope:
        self.calls.append({"project": project, "adapter": adapter, "request": request})
        return self.response


@dataclass
class FakeExecution:
    result: ExecutionResult
    calls: list[tuple[tuple[str, ...], object]] = field(default_factory=list)

    def run(self, command, profile) -> ExecutionResult:
        self.calls.append((tuple(command), profile))
        return self.result


def isolate_job_scratch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SINNIXD_TMPFS_SCRATCH_ROOT", str(tmp_path / "tmpfs-scratch"))
    monkeypatch.setenv("SINNIXD_NVME_SCRATCH_ROOT", str(tmp_path / "nvme-scratch"))


def start_server(
    server: UnixSocketServer,
    *,
    once: bool = False,
    stop_event: threading.Event | None = None,
) -> threading.Thread:
    ready = threading.Event()
    server.ready_event = ready
    target = server.serve_once if once else server.serve_forever
    args = () if once or stop_event is None else (stop_event,)
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()
    assert ready.wait(1), "Unix socket server did not begin listening"
    return thread


def start_rpc_reply_server(
    socket_path: Path, reply: Callable[[dict[str, object]], dict[str, object]]
) -> threading.Thread:
    ready = threading.Event()

    def serve() -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(socket_path))
            listener.listen()
            ready.set()
            with listener.accept()[0] as connection:
                send_frame(connection, reply(receive_frame(connection)))

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert ready.wait(1), "JSON-RPC reply server did not begin listening"
    return thread


def test_project_catalog_is_explicit_and_operation_catalog_is_bounded(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]))

    response = service.dispatch(
        request("project.operations", "project-adapters", {"project_id": "fixture"})
    )

    assert response.ok
    assert response.payload is not None
    catalog = response.payload.inline
    assert catalog["project_id"] == "fixture"
    assert catalog["descriptor_status"] == {
        "loaded_digest": catalog["descriptor_status"]["on_disk_digest"],
        "on_disk_digest": catalog["descriptor_status"]["on_disk_digest"],
        "matches_loaded": True,
    }
    operations = {operation["name"]: operation for operation in catalog["operations"]}
    assert operations["check"]["parameters"] == []
    assert operations["check"]["result"] == "exit"
    assert operations["parameterized"]["parameters"] == [
        {"name": "full", "type": "bool", "flag": "--full"},
        {
            "name": "package",
            "type": "string-list",
            "flag": "--package",
            "max_items": 4,
            "max_length": 32,
            "grammar": "safe-token",
        },
    ]
    assert operations["generic_extended_parameters"]["parameters"] == [
        {
            "name": "profile",
            "type": "enum",
            "flag": "--profile",
            "values": ["balanced", "strict"],
            "max_length": 128,
            "grammar": "safe-token",
        },
        {
            "name": "attempts",
            "type": "integer",
            "flag": "--attempts",
            "min": 1,
            "max": 16,
        },
        {
            "name": "feature",
            "type": "string-list",
            "flag": "--features",
            "max_items": 4,
            "max_length": 32,
            "grammar": "safe-token",
        },
        {
            "name": "package",
            "type": "enum-list",
            "flag": "--package",
            "max_items": 4,
            "values": ["sinexd", "xtask"],
            "max_length": 128,
            "grammar": "safe-token",
        },
    ]
    assert operations["sinex_all_sources"]["parameters"] == [
        {
            "name": "instance_id",
            "type": "string",
            "flag": "--instance-id",
            "max_length": 128,
            "grammar": "safe-token",
        },
        {"name": "reconcile", "type": "bool", "flag": "--reconcile"},
        {
            "name": "service_name",
            "type": "string",
            "flag": "--service-name",
            "max_length": 128,
            "grammar": "safe-token",
        },
        {
            "name": "include_default_excluded",
            "type": "bool",
            "flag": "--include-default-excluded",
        },
    ]
    assert operations["verify_closure"]["parameters"] == [
        {
            "name": "bead_id",
            "type": "string",
            "position": 1,
            "required": True,
            "max_length": 128,
            "grammar": "safe-token",
        },
        {"name": "json", "type": "bool", "flag": "--json"},
        {"name": "dry_run", "type": "bool", "flag": "--dry-run"},
    ]
    assert operations["parameterized"]["result"] == "json"
    assert operations["pytest_receipt"]["result"] == "pytest"


def test_scheduled_operation_registers_restart_safe_timer_and_preserves_provenance(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            "[operations.check]\n", '[operations.check]\nschedule = "hourly"\n'
        )
    )
    systemd = FakeSystemdJobs()
    catalog = ProjectCatalog([tmp_path])
    state_root = tmp_path.parent / "scheduled-job-state"
    SinnixdService(
        catalog,
        jobs=GenericJobs(systemd, GenericJobStore(state_root), wait_poll_seconds=0.001),
    )

    assert len(systemd.scheduled) == 1
    timer = systemd.scheduled[0]
    assert timer["on_calendar"] == "hourly"
    assert timer["command"][-2:] == ("--schedule-id", "fixture:check")
    assert catalog.get("fixture").operation("check").schedule == "hourly"

    restarted = SinnixdService(
        catalog,
        jobs=GenericJobs(systemd, GenericJobStore(state_root), wait_poll_seconds=0.001),
    )
    assert len(systemd.scheduled) == 1

    response = restarted.dispatch(
        request(
            "job.fire",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "operation": "check",
                "schedule_id": "fixture:check",
            },
        )
    )
    assert response.ok
    record = GenericJobStore(state_root).load(response.payload.inline["job_id"])
    assert record.spec.dimensions == {
        "trigger": "systemd-timer",
        "schedule_id": "fixture:check",
        "schedule": "hourly",
        "timer_unit": f"{timer['unit']}.timer",
    }


def test_project_operations_reports_descriptor_drift(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]))
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(descriptor.read_text() + "\n# changed after daemon startup\n")

    response = service.dispatch(
        request("project.operations", "project-adapters", {"project_id": "fixture"})
    )

    assert response.ok
    assert response.payload is not None
    status = response.payload.inline["descriptor_status"]
    assert status["matches_loaded"] is False
    assert status["loaded_digest"].startswith("sha256:")
    assert status["on_disk_digest"].startswith("sha256:")
    assert status["loaded_digest"] != status["on_disk_digest"]


def test_owner_mismatch_is_a_typed_error(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]))

    response = service.dispatch(request("project.list", "wrong-owner"))

    assert not response.ok
    assert response.owner == "project-adapters"
    assert response.error is not None
    assert response.error.code.value == "AUTHORITY_MISMATCH"

    missing = service.dispatch(
        request("project.get", "project-adapters", {"project_id": "missing"})
    )

    assert not missing.ok
    assert missing.owner == "project-adapters"
    assert missing.error is not None
    assert missing.error.code.value == "INVALID_ARGUMENT"


def test_declared_and_foreground_jobs_share_the_generic_route(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: deleting GenericJobs.start makes both launch assertions fail."""
    write_adapter(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)

    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "check"},
        )
    )

    assert started.ok
    assert started.payload is not None
    launch = started.payload.inline
    assert launch["unit"].startswith("sinnixd-job-")
    assert launch["unit"].endswith(".service")
    assert launch["kind"] == "declared-operation"
    assert len(fake_pueue.added) == 1
    assert fake_pueue.added[0]["working_directory"] == Path(tmp_path.resolve())
    queue_launch = queue_launch_input(jobs, launch["job_id"])
    assert queue_launch["timeout_seconds"] == DEFAULT_TIMEOUT_SECONDS
    assert queue_launch["environment"]["SINNIXD_JOB_ID"] == launch["job_id"]
    assert queue_launch["environment"]["SINNIXD_OPERATION"] == "check"
    assert queue_launch["environment"]["SINNIXD_CHECKOUT_ID"] == "default"
    assert (
        queue_launch["environment"]["SINNIXD_CHECKOUT_HEAD"]
        == launch["checkout"]["head"]
    )
    assert launch["checkout"]["path"] == str(tmp_path.resolve())

    foreground = service.start_foreground(
        command=("fixture-foreground",),
        working_directory=str(tmp_path),
        environment={"EMPTY": ""},
        timeout_seconds=123,
    )
    assert foreground["kind"] == "foreground-command"
    assert len(fake_pueue.added) == 2
    assert service.jobs.store.declared_launch(launch["job_id"])[0] == (
        "fixture-env",
        "--command",
        "fixture-check",
    )
    assert queue_launch_input(jobs, foreground["job_id"])["argv"] == [
        "fixture-foreground"
    ]
    foreground_record = service.jobs.store.load(foreground["job_id"])
    assert foreground_record.spec.to_dict()["environment_keys"] == [
        "EMPTY",
        "SINNIXD_JOB_ID",
    ]

    status = service.dispatch(
        request("job.get", "systemd-jobs", {"job_id": launch["job_id"]})
    )
    cancelled = service.dispatch(
        request("job.cancel", "systemd-jobs", {"job_id": launch["job_id"]})
    )

    assert status.ok
    assert status.payload is not None
    assert status.payload.inline["state"]["phase"] == "running"
    assert cancelled.ok
    assert cancelled.payload is not None
    assert cancelled.payload.inline["state"]["phase"] == "cancelled"
    assert fake_task_id(jobs, launch["job_id"]) in fake_pueue.killed


def test_declared_operation_timeout_contract_reaches_the_queued_command(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: a descriptor timeout must reach the wrapper that enforces it."""
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        + """
[operations.long_running]
description = "Run a bounded long fixture operation"
exec = ["fixture-long"]
pool = "bulk"
result = "exit"
cache = "none"
timeout_seconds = 7200
"""
    )
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)

    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "long_running"},
        )
    )

    assert started.ok and started.payload is not None
    assert started.payload.inline["timeout_seconds"] == 7200
    job_id = started.payload.inline["job_id"]
    assert service.jobs.store.declared_launch(job_id)[0] == (
        "fixture-env",
        "--command",
        "fixture-long",
    )
    assert queue_launch_input(jobs, job_id)["timeout_seconds"] == 7200


def test_declared_parameters_canonicalize_argv_and_persist_only_the_digest(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: parameter ordering must affect neither argv identity nor durable record contents."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)

    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "operation": "parameterized",
                "parameters": {"package": ["xtask", "sinexd", "xtask"], "full": True},
            },
        )
    )

    assert started.ok and started.payload is not None
    launch = started.payload.inline
    digest = hashlib.sha256(b'{"full":true,"package":["sinexd","xtask"]}').hexdigest()
    assert jobs.store.declared_launch(launch["job_id"])[0] == (
        "fixture-env",
        "--command",
        "fixture-check",
        "--full",
        "--package",
        "sinexd",
        "--package",
        "xtask",
    )
    assert launch["parameters"] == {"digest": digest}
    persisted = (jobs.store.records_root / f"{launch['job_id']}.json").read_text()
    assert '"parameters": {"digest": ' in persisted
    assert "sinexd" not in persisted and "xtask" not in persisted
    assert jobs.store.load(launch["job_id"]).spec.parameter_digest == digest


@pytest.mark.parametrize(
    "parameters",
    (
        {"unknown": True},
        {"full": "true"},
        {"package": []},
        {"package": ["--full"]},
        {"package": ["one", "two", "three", "four", "five"]},
    ),
)
def test_declared_parameters_reject_unknown_malformed_and_unbounded_input(
    tmp_path: Path, parameters: dict[str, object], fake_pueue: FakePueue
) -> None:
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    service = SinnixdService(
        ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd)
    )

    response = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "operation": "parameterized",
                "parameters": parameters,
            },
        )
    )

    assert response.error is not None
    assert response.error.code.value == "INVALID_ARGUMENT"
    assert fake_pueue.added == []


@pytest.mark.parametrize(
    "parameters",
    (
        {"profile": "unknown"},
        {"attempts": True},
        {"attempts": 0},
        {"attempts": 17},
        {"feature": ["--release"]},
        {"package": ["sinexd", "unknown"]},
        {"package": []},
    ),
)
def test_generic_extended_parameters_reject_invalid_values_before_launch(
    tmp_path: Path, parameters: dict[str, object], fake_pueue: FakePueue
) -> None:
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    service = SinnixdService(
        ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd)
    )

    response = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "operation": "generic_extended_parameters",
                "parameters": parameters,
            },
        )
    )

    assert response.error is not None
    assert response.error.code.value == "INVALID_ARGUMENT"
    assert fake_pueue.added == []


def test_generic_extended_parameters_derive_canonical_argv_and_digest(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)

    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "operation": "generic_extended_parameters",
                "parameters": {
                    "package": ["xtask", "sinexd", "xtask"],
                    "feature": ["serde", "tokio", "serde"],
                    "attempts": 4,
                    "profile": "strict",
                },
            },
        )
    )

    assert started.ok and started.payload is not None
    expected_canonical = {
        "attempts": 4,
        "feature": ["serde", "tokio"],
        "package": ["sinexd", "xtask"],
        "profile": "strict",
    }
    assert jobs.store.declared_launch(started.payload.inline["job_id"])[0] == (
        "fixture-env",
        "--command",
        "fixture-check",
        "--profile",
        "strict",
        "--attempts",
        "4",
        "--features",
        "serde",
        "--features",
        "tokio",
        "--package",
        "sinexd",
        "--package",
        "xtask",
    )
    assert started.payload.inline["parameters"] == {
        "digest": hashlib.sha256(
            json.dumps(
                expected_canonical,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode()
        ).hexdigest()
    }


@pytest.mark.parametrize(
    "parameters",
    (
        {"instance_id": "../escape"},
        {"instance_id": "x" * 129},
        {"reconcile": "true"},
        {"service_name": "/tmp/source"},
        {"include_default_excluded": 1},
    ),
)
def test_sinex_all_sources_fixture_rejects_invalid_values_before_launch(
    tmp_path: Path, parameters: dict[str, object], fake_pueue: FakePueue
) -> None:
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    service = SinnixdService(
        ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd)
    )

    response = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "operation": "sinex_all_sources",
                "parameters": parameters,
            },
        )
    )

    assert response.error is not None
    assert response.error.code.value == "INVALID_ARGUMENT"
    assert fake_pueue.added == []


def test_sinex_all_sources_fixture_derives_exact_argv_and_digest(
    tmp_path: Path,
) -> None:
    """The fixture follows xtask run all-sources' current foreground flags."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)

    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "operation": "sinex_all_sources",
                "parameters": {
                    "instance_id": "operator-source-driver-browser.history-3",
                    "reconcile": True,
                    "service_name": "source-driver-browser.history-3",
                    "include_default_excluded": True,
                },
            },
        )
    )

    assert started.ok and started.payload is not None
    expected_canonical = {
        "include_default_excluded": True,
        "instance_id": "operator-source-driver-browser.history-3",
        "reconcile": True,
        "service_name": "source-driver-browser.history-3",
    }
    assert jobs.store.declared_launch(started.payload.inline["job_id"])[0] == (
        "fixture-env",
        "--command",
        "xtask",
        "run",
        "all-sources",
        "--instance-id",
        "operator-source-driver-browser.history-3",
        "--reconcile",
        "--service-name",
        "source-driver-browser.history-3",
        "--include-default-excluded",
    )
    assert started.payload.inline["parameters"] == {
        "digest": hashlib.sha256(
            json.dumps(
                expected_canonical,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode()
        ).hexdigest()
    }


def test_required_positional_parameter_derives_before_optional_flags_and_contributes_to_digest(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: a typed bead ID must occupy argv position one, never a synthetic flag."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)

    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "operation": "verify_closure",
                "parameters": {"bead_id": "sinex-a1b2", "json": True, "dry_run": True},
            },
        )
    )

    assert started.ok and started.payload is not None
    assert jobs.store.declared_launch(started.payload.inline["job_id"])[0] == (
        "fixture-env",
        "--command",
        "xtask",
        "verify",
        "closure",
        "sinex-a1b2",
        "--json",
        "--dry-run",
    )
    assert started.payload.inline["parameters"] == {
        "digest": hashlib.sha256(
            b'{"bead_id":"sinex-a1b2","dry_run":true,"json":true}'
        ).hexdigest()
    }


@pytest.mark.parametrize(
    "parameters",
    (
        {},
        {"bead_id": "x" * 129},
        {"bead_id": "../unsafe"},
    ),
)
def test_required_positional_parameter_rejects_missing_or_invalid_values_before_launch(
    tmp_path: Path, parameters: dict[str, object], fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: rejected required positionals must not create a systemd job."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    service = SinnixdService(
        ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd)
    )

    response = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "operation": "verify_closure",
                "parameters": parameters,
            },
        )
    )

    assert response.error is not None
    assert response.error.code.value == "INVALID_ARGUMENT"
    assert fake_pueue.added == []


def test_fixed_operation_rejects_parameters_and_retains_its_declared_argv(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: parameters must not create an argv authority for fixed operations."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    service = SinnixdService(
        ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd)
    )

    fixed = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "check", "parameters": {}},
        )
    )
    rejected = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "operation": "check",
                "parameters": {"full": True},
            },
        )
    )

    assert fixed.ok and fixed.payload is not None
    assert service.jobs.store.declared_launch(fixed.payload.inline["job_id"])[0] == (
        "fixture-env",
        "--command",
        "fixture-check",
    )
    assert rejected.error is not None
    assert rejected.error.code.value == "INVALID_ARGUMENT"
    assert len(fake_pueue.added) == 1


@pytest.mark.parametrize(
    ("operation", "content", "overflowed", "expected"),
    (
        ("parameterized", b'{"receipt":"ok"}', False, {"receipt": "ok"}),
        ("pytest_receipt", b'{"receipt":"pytest"}', False, {"receipt": "pytest"}),
        ("parameterized", b'{"receipt":"ok"}injected', False, None),
        ("parameterized", b"not-json", False, None),
        ("parameterized", b'{"receipt":"too-large"}', True, None),
    ),
)
def test_declared_json_results_are_bounded_and_validated(
    tmp_path: Path,
    operation: str,
    content: bytes,
    overflowed: bool,
    expected: dict[str, str] | None,
) -> None:
    """Anti-vacuity: result artifacts must reject injected, malformed, and overflowed JSON."""
    write_adapter(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": operation},
        )
    )
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    record = jobs.store.load(job_id)
    assert record.result_path is not None
    record.result_path.write_bytes(content)
    if overflowed:
        record.result_path.with_suffix(".overflow").touch()

    if expected is not None:
        kind = "json" if operation == "parameterized" else "pytest"
        assert jobs.result(job_id) == {
            "job_id": job_id,
            "kind": kind,
            "value": expected,
            "artifact": {
                "ref": f"sinnix://jobs/{job_id}/artifacts/result",
                "max_bytes": 64_000,
                "kind": kind,
            },
        }
    else:
        with pytest.raises(JobResultError):
            jobs.result(job_id)
        response = service.dispatch(
            request("job.result", "systemd-jobs", {"job_id": job_id})
        )
        assert response.error is not None
        assert response.error.code.value == "RESULT_INVALID"


def test_declared_json_result_respects_the_callers_response_budget(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: typed JSON must not bypass job.result's max_bytes contract."""
    write_adapter(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "parameterized"},
        )
    )
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    record = jobs.store.load(job_id)
    assert record.result_path is not None
    record.result_path.write_bytes(b'{"receipt":"ok"}')

    with pytest.raises(JobResultLimitError, match="requested response limit"):
        jobs.result(job_id, max_bytes=8)
    response = service.dispatch(
        request("job.result", "systemd-jobs", {"job_id": job_id, "max_bytes": 8})
    )
    assert response.error is not None
    assert response.error.code.value == "RESOURCE_EXHAUSTED"


def test_job_reconciliation_marks_missing_units_without_daemon_owned_state(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: deleting GenericJobs.get's pueue observation loses the missing phase."""
    write_adapter(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)

    started = service.dispatch(
        request(
            "job.start", "systemd-jobs", {"project_id": "fixture", "operation": "check"}
        )
    )
    assert started.payload is not None
    job_id = started.payload.inline["job_id"]
    fake_pueue.remove([fake_task_id(jobs, job_id)])

    response = service.dispatch(request("job.get", "systemd-jobs", {"job_id": job_id}))

    assert response.ok
    assert response.payload is not None
    assert response.payload.inline["state"]["phase"] == "missing"
    assert response.payload.inline["state"]["terminal"]


def test_declared_project_job_rejects_arbitrary_execution(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))

    wrong_owner = service.dispatch(
        request(
            "job.start",
            "wrong-owner",
            {"project_id": "fixture", "operation": "check"},
        )
    )
    unknown_operation = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "shell"},
        )
    )
    direct_argv = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "check", "argv": ["id"]},
        )
    )

    assert wrong_owner.error is not None
    assert wrong_owner.error.code.value == "AUTHORITY_MISMATCH"
    assert wrong_owner.owner == "systemd-jobs"
    assert unknown_operation.error is not None
    assert unknown_operation.error.code.value == "INVALID_ARGUMENT"
    assert direct_argv.error is not None
    assert direct_argv.error.code.value == "INVALID_ARGUMENT"


def test_workspace_create_is_git_derived_durable_and_restart_safe(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: create must reach Git worktree authority and survive service restart."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)

    created = service.dispatch(
        request(
            "workspace.create",
            "git-workspaces",
            {
                "project_id": "fixture",
                "name": "fixture-lane",
                "branch": "feature/fixture-lane",
                "base": "HEAD",
            },
            "agent-control",
        )
    )

    assert created.ok and created.payload is not None
    workspace = created.payload.inline
    assert workspace["state"] == "available"
    assert workspace["current_branch"] == "feature/fixture-lane"
    assert workspace["identity_matches"]

    assert Path(workspace["path"]).is_dir()
    porcelain = subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "list", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert f"worktree {workspace['path']}" in porcelain

    restarted = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    recovered = restarted.dispatch(
        request(
            "workspace.get",
            "git-workspaces",
            {"workspace_id": workspace["workspace_id"]},
        )
    )
    assert recovered.ok and recovered.payload is not None
    assert recovered.payload.inline["head"] == workspace["head"]
    assert recovered.payload.inline["checkout_id"].startswith("worktree-")


def test_rapid_sequential_workspace_creates_leave_no_collision_orphans(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))

    created = [
        service.workspaces.create(
            project_id="fixture",
            name=f"rapid-{index}",
            branch=f"feature/rapid-{index}",
            base="HEAD",
        )
        for index in range(6)
    ]

    assert len(created) == 6
    assert len(service.workspaces.store.records()) == 6
    assert all(Path(item["path"]).is_dir() for item in created)
    assert not list((tmp_path / "worktrees").glob(".rapid-*"))


def test_workspace_create_refuses_a_registered_name_or_branch_without_replacing_it(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: a second create on a live lane's name must not adopt or delete it."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    workspace = service.workspaces.create(
        project_id="fixture",
        name="live-packet",
        branch="feature/live-packet",
        base="HEAD",
    )

    for name, branch in (
        ("live-packet", "feature/other-branch"),
        ("other-name", "feature/live-packet"),
    ):
        response = service.dispatch(
            request(
                "workspace.create",
                "git-workspaces",
                {
                    "project_id": "fixture",
                    "name": name,
                    "branch": branch,
                    "base": None,
                },
                "agent-control",
            )
        )
        assert response.error is not None
        assert response.error.code.value == "INVALID_ARGUMENT"
        assert "already exists" in response.error.message

    records = service.workspaces.store.records()
    assert [record.workspace_id for record in records] == [workspace["workspace_id"]]
    assert Path(workspace["path"]).is_dir()


def test_workspace_mutations_reject_weak_principals_paths_refs_and_duplicates(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    arguments = {
        "project_id": "fixture",
        "name": "safe-lane",
        "branch": "feature/safe-lane",
        "base": "HEAD",
    }

    weak = service.dispatch(
        request("workspace.create", "git-workspaces", arguments, "observer")
    )
    escaped = service.dispatch(
        request(
            "workspace.create",
            "git-workspaces",
            {**arguments, "name": "../escape"},
            "agent-control",
        )
    )
    invalid_ref = service.dispatch(
        request(
            "workspace.create",
            "git-workspaces",
            {**arguments, "base": "missing-ref"},
            "agent-control",
        )
    )
    created = service.dispatch(
        request("workspace.create", "git-workspaces", arguments, "agent-control")
    )
    duplicate = service.dispatch(
        request("workspace.create", "git-workspaces", arguments, "agent-control")
    )
    adopt_root = service.dispatch(
        request(
            "workspace.adopt",
            "git-workspaces",
            {"project_id": "fixture", "checkout_id": "default", "name": "root"},
            "operator",
        )
    )

    assert created.ok
    for response in (weak, escaped, invalid_ref, duplicate, adopt_root):
        assert response.error is not None
        assert response.error.code.value == "INVALID_ARGUMENT"


def test_workspace_status_exposes_branch_drift_and_dirty_state(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    created = service.workspaces.create(
        project_id="fixture",
        name="drift-lane",
        branch="feature/drift-lane",
        base="HEAD",
    )
    path = Path(created["path"])
    (path / "untracked.txt").write_text("operator work\n")
    subprocess.run(
        ["git", "-C", str(path), "switch", "--detach"], check=True, capture_output=True
    )

    observed = service.workspaces.get(created["workspace_id"])

    assert observed["state"] == "missing"
    assert observed["dirty"] is None
    assert not observed["identity_matches"]


def test_workspace_drop_gcs_missing_records_with_audit_notes(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    first = service.workspaces.create(
        project_id="fixture",
        name="dead-first",
        branch="feature/dead-first",
        base="HEAD",
    )
    second = service.workspaces.create(
        project_id="fixture",
        name="dead-second",
        branch="feature/dead-second",
        base="HEAD",
    )
    for workspace in (first, second):
        subprocess.run(
            ["git", "-C", str(tmp_path), "worktree", "remove", workspace["path"]],
            check=True,
            capture_output=True,
        )

    dropped = [
        service.workspaces.drop(first["workspace_id"]),
        service.workspaces.drop(second["workspace_id"], force=True),
    ]

    assert dropped == [
        {
            "workspace_id": first["workspace_id"],
            "dropped": True,
            "relationship_only": True,
            "state": "missing",
            "note": "workspace-missing-worktree-gc",
        },
        {
            "workspace_id": second["workspace_id"],
            "dropped": True,
            "relationship_only": True,
            "state": "missing",
            "note": "workspace-missing-worktree-gc",
        },
    ]
    notes = [
        json.loads(line)
        for line in service.workspaces.store.disposals.read_text().splitlines()
    ]
    assert [note["kind"] for note in notes] == [
        "workspace-missing-worktree-gc",
        "workspace-missing-worktree-gc",
    ]
    assert service.workspaces.store.records() == ()


def test_workspace_list_returns_mixed_records_without_git_revalidation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    live = service.workspaces.create(
        project_id="fixture",
        name="list-live",
        branch="feature/list-live",
        base="HEAD",
    )
    dead = service.workspaces.create(
        project_id="fixture",
        name="list-dead",
        branch="feature/list-dead",
        base="HEAD",
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "remove", dead["path"]],
        check=True,
        capture_output=True,
    )
    invalid_path = tmp_path / "not-a-worktree-directory"
    invalid_path.write_text("invalid workspace target\n")
    invalid = WorkspaceRecord(
        workspace_id="invalid-workspace",
        project_id="fixture",
        name="invalid-workspace",
        path=invalid_path,
        branch="feature/invalid-workspace",
        base="HEAD",
        created_at="2026-08-26T00:00:00+00:00",
    )
    service.workspaces.store.put(invalid)

    def no_git_revalidation(_project_id: str):
        raise AssertionError("workspace.list must not inspect Git worktrees")

    monkeypatch.setattr(service.projects, "checkouts", no_git_revalidation)
    listed = service.workspaces.list("fixture")
    rows = {row["workspace_id"]: row for row in listed["workspaces"]}

    assert rows[live["workspace_id"]]["state"] == "available"
    assert rows[live["workspace_id"]]["identity_matches"] is None
    assert rows[dead["workspace_id"]]["state"] == "missing"
    assert rows[dead["workspace_id"]]["identity_matches"] is None
    assert rows[dead["workspace_id"]]["head"] is None
    assert rows[invalid.workspace_id]["state"] == "invalid"
    assert rows[invalid.workspace_id]["identity_matches"] is None
    assert {record.workspace_id for record in service.workspaces.store.records()} == {
        live["workspace_id"],
        invalid.workspace_id,
    }


def test_workspace_list_gc_scales_with_many_dead_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    records = [
        WorkspaceRecord(
            workspace_id=f"dead-{index}",
            project_id="fixture",
            name=f"dead-{index}",
            path=tmp_path / "missing-worktrees" / str(index),
            branch=f"feature/dead-{index}",
            base="HEAD",
            created_at="2026-08-26T00:00:00+00:00",
        )
        for index in range(1000)
    ]
    service.workspaces.store.index.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    service.workspaces.store.index.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "workspaces": [record.to_dict() for record in records],
            }
        )
    )
    monkeypatch.setattr(
        service.projects,
        "checkouts",
        lambda _project_id: (_ for _ in ()).throw(
            AssertionError("dead records must not invoke Git")
        ),
    )

    started = time.monotonic()
    listed = service.workspaces.list("fixture")
    elapsed = time.monotonic() - started

    assert len(listed["workspaces"]) == len(records)
    assert {row["state"] for row in listed["workspaces"]} == {"missing"}
    assert service.workspaces.store.records() == ()
    assert elapsed < 1.0


def test_workspace_drop_deletes_a_clean_no_pr_branch_without_checkpoint_content(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: a drop must remove both Git objects, not just the workspace record."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    workspace = service.workspaces.create(
        project_id="fixture",
        name="verification-lane",
        branch="feature/verification-lane",
        base="HEAD",
    )
    checkpoint = service.workspaces.checkpoint(workspace["workspace_id"])
    gitdir = replace_worktree_gitfile_with_symlink(Path(workspace["path"]))
    assert gitdir.is_dir()

    disposed = service.dispatch(
        request(
            "workspace.drop",
            "git-workspaces",
            {"workspace_id": workspace["workspace_id"]},
            "operator",
        )
    )

    assert disposed.ok and disposed.payload is not None
    assert disposed.payload.inline["dropped"]
    assert disposed.payload.inline["deleted_branch"] == workspace["branch"]
    assert not Path(workspace["path"]).exists()
    assert not (
        service.workspaces.store.checkpoints_root
        / workspace["workspace_id"]
        / checkpoint["checkpoint_id"]
    ).exists()
    assert service.workspaces.list("fixture") == {"workspaces": []}


def test_workspace_gitfile_symlink_rejects_mismatched_and_outside_targets_without_mutation(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: only the exact registered administrative gitdir may be canonicalized."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    first = service.workspaces.create(
        project_id="fixture",
        name="symlink-first",
        branch="feature/symlink-first",
        base="HEAD",
    )
    second = service.workspaces.create(
        project_id="fixture",
        name="symlink-second",
        branch="feature/symlink-second",
        base="HEAD",
    )
    first_path = Path(first["path"])
    first_checkout = next(
        item
        for item in service.projects.checkouts("fixture")
        if item.path == first_path
    )
    second_gitdir = Path(
        (Path(second["path"]) / ".git").read_text().strip().removeprefix("gitdir: ")
    )
    first_gitfile = first_path / ".git"
    first_gitfile.unlink()
    first_gitfile.symlink_to(second_gitdir)

    with pytest.raises(
        WorkspaceError, match="does not match its registered worktree gitdir"
    ):
        service.workspaces._canonicalize_gitfile_symlink(first_checkout)
    assert first_gitfile.is_symlink()
    assert first_gitfile.resolve(strict=True) == second_gitdir

    outside = tmp_path / "outside-gitdir"
    outside.mkdir()
    first_gitfile.unlink()
    first_gitfile.symlink_to(outside)

    with pytest.raises(WorkspaceError, match="outside the repository worktrees area"):
        service.workspaces._canonicalize_gitfile_symlink(first_checkout)
    assert first_gitfile.is_symlink()
    assert first_gitfile.resolve(strict=True) == outside
    assert first_path.is_dir()
    assert Path(second["path"]).is_dir()


def test_workspace_drop_refuses_dirty_divergent_unpublished_and_checkpoint_only_content(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: each rejection leaves the managed worktree and branch available for recovery."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    dirty = service.workspaces.create(
        project_id="fixture",
        name="dispose-dirty",
        branch="feature/dispose-dirty",
        base="HEAD",
    )
    (Path(dirty["path"]) / "operator.txt").write_text("preserve\n")
    divergent = service.workspaces.create(
        project_id="fixture",
        name="dispose-divergent",
        branch="feature/dispose-divergent",
        base="HEAD",
    )
    subprocess.run(
        ["git", "-C", divergent["path"], "switch", "-c", "feature/dispose-replaced"],
        check=True,
    )
    unpublished = service.workspaces.create(
        project_id="fixture",
        name="dispose-unpublished",
        branch="feature/dispose-unpublished",
        base="HEAD",
    )
    unpublished_path = Path(unpublished["path"])
    (unpublished_path / "unpublished.txt").write_text("preserve\n")
    subprocess.run(
        ["git", "-C", str(unpublished_path), "add", "unpublished.txt"], check=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(unpublished_path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--quiet",
            "-m",
            "unpublished",
        ],
        check=True,
    )
    checkpoint_only = service.workspaces.create(
        project_id="fixture",
        name="dispose-checkpoint",
        branch="feature/dispose-checkpoint",
        base="HEAD",
    )
    checkpoint_path = Path(checkpoint_only["path"])
    (checkpoint_path / "recoverable.txt").write_text("preserve\n")
    service.workspaces.checkpoint(checkpoint_only["workspace_id"])
    (checkpoint_path / "recoverable.txt").unlink()

    for workspace in (dirty, divergent, unpublished, checkpoint_only):
        with pytest.raises(ValueError):
            service.workspaces.drop(workspace["workspace_id"])
        assert Path(workspace["path"]).is_dir()
        assert (
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(tmp_path),
                    "show-ref",
                    "--verify",
                    "--quiet",
                    f"refs/heads/{workspace['branch']}",
                ]
            ).returncode
            == 0
        )


def test_workspace_checkpoint_restore_round_trips_index_worktree_and_untracked_state(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: dropping any artifact loses one of the three asserted Git states."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    created = service.workspaces.create(
        project_id="fixture",
        name="checkpoint-lane",
        branch="feature/checkpoint-lane",
        base="HEAD",
    )
    path = Path(created["path"])
    (path / "flake.nix").write_text('{"staged": true}\n')
    subprocess.run(["git", "-C", str(path), "add", "flake.nix"], check=True)
    with (path / "flake.nix").open("a") as handle:
        handle.write("unstaged\n")
    (path / "untracked.txt").write_text("untracked payload\n")

    checkpoint = service.workspaces.checkpoint(created["workspace_id"])
    subprocess.run(
        ["git", "-C", str(path), "reset", "--hard", "HEAD"],
        check=True,
        capture_output=True,
    )
    (path / "untracked.txt").unlink()
    restored = service.workspaces.restore(
        created["workspace_id"], checkpoint["checkpoint_id"]
    )

    assert restored["restored"]
    assert (path / "flake.nix").read_text() == '{"staged": true}\nunstaged\n'
    assert (path / "untracked.txt").read_text() == "untracked payload\n"
    assert (
        "staged"
        in subprocess.run(
            ["git", "-C", str(path), "diff", "--cached"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    assert (
        "unstaged"
        in subprocess.run(
            ["git", "-C", str(path), "diff"], check=True, capture_output=True, text=True
        ).stdout
    )


def test_workspace_restore_rejects_dirty_or_stale_head_targets(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    created = service.workspaces.create(
        project_id="fixture",
        name="restore-guards",
        branch="feature/restore-guards",
        base="HEAD",
    )
    path = Path(created["path"])
    (path / "untracked.txt").write_text("checkpoint\n")
    checkpoint = service.workspaces.checkpoint(created["workspace_id"])

    with pytest.raises(ValueError, match="clean workspace"):
        service.workspaces.restore(created["workspace_id"], checkpoint["checkpoint_id"])

    (path / "untracked.txt").unlink()
    (path / "advance.txt").write_text("advance\n")
    subprocess.run(["git", "-C", str(path), "add", "advance.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--quiet",
            "-m",
            "advance",
        ],
        check=True,
    )
    with pytest.raises(ValueError, match="source HEAD"):
        service.workspaces.restore(created["workspace_id"], checkpoint["checkpoint_id"])


def test_workspace_restore_recreates_a_missing_worktree_at_the_checkpoint_head(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    created = service.workspaces.create(
        project_id="fixture",
        name="recover-lane",
        branch="feature/recover-lane",
        base="HEAD",
    )
    path = Path(created["path"])
    (path / "flake.nix").write_text('{"recovered": true}\n')
    subprocess.run(["git", "-C", str(path), "add", "flake.nix"], check=True)
    (path / "untracked.txt").write_text("preserved\n")
    checkpoint = service.workspaces.checkpoint(created["workspace_id"])
    subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "remove", "--force", str(path)],
        check=True,
    )

    recovered = service.workspaces.restore(
        created["workspace_id"], checkpoint["checkpoint_id"], recreate=True
    )

    assert recovered["recreated"] and recovered["path"] == str(path)
    assert (path / "flake.nix").read_text() == '{"recovered": true}\n'
    assert (path / "untracked.txt").read_text() == "preserved\n"
    assert (
        "recovered"
        in subprocess.run(
            ["git", "-C", str(path), "diff", "--cached"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )


def test_dropping_a_workspace_deletes_its_jobs_records_and_artifacts(
    tmp_path: Path,
) -> None:
    """A job record lives exactly as long as the checkout it ran in.

    Anti-vacuity: without the ownership deletion in workspace.drop the record
    and its log survive the worktree that owns them, and nothing else ever
    removes them.
    """
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    workspace = service.workspaces.create(
        project_id="fixture",
        name="owned-lane",
        branch="feature/owned-lane",
        base="HEAD",
    )
    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "operation": "check",
                "workspace_id": "owned-lane",
            },
        )
    )
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    record = jobs.store.load(job_id)
    record.log_path.write_text("lane output\n")
    other = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )

    dropped = service.dispatch(
        request(
            "workspace.drop",
            "git-workspaces",
            {"workspace_id": workspace["workspace_id"], "force": True},
            "operator",
        )
    )

    assert dropped.ok and dropped.payload is not None
    assert dropped.payload.inline["deleted_job_records"] == 1
    assert not (jobs.store.records_root / f"{job_id}.json").exists()
    assert not record.log_path.exists()
    assert (jobs.store.records_root / f"{other['job_id']}.json").exists()


def test_an_ad_hoc_rerun_supersedes_its_predecessor_but_never_a_plan_sibling(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Supersession follows ownership, not just the operation name.

    Anti-vacuity, both directions: dropping the plan-contract exemption makes
    node "b" delete its sibling node "a" (they share operation and checkout);
    dropping the supersession makes the second ad-hoc `check` leave the first
    one's record and log behind, which is what nothing else deletes.
    """
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    adapter = ProjectCatalog([tmp_path]).get("fixture")

    def finish(job_id: str) -> str:
        fake_pueue.succeed(fake_task_id(jobs, job_id))
        assert jobs.get(job_id)["state"]["terminal"]
        return job_id

    def ad_hoc() -> str:
        return finish(
            jobs.start_declared(
                project=adapter,
                operation=adapter.operation("check"),
                correlation_id="ad-hoc",
                parameters={},
                checkout=service.projects.checkout("fixture", "default"),
            )["job_id"]
        )

    def plan_node(node_id: str) -> str:
        return finish(
            jobs.start_declared(
                project=adapter,
                operation=adapter.operation("check"),
                correlation_id="plan",
                parameters={},
                checkout=service.projects.checkout("fixture", "default"),
                contract={"plan": {"plan_id": "plan-1", "node_id": node_id}},
            )["job_id"]
        )

    first_node = plan_node("a")
    second_node = plan_node("b")
    first_ad_hoc = ad_hoc()
    log = jobs.store.load(first_ad_hoc).log_path
    log.write_text("first ad-hoc run\n")
    second_ad_hoc = ad_hoc()

    # A plan owns its nodes: neither sibling deletes the other, and an ad-hoc
    # run of the same operation does not delete them either.
    assert (jobs.store.records_root / f"{first_node}.json").exists()
    assert (jobs.store.records_root / f"{second_node}.json").exists()
    # An ad-hoc rerun is the same question re-asked, and answers it.
    assert not (jobs.store.records_root / f"{first_ad_hoc}.json").exists()
    assert not log.exists()
    assert (jobs.store.records_root / f"{second_ad_hoc}.json").exists()


def test_a_scheduled_runs_superseded_predecessor_is_deleted_with_its_artifacts(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """The previous answer to a recurring question has no reader left.

    Anti-vacuity: without the supersession deletion every timer firing keeps
    its record and log forever, which is what filled the state root.
    """
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            "[operations.check]\n", '[operations.check]\nschedule = "hourly"\n'
        )
    )
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    schedule_id = scheduled_operation_id("fixture", "check")

    def fire() -> str:
        response = service.dispatch(
            request(
                "job.fire",
                "systemd-jobs",
                {
                    "project_id": "fixture",
                    "operation": "check",
                    "schedule_id": schedule_id,
                },
                "operator",
            )
        )
        assert response.ok and response.payload is not None
        job_id = response.payload.inline["job_id"]
        fake_pueue.succeed(fake_task_id(jobs, job_id))
        assert jobs.get(job_id)["state"]["terminal"]
        return job_id

    first = fire()
    log = jobs.store.load(first).log_path
    log.write_text("first run\n")
    second = fire()

    assert not (jobs.store.records_root / f"{first}.json").exists()
    assert not log.exists()
    assert (jobs.store.records_root / f"{second}.json").exists()


def test_declared_job_binds_workspace_and_exact_head(tmp_path: Path) -> None:
    """Anti-vacuity: workspace verification launches in that checkout and persists its HEAD."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    workspace = service.workspaces.create(
        project_id="fixture",
        name="verify-lane",
        branch="feature/verify-lane",
        base="HEAD",
    )
    assert service.workspaces.resolve_checkout(
        "fixture", workspace["checkout_id"]
    ).path == Path(workspace["path"])

    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "operation": "check",
                "workspace_id": "verify-lane",
            },
        )
    )

    assert started.ok and started.payload is not None
    record = jobs.store.load(started.payload.inline["job_id"])
    assert record.spec.working_directory == workspace["path"]
    assert record.spec.checkout is not None
    assert record.spec.checkout["checkout_id"] == workspace["checkout_id"]
    assert record.spec.checkout["head"] == workspace["head"]


def test_forged_packet_completion_arguments_have_no_service_route(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    workspace = service.workspaces.create(
        project_id="fixture",
        name="packet-lane",
        branch="feature/packet-lane",
        base="HEAD",
    )
    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "operation": "check",
                "workspace_id": workspace["workspace_id"],
            },
        )
    )
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]

    response = service.dispatch(
        request(
            "job.packet-completion",
            "systemd-jobs",
            {
                "job_id": job_id,
                "workspace_id": workspace["workspace_id"],
                "contract": {
                    "job_id": job_id,
                    "workspace_id": workspace["workspace_id"],
                    "write_scope": ["src/"],
                    "required_verification_refs": [],
                },
                "worker_result": None,
                "verification_receipts": [],
                "delegation": {"visibility": "unsupported", "pending": None},
                "evidence_receipts": [],
                "review": None,
            },
        )
    )

    assert response.error is not None
    assert response.error.code.value == "INVALID_ARGUMENT"


def test_delivery_snapshot_is_nul_safe_and_exact_file_scope_does_not_include_descendants(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    workspace = service.workspaces.create(
        project_id="fixture",
        name="snapshot-lane",
        branch="feature/snapshot",
        base="HEAD",
    )
    path = Path(workspace["path"])
    (path / "dir").mkdir()
    (path / "dir" / "exact").write_text("old\n")
    (path / "dir" / "delete\nfile").write_text("delete\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--quiet",
            "-m",
            "seed",
        ],
        check=True,
    )
    start = service.workspaces.get(workspace["workspace_id"])["head"]
    subprocess.run(
        ["git", "-C", str(path), "mv", "dir/exact", "dir/renamed\nfile"], check=True
    )
    (path / "dir" / "delete\nfile").unlink()
    (path / "dir" / "exact.child").write_text("outside exact-file scope\n")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--quiet",
            "-m",
            "paths",
        ],
        check=True,
    )
    snapshot = service.workspaces.delivery_snapshot(
        workspace["workspace_id"], start, scope=("dir/exact",)
    )
    assert not snapshot["in_scope"]
    assert {change["status"][0] for change in snapshot["changes"]} >= {"D", "R", "A"}
    assert any(
        "\n" in item for change in snapshot["changes"] for item in change["paths"]
    )
    assert service.workspaces.delivery_snapshot(
        workspace["workspace_id"], start, scope=("dir/",)
    )["in_scope"]


def test_packet_runner_seals_worker_report_to_runtime_observed_head(
    tmp_path: Path,
) -> None:
    initialize_git_checkout(tmp_path)
    start_head = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    (tmp_path / "change.txt").write_text("change\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "change.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--quiet",
            "-m",
            "change",
        ],
        check=True,
    )
    final_head = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    result_root = tmp_path / "private-results"
    result_root.mkdir(mode=0o700)
    result_path = result_root / "packet.result"
    result_path.touch(mode=0o600)
    delivery = {
        "anti_vacuity": True,
        "unresolved_work": [],
        "delegation": {"visibility": "unsupported", "pending": None},
        "deletion_evidence": [],
        "evidence_only": False,
    }
    result_path.write_text(json.dumps(delivery))

    _seal_packet_result(
        {"job_id": "packet-job", "checkout": {"head": start_head}},
        tmp_path,
        result_path,
    )

    assert json.loads(result_path.read_text()) == {
        "schema_version": 1,
        "job_id": "packet-job",
        "start_head": start_head,
        "final_head": final_head,
        "delivery": delivery,
    }

    result_path.write_text("not-json")
    with pytest.raises(RunnerError, match="worker result"):
        _seal_packet_result(
            {"job_id": "packet-job", "checkout": {"head": start_head}},
            tmp_path,
            result_path,
        )

    result_path.write_bytes(b"\xff")
    with pytest.raises(RunnerError, match="worker result") as caught:
        _seal_packet_result(
            {"job_id": "packet-job", "checkout": {"head": start_head}},
            tmp_path,
            result_path,
        )
    assert isinstance(caught.value.__cause__, UnicodeDecodeError)


def test_the_queued_command_refuses_a_checkout_that_moved_after_dispatch(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """A checkout mutation after dispatch cannot reach the project payload.

    Anti-vacuity: the binding is frozen when the job is queued, so without the
    wrapper's revalidation the command would run against a different tree than
    the one the caller verified.
    """
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    jobs = generic_jobs(tmp_path)
    catalog = ProjectCatalog([tmp_path])
    project = catalog.get("fixture")
    checkout = catalog.checkout("fixture", "default")
    started = jobs.start_declared(
        project=project,
        operation=project.operation("service"),
        correlation_id="declared-runner-fixture",
        parameters={},
        checkout=checkout,
    )
    record = jobs.store.load(started["job_id"])
    launch = queue_launch_input(jobs, record.job_id)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--allow-empty",
            "-m",
            "moved",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert queue_run.run(launch) == queue_run.REFUSED_EXIT_CODE

    assert "checkout revalidation failed" in Path(launch["log_path"]).read_text()


def test_typed_shell_and_agent_contracts_share_generic_job_lifecycle(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: typed contracts must reach GenericJobs, not a second controller."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(
        ProjectCatalog([tmp_path]),
        jobs=jobs,
        native_runner=runner,
    )

    shell = service.dispatch(
        request(
            "job.shell.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "argv": ["printf", "shell-secret"],
                "cwd": ".",
                "timeout_seconds": 60,
                "result": "exit-status",
            },
            "operator",
        )
    )
    agent = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "prompt": "private prompt",
                "backend": "codex",
                "model": "fixture",
                "effort": "high",
                "credential_profile": "subscription",
                "timeout_seconds": 60,
                "result": "last-message",
                "bead_binding": {
                    "bead_ref": "sinnix://projects/fixture/beads/fixture-1",
                    "project_ref": "sinnix://projects/fixture",
                    "checkout_ref": "sinnix://projects/fixture/checkouts/default",
                    "task_revision": "a" * 64,
                    "task_etag": "b" * 64,
                    "claim_ref": f"sinnix://projects/fixture/beads/fixture-1/claims/{'b' * 64}",
                    "claim_receipt": {
                        "ref": f"sinnix://projects/fixture/beads/fixture-1/claims/{'b' * 64}",
                        "owner_route": "beads.cli",
                    },
                    "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b",
                    "assignment_ref": None,
                },
            },
            "agent-control",
        )
    )
    operator_agent = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "prompt": "operator prompt",
                "backend": "claude",
                "model": "fixture",
                "effort": "high",
                "credential_profile": "subscription",
                "timeout_seconds": 60,
                "result": "last-message",
            },
            "operator",
        )
    )

    assert shell.ok and agent.ok and operator_agent.ok
    assert (
        shell.payload is not None
        and agent.payload is not None
        and operator_agent.payload is not None
    )
    shell_job = shell.payload.inline
    agent_job = agent.payload.inline
    assert shell_job["kind"] == "operator-shell"
    assert shell_job["principal"] == "operator"
    assert shell_job["contract"]["argv"]["executable"] == "printf"
    shell_input = json.loads(
        (tmp_path / "state" / "inputs" / f"{shell_job['job_id']}.json").read_text()
    )
    assert shell_input["environment_command"] == ["fixture-env", "--command"]
    assert agent_job["kind"] == "attested-agent"
    assert agent_job["principal"] == "agent-control"
    assert agent_job["contract"]["backend"] == "codex"
    assert (
        agent_job["contract"]["bead_binding"]["bead_ref"]
        == "sinnix://projects/fixture/beads/fixture-1"
    )
    assert (
        agent_job["contract"]["bead_binding"]["request_id"]
        == "2e46daf5-e9b1-4c6e-b99d-bcd46631730b"
    )
    assert agent_job["artifacts"]["result"]["max_bytes"] == 64_000
    persisted = (
        tmp_path / "state" / "jobs" / f"{agent_job['job_id']}.json"
    ).read_text()
    assert "private prompt" not in persisted
    assert "shell-secret" not in persisted
    assert "display only" not in persisted
    assert operator_agent.payload.inline["principal"] == "operator"
    assert operator_agent.payload.inline["contract"]["backend"] == "claude"
    assert len(fake_pueue.added) == 3
    assert all(job["unit"].startswith("sinnixd-job-") for job in (shell_job, agent_job))
    restarted = GenericJobs(
        UserSystemdJobs(), service.jobs.store, wait_poll_seconds=0.001
    )
    assert {job["job_id"] for job in restarted.list()["jobs"]} == {
        shell_job["job_id"],
        agent_job["job_id"],
        operator_agent.payload.inline["job_id"],
    }


def test_typed_shell_and_declared_operation_share_project_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity: shell must use the declared project environment contract."""
    monkeypatch.setenv("PROJECT_SECRET", "ambient-secret")
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        .replace('kind = "fixture"', 'kind = "nix-develop"')
        .replace(
            'command = ["fixture-env", "--command"]',
            'command = ["nix", "develop", "--command"]',
        )
    )
    initialize_git_checkout(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(
        ProjectCatalog([tmp_path]),
        jobs=jobs,
    )

    declared = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "check"},
        )
    )
    shell = service.dispatch(
        request(
            "job.shell.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "argv": ["python", "-m", "fixture"],
                "cwd": ".",
                "timeout_seconds": 60,
                "result": "exit-status",
            },
        )
    )

    assert declared.ok and shell.ok
    assert declared.payload is not None and shell.payload is not None
    declared_environment = queue_launch_input(jobs, declared.payload.inline["job_id"])[
        "environment"
    ]
    shell_environment = queue_launch_input(jobs, shell.payload.inline["job_id"])[
        "environment"
    ]
    project_environment = ProjectCatalog([tmp_path]).get("fixture").environment.values()
    assert {
        key: shell_environment[key] for key in project_environment
    } == project_environment
    assert {
        key: declared_environment[key] for key in project_environment
    } == project_environment
    assert shell_environment["PATH"] == declared_environment["PATH"]
    assert "PROJECT_SECRET" not in shell_environment
    assert "PROJECT_SECRET" not in declared_environment
    assert "PYTHONPATH" not in shell_environment
    assert "PYTHONPATH" not in declared_environment


def test_typed_shell_runner_enters_the_registered_project_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path.resolve()
    workdir = checkout / "nested"
    workdir.mkdir()
    observed: dict[str, object] = {}

    monkeypatch.setattr(os, "chdir", lambda path: observed.update(cwd=path))

    def execute(executable: str, argv: list[str], environment: dict[str, str]) -> None:
        observed.update(executable=executable, argv=argv, environment=environment)
        raise RuntimeError("exec intercepted")

    monkeypatch.setattr(os, "execvpe", execute)

    with pytest.raises(RuntimeError, match="exec intercepted"):
        _exec_shell(
            {
                "kind": "operator-shell",
                "principal": "operator",
                "cwd": str(workdir),
                "argv": ["python", "-m", "fixture"],
                "environment_command": ["nix", "develop", "--command"],
            },
            checkout,
        )

    assert observed["cwd"] == workdir
    assert observed["executable"] == "nix"
    assert observed["argv"] == [
        "nix",
        "develop",
        "--command",
        "python",
        "-m",
        "fixture",
    ]


def test_agent_production_route_uses_declared_environment_over_poisoned_ambient_imports(
    tmp_path: Path,
) -> None:
    """A real typed input gets its PATH and import root only from the declared environment."""
    write_adapter(tmp_path)
    environment = tmp_path / "fixture-environment"
    environment.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "printf 'entered\\n' >> environment.calls\n"
        'export PATH="$PWD/project-bin:/run/current-system/sw/bin"\n'
        'export PYTHONPATH="$PWD"\n'
        'exec "$@"\n'
    )
    environment.chmod(0o700)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'command = ["fixture-env", "--command"]',
            f'command = ["{environment}"]',
        )
    )
    (tmp_path / "project-bin").mkdir()
    (tmp_path / "devtools").mkdir()
    (tmp_path / "devtools" / "__init__.py").write_text("")
    (tmp_path / "devtools" / "__main__.py").write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "with Path('devtools.calls').open('a') as handle:\n"
        "    handle.write(' '.join(sys.argv[1:]) + '\\n')\n"
    )
    (tmp_path / "fixture_package").mkdir()
    (tmp_path / "fixture_package" / "__init__.py").write_text("CHECKOUT = __file__\n")
    devtools = tmp_path / "project-bin" / "devtools"
    devtools.write_text(f'#!/bin/sh\nexec {sys.executable} -m devtools "$@"\n')
    devtools.chmod(0o700)
    initialize_git_checkout(tmp_path)

    native = tmp_path / "native-runner"
    native.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "last=\n"
        "while [ $# -gt 0 ]; do\n"
        "  case $1 in --last-file) last=$2; shift 2 ;; *) shift ;; esac\n"
        "done\n"
        'test "$(command -v devtools)" = "$PWD/project-bin/devtools"\n'
        "devtools status\n"
        "devtools test tests/fixture.py::test_noop\n"
        "devtools verify --quick\n"
        f"{sys.executable} -c 'import fixture_package; assert fixture_package.CHECKOUT'\n"
        "printf native-started > native.started\n"
        'printf native-result > "$last"\n'
    )
    native.chmod(0o700)

    jobs = generic_jobs(tmp_path)
    service = SinnixdService(
        ProjectCatalog([tmp_path]),
        jobs=jobs,
        native_runner=native,
    )
    response = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "prompt": "fixture prompt",
                "backend": "codex",
                "model": "fixture",
                "effort": "high",
                "credential_profile": "subscription",
                "timeout_seconds": 60,
                "result": "last-message",
            },
            "agent-control",
        )
    )
    assert response.ok and response.payload is not None
    job_id = response.payload.inline["job_id"]
    launch = queue_launch_input(jobs, job_id)
    private = json.loads((tmp_path / "state" / "inputs" / f"{job_id}.json").read_text())
    assert private["environment_command"] == [str(environment)]
    assert private["environment_preflight"] == ["devtools", "status", "--stderr"]
    assert private["schema_version"] == 2

    poisoned = {str(key): str(value) for key, value in launch["environment"].items()}
    poisoned["PATH"] = ":".join(
        [str(tmp_path / "another-checkout" / "project-bin"), poisoned["PATH"]]
    )
    poisoned["PYTHONPATH"] = os.environ.get("PYTHONPATH", "")
    mutant = subprocess.run(
        [
            str(native),
            "--last-file",
            str(tmp_path / "state" / "results" / "mutant.result"),
        ],
        cwd=tmp_path,
        env=poisoned,
        capture_output=True,
        text=True,
        check=False,
    )
    assert mutant.returncode != 0
    assert not (tmp_path / "native.started").exists()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sinnixd.runner",
            "--input",
            str(tmp_path / "state" / "inputs" / f"{job_id}.json"),
            "--job-id",
            job_id,
            "--unit",
            f"sinnixd-job-{job_id}.service",
            "--native-runner",
            str(native),
            "--state-root",
            str(tmp_path / "state"),
        ],
        cwd=Path.cwd(),
        env=poisoned,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "native.started").read_text() == "native-started"
    assert (
        tmp_path / "state" / "results" / f"{job_id}.result"
    ).read_text() == "native-result"
    assert (tmp_path / "environment.calls").read_text().splitlines() == [
        "entered",
        "entered",
    ]
    assert (tmp_path / "devtools.calls").read_text().splitlines() == [
        "status --stderr",
        "status",
        "test tests/fixture.py::test_noop",
        "verify --quick",
    ]


def test_agent_environment_preflight_refuses_missing_declaration_before_launch(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'preflight = ["devtools", "status", "--stderr"]\n', ""
        )
    )
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    systemd = FakeSystemdJobs()
    service = SinnixdService(
        ProjectCatalog([tmp_path]),
        jobs=generic_jobs(tmp_path, systemd),
        native_runner=runner,
    )

    response = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "prompt": "prompt",
                "backend": "codex",
                "model": "fixture",
                "effort": "high",
                "credential_profile": "subscription",
                "timeout_seconds": 60,
                "result": "last-message",
            },
            "agent-control",
        )
    )
    assert not response.ok
    assert response.error is not None
    assert "agent environment preflight" in response.error.message
    assert fake_pueue.added == []


def test_agent_environment_preflight_refuses_corrupt_environment_before_native_runner(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    state = tmp_path / "state"
    inputs = state / "inputs"
    results = state / "results"
    inputs.mkdir(parents=True)
    results.mkdir()
    prompt = inputs / "fixture.prompt"
    prompt.write_text("prompt")
    job_id = "11111111-1111-1111-1111-111111111111"
    payload = {
        "schema_version": 2,
        "job_id": job_id,
        "kind": "attested-agent",
        "principal": "agent-control",
        "checkout": ProjectCatalog([tmp_path]).checkout("fixture", "default").to_dict(),
        "environment_command": [sys.executable, "-c", "raise SystemExit(17)"],
        "environment_preflight": ["fixture-preflight"],
        "backend": "codex",
        "model": "fixture",
        "effort": "high",
        "credential_profile": "subscription",
        "prompt_path": str(prompt),
        "result_path": str(results / "fixture.result"),
    }

    with pytest.raises(
        RunnerError,
        match="project environment preflight failed before agent implementation.*17",
    ):
        _run_agent(payload, tmp_path, native_runner=runner, state_root=state)
    assert not (results / "fixture.result").exists()


def test_agent_environment_preflight_timeout_is_distinct_and_prevents_native_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    inputs = state / "inputs"
    results = state / "results"
    inputs.mkdir(parents=True)
    results.mkdir()
    prompt = inputs / "fixture.prompt"
    prompt.write_text("prompt")
    runner = tmp_path / "native-runner"
    native_runner(runner)
    payload = {
        "schema_version": 2,
        "job_id": "11111111-1111-1111-1111-111111111111",
        "kind": "attested-agent",
        "principal": "agent-control",
        "environment_command": ["fixture-environment"],
        "environment_preflight": ["status"],
        "backend": "codex",
        "model": "fixture",
        "effort": "high",
        "credential_profile": "subscription",
        "prompt_path": str(prompt),
        "result_path": str(results / "fixture.result"),
    }

    observed: dict[str, object] = {}

    def timeout(*_args: object, **kwargs: object) -> None:
        observed.update(kwargs)
        raise subprocess.TimeoutExpired("fixture-environment", 30)

    monkeypatch.setattr(runner_module.subprocess, "run", timeout)
    with pytest.raises(RunnerError, match="agent-preflight-timeout.*30 seconds"):
        _run_agent(payload, tmp_path, native_runner=runner, state_root=state)
    assert observed == {"cwd": tmp_path, "check": False, "timeout": 30}
    assert not (results / "fixture.result").exists()


def test_agent_environment_preflight_uses_descriptor_timeout_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    inputs = state / "inputs"
    results = state / "results"
    inputs.mkdir(parents=True)
    results.mkdir()
    prompt = inputs / "fixture.prompt"
    prompt.write_text("prompt")
    runner = tmp_path / "native-runner"
    native_runner(runner)
    payload = {
        "schema_version": 2,
        "job_id": "11111111-1111-1111-1111-111111111111",
        "kind": "attested-agent",
        "principal": "agent-control",
        "environment_command": ["fixture-environment"],
        "environment_preflight": ["status"],
        "preflight_timeout_seconds": 180,
        "backend": "codex",
        "model": "fixture",
        "effort": "high",
        "credential_profile": "subscription",
        "prompt_path": str(prompt),
        "result_path": str(results / "fixture.result"),
    }
    calls: list[dict[str, object]] = []

    def run(*_args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(kwargs)
        return subprocess.CompletedProcess([], 0)

    monkeypatch.setattr(runner_module.subprocess, "run", run)
    assert _run_agent(payload, tmp_path, native_runner=runner, state_root=state) == 0
    assert calls[0]["timeout"] == 180
    assert len(calls) == 2


def test_pre_upgrade_attested_agent_input_fails_closed_with_stale_schema(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "legacy-agent.json"
    input_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "job_id": "11111111-1111-1111-1111-111111111111",
                "kind": "attested-agent",
                "principal": "agent-control",
            }
        )
    )
    with pytest.raises(RunnerError, match="stale attested-agent private input schema"):
        _load(input_path, "11111111-1111-1111-1111-111111111111")


def test_agent_environment_descriptor_audit_reports_each_registered_project(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "fixture"
    missing_command = tmp_path / "missing-command"
    write_adapter(fixture, project_id="fixture")
    write_adapter(missing_command, project_id="missing_command")
    descriptor = fixture / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'preflight = ["devtools", "status", "--stderr"]\n', ""
        )
    )
    descriptor = missing_command / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'command = ["fixture-env", "--command"]', "command = []"
        )
    )

    with pytest.raises(
        ProjectConfigError, match="agent-capable project environment contract failed"
    ) as error:
        validate_agent_environment_descriptors([fixture, missing_command])
    message = str(error.value)
    assert "fixture:" in message
    assert "environment.preflight" in message
    assert "missing_command:" in message
    assert "environment.command" in message


def test_project_get_publishes_agent_environment_capability(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    service = SinnixdService(
        ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path), native_runner=runner
    )

    response = service.dispatch(
        request(
            "project.get", "project-adapters", {"project_id": "fixture"}, "observer"
        )
    )

    assert response.ok and response.payload is not None
    environment = response.payload.inline["environment"]
    assert environment == {
        "kind": "fixture",
        "command": ["fixture-env", "--command"],
        "preflight": ["devtools", "status", "--stderr"],
        "agent_capable": True,
        "declared": [],
        "require": [],
    }


def test_typed_contracts_refuse_spoofed_principals_checkout_backend_environment_and_results(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    service = SinnixdService(
        ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path), native_runner=runner
    )
    shell_arguments = {
        "project_id": "fixture",
        "checkout_id": "default",
        "argv": ["true"],
        "cwd": ".",
        "timeout_seconds": 60,
        "result": "exit-status",
    }
    agent_arguments = {
        "project_id": "fixture",
        "checkout_id": "default",
        "prompt": "prompt",
        "backend": "codex",
        "model": "fixture",
        "effort": "high",
        "credential_profile": "subscription",
        "timeout_seconds": 60,
        "result": "last-message",
    }
    invalid_principal = service.dispatch(
        request("job.shell.start", "systemd-jobs", shell_arguments, "observer")
    )
    invalid_checkout = service.dispatch(
        request(
            "job.shell.start",
            "systemd-jobs",
            {**shell_arguments, "checkout_id": "absent"},
            "operator",
        )
    )
    invalid_backend = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {**agent_arguments, "backend": "unknown"},
            "agent-control",
        )
    )
    invalid_bead_binding = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {
                **agent_arguments,
                "bead_binding": {
                    "bead_ref": "sinnix://projects/fixture/beads/fixture-1",
                    "project_ref": "sinnix://projects/fixture",
                    "checkout_ref": "sinnix://projects/fixture/checkouts/default",
                    "task_revision": "a" * 64,
                    "task_etag": "b" * 64,
                    "claim_ref": "sinnix://projects/fixture/beads/other/claims/receipt",
                    "claim_receipt": {
                        "ref": "sinnix://projects/fixture/beads/other/claims/receipt"
                    },
                    "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b",
                    "assignment_ref": None,
                },
            },
            "agent-control",
        )
    )
    legacy_work_item_binding = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {
                **agent_arguments,
                "bead_binding": {
                    "bead_ref": "sinnix://projects/fixture/beads/fixture-1",
                    "project_ref": "sinnix://projects/fixture",
                    "checkout_ref": "sinnix://projects/fixture/checkouts/default",
                    "task_revision": "a" * 64,
                    "task_etag": "b" * 64,
                    "claim_ref": None,
                    "claim_receipt": None,
                    "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b",
                    "assignment_ref": None,
                    "work_item": "private task prose",
                },
            },
            "agent-control",
        )
    )
    invalid_environment = service.dispatch(
        request(
            "job.shell.start",
            "systemd-jobs",
            {**shell_arguments, "environment": {"SINNIXD_JOB_ID": "spoof"}},
            "operator",
        )
    )
    invalid_result = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {**agent_arguments, "result": "exit-status"},
            "agent-control",
        )
    )

    for response in (
        invalid_principal,
        invalid_checkout,
        invalid_backend,
        invalid_bead_binding,
        legacy_work_item_binding,
        invalid_environment,
        invalid_result,
    ):
        assert response.error is not None
        assert response.error.code.value == "INVALID_ARGUMENT"


def test_failed_agent_launch_removes_private_prompt_and_contract_input(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: a rejected launch cannot leave prompt material in durable state."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    fake_pueue.fail_add = True

    service = SinnixdService(
        ProjectCatalog([tmp_path]),
        jobs=generic_jobs(tmp_path),
        native_runner=runner,
    )

    response = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "prompt": "private prompt removed after launch failure",
                "backend": "codex",
                "model": "fixture",
                "effort": "high",
                "credential_profile": "subscription",
                "timeout_seconds": 60,
                "result": "last-message",
            },
            "agent-control",
        )
    )

    assert response.ok
    assert response.payload is not None
    assert response.payload.inline["state"]["phase"] == "launch-unknown"
    assert not list((tmp_path / "state" / "inputs").iterdir())


def test_runner_rejects_changed_or_unregistered_checkout_identities(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    checkout = ProjectCatalog([tmp_path]).checkout("fixture", "default").to_dict()

    for changed in (
        {**checkout, "git_common_dir": str(tmp_path / "other-common-dir")},
        {**checkout, "head": "0" * 40},
        {**checkout, "project_path": str(tmp_path / "unregistered-project")},
    ):
        with pytest.raises(RunnerError):
            _revalidate_checkout(changed)

    symlink = tmp_path.parent / f"{tmp_path.name}-symlink"
    symlink.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(RunnerError):
        _revalidate_checkout({**checkout, "path": str(symlink)})
    loop = tmp_path.parent / f"{tmp_path.name}-loop"
    loop.symlink_to(loop.name)
    with pytest.raises(RunnerError):
        _revalidate_checkout({**checkout, "path": str(loop)})


def test_agent_runner_revalidates_checkout_and_writes_a_bounded_result_fixture(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: the native runner only executes after Git identity and env checks pass."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    catalog = ProjectCatalog([tmp_path])
    checkout = catalog.checkout("fixture", "default")
    state = tmp_path / "state"
    inputs = state / "inputs"
    results = state / "results"
    runner_arguments = state / "native-runner.args"
    inputs.mkdir(parents=True)
    results.mkdir()
    prompt = inputs / "fixture.prompt"
    prompt.write_text("private fixture prompt")
    payload = {
        "schema_version": 2,
        "job_id": "11111111-1111-1111-1111-111111111111",
        "kind": "attested-agent",
        "principal": "agent-control",
        "checkout": checkout.to_dict(),
        "environment_command": ["env"],
        "environment_preflight": ["true"],
        "backend": "codex",
        "model": "fixture",
        "effort": "high",
        "credential_profile": "subscription",
        "prompt_path": str(prompt),
        "result_path": str(results / "fixture.result"),
    }
    input_path = inputs / "fixture.json"
    input_path.write_text(json.dumps(payload))
    environment = {
        **os.environ,
        "SINNIXD_JOB_ID": payload["job_id"],
        "SINNIXD_PROJECT_ID": "fixture",
        "SINNIXD_CHECKOUT_ID": "default",
        "SINNIXD_PRINCIPAL": "agent-control",
        "SINNIXD_TIMEOUT_SECONDS": "60",
        "RUNNER_ARGS": str(runner_arguments),
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sinnixd.runner",
            "--input",
            str(input_path),
            "--job-id",
            payload["job_id"],
            "--unit",
            f"sinnixd-job-{payload['job_id']}.service",
            "--native-runner",
            str(runner),
            "--state-root",
            str(state),
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "native-fixture-log"
    assert (results / "fixture.result").read_text() == "native-fixture-result"
    assert not prompt.exists()
    assert not input_path.exists()
    handoff = runner_arguments.read_text().splitlines()
    assert handoff[handoff.index("--workdir") + 1] == str(checkout.path)
    assert "--job-state-dir" not in handoff
    assert "--registered-project" not in handoff
    assert "--expected-git-common-dir" not in handoff


def test_runner_rejects_forged_sinnix_environment(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    checkout = ProjectCatalog([tmp_path]).checkout("fixture", "default")
    state = tmp_path / "state"
    inputs = state / "inputs"
    inputs.mkdir(parents=True)
    prompt = inputs / "fixture.prompt"
    prompt.write_text("private fixture prompt")
    job_id = "11111111-1111-1111-1111-111111111111"
    input_path = inputs / "fixture.json"
    input_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "job_id": job_id,
                "kind": "attested-agent",
                "principal": "agent-control",
                "checkout": checkout.to_dict(),
                "environment_command": ["env"],
                "environment_preflight": ["true"],
                "backend": "codex",
                "model": "fixture",
                "effort": "high",
                "credential_profile": "subscription",
                "prompt_path": str(prompt),
                "result_path": str(state / "results" / "fixture.result"),
            }
        )
    )
    environment = {
        **os.environ,
        "SINNIXD_JOB_ID": job_id,
        "SINNIXD_PROJECT_ID": "fixture",
        "SINNIXD_CHECKOUT_ID": "default",
        "SINNIXD_PRINCIPAL": "agent-control",
        "SINNIXD_TIMEOUT_SECONDS": "60",
        "SINNIXD_FORGED": "identity-overlay",
    }

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sinnixd.runner",
            "--input",
            str(input_path),
            "--job-id",
            job_id,
            "--unit",
            f"sinnixd-job-{job_id}.service",
            "--native-runner",
            str(runner),
            "--state-root",
            str(state),
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "untrusted SINNIX identity" in result.stderr


def test_environment_builder_keeps_empty_values_distinct_from_unset() -> None:
    """Anti-vacuity: replacing membership checks with truthiness drops the empty EMPTY value."""
    environment = build_environment(
        inherit=("EMPTY", "PRESENT", "MISSING", "REMOVED"),
        unset=("REMOVED",),
        source={"PATH": "", "EMPTY": "", "PRESENT": "value", "REMOVED": "secret"},
    )

    assert environment == {"PATH": "", "EMPTY": "", "PRESENT": "value"}


@pytest.mark.parametrize(
    ("finish", "expected"),
    [
        (lambda pueue, task_id: pueue.succeed(task_id), "succeeded"),
        (
            lambda pueue, task_id: pueue.fail(
                task_id, exit_code=queue_run.TIMEOUT_EXIT_CODE
            ),
            "timeout",
        ),
        (lambda pueue, task_id: pueue.fail(task_id, exit_code=1), "failed"),
        (
            lambda pueue, task_id: pueue.fail(
                task_id, exit_code=queue_run.REFUSED_EXIT_CODE
            ),
            "launch-failed",
        ),
        (lambda pueue, task_id: pueue.dependency_fail(task_id), "dependency-failed"),
        (lambda pueue, task_id: pueue.fail_to_spawn(task_id), "launch-failed"),
        (lambda pueue, task_id: pueue.kill_directly(task_id), "cancelled"),
    ],
)
def test_terminal_result_classification_comes_from_pueue(
    tmp_path: Path,
    fake_pueue: FakePueue,
    finish: Callable[[FakePueue, int], None],
    expected: str,
) -> None:
    """Anti-vacuity: deleting GenericJobs._classify breaks the terminal phase assertion."""
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={"PATH": ""},
    )
    finish(fake_pueue, fake_task_id(jobs, started["job_id"]))

    status = jobs.get(started["job_id"])

    assert status["state"]["phase"] == expected
    assert status["state"]["terminal"]


def test_logs_are_bounded_and_restart_reconciles_the_same_record(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: deleting the persisted record or GenericJobs.logs breaks restart reads."""
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={"PATH": ""},
    )
    fake_pueue.succeed(fake_task_id(jobs, started["job_id"]))
    record = jobs.store.load(started["job_id"])
    record.log_path.write_text("0123456789")

    log = jobs.logs(started["job_id"], offset=2, max_bytes=4)
    restarted = GenericJobs(systemd, jobs.store, wait_poll_seconds=0.001)
    listed = restarted.list()
    waited = restarted.wait(started["job_id"], timeout_seconds=1)

    assert log == {
        "job_id": started["job_id"],
        "offset": 2,
        "content": "2345",
        "next_offset": 6,
        "truncated": True,
        "artifact_truncated": False,
    }
    assert [job["job_id"] for job in listed["jobs"]] == [started["job_id"]]
    assert waited["state"]["phase"] == "succeeded"


def test_logs_report_a_truncated_persistent_artifact(tmp_path: Path) -> None:
    """Anti-vacuity: an overflow marker beside the log must surface as artifact_truncated."""
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    record = jobs.store.load(started["job_id"])
    record.log_path.write_bytes(b"0123")
    record.log_path.with_suffix(".overflow").touch()
    log = jobs.logs(started["job_id"], offset=2, max_bytes=2)
    assert log["content"] == "23"
    assert log["next_offset"] == 4
    assert not log["truncated"]
    assert log["artifact_truncated"]


def test_logs_report_marker_created_during_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity: sampling overflow before reading misses this interleaving."""
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    record = jobs.store.load(started["job_id"])
    record.log_path.write_bytes(b"0123")
    overflow_path = record.log_path.with_suffix(".overflow")
    original_read = jobs_module._read_private_artifact

    def marker_after_read(
        path: Path, max_bytes: int, *, offset: int = 0
    ) -> bytes | None:
        content = original_read(path, max_bytes, offset=offset)
        if path == record.log_path:
            overflow_path.touch()
        return content

    monkeypatch.setattr(jobs_module, "_read_private_artifact", marker_after_read)

    log = jobs.logs(started["job_id"], max_bytes=4)

    assert log["content"] == "0123"
    assert log["artifact_truncated"]


def test_foreground_specs_redact_argv_and_environment_from_disk(tmp_path: Path) -> None:
    """Anti-vacuity: serializing the launch command or environment exposes this fixture secret."""
    secret_argv = "argv-secret-do-not-persist"
    secret_env = "env-secret-do-not-persist"
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(
        command=("fixture", secret_argv),
        working_directory=str(tmp_path),
        environment={"SECRET": secret_env},
    )
    raw = (tmp_path / "state" / "jobs" / f"{started['job_id']}.json").read_text()
    persisted = json.loads(raw)
    assert secret_argv not in raw
    assert secret_env not in raw
    assert persisted["spec"]["command"]["display"] == "synthetic foreground command"
    assert len(persisted["spec"]["command"]["digest"]) == 64


def test_job_store_fsyncs_parent_after_replacing_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Anti-vacuity: a file fsync before rename cannot make the renamed entry crash-durable."""
    store = GenericJobStore(tmp_path / "state")
    record = store.create(
        GenericJobSpec(
            kind="foreground-command",
            command=("fixture",),
            working_directory=str(tmp_path),
            environment={},
        ),
        "00000000-0000-0000-0000-000000000001",
    )
    directory_fd = 10_000
    events: list[tuple[str, object]] = []
    original_open = os.open
    original_close = os.close
    original_replace = os.replace

    def tracked_open(path, flags, *args):
        if flags & os.O_DIRECTORY:
            events.append(("open-directory", Path(path)))
            return directory_fd
        return original_open(path, flags, *args)

    def tracked_fsync(descriptor: int) -> None:
        events.append(
            (
                "fsync-directory" if descriptor == directory_fd else "fsync-file",
                descriptor,
            )
        )

    def tracked_close(descriptor: int) -> None:
        if descriptor == directory_fd:
            events.append(("close-directory", descriptor))
            return
        original_close(descriptor)

    def tracked_replace(source, destination) -> None:
        events.append(("replace", Path(destination)))
        original_replace(source, destination)

    monkeypatch.setattr("sinnixd.jobs.os.open", tracked_open)
    monkeypatch.setattr("sinnixd.jobs.os.fsync", tracked_fsync)
    monkeypatch.setattr("sinnixd.jobs.os.close", tracked_close)
    monkeypatch.setattr("sinnixd.jobs.os.replace", tracked_replace)

    store.save(record)

    replace_index = events.index(
        ("replace", store.records_root / f"{record.job_id}.json")
    )
    file_fsync_index = max(
        index
        for index, event in enumerate(events[:replace_index])
        if event[0] == "fsync-file"
    )
    directory_fsync_index = next(
        index
        for index, event in enumerate(
            events[replace_index + 1 :], start=replace_index + 1
        )
        if event == ("fsync-directory", directory_fd)
        and events[index - 1] == ("open-directory", store.records_root)
    )
    assert file_fsync_index < replace_index < directory_fsync_index
    assert events[directory_fsync_index - 1] == ("open-directory", store.records_root)


def test_job_store_fsyncs_parents_when_creating_state_directories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Anti-vacuity: mkdir alone can lose a newly established state hierarchy after a crash."""
    synchronized: list[Path] = []
    original_fsync_directory = jobs_module._fsync_directory

    def tracked_fsync_directory(path: Path) -> None:
        synchronized.append(path)
        original_fsync_directory(path)

    monkeypatch.setattr("sinnixd.jobs._fsync_directory", tracked_fsync_directory)
    store = GenericJobStore(tmp_path / "state")

    store.create(
        GenericJobSpec(
            kind="foreground-command",
            command=("fixture",),
            working_directory=str(tmp_path),
            environment={},
        ),
        "00000000-0000-0000-0000-000000000002",
    )

    assert synchronized == [
        tmp_path,
        store.root,
        store.root,
        store.root,
        store.logs_root,
        store.root,
        store.records_root,
    ]


def test_confirmed_absence_and_launch_failure_are_distinct_terminal_outcomes(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: a task pueue has forgotten is a distinct terminal outcome from an ordinary cancel."""
    jobs = generic_jobs(tmp_path)
    status = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    fake_pueue.remove([fake_task_id(jobs, status["job_id"])])
    status = jobs.get(status["job_id"])
    cancelled = jobs.cancel(status["job_id"], reason="test-cancel")
    waited = jobs.wait(status["job_id"], timeout_seconds=1)
    assert status["state"]["phase"] == "missing"
    assert status["state"]["terminal"]
    assert cancelled["already_terminal"]
    assert not fake_pueue.killed
    assert waited["state"]["phase"] == "missing"


def test_pueue_add_failure_persists_launch_unknown_without_the_raw_error(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: a pueue.add failure must stay retryable and never leak its raw message."""
    fake_pueue.fail_add = True

    started = generic_jobs(tmp_path).start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    persisted = (tmp_path / "state" / "jobs" / f"{started['job_id']}.json").read_text()

    assert started["state"]["phase"] == "launch-unknown"
    assert started["state"]["error"] == {"code": "queue-job-error"}
    assert not started["state"]["terminal"]
    assert "fixture pueue add failed" not in persisted


def test_observation_failure_persists_only_the_stable_error_code(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: an unreachable pueue must stay retryable and never leak its raw message."""
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    fake_pueue.fail_tasks = True

    status = jobs.get(started["job_id"])
    persisted = (tmp_path / "state" / "jobs" / f"{started['job_id']}.json").read_text()

    assert status["state"]["phase"] == "observation-unknown"
    assert status["state"]["error"] == {"code": "queue-job-error"}
    assert not status["state"]["terminal"]
    assert "fixture pueue status failed" not in persisted


def test_cancel_kills_the_queued_task_and_persists_intent(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: cancel must kill pueue's task, not just record intent."""
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    task_id = fake_task_id(jobs, started["job_id"])

    cancelled = jobs.cancel(started["job_id"], reason="test-cancel")

    assert task_id in fake_pueue.killed
    assert cancelled["state"]["phase"] == "cancelled"
    record = jobs.store.load(started["job_id"])
    assert record.cancel_requested_at is not None


def test_cancel_of_a_job_never_reached_by_pueue_needs_no_kill(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: a job blocked on dependencies has no task to kill."""
    jobs = generic_jobs(tmp_path)
    dependency = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    record = jobs.store.create(
        GenericJobSpec(
            kind="declared-operation",
            command=("fixture",),
            working_directory=str(tmp_path),
            environment={},
            parameter_digest="0" * 64,
            dependency_job_ids=(dependency["job_id"],),
        )
    )
    jobs.store.save(
        GenericJobs._with_state(
            record,
            {
                "phase": "waiting-dependencies",
                "terminal": False,
                "observed_at": "x",
                "dependencies": [dependency["job_id"]],
            },
        )
    )

    cancelled = jobs.cancel(record.job_id, reason="test-cancel")

    assert not fake_pueue.killed
    assert cancelled["state"]["phase"] == "cancelled"
    assert cancelled["state"]["launch_evidence"] == "not-started"


def test_agentctl_wait_returns_a_timed_out_envelope_past_control_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Anti-vacuity: the CLI must decode a normal timed-out wait response after control framing has expired."""
    write_adapter(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    socket_path = tmp_path / "sinnixd.sock"
    stop_event = threading.Event()
    server = UnixSocketServer(socket_path, service, connection_timeout_seconds=0.05)
    wait_timeouts: list[float | None] = []
    original_wait_connection = server._serve_wait_connection

    def observe_wait_connection(*args, **kwargs) -> None:
        wait_timeouts.append(args[0].gettimeout())
        original_wait_connection(*args, **kwargs)

    server._serve_wait_connection = observe_wait_connection  # type: ignore[method-assign]
    thread = start_server(server, stop_event=stop_event)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agentctl",
            "--socket",
            str(socket_path),
            "job",
            "wait",
            started["job_id"],
            "--timeout-seconds",
            "1",
        ],
    )
    try:
        assert cli_module.main() == 0
    finally:
        stop_event.set()
        thread.join(timeout=2)

    response = json.loads(capsys.readouterr().out)
    assert not thread.is_alive()
    assert wait_timeouts == [1 + WAIT_TRANSPORT_MARGIN_SECONDS]
    assert response["ok"]
    assert response["payload"]["value"]["state"]["phase"] == "running"
    assert response["payload"]["value"]["wait_timed_out"]


def test_every_operation_has_a_declared_response_budget() -> None:
    """A new dispatch branch without a budget is a red test, not a 5s fallback."""
    budgeted = set(CONTROL_OPERATION_RESPONSE_TIMEOUT_SECONDS) | WAIT_OPERATIONS
    assert budgeted == SUPPORTED_OPERATIONS
    for operation, timeout in CONTROL_OPERATION_RESPONSE_TIMEOUT_SECONDS.items():
        assert timeout >= 5.0
        assert (
            _response_timeout_seconds(request(operation, "git-workspaces")) == timeout
        )


def test_slow_operations_keep_their_widened_budgets() -> None:
    """Remote effects must not outlive the client's success/failure response."""
    floors = {
        "campaign.run": 300.0,
        "campaign.status": 30.0,
        "workspace.list": 60.0,
        # `packet launch` dispatches creation as its own step, so provisioning
        # must fit the client budget here. Without it the socket closes
        # mid-provision and the daemon logs a BrokenPipeError while the caller
        # is told it is unavailable.
        "workspace.create": 300.0,
        # Listing reconciles live systemd state per non-terminal record; at
        # fleet scale a 5s budget times out mid-response (sinnix-16in).
        "job.list": 60.0,
    }
    for operation, floor in floors.items():
        assert CONTROL_OPERATION_RESPONSE_TIMEOUT_SECONDS[operation] >= floor


def test_an_exhausted_response_budget_is_typed_not_an_outage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The daemon answered late, not never; the caller must see the difference."""
    socket_path = tmp_path / "sinnixd.sock"
    started = threading.Event()
    release = threading.Event()

    def slow_server() -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(socket_path))
            listener.listen()
            started.set()
            connection, _ = listener.accept()
            with connection:
                receive_frame(connection)
                release.wait(timeout=5)

    thread = threading.Thread(target=slow_server, daemon=True)
    thread.start()
    assert started.wait(timeout=5)
    monkeypatch.setitem(
        CONTROL_OPERATION_RESPONSE_TIMEOUT_SECONDS, "runtime.status", 0.2
    )
    with pytest.raises(ResponseBudgetExceeded) as exceeded:
        call(socket_path, request("runtime.status", "sinnixd"))
    release.set()
    thread.join(timeout=5)
    assert exceeded.value.operation == "runtime.status"
    assert exceeded.value.budget_seconds == 0.2
    assert "runtime.status" in str(exceeded.value)
    # Anti-vacuity: an absent socket stays an unavailability, not a budget.
    with pytest.raises(OSError):
        call(tmp_path / "absent.sock", request("runtime.status", "sinnixd"))


def test_wait_operations_cover_the_requested_wait_deadline() -> None:
    for operation, owner in (
        ("job.wait", "systemd-jobs"),
        ("plan.wait", "project-plans"),
    ):
        wait_request = request(operation, owner, {"timeout_seconds": 55})
        assert _response_timeout_seconds(wait_request) == 60


def test_agentctl_wait_reports_capacity_exhaustion_while_all_wait_workers_are_occupied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Anti-vacuity: raw framing cannot cover the agentctl capacity-error path."""
    write_adapter(tmp_path)
    jobs = generic_jobs(tmp_path)
    wait_started = threading.Event()
    wait_lock = threading.Lock()
    active_waits = 0
    original_wait = jobs.wait
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    socket_path = tmp_path / "sinnixd.sock"
    stop_event = threading.Event()
    server = UnixSocketServer(
        socket_path, service, connection_timeout_seconds=0.05, max_workers=8
    )
    wait_timeouts: list[float | None] = []
    original_wait_connection = server._serve_wait_connection

    def counted_wait(job_id: str, timeout_seconds: int = 30) -> dict[str, object]:
        nonlocal active_waits
        with wait_lock:
            active_waits += 1
            if active_waits == server.wait_worker_count:
                wait_started.set()
        return original_wait(job_id, timeout_seconds)

    def observe_wait_connection(*args, **kwargs) -> None:
        wait_timeouts.append(args[0].gettimeout())
        original_wait_connection(*args, **kwargs)

    jobs.wait = counted_wait  # type: ignore[method-assign]
    server._serve_wait_connection = observe_wait_connection  # type: ignore[method-assign]
    thread = start_server(server, stop_event=stop_event)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    job_id = started["job_id"]
    wait_results: list[dict[str, object]] = []
    wait_errors: list[Exception] = []

    def run_wait() -> None:
        try:
            wait_results.append(
                call(
                    socket_path,
                    request(
                        "job.wait",
                        "systemd-jobs",
                        {"job_id": job_id, "timeout_seconds": 1},
                    ),
                )
            )
        except Exception as error:
            wait_errors.append(error)

    waiters = [
        threading.Thread(target=run_wait, daemon=True)
        for _ in range(server.wait_worker_count)
    ]
    for waiter in waiters:
        waiter.start()
    assert wait_started.wait(timeout=1)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agentctl",
            "--socket",
            str(socket_path),
            "job",
            "wait",
            job_id,
            "--timeout-seconds",
            "1",
        ],
    )
    assert cli_module.main() == 1
    capacity = json.loads(capsys.readouterr().out)
    status = call(socket_path, request("runtime.status", "sinnixd"))
    get = call(socket_path, request("job.get", "systemd-jobs", {"job_id": job_id}))
    for waiter in waiters:
        waiter.join(timeout=2)
    stop_event.set()
    thread.join(timeout=2)
    assert not capacity["ok"]
    assert capacity["error"]["code"] == "RESOURCE_EXHAUSTED"
    assert capacity["error"]["message"] == "job.wait capacity is exhausted"
    assert status["ok"] and get["ok"]
    assert not wait_errors
    assert all(not waiter.is_alive() for waiter in waiters)
    assert len(wait_results) == server.wait_worker_count
    assert not thread.is_alive()
    assert (
        wait_timeouts == [1 + WAIT_TRANSPORT_MARGIN_SECONDS] * server.wait_worker_count
    )
    assert all(
        result["payload"]["value"]["state"]["phase"] == "running"
        for result in wait_results
    )
    assert all(result["payload"]["value"]["wait_timed_out"] for result in wait_results)


def test_job_rpc_get_list_wait_logs_and_cancel_share_one_record(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: deleting any RPC route prevents its shared job ID from resolving."""
    write_adapter(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    started = service.dispatch(
        request(
            "job.start", "systemd-jobs", {"project_id": "fixture", "operation": "check"}
        )
    )
    assert started.payload is not None
    job_id = started.payload.inline["job_id"]
    fake_pueue.succeed(fake_task_id(jobs, job_id))

    get = service.dispatch(request("job.get", "systemd-jobs", {"job_id": job_id}))
    listed = service.dispatch(request("job.list", "systemd-jobs", {"limit": 1}))
    waited = service.dispatch(
        request("job.wait", "systemd-jobs", {"job_id": job_id, "timeout_seconds": 1})
    )
    logs = service.dispatch(
        request("job.logs", "systemd-jobs", {"job_id": job_id, "max_bytes": 10})
    )
    cancelled = service.dispatch(
        request("job.cancel", "systemd-jobs", {"job_id": job_id})
    )

    assert all(response.ok for response in (get, listed, waited, logs, cancelled))
    assert listed.payload is not None
    assert listed.payload.inline["jobs"][0]["job_id"] == job_id
    assert listed.payload.inline["limit"] == 1
    assert listed.payload.inline["total"] == 1
    assert not listed.payload.inline["truncated"]
    assert cancelled.payload is not None
    assert cancelled.payload.inline["already_terminal"]


def test_active_job_list_does_not_scan_terminal_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = generic_jobs(tmp_path, FakeSystemdJobs())
    started = jobs.start(
        GenericJobSpec(
            kind="foreground-command",
            command=("fixture",),
            working_directory=str(tmp_path),
            environment={},
            timeout_seconds=60,
            principal="operator",
        )
    )
    monkeypatch.setattr(
        jobs.store,
        "list",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("active listing scanned terminal history")
        ),
    )

    listed = jobs.list(active_only=True)

    assert [item["job_id"] for item in listed["jobs"]] == [started["job_id"]]


def test_nonterminal_save_does_not_rewrite_unchanged_indexes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = generic_jobs(tmp_path, FakeSystemdJobs())
    started = jobs.start(
        GenericJobSpec(
            kind="foreground-command",
            command=("fixture",),
            working_directory=str(tmp_path),
            environment={},
            timeout_seconds=60,
            principal="operator",
        )
    )
    record = jobs.store.load(started["job_id"])
    active_writes: list[set[str]] = []
    monkeypatch.setattr(jobs.store, "_write_active_record_ids", active_writes.append)

    jobs.store.save(record)

    assert active_writes == []


def test_job_owner_boundary_filters_before_pagination_and_denies_cross_principal_access(
    tmp_path: Path,
) -> None:
    """Only a job creator or the operator reaches any job control path."""
    write_adapter(tmp_path)
    service = SinnixdService(
        ProjectCatalog([tmp_path]),
        jobs=generic_jobs(tmp_path, FakeSystemdJobs()),
    )

    def start(principal: str) -> str:
        response = service.jobs.start(
            GenericJobSpec(
                kind="foreground-command",
                command=("fixture",),
                working_directory=str(tmp_path),
                environment={},
                timeout_seconds=60,
                principal=principal,
            )
        )
        return response["job_id"]

    agent_job = start("agent-control")
    operator_jobs = [start("operator"), start("operator")]

    observer_list = service.dispatch(
        request("job.list", "systemd-jobs", {"limit": 1}, principal="observer")
    )
    assert observer_list.ok and observer_list.payload is not None
    assert observer_list.payload.inline["jobs"] == []
    assert observer_list.payload.inline["total"] == 0

    for operation, arguments in (
        ("job.get", {"job_id": operator_jobs[0]}),
        ("job.wait", {"job_id": operator_jobs[0], "timeout_seconds": 1}),
        ("job.logs", {"job_id": operator_jobs[0]}),
        ("job.result", {"job_id": operator_jobs[0]}),
        ("job.cancel", {"job_id": operator_jobs[0]}),
    ):
        denied = service.dispatch(
            request(operation, "systemd-jobs", arguments, principal="observer")
        )
        assert denied.error is not None
        assert denied.error.code is ErrorCode.POLICY_DENIED

    agent_list = service.dispatch(
        request("job.list", "systemd-jobs", {"limit": 10}, principal="agent-control")
    )
    assert agent_list.ok and agent_list.payload is not None
    assert [row["job_id"] for row in agent_list.payload.inline["jobs"]] == [agent_job]
    assert service.dispatch(
        request(
            "job.get", "systemd-jobs", {"job_id": agent_job}, principal="agent-control"
        )
    ).ok
    agent_denied = service.dispatch(
        request(
            "job.get",
            "systemd-jobs",
            {"job_id": operator_jobs[0]},
            principal="agent-control",
        )
    )
    assert agent_denied.error is not None
    assert agent_denied.error.code is ErrorCode.POLICY_DENIED

    listing = service.dispatch(
        request("job.list", "systemd-jobs", {"limit": 100}, principal="operator")
    )
    assert listing.ok and listing.payload is not None
    seen = [row["job_id"] for row in listing.payload.inline["jobs"]]
    assert set(seen) == {agent_job, *operator_jobs}
    assert len(seen) == 3
    assert service.dispatch(
        request("job.get", "systemd-jobs", {"job_id": agent_job}, principal="operator")
    ).ok


def test_unix_socket_server_round_trips_the_common_envelope(tmp_path: Path) -> None:
    write_adapter(tmp_path / "project")
    socket_path = tmp_path / "sinnixd.sock"
    service = SinnixdService(ProjectCatalog([tmp_path / "project"]))
    server = UnixSocketServer(socket_path, service)
    thread = start_server(server, once=True)

    response = call(socket_path, request("runtime.status", "sinnixd"))
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert response["ok"]
    assert response["payload"]["value"]["projects"] == 1


def test_unix_socket_server_returns_json_rpc_errors_without_crashing(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path / "project")
    socket_path = tmp_path / "sinnixd.sock"
    server = UnixSocketServer(
        socket_path, SinnixdService(ProjectCatalog([tmp_path / "project"]))
    )
    thread = start_server(server, once=True)

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(str(socket_path))
        send_frame(
            connection,
            {
                "jsonrpc": "2.0",
                "id": "not-a-request-id",
                "method": "wrong-method",
                "params": {},
            },
        )
        response = receive_frame(connection)
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert response == {
        "jsonrpc": "2.0",
        "id": "not-a-request-id",
        "error": {
            "code": -32600,
            "message": "request must be a JSON-RPC 2.0 dispatch call",
        },
    }


def test_unix_socket_server_continues_after_malformed_and_stalled_clients(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path / "project")
    socket_path = tmp_path / "sinnixd.sock"
    server = UnixSocketServer(
        socket_path,
        SinnixdService(ProjectCatalog([tmp_path / "project"])),
        connection_timeout_seconds=0.05,
    )
    stop_event = threading.Event()
    thread = start_server(server, stop_event=stop_event)

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(str(socket_path))
        connection.sendall(b"\x00\x00")
        threading.Event().wait(0.1)

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(str(socket_path))
        send_frame(
            connection,
            {
                "jsonrpc": "2.0",
                "id": str(uuid4()),
                "method": "dispatch",
                "params": {
                    "schema": 1,
                    "request_id": str(uuid4()),
                    "correlation_id": str(uuid4()),
                    "operation": "project.list",
                    "owner": "project-adapters",
                    "principal": "test",
                    "arguments": [["project_id", "fixture"]],
                    "idempotency_key": None,
                },
            },
        )
        malformed = receive_frame(connection)

    assert malformed["error"]["code"] == -32600
    assert malformed["error"]["message"] == "arguments must be an object"

    response = call(socket_path, request("runtime.status", "sinnixd"))
    stop_event.set()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert response["ok"]


def test_environment_values_and_require_parse_into_the_catalog(
    tmp_path: Path,
) -> None:
    root = tmp_path / "declared-environment"
    write_adapter(root)
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'unset = ["PYTHONPATH"]',
            'unset = ["PYTHONPATH"]\n'
            'require = ["FIXTURE_ARCHIVE_ROOT", "HOME"]\n\n'
            "[environment.values]\n"
            'FIXTURE_ARCHIVE_ROOT = "/realm/state/fixture"\n',
        )
    )
    catalog = ProjectCatalog((root,))
    project = catalog.get("fixture")

    environment = project.environment.values()
    row = project.environment.catalog_row(agent_capable=True)

    assert environment["FIXTURE_ARCHIVE_ROOT"] == "/realm/state/fixture"
    assert row["declared"] == ["FIXTURE_ARCHIVE_ROOT"]
    assert row["require"] == ["FIXTURE_ARCHIVE_ROOT", "HOME"]
    assert "/realm/state/fixture" not in json.dumps(
        {key: value for key, value in row.items() if key != "declared"}
    )


def test_environment_missing_required_variable_fails_job_build_loudly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Anti-vacuity: the silent-drop inherit model shipped jobs with absent variables."""
    from sinnixd.projects import ProjectEnvironmentError

    root = tmp_path / "required-environment"
    write_adapter(root)
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'inherit = ["HOME"]',
            'inherit = ["HOME", "FIXTURE_ARCHIVE_ROOT"]\n'
            'require = ["FIXTURE_ARCHIVE_ROOT"]',
        )
    )
    catalog = ProjectCatalog((root,))
    project = catalog.get("fixture")
    monkeypatch.delenv("FIXTURE_ARCHIVE_ROOT", raising=False)

    with pytest.raises(ProjectEnvironmentError, match="FIXTURE_ARCHIVE_ROOT"):
        project.environment.values()

    monkeypatch.setenv("FIXTURE_ARCHIVE_ROOT", "/realm/state/fixture")
    assert project.environment.values()["FIXTURE_ARCHIVE_ROOT"] == (
        "/realm/state/fixture"
    )


@pytest.mark.parametrize(
    "fragment",
    (
        '[environment.values]\nSINNIXD_JOB_ID = "forged"\n',
        '[environment.values]\nlowercase = "rejected"\n',
        "[environment.values]\nFIXTURE_NUMBER = 7\n",
        'require = ["SINNIXD_JOB_ID"]\n',
        'require = ["lowercase"]\n',
    ),
)
def test_environment_declarations_reject_forged_or_malformed_names(
    tmp_path: Path, fragment: str
) -> None:
    root = tmp_path / "malformed-environment"
    write_adapter(root)
    descriptor = root / ".agentctl" / "project.toml"
    marker = 'unset = ["PYTHONPATH"]'
    if fragment.startswith("require"):
        descriptor.write_text(
            descriptor.read_text().replace(marker, marker + "\n" + fragment)
        )
    else:
        descriptor.write_text(
            descriptor.read_text().replace(marker, marker + "\n\n" + fragment)
        )
    with pytest.raises(ProjectConfigError, match="environment"):
        ProjectCatalog((root,)).get("fixture")


@pytest.mark.parametrize(
    ("argv", "operation", "payload"),
    (
        (
            (
                "agentctl",
                "job",
                "list",
                "--kind",
                "attested-agent",
                "--kind",
                "declared-operation",
            ),
            "job.list",
            {
                "limit": 100,
                "project_id": None,
                "phases": [],
                "kinds": ["attested-agent", "declared-operation"],
                "active_only": False,
            },
        ),
        (
            (
                "agentctl",
                "job",
                "wait",
                "74e64cb4-282e-4b27-b4b1-af052b268161",
            ),
            "job.wait",
            {
                "job_id": "74e64cb4-282e-4b27-b4b1-af052b268161",
                "timeout_seconds": 30,
            },
        ),
    ),
)
def test_agentctl_supervision_commands_map_to_job_envelopes(
    argv: tuple[str, ...],
    operation: str,
    payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, RequestEnvelope] = {}

    def fake_call(socket_path, request_value):
        captured["request"] = request_value
        return {"schema": 1, "ok": True}

    monkeypatch.setattr(sys, "argv", list(argv))
    monkeypatch.setattr(cli_module, "call", fake_call)

    assert cli_module.main() == 0
    outbound = captured["request"]
    assert outbound.operation == operation
    assert outbound.owner == "systemd-jobs"
    assert dict(outbound.arguments) == payload


@pytest.mark.parametrize("launch_form", (("launch",), ()))
def test_agent_dispatch_and_launch_forms_send_the_same_contract(
    launch_form: tuple[str, ...],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Anti-vacuity: the launch alias failing loudly was retried blind by coordinators."""
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("fixture prompt")
    captured: dict[str, RequestEnvelope] = {}

    def fake_call(socket_path, request_value):
        captured["request"] = request_value
        return {"schema": 1, "ok": True}

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agentctl",
            "agent",
            *launch_form,
            "--project",
            "fixture",
            "--checkout",
            "default",
            "--prompt-file",
            str(prompt_file),
            "--backend",
            "codex",
            "--model",
            "fixture-model",
            "--effort",
            "high",
        ],
    )
    monkeypatch.setattr(cli_module, "call", fake_call)

    assert cli_module.main() == 0
    outbound = captured["request"]
    assert outbound.operation == "job.agent.start"
    assert outbound.arguments["prompt"] == "fixture prompt"
    assert outbound.arguments["backend"] == "codex"


def test_agent_dispatch_carries_coordinator_label(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("fixture prompt")
    captured: dict[str, RequestEnvelope] = {}

    def fake_call(socket_path, request_value):
        captured["request"] = request_value
        return {"schema": 1, "ok": True}

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agentctl",
            "agent",
            "--project",
            "fixture",
            "--checkout",
            "default",
            "--prompt-file",
            str(prompt_file),
            "--backend",
            "codex",
            "--model",
            "fixture-model",
            "--effort",
            "high",
            "--coordinator-label",
            "wave-a",
        ],
    )
    monkeypatch.setattr(cli_module, "call", fake_call)

    assert cli_module.main() == 0
    assert captured["request"].arguments["coordinator_label"] == "wave-a"


def test_agent_dispatch_without_required_flags_names_the_alternatives(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["agentctl", "agent", "--project", "fixture"])

    with pytest.raises(SystemExit) as excinfo:
        cli_module.main()

    assert excinfo.value.code == 2
    stderr = capsys.readouterr().err
    assert "--checkout" in stderr
    assert "agent launch|list|status|wait|result" in stderr


def test_attested_agent_environment_carries_agent_actor_attribution(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: agents inheriting the operator's default actor pollute task audit trails."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(
        ProjectCatalog([tmp_path]),
        jobs=jobs,
        native_runner=runner,
    )

    agent = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "prompt": "fixture prompt",
                "backend": "codex",
                "model": "fixture",
                "effort": "high",
                "credential_profile": "subscription",
                "timeout_seconds": 60,
                "result": "last-message",
            },
            "agent-control",
        )
    )
    shell = service.dispatch(
        request(
            "job.shell.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "argv": ["printf", "shell"],
                "cwd": ".",
                "timeout_seconds": 60,
                "result": "exit-status",
            },
            "operator",
        )
    )

    assert agent.ok and shell.ok
    agent_job_id = agent.payload.inline["job_id"]
    agent_keys = service.jobs.store.load(agent_job_id).spec.environment_keys
    shell_keys = service.jobs.store.load(
        shell.payload.inline["job_id"]
    ).spec.environment_keys
    assert "BEADS_ACTOR" in agent_keys
    assert "BEADS_ACTOR" not in shell_keys
    agent_environment = queue_launch_input(jobs, agent_job_id)["environment"]
    assert agent_environment["BEADS_ACTOR"] == f"agent-{agent_job_id}"


def test_descriptor_declared_actor_overrides_the_per_job_attribution(
    tmp_path: Path,
) -> None:
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'unset = ["PYTHONPATH"]',
            'unset = ["PYTHONPATH"]\n\n[environment.values]\n'
            'BEADS_ACTOR = "fixture-fleet"\n',
        )
    )
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(
        ProjectCatalog([tmp_path]),
        jobs=jobs,
        native_runner=runner,
    )

    agent = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "prompt": "fixture prompt",
                "backend": "codex",
                "model": "fixture",
                "effort": "high",
                "credential_profile": "subscription",
                "timeout_seconds": 60,
                "result": "last-message",
            },
            "agent-control",
        )
    )

    assert agent.ok and agent.payload is not None
    agent_environment = queue_launch_input(jobs, agent.payload.inline["job_id"])[
        "environment"
    ]
    assert agent_environment["BEADS_ACTOR"] == "fixture-fleet"


def test_path_grammar_accepts_files_and_refuses_traversal() -> None:
    """Free text reaches a declared operation only as a file path.

    Anti-vacuity: dropping the per-component traversal lookahead makes the
    ``..`` cases pass, and widening the character class admits spaces.
    """
    grammar = projects._PARAMETER_GRAMMARS["path"]

    for accepted in ("/realm/tmp/work/body.md", "body.md", "a/b/c.txt"):
        assert grammar.fullmatch(accepted) is not None, accepted

    for refused in (
        "..",
        "../etc/passwd",
        "a/../b",
        "/realm/./x",
        "has space.md",
        "a//b",
        "",
    ):
        assert grammar.fullmatch(refused) is None, refused


def test_agentctl_expands_an_unambiguous_job_id_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fleet output and events print abbreviated ids; the CLI must accept them.

    Anti-vacuity: returning the input unchanged makes the first assertion red,
    and dropping the ambiguity guard makes the second one pass instead of exit.
    """
    jobs = tmp_path / "jobs"
    jobs.mkdir(parents=True)
    full = "37843efb-0094-46ff-a8ab-974b54eff9d2"
    (jobs / f"{full}.json").write_text("{}")
    monkeypatch.setattr(cli_module, "default_state_dir", lambda: tmp_path)

    assert cli_module._expand_job_id("37843efb") == full
    assert cli_module._expand_job_id(full) == full

    (jobs / "37843efb-0000-0000-0000-000000000000.json").write_text("{}")
    with pytest.raises(SystemExit):
        cli_module._expand_job_id("37843efb")


def test_project_catalog_takes_one_bad_descriptor_out_of_service(
    tmp_path: Path,
) -> None:
    """One repository's descriptor must not decide the daemon's availability.

    Anti-vacuity: dropping the per-root try in the tolerant path makes the
    good project unreachable, and dropping the re-raise makes the strict
    construction silently succeed.
    """
    good = tmp_path / "good"
    good.mkdir()
    write_adapter(good, project_id="good")
    bad = tmp_path / "bad"
    (bad / ".agentctl").mkdir(parents=True)
    (bad / ".agentctl" / "project.toml").write_text("schema = 1\n[project]\n")

    catalog = projects.ProjectCatalog([good, bad], tolerant=True)
    assert [row["id"] for row in catalog.list()] == ["good"]
    assert str(bad) in catalog.unavailable

    with pytest.raises(projects.ProjectConfigError):
        projects.ProjectCatalog([good, bad])


def test_worktree_removal_stops_the_type_daemon(tmp_path: Path) -> None:
    """The daemon outlives its worktree unless something stops it.

    Anti-vacuity: without the call the daemon survives the directory it
    describes, which is how ten of them held 9.2 GB on this machine.
    """
    from sinnixd.workspaces import _stop_type_daemon

    worktree = tmp_path / "ws"
    (worktree / ".venv/bin").mkdir(parents=True)
    marker = tmp_path / "called"
    daemon = worktree / ".venv/bin/dmypy"
    daemon.write_text(f'#!/bin/sh\necho "$1" > {marker}\n')
    daemon.chmod(0o755)

    _stop_type_daemon(worktree)
    assert marker.read_text().strip() == "stop"

    # A workspace without a provisioned venv must not raise.
    _stop_type_daemon(tmp_path / "absent")


def test_a_registration_outliving_its_directory_does_not_refuse_every_checkout(
    tmp_path: Path,
) -> None:
    """A prunable worktree is not a usable checkout, and not a reason to refuse the rest.

    Claude Code creates `.claude/worktrees/agent-*` locked and removes the
    directory without pruning, so a repository accumulates these on its own.
    Enumerating them with `resolve(strict=True)` raised a bare FileNotFoundError
    that aborted the whole listing — which is what stopped `campaign run` for an
    entire project.

    Anti-vacuity: drop the guard and this raises instead of listing the
    surviving checkouts.
    """
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    catalog = ProjectCatalog([tmp_path])
    service = SinnixdService(catalog, jobs=generic_jobs(tmp_path))
    survivor = service.workspaces.create(
        project_id="fixture",
        name="survivor",
        branch="feature/survivor",
        base="HEAD",
    )
    doomed = service.workspaces.create(
        project_id="fixture",
        name="doomed",
        branch="feature/doomed",
        base="HEAD",
    )
    shutil.rmtree(doomed["path"])
    assert not Path(doomed["path"]).exists()

    paths = {item.path for item in catalog.checkouts("fixture")}

    assert Path(survivor["path"]) in paths
    assert Path(doomed["path"]) not in paths
    assert tmp_path in paths


def _lane_publish_transport(
    responses: dict[str, object],
) -> tuple[list[str], Callable[..., object]]:
    operations: list[str] = []

    def fake_call(socket_path, request_value):
        operations.append(request_value.operation)
        outcome = responses[request_value.operation]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return operations, fake_call


def _lane_publish_listing() -> dict[str, object]:
    return {
        "schema": 1,
        "ok": True,
        "payload": {
            "value": {
                "workspaces": [
                    {
                        "workspace_id": "11111111-1111-1111-1111-111111111111",
                        "name": "packet-fixture",
                        "project_id": "fixture",
                    }
                ]
            }
        },
    }


def test_lane_publish_reply_names_the_enqueued_job_while_pending(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An enqueued-but-queued harvest is HARVEST_PENDING with the job id, never
    RESULT_INVALID (sinnix-e307)."""
    operations, fake_call = _lane_publish_transport(
        {
            "workspace.list": _lane_publish_listing(),
            "job.start": {
                "schema": 1,
                "ok": True,
                "payload": {"value": {"job_id": "job-e307"}},
            },
            "job.wait": ResponseBudgetExceeded("job.wait", 1.0),
            "job.get": {
                "schema": 1,
                "ok": True,
                "payload": {"value": {"state": {"phase": "queued", "terminal": False}}},
            },
        }
    )
    monkeypatch.setattr(sys, "argv", ["agentctl", "lane", "publish", "packet-fixture"])
    monkeypatch.setattr(cli_module, "call", fake_call)
    assert cli_module.main() == 2
    reply = json.loads(capsys.readouterr().out)
    assert reply["ok"] is False
    assert reply["job_id"] == "job-e307"
    assert reply["phase"] == "queued"
    assert reply["error"]["code"] == "HARVEST_PENDING"
    assert "job-e307" in reply["error"]["message"]
    assert operations == ["workspace.list", "job.start", "job.wait", "job.get"]


def test_lane_publish_start_failure_is_a_typed_step_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed enqueue must name its step; a budget-exhausted listing must not
    masquerade as an unknown workspace (sinnix-e307 silent non-enqueue)."""
    operations, fake_call = _lane_publish_transport(
        {
            "workspace.list": _lane_publish_listing(),
            "job.start": ResponseBudgetExceeded("job.start", 1.0),
        }
    )
    monkeypatch.setattr(sys, "argv", ["agentctl", "lane", "publish", "packet-fixture"])
    monkeypatch.setattr(cli_module, "call", fake_call)
    assert cli_module.main() == 1
    reply = json.loads(capsys.readouterr().out)
    assert reply["ok"] is False
    assert reply["failed_step"] == "job.start"
    assert reply["error"]["code"] == "RESPONSE_BUDGET_EXCEEDED"
    assert "job_id" not in reply
    assert operations == ["workspace.list", "job.start"]


def test_lane_publish_listing_budget_failure_is_not_unknown_workspace(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    operations, fake_call = _lane_publish_transport(
        {"workspace.list": ResponseBudgetExceeded("workspace.list", 1.0)}
    )
    monkeypatch.setattr(sys, "argv", ["agentctl", "lane", "publish", "packet-fixture"])
    monkeypatch.setattr(cli_module, "call", fake_call)
    assert cli_module.main() == 1
    reply = json.loads(capsys.readouterr().out)
    assert reply["failed_step"] == "workspace.list"
    assert reply["error"]["code"] == "RESPONSE_BUDGET_EXCEEDED"
    assert "unknown workspace" not in json.dumps(reply)
    assert operations == ["workspace.list"]


def test_lane_publish_success_reply_carries_job_identity(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    operations, fake_call = _lane_publish_transport(
        {
            "workspace.list": _lane_publish_listing(),
            "job.start": {
                "schema": 1,
                "ok": True,
                "payload": {"value": {"job_id": "job-ok"}},
            },
            "job.wait": {"schema": 1, "ok": True},
            "job.get": {
                "schema": 1,
                "ok": True,
                "payload": {
                    "value": {"state": {"phase": "succeeded", "terminal": True}}
                },
            },
            "job.result": {
                "schema": 1,
                "ok": True,
                "payload": {"value": {"value": {"outcome": "HARVEST_OK"}}},
            },
        }
    )
    monkeypatch.setattr(sys, "argv", ["agentctl", "lane", "publish", "packet-fixture"])
    monkeypatch.setattr(cli_module, "call", fake_call)
    assert cli_module.main() == 0
    reply = json.loads(capsys.readouterr().out)
    assert reply["ok"] is True
    assert reply["job_id"] == "job-ok"
    assert reply["outcome"] == "HARVEST_OK"
    assert operations[-1] == "job.result"


def _listing_record(job_id: str, *, terminal: bool, phase: str) -> SimpleNamespace:
    return SimpleNamespace(
        job_id=job_id,
        created_at=f"2026-08-31T0{job_id[-1]}:00:00+00:00",
        state={"phase": phase, "terminal": terminal},
        spec=SimpleNamespace(
            kind="declared-operation",
            project_id="fixture",
            operation="harvest",
            principal="operator",
        ),
    )


class _RowFaultJobs(jobs_module.GenericJobs):
    """GenericJobs with enrichment stubs that fail for chosen job ids."""

    def __init__(self, records, fail_ids):  # noqa: D107 - test stub
        self._records = records
        self._fail_ids = fail_ids
        self.store = SimpleNamespace(
            list=lambda: list(records),
            active_records=lambda: [r for r in records if not r.state["terminal"]],
        )

    def get(self, job_id):
        if job_id in self._fail_ids:
            raise jobs_module.JobRecordError("stale checkout binding")
        record = next(r for r in self._records if r.job_id == job_id)
        return {"job_id": job_id, "state": dict(record.state)}

    def _public(self, record, state):
        if record.job_id in self._fail_ids:
            raise OSError("result artifact unreadable")
        return {"job_id": record.job_id, "state": dict(state)}


def test_job_listing_degrades_one_bad_row_and_keeps_the_window() -> None:
    """One stale row degrades alone; neighbors and membership survive
    (sinnix-8rch). Anti-vacuity: rendering rows without the per-row boundary
    aborts this exact window on the JobRecordError."""
    records = [
        _listing_record("job-1", terminal=True, phase="succeeded"),
        _listing_record("job-2", terminal=False, phase="running"),
        _listing_record("job-3", terminal=True, phase="failed"),
    ]
    jobs = _RowFaultJobs(records, fail_ids={"job-2"})
    listing = jobs.list()
    rows = {row["job_id"]: row for row in listing["jobs"]}
    assert set(rows) == {"job-1", "job-2", "job-3"}
    assert "degraded" not in rows["job-1"]
    assert "degraded" not in rows["job-3"]
    degraded = rows["job-2"]["degraded"]
    assert degraded["enrichment"] == "reconciliation"
    assert "stale checkout binding" in degraded["error"]
    assert rows["job-2"]["state"]["phase"] == "running"
    assert listing["total"] == 3


def test_job_listing_degrades_terminal_render_failures_independently() -> None:
    records = [
        _listing_record("job-1", terminal=True, phase="succeeded"),
        _listing_record("job-2", terminal=True, phase="succeeded"),
    ]
    jobs = _RowFaultJobs(records, fail_ids={"job-1"})
    listing = jobs.list()
    rows = {row["job_id"]: row for row in listing["jobs"]}
    assert rows["job-1"]["degraded"]["enrichment"] == "render"
    assert "degraded" not in rows["job-2"]


def test_job_get_keeps_typed_deep_inspection_for_a_bad_row() -> None:
    """Listing degrades; get still raises the typed error (sinnix-8rch AC3)."""
    records = [_listing_record("job-2", terminal=False, phase="running")]
    jobs = _RowFaultJobs(records, fail_ids={"job-2"})
    with pytest.raises(jobs_module.JobRecordError):
        jobs.get("job-2")


def _resolver_workspaces(records) -> SimpleNamespace:
    return SimpleNamespace(store=SimpleNamespace(records=lambda: list(records)))


def _workspace_record(workspace_id: str, name: str, branch: str) -> WorkspaceRecord:
    return WorkspaceRecord(
        workspace_id=workspace_id,
        project_id="fixture",
        name=name,
        path=Path(f"/tmp/{name}"),
        branch=branch,
        base="origin/master",
        created_at="2026-08-31T00:00:00+00:00",
    )


def test_workspace_reference_resolves_every_printed_identifier() -> None:
    """UUID, name, and unique branch all resolve to the same record
    (sinnix-vb1u). Anti-vacuity: UUID-only lookup raises KeyError for the
    name and branch forms."""
    from sinnixd.workspaces import GitWorkspaces

    record = _workspace_record(
        "11111111-1111-1111-1111-111111111111",
        "packet-fixture",
        "feature/packet/fixture",
    )
    other = _workspace_record(
        "22222222-2222-2222-2222-222222222222",
        "packet-other",
        "feature/packet/other",
    )
    stub = _resolver_workspaces([record, other])
    for reference in (record.workspace_id, record.name, record.branch):
        assert GitWorkspaces._record(stub, reference) is record


def test_ambiguous_workspace_reference_refuses_with_candidates() -> None:
    from sinnixd.workspaces import GitWorkspaces

    first = _workspace_record(
        "11111111-1111-1111-1111-111111111111", "packet-dup", "feature/one"
    )
    second = _workspace_record(
        "22222222-2222-2222-2222-222222222222", "packet-dup", "feature/two"
    )
    stub = _resolver_workspaces([first, second])
    with pytest.raises(WorkspaceError) as refused:
        GitWorkspaces._record(stub, "packet-dup")
    message = str(refused.value)
    assert first.workspace_id in message
    assert second.workspace_id in message
    with pytest.raises(KeyError):
        GitWorkspaces._record(stub, "packet-absent")


def test_agent_jobs_may_run_four_hours_and_launch_defaults_to_the_ceiling() -> None:
    """Real lanes routinely exceed an hour; the old 1h ceiling forced serial
    relaunch rounds. Anti-vacuity: restoring the 3600 ceiling fails both the
    validity assertion and the argparse default."""
    from sinnixd.limits import (
        MAX_AGENT_TIMEOUT_SECONDS,
        maximum_timeout_seconds,
        valid_timeout_seconds,
    )

    assert MAX_AGENT_TIMEOUT_SECONDS == 14_400
    assert maximum_timeout_seconds("attested-agent") == 14_400
    assert valid_timeout_seconds(14_400, kind="attested-agent")
    assert not valid_timeout_seconds(14_401, kind="attested-agent")
    arguments = cli_module.parser().parse_args(
        [
            "agent",
            "launch",
            "--project",
            "fixture",
            "--checkout",
            "worktree-0000000000000000",
            "--prompt-file",
            "/dev/null",
            "--backend",
            "codex",
            "--model",
            "fixture-model",
            "--effort",
            "high",
        ]
    )
    assert arguments.timeout_seconds == 14_400


def test_agent_launch_prepends_the_generated_environment_preamble(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bare continuation prompt gains the declared environment wrapper;
    packet-compiled prompts pass through untouched (sinnix-05rs).
    Anti-vacuity: sending the prompt file verbatim fails the wrapper
    assertion."""
    (tmp_path / ".agentctl").mkdir()
    (tmp_path / ".agentctl" / "project.toml").write_text(
        'schema = 1\n[project]\nid = "fixture"\n'
        "[environment]\n"
        'command = ["nix", "develop", "--accept-flake-config", "--command"]\n'
    )
    monkeypatch.setattr(cli_module, "resolve_project_root", lambda project: tmp_path)
    captured: dict[str, Any] = {}

    def fake_call(socket_path, request_value):
        captured["prompt"] = request_value.arguments["prompt"]
        return {
            "schema": 1,
            "ok": True,
            "payload": {"value": {"job_id": "job-preamble"}},
        }

    monkeypatch.setattr(cli_module, "call", fake_call)
    plain = tmp_path / "prompt.md"
    plain.write_text("Continue the bead.")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agentctl",
            "agent",
            "launch",
            "--project",
            "fixture",
            "--checkout",
            "worktree-0000000000000000",
            "--prompt-file",
            str(plain),
            "--backend",
            "codex",
            "--model",
            "fixture-model",
            "--effort",
            "high",
        ],
    )
    assert cli_module.main() == 0
    assert captured["prompt"].startswith("# Continuation preamble (generated)")
    assert "nix develop --accept-flake-config --command <command>" in captured["prompt"]
    assert captured["prompt"].endswith("Continue the bead.")

    packet = tmp_path / "packet.md"
    packet.write_text("# Dispatch packet (v2)\n\ncompiled contents")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agentctl",
            "agent",
            "launch",
            "--project",
            "fixture",
            "--checkout",
            "worktree-0000000000000000",
            "--prompt-file",
            str(packet),
            "--backend",
            "codex",
            "--model",
            "fixture-model",
            "--effort",
            "high",
        ],
    )
    assert cli_module.main() == 0
    assert captured["prompt"] == "# Dispatch packet (v2)\n\ncompiled contents"


def test_sub_hourly_timers_are_not_persistent() -> None:
    """Anti-vacuity: a persistent transient timer fires on registration, so
    every deploy ran the ten-minute sweep an extra time (2026-09-01)."""
    from sinnixd.jobs import timer_persistent

    assert timer_persistent("*:0/10") is False
    assert timer_persistent("*-*-* *:15:00") is False
    assert timer_persistent("*-*-* 03:17:00") is True
    assert timer_persistent("hourly") is True
    assert timer_persistent("weekly") is True


def test_default_checkout_operations_refuse_lane_worktrees(tmp_path: Path) -> None:
    """Anti-vacuity: an agent in packet-polylogue-nrlsl queued a 16 GB
    complete-corpus run in its own worktree (2026-09-02 00:44Z)."""
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'description = "Run fixture checks"\n',
            'description = "Run fixture checks"\ncheckout = "default"\n',
        )
    )
    initialize_git_checkout(tmp_path)
    other_checkout = tmp_path.parent / "lane-checkout"
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "worktree",
            "add",
            "--quiet",
            "--detach",
            str(other_checkout),
            "HEAD",
        ],
        check=True,
    )
    catalog = ProjectCatalog([tmp_path])
    project = catalog.get("fixture")
    operation = project.operation("check")
    assert operation.checkout == "default"
    lane = next(
        checkout
        for checkout in catalog.checkouts("fixture")
        if checkout.path == other_checkout.resolve()
    )
    jobs = generic_jobs(tmp_path.parent / "job-state")

    with pytest.raises(ValueError, match="runs only on the default checkout"):
        jobs.start_declared(
            project=project,
            operation=operation,
            correlation_id="lane",
            parameters={},
            checkout=lane,
        )
    started = jobs.start_declared(
        project=project,
        operation=operation,
        correlation_id="main",
        parameters={},
        checkout=catalog.checkout("fixture", "default"),
    )
    assert started["job_id"]


def test_operation_checkout_policy_is_closed(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'description = "Run fixture checks"\n',
            'description = "Run fixture checks"\ncheckout = "lane"\n',
        )
    )
    with pytest.raises(ProjectConfigError, match="operations.check.checkout"):
        ProjectCatalog([tmp_path])


def test_wait_blocks_in_pueue_until_the_task_is_terminal(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: sampling the record instead of waiting returns `running`.

    The fake only finishes the task when someone actually waits on it, so a
    wait that polls observation returns the non-terminal phase and fails here.
    """
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={"PATH": ""},
    )
    task_id = fake_task_id(jobs, started["job_id"])
    fake_pueue.running(task_id)
    fake_pueue.finish_when_waited(task_id, lambda pueue: pueue.succeed(task_id))

    status = jobs.wait(started["job_id"], timeout_seconds=5)

    assert fake_pueue.waited == [task_id]
    assert status["state"]["terminal"]
    assert status["state"]["phase"] == "succeeded"
    assert "wait_timed_out" not in status


def test_wait_reports_a_timeout_without_claiming_a_terminal_phase(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={"PATH": ""},
    )
    fake_pueue.running(fake_task_id(jobs, started["job_id"]))

    status = jobs.wait(started["job_id"], timeout_seconds=1)

    assert status["wait_timed_out"] is True
    assert status["state"]["phase"] == "running"
    assert not status["state"]["terminal"]


def test_an_unknown_pool_refuses_the_launch_and_names_the_repair(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """A group pueue does not have is a configuration defect; retrying cannot fix it.

    Anti-vacuity: treating it as a transient launch error leaves the job
    non-terminal and silent, which is how the first live job reported nothing.
    """
    del fake_pueue.groups["interactive"]
    jobs = generic_jobs(tmp_path)

    started = jobs.start_foreground(
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={"PATH": ""},
    )

    assert started["state"]["terminal"]
    assert started["state"]["phase"] == "launch-failed"
    message = started["state"]["error"]["message"]
    assert "interactive" in message
    assert "pueue group add interactive" in message


def test_a_launch_error_survives_re_observation(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: rebuilding state from an absent task dropped the only
    account of why the job never started, leaving a bare launch-unknown."""
    fake_pueue.fail_add = True
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={"PATH": ""},
    )
    assert started["state"]["phase"] == "launch-unknown"

    observed = jobs.get(started["job_id"])

    assert observed["state"]["phase"] == "launch-unknown"
    assert observed["state"]["error"] == started["state"]["error"]


def test_status_names_every_declared_pool_pueue_cannot_provide(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: without this, a missing group is discovered by a failed job.

    The fixture's operations name `normal`; removing the group must surface in
    status with the operations that need it and the command that repairs it.
    """
    write_adapter(tmp_path)
    del fake_pueue.groups["normal"]
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))

    status = service.dispatch(request("runtime.status", "sinnixd", {}, "operator"))

    assert status.ok and status.payload is not None
    missing = status.payload.inline["queue"]["missing_pools"]
    assert [entry["pool"] for entry in missing] == ["normal"]
    assert missing[0]["repair"] == "pueue group add normal"
    assert missing[0]["declared_by"]


def test_cancelling_a_queued_task_removes_it_from_the_queue(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """Anti-vacuity: pueue kill does nothing to a task that has not started.

    Without the removal the task keeps its slot and runs after its cancellation
    was reported, which is how seventeen verify_affected jobs ran post-cancel.
    """
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={"PATH": ""},
    )
    task_id = fake_task_id(jobs, started["job_id"])
    fake_pueue.queue(task_id)

    response = jobs.cancel(started["job_id"], reason="operator")

    assert response["cancel_requested"] is True
    assert fake_pueue.removed == [task_id]
    assert fake_pueue.task(task_id) is None
    assert response["state"]["phase"] == "cancelled"
    assert response["state"]["terminal"] is True
    assert jobs.get(started["job_id"])["state"]["phase"] == "cancelled"


def test_cancelling_a_running_task_kills_it_rather_than_dequeueing(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={"PATH": ""},
    )
    task_id = fake_task_id(jobs, started["job_id"])
    fake_pueue.running(task_id)

    jobs.cancel(started["job_id"], reason="operator")

    # Killing stops the process group; removing takes the slot back. A running
    # task needs both, or its slot stays claimed by a task that is gone.
    assert fake_pueue.killed == [task_id]
    assert fake_pueue.removed == [task_id]


def test_a_killed_job_still_reads_its_output_from_pueue(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    """A timeout or cancel must leave readable evidence.

    Anti-vacuity: the wrapper is SIGKILLed, so its own artifact can be empty;
    without the fallback `job logs` raises and the failure has no account.
    """
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={"PATH": ""},
    )
    task_id = fake_task_id(jobs, started["job_id"])
    record = jobs.store.load(started["job_id"])
    record.log_path.write_bytes(b"")
    fake_pueue.set_log(task_id, "partial output before the kill\n")
    fake_pueue.fail(task_id, exit_code=queue_run.TIMEOUT_EXIT_CODE)

    assert jobs.get(started["job_id"])["state"]["phase"] == "timeout"
    assert "partial output" in jobs.logs(started["job_id"])["content"]
