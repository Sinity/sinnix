from __future__ import annotations

import hashlib
import json
import os
import secrets
import signal
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from sinnix_lib.ledger import append_jsonl, iter_jsonl
from sinnix_lib.systemd import show_units

from . import pressure as pressure_model
from .agent_jobs import AgentCtlClient, AgentCtlError
from .reducer import now_iso

# Schema of the one-time marker record written to the receipts ledger the
# first time it is created. Its presence (not its content) is what makes
# migration idempotent -- see ActionService._migrate_legacy_receipts.
RECEIPTS_MIGRATION_SCHEMA = "sinnix-ops-action-receipts-migration-v1"

# Properties captured for a receipt's previous_state/resulting_state on unit
# targets -- the target's own live systemd shape, not the
# whole reducer snapshot (see ActionService._target_state).
UNIT_STATE_PROPERTIES = ("LoadState", "ActiveState", "SubState")

# Process targets support only stop -- see sinnix-mble / C3 in the
# 2026-08-18 pressure incident taxonomy. This is the one granularity the
# rest of the API cannot express: a runaway `rg` or `bd list` costs nothing
# to kill. Bounded the same way as everything else here: attested identity,
# admission by cgroup membership, and a receipt rather than a private kill
# path.
PROCESS_ACTIONS = {"stop"}

# A `{"process": {"pid": N, "start_ticks": M}}` target is admitted for
# `stop` only when the live cgroup it currently belongs to is one of these.
# `agent.slice` / `build.slice` are named explicitly (not derived from the
# inventory's ManagedOOMMemoryPressure marker) because an interactive agent
# process is eligible for this bounded action even though agent.slice is
# deliberately left uncapped and unmarked. A shared ceiling would throttle a
# healthy agent behind a busy one, so the slice would not appear in the
# sacrificial set below despite containing processes this verb may reach.
PROCESS_ADMITTED_BASE_SLICES = frozenset({"agent.slice", "build.slice"})

# SIGTERM first, escalate to SIGKILL only if the same process (same
# start_ticks) is still alive after this many seconds. Short and bounded on
# purpose: every command this verb targets (rg, bd, git, ausearch -- the
# C3 cluster) is a short-lived tool invocation with no state to flush, so
# there is no reason to wait as long as systemd's own unit-stop timeouts
# (15-90s). Long enough that a process already exiting on its own is not
# raced into a needless SIGKILL.
PROCESS_STOP_GRACE_SECONDS = 3.0
PROCESS_POLL_INTERVAL_SECONDS = 0.05

# The mutable-property allowlist for `set_policy`/`reset_policy`, in one
# place: validate_request's admission check, the adapter's live-value guard,
# and reset_policy's own restoration list all read this rather than each
# carrying a copy that could drift from the others. The hub's /services/
# page imports it too, so its per-property controls stay honest to exactly
# what the action API will accept.
# A tuple, not a set: reset_policy's `systemctl set-property` assignment
# list is built by iterating this, and a stable order keeps that command
# (and anything logging or testing it) deterministic across runs.
POLICY_PROPERTIES = (
    "MemoryHigh",
    "MemoryMax",
    "MemoryLow",
    "CPUWeight",
    "IOWeight",
    "Nice",
)


def sacrificial_slices(inventory: dict[str, Any] | None) -> set[str]:
    """Slices the runtime inventory itself marks sacrificial: those carrying
    `ManagedOOMMemoryPressure = "kill"` (runtime-defaults.nix's
    background/build/nix-build slices, both the system and user variants).
    Read from the live inventory rather than hardcoded, so a slice's
    admission tracks its own declared policy rather than a second list that
    can drift from it. Module-level and inventory-only (no I/O, no
    ActionError) so /pressure/ can mirror the same boundary the action API
    enforces, the same way `parkable_units` mirrors `park`'s admission,
    without either raising on a missing inventory or duplicating the rule."""
    slices = inventory.get("slices") if isinstance(inventory, dict) else None
    found: set[str] = set()
    if not isinstance(slices, dict):
        return found
    for manager_slices in slices.values():
        if not isinstance(manager_slices, dict):
            continue
        for name, slice_config in manager_slices.items():
            if (
                isinstance(slice_config, dict)
                and slice_config.get("ManagedOOMMemoryPressure") == "kill"
            ):
                found.add(f"{name}.slice")
    return found


def process_admitted_slices(inventory: dict[str, Any] | None) -> set[str]:
    """The full admitted set for a process-stop target: agent.slice and
    build.slice unconditionally, plus whatever the live inventory currently
    marks sacrificial."""
    return PROCESS_ADMITTED_BASE_SLICES | sacrificial_slices(inventory)


ACTION_FIELDS = {
    "action",
    "target",
    "expected_revision",
    "idempotency_key",
    "operator_reason",
    "parameters",
}
ACTIONS = {
    "interrupt",
    "freeze",
    "thaw",
    "reset_policy",
    "set_policy",
    "park",
    "rebuild_override",
    "restart",
    "start",
    "stop",
}

# Lifecycle verbs share one admission gate: the target must be an attested
# runtime-inventory unit that declares observe.restartable. This is what lets
# the web hub drive on-demand AI backends without a second control plane.
LIFECYCLE_ACTIONS = {"restart", "start", "stop"}


class ActionError(ValueError):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _string(value: Any, name: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ActionError(f"{name} must be a non-empty string")
    return value


def validate_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != ACTION_FIELDS:
        raise ActionError("action request has unknown or missing fields")
    action = _string(value["action"], "action", 32)
    if action not in ACTIONS:
        raise ActionError("unknown action")
    target = value["target"]
    if (
        not isinstance(target, dict)
        or not target
        or set(target) - {"job_id", "unit", "process"}
    ):
        raise ActionError("target must contain only job_id, unit, or process")
    if sum(key in target for key in ("job_id", "unit", "process")) != 1:
        raise ActionError(
            "target must identify exactly one job, runtime unit, or process"
        )
    if "process" in target:
        process = target["process"]
        if not isinstance(process, dict) or set(process) != {"pid", "start_ticks"}:
            raise ActionError("process target must contain only pid and start_ticks")
        pid = process["pid"]
        start_ticks = process["start_ticks"]
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 1:
            raise ActionError("process pid must be an integer greater than 1")
        if (
            isinstance(start_ticks, bool)
            or not isinstance(start_ticks, int)
            or start_ticks < 0
        ):
            raise ActionError("process start_ticks must be a non-negative integer")
        target = {"process": {"pid": pid, "start_ticks": start_ticks}}
    else:
        target = {key: _string(item, key, 256) for key, item in target.items()}
    if "process" in target and action not in PROCESS_ACTIONS:
        raise ActionError("process targets only support stop")
    expected = value["expected_revision"]
    if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
        raise ActionError("expected_revision must be a non-negative integer")
    key = _string(value["idempotency_key"], "idempotency_key", 128)
    reason = _string(value["operator_reason"], "operator_reason", 512)
    parameters = value["parameters"]
    if not isinstance(parameters, dict):
        raise ActionError("parameters must be an object")
    if "job_id" in target and action != "interrupt":
        raise ActionError("job targets only support interrupt")
    if action == "interrupt" and "job_id" not in target:
        raise ActionError("interrupt requires a job target")
    if (
        action in {"set_policy", "reset_policy", "park", "thaw"}
        and "unit" not in target
    ):
        raise ActionError(f"{action} requires a runtime unit target")
    if action == "set_policy":
        if set(parameters) != {"property", "value"}:
            raise ActionError("set_policy requires property and value")
        _string(parameters["property"], "property", 32)
        _string(parameters["value"], "value", 64)
        if parameters["property"] not in POLICY_PROPERTIES:
            raise ActionError("unsupported runtime policy property")
    if action == "interrupt" and parameters:
        raise ActionError("interrupt accepts no parameters")
    if action == "park":
        if set(parameters) != {"deadline_seconds"}:
            raise ActionError("park requires deadline_seconds")
        deadline = parameters["deadline_seconds"]
        if (
            isinstance(deadline, bool)
            or not isinstance(deadline, int)
            or not 1 <= deadline <= 86400
        ):
            raise ActionError("deadline_seconds must be between 1 and 86400")
    if action in {"reset_policy", "thaw", "start", "stop"} and parameters:
        raise ActionError(f"{action} does not accept parameters")
    if action == "rebuild_override":
        if set(parameters) != {"name", "value"}:
            raise ActionError("rebuild_override requires name and value")
        if parameters["name"] not in {"max_jobs", "cores", "eval_cache"}:
            raise ActionError("unsupported rebuild override")
        _string(parameters["value"], "value", 32)
    return {
        "action": action,
        "target": target,
        "expected_revision": expected,
        "idempotency_key": key,
        "operator_reason": reason,
        "parameters": parameters,
    }


class ActionService:
    def __init__(
        self,
        snapshot: Callable[[], dict[str, Any]],
        inventory_path: Path,
        receipts_path: Path,
        adapter: (
            Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None
        ) = None,
        agent_jobs: AgentCtlClient | None = None,
        unit_state_prober: Callable[[str, str], dict[str, str]] | None = None,
        process_prober: (Callable[[int], tuple[int, str, str] | None] | None) = None,
        self_pid: int | None = None,
        process_stop_grace_seconds: float = PROCESS_STOP_GRACE_SECONDS,
        signaler: Callable[[int, int], None] = os.kill,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.snapshot = snapshot
        self.inventory_path = inventory_path
        # The retired whole-file dict: left in place untouched, read once by
        # the migration and never written again.
        self.receipts_path = receipts_path
        # The store of record: append-only, same directory and stem as
        # receipts_path, ".jsonl" instead of ".json" (see
        # state.StateLayer.receipts_ledger_path, which this mirrors so a
        # caller that only has receipts_path -- every existing one -- still
        # gets the right ledger file without threading a second parameter
        # through cli.py).
        self.receipts_ledger_path = receipts_path.with_name(
            receipts_path.stem + ".jsonl"
        )
        self.adapter = adapter or self._live_adapter
        self.agent_jobs = agent_jobs or AgentCtlClient()
        self.unit_state_prober = unit_state_prober or self._live_unit_state_prober
        self.process_prober = process_prober or self._live_process_prober
        # os.getpid() at construction time, not per-call: the reducer's own
        # pid never changes for the life of the process, and evaluating it
        # once here is what lets a test override it without patching os.
        self.self_pid = self_pid if self_pid is not None else os.getpid()
        self.process_stop_grace_seconds = process_stop_grace_seconds
        self.signaler = signaler
        self.sleeper = sleeper
        self.clock = clock
        self.receipts: dict[str, dict[str, Any]] = self._load_receipts()

    def _migrate_legacy_receipts(self) -> None:
        """Fold the old whole-file receipts dict into the ledger once.

        The ledger's mere existence is the marker: a first start with no
        ledger yet creates one, writing a migration record even when there
        was nothing to fold (so the marker itself proves this ran and is not
        inferred from row count), and every later start sees the ledger
        already there and does nothing. ``receipts_path`` is read here and
        never touched again -- no deletion, no rewrite.
        """
        if self.receipts_ledger_path.exists():
            return
        try:
            legacy = json.loads(self.receipts_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            legacy = None
        folded = legacy if isinstance(legacy, dict) else {}
        append_jsonl(
            self.receipts_ledger_path,
            {
                "schema": RECEIPTS_MIGRATION_SCHEMA,
                "migrated_from": str(self.receipts_path),
                "count": len(folded),
                "migrated_at": now_iso(),
            },
        )
        for record in folded.values():
            if isinstance(record, dict):
                append_jsonl(self.receipts_ledger_path, record)

    def _load_receipts(self) -> dict[str, dict[str, Any]]:
        self._migrate_legacy_receipts()
        receipts: dict[str, dict[str, Any]] = {}
        for record in iter_jsonl(self.receipts_ledger_path):
            if not isinstance(record, dict):
                continue
            if record.get("schema") == RECEIPTS_MIGRATION_SCHEMA:
                continue
            key = record.get("idempotency_key")
            if isinstance(key, str):
                # Last write wins on replay -- a key is in practice written
                # exactly once (execute() short-circuits on a prior receipt),
                # so this is a no-op today and a correctness net if that ever
                # changes.
                receipts[key] = record
        return receipts

    def _inventory(self) -> dict[str, Any]:
        try:
            value = json.loads(self.inventory_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ActionError(f"runtime inventory unavailable: {error}", 503) from error
        if (
            not isinstance(value, dict)
            or value.get("schema") != "sinnix-runtime-inventory-v1"
        ):
            raise ActionError("runtime inventory is not attested", 503)
        return value

    def _resolve(
        self, request: dict[str, Any], snapshot: dict[str, Any]
    ) -> dict[str, Any]:
        target = request["target"]
        if "job_id" in target:
            try:
                job = self.agent_jobs.get(target["job_id"])
            except AgentCtlError as error:
                raise ActionError(f"agentctl job lookup failed: {error}", 503) from error
            if job.get("terminal") is True:
                raise ActionError("job is already terminal", 409)
            return {"kind": "job", "job": self._job_state(job)}
        if "process" in target:
            process = target["process"]
            return self._resolve_process(process["pid"], process["start_ticks"])
        surfaces = self._inventory().get("surfaces", {})
        surface = surfaces.get(target["unit"])
        if not isinstance(surface, dict):
            surface = next(
                (
                    candidate
                    for candidate in surfaces.values()
                    if isinstance(candidate, dict)
                    and candidate.get("unit") == target["unit"]
                ),
                None,
            )
        if not isinstance(surface, dict):
            raise ActionError("runtime unit is not in the inventory", 403)
        if request["action"] in LIFECYCLE_ACTIONS and not surface.get(
            "observe", {}
        ).get("restartable", False):
            raise ActionError("runtime unit is not restartable", 403)
        return {"kind": "unit", "surface": surface}

    def _live_unit_state_prober(self, unit: str, manager: str) -> dict[str, str]:
        return show_units(
            [unit], user=(manager == "user"), properties=UNIT_STATE_PROPERTIES
        ).get(unit, {})

    def _resolve_process(self, pid: int, start_ticks: int) -> dict[str, Any]:
        """Admit a `{pid, start_ticks}` process target: live identity AND
        cgroup membership, not either alone.

        Identity is verified against /proc/<pid>/stat field 22 (starttime)
        at execution time, not at request-construction time -- the caller
        quoted it off a hog-table row that may be arbitrarily stale, and a
        mismatch means the pid has been reused by an unrelated process
        (refused, never silently retargeted).

        Admission is by live cgroup membership, not by process name or
        command-line heuristics: a name list is not a containment boundary
        (the taxonomy this verb was designed against is explicit about
        that). Only `agent.slice` / `build.slice` and slices the inventory
        itself marks sacrificial admit a stop. A process with no slice segment at
        all (a PID 1 direct child, e.g. `init.scope`) falls out of this
        check the same way anything else outside the admitted set does --
        there is no separate PID 1 special case to maintain."""
        live = self.process_prober(pid)
        if live is None:
            raise ActionError("process does not exist", 404)
        live_start_ticks, unit, slice_unit = live
        if live_start_ticks != start_ticks:
            raise ActionError(
                "process identity mismatch: start_ticks does not match "
                "/proc/<pid>/stat -- the pid has been reused by a different "
                "process since it was observed",
                409,
            )
        if pid == self.self_pid:
            raise ActionError("the reducer may not target its own process", 403)
        admitted = process_admitted_slices(self._inventory())
        if slice_unit not in admitted:
            raise ActionError(
                "process is not in an admitted cgroup (must be agent.slice, "
                "build.slice, or a slice the runtime inventory marks "
                f"sacrificial; this process is in {slice_unit or '(no slice)'})",
                403,
            )
        return {
            "kind": "process",
            "pid": pid,
            "start_ticks": start_ticks,
            "unit": unit,
            "slice_unit": slice_unit,
        }

    def _live_process_prober(self, pid: int) -> tuple[int, str, str] | None:
        """(start_ticks, unit, slice_unit) read straight from /proc, or None
        if the pid does not currently exist. Reuses pressure.py's own
        starttime-field parsing and cgroup parsing so the two places that
        read a process's identity off this host agree by construction."""
        directory = pressure_model.PROC / str(pid)
        try:
            stat_text = (directory / "stat").read_text(encoding="utf-8")
        except OSError:
            return None
        # comm sits in parentheses and may itself contain spaces or
        # parentheses: split after the last ")", matching pressure.py's
        # _start_ticks and the /proc/pid/stat(5) field layout it relies on.
        tail = stat_text.rpartition(")")[2].split()
        try:
            start_ticks = int(tail[19])
        except (IndexError, ValueError):
            return None
        try:
            cgroup_text = (directory / "cgroup").read_text(encoding="utf-8")
        except OSError:
            cgroup_text = ""
        _unit, slice_unit = pressure_model.parse_cgroup(cgroup_text)
        return start_ticks, _unit, slice_unit

    def _stop_process(self, resolved: dict[str, Any]) -> dict[str, Any]:
        """SIGTERM, then SIGKILL only if the same identity (pid AND
        start_ticks) is still alive after `process_stop_grace_seconds`. Hand
        rolled rather than shelling out to `systemctl stop` because a bare
        pid is not a systemd unit -- there is
        nothing for systemctl to target. Re-checks identity on every poll,
        not just liveness, so a pid that exits and is immediately reused by
        an unrelated process during the grace window is never mistaken for
        "still needs killing"."""
        pid = resolved["pid"]
        start_ticks = resolved["start_ticks"]

        def alive() -> bool:
            live = self.process_prober(pid)
            return live is not None and live[0] == start_ticks

        try:
            self.signaler(pid, signal.SIGTERM)
        except ProcessLookupError:
            return {
                "name": "stop",
                "status": "accepted",
                "signal": "none",
                "reason": "process had already exited",
            }
        except OSError as error:
            raise ActionError(f"SIGTERM failed: {error}", 502) from error

        deadline = self.clock() + self.process_stop_grace_seconds
        while self.clock() < deadline:
            if not alive():
                return {
                    "name": "stop",
                    "status": "accepted",
                    "signal": "SIGTERM",
                    "grace_seconds": self.process_stop_grace_seconds,
                }
            self.sleeper(PROCESS_POLL_INTERVAL_SECONDS)

        if not alive():
            return {
                "name": "stop",
                "status": "accepted",
                "signal": "SIGTERM",
                "grace_seconds": self.process_stop_grace_seconds,
            }
        try:
            self.signaler(pid, signal.SIGKILL)
        except ProcessLookupError:
            return {
                "name": "stop",
                "status": "accepted",
                "signal": "SIGTERM",
                "grace_seconds": self.process_stop_grace_seconds,
            }
        except OSError as error:
            raise ActionError(f"SIGKILL failed: {error}", 502) from error
        return {
            "name": "stop",
            "status": "accepted",
            "signal": "SIGKILL",
            "grace_seconds": self.process_stop_grace_seconds,
        }

    def _target_state(self, resolved: dict[str, Any]) -> dict[str, Any]:
        """The resolved target's OWN prior/current state, not the whole
        reducer snapshot -- a prior receipt used to embed 25KB+ of
        unrelated agent-gateway job histories and per-process IO because
        previous_state/resulting_state copied `snapshot["state"]` wholesale
        (sinnix-rd69). The full snapshot stays reachable by its sequence
        number, recorded separately in `preconditions.revision`."""
        kind = resolved.get("kind")
        if kind == "job":
            return {"kind": "job", "job": self._job_state(resolved.get("job"))}
        if kind == "unit":
            surface = resolved.get("surface") or {}
            unit = surface.get("unit")
            manager = surface.get("manager", "system")
            return {
                "kind": "unit",
                "surface": surface,
                "systemd": self.unit_state_prober(unit, manager) if unit else {},
            }
        if kind == "process":
            pid = resolved.get("pid")
            start_ticks = resolved.get("start_ticks")
            live = self.process_prober(pid) if pid is not None else None
            return {
                "kind": "process",
                "pid": pid,
                "start_ticks": start_ticks,
                "unit": resolved.get("unit"),
                "slice_unit": resolved.get("slice_unit"),
                "alive": live is not None and live[0] == start_ticks,
            }
        return {"kind": kind}

    @staticmethod
    def _job_state(job: Any) -> dict[str, Any]:
        """The job row as agentctl prints it, bounded to the fields a receipt reads."""
        if not isinstance(job, dict):
            return {}
        return {
            key: job.get(key)
            for key in (
                "job_id",
                "label",
                "kind",
                "project",
                "operation",
                "group",
                "phase",
                "terminal",
                "exit_code",
                "path",
                "started_at",
                "ended_at",
            )
            if key in job
        }

    def execute(self, raw: Any) -> dict[str, Any]:
        request = validate_request(raw)
        digest = hashlib.sha256(
            json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        prior = self.receipts.get(request["idempotency_key"])
        if prior is not None:
            if prior.get("request_hash") != digest:
                raise ActionError(
                    "idempotency key is already bound to another request", 409
                )
            return prior
        try:
            snapshot = self.snapshot()
            if request["expected_revision"] != snapshot.get("sequence"):
                raise ActionError("expected_revision is stale", 409)
            resolved = self._resolve(request, snapshot)
            previous_target_state = self._target_state(resolved)
            adapter_receipt = self.adapter(request, resolved)
        except ActionError as error:
            rejected = {
                "schema": "sinnix-ops-action-v1",
                "receipt_id": str(uuid.uuid4()),
                "idempotency_key": request["idempotency_key"],
                "request_hash": digest,
                "action": request["action"],
                "target": request["target"],
                "operator_reason": request["operator_reason"],
                "expected_revision": request["expected_revision"],
                "status": "rejected",
                "error": str(error),
                "created_at": now_iso(),
            }
            self.receipts[request["idempotency_key"]] = rejected
            append_jsonl(self.receipts_ledger_path, rejected)
            raise
        receipt = {
            "schema": "sinnix-ops-action-v1",
            "receipt_id": str(uuid.uuid4()),
            "idempotency_key": request["idempotency_key"],
            "request_hash": digest,
            "action": request["action"],
            "target": request["target"],
            "operator_reason": request["operator_reason"],
            "expected_revision": request["expected_revision"],
            "preconditions": {
                "revision": snapshot.get("sequence"),
                "resolved": resolved,
            },
            "previous_state": previous_target_state,
            # Re-probed after the adapter ran: for unit targets the systemctl
            # state the action produced; for a job the row agentctl returned
            # from the cancel.
            "resulting_state": (
                {"kind": "job", "job": self._job_state(adapter_receipt.get("job"))}
                if resolved.get("kind") == "job" and isinstance(adapter_receipt, dict)
                else self._target_state(resolved)
            ),
            "adapter": adapter_receipt,
            "created_at": now_iso(),
        }
        self.receipts[request["idempotency_key"]] = receipt
        append_jsonl(self.receipts_ledger_path, receipt)
        return receipt

    def lookup(self, key: str) -> dict[str, Any] | None:
        return self.receipts.get(key)

    def _live_adapter(
        self, request: dict[str, Any], resolved: dict[str, Any]
    ) -> dict[str, Any]:
        action = request["action"]
        if action == "interrupt":
            job_id = resolved["job"]["job_id"]
            try:
                return {"name": action, "job": self.agent_jobs.cancel(job_id)}
            except AgentCtlError as error:
                raise ActionError(f"agentctl cancel failed: {error}", 503) from error
        elif resolved.get("kind") == "process":
            # Not a systemd unit -- there is nothing for systemctl to
            # target, so this is the one adapter branch that does not shell
            # out to a command list below.
            return self._stop_process(resolved)
        elif action in LIFECYCLE_ACTIONS:
            surface = resolved["surface"]
            manager = surface["manager"]
            command = [
                "systemctl",
                "--user" if manager == "user" else "--system",
                action,
                surface["unit"],
            ]
        elif action in {"freeze", "thaw"}:
            command = [
                "sinnix-pressure-park",
                action,
                "--",
                resolved["surface"]["unit"],
            ]
        elif action == "park":
            surface = resolved["surface"]
            unit = surface["unit"]
            suffix = hashlib.sha256(unit.encode()).hexdigest()[:16]
            manager = surface["manager"]
            prefix = ["systemd-run", "--quiet", "--collect"]
            if manager == "user":
                prefix.insert(1, "--user")
            command = [
                *prefix,
                f"--unit=sinnix-ops-thaw-{suffix}",
                f"--on-active={request['parameters']['deadline_seconds']}",
                "sinnix-pressure-park",
                "thaw",
                "--",
                unit,
            ]
            subprocess.run(
                ["sinnix-pressure-park", "freeze", "--", unit],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
        elif action == "set_policy":
            surface = resolved["surface"]
            property_name = request["parameters"]["property"]
            value = request["parameters"]["value"]
            if property_name not in POLICY_PROPERTIES:
                raise ActionError("unsupported runtime policy property", 403)
            declared = surface.get("effectiveResources", {})
            if property_name not in declared:
                raise ActionError(
                    "property is not declared by the runtime inventory", 403
                )
            manager = surface["manager"]
            command = [
                "systemctl",
                "--user" if manager == "user" else "--system",
                "set-property",
                surface["unit"],
                f"{property_name}={value}",
            ]
        elif action == "rebuild_override":
            command = [
                "sinnix-rebuild-override",
                "put",
                "--name",
                request["parameters"]["name"],
                "--value",
                request["parameters"]["value"],
            ]
        elif action == "reset_policy":
            surface = resolved["surface"]
            manager = surface["manager"]
            properties = surface.get("effectiveResources", {})
            assignments = [
                f"{key}={properties[key]}"
                for key in POLICY_PROPERTIES
                if properties.get(key) not in (None, "")
            ]
            if not assignments:
                return {
                    "name": action,
                    "status": "noop",
                    "reason": "inventory has no mutable policy fields",
                }
            command = [
                "systemctl",
                "--user" if manager == "user" else "--system",
                "set-property",
                surface["unit"],
                *assignments,
            ]
        else:
            return {
                "name": action,
                "status": "accepted",
                "receipt": secrets.token_hex(8),
            }
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=10, check=False
        )
        if result.returncode != 0:
            raise ActionError(
                f"bounded adapter failed: {result.stderr.strip()[:200]}", 502
            )
        return {
            "name": action,
            "status": "accepted",
            "exit_status": result.returncode,
            "stdout": result.stdout[:1000],
        }
