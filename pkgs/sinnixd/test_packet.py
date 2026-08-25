from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import sinnixd.cli as cli_module
from sinnix_mcp import ErrorCode
from sinnixd.delivery import DeliveryError
from sinnixd.packet import PacketFinalizeSaga, PacketSagaError, PacketSagaStore
from sinnixd.tasks import TaskError

WORKSPACE_ID = "workspace-1"
VERIFICATION_JOB_ID = "verification-1"
PACKET_JOB_ID = "packet-1"
MERGE_SHA = "a" * 40


@dataclass
class FakeWorkspaces:
    present: bool = True

    def get(self, workspace_id: str) -> dict[str, str]:
        if not self.present:
            raise KeyError(workspace_id)
        return {"workspace_id": workspace_id, "project_id": "fixture"}


@dataclass
class FakeDelivery:
    workspaces: FakeWorkspaces = field(default_factory=FakeWorkspaces)
    refuse_land: bool = False
    land_after_mutation: bool = False
    land_calls: int = 0
    merge_mutations: int = 0
    finish_calls: int = 0
    finish_after_removal: bool = False

    def land(
        self, workspace_id: str, job_id: str, *, packet_job_id: str
    ) -> dict[str, object]:
        self.land_calls += 1
        if self.refuse_land:
            raise DeliveryError("review is not in a landable GitHub state")
        if self.land_after_mutation and self.merge_mutations == 0:
            self.merge_mutations += 1
            raise DeliveryError("GitHub reply was lost after merge")
        if self.merge_mutations == 0:
            self.merge_mutations += 1
        return {
            "landed": True,
            "completion": {
                "bead_ref": "sinnix://projects/fixture/beads/task-1",
                "head": MERGE_SHA,
            },
        }

    def finish(self, workspace_id: str) -> dict[str, object]:
        self.finish_calls += 1
        if self.finish_after_removal:
            self.workspaces.present = False
            self.finish_after_removal = False
            raise KeyboardInterrupt("crash after workspace removal")
        if not self.workspaces.present:
            raise KeyError(workspace_id)
        self.workspaces.present = False
        return {"workspace_id": workspace_id, "finished": True, "head": MERGE_SHA}


@dataclass
class FakeTasks:
    fail_after_apply: bool = False
    crash_before_apply: bool = False
    calls: int = 0
    mutations: int = 0

    def execute(
        self,
        *,
        operation: str,
        arguments: dict[str, object],
        principal: str,
        mutation_id: str,
    ) -> dict[str, object]:
        assert operation == "task.complete"
        assert principal == "agent-control"
        assert mutation_id.startswith("packet-")
        self.calls += 1
        if self.crash_before_apply:
            self.crash_before_apply = False
            raise KeyboardInterrupt("crash after completion consumption")
        if self.mutations == 0:
            self.mutations += 1
            if self.fail_after_apply:
                self.fail_after_apply = False
                raise TaskError(
                    ErrorCode.OWNER_UNAVAILABLE, "task backend reply was lost"
                )
        return {"result": {"state": "applied"}}


def saga(
    tmp_path: Path, delivery: FakeDelivery, tasks: FakeTasks
) -> PacketFinalizeSaga:
    return PacketFinalizeSaga(
        delivery=delivery, tasks=tasks, store=PacketSagaStore(tmp_path / "state")
    )


def finalize(instance: PacketFinalizeSaga) -> dict[str, object]:
    return instance.finalize(
        workspace_id=WORKSPACE_ID,
        verification_job_id=VERIFICATION_JOB_ID,
        packet_job_id=PACKET_JOB_ID,
    )


def test_packet_finalize_success_is_idempotent_and_has_a_durable_record(
    tmp_path: Path,
) -> None:
    delivery = FakeDelivery()
    tasks = FakeTasks()
    instance = saga(tmp_path, delivery, tasks)

    first = finalize(instance)
    replayed = finalize(instance)

    assert first["state"] == replayed["state"] == "complete"
    assert first["step"] == replayed["step"] == "complete"
    assert delivery.land_calls == 1
    assert delivery.merge_mutations == 1
    assert tasks.calls == 1
    assert delivery.finish_calls == 1
    assert instance.store.load(first["saga_id"])["step"] == "complete"


def test_packet_finalize_land_refusal_parks_then_resumes_without_duplicate_merge(
    tmp_path: Path,
) -> None:
    delivery = FakeDelivery(refuse_land=True)
    tasks = FakeTasks()
    instance = saga(tmp_path, delivery, tasks)

    with pytest.raises(PacketSagaError) as refused:
        finalize(instance)
    assert refused.value.code == ErrorCode.INVALID_ARGUMENT
    delivery.refuse_land = False

    result = finalize(instance)

    assert result["state"] == "complete"
    assert delivery.land_calls == 2
    assert delivery.merge_mutations == 1


def test_packet_finalize_land_crash_window_reconciles_a_single_merge(
    tmp_path: Path,
) -> None:
    delivery = FakeDelivery(land_after_mutation=True)
    tasks = FakeTasks()
    instance = saga(tmp_path, delivery, tasks)

    with pytest.raises(PacketSagaError):
        finalize(instance)
    result = finalize(instance)

    assert result["state"] == "complete"
    assert delivery.land_calls == 2
    assert delivery.merge_mutations == 1


def test_packet_finalize_missing_artifact_is_typed_and_remains_parked(
    tmp_path: Path,
) -> None:
    delivery = FakeDelivery()
    tasks = FakeTasks()
    original_land = delivery.land

    def missing_artifact(
        workspace_id: str, job_id: str, *, packet_job_id: str
    ) -> dict[str, object]:
        original_land(workspace_id, job_id, packet_job_id=packet_job_id)
        return {"landed": True}

    delivery.land = missing_artifact  # type: ignore[method-assign]
    instance = saga(tmp_path, delivery, tasks)

    with pytest.raises(PacketSagaError) as refused:
        finalize(instance)
    assert refused.value.code == ErrorCode.RESULT_INVALID
    status = instance.status(refused.value.saga_id)
    assert status["step"] == "completion"
    assert status["failure"]["code"] == ErrorCode.RESULT_INVALID.value
    assert tasks.calls == 0


def test_packet_finalize_completion_crash_window_resumes_without_relanding(
    tmp_path: Path,
) -> None:
    delivery = FakeDelivery()
    tasks = FakeTasks(crash_before_apply=True)
    instance = saga(tmp_path, delivery, tasks)

    with pytest.raises(KeyboardInterrupt):
        finalize(instance)
    assert (
        instance.status(
            instance.store.saga_id(
                "fixture", WORKSPACE_ID, VERIFICATION_JOB_ID, PACKET_JOB_ID
            )
        )["step"]
        == "task.complete"
    )

    result = finalize(instance)

    assert result["state"] == "complete"
    assert delivery.land_calls == 1
    assert tasks.mutations == 1


def test_packet_finalize_task_complete_crash_window_replays_idempotently(
    tmp_path: Path,
) -> None:
    delivery = FakeDelivery()
    tasks = FakeTasks(fail_after_apply=True)
    instance = saga(tmp_path, delivery, tasks)

    with pytest.raises(PacketSagaError) as refused:
        finalize(instance)
    assert refused.value.code == ErrorCode.OWNER_UNAVAILABLE
    assert instance.status(refused.value.saga_id)["step"] == "task.complete"

    result = finalize(instance)

    assert result["state"] == "complete"
    assert tasks.calls == 2
    assert tasks.mutations == 1
    assert delivery.land_calls == 1
    assert delivery.finish_calls == 1


def test_packet_finalize_finish_crash_window_recovers_after_workspace_removal(
    tmp_path: Path,
) -> None:
    delivery = FakeDelivery(finish_after_removal=True)
    tasks = FakeTasks()
    instance = saga(tmp_path, delivery, tasks)

    with pytest.raises(KeyboardInterrupt):
        finalize(instance)
    status = instance.status(
        instance.store.saga_id(
            "fixture", WORKSPACE_ID, VERIFICATION_JOB_ID, PACKET_JOB_ID
        )
    )
    assert status["step"] == "finish"
    assert status["failure"]["state"] == "started"

    result = finalize(instance)

    assert result["state"] == "complete"
    assert delivery.finish_calls == 2
    assert tasks.calls == 1


def test_agentctl_packet_finalize_maps_to_the_packet_saga_route(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured: dict[str, object] = {}

    def fake_call(_socket_path: Path, request: object) -> dict[str, object]:
        captured["request"] = request
        return {"schema": 1, "ok": True}

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agentctl",
            "packet",
            "finalize",
            WORKSPACE_ID,
            "--verification-job",
            VERIFICATION_JOB_ID,
            "--packet-job",
            PACKET_JOB_ID,
        ],
    )
    monkeypatch.setattr(cli_module, "call", fake_call)

    assert cli_module.main() == 0
    request = captured["request"]
    assert request.operation == "packet.finalize"
    assert request.owner == "packet-saga"
    assert request.principal == "operator"
    assert dict(request.arguments) == {
        "workspace_id": WORKSPACE_ID,
        "verification_job_id": VERIFICATION_JOB_ID,
        "packet_job_id": PACKET_JOB_ID,
    }
    assert capsys.readouterr().out
