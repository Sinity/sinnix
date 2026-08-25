from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from sinnix_lib.atomic_json import write_json_atomic
from sinnix_lib.lock import flock
from sinnix_mcp import ErrorCode

from .delivery import DeliveryError, GitHubDelivery
from .tasks import TaskError, TaskService
from .workspaces import WorkspaceError

SAGA_SCHEMA_VERSION = 1
SAGA_DIRECTORY = "packet-sagas"
_SHA_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_TASK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class PacketSagaError(ValueError):
    """A packet finalization step parked a resumable saga."""

    def __init__(self, code: ErrorCode, message: str, saga_id: str) -> None:
        self.code = code
        self.saga_id = saga_id
        super().__init__(f"{message} (saga_id={saga_id})")


@dataclass(frozen=True)
class PacketSagaStore:
    """Durable outbox records for packet finalization."""

    root: Path

    @property
    def sagas_root(self) -> Path:
        return self.root / SAGA_DIRECTORY

    def saga_id(
        self,
        project_id: str,
        workspace_id: str,
        verification_job_id: str,
        packet_job_id: str,
    ) -> str:
        # Workspace IDs are globally durable identities. Keeping project_id in
        # the record still detects cross-project reuse, while omitting it from
        # the key lets a retry find a completed saga after workspace finish
        # removed the workspace record.
        identity = "\0".join((workspace_id, verification_job_id, packet_job_id))
        return "packet-" + hashlib.sha256(identity.encode()).hexdigest()[:32]

    def path(self, saga_id: str) -> Path:
        if not re.fullmatch(r"packet-[0-9a-f]{32}", saga_id):
            raise ValueError("packet saga id is malformed")
        return self.sagas_root / f"{saga_id}.json"

    @contextmanager
    def locked(self, saga_id: str) -> Iterator[None]:
        path = self.path(saga_id)
        self.sagas_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        with flock(path.with_name(path.name + ".lock")):
            yield

    def load(self, saga_id: str) -> dict[str, Any] | None:
        path = self.path(saga_id)
        try:
            value = json.loads(path.read_text())
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("packet saga record is unavailable") from error
        self._validate(value, saga_id)
        return value

    def save(self, value: Mapping[str, Any]) -> None:
        saga_id = value.get("saga_id")
        if not isinstance(saga_id, str):
            raise ValueError("packet saga record has no id")
        self._validate(value, saga_id)
        path = self.path(saga_id)
        write_json_atomic(path, dict(value), mode=0o600, fsync=True)
        try:
            descriptor = os.open(
                path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            )
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError as error:
            raise ValueError("packet saga record durability failed") from error

    @staticmethod
    def _validate(value: Any, saga_id: str) -> None:
        fields = {
            "schema_version",
            "saga_id",
            "project_id",
            "workspace_id",
            "verification_job_id",
            "packet_job_id",
            "step",
            "attempts",
            "land_receipt",
            "completion",
            "task_id",
            "merge_sha",
            "task_receipt",
            "finish_receipt",
            "failure",
        }
        if not isinstance(value, Mapping) or set(value) != fields:
            raise ValueError("packet saga record schema is invalid")
        if (
            value["schema_version"] != SAGA_SCHEMA_VERSION
            or value["saga_id"] != saga_id
            or any(
                not isinstance(value[name], str) or not value[name]
                for name in (
                    "project_id",
                    "workspace_id",
                    "verification_job_id",
                    "packet_job_id",
                )
            )
            or value["step"]
            not in {"land", "completion", "task.complete", "finish", "complete"}
            or isinstance(value["attempts"], bool)
            or not isinstance(value["attempts"], int)
            or not 0 <= value["attempts"] <= 1000
        ):
            raise ValueError("packet saga record fields are invalid")
        for name in (
            "land_receipt",
            "completion",
            "task_receipt",
            "finish_receipt",
            "failure",
        ):
            if value[name] is not None and not isinstance(value[name], dict):
                raise ValueError("packet saga record fields are invalid")
        if value["task_id"] is not None and not isinstance(value["task_id"], str):
            raise ValueError("packet saga task id is invalid")
        if value["merge_sha"] is not None and (
            not isinstance(value["merge_sha"], str)
            or not _SHA_RE.fullmatch(value["merge_sha"])
        ):
            raise ValueError("packet saga merge SHA is invalid")

    def create(
        self,
        *,
        saga_id: str,
        project_id: str,
        workspace_id: str,
        verification_job_id: str,
        packet_job_id: str,
    ) -> dict[str, Any]:
        value = {
            "schema_version": SAGA_SCHEMA_VERSION,
            "saga_id": saga_id,
            "project_id": project_id,
            "workspace_id": workspace_id,
            "verification_job_id": verification_job_id,
            "packet_job_id": packet_job_id,
            "step": "land",
            "attempts": 0,
            "land_receipt": None,
            "completion": None,
            "task_id": None,
            "merge_sha": None,
            "task_receipt": None,
            "finish_receipt": None,
            "failure": None,
        }
        self.save(value)
        return value


@dataclass
class PacketFinalizeSaga:
    delivery: GitHubDelivery
    tasks: TaskService
    store: PacketSagaStore

    def finalize(
        self,
        *,
        workspace_id: str,
        verification_job_id: str,
        packet_job_id: str,
    ) -> dict[str, Any]:
        saga_id = self.store.saga_id(
            "", workspace_id, verification_job_id, packet_job_id
        )
        with self.store.locked(saga_id):
            record = self.store.load(saga_id)
            if record is None:
                workspace = self.delivery.workspaces.get(workspace_id)
                project_id = workspace["project_id"]
                record = self.store.create(
                    saga_id=saga_id,
                    project_id=project_id,
                    workspace_id=workspace_id,
                    verification_job_id=verification_job_id,
                    packet_job_id=packet_job_id,
                )
            else:
                project_id = record["project_id"]
            self._check_identity(
                record,
                project_id,
                workspace_id,
                verification_job_id,
                packet_job_id,
            )
            if record["step"] == "complete":
                return self._response(record)
            try:
                self._run_steps(record)
            except PacketSagaError:
                raise
            except (ValueError, OSError) as error:
                self._park(record, "saga", ErrorCode.OPERATION_FAILED, str(error))
                raise PacketSagaError(
                    ErrorCode.OPERATION_FAILED, str(error), saga_id
                ) from error
            return self._response(record)

    def status(self, saga_id: str) -> dict[str, Any]:
        record = self.store.load(saga_id)
        if record is None:
            raise ValueError("packet saga was not found")
        return self._response(record)

    def _run_steps(self, record: dict[str, Any]) -> None:
        if record["step"] == "land":
            self._land(record)
        if record["step"] == "completion":
            self._consume_completion(record)
        if record["step"] == "task.complete":
            self._complete_task(record)
        if record["step"] == "finish":
            self._finish(record)

    def _land(self, record: dict[str, Any]) -> None:
        self._attempt(record)
        try:
            receipt = self.delivery.land(
                record["workspace_id"],
                record["verification_job_id"],
                packet_job_id=record["packet_job_id"],
            )
        except DeliveryError as error:
            self._park(record, "land", ErrorCode.INVALID_ARGUMENT, str(error))
            raise PacketSagaError(
                ErrorCode.INVALID_ARGUMENT, str(error), record["saga_id"]
            ) from error
        if not isinstance(receipt, dict):
            self._park(
                record, "land", ErrorCode.RESULT_INVALID, "land returned no receipt"
            )
            raise PacketSagaError(
                ErrorCode.RESULT_INVALID, "land returned no receipt", record["saga_id"]
            )
        record["land_receipt"] = receipt
        record["step"] = "completion"
        record["failure"] = None
        self.store.save(record)

    def _consume_completion(self, record: dict[str, Any]) -> None:
        self._attempt(record)
        receipt = record.get("land_receipt")
        completion = receipt.get("completion") if isinstance(receipt, Mapping) else None
        try:
            project_id, task_id, merge_sha = self._completion_identity(
                completion, record["project_id"]
            )
        except ValueError as error:
            self._park(record, "completion", ErrorCode.RESULT_INVALID, str(error))
            raise PacketSagaError(
                ErrorCode.RESULT_INVALID, str(error), record["saga_id"]
            ) from error
        record["completion"] = dict(completion)
        record["task_id"] = task_id
        record["merge_sha"] = merge_sha
        if project_id != record["project_id"]:
            raise AssertionError("completion project was checked before assignment")
        record["step"] = "task.complete"
        record["failure"] = None
        self.store.save(record)

    def _complete_task(self, record: dict[str, Any]) -> None:
        self._attempt(record)
        try:
            result = self.tasks.execute(
                operation="task.complete",
                arguments={
                    "project_id": record["project_id"],
                    "task_id": record["task_id"],
                    "merge_sha": record["merge_sha"],
                    "reason": f"landed packet {record['saga_id']}",
                },
                principal="agent-control",
                mutation_id=record["saga_id"],
            )
        except TaskError as error:
            self._park(record, "task.complete", error.code, str(error))
            raise PacketSagaError(error.code, str(error), record["saga_id"]) from error
        record["task_receipt"] = result
        record["step"] = "finish"
        record["failure"] = None
        self.store.save(record)

    def _finish(self, record: dict[str, Any]) -> None:
        self._attempt(record)
        record["failure"] = {"step": "finish", "state": "started"}
        self.store.save(record)
        try:
            result = self.delivery.finish(record["workspace_id"])
        except (DeliveryError, WorkspaceError, KeyError) as error:
            # finish_merged removes the workspace atomically. If the process
            # died after that mutation and before save(), the missing record is
            # the only authority available to this saga, so resume completes it.
            try:
                self.delivery.workspaces.get(record["workspace_id"])
            except (KeyError, WorkspaceError):
                result = {
                    "workspace_id": record["workspace_id"],
                    "finished": True,
                    "head": record["merge_sha"],
                    "recovered": True,
                }
            else:
                self._park(record, "finish", ErrorCode.INVALID_ARGUMENT, str(error))
                raise PacketSagaError(
                    ErrorCode.INVALID_ARGUMENT, str(error), record["saga_id"]
                ) from error
        record["finish_receipt"] = result
        record["failure"] = None
        record["step"] = "complete"
        self.store.save(record)

    def _attempt(self, record: dict[str, Any]) -> None:
        record["attempts"] += 1
        self.store.save(record)

    def _park(
        self, record: dict[str, Any], step: str, code: ErrorCode, message: str
    ) -> None:
        record["step"] = step
        record["failure"] = {"step": step, "code": code.value, "message": message}
        self.store.save(record)

    @staticmethod
    def _check_identity(
        record: Mapping[str, Any],
        project_id: str,
        workspace_id: str,
        verification_job_id: str,
        packet_job_id: str,
    ) -> None:
        if any(
            record[name] != value
            for name, value in (
                ("project_id", project_id),
                ("workspace_id", workspace_id),
                ("verification_job_id", verification_job_id),
                ("packet_job_id", packet_job_id),
            )
        ):
            raise ValueError("packet saga identity conflicts with its durable record")

    @staticmethod
    def _completion_identity(completion: Any, project_id: str) -> tuple[str, str, str]:
        if not isinstance(completion, Mapping):
            raise ValueError("completion artifact is missing")
        bead_ref = completion.get("bead_ref")
        prefix = f"sinnix://projects/{project_id}/beads/"
        if (
            not isinstance(bead_ref, str)
            or not bead_ref.startswith(prefix)
            or not bead_ref.removeprefix(prefix)
            or "/" in bead_ref.removeprefix(prefix)
        ):
            raise ValueError("completion artifact lacks a valid Beads reference")
        task_id = bead_ref.removeprefix(prefix)
        if not _TASK_RE.fullmatch(task_id):
            raise ValueError("completion artifact task reference is malformed")
        merge_sha = completion.get("head")
        if not isinstance(merge_sha, str) or not _SHA_RE.fullmatch(merge_sha):
            raise ValueError("completion artifact lacks a valid merge SHA")
        return project_id, task_id, merge_sha

    @staticmethod
    def _response(record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "saga_id": record["saga_id"],
            "state": "complete" if record["step"] == "complete" else "parked",
            "step": record["step"],
            "attempts": record["attempts"],
            "task_id": record["task_id"],
            "merge_sha": record["merge_sha"],
            "failure": record["failure"],
            "completion": record["completion"],
            "task": record["task_receipt"],
            "finish": record["finish_receipt"],
        }
