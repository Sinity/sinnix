from __future__ import annotations

import hashlib
import json
import re
import secrets
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable

from sinnix_lib.ledger import append_jsonl, iter_jsonl
from sinnix_lib.systemd import show_units

from .reducer import now_iso

# Schema of the one-time marker record written to the receipts ledger the
# first time it is created. Its presence (not its content) is what makes
# migration idempotent -- see ActionService._migrate_legacy_receipts.
RECEIPTS_MIGRATION_SCHEMA = "sinnix-ops-action-receipts-migration-v1"

# Properties captured for a receipt's previous_state/resulting_state on
# unit and scope targets -- the target's own live systemd shape, not the
# whole reducer snapshot (see ActionService._target_state).
UNIT_STATE_PROPERTIES = ("LoadState", "ActiveState", "SubState")

# Ad-hoc `sinnix-scope` transient scopes (build.slice/agent.slice/etc placements
# created by the generated sinnix-scope launcher (flake/launch.nix), distinct
# from attested agent-gateway jobs
# which use the `sinnix-agent-job-<id>.scope` namespace and the job_id target
# instead). Admission for these is structural, not inventory-registered: the
# name must match the launcher's own naming convention
# (`sinnix-<commandClass>-<timestamp>-<pid>.scope`) AND the unit must resolve
# live via systemctl (see _resolve_scope) -- name-matching alone is not trust,
# a dead or renamed unit is rejected too.
# The launcher names transient scopes
# sinnix-<class>-<identity>-<epoch_ns>-<pid>.scope, where <identity> is the
# launched command's own name, sanitized to [A-Za-z0-9_.-] and capped at 40
# chars (flake/launch/scope-runtime.bash). The identity segment arrived
# 2026-08-13 (sinnix-1ei); this pattern lagged without it and admitted
# nothing for five days -- every live stop-scope action 403'd on name shape.
SCOPE_UNIT_PATTERN = re.compile(
    r"^sinnix-(agent|build|background|gpu-runtime|nix-build|system)"
    r"-[A-Za-z0-9_.-]{1,40}-\d+-\d+\.scope$"
)

# Scope targets support only the reversible verb: `systemctl stop` on a scope
# sends SIGTERM and escalates to SIGKILL on its own timeout, so no explicit
# kill/escalate verb exists here.
SCOPE_ACTIONS = {"stop"}


def focus_registered_session(job: dict[str, Any]) -> dict[str, Any]:
    """Verify Kitty and Hyprland identities before focusing the registered target."""

    correlation = job.get("correlation")
    if not isinstance(correlation, dict):
        raise ActionError("job has no registered terminal target", 409)
    socket_path = correlation.get("kitty_socket")
    kitty_window_id = correlation.get("kitty_window_id")
    hyprland_address = correlation.get("hyprland_address")
    if not all(
        isinstance(value, str) and value
        for value in (socket_path, kitty_window_id, hyprland_address)
    ):
        raise ActionError("job terminal target is incomplete", 409)

    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=5, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ActionError(
                f"focus verification unavailable: {type(error).__name__}", 503
            ) from error
        if result.returncode != 0:
            raise ActionError("focus target verification failed", 409)
        return result

    endpoint = f"unix:{socket_path}"
    try:
        kitty_windows = json.loads(run(["kitty", "@", "--to", endpoint, "ls"]).stdout)
    except (json.JSONDecodeError, TypeError) as error:
        raise ActionError("Kitty target inventory is malformed", 409) from error
    matches = [
        window
        for os_window in kitty_windows
        if isinstance(kitty_windows, list)
        for tab in os_window.get("tabs", [])
        if isinstance(os_window, dict)
        for window in tab.get("windows", [])
        if isinstance(tab, dict)
        if str(window.get("id")) == kitty_window_id
    ]
    if len(matches) != 1:
        raise ActionError("registered Kitty window is not unique", 409)
    run(
        [
            "kitty",
            "@",
            "--to",
            endpoint,
            "focus-window",
            "--match",
            f"id:{kitty_window_id}",
        ]
    )
    run(["hyprctl", "dispatch", "focuswindow", f"address:{hyprland_address}"])
    try:
        active = json.loads(run(["hyprctl", "-j", "activewindow"]).stdout)
    except (json.JSONDecodeError, TypeError) as error:
        raise ActionError("Hyprland focus verification is malformed", 409) from error
    if str(active.get("address")) != hyprland_address:
        raise ActionError("Hyprland focused window does not match registration", 409)
    return {
        "target": {
            "kitty_window_id": kitty_window_id,
            "hyprland_address": hyprland_address,
        },
        "status": "verified",
    }


ACTION_FIELDS = {
    "action",
    "target",
    "expected_revision",
    "idempotency_key",
    "operator_reason",
    "parameters",
}
ACTIONS = {
    "focus",
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
        or set(target) - {"job_id", "unit", "scope"}
    ):
        raise ActionError("target must contain only job_id, unit, or scope")
    if sum(key in target for key in ("job_id", "unit", "scope")) != 1:
        raise ActionError(
            "target must identify exactly one attested job, runtime unit, or scope"
        )
    target = {key: _string(item, key, 256) for key, item in target.items()}
    expected = value["expected_revision"]
    if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
        raise ActionError("expected_revision must be a non-negative integer")
    key = _string(value["idempotency_key"], "idempotency_key", 128)
    reason = _string(value["operator_reason"], "operator_reason", 512)
    parameters = value["parameters"]
    if not isinstance(parameters, dict):
        raise ActionError("parameters must be an object")
    if "job_id" in target and action not in {"focus", "interrupt"}:
        raise ActionError("job targets only support focus and interrupt")
    if "scope" in target and action not in SCOPE_ACTIONS:
        raise ActionError("scope targets only support stop")
    if action == "focus" and "unit" in target:
        raise ActionError("focus requires an attested job target")
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
        if parameters["property"] not in {
            "MemoryHigh",
            "MemoryMax",
            "MemoryLow",
            "CPUWeight",
            "IOWeight",
            "Nice",
        }:
            raise ActionError("unsupported runtime policy property")
    if action == "interrupt":
        if set(parameters) - {"orphan_reap"}:
            raise ActionError("interrupt accepts only orphan_reap")
        if "orphan_reap" in parameters and not isinstance(
            parameters["orphan_reap"], bool
        ):
            raise ActionError("orphan_reap must be boolean")
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
        controller: str = "agent_job_control.sh",
        scope_prober: Callable[[str], str | None] | None = None,
        unit_state_prober: Callable[[str, str], dict[str, str]] | None = None,
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
        self.controller = controller
        self.scope_prober = scope_prober or self._live_scope_prober
        self.unit_state_prober = unit_state_prober or self._live_unit_state_prober
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
            state = snapshot.get("state") or {}
            gateway = state.get("agent_gateway") if isinstance(state, dict) else None
            jobs = (
                gateway.get("jobs", [])
                if isinstance(gateway, dict)
                else state.get("jobs", [])
            )
            job = next(
                (item for item in jobs if item.get("job_id") == target["job_id"]), None
            )
            attested = (
                isinstance(job, dict)
                and all(
                    isinstance(job.get(field), value_type) and bool(job.get(field))
                    for field, value_type in (
                        ("job_id", str),
                        ("schema_version", int),
                        ("launcher", dict),
                        ("worktree", str),
                    )
                )
                and job.get("schema_version") in {2, 3}
                and all(
                    isinstance(job["launcher"].get(field), value_type)
                    and bool(job["launcher"].get(field))
                    for field, value_type in (
                        ("pid", int),
                        ("proc_start", str),
                        ("scope_unit", str),
                        ("cgroup", str),
                    )
                )
            )
            if not attested:
                raise ActionError("job target is unknown or unattested", 403)
            orphan = next(
                (
                    row
                    for row in (
                        state.get("agent_gateway", {}).get("orphaned_jobs", [])
                        if isinstance(state.get("agent_gateway"), dict)
                        else []
                    )
                    if isinstance(row, dict) and row.get("job_id") == target["job_id"]
                ),
                None,
            )
            return {"kind": "job", "job": job, "orphan": orphan}
        if "scope" in target:
            return self._resolve_scope(target["scope"])
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

    def _resolve_scope(self, unit: str) -> dict[str, Any]:
        """Admit a sinnix-scope transient unit: name-shape AND live-state, not
        either alone. A name match on a unit that has already exited (or never
        existed) is exactly the stale-target case expected_revision plus this
        check must both reject."""
        if not SCOPE_UNIT_PATTERN.match(unit):
            raise ActionError(
                "scope target does not match a sinnix-placed transient scope name",
                403,
            )
        manager = self.scope_prober(unit)
        if manager is None:
            raise ActionError("scope unit is not a live sinnix-placed scope", 403)
        return {"kind": "scope", "unit": unit, "manager": manager}

    def _live_scope_prober(self, unit: str) -> str | None:
        for manager in ("user", "system"):
            command = ["systemctl"]
            if manager == "user":
                command.append("--user")
            command += ["show", unit, "--property=LoadState,ActiveState"]
            try:
                result = subprocess.run(
                    command, capture_output=True, text=True, timeout=5, check=False
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                raise ActionError(
                    f"scope verification unavailable: {type(error).__name__}", 503
                ) from error
            if result.returncode != 0:
                continue
            properties = dict(
                line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
            )
            if properties.get("LoadState") == "loaded" and properties.get(
                "ActiveState"
            ) in {"active", "activating"}:
                return manager
        return None

    def _live_unit_state_prober(self, unit: str, manager: str) -> dict[str, str]:
        return show_units(
            [unit], user=(manager == "user"), properties=UNIT_STATE_PROPERTIES
        ).get(unit, {})

    def _target_state(self, resolved: dict[str, Any]) -> dict[str, Any]:
        """The resolved target's OWN prior/current state, not the whole
        reducer snapshot -- a stop-scope receipt used to embed 25KB+ of
        unrelated agent-gateway job histories and per-process IO because
        previous_state/resulting_state copied `snapshot["state"]` wholesale
        (sinnix-rd69). The full snapshot stays reachable by its sequence
        number, recorded separately in `preconditions.revision`."""
        kind = resolved.get("kind")
        if kind == "job":
            return {"kind": "job", "job": resolved.get("job")}
        if kind == "scope":
            unit = resolved.get("unit")
            manager = resolved.get("manager", "system")
            return {
                "kind": "scope",
                "unit": unit,
                "manager": manager,
                "systemd": self.unit_state_prober(unit, manager) if unit else {},
            }
        if kind == "unit":
            surface = resolved.get("surface") or {}
            unit = surface.get("unit")
            manager = surface.get("manager", "system")
            return {
                "kind": "unit",
                "surface": surface,
                "systemd": self.unit_state_prober(unit, manager) if unit else {},
            }
        return {"kind": kind}

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
            if request["action"] == "interrupt" and request["parameters"].get(
                "orphan_reap"
            ):
                orphan = resolved.get("orphan")
                policy = orphan.get("policy") if isinstance(orphan, dict) else None
                if (
                    not isinstance(policy, dict)
                    or policy.get("proposed_action") != "reap"
                ):
                    raise ActionError(
                        "orphan reap requires two identical cold expendable observations",
                        409,
                    )
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
            # Re-probed after the adapter ran, not the same pre-action copy:
            # for unit/scope targets this reflects the systemctl state the
            # action actually produced. Job targets have no post-action
            # re-snapshot source, so this stays identical to previous_state
            # for those (unchanged from prior behavior).
            "resulting_state": self._target_state(resolved),
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
        if action == "focus":
            return {"name": action, **focus_registered_session(resolved["job"])}
        if action == "interrupt":
            job_id = resolved["job"]["job_id"]
            command = [self.controller, "interrupt", "--job", job_id]
        elif resolved.get("kind") == "scope":
            # stop, not kill: systemctl stop on a scope sends SIGTERM to every
            # process in it and escalates to SIGKILL on its own timeout, which
            # is the reversible-first semantics this action wants.
            command = [
                "systemctl",
                "--user" if resolved["manager"] == "user" else "--system",
                "stop",
                resolved["unit"],
            ]
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
            allowed = {
                "MemoryHigh",
                "MemoryMax",
                "MemoryLow",
                "CPUWeight",
                "IOWeight",
                "Nice",
            }
            if property_name not in allowed:
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
            allowed = (
                "MemoryHigh",
                "MemoryMax",
                "MemoryLow",
                "CPUWeight",
                "IOWeight",
                "Nice",
            )
            assignments = [
                f"{key}={properties[key]}"
                for key in allowed
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
