from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import pytest
from sinnix_mcp import RequestEnvelope

from sinnixd.jobs import GenericJobs, GenericJobStore, _completion_marker_path
from sinnixd.project_plans import PlanStore, ProjectPlanError, ProjectPlanExecutor
from sinnixd.projects import ProjectCatalog
from sinnixd.service import SinnixdService


@dataclass
class PlanSystemd:
    started: list[dict[str, object]] = field(default_factory=list)
    properties: dict[str, dict[str, str]] = field(default_factory=dict)

    def start(self, **kwargs: object) -> None:
        unit = str(kwargs["unit"])
        self.started.append(dict(kwargs))
        self.properties.setdefault(
            unit,
            {
                "LoadState": "loaded",
                "ActiveState": "active",
                "Result": "success",
                "ExecMainStatus": "0",
                "InvocationID": unit,
            },
        )

    def show(self, unit: str, *, timeout_seconds: float = 0.25) -> dict[str, str]:
        return dict(self.properties.get(unit, {"LoadState": "not-found"}))

    def stop(self, unit: str) -> None:
        self.properties[unit] = {
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "signal",
            "ExecMainStatus": "15",
            "InvocationID": unit,
        }

    def finish(self, job_id: str, jobs: GenericJobs, *, success: bool = True) -> None:
        record = jobs.store.load(job_id)
        self.properties[record.unit] = {
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "success" if success else "exit-code",
            "ExecMainStatus": "0" if success else "1",
            "InvocationID": record.unit,
        }
        _completion_marker_path(record.log_path).write_text("done\n")
        if record.result_path is not None:
            record.result_path.write_text(json.dumps({"job": job_id, "ok": success}))


def plan_fixture(
    tmp_path: Path,
) -> tuple[ProjectPlanExecutor, PlanSystemd, GenericJobs]:
    root = tmp_path / "project"
    root.mkdir()
    (root / "tracked").write_text("fixture\n")
    (root / ".agentctl").mkdir()
    (root / ".agentctl" / "project.toml").write_text("""
schema = 1
[project]
id = "fixture"
display_name = "Fixture"
root_markers = ["tracked"]
[environment]
kind = "fixture"
command = ["env"]
[operations.prepare]
description = "prepare"
exec = ["prepare"]
pool = "normal"
result = "json"
cache = "none"
[operations.node]
description = "node"
exec = ["node"]
pool = "normal"
result = "json"
cache = "none"
plan_node = true
exclusive_keys = ["fixture:promotion"]
[operations.node.parameters.value]
type = "string"
flag = "--value"
max_length = 32
""")
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--quiet",
            "-m",
            "fixture",
        ],
        check=True,
    )
    catalog = ProjectCatalog([root])
    systemd = PlanSystemd()
    jobs = GenericJobs(systemd, GenericJobStore(tmp_path / "state"))
    plans = ProjectPlanExecutor(
        catalog, jobs, PlanStore(jobs.store.root), workspaces=None
    )
    return plans, systemd, jobs


def submit(
    plans: ProjectPlanExecutor,
    nodes: list[dict[str, object]],
    generation: str = "gen-1",
) -> dict[str, object]:
    return plans.submit(
        {
            "project_id": "fixture",
            "input_generation": generation,
            "nodes": nodes,
        },
        correlation_id="fixture-correlation",
        principal="operator",
    )


def test_plan_rejects_cycles_and_validates_payload_schema(tmp_path: Path) -> None:
    plans, _, _ = plan_fixture(tmp_path)
    with pytest.raises(ProjectPlanError, match="cycle"):
        submit(
            plans,
            [
                {"id": "a", "operation": "prepare", "depends_on": ["b"]},
                {"id": "b", "operation": "prepare", "depends_on": ["a"]},
            ],
        )
    with pytest.raises(ProjectPlanError, match="unknown field"):
        submit(
            plans,
            [{"id": "n", "operation": "node", "parameters": {"unknown": True}}],
        )


def test_ready_nodes_run_concurrently_and_keep_dependency_job_ids(
    tmp_path: Path,
) -> None:
    plans, systemd, jobs = plan_fixture(tmp_path)
    result = submit(
        plans,
        [
            {"id": "a", "operation": "prepare"},
            {"id": "b", "operation": "prepare"},
            {"id": "c", "operation": "prepare", "depends_on": ["a", "b"]},
        ],
    )
    assert len(systemd.started) == 2
    nodes = {node["node_id"]: node for node in result["nodes"]}
    child = jobs.store.load(nodes["c"]["job_id"])
    assert child.spec.dependency_job_ids == (nodes["a"]["job_id"], nodes["b"]["job_id"])
    assert child.spec.exclusive_keys == ()


def test_dependency_failure_blocks_downstream_node(tmp_path: Path) -> None:
    plans, systemd, jobs = plan_fixture(tmp_path)
    result = submit(
        plans,
        [
            {"id": "a", "operation": "prepare"},
            {"id": "b", "operation": "prepare", "depends_on": ["a"]},
        ],
    )
    a = next(node for node in result["nodes"] if node["node_id"] == "a")
    systemd.finish(a["job_id"], jobs, success=False)
    aggregate = plans.get(result["plan_id"])
    states = {node["node_id"]: node["state"]["phase"] for node in aggregate["nodes"]}
    assert states == {"a": "failed", "b": "dependency-failed"}
    assert aggregate["state"]["phase"] == "failed"


def test_exact_completed_nodes_are_reused_and_mismatches_are_rejected(
    tmp_path: Path,
) -> None:
    plans, systemd, jobs = plan_fixture(tmp_path)
    nodes = [{"id": "n", "operation": "node", "parameters": {"value": "one"}}]
    first = submit(plans, nodes)
    node = first["nodes"][0]
    systemd.finish(node["job_id"], jobs)
    assert plans.get(first["plan_id"])["state"]["phase"] == "succeeded"
    before = len(systemd.started)

    repeated = submit(plans, nodes)
    assert repeated["nodes"][0]["job_id"] == node["job_id"]
    assert repeated["nodes"][0]["reused"] is True
    assert len(systemd.started) == before

    changed_generation = submit(plans, nodes, generation="gen-2")
    assert changed_generation["nodes"][0]["job_id"] != node["job_id"]
    changed_payload = submit(
        plans,
        [{"id": "n", "operation": "node", "parameters": {"value": "two"}}],
    )
    assert changed_payload["nodes"][0]["job_id"] != node["job_id"]


def test_interrupted_manifest_reconciles_to_existing_node_job(tmp_path: Path) -> None:
    plans, _, _ = plan_fixture(tmp_path)
    result = submit(plans, [{"id": "n", "operation": "prepare"}])
    stored = plans.store.load(result["plan_id"])
    job_id = stored["nodes"][0]["job_id"]
    stored["nodes"][0]["job_id"] = None
    plans.store.save(stored)

    recovered = plans.get(result["plan_id"])
    assert recovered["nodes"][0]["job_id"] == job_id
    assert recovered["nodes"][0]["state"]["phase"] == "running"


def test_node_operation_payloads_and_aggregate_results_are_bounded(
    tmp_path: Path,
) -> None:
    plans, systemd, jobs = plan_fixture(tmp_path)
    result = plans.submit(
        {
            "project_id": "fixture",
            "input_generation": "gen-1",
            "node_operation": "node",
            "nodes": [
                {"id": "one", "payload": {"value": "one"}},
                {"id": "two", "payload": {"value": "two"}},
            ],
        },
        correlation_id="fixture-correlation",
        principal="operator",
    )
    first_job = result["nodes"][0]["job_id"]
    systemd.finish(first_job, jobs)
    progressed = plans.get(result["plan_id"])
    assert len(systemd.started) == 2
    second_job = next(
        node["job_id"] for node in result["nodes"] if node["job_id"] != first_job
    )
    systemd.finish(second_job, jobs)
    aggregate = plans.get(result["plan_id"])
    encoded = json.dumps(aggregate["result"], separators=(",", ":")).encode()
    assert len(encoded) <= 64_000
    assert [node["result"]["value"]["ok"] for node in aggregate["nodes"]] == [
        True,
        True,
    ]


def test_plan_service_routes_preserve_typed_owner_surface(tmp_path: Path) -> None:
    plans, _, jobs = plan_fixture(tmp_path)
    service = SinnixdService(plans.projects, jobs=jobs)
    response = service.dispatch(
        RequestEnvelope(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            operation="plan.submit",
            owner="project-plans",
            principal="operator",
            arguments={
                "project_id": "fixture",
                "input_generation": "gen-1",
                "nodes": [{"id": "n", "operation": "prepare"}],
            },
        )
    )
    assert response.ok
    assert response.owner == "project-plans"
