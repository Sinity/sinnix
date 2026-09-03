from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sinnix_mcp import RequestEnvelope
from sinnixd.jobs import GenericJobs, GenericJobStore, UserSystemdJobs
from sinnixd.project_plans import PlanStore, ProjectPlanError, ProjectPlanExecutor
from sinnixd.projects import ProjectCatalog
from sinnixd.service import SinnixdService

if TYPE_CHECKING:
    from conftest import FakePueue


def finish(
    fake_pueue: FakePueue, job_id: str, jobs: GenericJobs, *, success: bool = True
) -> None:
    record = jobs.store.load(job_id)
    assert record.queue_task_id is not None
    if success:
        fake_pueue.succeed(record.queue_task_id)
    else:
        fake_pueue.fail(record.queue_task_id, exit_code=1)
    if record.result_path is not None:
        record.result_path.write_text(json.dumps({"job": job_id, "ok": success}))


def plan_fixture(
    tmp_path: Path, fake_pueue: FakePueue
) -> tuple[ProjectPlanExecutor, FakePueue, GenericJobs]:
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
[operations.node.parameters.value]
type = "string"
flag = "--value"
required = true
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
    jobs = GenericJobs(UserSystemdJobs(), GenericJobStore(tmp_path / "state"))
    plans = ProjectPlanExecutor(
        catalog, jobs, PlanStore(jobs.store.root), workspaces=None
    )
    return plans, fake_pueue, jobs


def submit(
    plans: ProjectPlanExecutor,
    nodes: list[dict[str, object]],
) -> dict[str, object]:
    return plans.submit(
        {
            "project_id": "fixture",
            "nodes": nodes,
        },
        correlation_id="fixture-correlation",
        principal="operator",
    )


def test_plan_rejects_cycles_and_validates_payload_schema(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    plans, _, _ = plan_fixture(tmp_path, fake_pueue)
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
    with pytest.raises(ProjectPlanError, match="omit required field"):
        submit(plans, [{"id": "n", "operation": "node"}])


def test_ready_nodes_run_concurrently_and_keep_dependency_job_ids(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    plans, fake_pueue, jobs = plan_fixture(tmp_path, fake_pueue)
    result = submit(
        plans,
        [
            {"id": "a", "operation": "prepare"},
            {"id": "b", "operation": "prepare"},
            {"id": "c", "operation": "prepare", "depends_on": ["a", "b"]},
        ],
    )
    # Every node is submitted at once; pueue holds the dependent behind its
    # `--after` edges rather than sinnixd withholding the submission.
    assert len(fake_pueue.added) == 3
    nodes = {node["node_id"]: node for node in result["nodes"]}
    child = jobs.store.load(nodes["c"]["job_id"])
    assert child.spec.dependency_job_ids == (nodes["a"]["job_id"], nodes["b"]["job_id"])
    child_task = next(
        added
        for added in fake_pueue.added
        if added["label"].endswith(nodes["c"]["job_id"])
    )
    assert set(child_task["after"]) == {
        jobs.store.load(nodes["a"]["job_id"]).queue_task_id,
        jobs.store.load(nodes["b"]["job_id"]).queue_task_id,
    }
    assert child.spec.exclusive_keys == ()


def test_plan_accepts_nodes_before_their_dependencies(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    plans, fake_pueue, jobs = plan_fixture(tmp_path, fake_pueue)
    result = submit(
        plans,
        [
            {"id": "child", "operation": "prepare", "depends_on": ["parent"]},
            {"id": "parent", "operation": "prepare"},
        ],
    )
    nodes = {node["node_id"]: node for node in result["nodes"]}
    child = jobs.store.load(nodes["child"]["job_id"])
    assert child.spec.dependency_job_ids == (nodes["parent"]["job_id"],)
    assert [item["label"] for item in fake_pueue.added]


def test_dependency_failure_blocks_downstream_node(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    plans, fake_pueue, jobs = plan_fixture(tmp_path, fake_pueue)
    result = submit(
        plans,
        [
            {"id": "a", "operation": "prepare"},
            {"id": "b", "operation": "prepare", "depends_on": ["a"]},
        ],
    )
    a = next(node for node in result["nodes"] if node["node_id"] == "a")
    finish(fake_pueue, a["job_id"], jobs, success=False)
    aggregate = plans.get(result["plan_id"])
    states = {node["node_id"]: node["state"]["phase"] for node in aggregate["nodes"]}
    assert states == {"a": "failed", "b": "dependency-failed"}
    assert aggregate["state"]["phase"] == "failed"


def test_interrupted_manifest_reconciles_to_existing_node_job(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    plans, _, _ = plan_fixture(tmp_path, fake_pueue)
    result = submit(plans, [{"id": "n", "operation": "prepare"}])
    stored = plans.store.load(result["plan_id"])
    job_id = stored["nodes"][0]["job_id"]
    stored["nodes"][0]["job_id"] = None
    plans.store.save(stored)

    recovered = plans.get(result["plan_id"])
    assert recovered["nodes"][0]["job_id"] == job_id
    assert recovered["nodes"][0]["state"]["phase"] == "running"


def test_node_operation_payloads_and_aggregate_results_are_bounded(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    plans, fake_pueue, jobs = plan_fixture(tmp_path, fake_pueue)
    result = plans.submit(
        {
            "project_id": "fixture",
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
    finish(fake_pueue, first_job, jobs)
    plans.get(result["plan_id"])
    assert len(fake_pueue.added) == 2
    second_job = next(
        node["job_id"] for node in result["nodes"] if node["job_id"] != first_job
    )
    finish(fake_pueue, second_job, jobs)
    aggregate = plans.get(result["plan_id"])
    encoded = json.dumps(aggregate["result"], separators=(",", ":")).encode()
    assert len(encoded) <= 64_000
    assert [node["result"]["value"]["ok"] for node in aggregate["nodes"]] == [
        True,
        True,
    ]


def test_plan_service_routes_preserve_typed_owner_surface(
    tmp_path: Path, fake_pueue: FakePueue
) -> None:
    plans, _, jobs = plan_fixture(tmp_path, fake_pueue)
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
                "nodes": [{"id": "n", "operation": "prepare"}],
            },
        )
    )
    assert response.ok
    assert response.owner == "project-plans"
