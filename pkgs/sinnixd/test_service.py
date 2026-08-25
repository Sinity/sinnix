from __future__ import annotations

import json
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import sinnixd.api as api_module
import sinnixd.cli as cli_module
import sinnixd.jobs as jobs_module
from sinnix_mcp import ErrorCode, OpaquePayload, RequestEnvelope, ResponseEnvelope, SinnixRef, SourceBinding
from sinnix_mcp.execution import EnvironmentProfile, ExecutionResult, OwnerExecution

from sinnixd.api import (
    CONNECTION_TIMEOUT_SECONDS,
    CONTROL_OPERATION_RESPONSE_TIMEOUT_SECONDS,
    MAX_JSON_RPC_ERROR_MESSAGE_BYTES,
    ProtocolError,
    WAIT_TRANSPORT_MARGIN_SECONDS,
    SinnixdClient,
    SinnixdClientError,
    UnixSocketServer,
    _response_timeout_seconds,
    call,
    receive_frame,
    send_frame,
)
from sinnixd.environment import build_environment
from sinnixd.delivery import DeliveryError, GitHubDelivery
from sinnixd.jobs import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_LOG_ARTIFACT_BYTES,
    SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    GenericJobSpec,
    GenericJobStore,
    GenericJobs,
    JobRecordError,
    JobResultError,
    JobResultLimitError,
    SystemdJobError,
    SystemdJobTimeout,
    UserSystemdJobs,
    capture_executable,
    capture_main,
)
from sinnixd.limits import MAX_DECLARED_OPERATION_TIMEOUT_SECONDS
from sinnixd.owner_adapters import DeclaredOwnerAdapters, OwnerAdapterError
from sinnixd.projects import ProjectCatalog, ProjectConfigError, RegisteredCheckout, parse_worktree_records
from sinnixd.runner import (
    RunnerError,
    _exec_shell,
    _require_environment,
    _revalidate_checkout,
    _run_declared,
    _seal_packet_result,
)
from sinnixd.service import SinnixdService
from sinnixd.tasks import (
    BeadsCommandBoundary,
    FLOCK_EXECUTABLE,
    MAX_TASK_OUTPUT_BYTES,
    TASK_MUTATION_JOURNAL_DIRECTORY,
    TaskAuthority,
    TaskError,
    TaskMutationJournal,
    TaskService,
    reconcile_task_mutations,
)
from sinnixd.workspaces import GitWorkspaces, WorkspaceError, WorkspaceStore


@pytest.mark.parametrize(("ok", "expected"), ((True, 0), (False, 1)))
def test_agentctl_exit_status_matches_response_envelope(
    ok: bool, expected: int, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
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
            return {"jsonrpc": "2.0", "id": "not-the-request-id", "result": {"ok": True}}
        if shape == "unexpected-response-field":
            return {"jsonrpc": "2.0", "id": raw["id"], "result": {"ok": True}, "extra": "rejected"}
        message = "server-secret" if shape == "unexpected-error-field" else "x" * (MAX_JSON_RPC_ERROR_MESSAGE_BYTES + 1)
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

    with pytest.raises(SinnixdClientError, match="^sinnixd is unavailable$"):
        SinnixdClient(socket_path).dispatch(request_value)

    thread.join(timeout=1)
    assert not thread.is_alive()


@pytest.mark.parametrize(
    ("argv", "operation", "payload"),
    (
        (("agentctl", "task", "list", "fixture", "--status", "open"), "task.list", {"project_id": "fixture", "status": "open", "limit": 100}),
        (("agentctl", "task", "get", "fixture", "fixture-1"), "task.get", {"project_id": "fixture", "task_id": "fixture-1"}),
        (("agentctl", "task", "create", "fixture", "typed title", "--description", "typed description", "--type", "task", "--priority", "2", "--label", "area:agentctl", "--parent", "fixture-parent", "--dependency", "depends-on:fixture-blocker", "--request-id", "request-1"), "task.create", {"project_id": "fixture", "title": "typed title", "description": "typed description", "issue_type": "task", "priority": 2, "labels": ["area:agentctl"], "parent_task_id": "fixture-parent", "dependencies": [{"relation": "depends-on", "task_id": "fixture-blocker"}]}),
        (("agentctl", "task", "claim", "fixture", "fixture-1", "--request-id", "request-1"), "task.claim", {"project_id": "fixture", "task_id": "fixture-1"}),
        (("agentctl", "task", "note", "fixture", "fixture-1", "note", "--request-id", "request-1"), "task.note", {"project_id": "fixture", "task_id": "fixture-1", "text": "note"}),
        (("agentctl", "task", "relate", "fixture", "fixture-1", "fixture-2", "--request-id", "request-1"), "task.relate", {"project_id": "fixture", "task_id": "fixture-1", "related_task_id": "fixture-2"}),
        (("agentctl", "task", "complete", "fixture", "fixture-1", "--reason", "done", "--merge-sha", "a" * 40, "--request-id", "request-1"), "task.complete", {"project_id": "fixture", "task_id": "fixture-1", "reason": "done", "merge_sha": "a" * 40}),
        (("agentctl", "task", "release", "fixture", "fixture-1", "--if-assignee", "worker", "--request-id", "request-1"), "task.release", {"project_id": "fixture", "task_id": "fixture-1", "if_assignee": "worker"}),
        (("agentctl", "task", "reconcile", "fixture"), "task.reconcile", {"project_id": "fixture"}),
        (("agentctl", "task", "snapshot", "fixture"), "task.snapshot", {"project_id": "fixture"}),
    ),
)
def test_agentctl_task_commands_map_to_task_envelopes(
    argv: tuple[str, ...], operation: str, payload: dict[str, object], monkeypatch: pytest.MonkeyPatch
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
    assert outbound.owner == "task-backend"
    assert outbound.principal == "operator"
    assert dict(outbound.arguments) == payload
    expected_key = "request-1" if operation in {"task.create", "task.claim", "task.note", "task.relate", "task.complete", "task.release"} else None
    assert outbound.idempotency_key == expected_key


@pytest.mark.parametrize(
    ("command", "extra_args"),
    (("get", ()), ("status", ()), ("status", ("--json",))),
)
def test_agentctl_job_status_aliases_job_get(
    command: str, extra_args: tuple[str, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, RequestEnvelope] = {}

    def fake_call(socket_path, request_value):
        captured["request"] = request_value
        return {"schema": 1, "ok": True}

    monkeypatch.setattr(sys, "argv", ["agentctl", "job", command, "job-1", *extra_args])
    monkeypatch.setattr(cli_module, "call", fake_call)

    assert cli_module.main() == 0
    assert captured["request"].operation == "job.get"
    assert captured["request"].arguments == {"job_id": "job-1"}


def test_agentctl_task_mutations_require_a_stable_request_id() -> None:
    with pytest.raises(SystemExit):
        cli_module.parser().parse_args(["task", "claim", "fixture", "fixture-1"])
    with pytest.raises(SystemExit):
        cli_module.parser().parse_args(["task", "complete", "fixture", "fixture-1", "--request-id", "request-1"])
    with pytest.raises(SystemExit):
        cli_module.parser().parse_args(["task", "create", "fixture", "title", "--description", "body", "--type", "task", "--priority", "2"])
    with pytest.raises(SystemExit):
        cli_module.parser().parse_args(["task", "create", "fixture", "title", "--description", "body", "--type", "task", "--priority", "5", "--request-id", "request-1"])


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
            "--cursor",
            "next-page",
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
        "cursor": "next-page",
        "project_id": "polylogue",
        "phases": ["queued", "running"],
        "active_only": True,
    }


def test_agentctl_task_list_preserves_cursor_and_order_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, RequestEnvelope] = {}

    def fake_call(socket_path, request_value):
        captured["request"] = request_value
        return {"schema": 1, "ok": True}

    monkeypatch.setattr(
        sys,
        "argv",
        ["agentctl", "task", "list", "fixture", "--limit", "2", "--cursor", "cursor-fixture", "--sort", "id", "--reverse"],
    )
    monkeypatch.setattr(cli_module, "call", fake_call)

    assert cli_module.main() == 0
    outbound = captured["request"]
    assert dict(outbound.arguments) == {
        "project_id": "fixture",
        "limit": 2,
        "cursor": "cursor-fixture",
        "order": {"field": "id", "reverse": True},
    }


def test_agentctl_workspace_dispose_maps_to_a_typed_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, RequestEnvelope] = {}

    def fake_call(socket_path, request_value):
        captured["request"] = request_value
        return {"schema": 1, "ok": True}

    monkeypatch.setattr(sys, "argv", ["agentctl", "workspace", "dispose", "workspace-1"])
    monkeypatch.setattr(cli_module, "call", fake_call)

    assert cli_module.main() == 0
    outbound = captured["request"]
    assert outbound.operation == "workspace.dispose"
    assert outbound.owner == "git-workspaces"
    assert outbound.principal == "agent-control"
    assert dict(outbound.arguments) == {"workspace_id": "workspace-1"}


def test_agentctl_workspace_finish_integrated_maps_target_to_a_typed_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, RequestEnvelope] = {}

    def fake_call(socket_path, request_value):
        captured["request"] = request_value
        return {"schema": 1, "ok": True}

    monkeypatch.setattr(
        sys,
        "argv",
        ["agentctl", "workspace", "finish-integrated", "workspace-1", "--target", "abc123"],
    )
    monkeypatch.setattr(cli_module, "call", fake_call)

    assert cli_module.main() == 0
    outbound = captured["request"]
    assert outbound.operation == "workspace.finish-integrated"
    assert outbound.owner == "git-workspaces"
    assert outbound.principal == "agent-control"
    assert dict(outbound.arguments) == {"workspace_id": "workspace-1", "target_ref": "abc123"}


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
        ["agentctl", "job", "start", "fixture", "parameterized", "--parameters-json", '{"package":["xtask","sinexd"],"full":true}'],
    )
    monkeypatch.setattr(cli_module, "call", fake_call)

    assert cli_module.main() == 0
    assert dict(captured["request"].arguments) == {
        "project_id": "fixture",
        "operation": "parameterized",
        "workspace_id": None,
        "parameters": {"package": ["xtask", "sinexd"], "full": True},
    }


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
inherit = ["HOME"]
unset = ["PYTHONPATH"]

[workspace]
provider = "git-worktree"
root = "{root / 'worktrees'}"
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
exclusive_keys = ["fixture:check"]

[operations.service]
description = "Run a fixture development service"
exec = ["fixture-service"]
pool = "normal"
result = "exit"
cache = "none"

[operations.service.service]
readiness = "project-command"
lifetime = "job"

[operations.service.service.ports.http]
environment = "FIXTURE_HTTP_PORT"
range = [41000, 41001]

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


def write_owner_adapter(root: Path) -> None:
    write_adapter(root)
    descriptor = root / ".agentctl" / "project.toml"
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
documentation = "Bounded Polylogue archive status."
"""
    )


@pytest.mark.parametrize(
    "fragment",
    (
        "unknown = true\n",
        "[operations.parameterized.parameters.broken]\ntype = \"integer\"\nflag = \"--broken\"\nmin = 1\n",
        "[operations.parameterized.parameters.unbounded]\ntype = \"string-list\"\nflag = \"--unbounded\"\nmax_items = 4\n",
        "[operations.parameterized.parameters.unknown_string]\ntype = \"string\"\nflag = \"--string\"\nmax_length = 4\ngrammar = \"shell\"\n",
        "[operations.parameterized.parameters.boolean_integer]\ntype = \"integer\"\nflag = \"--integer\"\nmin = true\nmax = 4\n",
        "[operations.parameterized.parameters.empty_enum]\ntype = \"enum\"\nflag = \"--enum\"\nvalues = []\n",
        "[operations.parameterized.parameters.duplicate_enum]\ntype = \"enum\"\nflag = \"--enum\"\nvalues = [\"same\", \"same\"]\n",
        "[operations.parameterized.parameters.unbounded_enum_list]\ntype = \"enum-list\"\nflag = \"--enum-list\"\nvalues = [\"one\"]\n",
        "[operations.parameterized.parameters.duplicate_flag]\ntype = \"string\"\nflag = \"--full\"\nmax_length = 4\n",
        "[operations.verify_closure.parameters.ambiguous]\ntype = \"string\"\nflag = \"--ambiguous\"\nposition = 2\nrequired = true\nmax_length = 4\n",
        "[operations.verify_closure.parameters.optional]\ntype = \"string\"\nposition = 2\nrequired = false\nmax_length = 4\n",
        "[operations.verify_closure.parameters.duplicate_position]\ntype = \"string\"\nposition = 1\nrequired = true\nmax_length = 4\n",
        "[operations.verify_closure.parameters.gapped_position]\ntype = \"string\"\nposition = 3\nrequired = true\nmax_length = 4\n",
        "[operations.verify_closure.parameters.list_position]\ntype = \"string-list\"\nposition = 2\nrequired = true\nmax_items = 1\nmax_length = 4\n",
    ),
)
def test_project_operation_parameter_schema_is_closed_and_bounded(tmp_path: Path, fragment: str) -> None:
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(descriptor.read_text() + fragment)

    with pytest.raises(ProjectConfigError):
        ProjectCatalog([tmp_path])


def test_project_operation_parameter_count_supports_broad_typed_clis(tmp_path: Path) -> None:
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


def test_operation_dependencies_reject_required_parameter_targets(tmp_path: Path) -> None:
    """Anti-vacuity: dependencies have no parameter payload to satisfy required inputs."""
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        + """
[operations.depends_on_required]
description = "Depend on a parameterized operation"
exec = ["fixture-check"]
pool = "normal"
result = "exit"
cache = "none"
dependencies = ["verify_closure"]
"""
    )

    with pytest.raises(ProjectConfigError, match="required parameters.*verify_closure"):
        ProjectCatalog([tmp_path])


def test_required_parameter_operations_reject_dependencies(tmp_path: Path) -> None:
    """Anti-vacuity: required input validation cannot follow dependency launch."""
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        + """
[operations.required_with_dependency]
description = "Run a required operation after a dependency"
exec = ["fixture-check"]
pool = "normal"
result = "exit"
cache = "none"
dependencies = ["check"]

[operations.required_with_dependency.parameters.bead_id]
type = "string"
position = 1
required = true
max_length = 128
grammar = "safe-token"
"""
    )

    with pytest.raises(ProjectConfigError, match="cannot declare dependencies.*required_with_dependency"):
        ProjectCatalog([tmp_path])


@pytest.mark.parametrize(
    "value",
    ("true", '"3600"', "0", "-1", str(MAX_DECLARED_OPERATION_TIMEOUT_SECONDS + 1)),
)
def test_declared_operation_timeout_must_be_a_positive_bounded_integer(tmp_path: Path, value: str) -> None:
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'exclusive_keys = ["fixture:check"]',
            f'timeout_seconds = {value}\nexclusive_keys = ["fixture:check"]',
        )
    )

    with pytest.raises(ProjectConfigError, match="operations.check.timeout_seconds"):
        ProjectCatalog([tmp_path])


def test_declared_operation_timeout_defaults_and_survives_launch_recovery(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'exclusive_keys = ["fixture:check"]',
            f'timeout_seconds = {MAX_DECLARED_OPERATION_TIMEOUT_SECONDS}\nexclusive_keys = ["fixture:check"]',
        )
    )
    catalog = ProjectCatalog([tmp_path])
    check = catalog.get("fixture").operation("check")
    assert check.timeout_seconds == MAX_DECLARED_OPERATION_TIMEOUT_SECONDS
    assert catalog.get("fixture").operation("parameterized").timeout_seconds == DEFAULT_TIMEOUT_SECONDS
    assert check.catalog_row()["timeout_seconds"] == MAX_DECLARED_OPERATION_TIMEOUT_SECONDS

    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(catalog, jobs=jobs)
    response = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "check"}))
    assert response.ok and response.payload is not None
    launched = response.payload.inline
    assert launched["timeout_seconds"] == MAX_DECLARED_OPERATION_TIMEOUT_SECONDS
    assert systemd.started[0]["timeout_seconds"] == MAX_DECLARED_OPERATION_TIMEOUT_SECONDS

    record = jobs.store.load(launched["job_id"])
    assert record.spec.timeout_seconds == MAX_DECLARED_OPERATION_TIMEOUT_SECONDS
    recovered = GenericJobs(systemd, jobs.store, wait_poll_seconds=0.001)
    assert recovered.get(launched["job_id"])["timeout_seconds"] == MAX_DECLARED_OPERATION_TIMEOUT_SECONDS
    assert GenericJobSpec(
        kind="foreground-command", command=("fixture",), working_directory=str(tmp_path), environment={}
    ).timeout_seconds == DEFAULT_TIMEOUT_SECONDS


@pytest.mark.parametrize(
    "replacement",
    (
        'readiness = "product-probe"',
        'lifetime = "daemon"',
        'environment = "SINNIXD_JOB_ID"',
        'environment = "HOME"',
        'range = [1023, 1024]',
        'range = [41000, 41256]',
    ),
)
def test_service_declaration_is_closed_and_bounded(tmp_path: Path, replacement: str) -> None:
    """Anti-vacuity: a service descriptor cannot become a caller-controlled launch overlay."""
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    if replacement.startswith("readiness"):
        descriptor.write_text(descriptor.read_text().replace('readiness = "project-command"', replacement))
    elif replacement.startswith("lifetime"):
        descriptor.write_text(descriptor.read_text().replace('lifetime = "job"', replacement))
    elif replacement.startswith("environment"):
        descriptor.write_text(descriptor.read_text().replace('environment = "FIXTURE_HTTP_PORT"', replacement))
    else:
        descriptor.write_text(descriptor.read_text().replace('range = [41000, 41001]', replacement))

    with pytest.raises(ProjectConfigError, match="operations.service.service"):
        ProjectCatalog([tmp_path])


def test_service_lease_is_bounded_public_metadata_and_injects_only_declared_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anti-vacuity: a service lease must reach the generic launch without persisting arbitrary environment input."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)

    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))

    assert started.ok and started.payload is not None
    lease = started.payload.inline["lease"]
    assert lease is not None
    assert lease["id"] == started.payload.inline["job_id"]
    assert lease["host"] == "127.0.0.1"
    assert lease["ports"] == [{"name": "http", "environment": "FIXTURE_HTTP_PORT", "port": 41000}]
    assert systemd.started[0]["environment"]["FIXTURE_HTTP_PORT"] == "41000"
    persisted = (tmp_path / "state" / "jobs" / f"{lease['id']}.json").read_text()
    assert "fixture-service" not in persisted
    assert "FIXTURE_HTTP_PORT" in persisted
    rejected = service.dispatch(
        request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service", "environment": {"SECRET": "value"}})
    )
    assert rejected.error is not None
    assert rejected.error.code.value == "INVALID_ARGUMENT"


def test_declared_service_dependency_supplies_lease_and_unblocks_when_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dependent operation receives its service lease and starts only after the port is bound."""
    port_available = True
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: port_available)
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'exclusive_keys = ["fixture:check"]',
            'exclusive_keys = ["fixture:check"]\ndependencies = ["service"]',
        )
    )
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)

    started = service.dispatch(
        request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "check"})
    )

    assert started.ok and started.payload is not None
    check_id = started.payload.inline["job_id"]
    check_record = jobs.store.load(check_id)
    _, launch_environment = jobs.store.declared_launch(check_id)
    assert launch_environment["FIXTURE_HTTP_PORT"] == "41000"
    assert check_record.state["phase"] == "waiting-dependencies"
    dependency_id = check_record.spec.dependency_job_ids[0]
    dependency_command, dependency_environment = jobs.store.declared_launch(dependency_id)
    assert dependency_command == ("fixture-env", "--command", "fixture-service")
    assert len(systemd.started) == 1

    port_available = False
    jobs.get(check_id)
    assert len(systemd.started) == 1, "a transient port bind is not readiness"

    readiness_file = Path(dependency_environment["SINNIXD_SERVICE_READY_FILE"])
    readiness_file.write_text(f"{dependency_id}\n")
    jobs.get(check_id)
    check_command, _ = jobs.store.declared_launch(check_id)
    assert check_command == ("fixture-env", "--command", "fixture-check")
    assert len(systemd.started) == 2


def test_live_service_leases_never_share_a_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anti-vacuity: two live declared jobs must allocate different port slots from one range."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))

    first = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))
    second = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))

    assert first.ok and second.ok and first.payload is not None and second.payload is not None
    assert first.payload.inline["lease"]["ports"][0]["port"] == 41000
    assert second.payload.inline["lease"]["ports"][0]["port"] == 41001


def test_tree_cached_service_coalesces_within_scope_and_retires_terminal_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Service reuse is scoped to its root or registered checkout and never caches a dead success."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        .replace('cache = "none"\n\n[operations.service.service]', 'cache = "tree+environment"\n\n[operations.service.service]')
        .replace("range = [41000, 41001]", "range = [41000, 41003]")
    )
    initialize_git_checkout(tmp_path)
    other_checkout = tmp_path.parent / "other-checkout"
    subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "add", "--quiet", "--detach", str(other_checkout), "HEAD"],
        check=True,
    )

    catalog = ProjectCatalog([tmp_path])
    project = catalog.get("fixture")
    default_checkout = catalog.checkout("fixture", "default")
    other_checkout_record = next(
        checkout for checkout in catalog.checkouts("fixture") if checkout.path == other_checkout.resolve()
    )
    jobs = generic_jobs(tmp_path.parent / "job-state")
    operation = project.operation("service")
    assert operation.cache == "tree+environment"

    def start(checkout: RegisteredCheckout | None) -> dict[str, object]:
        return jobs.start_declared(
            project=project,
            operation=operation,
            correlation_id="service-scope",
            parameters={},
            checkout=checkout,
        )

    root_first = start(None)
    root_record = jobs.store.load(root_first["job_id"])
    assert root_record.spec.cache_key is not None
    assert jobs._admission_state()["active"][root_record.spec.cache_key] == root_first["job_id"]
    root_duplicate = start(None)
    assert root_duplicate["job_id"] == root_first["job_id"]
    assert root_duplicate["coalesced"]
    assert jobs.store.load(root_first["job_id"]).state["subscribers"] == 2
    assert len(list(jobs.store.leases_root.glob("*.json"))) == 1

    default_started = start(default_checkout)
    default_duplicate = start(default_checkout)
    assert default_duplicate["job_id"] == default_started["job_id"]
    assert default_duplicate["coalesced"]
    assert jobs.store.load(default_started["job_id"]).state["subscribers"] == 2
    assert len(list(jobs.store.leases_root.glob("*.json"))) == 2
    other_started = start(other_checkout_record)
    assert default_started["job_id"] != root_first["job_id"]
    assert other_started["job_id"] not in {root_first["job_id"], default_started["job_id"]}
    default_record = jobs.store.load(default_started["job_id"])
    other_record = jobs.store.load(other_started["job_id"])
    assert default_record.spec.cache_key != other_record.spec.cache_key
    assert default_record.spec.lease is not None and other_record.spec.lease is not None
    assert default_record.spec.lease.ports[0].port != other_record.spec.lease.ports[0].port
    assert len(list(jobs.store.leases_root.glob("*.json"))) == 3

    jobs.systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "failed",
        "Result": "exit-code",
        "ExecMainStatus": "1",
        "InvocationID": "fixture-failure",
    }
    failed = jobs.get(root_first["job_id"])
    assert failed["state"]["phase"] == "failed"
    assert not (jobs.store.leases_root / f"{root_first['job_id']}.json").exists()
    root_after_failure = start(None)
    assert root_after_failure["job_id"] != root_first["job_id"]

    jobs.systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
        "InvocationID": "fixture-success",
    }
    succeeded = jobs.get(root_after_failure["job_id"])
    assert succeeded["state"]["phase"] == "succeeded"
    root_after_success = start(None)
    assert root_after_success["job_id"] != root_after_failure["job_id"]
    assert "reused" not in root_after_success
    assert len(list(jobs.store.leases_root.glob("*.json"))) == 3


def test_tree_cached_service_retires_after_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cancelled cached service releases admission and its descriptor-owned lease."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'cache = "none"\n\n[operations.service.service]',
            'cache = "tree+environment"\n\n[operations.service.service]',
        )
    )
    initialize_git_checkout(tmp_path)
    systemd = FakeSystemdJobs(
        properties={
            "LoadState": "loaded",
            "ActiveState": "active",
            "InvocationID": "fixture-invocation",
            "Result": "success",
        }
    )
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)

    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    record = jobs.store.load(job_id)
    assert record.spec.cache_key is not None and record.spec.lease is not None
    cache_key = record.spec.cache_key
    assert jobs._admission_state()["active"][cache_key] == job_id

    cancelled = service.dispatch(request("job.cancel", "systemd-jobs", {"job_id": job_id}))
    assert cancelled.ok and cancelled.payload is not None
    assert cancelled.payload.inline["state"]["phase"] == "cancelled"
    admission = jobs._admission_state()
    assert cache_key not in admission["active"]
    assert cache_key not in admission["cache"]
    assert jobs.store.service_lease_records() == []
    assert not (jobs.store.leases_root / f"{job_id}.json").exists()

    replacement = service.dispatch(
        request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"})
    )
    assert replacement.ok and replacement.payload is not None
    assert replacement.payload.inline["job_id"] != job_id
    assert "reused" not in replacement.payload.inline
    assert replacement.payload.inline["lease"]["ports"][0]["port"] == 41000


def test_tree_cached_service_retires_after_terminal_outcome_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A terminal cancellation-unknown service cannot remain in cache or lease state."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'cache = "none"\n\n[operations.service.service]',
            'cache = "tree+environment"\n\n[operations.service.service]',
        )
    )
    initialize_git_checkout(tmp_path)

    class StopTimesOutThenCollects(FakeSystemdJobs):
        def stop(self, unit: str) -> None:
            self.stopped.append(unit)
            self.properties = {
                "LoadState": "not-found",
                "ActiveState": "inactive",
                "InvocationID": "",
                "Result": "success",
                "ExecMainStatus": "0",
            }
            raise SystemdJobError("fixture stop timeout")

    systemd = StopTimesOutThenCollects(
        properties={
            "LoadState": "loaded",
            "ActiveState": "active",
            "InvocationID": "fixture-invocation",
            "Result": "success",
        }
    )
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)

    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    record = jobs.store.load(job_id)
    assert record.spec.cache_key is not None and record.spec.lease is not None
    cache_key = record.spec.cache_key
    assert jobs._admission_state()["active"][cache_key] == job_id

    cancelled = service.dispatch(request("job.cancel", "systemd-jobs", {"job_id": job_id}))
    assert cancelled.error is not None
    jobs.store.save(replace(jobs.store.load(job_id), cancel_requested_at="2000-01-01T00:00:00+00:00"))

    restarted = GenericJobs(systemd, GenericJobStore(jobs.store.root), wait_poll_seconds=0.001)
    reconciled = restarted.get(job_id)
    assert reconciled["state"]["phase"] == "outcome-unknown"
    assert reconciled["state"]["terminal"]
    admission = restarted._admission_state()
    assert cache_key not in admission["active"]
    assert cache_key not in admission["cache"]
    assert restarted.store.service_lease_records() == []
    assert not (restarted.store.leases_root / f"{job_id}.json").exists()
    assert (restarted.store.leases_root / f"{job_id}.released").exists()

    replacement = SinnixdService(ProjectCatalog([tmp_path]), jobs=restarted).dispatch(
        request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"})
    )
    assert replacement.ok and replacement.payload is not None
    assert replacement.payload.inline["job_id"] != job_id
    assert "reused" not in replacement.payload.inline
    assert replacement.payload.inline["lease"]["ports"][0]["port"] == 41000


def test_tree_cached_services_isolate_distinct_project_roots_in_one_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Identical trees from distinct roots must not coalesce a lease-owning service."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    roots = (tmp_path / "project-a", tmp_path / "project-b")
    for root in roots:
        write_adapter(root)
        descriptor = root / ".agentctl" / "project.toml"
        descriptor.write_text(
            descriptor.read_text()
            .replace(
                'cache = "none"\n\n[operations.service.service]',
                'cache = "tree+environment"\n\n[operations.service.service]',
            )
            .replace(f'root = "{root / "worktrees"}"', 'root = "/fixture-worktrees"')
        )
        initialize_git_checkout(root)

    first_project = ProjectCatalog([roots[0]]).get("fixture")
    second_project = ProjectCatalog([roots[1]]).get("fixture")
    assert GenericJobs._cache_tree(first_project.root) == GenericJobs._cache_tree(second_project.root)
    assert first_project.environment.values() == second_project.environment.values()

    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path / "shared-job-state", systemd)
    first_service = SinnixdService(ProjectCatalog([roots[0]]), jobs=jobs)
    second_service = SinnixdService(ProjectCatalog([roots[1]]), jobs=jobs)
    start_arguments = {"project_id": "fixture", "operation": "service"}
    first = first_service.dispatch(request("job.start", "systemd-jobs", start_arguments))
    second = second_service.dispatch(request("job.start", "systemd-jobs", start_arguments))
    assert first.ok and second.ok and first.payload is not None and second.payload is not None
    first_id = first.payload.inline["job_id"]
    second_id = second.payload.inline["job_id"]
    assert first_id != second_id
    first_record = jobs.store.load(first_id)
    second_record = jobs.store.load(second_id)
    assert first_record.spec.cache_key is not None and second_record.spec.cache_key is not None
    assert first_record.spec.cache_key != second_record.spec.cache_key
    assert first_record.spec.lease is not None and second_record.spec.lease is not None
    assert first_record.spec.lease.ports[0].port == 41000
    assert second_record.spec.lease.ports[0].port == 41001
    assert jobs._admission_state()["active"] == {
        first_record.spec.cache_key: first_id,
        second_record.spec.cache_key: second_id,
    }

    first_duplicate = first_service.dispatch(request("job.start", "systemd-jobs", start_arguments))
    second_duplicate = second_service.dispatch(request("job.start", "systemd-jobs", start_arguments))
    assert first_duplicate.ok and second_duplicate.ok
    assert first_duplicate.payload is not None and second_duplicate.payload is not None
    assert first_duplicate.payload.inline["job_id"] == first_id
    assert second_duplicate.payload.inline["job_id"] == second_id
    assert first_duplicate.payload.inline["coalesced"]
    assert second_duplicate.payload.inline["coalesced"]
    assert len(systemd.started) == 2


def test_terminal_service_jobs_release_port_leases_for_success_failure_timeout_and_cancellation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anti-vacuity: every terminal systemd outcome must make the port available to the next declared service."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)

    for name, properties in (
        ("success", {"LoadState": "loaded", "ActiveState": "inactive", "Result": "success", "ExecMainStatus": "0", "InvocationID": "fixture-invocation"}),
        ("failure", {"LoadState": "loaded", "ActiveState": "failed", "Result": "exit-code", "ExecMainStatus": "1", "InvocationID": "fixture-invocation"}),
        ("timeout", {"LoadState": "loaded", "ActiveState": "failed", "Result": "timeout", "ExecMainStatus": "1", "InvocationID": "fixture-invocation"}),
    ):
        case = tmp_path / name
        write_adapter(case)
        systemd = FakeSystemdJobs()
        jobs = generic_jobs(case, systemd)
        service = SinnixdService(ProjectCatalog([case]), jobs=jobs)
        started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))
        assert started.ok and started.payload is not None
        job_id = started.payload.inline["job_id"]
        systemd.properties = properties
        terminal = service.dispatch(request("job.get", "systemd-jobs", {"job_id": job_id}))
        assert terminal.ok and terminal.payload is not None
        assert terminal.payload.inline["lease"]["state"] == "released"
        assert not (case / "state" / "leases" / f"{job_id}.json").exists()

    case = tmp_path / "cancelled"
    write_adapter(case)
    systemd = FakeSystemdJobs(properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"})
    jobs = generic_jobs(case, systemd)
    service = SinnixdService(ProjectCatalog([case]), jobs=jobs)
    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))
    assert started.ok and started.payload is not None
    cancelled = service.dispatch(request("job.cancel", "systemd-jobs", {"job_id": started.payload.inline["job_id"]}))
    assert cancelled.ok and cancelled.payload is not None
    assert cancelled.payload.inline["state"]["phase"] == "cancelled"
    assert cancelled.payload.inline["lease"]["state"] == "released"
    replacement = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))
    assert replacement.ok and replacement.payload is not None
    assert replacement.payload.inline["lease"]["ports"][0]["port"] == 41000


def test_service_lease_recovery_reconstructs_live_ownership_and_expires_missing_units(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anti-vacuity: restart must rebuild a valid active lease and discard one systemd proves stale."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    lease_path = tmp_path / "state" / "leases" / f"{job_id}.json"
    lease_path.unlink()

    recovered = GenericJobs(systemd, jobs.store, wait_poll_seconds=0.001)
    assert lease_path.exists()
    systemd.properties = {"LoadState": "not-found", "ActiveState": "inactive"}
    _ = GenericJobs(systemd, jobs.store, wait_poll_seconds=0.001)
    assert not lease_path.exists()
    assert recovered.get(job_id)["state"]["terminal"]

    orphan_store = GenericJobStore(tmp_path / "orphan-state")
    operation = ProjectCatalog([tmp_path]).get("fixture").operation("service")
    assert operation.service is not None
    orphan = orphan_store.allocate_service_lease(str(uuid4()), operation.service)
    assert (orphan_store.leases_root / f"{orphan.lease_id}.json").exists()
    _ = GenericJobs(systemd, orphan_store, wait_poll_seconds=0.001)
    assert not (orphan_store.leases_root / f"{orphan.lease_id}.json").exists()


def test_cancelled_outcome_unknown_restart_releases_lease_index_and_reuses_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real service path must reclaim a cancellation-unknown lease after restart."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)

    class StopTimesOutThenCollects(FakeSystemdJobs):
        def stop(self, unit: str) -> None:
            self.stopped.append(unit)
            self.properties = {
                "LoadState": "not-found",
                "ActiveState": "inactive",
                "InvocationID": "",
                "Result": "success",
                "ExecMainStatus": "0",
            }
            raise SystemdJobError("fixture stop timeout")

    systemd = StopTimesOutThenCollects()
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]

    cancelled = service.dispatch(request("job.cancel", "systemd-jobs", {"job_id": job_id}))
    assert cancelled.error is not None
    record = jobs.store.load(job_id)
    jobs.store.save(replace(record, cancel_requested_at="2000-01-01T00:00:00+00:00"))

    restarted = GenericJobs(systemd, GenericJobStore(jobs.store.root), wait_poll_seconds=0.001)
    reconciled = restarted.get(job_id)
    assert reconciled["state"]["phase"] == "outcome-unknown"
    assert reconciled["state"]["terminal"]
    assert reconciled["state"]["outcome_evidence"] == "unit-collected-after-cancellation-grace"
    assert restarted.store.service_lease_records() == []
    assert not (tmp_path / "state" / "leases" / f"{job_id}.json").exists()
    assert (tmp_path / "state" / "leases" / f"{job_id}.released").exists()

    replacement_service = SinnixdService(ProjectCatalog([tmp_path]), jobs=restarted)
    repeated = replacement_service.dispatch(request("job.cancel", "systemd-jobs", {"job_id": job_id}))
    assert repeated.ok and repeated.payload is not None
    assert repeated.payload.inline["already_terminal"]
    assert systemd.stopped == [f"sinnixd-job-{job_id}.service"]
    replacement = replacement_service.dispatch(
        request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"})
    )
    assert replacement.ok and replacement.payload is not None
    assert replacement.payload.inline["lease"]["ports"][0]["port"] == 41000


def test_loaded_outcome_unknown_restart_keeps_uncertain_lease_reserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A loaded unit without terminal evidence must retain its lease and port."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs(
        properties={
            "LoadState": "loaded",
            "ActiveState": "active",
            "InvocationID": "fixture-invocation",
            "Result": "success",
            "ExecMainStatus": "0",
        }
    )
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    record = jobs.store.load(job_id)
    jobs.store.save(
        replace(
            jobs._with_state(
                record,
                {
                    "phase": "outcome-unknown",
                    "terminal": True,
                    "systemd": dict(systemd.properties),
                    "cancellation": {"requested_at": "2000-01-01T00:00:00+00:00", "invocation_id": "fixture-invocation"},
                    "outcome_evidence": "unit-collected-after-cancellation-grace",
                    "observed_at": "fixture",
                },
            ),
            cancel_requested_at="2000-01-01T00:00:00+00:00",
            cancel_requested_invocation_id="fixture-invocation",
        )
    )

    _ = GenericJobs(systemd, GenericJobStore(jobs.store.root), wait_poll_seconds=0.001)
    assert (tmp_path / "state" / "leases" / f"{job_id}.json").exists()
    assert not (tmp_path / "state" / "leases" / f"{job_id}.released").exists()
    operation = ProjectCatalog([tmp_path]).get("fixture").operation("service")
    assert operation.service is not None
    replacement = jobs.store.allocate_service_lease(str(uuid4()), operation.service)
    assert replacement.ports[0].port == 41001


def test_restart_finalizes_admission_for_a_newly_terminal_active_record(tmp_path: Path) -> None:
    """A restart must retire only the active cache entry it observes terminal, not rescan historical jobs."""
    systemd = FakeSystemdJobs(properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"})
    store = GenericJobStore(tmp_path / "state")
    original = GenericJobs(systemd, store, wait_poll_seconds=0.001)
    record = store.create(
        GenericJobSpec(
            kind="declared-operation",
            command=("fixture",),
            working_directory=str(tmp_path),
            environment={},
            project_id="fixture",
            operation="check",
            parameter_digest="0" * 64,
            cache_key="a" * 64,
        )
    )
    store.save(original._with_state(record, {"phase": "submitted", "terminal": False, "observed_at": "fixture"}))
    original._save_admission_state({"schema_version": 1, "active": {record.spec.cache_key: record.job_id}, "cache": {}, "estimates": {}})
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
        "InvocationID": "fixture-invocation",
    }

    restarted = GenericJobs(systemd, original.store, wait_poll_seconds=0.001)

    admission = restarted._admission_state()
    assert record.spec.cache_key not in admission["active"]
    assert admission["cache"][record.spec.cache_key]["job_id"] == record.job_id


def test_recovery_and_get_skip_historical_terminal_jobs_but_release_failed_loaded_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Live failure harness: one active request cannot serialize a terminal corpus through systemd or per-job locks."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)

    class CountingSystemd(FakeSystemdJobs):
        def __init__(self) -> None:
            super().__init__(properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "active-invocation"})
            self.observed: list[str] = []

        def show(self, unit: str, *, timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS) -> dict[str, str]:
            self.observed.append(unit)
            return super().show(unit, timeout_seconds=timeout_seconds)

    store = GenericJobStore(tmp_path / "state")
    terminal_ids: set[str] = set()
    for _ in range(128):
        record = store.create(
            GenericJobSpec(kind="foreground-command", command=("fixture",), working_directory=str(tmp_path), environment={})
        )
        terminal_ids.add(record.job_id)
        store.save(GenericJobs._with_state(record, {"phase": "succeeded", "terminal": True, "observed_at": "fixture"}))
    active = store.create(
        GenericJobSpec(kind="foreground-command", command=("fixture",), working_directory=str(tmp_path), environment={})
    )
    operation = ProjectCatalog([tmp_path]).get("fixture").operation("service")
    assert operation.service is not None
    stale_id = str(uuid4())
    stale_lease = store.allocate_service_lease(stale_id, operation.service)
    stale = store.create(
        GenericJobSpec(
            kind="declared-operation",
            command=("fixture-service",),
            working_directory=str(tmp_path),
            environment={"FIXTURE_HTTP_PORT": str(stale_lease.ports[0].port)},
            project_id="fixture",
            operation="service",
            parameter_digest="0" * 64,
            lease=stale_lease,
        ),
        stale_id,
    )
    store.save(
        GenericJobs._with_state(
            stale,
            {
                "phase": "failed",
                "terminal": True,
                "lease_invocation_id": "failed-invocation",
                "systemd": {
                    "LoadState": "loaded",
                    "ActiveState": "failed",
                    "Result": "exit-code",
                    "ExecMainStatus": "1",
                    "InvocationID": "failed-invocation",
                },
                "observed_at": "fixture",
            },
        )
    )
    locks_before = {path.name for path in store.locks_root.glob("*.lock")} if store.locks_root.exists() else set()
    systemd = CountingSystemd()
    monkeypatch.setattr(
        store,
        "list",
        lambda: (_ for _ in ()).throw(AssertionError("startup must not scan the terminal corpus")),
    )

    recovered = GenericJobs(systemd, store, wait_poll_seconds=0.001)

    assert systemd.observed == [active.unit]
    assert not (store.leases_root / f"{stale_id}.json").exists()
    assert recovered.get(stale_id)["lease"]["state"] == "released"
    assert systemd.observed == [active.unit]
    recovered.get(active.job_id)
    assert systemd.observed == [active.unit, active.unit]
    locks_after = {path.name for path in store.locks_root.glob("*.lock")}
    assert locks_after - locks_before == {f"{active.job_id}.lock"}
    assert not {f"{job_id}.lock" for job_id in terminal_ids}.intersection(locks_after)


def test_service_lease_invocation_mismatch_keeps_the_reservation_active(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anti-vacuity: a later unit invocation cannot inherit an earlier observation's release authority."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs(properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "first-invocation"})
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd))
    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    assert service.dispatch(request("job.get", "systemd-jobs", {"job_id": job_id})).ok

    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "failed",
        "Result": "exit-code",
        "ExecMainStatus": "1",
        "InvocationID": "newer-invocation",
    }
    mismatched = service.dispatch(request("job.get", "systemd-jobs", {"job_id": job_id}))

    assert mismatched.ok and mismatched.payload is not None
    assert mismatched.payload.inline["state"]["phase"] == "observation-unknown"
    assert mismatched.payload.inline["lease"]["state"] == "active"
    assert (tmp_path / "state" / "leases" / f"{job_id}.json").exists()


def test_concurrent_start_and_get_do_not_take_historical_terminal_locks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Live failure harness: concurrent client routes finish without waiting on terminal-record lock files."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    store = GenericJobStore(tmp_path / "state")
    terminal_ids: set[str] = set()
    for _ in range(64):
        record = store.create(
            GenericJobSpec(kind="foreground-command", command=("fixture",), working_directory=str(tmp_path), environment={})
        )
        terminal_ids.add(record.job_id)
        store.save(GenericJobs._with_state(record, {"phase": "failed", "terminal": True, "observed_at": "fixture"}))
    active = store.create(
        GenericJobSpec(kind="foreground-command", command=("fixture",), working_directory=str(tmp_path), environment={})
    )
    systemd = FakeSystemdJobs(properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"})
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
        lambda: (_ for _ in ()).throw(AssertionError("start/get must not scan the terminal corpus")),
    )
    started: list[dict[str, object]] = []
    failures: list[BaseException] = []

    def start_service() -> None:
        try:
            started.append(jobs.start_declared(project=project, operation=project.operation("service"), correlation_id="concurrent", parameters={}))
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


def test_service_lease_creation_is_atomic_against_concurrent_recovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A second daemon cannot collect an in-flight reservation and reallocate its port."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    store = GenericJobStore(tmp_path / "state")
    first = GenericJobs(FakeSystemdJobs(), store, wait_poll_seconds=0.001)
    entered, release, recovered = threading.Event(), threading.Event(), threading.Event()
    original_create = store.create
    adapter = ProjectCatalog([tmp_path]).get("fixture")

    def blocked_create(spec: GenericJobSpec, job_id: str | None = None):
        entered.set()
        assert release.wait(5)
        return original_create(spec, job_id)

    monkeypatch.setattr(store, "create", blocked_create)
    first_result: list[dict[str, object]] = []
    first_thread = threading.Thread(
        target=lambda: first_result.append(
            first.start_declared(project=adapter, operation=adapter.operation("service"), correlation_id="first", parameters={})
        )
    )
    first_thread.start()
    assert entered.wait(1)

    def recover() -> None:
        GenericJobStore(store.root).recover_service_leases(FakeSystemdJobs().show)
        recovered.set()

    second_thread = threading.Thread(target=recover)
    second_thread.start()
    assert not recovered.wait(0.05)
    release.set()
    first_thread.join(5)
    second_thread.join(5)
    assert not first_thread.is_alive() and not second_thread.is_alive()
    assert recovered.is_set()
    first_lease = first_result[0]["lease"]
    assert isinstance(first_lease, dict)
    assert first_lease["ports"][0]["port"] == 41000
    second = GenericJobs(FakeSystemdJobs(), GenericJobStore(store.root), wait_poll_seconds=0.001)
    replacement = second.start_declared(project=adapter, operation=adapter.operation("service"), correlation_id="second", parameters={})
    assert replacement["lease"]["ports"][0]["port"] == 41001


@pytest.mark.parametrize(
    ("record_state", "systemd_state", "preserved"),
    (
        ("malformed", {"LoadState": "loaded", "ActiveState": "active"}, True),
        ("missing", {"LoadState": "not-found", "ActiveState": "inactive"}, False),
        ("malformed", None, True),
    ),
)
def test_orphaned_valid_service_lease_recovery_requires_authoritative_absence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_state: str,
    systemd_state: dict[str, str] | None,
    preserved: bool,
) -> None:
    """Malformed records are never executable, but valid leases need absence proof before release."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)

    class UnavailableSystemd(FakeSystemdJobs):
        def show(self, unit: str, *, timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS) -> dict[str, str]:
            raise SystemdJobError("systemd unavailable")

    store = GenericJobStore(tmp_path / "state")
    operation = ProjectCatalog([tmp_path]).get("fixture").operation("service")
    assert operation.service is not None
    lease = store.allocate_service_lease(str(uuid4()), operation.service)
    record_path = store.records_root / f"{lease.lease_id}.json"
    if record_state == "malformed":
        record_path.parent.mkdir(parents=True)
        record_path.write_text("{")
    systemd = UnavailableSystemd() if systemd_state is None else FakeSystemdJobs(properties=systemd_state)
    _ = GenericJobs(systemd, store, wait_poll_seconds=0.001)

    lease_path = store.leases_root / f"{lease.lease_id}.json"
    assert lease_path.exists() is preserved
    with pytest.raises(JobRecordError):
        store.load(lease.lease_id)
    replacement = store.allocate_service_lease(str(uuid4()), operation.service)
    assert replacement.ports[0].port == (41001 if preserved else 41000)


def test_failed_service_launch_releases_its_lease(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anti-vacuity: a rejected transient service must not strand its reserved loopback port."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)

    class FailedStart(FakeSystemdJobs):
        def start(self, **_kwargs) -> None:
            raise SystemdJobError("fixture launch failure")

    write_adapter(tmp_path)
    systemd = FailedStart(properties={"LoadState": "not-found", "ActiveState": "inactive"})
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd))
    failed = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))

    assert failed.ok and failed.payload is not None
    assert failed.payload.inline["state"]["phase"] == "launch-failed"
    assert failed.payload.inline["lease"]["state"] == "released"
    assert not list((tmp_path / "state" / "leases").glob("*.json"))


def test_service_lease_claimed_between_allocation_and_launch_releases_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anti-vacuity: a port claimed after allocation cannot produce an active lease."""
    availability = iter((True, False))
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: next(availability))
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs(properties={"LoadState": "not-found", "ActiveState": "inactive"})
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd))

    failed = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))

    assert failed.ok and failed.payload is not None
    assert failed.payload.inline["state"]["phase"] == "launch-failed"
    assert failed.payload.inline["lease"]["state"] == "released"
    assert not list((tmp_path / "state" / "leases").glob("*.json"))


def test_queued_service_cancellation_wins_the_admission_start_interleaving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Admission re-reads the locked record, so cancellation cannot be overwritten by submitted."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'cache = "none"\n\n[operations.service.service]',
            'cache = "none"\nestimate_memory_bytes = 4294967296\n\n[operations.service.service]',
        )
    )
    systemd = FakeSystemdJobs(properties={"LoadState": "not-found", "ActiveState": "inactive"})
    store = GenericJobStore(tmp_path / "state")
    jobs = GenericJobs(
        systemd,
        store,
        wait_poll_seconds=0.001,
        pressure_probe=lambda: {"memory_full_avg10": 0.2},
    )
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"}))
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    assert started.payload.inline["state"]["phase"] == "queued"

    before_start, resume_admission, cancellation_saved = threading.Event(), threading.Event(), threading.Event()
    original_save = store.save

    def save_and_signal(record):
        original_save(record)
        if record.job_id == job_id and record.state.get("phase") == "cancelled":
            cancellation_saved.set()

    def pause_before_start(candidate: str) -> None:
        assert candidate == job_id
        before_start.set()
        assert resume_admission.wait(5)

    monkeypatch.setattr(store, "save", save_and_signal)
    jobs.before_admission_start = pause_before_start
    jobs.pressure_probe = lambda: {"memory_full_avg10": 0.0}
    def admit() -> None:
        with jobs._admission_lock:
            jobs._admit_locked()

    admission_thread = threading.Thread(target=admit)
    admission_thread.start()
    assert before_start.wait(1)
    cancellation_thread = threading.Thread(target=lambda: jobs.cancel(job_id))
    cancellation_thread.start()
    assert cancellation_saved.wait(1)
    resume_admission.set()
    admission_thread.join(5)
    cancellation_thread.join(5)

    record = store.load(job_id)
    assert not admission_thread.is_alive() and not cancellation_thread.is_alive()
    assert systemd.started == []
    assert record.state["phase"] == "cancelled" and record.state["terminal"]
    assert not (store.leases_root / f"{job_id}.json").exists()


def test_queued_declared_cancellation_survives_service_refresh_and_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity: a queued cancellation stays terminal when its unit never existed."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'cache = "none"\n\n[operations.service.service]',
            'cache = "none"\nestimate_memory_bytes = 4294967296\n\n[operations.service.service]',
        )
    )
    systemd = FakeSystemdJobs(properties={"LoadState": "not-found", "ActiveState": "inactive"})
    store = GenericJobStore(tmp_path / "state")
    jobs = GenericJobs(
        systemd,
        store,
        wait_poll_seconds=0.001,
        pressure_probe=lambda: {"memory_full_avg10": 0.2},
    )
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    started = service.dispatch(
        request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "service"})
    )
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    assert started.payload.inline["state"]["phase"] == "queued"

    cancelled = service.dispatch(request("job.cancel", "systemd-jobs", {"job_id": job_id}))
    assert cancelled.ok and cancelled.payload is not None
    assert cancelled.payload.inline["state"]["phase"] == "cancelled"
    assert cancelled.payload.inline["state"]["launch_evidence"] == "not-started"

    def assert_cancelled_truth(current: SinnixdService) -> None:
        for _ in range(2):
            refreshed = current.dispatch(request("job.get", "systemd-jobs", {"job_id": job_id}))
            assert refreshed.ok and refreshed.payload is not None
            assert refreshed.payload.inline["state"] == cancelled.payload.inline["state"]

            listed = current.dispatch(request("job.list", "systemd-jobs", {}))
            assert listed.ok and listed.payload is not None
            assert listed.payload.inline["jobs"][0]["job_id"] == job_id
            assert listed.payload.inline["jobs"][0]["state"] == cancelled.payload.inline["state"]

            result = current.dispatch(request("job.result", "systemd-jobs", {"job_id": job_id}))
            assert not result.ok
            assert result.error is not None
            assert result.error.code.value == "RESULT_INVALID"
            assert result.error.message == "job exit result is unavailable"
            assert result.payload is None

    assert_cancelled_truth(service)

    restarted = SinnixdService(
        ProjectCatalog([tmp_path]),
        jobs=GenericJobs(
            FakeSystemdJobs(properties={"LoadState": "not-found", "ActiveState": "inactive"}),
            GenericJobStore(store.root),
            wait_poll_seconds=0.001,
            pressure_probe=lambda: {"memory_full_avg10": 0.0},
        ),
    )
    assert_cancelled_truth(restarted)


def test_declared_missing_unit_without_cancellation_evidence_stays_missing(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: an absent post-launch declared unit is not inferred cancelled."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs(properties={"LoadState": "not-found", "ActiveState": "inactive"})
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd))

    started = service.dispatch(
        request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "check"})
    )
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    assert started.payload.inline["state"]["phase"] == "submitted"

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


def test_dependency_admission_never_nests_candidate_and_dependency_job_locks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Malformed durable dependency cycles cannot create a cross-process job-lock cycle during admission."""
    store = GenericJobStore(tmp_path / "state")
    jobs = GenericJobs(FakeSystemdJobs(), store, wait_poll_seconds=0.001)
    first_id, second_id = str(uuid4()), str(uuid4())

    def queued_record(job_id: str, dependency_id: str):
        record = store.create(
            GenericJobSpec(
                kind="declared-operation",
                command=("fixture-service",),
                working_directory=str(tmp_path),
                environment={},
                project_id="fixture",
                operation="service",
                parameter_digest="0" * 64,
                result_kind="exit-status",
                dependency_job_ids=(dependency_id,),
            ),
            job_id,
        )
        store.write_declared_launch(job_id, record.spec.command, record.spec.environment)
        store.save(jobs._with_state(record, {"phase": "queued", "terminal": False, "observed_at": "fixture"}))

    queued_record(first_id, second_id)
    queued_record(second_id, first_id)
    original_locked = store.locked
    held: list[str] = []

    @contextmanager
    def reject_nested_job_locks(job_id: str):
        assert not held, f"nested job locks: {held!r} then {job_id}"
        held.append(job_id)
        try:
            with original_locked(job_id):
                yield
        finally:
            held.pop()

    monkeypatch.setattr(store, "locked", reject_nested_job_locks)
    with jobs._admission_lock:
        jobs._admit_locked()

    assert store.load(first_id).state["phase"] == "waiting-dependencies"
    assert store.load(second_id).state["phase"] == "waiting-dependencies"


def test_service_input_write_failure_terminalizes_the_record_and_removes_partial_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed private launch-input write cannot leave an unlaunchable record or a held port."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    store = GenericJobStore(tmp_path / "state")
    jobs = GenericJobs(FakeSystemdJobs(), store, wait_poll_seconds=0.001)
    project = ProjectCatalog([tmp_path]).get("fixture")
    original_write = store.write_declared_launch

    def partial_then_fail(job_id: str, command: tuple[str, ...], environment: dict[str, str]) -> None:
        _ = command, environment
        store.inputs_root.mkdir(parents=True, exist_ok=True)
        (store.inputs_root / f"{job_id}.launch").write_text("{")
        raise OSError("fixture input persistence failure")

    monkeypatch.setattr(store, "write_declared_launch", partial_then_fail)
    with pytest.raises(OSError, match="fixture input persistence failure"):
        jobs.start_declared(project=project, operation=project.operation("service"), correlation_id="write-failure", parameters={})
    monkeypatch.setattr(store, "write_declared_launch", original_write)

    [record] = store.list()
    assert record.state["phase"] == "launch-failed" and record.state["terminal"]
    assert not (store.inputs_root / f"{record.job_id}.launch").exists()
    assert not (store.leases_root / f"{record.job_id}.json").exists()
    service = project.operation("service").service
    assert service is not None
    replacement = store.allocate_service_lease(str(uuid4()), service)
    assert replacement.ports[0].port == 41000


def test_restart_terminalizes_truncated_unpublished_service_input_after_unit_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crash between durable record and launch publication is recovered without retaining its lease."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    store = GenericJobStore(tmp_path / "state")
    operation = ProjectCatalog([tmp_path]).get("fixture").operation("service")
    assert operation.service is not None
    job_id = str(uuid4())
    lease = store.allocate_service_lease(job_id, operation.service)
    record = store.create(
        GenericJobSpec(
            kind="declared-operation",
            command=("fixture-service",),
            working_directory=str(tmp_path),
            environment={"FIXTURE_HTTP_PORT": str(lease.ports[0].port)},
            project_id="fixture",
            operation="service",
            parameter_digest="0" * 64,
            result_kind="exit-status",
            pool=operation.pool,
            lease=lease,
        ),
        job_id,
    )
    (store.inputs_root).mkdir(parents=True, exist_ok=True)
    (store.inputs_root / f"{job_id}.launch").write_text("{")
    _ = GenericJobs(
        FakeSystemdJobs(properties={"LoadState": "not-found", "ActiveState": "inactive"}),
        store,
        wait_poll_seconds=0.001,
    )

    recovered = store.load(record.job_id)
    assert recovered.state["phase"] == "launch-failed" and recovered.state["terminal"]
    assert not (store.inputs_root / f"{job_id}.launch").exists()
    assert not (store.leases_root / f"{job_id}.json").exists()
    replacement = store.allocate_service_lease(str(uuid4()), operation.service)
    assert replacement.ports[0].port == 41000


@pytest.mark.parametrize("artifact", ("missing", "truncated"))
@pytest.mark.parametrize("phase", ("queued", "active", "terminal"))
def test_record_owns_ports_when_its_lease_artifact_is_missing_or_truncated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, artifact: str, phase: str
) -> None:
    """Allocation derives occupancy from queued, active, and unreleased terminal records, never only lease files."""
    monkeypatch.setattr("sinnixd.jobs._loopback_port_available", lambda _port: True)
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    if phase == "queued":
        descriptor.write_text(
            descriptor.read_text().replace(
                'cache = "none"\n\n[operations.service.service]',
                'cache = "none"\nestimate_memory_bytes = 4294967296\n\n[operations.service.service]',
            )
        )
    systemd = (
        FakeSystemdJobs(properties={"LoadState": "not-found", "ActiveState": "inactive"})
        if phase == "queued"
        else FakeSystemdJobs()
    )
    jobs = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: {"memory_full_avg10": 0.2 if phase == "queued" else 0.0},
    )
    project = ProjectCatalog([tmp_path]).get("fixture")
    started = jobs.start_declared(project=project, operation=project.operation("service"), correlation_id=f"{phase}-{artifact}", parameters={})
    assert started["state"]["phase"] == ("queued" if phase == "queued" else "submitted")
    job_id = started["job_id"]
    if phase == "terminal":
        record = jobs.store.load(job_id)
        jobs.store.save(
            jobs._with_state(record, {"phase": "launch-failed", "terminal": True, "observed_at": "fixture"})
        )
    lease_path = jobs.store.leases_root / f"{job_id}.json"
    if artifact == "missing":
        lease_path.unlink()
    else:
        lease_path.write_text("{")

    operation = project.operation("service")
    assert operation.service is not None
    second = GenericJobStore(jobs.store.root).allocate_service_lease(str(uuid4()), operation.service)
    assert second.ports[0].port == 41001

    if phase != "terminal":
        jobs.cancel(job_id)
    systemd.properties = {"LoadState": "not-found", "ActiveState": "inactive"}
    jobs.get(job_id)
    reclaimed = GenericJobStore(jobs.store.root).allocate_service_lease(str(uuid4()), operation.service)
    assert reclaimed.ports[0].port == 41000


def test_typed_runner_keeps_the_one_hour_timeout_identity_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SINNIXD_TIMEOUT_SECONDS", str(MAX_DECLARED_OPERATION_TIMEOUT_SECONDS))

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


def test_project_operation_result_must_have_an_executable_declared_contract(tmp_path: Path) -> None:
    """Anti-vacuity: descriptor result metadata cannot be accepted and ignored."""
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(descriptor.read_text().replace('result = "json"', 'result = "agent"'))

    with pytest.raises(ProjectConfigError, match="operations.parameterized.result is invalid"):
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
    started: list[dict[str, object]] = field(default_factory=list)
    stopped: list[str] = field(default_factory=list)
    properties: dict[str, str] = field(
        default_factory=lambda: {
            "LoadState": "loaded",
            "ActiveState": "active",
            "SubState": "running",
            "MainPID": "42",
            "Result": "success",
        }
    )

    def start(
        self,
        *,
        unit: str,
        command: tuple[str, ...],
        working_directory: str,
        environment: dict[str, str],
        timeout_seconds: int,
        log_path: Path,
        json_result_path: Path | None = None,
    ) -> None:
        self.started.append(
            {
                "unit": unit,
                "command": command,
                "working_directory": working_directory,
                "environment": environment,
                "timeout_seconds": timeout_seconds,
                "log_path": log_path,
                "json_result_path": json_result_path,
            }
        )

    def show(
        self,
        unit: str,
        *,
        timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    ) -> dict[str, str]:
        assert unit.startswith("sinnixd-job-")
        return self.properties

    def stop(self, unit: str) -> None:
        self.stopped.append(unit)
        self.properties = {
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "signal",
            "ExecMainCode": "killed",
            "ExecMainStatus": "15",
            "InvocationID": self.properties.get("InvocationID", "fixture-invocation"),
        }


def generic_jobs(tmp_path: Path, systemd: FakeSystemdJobs | None = None) -> GenericJobs:
    return GenericJobs(systemd or FakeSystemdJobs(), GenericJobStore(tmp_path / "state"), wait_poll_seconds=0.001)


def initialize_git_checkout(root: Path) -> None:
    for arguments in (
        ("git", "init", "--quiet", str(root)),
        ("git", "-C", str(root), "add", "."),
        ("git", "-C", str(root), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "--allow-empty", "-m", "fixture"),
    ):
        subprocess.run(arguments, check=True)
    subprocess.run(
        ["git", "-C", str(root), "update-ref", "refs/remotes/origin/master", "HEAD"], check=True
    )


def replace_worktree_gitfile_with_symlink(worktree: Path, target: Path | None = None) -> Path:
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
        "worktree /repo\nHEAD " + "a" * 40 + "\ndetached\nlocked operator reason\nprunable stale\n\n"
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
        "if [ -n \"${RUNNER_ARGS:-}\" ]; then printf '%s\\n' \"$@\" > \"$RUNNER_ARGS\"; fi\n"
        "while [ $# -gt 0 ]; do\n"
        "  case $1 in --last-file) last=$2; shift 2 ;; --prompt-file) prompt=$2; shift 2 ;; *) shift ;; esac\n"
        "done\n"
        "test -f \"$prompt\"\n"
        "printf native-fixture-result > \"$last\"\n"
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


@dataclass
class FakeTaskBoundary:
    results: list[ExecutionResult]
    calls: list[tuple[tuple[str, ...], Path]] = field(default_factory=list)
    lock_paths: list[Path | None] = field(default_factory=list)
    entered: threading.Event | None = None
    release: threading.Event | None = None
    active: int = 0
    max_active: int = 0
    _guard: threading.Lock = field(default_factory=threading.Lock)

    def run(self, *, argv: tuple[str, ...], cwd: Path, environment: dict[str, str], lock_path: Path | None = None, max_stdout_bytes: int | None = None) -> ExecutionResult:
        self.calls.append((argv, cwd))
        self.lock_paths.append(lock_path)
        with self._guard:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            assert self.release.wait(1), "task command was not released"
        with self._guard:
            self.active -= 1
        return self.results.pop(0)


@dataclass
class CanonicalTaskBoundary:
    tasks: dict[str, dict[str, object]]
    calls: list[tuple[tuple[str, ...], Path]] = field(default_factory=list)
    databases: list[Path] = field(default_factory=list)

    def run(self, *, argv: tuple[str, ...], cwd: Path, environment: dict[str, str], lock_path: Path | None = None, max_stdout_bytes: int | None = None) -> ExecutionResult:
        self.calls.append((argv, cwd))
        database = Path(environment["BEADS_DIR"]) / "dolt"
        self.databases.append(database)
        command_offset = argv.index("--json") + 1
        if argv[command_offset : command_offset + 1] == ("--readonly",):
            command_offset += 1
        command = argv[command_offset:]
        if command[:1] == ("update",) and command[2:] == ("--claim",):
            task = self.tasks[command[1]]
            task["status"] = "claimed"
            return task_result([dict(task)])
        if command[:1] == ("show",):
            return task_result([dict(self.tasks[command[1]])])
        raise AssertionError(f"unexpected canonical task command: {command}")


def task_result(value: object) -> ExecutionResult:
    return ExecutionResult(
        command=(),
        exit_status=0,
        stdout=json.dumps(value).encode(),
        stderr=b"",
    )


def activate_task_authority(
    project_root: Path,
    state_root: Path,
    *,
    project_id: str = "fixture",
    source_database: Path | None = None,
    rows: int = 1,
    digest: str = "sha256:" + "a" * 64,
) -> Path:
    authority_root = state_root / project_id
    database = authority_root / ".beads" / "dolt"
    database.mkdir(mode=0o700, parents=True)
    source_database = source_database or project_root / ".beads" / "dolt"
    source_database.parent.mkdir(parents=True, exist_ok=True)
    (source_database.parent / "redirect").write_text(str(database.parent) + "\n")
    (authority_root / "authority.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "project_id": project_id,
                "database": str(database),
                "source_database": str(source_database),
                "verification": {
                    "source_export_sha256": digest,
                    "destination_export_sha256": digest,
                    "source_rows": rows,
                    "destination_rows": rows,
                },
            }
        )
    )
    return database


def task_service(tmp_path: Path, boundary: FakeTaskBoundary | None = None) -> tuple[TaskService, FakeTaskBoundary]:
    write_adapter(tmp_path)
    fake = boundary or FakeTaskBoundary([task_result({"ok": True})])
    task_state_root = tmp_path / "task-state"
    activate_task_authority(tmp_path, task_state_root)
    return (
        TaskService(
            ProjectCatalog([tmp_path]),
            generic_jobs(tmp_path),
            fake,
            task_state_root=task_state_root,
        ),
        fake,
    )


def isolate_job_scratch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SINNIXD_TMPFS_SCRATCH_ROOT", str(tmp_path / "tmpfs-scratch"))
    monkeypatch.setenv("SINNIXD_NVME_SCRATCH_ROOT", str(tmp_path / "nvme-scratch"))


def test_task_reads_resolve_catalog_projects_and_use_readonly_fixed_argv(tmp_path: Path) -> None:
    service, boundary = task_service(
        tmp_path,
        FakeTaskBoundary([task_result([{"id": "fixture-1"}]), task_result([{"id": "fixture-1"}])]),
    )

    listed = service.execute(
        operation="task.list",
        arguments={"project_id": "fixture", "status": "open", "limit": 20},
        principal="observer",
    )
    fetched = service.execute(
        operation="task.get",
        arguments={"project_id": "fixture", "task_id": "fixture-1"},
        principal="observer",
    )

    assert listed["result"]["issues"] == [{"id": "fixture-1"}]
    assert listed["result"]["total"] == 1
    assert listed["result"]["next_cursor"] is None
    assert listed["result"]["coverage"]["total_exact"] is True
    assert fetched["result"] == {"id": "fixture-1"}
    authority_root = tmp_path / "task-state" / "fixture"
    database = authority_root / ".beads" / "dolt"
    prefix = ("--json", "--readonly")
    assert boundary.calls == [
        ((*prefix, "list", "--flat", "--status", "open", "--limit", "0", "--max-rows", "100000"), tmp_path),
        ((*prefix, "show", "fixture-1"), tmp_path),
    ]


def test_task_list_traverses_real_pages_from_one_immutable_snapshot(tmp_path: Path) -> None:
    rows = [{"id": f"fixture-{index}", "status": "open"} for index in range(1, 6)]
    service, boundary = task_service(tmp_path, FakeTaskBoundary([task_result(rows)]))
    arguments: dict[str, object] = {"project_id": "fixture", "status": "open", "limit": 2}
    seen: list[str] = []
    source_revision: str | None = None
    cursor: str | None = None

    while True:
        page_arguments = dict(arguments)
        if cursor is not None:
            page_arguments["cursor"] = cursor
        page = service.execute(operation="task.list", arguments=page_arguments, principal="observer")
        result = page["result"]
        assert result["coverage"] == {
            "state": "complete",
            "kind": "result_snapshot",
            "returned": 5,
            "total": 5,
            "total_exact": True,
            "source_revision": result["source_revision"],
        }
        assert result["page"]["complete"] is (result["next_cursor"] is None)
        seen.extend(row["id"] for row in result["issues"])
        source_revision = source_revision or result["source_revision"]
        assert result["source_revision"] == source_revision
        cursor = result["next_cursor"]
        if cursor is None:
            break

    assert seen == [f"fixture-{index}" for index in range(1, 6)]
    assert len(boundary.calls) == 1
    assert boundary.calls[0][0][-4:] == ("--limit", "0", "--max-rows", "100000")


def test_task_list_cursor_rejects_negative_cases_before_owner_dispatch(tmp_path: Path) -> None:
    service, boundary = task_service(tmp_path, FakeTaskBoundary([task_result([{"id": "fixture-1"}, {"id": "fixture-2"}])]))
    first = service.execute(
        operation="task.list", arguments={"project_id": "fixture", "limit": 1}, principal="observer"
    )["result"]
    cursor = first["next_cursor"]
    assert isinstance(cursor, str)
    owner_calls = len(boundary.calls)

    cases = (
        ("malformed", "not-a-cursor", "INVALID_ARGUMENT"),
        ("oversized", "x" * 513, "INVALID_ARGUMENT"),
    )
    for _, bad_cursor, code in cases:
        with pytest.raises(TaskError) as error:
            service.execute(
                operation="task.list",
                arguments={"project_id": "fixture", "limit": 1, "cursor": bad_cursor},
                principal="observer",
            )
        assert error.value.code.value == code

    with pytest.raises(TaskError, match="principal") as foreign:
        service.execute(
            operation="task.list",
            arguments={"project_id": "fixture", "limit": 1, "cursor": cursor},
            principal="operator",
        )
    assert foreign.value.code.value == "INVALID_ARGUMENT"

    other_project = tmp_path / "other-project"
    write_adapter(other_project, project_id="other")
    activate_task_authority(other_project, tmp_path / "task-state", project_id="other")
    service.projects = ProjectCatalog([tmp_path, other_project])
    with pytest.raises(TaskError):
        service.execute(
            operation="task.list",
            arguments={"project_id": "other", "limit": 1, "cursor": cursor},
            principal="observer",
        )

    with pytest.raises(TaskError, match="query") as mismatched:
        service.execute(
            operation="task.list",
            arguments={"project_id": "fixture", "status": "closed", "limit": 1, "cursor": cursor},
            principal="observer",
        )
    assert mismatched.value.code.value == "INVALID_ARGUMENT"
    assert len(boundary.calls) == owner_calls

    snapshot = next((tmp_path / "task-state" / "fixture" / "sinnixd-task-list-snapshots").glob("*.json"))
    snapshot.unlink()
    with pytest.raises(TaskError) as missing:
        service.execute(
            operation="task.list", arguments={"project_id": "fixture", "limit": 1, "cursor": cursor}, principal="observer"
        )
    assert missing.value.code.value == "STALE_CURSOR"
    assert len(boundary.calls) == owner_calls


def test_task_list_service_returns_structured_stale_cursor_error(tmp_path: Path) -> None:
    service, _ = task_service(tmp_path, FakeTaskBoundary([task_result([{"id": "fixture-1"}, {"id": "fixture-2"}])]))
    daemon = SinnixdService(ProjectCatalog([tmp_path]), tasks=service)
    first = daemon.dispatch(
        request("task.list", "task-backend", {"project_id": "fixture", "limit": 1}, "observer")
    )
    assert first.ok and first.payload is not None
    cursor = first.payload.inline["result"]["next_cursor"]
    next((tmp_path / "task-state" / "fixture" / "sinnixd-task-list-snapshots").glob("*.json")).unlink()
    response = daemon.dispatch(
        request("task.list", "task-backend", {"project_id": "fixture", "limit": 1, "cursor": cursor}, "observer")
    )
    assert response.error is not None
    assert response.error.code is ErrorCode.STALE_CURSOR


@pytest.mark.parametrize(
    ("operation", "arguments", "expected"),
    (
        ("task.claim", {"task_id": "fixture-1"}, ("update", "fixture-1", "--claim")),
        ("task.note", {"task_id": "fixture-1", "text": "append this"}, ("note", "fixture-1", "append this")),
        ("task.relate", {"task_id": "fixture-1", "related_task_id": "fixture-2"}, ("dep", "relate", "fixture-1", "fixture-2")),
        ("task.complete", {"task_id": "fixture-1", "merge_sha": "a" * 40, "reason": "verified"}, ("close", "fixture-1", "--reason", "verified")),
        ("task.release", {"task_id": "fixture-1", "reason": "stopped", "if_assignee": "worker"}, ("unclaim", "fixture-1", "--reason", "stopped", "--if-assignee", "worker")),
    ),
)
def test_task_mutations_map_to_fixed_beads_argv(
    tmp_path: Path, operation: str, arguments: dict[str, str], expected: tuple[str, ...]
) -> None:
    service, boundary = task_service(tmp_path, FakeTaskBoundary([task_result({"ok": True})]))

    result = service.execute(
        operation=operation,
        arguments={"project_id": "fixture", **arguments},
        principal="agent-control",
        mutation_id="request-1",
    )

    assert result["project_id"] == "fixture"
    assert result["operation"] == operation
    assert result["result"]["state"] == "applied"
    assert result["result"]["result"]["bytes"] == len(json.dumps({"ok": True}, sort_keys=True, separators=(",", ":")).encode())
    authority_root = tmp_path / "task-state" / "fixture"
    database = authority_root / ".beads" / "dolt"
    assert boundary.calls == [
        (("--json", *expected), tmp_path)
    ]


def test_task_create_returns_a_replay_safe_canonical_ref_and_owner_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anti-vacuity: the replay reads the durable receipt, so a second backend create would fail this test."""
    isolate_job_scratch(monkeypatch, tmp_path)
    boundary = FakeTaskBoundary([task_result({"id": "fixture-new", "title": "backend-only"})])
    service, _ = task_service(tmp_path, boundary)
    arguments = {
        "project_id": "fixture",
        "title": "typed title",
        "description": "private create description",
        "issue_type": "feature",
        "priority": 1,
        "labels": ["area:agentctl", "lane:agents"],
        "parent_task_id": "fixture-parent",
        "dependencies": [
            {"relation": "depends-on", "task_id": "fixture-blocker"},
            {"relation": "relates-to", "task_id": "fixture-peer"},
        ],
    }

    first = service.execute(operation="task.create", arguments=arguments, principal="agent-control", mutation_id="request-1")
    replayed = service.execute(operation="task.create", arguments=arguments, principal="agent-control", mutation_id="request-1")

    assert first == replayed
    assert first["task_ref"] == "sinnix://projects/fixture/beads/fixture-new"
    assert first["owner_evidence"] == {
        "owner": "task-backend",
        "state": "applied",
        "attempts": 1,
        "result": {"sha256": TaskMutationJournal(TaskAuthority.load(tmp_path / "task-state", "fixture").root / TASK_MUTATION_JOURNAL_DIRECTORY).records()[0].result["sha256"], "bytes": len(json.dumps({"id": "fixture-new", "title": "backend-only"}, sort_keys=True, separators=(",", ":")).encode()), "created_task_id": "fixture-new"},
        "failure": None,
    }
    assert boundary.calls == [
        (("--json", "create", "--title", "typed title", "--description", "private create description", "--type", "feature", "--priority", "1", "--labels", "area:agentctl,lane:agents", "--parent", "fixture-parent", "--deps", "depends-on:fixture-blocker,relates-to:fixture-peer"), tmp_path)
    ]
    journal = TaskMutationJournal(TaskAuthority.load(tmp_path / "task-state", "fixture").root / TASK_MUTATION_JOURNAL_DIRECTORY)
    public_record = next(journal.records_root.glob("*.json"))
    assert "private create description" not in public_record.read_text()


def test_task_create_uses_the_real_beads_result_shape_and_replays_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Production boundary: current bd emits one object for create, and replay must not create twice."""
    isolate_job_scratch(monkeypatch, tmp_path)
    project_root = tmp_path / "project"
    project_root.mkdir()
    write_adapter(project_root)
    task_state_root = tmp_path / "task-state"
    authority_root = task_state_root / "fixture"
    authority_root.mkdir(parents=True)
    beads_environment = {
        **os.environ,
        "HOME": str(authority_root),
        "XDG_CONFIG_HOME": str(authority_root / ".config"),
        "XDG_DATA_HOME": str(authority_root / ".local" / "share"),
        "XDG_STATE_HOME": str(authority_root / ".local" / "state"),
    }
    subprocess.run(
        ["bd", "init", "--skip-agents", "--skip-hooks", "--non-interactive", "--prefix", "fixture"],
        cwd=authority_root,
        check=True,
        capture_output=True,
        text=True,
        env=beads_environment,
    )
    activate_task_authority(project_root, task_state_root, rows=0)
    service = TaskService(
        ProjectCatalog([project_root]),
        generic_jobs(tmp_path / "jobs"),
        BeadsCommandBoundary(execution=OwnerExecution(beads_environment)),
        task_state_root=task_state_root,
    )
    arguments = {
        "project_id": "fixture",
        "title": "real boundary task",
        "description": "created through the production bd boundary",
        "issue_type": "task",
        "priority": 2,
        "labels": [],
        "dependencies": [],
    }

    first = service.execute(
        operation="task.create",
        arguments=arguments,
        principal="agent-control",
        mutation_id="real-boundary-request",
    )
    replayed = service.execute(
        operation="task.create",
        arguments=arguments,
        principal="agent-control",
        mutation_id="real-boundary-request",
    )
    listed = service.execute(
        operation="task.list",
        arguments={"project_id": "fixture", "status": "open", "limit": 20},
        principal="observer",
    )

    assert first == replayed
    assert first["task_ref"].startswith("sinnix://projects/fixture/beads/fixture-")
    assert first["owner_evidence"]["result"]["created_task_id"] == first["task_ref"].rsplit("/", 1)[1]
    assert listed["result"]["total"] == 1
    assert [issue["title"] for issue in listed["result"]["issues"]] == ["real boundary task"]


def test_task_create_outage_replays_without_dirtying_the_registered_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anti-vacuity: creation stays pending across an outage, then replays once from the private intent."""
    isolate_job_scratch(monkeypatch, tmp_path)
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    task_state_root = tmp_path.parent / f"task-state-{tmp_path.name}"
    source_database = tmp_path.parent / f"legacy-task-source-{tmp_path.name}" / ".beads" / "dolt"
    activate_task_authority(tmp_path, task_state_root, source_database=source_database)
    arguments = {"project_id": "fixture", "title": "replayed task", "description": "private replay description", "issue_type": "task", "priority": 2, "labels": [], "dependencies": []}
    unavailable = ExecutionResult(command=(), exit_status=None, stdout=b"", stderr=b"", failure_class="command_unavailable:FileNotFoundError")
    first_boundary = FakeTaskBoundary([unavailable])
    first = TaskService(ProjectCatalog([tmp_path]), generic_jobs(tmp_path.parent / f"first-jobs-{tmp_path.name}"), first_boundary, task_state_root=task_state_root)

    pending = first.execute(operation="task.create", arguments=arguments, principal="agent-control", mutation_id="request-1")

    assert pending["owner_evidence"] == {"owner": "task-backend", "state": "pending", "attempts": 1, "result": None, "failure": {"code": "OWNER_UNAVAILABLE"}}
    assert "task_ref" not in pending
    authority = TaskAuthority.load(task_state_root, "fixture")
    journal = TaskMutationJournal(authority.root / TASK_MUTATION_JOURNAL_DIRECTORY)
    assert "private replay description" not in next(journal.records_root.glob("*.json")).read_text()
    assert subprocess.run(["git", "-C", str(tmp_path), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout == ""

    second_boundary = FakeTaskBoundary([task_result({"id": "fixture-replayed"})])
    receipts = reconcile_task_mutations(journal=journal, authority=authority, cwd=tmp_path, boundary=second_boundary)
    restarted = TaskService(ProjectCatalog([tmp_path]), generic_jobs(tmp_path.parent / f"second-jobs-{tmp_path.name}"), second_boundary, task_state_root=task_state_root)
    replayed = restarted.execute(operation="task.create", arguments=arguments, principal="agent-control", mutation_id="request-1")

    assert receipts[0]["state"] == "applied"
    assert replayed["task_ref"] == "sinnix://projects/fixture/beads/fixture-replayed"
    assert len(first_boundary.calls) == 1
    assert len(second_boundary.calls) == 1
    assert subprocess.run(["git", "-C", str(tmp_path), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout == ""


@pytest.mark.parametrize(
    "arguments",
    (
        {"project_id": "missing", "title": "title", "description": "body", "issue_type": "task", "priority": 2, "labels": [], "dependencies": []},
        {"project_id": "fixture", "title": "title", "description": "body", "issue_type": "unknown", "priority": 2, "labels": [], "dependencies": []},
        {"project_id": "fixture", "title": "title", "description": "body", "issue_type": "task", "priority": True, "labels": [], "dependencies": []},
        {"project_id": "fixture", "title": "title", "description": "body", "issue_type": "task", "priority": 2, "labels": ["bad,label"], "dependencies": []},
        {"project_id": "fixture", "title": "title", "description": "body", "issue_type": "task", "priority": 2, "labels": [], "parent_task_id": "--invalid", "dependencies": []},
        {"project_id": "fixture", "title": "title", "description": "body", "issue_type": "task", "priority": 2, "labels": [], "dependencies": [{"relation": "not-a-relation", "task_id": "fixture-1"}]},
    ),
)
def test_task_create_rejects_invalid_project_parent_and_typed_input(tmp_path: Path, arguments: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_job_scratch(monkeypatch, tmp_path)
    service, boundary = task_service(tmp_path)

    with pytest.raises(TaskError) as error:
        service.execute(operation="task.create", arguments=arguments, principal="agent-control", mutation_id="request-1")

    assert error.value.code == ErrorCode.INVALID_ARGUMENT
    assert not boundary.calls


def test_task_create_relation_failure_is_a_failed_journalled_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_job_scratch(monkeypatch, tmp_path)
    service, boundary = task_service(tmp_path, FakeTaskBoundary([ExecutionResult(command=(), exit_status=1, stdout=b"", stderr=b"parent missing")]))
    response = SinnixdService(ProjectCatalog([tmp_path]), tasks=service).dispatch(
        request(
            "task.create",
            "task-backend",
            {"project_id": "fixture", "title": "relation failure", "description": "body", "issue_type": "task", "priority": 2, "labels": [], "parent_task_id": "fixture-parent", "dependencies": [{"relation": "depends-on", "task_id": "fixture-blocker"}]},
            "agent-control",
            idempotency_key="request-1",
        )
    )

    assert not response.ok and response.error is not None
    assert response.error.code == ErrorCode.OPERATION_FAILED
    record = TaskMutationJournal(
        TaskAuthority.load(tmp_path / "task-state", "fixture").root
        / TASK_MUTATION_JOURNAL_DIRECTORY
    ).records()[0]
    assert record.state == "failed"
    assert record.failure == {"code": "OPERATION_FAILED"}
    assert boundary.calls == [(("--json", "create", "--title", "relation failure", "--description", "body", "--type", "task", "--priority", "2", "--parent", "fixture-parent", "--deps", "depends-on:fixture-blocker"), tmp_path)]


def test_task_mutation_outage_survives_restart_and_reconciles_without_git_dirtying(tmp_path: Path) -> None:
    """Anti-vacuity: an unavailable command becomes pending, then a new service replays it exactly once."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    task_state_root = tmp_path.parent / "task-state"
    source_database = tmp_path.parent / "legacy-task-source" / ".beads" / "dolt"
    activate_task_authority(tmp_path, task_state_root, source_database=source_database)
    unavailable = ExecutionResult(command=(), exit_status=None, stdout=b"", stderr=b"", failure_class="command_unavailable:FileNotFoundError")
    first_boundary = FakeTaskBoundary([unavailable])
    first = TaskService(ProjectCatalog([tmp_path]), generic_jobs(tmp_path.parent / "first-jobs"), first_boundary, task_state_root=task_state_root)
    payload = {"project_id": "fixture", "task_id": "fixture-1", "text": "private replay payload"}

    pending = first.execute(operation="task.note", arguments=payload, principal="agent-control", mutation_id="request-1")

    assert pending["result"]["state"] == "pending"
    assert pending["result"]["failure"] == {"code": "OWNER_UNAVAILABLE"}
    authority = TaskAuthority.load(task_state_root, "fixture")
    journal = TaskMutationJournal(authority.root / TASK_MUTATION_JOURNAL_DIRECTORY)
    public_records = list(journal.records_root.glob("*.json"))
    assert len(public_records) == 1
    assert "private replay payload" not in public_records[0].read_text()
    assert subprocess.run(["git", "-C", str(tmp_path), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout == ""

    second_boundary = FakeTaskBoundary([task_result({"reconciled": True})])
    receipts = reconcile_task_mutations(journal=journal, authority=authority, cwd=tmp_path, boundary=second_boundary)
    restarted = TaskService(ProjectCatalog([tmp_path]), generic_jobs(tmp_path.parent / "restart-jobs"), second_boundary, task_state_root=task_state_root)
    replayed = restarted.execute(operation="task.note", arguments=payload, principal="agent-control", mutation_id="request-1")

    assert receipts[0]["state"] == "applied"
    assert replayed["result"]["state"] == "applied"
    assert len(first_boundary.calls) == 1
    assert len(second_boundary.calls) == 1
    assert not list(journal.intents_root.glob("*.json"))
    assert subprocess.run(["git", "-C", str(tmp_path), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout == ""


def test_task_completion_is_idempotent_by_project_task_and_merge_sha(tmp_path: Path) -> None:
    service, boundary = task_service(tmp_path, FakeTaskBoundary([task_result({"closed": True})]))
    arguments = {"project_id": "fixture", "task_id": "fixture-1", "merge_sha": "b" * 40, "reason": "merged"}

    first = service.execute(operation="task.complete", arguments=arguments, principal="agent-control", mutation_id="request-1")
    replayed = service.execute(operation="task.complete", arguments=arguments, principal="agent-control", mutation_id="request-2")

    assert first["result"]["state"] == "applied"
    assert replayed["result"]["state"] == "applied"
    assert len(boundary.calls) == 1
    with pytest.raises(TaskError, match="idempotency identity"):
        service.execute(
            operation="task.complete",
            arguments={**arguments, "reason": "conflicting evidence"},
            principal="agent-control",
            mutation_id="request-3",
        )


def test_task_mutation_distinct_request_ids_apply_independently(tmp_path: Path) -> None:
    service, boundary = task_service(
        tmp_path,
        FakeTaskBoundary([task_result({"attempt": 1}), task_result({"attempt": 2})]),
    )

    first = service.execute(
        operation="task.note",
        arguments={"project_id": "fixture", "task_id": "fixture-1", "text": "first"},
        principal="agent-control",
        mutation_id="request-1",
    )
    second = service.execute(
        operation="task.note",
        arguments={"project_id": "fixture", "task_id": "fixture-1", "text": "second"},
        principal="agent-control",
        mutation_id="request-2",
    )

    assert first["result"]["state"] == "applied"
    assert second["result"]["state"] == "applied"
    assert len(boundary.calls) == 2


def test_task_reconcile_returns_a_durable_fixed_command_receipt(tmp_path: Path) -> None:
    """Anti-vacuity: a slow sync must not run through the 30-second task boundary."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    boundary = FakeTaskBoundary([task_result({"ok": True})])
    task_state_root = tmp_path / "task-state"
    activate_task_authority(tmp_path, task_state_root)
    tasks = TaskService(ProjectCatalog([tmp_path]), jobs, boundary, task_state_root=task_state_root)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs, tasks=tasks)

    claimed = tasks.execute(
        operation="task.claim",
        arguments={"project_id": "fixture", "task_id": "fixture-1"},
        principal="agent-control",
        mutation_id="request-1",
    )
    response = service.dispatch(request("task.reconcile", "task-backend", {"project_id": "fixture"}, "agent-control"))

    assert claimed["result"]["state"] == "applied"
    assert response.ok and response.payload is not None
    payload = response.payload.inline
    assert payload["project_id"] == "fixture"
    assert payload["operation"] == "task.reconcile"
    receipt = payload["result"]
    assert isinstance(receipt, dict)
    job_id = receipt["job_id"]
    assert isinstance(job_id, str)
    lock_path = task_state_root / "fixture" / "sinnixd-task-mutations.lock"
    assert boundary.lock_paths == [None]
    authority_root = task_state_root / "fixture"
    database = authority_root / ".beads" / "dolt"
    assert boundary.calls == [
        (
            (
                    "--json",
                "update",
                "fixture-1",
                "--claim",
            ),
                tmp_path,
        )
    ]
    assert len(systemd.started) == 1
    launched = systemd.started[0]
    assert launched["unit"] == receipt["unit"]
    assert launched["command"] == (
        FLOCK_EXECUTABLE,
        "--exclusive",
        str(lock_path),
        "sinnixd-task-reconcile",
        "--project-id",
        "fixture",
        "--project-root",
        str(tmp_path),
        "--task-state-root",
        str(task_state_root),
    )
    assert launched["working_directory"] == str(tmp_path)
    assert launched["timeout_seconds"] == DEFAULT_TIMEOUT_SECONDS
    environment = launched["environment"]
    assert isinstance(environment, dict)
    assert environment["BEADS_DIR"] == str(authority_root / ".beads")
    assert environment["SINNIXD_JOB_ID"] == job_id
    assert environment["SINNIXD_PROJECT_ID"] == "fixture"
    assert environment["SINNIXD_OPERATION"] == "task.reconcile"
    record = jobs.store.load(job_id)
    assert record.spec.project_id == "fixture"
    assert record.spec.operation == "task.reconcile"
    assert record.spec.to_dict()["command"]["display"] == "synthetic foreground command"


def test_task_snapshot_parses_jsonl_without_writing_a_store(tmp_path: Path) -> None:
    snapshot = ExecutionResult(
        command=(),
        exit_status=0,
        stdout=b'{"id":"fixture-1"}\n{"id":"fixture-2"}\n',
        stderr=b"",
    )
    service, boundary = task_service(tmp_path, FakeTaskBoundary([snapshot]))

    result = service.execute(
        operation="task.snapshot", arguments={"project_id": "fixture"}, principal="observer"
    )

    assert result == {
        "project_id": "fixture",
        "operation": "task.snapshot",
        "result": [{"id": "fixture-1"}, {"id": "fixture-2"}],
    }
    authority_root = tmp_path / "task-state" / "fixture"
    database = authority_root / ".beads" / "dolt"
    assert boundary.calls == [
        (
                ("--json", "--readonly", "export"),
                tmp_path,
        )
    ]


def test_task_mutations_are_serialized_per_project(tmp_path: Path) -> None:
    entered = threading.Event()
    release = threading.Event()
    boundary = FakeTaskBoundary([task_result({"ok": 1}), task_result({"ok": 2})], entered=entered, release=release)
    write_adapter(tmp_path)
    task_state_root = tmp_path / "task-state"
    activate_task_authority(tmp_path, task_state_root)
    first_service = TaskService(ProjectCatalog([tmp_path]), generic_jobs(tmp_path / "first-jobs"), boundary, task_state_root=task_state_root)
    second_service = TaskService(ProjectCatalog([tmp_path]), generic_jobs(tmp_path / "second-jobs"), boundary, task_state_root=task_state_root)
    errors: list[BaseException] = []

    def mutate(service: TaskService, task_id: str) -> None:
        try:
            service.execute(
                operation="task.claim",
                arguments={"project_id": "fixture", "task_id": task_id},
                principal="agent-control",
                mutation_id=f"request-{task_id}",
            )
        except BaseException as error:
            errors.append(error)

    first = threading.Thread(target=mutate, args=(first_service, "fixture-1"))
    second = threading.Thread(target=mutate, args=(second_service, "fixture-2"))
    first.start()
    assert entered.wait(1), "first task mutation did not reach the backend"
    second.start()
    assert len(boundary.calls) == 1
    release.set()
    first.join(1)
    second.join(1)

    assert not errors
    assert boundary.max_active == 1
    assert len(boundary.calls) == 2


def test_divergent_worktrees_share_canonical_authority_and_ignore_stale_jsonl(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    write_adapter(repository)
    (repository / "modules" / "fixture.nix").write_text("{}\n")
    snapshots = repository / ".beads" / "issues.jsonl"
    snapshots.parent.mkdir()
    snapshots.write_text('{"id":"fixture-1","status":"open"}\n')
    initialize_git_checkout(repository)
    subprocess.run(["git", "-C", str(repository), "branch", "stale-checkout"], check=True)
    snapshots.write_text('{"id":"fixture-1","status":"closed"}\n')
    subprocess.run(["git", "-C", str(repository), "add", ".beads/issues.jsonl"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--quiet",
            "-m",
            "newer snapshot",
        ],
        check=True,
    )
    stale_checkout = tmp_path / "stale-checkout"
    subprocess.run(
        ["git", "-C", str(repository), "worktree", "add", "--quiet", str(stale_checkout), "stale-checkout"],
        check=True,
    )
    assert snapshots.read_text() != (stale_checkout / ".beads" / "issues.jsonl").read_text()

    task_state_root = tmp_path / "task-state"
    database = activate_task_authority(repository, task_state_root)
    boundary = CanonicalTaskBoundary({"fixture-1": {"id": "fixture-1", "status": "closed"}})
    primary = TaskService(
        ProjectCatalog([repository]),
        generic_jobs(tmp_path / "primary-jobs"),
        boundary,
        task_state_root=task_state_root,
    )
    stale = TaskService(
        ProjectCatalog([stale_checkout]),
        generic_jobs(tmp_path / "stale-jobs"),
        boundary,
        task_state_root=task_state_root,
    )

    primary.execute(
        operation="task.claim",
        arguments={"project_id": "fixture", "task_id": "fixture-1"},
        principal="agent-control",
        mutation_id="claim-fixture-1",
    )
    observed = stale.execute(
        operation="task.get",
        arguments={"project_id": "fixture", "task_id": "fixture-1"},
        principal="observer",
    )

    assert observed["result"] == {"id": "fixture-1", "status": "claimed"}
    assert boundary.databases == [database, database]
    assert [cwd for _, cwd in boundary.calls] == [repository, stale_checkout]
    assert json.loads((stale_checkout / ".beads" / "issues.jsonl").read_text())["status"] == "open"


def test_task_authority_refuses_unverified_or_dual_authority(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    task_state_root = tmp_path / "task-state"
    boundary = FakeTaskBoundary([task_result({"id": "fixture-1"})])
    tasks = TaskService(
        ProjectCatalog([tmp_path]),
        generic_jobs(tmp_path),
        boundary,
        task_state_root=task_state_root,
    )
    request = {
        "operation": "task.get",
        "arguments": {"project_id": "fixture", "task_id": "fixture-1"},
        "principal": "observer",
    }

    with pytest.raises(TaskError, match="not activated") as missing:
        tasks.execute(**request)
    assert missing.value.code == ErrorCode.OWNER_UNAVAILABLE

    database = activate_task_authority(tmp_path, task_state_root)
    receipt_path = task_state_root / "fixture" / "authority.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["verification"]["destination_rows"] = 2
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(TaskError, match="verification is incomplete") as unverified:
        tasks.execute(**request)
    assert unverified.value.code == ErrorCode.OPERATION_FAILED

    receipt["verification"]["destination_rows"] = 1
    receipt_path.write_text(json.dumps(receipt))
    source_database = tmp_path / ".beads" / "dolt"
    source_database.mkdir()
    with pytest.raises(TaskError, match="ambiguous") as dual:
        tasks.execute(**request)
    assert dual.value.code == ErrorCode.OPERATION_FAILED
    assert database.is_dir()
    assert not boundary.calls


@pytest.mark.parametrize(
    ("backend_result", "expected_code"),
    (
        (ExecutionResult(command=(), exit_status=None, stdout=b"", stderr=b"", timed_out=True), "OWNER_UNAVAILABLE"),
        (ExecutionResult(command=(), exit_status=0, stdout=b"x" * (MAX_TASK_OUTPUT_BYTES + 1), stderr=b""), "RESOURCE_EXHAUSTED"),
        (ExecutionResult(command=(), exit_status=1, stdout=b"", stderr=b"private backend detail"), "OPERATION_FAILED"),
        (ExecutionResult(command=(), exit_status=0, stdout=b"not-json", stderr=b""), "RESULT_INVALID"),
    ),
)
def test_task_backend_failures_map_to_clean_error_envelopes(
    tmp_path: Path, backend_result: ExecutionResult, expected_code: str
) -> None:
    write_adapter(tmp_path)
    task_state_root = tmp_path / "task-state"
    activate_task_authority(tmp_path, task_state_root)
    tasks = TaskService(
        ProjectCatalog([tmp_path]),
        generic_jobs(tmp_path),
        FakeTaskBoundary([backend_result]),
        task_state_root=task_state_root,
    )
    service = SinnixdService(ProjectCatalog([tmp_path]), tasks=tasks)

    response = service.dispatch(
        request("task.get", "task-backend", {"project_id": "fixture", "task_id": "fixture-1"}, "observer")
    )

    assert response.error is not None
    assert response.error.code.value == expected_code
    assert "private backend detail" not in response.error.message


def test_task_rejects_unauthorized_principals_and_invalid_arguments(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    task_state_root = tmp_path / "task-state"
    activate_task_authority(tmp_path, task_state_root)
    tasks = TaskService(
        ProjectCatalog([tmp_path]),
        generic_jobs(tmp_path),
        FakeTaskBoundary([task_result({"ok": True})]),
        task_state_root=task_state_root,
    )
    service = SinnixdService(ProjectCatalog([tmp_path]), tasks=tasks)

    denied = service.dispatch(
        request("task.claim", "task-backend", {"project_id": "fixture", "task_id": "fixture-1"}, "observer")
    )
    invalid = service.dispatch(
        request("task.get", "task-backend", {"project_id": "fixture", "task_id": "--bad", "extra": True}, "observer")
    )
    missing_request_id = service.dispatch(
        request("task.claim", "task-backend", {"project_id": "fixture", "task_id": "fixture-1"}, "agent-control")
    )
    unknown = service.dispatch(
        request("task.list", "task-backend", {"project_id": "missing"}, "observer")
    )

    assert denied.error is not None and denied.error.code.value == "POLICY_DENIED"
    assert invalid.error is not None and invalid.error.code.value == "INVALID_ARGUMENT"
    assert missing_request_id.error is not None and missing_request_id.error.code.value == "INVALID_ARGUMENT"
    assert unknown.error is not None and unknown.error.code.value == "INVALID_ARGUMENT"
    assert not tasks.boundary.calls


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


def test_project_catalog_is_explicit_and_operation_catalog_is_bounded(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]))

    response = service.dispatch(request("project.operations", "project-adapters", {"project_id": "fixture"}))

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
        {"name": "attempts", "type": "integer", "flag": "--attempts", "min": 1, "max": 16},
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


def test_project_operations_reports_descriptor_drift(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]))
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(descriptor.read_text() + "\n# changed after daemon startup\n")

    response = service.dispatch(request("project.operations", "project-adapters", {"project_id": "fixture"}))

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


def test_user_systemd_jobs_starts_a_retained_service_with_log_boundary(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(args, **kwargs):
        calls.append((list(args), kwargs))
        return SimpleNamespace(stdout="")

    monkeypatch.setattr("sinnixd.jobs.subprocess.run", fake_run)

    UserSystemdJobs().start(
        unit="sinnixd-job-00000000-0000-0000-0000-000000000001.service",
        command=("nix", "develop", "--command", "lint"),
        working_directory="/work/project",
        environment={"HOME": "/home/sinity", "SINNIXD_JOB_ID": "job"},
        timeout_seconds=123,
        log_path=tmp_path / "job.log",
    )

    assert [args for args, _kwargs in calls] == [
        [
            "systemd-run",
            "--user",
            "--quiet",
            "--unit=sinnixd-job-00000000-0000-0000-0000-000000000001.service",
            "--slice=agent.slice",
            "--property=WorkingDirectory=/work/project",
            "--property=RuntimeMaxSec=123s",
            "--property=StandardOutput=journal",
            "--property=StandardError=journal",
            "--",
            str(capture_executable()),
            "--log-path",
            str(tmp_path / "job.log"),
            "--overflow-path",
            str(tmp_path / "job.overflow"),
            "--max-bytes",
            str(MAX_LOG_ARTIFACT_BYTES),
            "--",
            "/run/current-system/sw/bin/env",
            "-i",
            "HOME=/home/sinity",
            "SINNIXD_JOB_ID=job",
            "nix",
            "develop",
            "--command",
            "lint",
        ]
    ]
    assert calls[0][1] == {
        "check": True,
        "capture_output": True,
        "text": True,
        "timeout": SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    }


def test_user_systemd_calls_use_finite_timeouts_and_redact_timeout_details(
    monkeypatch, tmp_path: Path
) -> None:
    """Anti-vacuity: omitting subprocess timeouts leaves a control worker held by a stuck user manager."""
    calls: list[dict[str, object]] = []

    def fake_run(args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(stdout="LoadState=loaded\nActiveState=active\n")

    monkeypatch.setattr("sinnixd.jobs.subprocess.run", fake_run)
    systemd = UserSystemdJobs()
    systemd.start(
        unit="sinnixd-job-00000000-0000-0000-0000-000000000001.service",
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={},
        timeout_seconds=1,
        log_path=tmp_path / "job.log",
    )
    systemd.show("sinnixd-job-00000000-0000-0000-0000-000000000001.service")
    systemd.stop("sinnixd-job-00000000-0000-0000-0000-000000000001.service")

    assert [call["timeout"] for call in calls] == [
        SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    ]

    secret = "timeout-command-detail-must-not-escape"

    def timed_out(args, **kwargs):
        raise subprocess.TimeoutExpired([*args, secret], kwargs["timeout"])

    monkeypatch.setattr("sinnixd.jobs.subprocess.run", timed_out)
    with pytest.raises(SystemdJobTimeout) as error:
        systemd.show("sinnixd-job-00000000-0000-0000-0000-000000000001.service")
    assert str(error.value) == "systemd command timed out"
    assert secret not in str(error.value)

    monkeypatch.setattr(
        "sinnixd.jobs.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout="malformed-systemctl-output"),
    )
    with pytest.raises(SystemdJobError, match="show output is malformed"):
        systemd.show("sinnixd-job-00000000-0000-0000-0000-000000000001.service")


def test_user_systemd_os_error_reconciles_without_persisting_raw_error(monkeypatch, tmp_path: Path) -> None:
    """Anti-vacuity: raw subprocess OSErrors must enter the systemd reconciliation path."""
    secret = "systemd-run-os-error-do-not-persist"
    calls: list[str] = []

    def fake_run(args, **_kwargs):
        calls.append(args[0])
        if args[0] == "systemd-run":
            raise OSError(secret)
        return SimpleNamespace(stdout="LoadState=loaded\nActiveState=active\nResult=success\n")

    monkeypatch.setattr("sinnixd.jobs.subprocess.run", fake_run)
    jobs = GenericJobs(UserSystemdJobs(), GenericJobStore(tmp_path / "state"), wait_poll_seconds=0.001)

    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    persisted = (tmp_path / "state" / "jobs" / f"{started['job_id']}.json").read_text()

    assert calls == ["systemd-run", "systemctl"]
    assert started["state"]["phase"] == "running"
    assert secret not in persisted


def test_declared_and_foreground_jobs_share_the_generic_route(tmp_path: Path) -> None:
    """Anti-vacuity: deleting GenericJobs.start makes both launch assertions fail."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    service = SinnixdService(
        ProjectCatalog([tmp_path]),
        jobs=generic_jobs(tmp_path, systemd),
    )

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
    assert len(systemd.started) == 1
    assert systemd.started[0]["working_directory"] == str(tmp_path.resolve())
    assert systemd.started[0]["timeout_seconds"] == DEFAULT_TIMEOUT_SECONDS
    assert systemd.started[0]["environment"]["SINNIXD_JOB_ID"] == launch["job_id"]
    assert systemd.started[0]["environment"]["SINNIXD_OPERATION"] == "check"
    assert systemd.started[0]["environment"]["SINNIXD_CHECKOUT_ID"] == "default"
    assert systemd.started[0]["environment"]["SINNIXD_CHECKOUT_HEAD"] == launch["checkout"]["head"]
    assert launch["checkout"]["path"] == str(tmp_path.resolve())

    foreground = service.start_foreground(
        command=("fixture-foreground",),
        working_directory=str(tmp_path),
        environment={"EMPTY": ""},
        timeout_seconds=123,
    )
    assert foreground["kind"] == "foreground-command"
    assert len(systemd.started) == 2
    assert service.jobs.store.declared_launch(launch["job_id"])[0] == (
        "fixture-env", "--command", "fixture-check"
    )
    assert systemd.started[1]["command"] == ("fixture-foreground",)
    foreground_record = service.jobs.store.load(foreground["job_id"])
    assert foreground_record.spec.to_dict()["environment_keys"] == ["EMPTY", "SINNIXD_JOB_ID"]

    status = service.dispatch(request("job.get", "systemd-jobs", {"job_id": launch["job_id"]}))
    cancelled = service.dispatch(
        request("job.cancel", "systemd-jobs", {"job_id": launch["job_id"]})
    )

    assert status.ok
    assert status.payload is not None
    assert status.payload.inline["state"]["systemd"]["MainPID"] == "42"
    assert cancelled.ok
    assert systemd.stopped == [launch["unit"]]


def test_declared_operation_timeout_contract_reaches_systemd(tmp_path: Path) -> None:
    """Anti-vacuity: a descriptor timeout must become the transient unit bound."""
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
    systemd = FakeSystemdJobs()
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd))

    started = service.dispatch(
        request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "long_running"})
    )

    assert started.ok and started.payload is not None
    assert started.payload.inline["timeout_seconds"] == 7200
    assert service.jobs.store.declared_launch(started.payload.inline["job_id"])[0] == (
        "fixture-env", "--command", "fixture-long"
    )
    assert systemd.started[0]["timeout_seconds"] == 7200


def test_declared_parameters_canonicalize_argv_and_persist_only_the_digest(tmp_path: Path) -> None:
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
        "fixture-env", "--command", "fixture-check", "--full", "--package", "sinexd", "--package", "xtask"
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
    tmp_path: Path, parameters: dict[str, object]
) -> None:
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd))

    response = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "parameterized", "parameters": parameters},
        )
    )

    assert response.error is not None
    assert response.error.code.value == "INVALID_ARGUMENT"
    assert systemd.started == []


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
    tmp_path: Path, parameters: dict[str, object]
) -> None:
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd))

    response = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "generic_extended_parameters", "parameters": parameters},
        )
    )

    assert response.error is not None
    assert response.error.code.value == "INVALID_ARGUMENT"
    assert systemd.started == []


def test_generic_extended_parameters_derive_canonical_argv_and_digest(tmp_path: Path) -> None:
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
        "fixture-env", "--command", "fixture-check",
        "--profile", "strict", "--attempts", "4",
        "--features", "serde", "--features", "tokio",
        "--package", "sinexd", "--package", "xtask",
    )
    assert started.payload.inline["parameters"] == {
        "digest": hashlib.sha256(
            json.dumps(expected_canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
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
    tmp_path: Path, parameters: dict[str, object]
) -> None:
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd))

    response = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "sinex_all_sources", "parameters": parameters},
        )
    )

    assert response.error is not None
    assert response.error.code.value == "INVALID_ARGUMENT"
    assert systemd.started == []


def test_sinex_all_sources_fixture_derives_exact_argv_and_digest(tmp_path: Path) -> None:
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
        "fixture-env", "--command", "xtask", "run", "all-sources",
        "--instance-id", "operator-source-driver-browser.history-3",
        "--reconcile",
        "--service-name", "source-driver-browser.history-3",
        "--include-default-excluded",
    )
    assert started.payload.inline["parameters"] == {
        "digest": hashlib.sha256(
            json.dumps(expected_canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
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
        "fixture-env", "--command", "xtask", "verify", "closure", "sinex-a1b2", "--json", "--dry-run",
    )
    assert started.payload.inline["parameters"] == {
        "digest": hashlib.sha256(b'{"bead_id":"sinex-a1b2","dry_run":true,"json":true}').hexdigest()
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
    tmp_path: Path, parameters: dict[str, object]
) -> None:
    """Anti-vacuity: rejected required positionals must not create a systemd job."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd))

    response = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "verify_closure", "parameters": parameters},
        )
    )

    assert response.error is not None
    assert response.error.code.value == "INVALID_ARGUMENT"
    assert systemd.started == []


def test_fixed_operation_rejects_parameters_and_retains_its_declared_argv(tmp_path: Path) -> None:
    """Anti-vacuity: parameters must not create an argv authority for fixed operations."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd))

    fixed = service.dispatch(
        request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "check", "parameters": {}})
    )
    rejected = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "check", "parameters": {"full": True}},
        )
    )

    assert fixed.ok and fixed.payload is not None
    assert service.jobs.store.declared_launch(fixed.payload.inline["job_id"])[0] == (
        "fixture-env", "--command", "fixture-check"
    )
    assert rejected.error is not None
    assert rejected.error.code.value == "INVALID_ARGUMENT"
    assert len(systemd.started) == 1


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
    tmp_path: Path, operation: str, content: bytes, overflowed: bool, expected: dict[str, str] | None
) -> None:
    """Anti-vacuity: result artifacts must reject injected, malformed, and overflowed JSON."""
    write_adapter(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": operation}))
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
            "artifact": {"ref": f"sinnix://jobs/{job_id}/artifacts/result", "max_bytes": 64_000, "kind": kind},
        }
    else:
        with pytest.raises(JobResultError):
            jobs.result(job_id)
        response = service.dispatch(request("job.result", "systemd-jobs", {"job_id": job_id}))
        assert response.error is not None
        assert response.error.code.value == "RESULT_INVALID"


def test_declared_json_result_respects_the_callers_response_budget(tmp_path: Path) -> None:
    """Anti-vacuity: typed JSON must not bypass job.result's max_bytes contract."""
    write_adapter(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "parameterized"}))
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    record = jobs.store.load(job_id)
    assert record.result_path is not None
    record.result_path.write_bytes(b'{"receipt":"ok"}')

    with pytest.raises(JobResultLimitError, match="requested response limit"):
        jobs.result(job_id, max_bytes=8)
    response = service.dispatch(request("job.result", "systemd-jobs", {"job_id": job_id, "max_bytes": 8}))
    assert response.error is not None
    assert response.error.code.value == "RESOURCE_EXHAUSTED"


def test_capture_separates_json_stdout_from_logs(tmp_path: Path) -> None:
    log_path = tmp_path / "job.log"
    result_path = tmp_path / "job.result"
    log_path.touch(mode=0o600)
    assert capture_main(
        (
            "--log-path", str(log_path), "--overflow-path", str(tmp_path / "job.overflow"), "--max-bytes", "64",
            "--result-path", str(result_path), "--result-overflow-path", str(tmp_path / "result.overflow"),
            "--", "/bin/sh", "-c", "printf '{\"receipt\":true}'; printf diagnostic >&2",
        )
    ) == 0
    assert json.loads(result_path.read_text()) == {"receipt": True}
    assert "diagnostic" in log_path.read_text()


def test_capture_writes_to_the_store_preallocated_log_artifact(tmp_path: Path) -> None:
    """Anti-vacuity: the real GenericJobStore log reservation remains capturable."""
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    record = jobs.store.load(started["job_id"])
    assert record.log_path.exists()

    assert capture_main(
        (
            "--log-path", str(record.log_path), "--overflow-path", str(record.log_path.with_suffix(".overflow")),
            "--max-bytes", "64", "--", "/bin/sh", "-c", "printf captured-log",
        )
    ) == 0
    assert record.log_path.read_text() == "captured-log"


def test_capture_refuses_hostile_artifact_symlinks(tmp_path: Path) -> None:
    """Anti-vacuity: a job process cannot redirect capture artifacts through a same-user symlink."""
    protected = tmp_path / "protected"
    protected.write_text("keep")
    log_path = tmp_path / "job.log"
    result_path = tmp_path / "job.result"
    log_path.touch(mode=0o600)
    result_path.symlink_to(protected)

    with pytest.raises(FileExistsError):
        capture_main(
            (
                "--log-path", str(log_path), "--overflow-path", str(tmp_path / "job.overflow"), "--max-bytes", "64",
                "--result-path", str(result_path), "--result-overflow-path", str(tmp_path / "result.overflow"),
                "--", "/bin/true",
            )
        )
    assert protected.read_text() == "keep"


def test_job_reconciliation_marks_missing_units_without_daemon_owned_state(tmp_path: Path) -> None:
    """Anti-vacuity: deleting GenericJobs.get's systemd.show call loses the missing phase."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs(properties={"LoadState": "not-found", "ActiveState": "inactive"})
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd))

    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "check"}))
    assert started.payload is not None

    response = service.dispatch(request("job.get", "systemd-jobs", {"job_id": started.payload.inline["job_id"]}))

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


def test_workspace_create_is_git_derived_durable_and_restart_safe(tmp_path: Path) -> None:
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
    assert workspace["managed"]
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
        request("workspace.get", "git-workspaces", {"workspace_id": workspace["workspace_id"]})
    )
    assert recovered.ok and recovered.payload is not None
    assert recovered.payload.inline["head"] == workspace["head"]
    assert recovered.payload.inline["checkout_id"].startswith("worktree-")


def test_workspace_adopt_uses_existing_linked_checkout_without_claiming_creation(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    linked = tmp_path / "external-linked"
    subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "add", "-b", "feature/adopted", str(linked), "HEAD"],
        check=True,
        capture_output=True,
    )
    catalog = ProjectCatalog([tmp_path])
    checkout = next(item for item in catalog.checkouts("fixture") if item.path == linked)
    service = SinnixdService(catalog, jobs=generic_jobs(tmp_path))

    adopted = service.dispatch(
        request(
            "workspace.adopt",
            "git-workspaces",
            {"project_id": "fixture", "checkout_id": checkout.checkout_id, "name": "adopted-lane"},
            "operator",
        )
    )

    assert adopted.ok and adopted.payload is not None
    assert adopted.payload.inline["path"] == str(linked)
    assert not adopted.payload.inline["managed"]
    assert adopted.payload.inline["current_branch"] == "feature/adopted"


def test_workspace_mutations_reject_weak_principals_paths_refs_and_duplicates(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    arguments = {
        "project_id": "fixture",
        "name": "safe-lane",
        "branch": "feature/safe-lane",
        "base": "HEAD",
    }

    weak = service.dispatch(request("workspace.create", "git-workspaces", arguments, "observer"))
    escaped = service.dispatch(
        request("workspace.create", "git-workspaces", {**arguments, "name": "../escape"}, "agent-control")
    )
    invalid_ref = service.dispatch(
        request("workspace.create", "git-workspaces", {**arguments, "base": "missing-ref"}, "agent-control")
    )
    created = service.dispatch(request("workspace.create", "git-workspaces", arguments, "agent-control"))
    duplicate = service.dispatch(request("workspace.create", "git-workspaces", arguments, "agent-control"))
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
        project_id="fixture", name="drift-lane", branch="feature/drift-lane", base="HEAD"
    )
    path = Path(created["path"])
    (path / "untracked.txt").write_text("operator work\n")
    subprocess.run(["git", "-C", str(path), "switch", "--detach"], check=True, capture_output=True)

    observed = service.workspaces.get(created["workspace_id"])

    assert observed["state"] == "missing"
    assert observed["dirty"] is None
    assert not observed["identity_matches"]


def test_workspace_reap_forgets_missing_and_removes_only_clean_contained_managed_worktrees(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    missing = service.workspaces.create(
        project_id="fixture", name="missing-lane", branch="feature/missing-lane", base="HEAD"
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "remove", missing["path"]],
        check=True,
        capture_output=True,
    )

    forgotten = service.dispatch(
        request(
            "workspace.reap",
            "git-workspaces",
            {"workspace_id": missing["workspace_id"]},
            "operator",
        )
    )
    clean = service.workspaces.create(
        project_id="fixture", name="clean-lane", branch="feature/clean-lane", base="HEAD"
    )
    reaped = service.workspaces.reap(clean["workspace_id"])

    assert forgotten.ok and forgotten.payload is not None
    assert forgotten.payload.inline["relationship_only"]
    assert reaped["reaped"] and not reaped["relationship_only"]
    assert not Path(clean["path"]).exists()
    assert service.workspaces.list("fixture") == {"workspaces": []}


def test_delivery_rejects_pending_hosted_checks() -> None:
    assert not GitHubDelivery._checks_pass(
        [{"__typename": "StatusContext", "context": "ci", "state": "PENDING"}]
    )
    assert GitHubDelivery._checks_pass(
        [
            {"__typename": "StatusContext", "context": "ci", "state": "SUCCESS"},
            {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "NEUTRAL"},
        ]
    )


def test_workspace_reap_preserves_dirty_divergent_and_adopted_worktrees(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    dirty = service.workspaces.create(
        project_id="fixture", name="dirty-lane", branch="feature/dirty-lane", base="HEAD"
    )
    dirty_path = Path(dirty["path"])
    (dirty_path / "operator.txt").write_text("preserve\n")
    divergent = service.workspaces.create(
        project_id="fixture", name="divergent-lane", branch="feature/divergent-lane", base="HEAD"
    )
    divergent_path = Path(divergent["path"])
    (divergent_path / "committed.txt").write_text("unique\n")
    subprocess.run(["git", "-C", str(divergent_path), "add", "committed.txt"], check=True)
    subprocess.run(
        [
            "git", "-C", str(divergent_path), "-c", "user.name=Fixture", "-c",
            "user.email=fixture@example.test", "commit", "--quiet", "-m", "diverge",
        ],
        check=True,
    )
    external = tmp_path / "external-reap"
    subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "add", "-b", "feature/external-reap", str(external), "HEAD"],
        check=True,
        capture_output=True,
    )
    checkout = next(item for item in service.projects.checkouts("fixture") if item.path == external)
    adopted = service.workspaces.adopt(project_id="fixture", checkout_id=checkout.checkout_id, name="adopted-reap")

    for workspace_id in (dirty["workspace_id"], divergent["workspace_id"], adopted["workspace_id"]):
        with pytest.raises(ValueError):
            service.workspaces.reap(workspace_id)

    assert (dirty_path / "operator.txt").read_text() == "preserve\n"
    assert divergent_path.is_dir()
    assert external.is_dir()


def test_workspace_dispose_deletes_a_clean_no_pr_branch_without_checkpoint_content(tmp_path: Path) -> None:
    """Anti-vacuity: disposal must remove both Git objects, not just the workspace record."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    workspace = service.workspaces.create(
        project_id="fixture", name="verification-lane", branch="feature/verification-lane", base="HEAD"
    )
    checkpoint = service.workspaces.checkpoint(workspace["workspace_id"])
    gitdir = replace_worktree_gitfile_with_symlink(Path(workspace["path"]))
    assert gitdir.is_dir()

    disposed = service.dispatch(
        request(
            "workspace.dispose",
            "git-workspaces",
            {"workspace_id": workspace["workspace_id"]},
            "operator",
        )
    )

    assert disposed.ok and disposed.payload is not None
    assert disposed.payload.inline["disposed"]
    assert disposed.payload.inline["deleted_branch"] == workspace["branch"]
    assert not Path(workspace["path"]).exists()
    assert not (service.workspaces.store.checkpoints_root / workspace["workspace_id"] / checkpoint["checkpoint_id"]).exists()
    assert service.workspaces.list("fixture") == {"workspaces": []}


def test_workspace_finish_integrated_accepts_cherry_picked_tree_and_rejects_missing_change(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Fixture"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "fixture@example.test"], check=True)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    workspace = service.workspaces.create(
        project_id="fixture", name="integrated", branch="feature/integrated", base="HEAD"
    )
    workspace_path = Path(workspace["path"])
    (workspace_path / "integrated.txt").write_text("represented exactly\n")
    subprocess.run(["git", "-C", str(workspace_path), "add", "integrated.txt"], check=True)
    subprocess.run(["git", "-C", str(workspace_path), "commit", "--quiet", "-m", "integrated"], check=True)

    with pytest.raises(WorkspaceError, match="not fully represented"):
        service.workspaces.finish_integrated(workspace["workspace_id"], "master")

    source_head = subprocess.run(
        ["git", "-C", str(workspace_path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    subprocess.run(["git", "-C", str(tmp_path), "cherry-pick", source_head], check=True, capture_output=True)
    target_head = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(tmp_path), "update-ref", "refs/remotes/origin/master", target_head], check=True
    )
    gitdir = replace_worktree_gitfile_with_symlink(workspace_path)
    assert gitdir.is_dir()

    finished = service.workspaces.finish_integrated(workspace["workspace_id"], target_head)

    assert finished == {
        "workspace_id": workspace["workspace_id"],
        "finished": True,
        "head": source_head,
        "integration_target": target_head,
    }
    assert not workspace_path.exists()
    assert not service.workspaces.list()["workspaces"]
    assert subprocess.run(
        ["git", "-C", str(tmp_path), "show-ref", "--verify", "--quiet", f"refs/heads/{workspace['branch']}"]
    ).returncode == 1


def test_workspace_gitfile_symlink_rejects_mismatched_and_outside_targets_without_mutation(tmp_path: Path) -> None:
    """Anti-vacuity: only the exact registered administrative gitdir may be canonicalized."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    first = service.workspaces.create(
        project_id="fixture", name="symlink-first", branch="feature/symlink-first", base="HEAD"
    )
    second = service.workspaces.create(
        project_id="fixture", name="symlink-second", branch="feature/symlink-second", base="HEAD"
    )
    first_path = Path(first["path"])
    first_checkout = next(item for item in service.projects.checkouts("fixture") if item.path == first_path)
    second_gitdir = Path((Path(second["path"]) / ".git").read_text().strip().removeprefix("gitdir: "))
    first_gitfile = first_path / ".git"
    first_gitfile.unlink()
    first_gitfile.symlink_to(second_gitdir)

    with pytest.raises(WorkspaceError, match="does not match its registered worktree gitdir"):
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


def test_workspace_dispose_refuses_dirty_divergent_unpublished_and_checkpoint_only_content(tmp_path: Path) -> None:
    """Anti-vacuity: each rejection leaves the managed worktree and branch available for recovery."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    dirty = service.workspaces.create(
        project_id="fixture", name="dispose-dirty", branch="feature/dispose-dirty", base="HEAD"
    )
    (Path(dirty["path"]) / "operator.txt").write_text("preserve\n")
    divergent = service.workspaces.create(
        project_id="fixture", name="dispose-divergent", branch="feature/dispose-divergent", base="HEAD"
    )
    subprocess.run(["git", "-C", divergent["path"], "switch", "-c", "feature/dispose-replaced"], check=True)
    unpublished = service.workspaces.create(
        project_id="fixture", name="dispose-unpublished", branch="feature/dispose-unpublished", base="HEAD"
    )
    unpublished_path = Path(unpublished["path"])
    (unpublished_path / "unpublished.txt").write_text("preserve\n")
    subprocess.run(["git", "-C", str(unpublished_path), "add", "unpublished.txt"], check=True)
    subprocess.run(
        [
            "git", "-C", str(unpublished_path), "-c", "user.name=Fixture", "-c",
            "user.email=fixture@example.test", "commit", "--quiet", "-m", "unpublished",
        ],
        check=True,
    )
    checkpoint_only = service.workspaces.create(
        project_id="fixture", name="dispose-checkpoint", branch="feature/dispose-checkpoint", base="HEAD"
    )
    checkpoint_path = Path(checkpoint_only["path"])
    (checkpoint_path / "recoverable.txt").write_text("preserve\n")
    service.workspaces.checkpoint(checkpoint_only["workspace_id"])
    (checkpoint_path / "recoverable.txt").unlink()

    for workspace in (dirty, divergent, unpublished, checkpoint_only):
        with pytest.raises(ValueError):
            service.workspaces.dispose(workspace["workspace_id"])
        assert Path(workspace["path"]).is_dir()
        assert subprocess.run(
            ["git", "-C", str(tmp_path), "show-ref", "--verify", "--quiet", f"refs/heads/{workspace['branch']}"]
        ).returncode == 0


def test_workspace_checkpoint_restore_round_trips_index_worktree_and_untracked_state(tmp_path: Path) -> None:
    """Anti-vacuity: dropping any artifact loses one of the three asserted Git states."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    created = service.workspaces.create(
        project_id="fixture", name="checkpoint-lane", branch="feature/checkpoint-lane", base="HEAD"
    )
    path = Path(created["path"])
    (path / "flake.nix").write_text('{"staged": true}\n')
    subprocess.run(["git", "-C", str(path), "add", "flake.nix"], check=True)
    with (path / "flake.nix").open("a") as handle:
        handle.write("unstaged\n")
    (path / "untracked.txt").write_text("untracked payload\n")

    checkpoint = service.workspaces.checkpoint(created["workspace_id"])
    subprocess.run(["git", "-C", str(path), "reset", "--hard", "HEAD"], check=True, capture_output=True)
    (path / "untracked.txt").unlink()
    restored = service.workspaces.restore(created["workspace_id"], checkpoint["checkpoint_id"])

    assert restored["restored"]
    assert (path / "flake.nix").read_text() == '{"staged": true}\nunstaged\n'
    assert (path / "untracked.txt").read_text() == "untracked payload\n"
    assert "staged" in subprocess.run(
        ["git", "-C", str(path), "diff", "--cached"], check=True, capture_output=True, text=True
    ).stdout
    assert "unstaged" in subprocess.run(
        ["git", "-C", str(path), "diff"], check=True, capture_output=True, text=True
    ).stdout


def test_workspace_restore_rejects_dirty_or_stale_head_targets(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    created = service.workspaces.create(
        project_id="fixture", name="restore-guards", branch="feature/restore-guards", base="HEAD"
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
            "git", "-C", str(path), "-c", "user.name=Fixture", "-c",
            "user.email=fixture@example.test", "commit", "--quiet", "-m", "advance",
        ],
        check=True,
    )
    with pytest.raises(ValueError, match="source HEAD"):
        service.workspaces.restore(created["workspace_id"], checkpoint["checkpoint_id"])


def test_workspace_recover_recreates_missing_exact_head_and_restores_checkpoint(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    created = service.workspaces.create(
        project_id="fixture", name="recover-lane", branch="feature/recover-lane", base="HEAD"
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

    recovered = service.workspaces.recover(created["workspace_id"], checkpoint["checkpoint_id"])

    assert recovered["recovered"] and recovered["path"] == str(path)
    assert (path / "flake.nix").read_text() == '{"recovered": true}\n'
    assert (path / "untracked.txt").read_text() == "preserved\n"
    assert "recovered" in subprocess.run(
        ["git", "-C", str(path), "diff", "--cached"], check=True, capture_output=True, text=True
    ).stdout


def test_workspace_stack_restacks_child_onto_parent_and_survives_restart(tmp_path: Path) -> None:
    """Anti-vacuity: the durable parent edge drives a real Git rebase after restart."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Fixture"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "fixture@example.test"], check=True)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    parent = service.workspaces.create(
        project_id="fixture", name="parent-lane", branch="feature/parent", base="HEAD"
    )
    child = service.workspaces.stack(
        parent_workspace_id=parent["workspace_id"], name="child-lane", branch="feature/child"
    )
    parent_path = Path(parent["path"])
    child_path = Path(child["path"])
    (child_path / "child.txt").write_text("child\n")
    subprocess.run(["git", "-C", str(child_path), "add", "child.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(child_path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "child"],
        check=True,
    )
    child_before = subprocess.run(
        ["git", "-C", str(child_path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    (parent_path / "parent.txt").write_text("parent\n")
    subprocess.run(["git", "-C", str(parent_path), "add", "parent.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(parent_path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "parent"],
        check=True,
    )

    restarted = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    result = restarted.workspaces.restack(child["workspace_id"])

    assert result["restacked"] and result["before_head"] == child_before
    assert result["parent_workspace_id"] == parent["workspace_id"]
    assert result["head"] != child_before
    assert (child_path / "parent.txt").read_text() == "parent\n"
    with pytest.raises(ValueError, match="stacked children"):
        restarted.workspaces.reap(parent["workspace_id"])


def test_workspace_restack_detaches_child_after_squash_equivalent_parent_disappears(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Fixture"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "fixture@example.test"], check=True)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    parent = service.workspaces.create(
        project_id="fixture", name="merged-parent", branch="feature/merged-parent", base="HEAD"
    )
    child = service.workspaces.stack(
        parent_workspace_id=parent["workspace_id"], name="surviving-child", branch="feature/surviving-child"
    )
    child_path = Path(child["path"])
    (child_path / "child.txt").write_text("child\n")
    subprocess.run(["git", "-C", str(child_path), "add", "child.txt"], check=True)
    subprocess.run(["git", "-C", str(child_path), "commit", "--quiet", "-m", "child"], check=True)
    parent_path = Path(parent["path"])
    (parent_path / "parent.txt").write_text("parent\n")
    subprocess.run(["git", "-C", str(parent_path), "add", "parent.txt"], check=True)
    subprocess.run(["git", "-C", str(parent_path), "commit", "--quiet", "-m", "parent"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "merge", "--squash", parent["branch"]], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "--quiet", "-m", "merged parent"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "update-ref", "refs/remotes/origin/master", "HEAD"], check=True
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "remove", "--force", str(parent_path)], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "branch", "-D", parent["branch"]], check=True)

    restacked = service.workspaces.restack(child["workspace_id"])

    assert restacked["restacked"] and restacked["detached_merged_parent"]
    assert (child_path / "parent.txt").read_text() == "parent\n"
    assert (child_path / "child.txt").read_text() == "child\n"
    forgotten = service.workspaces.reap(parent["workspace_id"])
    assert forgotten["relationship_only"]


@pytest.mark.parametrize(
    ("conflict_path", "expected_class"),
    [("fixture.lock", "exact-file"), ("generated.json", "generated-surface"), ("ordinary.txt", "hard")],
)
def test_workspace_restack_reports_declared_collision_without_mutating_child(
    tmp_path: Path, conflict_path: str, expected_class: str
) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    parent = service.workspaces.create(
        project_id="fixture", name="collision-parent", branch="feature/collision-parent", base="HEAD"
    )
    child = service.workspaces.stack(
        parent_workspace_id=parent["workspace_id"], name="collision-child", branch="feature/collision-child"
    )
    for workspace, content, message in ((parent, "parent\n", "parent lock"), (child, "child\n", "child lock")):
        path = Path(workspace["path"])
        (path / conflict_path).write_text(content)
        subprocess.run(["git", "-C", str(path), "add", conflict_path], check=True)
        subprocess.run(
            ["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", message],
            check=True,
        )
    child_head = subprocess.run(
        ["git", "-C", child["path"], "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()

    result = service.workspaces.restack(child["workspace_id"])

    assert not result["restacked"]
    assert result["collisions"] == [{"path": conflict_path, "class": expected_class}]
    assert subprocess.run(
        ["git", "-C", child["path"], "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip() == child_head


def test_workspace_restack_reports_semantic_slot_collision_across_different_paths(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    parent = service.workspaces.create(
        project_id="fixture", name="slot-parent", branch="feature/slot-parent", base="HEAD"
    )
    child = service.workspaces.stack(
        parent_workspace_id=parent["workspace_id"], name="slot-child", branch="feature/slot-child"
    )
    for workspace, relative, content in (
        (parent, "registry/parent.toml", "parent = true\n"),
        (child, "registry/child.toml", "child = true\n"),
    ):
        path = Path(workspace["path"])
        (path / "registry").mkdir()
        (path / relative).write_text(content)
        subprocess.run(["git", "-C", str(path), "add", relative], check=True)
        subprocess.run(
            ["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", relative],
            check=True,
        )

    result = service.workspaces.restack(child["workspace_id"])

    assert result["collisions"] == [
        {
            "class": "semantic-slot",
            "slot": "fixture-registry",
            "child_paths": "registry/child.toml",
            "parent_paths": "registry/parent.toml",
        }
    ]


def test_declared_job_binds_workspace_and_exact_head(tmp_path: Path) -> None:
    """Anti-vacuity: workspace verification launches in that checkout and persists its HEAD."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    workspace = service.workspaces.create(
        project_id="fixture", name="verify-lane", branch="feature/verify-lane", base="HEAD"
    )
    assert service.workspaces.resolve_checkout("fixture", workspace["checkout_id"]).path == Path(workspace["path"])

    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "check", "workspace_id": "verify-lane"},
        )
    )

    assert started.ok and started.payload is not None
    record = jobs.store.load(started.payload.inline["job_id"])
    assert record.spec.working_directory == workspace["path"]
    assert record.spec.checkout is not None
    assert record.spec.checkout["checkout_id"] == workspace["checkout_id"]
    assert record.spec.checkout["head"] == workspace["head"]


def test_forged_packet_completion_arguments_have_no_service_route(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    workspace = service.workspaces.create(
        project_id="fixture", name="packet-lane", branch="feature/packet-lane", base="HEAD"
    )
    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "check", "workspace_id": workspace["workspace_id"]},
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


def test_delivery_snapshot_is_nul_safe_and_exact_file_scope_does_not_include_descendants(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    workspace = service.workspaces.create(project_id="fixture", name="snapshot-lane", branch="feature/snapshot", base="HEAD")
    path = Path(workspace["path"])
    (path / "dir").mkdir()
    (path / "dir" / "exact").write_text("old\n")
    (path / "dir" / "delete\nfile").write_text("delete\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "seed"], check=True)
    start = service.workspaces.get(workspace["workspace_id"])["head"]
    subprocess.run(["git", "-C", str(path), "mv", "dir/exact", "dir/renamed\nfile"], check=True)
    (path / "dir" / "delete\nfile").unlink()
    (path / "dir" / "exact.child").write_text("outside exact-file scope\n")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "paths"], check=True)
    snapshot = service.workspaces.delivery_snapshot(workspace["workspace_id"], start, scope=("dir/exact",))
    assert not snapshot["in_scope"]
    assert {change["status"][0] for change in snapshot["changes"]} >= {"D", "R", "A"}
    assert any("\n" in item for change in snapshot["changes"] for item in change["paths"])
    assert service.workspaces.delivery_snapshot(workspace["workspace_id"], start, scope=("dir/",))["in_scope"]


def test_beads_bound_packet_and_exact_head_verifier_compose_into_delivery(tmp_path: Path) -> None:
    """The accepting path joins two authoritative jobs; neither can substitute for the other."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    native = tmp_path / "native-runner"
    native_runner(native)
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs, native_runner=native)
    workspace = service.workspaces.create(
        project_id="fixture", name="packet-delivery", branch="feature/packet-delivery", base="HEAD"
    )
    checkout_id = workspace["checkout_id"]
    binding = {
        "bead_ref": "sinnix://projects/fixture/beads/fixture-1",
        "project_ref": "sinnix://projects/fixture",
        "checkout_ref": f"sinnix://projects/fixture/checkouts/{checkout_id}",
        "task_revision": "a" * 64,
        "task_etag": "b" * 64,
        "claim_ref": f"sinnix://projects/fixture/beads/fixture-1/claims/{'c' * 64}",
        "claim_receipt": {
            "ref": f"sinnix://projects/fixture/beads/fixture-1/claims/{'c' * 64}",
            "owner_route": "beads.cli",
        },
        "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b",
        "assignment_ref": None,
        "write_scope": ["delivery.txt", "obsolete.txt"],
    }
    path = Path(workspace["path"])
    (path / "obsolete.txt").write_text("remove me\n")
    subprocess.run(["git", "-C", str(path), "add", "obsolete.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "seed deletion"],
        check=True,
    )
    packet = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {
                "project_id": "fixture", "checkout_id": checkout_id, "prompt": "return structured delivery",
                "backend": "codex", "model": "fixture", "effort": "high",
                "credential_profile": "subscription", "timeout_seconds": 60,
                "result": "last-message", "bead_binding": binding,
            },
            "agent-control",
        )
    )
    assert packet.ok and packet.payload is not None
    packet_id = packet.payload.inline["job_id"]
    packet_record = jobs.store.load(packet_id)
    start_head = packet_record.spec.checkout["head"]
    (path / "delivery.txt").write_text("delivered\n")
    (path / "obsolete.txt").unlink()
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "delivery"],
        check=True,
    )
    final_head = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    worker_delivery = {
        "anti_vacuity": True,
        "unresolved_work": [],
        "delegation": {"visibility": "unsupported", "pending": None},
        "deletion_evidence": ["obsolete.txt"],
        "evidence_only": False,
    }
    assert packet_record.result_path is not None
    packet_record.result_path.write_text(json.dumps({
        "schema_version": 1, "job_id": packet_id, "start_head": start_head,
        "final_head": final_head, "delivery": worker_delivery,
    }))
    jobs_module._write_private_marker(jobs_module._completion_marker_path(packet_record.log_path))
    systemd.properties = {
        "LoadState": "loaded", "ActiveState": "inactive", "Result": "success",
        "ExecMainStatus": "0", "InvocationID": "fixture-invocation",
    }
    assert jobs.get(packet_id)["state"]["phase"] == "succeeded"
    verifier = service.dispatch(request(
        "job.start", "systemd-jobs",
        {
            "project_id": "fixture", "operation": "check", "workspace_id": workspace["workspace_id"],
            "bead_binding": binding,
        },
    ))
    assert verifier.ok and verifier.payload is not None
    verifier_id = verifier.payload.inline["job_id"]
    assert jobs.get(verifier_id)["state"]["phase"] == "succeeded"

    delivery = GitHubDelivery(service.projects, service.workspaces, jobs)
    _workspace, _project, receipt = delivery._verified_workspace(
        workspace["workspace_id"], verifier_id, packet_id
    )
    assert receipt["bead_ref"] == binding["bead_ref"]
    assert receipt["head"] == final_head

    (path / "dirty.txt").write_text("uncommitted\n")
    with pytest.raises(DeliveryError, match="exact HEAD"):
        delivery._verified_workspace(workspace["workspace_id"], verifier_id, packet_id)
    (path / "dirty.txt").unlink()

    bad_binding = {**binding, "write_scope": ["other.txt"]}
    jobs.store.save(replace(
        packet_record,
        spec=replace(packet_record.spec, contract={**packet_record.spec.contract, "bead_binding": bad_binding}),
    ))
    verifier_record = jobs.store.load(verifier_id)
    jobs.store.save(replace(
        verifier_record,
        spec=replace(verifier_record.spec, contract={**verifier_record.spec.contract, "bead_binding": bad_binding}),
    ))
    with pytest.raises(DeliveryError, match="write scope"):
        delivery._verified_workspace(workspace["workspace_id"], verifier_id, packet_id)
    jobs.store.save(packet_record)
    jobs.store.save(verifier_record)

    for evidence in ([], ["unrelated.txt"]):
        packet_record.result_path.write_text(json.dumps({
            "schema_version": 1, "job_id": packet_id, "start_head": start_head,
            "final_head": final_head,
            "delivery": {**worker_delivery, "deletion_evidence": evidence},
        }))
        with pytest.raises(DeliveryError, match="deletion evidence"):
            delivery._verified_workspace(workspace["workspace_id"], verifier_id, packet_id)

    packet_record.result_path.write_text(json.dumps({
        "schema_version": 1, "job_id": packet_id, "start_head": start_head,
        "final_head": final_head,
        "delivery": {**worker_delivery, "unresolved_work": ["still running"]},
    }))
    with pytest.raises(DeliveryError, match="incomplete"):
        delivery._verified_workspace(workspace["workspace_id"], verifier_id, packet_id)
    packet_record.result_path.write_text(json.dumps({
        "schema_version": 1, "job_id": packet_id, "start_head": start_head,
        "final_head": final_head, "delivery": worker_delivery,
    }))

    packet_record.result_path.write_text(json.dumps({
        "schema_version": 1, "job_id": packet_id, "start_head": start_head,
        "final_head": final_head, "delivery": None,
    }))
    with pytest.raises(DeliveryError, match="malformed"):
        delivery._verified_workspace(workspace["workspace_id"], verifier_id, packet_id)
    packet_record.result_path.write_text(json.dumps({
        "schema_version": 1, "job_id": packet_id, "start_head": start_head,
        "final_head": final_head, "delivery": worker_delivery,
    }))

    for scope in (["../outside"], [f"entry-{index}" for index in range(129)]):
        rejected = service.dispatch(request(
            "job.start", "systemd-jobs",
            {
                "project_id": "fixture", "operation": "check", "workspace_id": workspace["workspace_id"],
                "bead_binding": {**binding, "write_scope": scope},
            },
        ))
        assert not rejected.ok

    (path / "later.txt").write_text("post-terminal\n")
    subprocess.run(["git", "-C", str(path), "add", "later.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "later"],
        check=True,
    )
    with pytest.raises(DeliveryError, match="exact HEAD"):
        delivery._verified_workspace(workspace["workspace_id"], verifier_id, packet_id)


def test_packet_runner_seals_worker_report_to_runtime_observed_head(tmp_path: Path) -> None:
    initialize_git_checkout(tmp_path)
    start_head = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    (tmp_path / "change.txt").write_text("change\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "change.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "change"],
        check=True,
    )
    final_head = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    result_root = tmp_path / "private-results"
    result_root.mkdir(mode=0o700)
    result_path = result_root / "packet.result"
    result_path.touch(mode=0o600)
    delivery = {
        "anti_vacuity": True, "unresolved_work": [],
        "delegation": {"visibility": "unsupported", "pending": None},
        "deletion_evidence": [], "evidence_only": False,
    }
    result_path.write_text(json.dumps(delivery))

    _seal_packet_result(
        {"job_id": "packet-job", "checkout": {"head": start_head}}, tmp_path, result_path
    )

    assert json.loads(result_path.read_text()) == {
        "schema_version": 1,
        "job_id": "packet-job",
        "start_head": start_head,
        "final_head": final_head,
        "delivery": delivery,
    }


def test_seal_output_composes_through_exact_head_into_delivery_validation(tmp_path: Path) -> None:
    """Composed: real runner seal output flows through exact-head evidence into delivery acceptance and tamper rejection."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    native = tmp_path / "native-runner"
    native_runner(native)
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs, native_runner=native)
    workspace = service.workspaces.create(
        project_id="fixture", name="seal-compose", branch="feature/seal-compose", base="HEAD"
    )
    checkout_id = workspace["checkout_id"]
    path = Path(workspace["path"])

    # Seed a file that will be deleted during the packet range.
    (path / "seed.txt").write_text("to be removed\n")
    subprocess.run(["git", "-C", str(path), "add", "seed.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
         "commit", "--quiet", "-m", "seed deletion target"],
        check=True,
    )

    binding = {
        "bead_ref": "sinnix://projects/fixture/beads/seal-test-1",
        "project_ref": "sinnix://projects/fixture",
        "checkout_ref": f"sinnix://projects/fixture/checkouts/{checkout_id}",
        "task_revision": "a" * 64,
        "task_etag": "b" * 64,
        "claim_ref": f"sinnix://projects/fixture/beads/seal-test-1/claims/{'c' * 64}",
        "claim_receipt": {
            "ref": f"sinnix://projects/fixture/beads/seal-test-1/claims/{'c' * 64}",
            "owner_route": "beads.cli",
        },
        "request_id": "9f1a2b3c-0000-4d5e-8f6a-7b8c9d0e1f2a",
        "assignment_ref": None,
        "write_scope": ["added.txt", "seed.txt"],
    }

    packet_response = service.dispatch(request(
        "job.agent.start", "systemd-jobs",
        {
            "project_id": "fixture", "checkout_id": checkout_id,
            "prompt": "return structured delivery for seal composition test",
            "backend": "codex", "model": "fixture", "effort": "high",
            "credential_profile": "subscription", "timeout_seconds": 60,
            "result": "last-message", "bead_binding": binding,
        },
        "agent-control",
    ))
    assert packet_response.ok and packet_response.payload is not None
    packet_id = packet_response.payload.inline["job_id"]
    packet_record = jobs.store.load(packet_id)
    start_head = packet_record.spec.checkout["head"]

    # Produce the packet range: one add, one delete.
    (path / "added.txt").write_text("new content\n")
    (path / "seed.txt").unlink()
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
         "commit", "--quiet", "-m", "packet range: add+delete"],
        check=True,
    )

    # Use the real runner seal on a valid worker delivery report.
    assert packet_record.result_path is not None
    packet_record.result_path.parent.mkdir(parents=True, exist_ok=True)
    packet_record.result_path.touch(mode=0o600)
    worker_delivery = {
        "anti_vacuity": True,
        "unresolved_work": [],
        "delegation": {"visibility": "unsupported", "pending": None},
        "deletion_evidence": ["seed.txt"],
        "evidence_only": False,
    }
    packet_record.result_path.write_text(json.dumps(worker_delivery))
    _seal_packet_result(
        {"job_id": packet_id, "checkout": {"head": start_head}}, path, packet_record.result_path
    )
    sealed = json.loads(packet_record.result_path.read_text())
    final_head = sealed["final_head"]

    # Worker result was sealed by the real runner; mark the job succeeded.
    jobs_module._write_private_marker(jobs_module._completion_marker_path(packet_record.log_path))
    systemd.properties = {
        "LoadState": "loaded", "ActiveState": "inactive", "Result": "success",
        "ExecMainStatus": "0", "InvocationID": "seal-compose-invocation",
    }
    assert jobs.get(packet_id)["state"]["phase"] == "succeeded"

    # Verifier job runs at final_head with the same binding.
    verifier_response = service.dispatch(request(
        "job.start", "systemd-jobs",
        {
            "project_id": "fixture", "operation": "check",
            "workspace_id": workspace["workspace_id"], "bead_binding": binding,
        },
    ))
    assert verifier_response.ok and verifier_response.payload is not None
    verifier_id = verifier_response.payload.inline["job_id"]
    assert jobs.get(verifier_id)["state"]["phase"] == "succeeded"

    delivery_gate = GitHubDelivery(service.projects, service.workspaces, jobs)

    # Accepting path: real seal output + correct deletion evidence + verifier at final_head.
    _workspace, _project, receipt = delivery_gate._verified_workspace(
        workspace["workspace_id"], verifier_id, packet_id
    )
    assert receipt["head"] == final_head
    assert receipt["bead_ref"] == binding["bead_ref"]

    # Tamper: mutate the sealed envelope's final_head to a synthetic value.
    tampered = {**sealed, "final_head": "b" * 40}
    packet_record.result_path.write_text(json.dumps(tampered))
    with pytest.raises(DeliveryError):
        delivery_gate._verified_workspace(workspace["workspace_id"], verifier_id, packet_id)

    # Restore and verify deletion overclaim is now rejected.
    packet_record.result_path.write_text(json.dumps(sealed))
    overclaim = {**worker_delivery, "deletion_evidence": ["seed.txt", "unrelated.txt"]}
    packet_record.result_path.write_text(json.dumps({**sealed, "delivery": overclaim}))
    with pytest.raises(DeliveryError, match="deletion evidence"):
        delivery_gate._verified_workspace(workspace["workspace_id"], verifier_id, packet_id)


def test_admission_revalidates_queued_declared_workspace_before_systemd_launch(tmp_path: Path) -> None:
    """A queued declared service whose checkout HEAD moved must terminalize before it reaches systemd."""
    write_adapter(tmp_path)
    descriptor = tmp_path / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'cache = "none"\n\n[operations.service.service]',
            'cache = "none"\nestimate_memory_bytes = 4294967296\n\n[operations.service.service]',
        )
    )
    initialize_git_checkout(tmp_path)
    systemd = FakeSystemdJobs(properties={"LoadState": "not-found", "ActiveState": "inactive"})
    jobs = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        wait_poll_seconds=0.001,
        pressure_probe=lambda: {"memory_full_avg10": 0.2},
    )
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    workspace = service.workspaces.create(
        project_id="fixture", name="queued-drift", branch="feature/queued-drift", base="HEAD"
    )
    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "service", "workspace_id": workspace["workspace_id"]},
        )
    )
    assert started.ok and started.payload is not None
    assert started.payload.inline["state"]["phase"] == "queued"
    path = Path(workspace["path"])
    (path / "drift.txt").write_text("changed HEAD before admission\n")
    subprocess.run(["git", "-C", str(path), "add", "drift.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "drift"],
        check=True,
    )
    jobs.pressure_probe = lambda: {"memory_full_avg10": 0.0}
    jobs._admit_locked()

    record = jobs.store.load(started.payload.inline["job_id"])
    assert record.state["phase"] == "launch-failed"
    assert record.state["terminal"]
    assert systemd.started == []
    assert not (jobs.store.leases_root / f"{record.job_id}.json").exists()


def test_declared_runner_revalidates_bound_checkout_at_payload_exec_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A checkout mutation after systemd admission cannot reach the project payload."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    systemd = FakeSystemdJobs(properties={"LoadState": "loaded", "ActiveState": "active"})
    jobs = generic_jobs(tmp_path, systemd)
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
    _, launch_environment = jobs.store.declared_launch(record.job_id)
    assert systemd.started[0]["command"][1] == "--declared"
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--allow-empty", "-m", "moved"],
        check=True,
        capture_output=True,
        text=True,
    )
    for key in (
        "SINNIXD_JOB_ID",
        "SINNIXD_PROJECT_ID",
        "SINNIXD_OPERATION",
        "SINNIXD_CHECKOUT_ID",
        "SINNIXD_CHECKOUT_HEAD",
    ):
        monkeypatch.setenv(key, launch_environment[key])
    with pytest.raises(RunnerError, match="registered Git worktree"):
        _run_declared(jobs.store.root, record.job_id, record.unit)


def test_exact_head_verified_workspace_publishes_lands_and_finishes_without_a_pr_ledger(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    workspace = service.workspaces.create(
        project_id="fixture", name="delivery-lane", branch="feature/delivery", base="HEAD"
    )
    path = Path(workspace["path"])
    (path / "delivery.txt").write_text("deliver\n")
    subprocess.run(["git", "-C", str(path), "add", "delivery.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "delivery"],
        check=True,
    )
    workspace = service.workspaces.get(workspace["workspace_id"])
    started = service.dispatch(
        request(
            "job.start", "systemd-jobs",
            {"project_id": "fixture", "operation": "check", "workspace_id": workspace["workspace_id"]},
        )
    )
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    systemd.properties = {"LoadState": "loaded", "ActiveState": "inactive", "Result": "success", "ExecMainStatus": "0"}
    calls: list[list[str]] = []
    merged = False
    created = False
    review_reads = 0

    def fake_run(argv, **_kwargs):
        nonlocal created, merged, review_reads
        command = list(argv)
        calls.append(command)
        if command[:3] == ["gh", "pr", "merge"]:
            merged = True
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:3] == ["gh", "pr", "create"]:
            created = True
            return subprocess.CompletedProcess(command, 0, "https://github.test/example/pull/17\n", "")
        if command[:3] == ["gh", "pr", "view"]:
            if command[-1] == "url":
                return subprocess.CompletedProcess(
                    command, 0 if created else 1, json.dumps({"url": "https://github.test/example/pull/17"}), "missing"
                )
            review_reads += 1
            payload = {
                "number": 17,
                "url": "https://github.test/example/pull/17",
                "state": "MERGED" if merged else "OPEN",
                "isDraft": False,
                "mergeStateStatus": "CLEAN",
                "headRefOid": "0" * 40 if review_reads == 1 else workspace["head"],
                "baseRefName": "master",
                "statusCheckRollup": [],
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        return subprocess.CompletedProcess(command, 0, "https://github.test/example/pull/17\n", "")

    delivery = GitHubDelivery(service.projects, service.workspaces, jobs, run=fake_run)
    (path / "late.txt").write_text("late change\n")
    subprocess.run(["git", "-C", str(path), "add", "late.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "late"],
        check=True,
    )
    workspace = service.workspaces.get(workspace["workspace_id"])
    with pytest.raises(DeliveryError, match="exact HEAD"):
        delivery.publish(workspace["workspace_id"], job_id, "Stale", "must not publish")
    assert calls == []
    replacement = service.dispatch(
        request(
            "job.start", "systemd-jobs",
            {"project_id": "fixture", "operation": "check", "workspace_id": workspace["workspace_id"]},
        )
    )
    assert replacement.ok and replacement.payload is not None
    job_id = replacement.payload.inline["job_id"]
    published = delivery.publish(workspace["workspace_id"], job_id, "Deliver fixture", "Verified body")
    reconciled = delivery.publish(workspace["workspace_id"], job_id, "Deliver fixture", "Verified body")
    landed = delivery.land(workspace["workspace_id"], job_id)
    finished = delivery.finish(workspace["workspace_id"])

    assert published["published"] and published["created"]
    assert reconciled["published"] and not reconciled["created"]
    assert landed["landed"] and finished["finished"]
    assert any(command[-7:-4] == ["git", "-C", str(path)] and "push" in command for command in calls)
    assert any(command[:3] == ["gh", "pr", "create"] for command in calls)
    assert any(command[:3] == ["gh", "pr", "merge"] for command in calls)
    assert not path.exists()
    assert sum(command[:3] == ["gh", "pr", "create"] for command in calls) == 1
    assert service.workspaces.list("fixture") == {"workspaces": []}


def test_typed_shell_and_agent_contracts_share_generic_job_lifecycle(tmp_path: Path) -> None:
    """Anti-vacuity: typed contracts must reach GenericJobs, not a second controller."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    systemd = FakeSystemdJobs(
        properties={"LoadState": "loaded", "ActiveState": "inactive", "Result": "success", "ExecMainStatus": "0"}
    )
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd), native_runner=runner)

    shell = service.dispatch(
        request(
            "job.shell.start",
            "systemd-jobs",
            {"project_id": "fixture", "checkout_id": "default", "argv": ["printf", "shell-secret"], "cwd": ".", "timeout_seconds": 60, "result": "exit-status"},
            "operator",
        )
    )
    agent = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {"project_id": "fixture", "checkout_id": "default", "prompt": "private prompt", "backend": "codex", "model": "fixture", "effort": "high", "credential_profile": "subscription", "timeout_seconds": 60, "result": "last-message", "bead_binding": {"bead_ref": "sinnix://projects/fixture/beads/fixture-1", "project_ref": "sinnix://projects/fixture", "checkout_ref": "sinnix://projects/fixture/checkouts/default", "task_revision": "a" * 64, "task_etag": "b" * 64, "claim_ref": f"sinnix://projects/fixture/beads/fixture-1/claims/{'b' * 64}", "claim_receipt": {"ref": f"sinnix://projects/fixture/beads/fixture-1/claims/{'b' * 64}", "owner_route": "beads.cli"}, "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b", "assignment_ref": None}},
            "agent-control",
        )
    )
    operator_agent = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {"project_id": "fixture", "checkout_id": "default", "prompt": "operator prompt", "backend": "codex", "model": "fixture", "effort": "high", "credential_profile": "subscription", "timeout_seconds": 60, "result": "last-message"},
            "operator",
        )
    )

    assert shell.ok and agent.ok and operator_agent.ok
    assert shell.payload is not None and agent.payload is not None and operator_agent.payload is not None
    shell_job = shell.payload.inline
    agent_job = agent.payload.inline
    assert shell_job["kind"] == "operator-shell"
    assert shell_job["principal"] == "operator"
    assert shell_job["contract"]["argv"]["executable"] == "printf"
    shell_input = json.loads((tmp_path / "state" / "inputs" / f"{shell_job['job_id']}.json").read_text())
    assert shell_input["environment_command"] == ["fixture-env", "--command"]
    assert agent_job["kind"] == "attested-agent"
    assert agent_job["principal"] == "agent-control"
    assert agent_job["contract"]["backend"] == "codex"
    assert agent_job["contract"]["bead_binding"]["bead_ref"] == "sinnix://projects/fixture/beads/fixture-1"
    assert agent_job["contract"]["bead_binding"]["request_id"] == "2e46daf5-e9b1-4c6e-b99d-bcd46631730b"
    assert agent_job["artifacts"]["result"]["max_bytes"] == 64_000
    persisted = (tmp_path / "state" / "jobs" / f"{agent_job['job_id']}.json").read_text()
    assert "private prompt" not in persisted
    assert "shell-secret" not in persisted
    assert "display only" not in persisted
    assert operator_agent.payload.inline["principal"] == "operator"
    assert len(systemd.started) == 3
    assert all(start["unit"].startswith("sinnixd-job-") for start in systemd.started)
    restarted = GenericJobs(systemd, service.jobs.store, wait_poll_seconds=0.001)
    assert {job["job_id"] for job in restarted.list()["jobs"]} == {
        shell_job["job_id"],
        agent_job["job_id"],
        operator_agent.payload.inline["job_id"],
    }


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
    assert observed["argv"] == ["nix", "develop", "--command", "python", "-m", "fixture"]


def test_typed_contracts_refuse_spoofed_principals_checkout_backend_environment_and_results(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path), native_runner=runner)
    shell_arguments = {
        "project_id": "fixture", "checkout_id": "default", "argv": ["true"], "cwd": ".", "timeout_seconds": 60, "result": "exit-status"
    }
    agent_arguments = {
        "project_id": "fixture", "checkout_id": "default", "prompt": "prompt", "backend": "codex", "model": "fixture", "effort": "high", "credential_profile": "subscription", "timeout_seconds": 60, "result": "last-message"
    }
    invalid_principal = service.dispatch(request("job.shell.start", "systemd-jobs", shell_arguments, "observer"))
    invalid_checkout = service.dispatch(request("job.shell.start", "systemd-jobs", {**shell_arguments, "checkout_id": "absent"}, "operator"))
    invalid_backend = service.dispatch(request("job.agent.start", "systemd-jobs", {**agent_arguments, "backend": "unknown"}, "agent-control"))
    invalid_bead_binding = service.dispatch(request("job.agent.start", "systemd-jobs", {**agent_arguments, "bead_binding": {"bead_ref": "sinnix://projects/fixture/beads/fixture-1", "project_ref": "sinnix://projects/fixture", "checkout_ref": "sinnix://projects/fixture/checkouts/default", "task_revision": "a" * 64, "task_etag": "b" * 64, "claim_ref": "sinnix://projects/fixture/beads/other/claims/receipt", "claim_receipt": {"ref": "sinnix://projects/fixture/beads/other/claims/receipt"}, "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b", "assignment_ref": None}}, "agent-control"))
    legacy_work_item_binding = service.dispatch(request("job.agent.start", "systemd-jobs", {**agent_arguments, "bead_binding": {"bead_ref": "sinnix://projects/fixture/beads/fixture-1", "project_ref": "sinnix://projects/fixture", "checkout_ref": "sinnix://projects/fixture/checkouts/default", "task_revision": "a" * 64, "task_etag": "b" * 64, "claim_ref": None, "claim_receipt": None, "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b", "assignment_ref": None, "work_item": "private task prose"}}, "agent-control"))
    invalid_environment = service.dispatch(request("job.shell.start", "systemd-jobs", {**shell_arguments, "environment": {"SINNIXD_JOB_ID": "spoof"}}, "operator"))
    invalid_result = service.dispatch(request("job.agent.start", "systemd-jobs", {**agent_arguments, "result": "exit-status"}, "agent-control"))

    for response in (invalid_principal, invalid_checkout, invalid_backend, invalid_bead_binding, legacy_work_item_binding, invalid_environment, invalid_result):
        assert response.error is not None
        assert response.error.code.value == "INVALID_ARGUMENT"


def test_failed_agent_launch_removes_private_prompt_and_contract_input(tmp_path: Path) -> None:
    """Anti-vacuity: a rejected launch cannot leave prompt material in durable state."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    class ConfirmedAbsent(FakeSystemdJobs):
        def start(self, **kwargs) -> None:
            raise SystemdJobError("fixture launch rejected")

    systemd = ConfirmedAbsent(properties={"LoadState": "not-found", "ActiveState": "inactive"})
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd), native_runner=runner)

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
    assert response.payload.inline["state"]["phase"] == "launch-failed"
    assert not list((tmp_path / "state" / "inputs").iterdir())


def test_runner_rejects_changed_or_unregistered_checkout_identities(tmp_path: Path) -> None:
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


def test_agent_runner_revalidates_checkout_and_writes_a_bounded_result_fixture(tmp_path: Path) -> None:
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
        "schema_version": 1,
        "job_id": "11111111-1111-1111-1111-111111111111",
        "kind": "attested-agent",
        "principal": "agent-control",
        "checkout": checkout.to_dict(),
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
        [sys.executable, "-m", "sinnixd.runner", "--input", str(input_path), "--job-id", payload["job_id"], "--unit", f"sinnixd-job-{payload['job_id']}.service", "--native-runner", str(runner), "--state-root", str(state)],
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
                "schema_version": 1,
                "job_id": job_id,
                "kind": "attested-agent",
                "principal": "agent-control",
                "checkout": checkout.to_dict(),
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
        [sys.executable, "-m", "sinnixd.runner", "--input", str(input_path), "--job-id", job_id, "--unit", f"sinnixd-job-{job_id}.service", "--native-runner", str(runner), "--state-root", str(state)],
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
    ("properties", "expected"),
    [
        ({"LoadState": "loaded", "ActiveState": "inactive", "Result": "success", "ExecMainStatus": "0"}, "succeeded"),
        ({"LoadState": "loaded", "ActiveState": "inactive", "Result": "timeout", "ExecMainStatus": "9"}, "timed_out"),
        ({"LoadState": "loaded", "ActiveState": "failed", "Result": "exit-code", "ExecMainStatus": "1"}, "failed"),
    ],
)
def test_terminal_result_classification_comes_from_systemd(
    tmp_path: Path, properties: dict[str, str], expected: str
) -> None:
    """Anti-vacuity: deleting GenericJobs._classify breaks the terminal phase assertion."""
    systemd = FakeSystemdJobs(properties=properties)
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={"PATH": ""},
    )

    status = jobs.get(started["job_id"])

    assert status["state"]["phase"] == expected
    assert status["state"]["terminal"]


def test_logs_are_bounded_and_restart_reconciles_the_same_record(tmp_path: Path) -> None:
    """Anti-vacuity: deleting the persisted record or GenericJobs.logs breaks restart reads."""
    systemd = FakeSystemdJobs(
        properties={"LoadState": "loaded", "ActiveState": "inactive", "Result": "success", "ExecMainStatus": "0"}
    )
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={"PATH": ""},
    )
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


def test_capture_caps_persistent_artifacts_and_reports_producer_overflow(tmp_path: Path) -> None:
    """Anti-vacuity: delayed marker writes fail while the producer is still running."""
    log_path = tmp_path / "overflow.log"
    overflow_path = tmp_path / "overflow.overflow"
    log_path.touch(mode=0o600)
    result: dict[str, int] = {}
    producer = ("/bin/sh", "-c", "printf 012345; sleep 1")

    thread = threading.Thread(
        target=lambda: result.setdefault(
            "exit_code",
            capture_main(("--log-path", str(log_path), "--overflow-path", str(overflow_path), "--max-bytes", "4", "--", *producer)),
        ),
        daemon=True,
    )
    thread.start()
    deadline = time.monotonic() + 0.5
    while not overflow_path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)

    assert overflow_path.exists()
    assert thread.is_alive()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert result["exit_code"] == 0
    assert log_path.stat().st_size == 4

    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    record = jobs.store.load(started["job_id"])
    record.log_path.write_bytes(b"0123")
    record.log_path.with_suffix(".overflow").touch()
    log = jobs.logs(started["job_id"], offset=2, max_bytes=2)
    assert log["content"] == "23"
    assert log["next_offset"] == 4
    assert not log["truncated"]
    assert log["artifact_truncated"]


def test_logs_report_marker_created_during_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anti-vacuity: sampling overflow before reading misses this interleaving."""
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    record = jobs.store.load(started["job_id"])
    record.log_path.write_bytes(b"0123")
    overflow_path = record.log_path.with_suffix(".overflow")
    original_read = jobs_module._read_private_artifact

    def marker_after_read(path: Path, max_bytes: int, *, offset: int = 0) -> bytes | None:
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


def test_job_store_fsyncs_parent_after_replacing_record(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Anti-vacuity: a file fsync before rename cannot make the renamed entry crash-durable."""
    store = GenericJobStore(tmp_path / "state")
    record = store.create(
        GenericJobSpec(kind="foreground-command", command=("fixture",), working_directory=str(tmp_path), environment={}),
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
        events.append(("fsync-directory" if descriptor == directory_fd else "fsync-file", descriptor))

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

    replace_index = events.index(("replace", store.records_root / f"{record.job_id}.json"))
    file_fsync_index = max(index for index, event in enumerate(events[:replace_index]) if event[0] == "fsync-file")
    directory_fsync_index = next(
        index
        for index, event in enumerate(events[replace_index + 1 :], start=replace_index + 1)
        if event == ("fsync-directory", directory_fd) and events[index - 1] == ("open-directory", store.records_root)
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
        GenericJobSpec(kind="foreground-command", command=("fixture",), working_directory=str(tmp_path), environment={}),
        "00000000-0000-0000-0000-000000000002",
    )

    assert synchronized == [tmp_path, store.root, store.root, store.logs_root, store.root, store.root, store.records_root]


@pytest.mark.parametrize(
    ("mode", "properties", "expected"),
    [
        ("missing", {"LoadState": "not-found", "ActiveState": "inactive"}, "missing"),
    ],
)
def test_confirmed_absence_and_launch_failure_are_distinct_terminal_outcomes(
    tmp_path: Path, mode: str, properties: dict[str, str] | None, expected: str
) -> None:
    """Anti-vacuity: post-launch loss, missing units, and launch failures have distinct terminal records."""
    systemd = FakeSystemdJobs(properties=properties or {})
    jobs = generic_jobs(tmp_path, systemd)
    status = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    status = jobs.get(status["job_id"])
    cancelled = jobs.cancel(status["job_id"])
    waited = jobs.wait(status["job_id"], timeout_seconds=1)
    assert status["state"]["phase"] == expected
    assert status["state"]["terminal"]
    assert cancelled["already_terminal"]
    assert not systemd.stopped
    assert waited["state"]["phase"] == expected


def test_start_returns_systemd_state_when_accepted_reply_is_lost(tmp_path: Path) -> None:
    """Anti-vacuity: an accepted transient unit must not become launch-failed when its reply is lost."""
    secret = "accepted-but-reply-lost"

    class ReplyLostAfterAccept(FakeSystemdJobs):
        def start(self, **kwargs) -> None:
            self.started.append(dict(kwargs))
            raise SystemdJobError(secret)

    jobs = generic_jobs(tmp_path, ReplyLostAfterAccept())

    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    persisted = (tmp_path / "state" / "jobs" / f"{started['job_id']}.json").read_text()

    assert started["state"]["phase"] == "running"
    assert started["state"]["systemd"]["LoadState"] == "loaded"
    assert secret not in persisted


def test_start_persists_launch_failed_only_when_systemd_confirms_absence(tmp_path: Path) -> None:
    """Anti-vacuity: a launch error alone is insufficient evidence that systemd rejected the unit."""
    secret = "confirmed-absent-launch-error"

    class ConfirmedAbsent(FakeSystemdJobs):
        def start(self, **kwargs) -> None:
            raise SystemdJobError(secret)

    jobs = generic_jobs(tmp_path, ConfirmedAbsent(properties={"LoadState": "not-found", "ActiveState": "inactive"}))

    result = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    record = jobs.store.load(result["job_id"])
    persisted = (tmp_path / "state" / "jobs" / f"{record.job_id}.json").read_text()
    assert result["unit"] == record.unit
    assert result["state"]["phase"] == "launch-failed"
    assert record.state["phase"] == "launch-failed"
    assert record.state["error"] == {"code": "systemd-job-error"}
    assert secret not in persisted


@pytest.mark.parametrize("mode", ("observation-unknown", "launch-failed"))
def test_systemd_errors_persist_only_stable_codes(tmp_path: Path, mode: str) -> None:
    """Anti-vacuity: persisting a SystemdJobError message writes this fixture secret to disk."""
    secret = "systemd-error-secret-do-not-persist"

    class FailingShow(FakeSystemdJobs):
        def show(
            self,
            unit: str,
            *,
            timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        ) -> dict[str, str]:
            raise SystemdJobError(secret)

    class FailingStart(FakeSystemdJobs):
        def start(self, **kwargs) -> None:
            raise SystemdJobError(secret)

    jobs = generic_jobs(
        tmp_path,
        FailingShow()
        if mode == "observation-unknown"
        else FailingStart(properties={"LoadState": "not-found", "ActiveState": "inactive"}),
    )
    if mode == "launch-failed":
        status = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    else:
        started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
        status = jobs.get(started["job_id"])

    persisted = (tmp_path / "state" / "jobs" / f"{status['job_id']}.json").read_text()

    assert status["state"]["phase"] == mode
    assert status["state"]["error"] == {"code": "systemd-job-error"}
    assert status["state"]["terminal"] is (mode == "launch-failed")
    assert secret not in persisted
    assert '"message"' not in persisted


def test_launch_unknown_reconciles_to_observed_success_through_get_and_wait(tmp_path: Path) -> None:
    """Anti-vacuity: launch uncertainty must retain its identity until systemd later answers."""
    class ReplyAndFirstShowLost(FakeSystemdJobs):
        show_is_unavailable = True

        def start(self, **kwargs) -> None:
            self.started.append(dict(kwargs))
            raise SystemdJobError("reply unavailable")

        def show(
            self,
            unit: str,
            *,
            timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        ) -> dict[str, str]:
            if self.show_is_unavailable:
                raise SystemdJobError("manager unavailable")
            return super().show(unit, timeout_seconds=timeout_seconds)

    systemd = ReplyAndFirstShowLost()
    jobs = generic_jobs(tmp_path, systemd)
    uncertain = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    persisted = jobs.store.load(uncertain["job_id"])

    assert uncertain["unit"] == persisted.unit
    assert uncertain["state"]["phase"] == "launch-unknown"
    assert uncertain["state"]["error"] == {"code": "systemd-job-error"}
    assert not uncertain["state"]["terminal"]

    systemd.show_is_unavailable = False
    systemd.properties = {"LoadState": "loaded", "ActiveState": "active", "Result": "success"}
    running = jobs.get(uncertain["job_id"])
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    succeeded = jobs.wait(uncertain["job_id"], timeout_seconds=1)

    assert running["job_id"] == uncertain["job_id"]
    assert running["unit"] == uncertain["unit"]
    assert running["state"]["phase"] == "running"
    assert succeeded["job_id"] == uncertain["job_id"]
    assert succeeded["state"]["phase"] == "succeeded"


def test_launch_unknown_reconciles_to_launch_failed_when_systemd_confirms_absence(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: unavailable reconciliation must not relabel confirmed absence as ordinary missing."""
    class ReplyAndFirstShowLost(FakeSystemdJobs):
        show_is_unavailable = True

        def start(self, **kwargs) -> None:
            raise SystemdJobError("reply unavailable")

        def show(
            self,
            unit: str,
            *,
            timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        ) -> dict[str, str]:
            if self.show_is_unavailable:
                raise SystemdJobError("manager unavailable")
            return super().show(unit, timeout_seconds=timeout_seconds)

    systemd = ReplyAndFirstShowLost()
    jobs = generic_jobs(tmp_path, systemd)
    uncertain = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    systemd.show_is_unavailable = False
    systemd.properties = {"LoadState": "not-found", "ActiveState": "inactive"}

    failed = jobs.get(uncertain["job_id"])

    assert failed["job_id"] == uncertain["job_id"]
    assert failed["unit"] == uncertain["unit"]
    assert failed["state"]["phase"] == "launch-failed"
    assert failed["state"]["terminal"]


def test_launch_unknown_cancel_reconciles_the_same_job_id(tmp_path: Path) -> None:
    """Anti-vacuity: cancellation must operate on the durable uncertain launch record."""
    class ReplyAndFirstShowLost(FakeSystemdJobs):
        show_is_unavailable = True

        def start(self, **kwargs) -> None:
            raise SystemdJobError("reply unavailable")

        def show(
            self,
            unit: str,
            *,
            timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        ) -> dict[str, str]:
            if self.show_is_unavailable:
                raise SystemdJobError("manager unavailable")
            return super().show(unit, timeout_seconds=timeout_seconds)

    systemd = ReplyAndFirstShowLost(
        properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"}
    )
    jobs = generic_jobs(tmp_path, systemd)
    uncertain = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    systemd.show_is_unavailable = False

    cancelled = jobs.cancel(uncertain["job_id"])

    assert systemd.stopped == [uncertain["unit"]]
    assert cancelled["job_id"] == uncertain["job_id"]
    assert cancelled["unit"] == uncertain["unit"]
    assert cancelled["state"]["phase"] == "cancelled"


def test_job_wait_caps_manager_calls_at_its_remaining_deadline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Anti-vacuity: a blocked manager call must consume at most the wait's remaining budget."""
    clock = [0.0]

    class UnavailableSystemd(FakeSystemdJobs):
        timeouts: list[float] = []

        def start(self, **kwargs) -> None:
            raise SystemdJobError("reply unavailable")

        def show(
            self,
            unit: str,
            *,
            timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        ) -> dict[str, str]:
            self.timeouts.append(timeout_seconds)
            clock[0] += timeout_seconds
            raise SystemdJobError("manager unavailable")

    monkeypatch.setattr("sinnixd.jobs.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("sinnixd.jobs.time.sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    systemd = UnavailableSystemd()
    jobs = GenericJobs(systemd, GenericJobStore(tmp_path / "state"), wait_poll_seconds=0.1)
    uncertain = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    systemd.timeouts.clear()
    clock[0] = 0.0

    timed_out = jobs.wait(uncertain["job_id"], timeout_seconds=1)

    assert timed_out["job_id"] == uncertain["job_id"]
    assert timed_out["state"]["phase"] == "observation-unknown"
    assert timed_out["wait_timed_out"]
    assert systemd.timeouts
    assert all(0 < timeout <= SYSTEMD_COMMAND_TIMEOUT_SECONDS for timeout in systemd.timeouts)
    assert clock[0] == 1.0


@pytest.mark.parametrize(
    ("terminal", "expected"),
    [
        ({"Result": "success", "ExecMainStatus": "0"}, "succeeded"),
        ({"Result": "exit-code", "ExecMainStatus": "1"}, "failed"),
        ({"Result": "timeout", "ExecMainStatus": "9"}, "timed_out"),
        ({"Result": "signal", "ExecMainStatus": "15", "InvocationID": "different-invocation"}, "failed"),
    ],
)
def test_cancel_persists_intent_and_preserves_systemd_exit_races(
    tmp_path: Path, terminal: dict[str, str], expected: str
) -> None:
    """Anti-vacuity: intent-only cancellation would relabel these terminal systemd results."""
    class TerminalDuringStop(FakeSystemdJobs):
        def stop(self, unit: str) -> None:
            self.stopped.append(unit)
            self.properties = {
                "LoadState": "loaded",
                "ActiveState": "inactive",
                "InvocationID": "fixture-invocation",
                **terminal,
            }

    class StopFails(FakeSystemdJobs):
        def stop(self, unit: str) -> None:
            self.stopped.append(unit)
            raise SystemdJobError("stop interrupted")

    terminal_jobs = generic_jobs(
        tmp_path / expected,
        TerminalDuringStop(properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"}),
    )
    started = terminal_jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    cancelled = terminal_jobs.cancel(started["job_id"])
    assert cancelled["state"]["phase"] == expected
    assert terminal_jobs.store.load(started["job_id"]).cancel_stop_acknowledged_at is not None

    crashing = generic_jobs(tmp_path / "crash", StopFails(properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"}))
    started = crashing.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    with pytest.raises(SystemdJobError):
        crashing.cancel(started["job_id"])
    record = crashing.store.load(started["job_id"])
    assert record.cancel_requested_at is not None
    assert record.cancel_requested_invocation_id == "fixture-invocation"


def test_cancelled_missing_unit_distinguishes_acknowledged_and_ambiguous_stop(tmp_path: Path) -> None:
    """Anti-vacuity: cancellation intent alone must leave an absent unit retryable."""
    class CollectedDuringStop(FakeSystemdJobs):
        def stop(self, unit: str) -> None:
            self.stopped.append(unit)
            self.properties = {"LoadState": "not-found", "ActiveState": "inactive"}

    systemd = CollectedDuringStop(
        properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"}
    )
    jobs = generic_jobs(tmp_path / "acknowledged", systemd)
    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    cancelled = jobs.cancel(started["job_id"])
    assert cancelled["state"]["phase"] == "cancelled"
    assert cancelled["state"]["cancellation"]["invocation_id"] == "fixture-invocation"

    missing_systemd = FakeSystemdJobs(
        properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"}
    )
    missing_jobs = generic_jobs(tmp_path / "intent-only", missing_systemd)
    started = missing_jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    record = missing_jobs.store.load(started["job_id"])
    missing_jobs.store.save(missing_jobs._with_cancel_intent(record, "fixture-invocation"))
    missing_systemd.properties = {"LoadState": "not-found", "ActiveState": "inactive"}
    intent_only = missing_jobs.get(started["job_id"])
    assert intent_only["state"]["phase"] == "outcome-unknown"
    assert not intent_only["state"]["terminal"]

    class CrashAfterStopStore(GenericJobStore):
        crash_on_acknowledgement: bool = False

        def save(self, record) -> None:
            if self.crash_on_acknowledgement and record.cancel_stop_acknowledged_at is not None:
                raise OSError("simulated daemon crash after systemd stop")
            super().save(record)

    crashing_systemd = CollectedDuringStop(
        properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"}
    )
    crashing_store = CrashAfterStopStore(tmp_path / "ack-crash" / "state")
    crashing_jobs = GenericJobs(crashing_systemd, crashing_store, wait_poll_seconds=0.001)
    started = crashing_jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    crashing_store.crash_on_acknowledgement = True
    with pytest.raises(OSError, match="simulated daemon crash"):
        crashing_jobs.cancel(started["job_id"])
    persisted = crashing_store.load(started["job_id"])
    assert persisted.cancel_requested_at is not None
    assert persisted.cancel_stop_acknowledged_at is None
    crash_reconciled = crashing_jobs.get(started["job_id"])
    assert crash_reconciled["state"]["phase"] == "outcome-unknown"
    assert not crash_reconciled["state"]["terminal"]


def test_agentctl_wait_returns_a_timed_out_envelope_past_control_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Anti-vacuity: the CLI must decode a normal timed-out wait response after control framing has expired."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs(properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"})
    jobs = generic_jobs(tmp_path, systemd)
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
    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    monkeypatch.setattr(
        sys,
        "argv",
        ["agentctl", "--socket", str(socket_path), "job", "wait", started["job_id"], "--timeout-seconds", "1"],
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


def test_delivery_operations_have_truthful_bounded_response_timeouts() -> None:
    """Remote effects must not outlive the client's success/failure response."""
    expected = {
        "workspace.publish": 790.0,
        "workspace.review-status": 65.0,
        "workspace.land": 185.0,
        "workspace.finish": 185.0,
    }
    assert CONTROL_OPERATION_RESPONSE_TIMEOUT_SECONDS == expected
    for operation, timeout in expected.items():
        assert _response_timeout_seconds(request(operation, "git-workspaces")) == timeout
    assert _response_timeout_seconds(request("workspace.get", "git-workspaces")) == CONNECTION_TIMEOUT_SECONDS
    assert _response_timeout_seconds(request("unknown.slow-effect", "git-workspaces")) == CONNECTION_TIMEOUT_SECONDS


def test_slow_delivery_response_outlives_the_ordinary_control_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A remote effect that is still running must not be reported as daemon loss."""
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, FakeSystemdJobs()))
    assert service.delivery is not None

    def slow_publish(_workspace_id: str, _job_id: str, _title: str, _body: str) -> dict[str, object]:
        time.sleep(0.1)
        return {"published": True, "publication_output": "https://github.test/pull/17"}

    monkeypatch.setattr(service.delivery, "publish", slow_publish)
    monkeypatch.setattr(api_module, "CONNECTION_TIMEOUT_SECONDS", 0.05)
    socket_path = tmp_path / "sinnixd.sock"
    stop_event = threading.Event()
    server = UnixSocketServer(socket_path, service, connection_timeout_seconds=0.05)
    thread = start_server(server, stop_event=stop_event)
    publication = request(
        "workspace.publish",
        "git-workspaces",
        {"workspace_id": "fixture", "job_id": "verified", "title": "Fixture", "body": "body"},
        "agent-control",
    )
    try:
        response = call(socket_path, publication)
    finally:
        stop_event.set()
        thread.join(timeout=2)

    assert not thread.is_alive()
    assert response["ok"] is True
    assert response["payload"]["value"] == {
        "published": True,
        "publication_output": "https://github.test/pull/17",
    }


def test_agentctl_wait_reports_capacity_exhaustion_while_all_wait_workers_are_occupied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Anti-vacuity: raw framing cannot cover the agentctl capacity-error path."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs(properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"})
    jobs = generic_jobs(tmp_path, systemd)
    wait_started = threading.Event()
    wait_lock = threading.Lock()
    active_waits = 0
    original_wait = jobs.wait
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    socket_path = tmp_path / "sinnixd.sock"
    stop_event = threading.Event()
    server = UnixSocketServer(socket_path, service, connection_timeout_seconds=0.05, max_workers=8)
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
    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    job_id = started["job_id"]
    wait_results: list[dict[str, object]] = []
    wait_errors: list[Exception] = []

    def run_wait() -> None:
        try:
            wait_results.append(call(socket_path, request("job.wait", "systemd-jobs", {"job_id": job_id, "timeout_seconds": 1})))
        except Exception as error:
            wait_errors.append(error)

    waiters = [threading.Thread(target=run_wait, daemon=True) for _ in range(server.wait_worker_count)]
    for waiter in waiters:
        waiter.start()
    assert wait_started.wait(timeout=1)
    monkeypatch.setattr(
        sys,
        "argv",
        ["agentctl", "--socket", str(socket_path), "job", "wait", job_id, "--timeout-seconds", "1"],
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
    assert wait_timeouts == [1 + WAIT_TRANSPORT_MARGIN_SECONDS] * server.wait_worker_count
    assert all(result["payload"]["value"]["state"]["phase"] == "running" for result in wait_results)
    assert all(result["payload"]["value"]["wait_timed_out"] for result in wait_results)


def test_job_rpc_get_list_wait_logs_and_cancel_share_one_record(tmp_path: Path) -> None:
    """Anti-vacuity: deleting any RPC route prevents its shared job ID from resolving."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs(
        properties={"LoadState": "loaded", "ActiveState": "inactive", "Result": "success", "ExecMainStatus": "0"}
    )
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd))
    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "check"}))
    assert started.payload is not None
    job_id = started.payload.inline["job_id"]

    get = service.dispatch(request("job.get", "systemd-jobs", {"job_id": job_id}))
    listed = service.dispatch(request("job.list", "systemd-jobs", {"limit": 1}))
    waited = service.dispatch(request("job.wait", "systemd-jobs", {"job_id": job_id, "timeout_seconds": 1}))
    logs = service.dispatch(request("job.logs", "systemd-jobs", {"job_id": job_id, "max_bytes": 10}))
    cancelled = service.dispatch(request("job.cancel", "systemd-jobs", {"job_id": job_id}))

    assert all(response.ok for response in (get, listed, waited, logs, cancelled))
    assert listed.payload is not None
    assert listed.payload.inline["jobs"][0]["job_id"] == job_id
    assert listed.payload.inline["limit"] == 1
    assert listed.payload.inline["total"] == 1
    assert not listed.payload.inline["truncated"]
    assert cancelled.payload is not None
    assert cancelled.payload.inline["already_terminal"]


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
        request("job.get", "systemd-jobs", {"job_id": agent_job}, principal="agent-control")
    ).ok
    agent_denied = service.dispatch(
        request("job.get", "systemd-jobs", {"job_id": operator_jobs[0]}, principal="agent-control")
    )
    assert agent_denied.error is not None
    assert agent_denied.error.code is ErrorCode.POLICY_DENIED

    seen: list[str] = []
    cursor: str | None = None
    while True:
        arguments: dict[str, object] = {"limit": 1}
        if cursor is not None:
            arguments["cursor"] = cursor
        page = service.dispatch(
            request("job.list", "systemd-jobs", arguments, principal="operator")
        )
        assert page.ok and page.payload is not None
        seen.extend(row["job_id"] for row in page.payload.inline["jobs"])
        cursor = page.payload.inline["next_cursor"]
        if cursor is not None and len(seen) == 1:
            rebound = service.dispatch(
                request(
                    "job.list",
                    "systemd-jobs",
                    {"limit": 1, "cursor": cursor},
                    principal="agent-control",
                )
            )
            assert rebound.error is not None
            assert rebound.error.code is ErrorCode.INVALID_ARGUMENT
            changed_filter = service.dispatch(
                request(
                    "job.list",
                    "systemd-jobs",
                    {"limit": 1, "cursor": cursor, "active_only": True},
                    principal="operator",
                )
            )
            assert changed_filter.error is not None
            assert changed_filter.error.code is ErrorCode.INVALID_ARGUMENT
        if cursor is None:
            break
    assert set(seen) == {agent_job, *operator_jobs}
    assert len(seen) == 3
    assert service.dispatch(
        request("job.get", "systemd-jobs", {"job_id": agent_job}, principal="operator")
    ).ok


def test_declared_cache_identities_remain_controllable_by_their_principal(
    tmp_path: Path,
) -> None:
    """A coalesced or reused declared ID must remain usable by its owning principal."""
    project_root = tmp_path / "project"
    write_adapter(project_root)
    descriptor = project_root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace('exclusive_keys = ["fixture:check"]\n', "")
    )
    initialize_git_checkout(project_root)
    systemd = FakeSystemdJobs()
    service = SinnixdService(
        ProjectCatalog([project_root]), jobs=generic_jobs(tmp_path, systemd)
    )

    def start(principal: str) -> dict[str, object]:
        response = service.dispatch(
            request(
                "job.start",
                "systemd-jobs",
                {"project_id": "fixture", "operation": "check"},
                principal=principal,
            )
        )
        assert response.ok and response.payload is not None
        return response.payload.inline

    operator_first = start("operator")
    operator_coalesced = start("operator")
    agent_first = start("agent-control")
    agent_coalesced = start("agent-control")

    assert operator_coalesced["job_id"] == operator_first["job_id"]
    assert operator_coalesced["coalesced"]
    assert agent_coalesced["job_id"] == agent_first["job_id"]
    assert agent_coalesced["coalesced"]
    assert agent_first["job_id"] != operator_first["job_id"]
    assert len(systemd.started) == 2

    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    for principal, launch in (
        ("operator", operator_first),
        ("agent-control", agent_first),
    ):
        job_id = launch["job_id"]
        assert isinstance(job_id, str)
        for operation, arguments in (
            ("job.get", {"job_id": job_id}),
            ("job.wait", {"job_id": job_id, "timeout_seconds": 1}),
            ("job.logs", {"job_id": job_id}),
            ("job.result", {"job_id": job_id}),
            ("job.cancel", {"job_id": job_id}),
        ):
            response = service.dispatch(
                request(operation, "systemd-jobs", arguments, principal=principal)
            )
            assert response.ok

    operator_reused = start("operator")
    agent_reused = start("agent-control")
    assert operator_reused["job_id"] == operator_first["job_id"]
    assert operator_reused["reused"]
    assert agent_reused["job_id"] == agent_first["job_id"]
    assert agent_reused["reused"]


def test_real_user_systemd_service_cgroup_cancels_descendants(tmp_path: Path) -> None:
    """Anti-vacuity: this enters systemd-run/systemctl; replacing the launcher with a subprocess leaves the child alive."""
    if shutil.which("systemd-run") is None or shutil.which("systemctl") is None:
        pytest.skip("systemd user tools are unavailable")
    manager = subprocess.run(["systemctl", "--user", "show-environment"], capture_output=True, text=True, check=False)
    if manager.returncode != 0:
        pytest.skip("a usable user systemd manager is unavailable")

    child_pid = tmp_path / "child.pid"
    script = tmp_path / "spawn-child.sh"
    script.write_text("#!/bin/sh\nsleep 30 &\necho $! > \"$1\"\necho lifecycle-output\nwait\n")
    script.chmod(0o700)
    jobs = GenericJobs(UserSystemdJobs(), GenericJobStore(tmp_path / "state"), wait_poll_seconds=0.05)
    started: dict[str, object] | None = None
    try:
        started = jobs.start_foreground(
            command=("/bin/sh", str(script), str(child_pid)),
            working_directory=str(tmp_path),
            environment=build_environment(source=os.environ),
            timeout_seconds=60,
        )
        deadline = time.monotonic() + 5
        while not child_pid.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert child_pid.exists()
        status = jobs.get(str(started["job_id"]))
        assert status["state"]["systemd"]["ControlGroup"].endswith(str(started["unit"]))

        cancelled = jobs.cancel(str(started["job_id"]))
        terminal = jobs.wait(str(started["job_id"]), timeout_seconds=5)
        pid = int(child_pid.read_text().strip())
        assert cancelled["cancel_requested"]
        assert terminal["state"]["phase"] == "cancelled"
        assert not Path(f"/proc/{pid}").exists()
    finally:
        if started is not None:
            try:
                UserSystemdJobs().stop(str(started["unit"]))
            except SystemdJobError:
                pass


def test_source_scoped_owner_adapter_is_registered_and_forwards_exact_response(tmp_path: Path) -> None:
    write_owner_adapter(tmp_path)
    source = SourceBinding(
        source_ref=SinnixRef.parse("sinnix://polylogue/archive"),
        generation="fixture-generation",
        root_digest="sha256:" + "1" * 64,
    )
    request_value = request(
        "polylogue.archive.status",
        "polylogue-archive",
        {"scope": "archive"},
    )
    owner_response = ResponseEnvelope(
        request_id=request_value.request_id,
        correlation_id=request_value.correlation_id,
        owner="polylogue-archive",
        payload=OpaquePayload.bounded({"archive": {"sessions": 2}}),
        source_bindings=(source,),
    )
    adapters = FakeOwnerAdapters(owner_response)
    service = SinnixdService(ProjectCatalog([tmp_path]), owner_adapters=adapters)

    response = service.dispatch(request_value)

    assert response == owner_response
    assert service.owners.resolve("polylogue.archive.status").source_scoped
    assert adapters.calls[0]["adapter"].source_ref == source.source_ref
    assert adapters.calls[0]["project"].project_id == "fixture"

    wrong_owner = service.dispatch(
        request("polylogue.archive.status", "wrong-owner", {"scope": "archive"})
    )
    assert wrong_owner.error is not None
    assert wrong_owner.error.code.value == "AUTHORITY_MISMATCH"


def test_owner_adapters_reject_duplicate_authority_namespaces(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_owner_adapter(first)
    write_owner_adapter(second)
    descriptor = second / ".agentctl" / "project.toml"
    descriptor.write_text(descriptor.read_text().replace('id = "fixture"', 'id = "second"'))

    with pytest.raises(ProjectConfigError, match="duplicate owner namespace"):
        SinnixdService(ProjectCatalog([first, second]))


def test_declared_owner_adapter_runs_fixed_command_and_enforces_source_binding(tmp_path: Path) -> None:
    write_owner_adapter(tmp_path)
    project, adapter = ProjectCatalog([tmp_path]).owner_adapter("polylogue.archive.status")
    source = SourceBinding(
        source_ref=SinnixRef.parse("sinnix://polylogue/archive"),
        generation="fixture-generation",
        root_digest="sha256:" + "2" * 64,
    )
    request_value = request(
        "polylogue.archive.status",
        "polylogue-archive",
        {"scope": "archive", "expected_source_binding": source.to_dict()},
    )
    response = ResponseEnvelope(
        request_id=request_value.request_id,
        correlation_id=request_value.correlation_id,
        owner="polylogue-archive",
        payload=OpaquePayload.bounded({"archive": {"sessions": 2}}),
        source_bindings=(source,),
    )
    execution = FakeExecution(
        ExecutionResult(
            command=(),
            exit_status=0,
            stdout=json.dumps(response.to_dict()).encode(),
            stderr=b"",
        )
    )

    result = DeclaredOwnerAdapters(execution).call(
        project=project,
        adapter=adapter,
        request=request_value,
    )

    command, profile = execution.calls[0]
    forwarded = json.loads(profile.stdin_bytes)
    assert result == response
    assert profile.route.environment_profile is EnvironmentProfile.USER_BUS
    assert command[:7] == (
        "/run/current-system/sw/bin/systemd-run",
        "--user",
        "--quiet",
        "--collect",
        "--wait",
        "--pipe",
        f"--unit=sinnixd-owner-{request_value.request_id}.service",
    )
    assert command[-3:] == ("fixture-env", "--command", "polylogue-agentctl-adapter")
    assert forwarded["arguments"] == {"scope": "archive"}

    wrong_precondition = request(
        "polylogue.archive.status",
        "polylogue-archive",
        {
            "scope": "archive",
            "expected_source_binding": {
                **source.to_dict(),
                "source_ref": "sinnix://polylogue/other",
            },
        },
    )
    with pytest.raises(OwnerAdapterError, match="different source"):
        DeclaredOwnerAdapters(execution).call(
            project=project,
            adapter=adapter,
            request=wrong_precondition,
        )
    assert len(execution.calls) == 1

    wrong_source = ResponseEnvelope(
        request_id=request_value.request_id,
        correlation_id=request_value.correlation_id,
        owner="polylogue-archive",
        payload=OpaquePayload.bounded({"archive": {"sessions": 2}}),
        source_bindings=(
            SourceBinding(
                source_ref=SinnixRef.parse("sinnix://polylogue/other"),
                generation=source.generation,
                root_digest=source.root_digest,
            ),
        ),
    )
    execution.result = ExecutionResult(
        command=(),
        exit_status=0,
        stdout=json.dumps(wrong_source.to_dict()).encode(),
        stderr=b"",
    )
    with pytest.raises(OwnerAdapterError, match="wrong source"):
        DeclaredOwnerAdapters(execution).call(
            project=project,
            adapter=adapter,
            request=request_value,
        )


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


def test_unix_socket_server_returns_json_rpc_errors_without_crashing(tmp_path: Path) -> None:
    write_adapter(tmp_path / "project")
    socket_path = tmp_path / "sinnixd.sock"
    server = UnixSocketServer(socket_path, SinnixdService(ProjectCatalog([tmp_path / "project"])))
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


def test_unix_socket_server_continues_after_malformed_and_stalled_clients(tmp_path: Path) -> None:
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
