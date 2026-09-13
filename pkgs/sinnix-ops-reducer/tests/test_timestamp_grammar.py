"""One UTC grammar across the records this package writes and joins.

The health ledger, the reducer snapshot, the action receipts and orient are
read together -- a lane's transition is matched against the snapshot revision
that observed it, and a receipt against the snapshot it was admitted from.
While the health ledger stamped seconds and everything else stamped
microseconds, joining this package's own records meant handling two grammars.
Every producer here emits ``%Y-%m-%dT%H:%M:%SZ``.

The sentinel tests are what make that structural rather than coincidental: a
producer that goes back to a local ``datetime.now(...)`` spelling never sees
the patched helper, whatever string it happens to format.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sinnix_ops_reducer import actions as actions_module
from sinnix_ops_reducer import health, orient
from sinnix_ops_reducer import reducer as reducer_module
from sinnix_ops_reducer.actions import ActionService
from sinnix_ops_reducer.reducer import Reducer

UTC_TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
SENTINEL = "1999-12-31T23:59:58Z"

INVENTORY = {
    "schema": "sinnix-runtime-inventory-v1",
    "surfaces": {
        "safe": {
            "unit": "safe.service",
            "manager": "system",
            "observe": {"restartable": True},
        }
    },
}


def _inventory(path: Path) -> Path:
    path.write_text(json.dumps(INVENTORY))
    return path


def _action_service(tmp_path: Path, reducer: Reducer) -> ActionService:
    return ActionService(
        reducer.snapshot,
        _inventory(tmp_path / "inventory.json"),
        tmp_path / "receipts.json",
        adapter=lambda request, resolved: {"name": request["action"], "status": "fake"},
        unit_state_prober=lambda unit, manager: {
            "ActiveState": "active",
            "SubState": "running",
            "LoadState": "loaded",
            "InvocationID": "fixture",
            "FreezerState": "running",
        },
    )


def _request(key: str) -> dict[str, Any]:
    return {
        "action": "freeze",
        "target": {"unit": "safe"},
        "expected_target": {
            "kind": "unit",
            "unit": "safe.service",
            "manager": "system",
            "properties": {
                "ActiveState": "active",
                "SubState": "running",
                "LoadState": "loaded",
                "InvocationID": "fixture",
                "FreezerState": "running",
            },
        },
        "idempotency_key": key,
        "operator_reason": "timestamp grammar fixture",
        "parameters": {},
    }


def _transition(tmp_path: Path) -> dict[str, Any]:
    ledger = tmp_path / "health-transitions.jsonl"
    health.emit_failure(
        "safe",
        "exit-code",
        INVENTORY,
        health.Emitter(tmp_path / "health-state.json", ledger, lambda *_: None),
    )
    return json.loads(ledger.read_text().splitlines()[0])


def test_every_record_this_package_joins_carries_one_utc_grammar(
    tmp_path: Path,
) -> None:
    reducer = Reducer(
        tmp_path / "status.json",
        tmp_path / "token",
        lambda: {},
        tmp_path / "reducer.json",
    )
    snapshot = reducer.refresh()
    actions = _action_service(tmp_path, reducer)
    receipt = actions.execute(_request("grammar-1"))
    ledger_records = [
        json.loads(line)
        for line in (tmp_path / "receipts.jsonl").read_text().splitlines()
    ]
    migration = next(
        record
        for record in ledger_records
        if record.get("schema") == actions_module.RECEIPTS_MIGRATION_SCHEMA
    )

    stamps = {
        "health transition ts": _transition(tmp_path)["ts"],
        "snapshot observed_at": snapshot["observed_at"],
        "snapshot source observed_at": snapshot["sources"]["sinnix-observe"][
            "observed_at"
        ],
        "reducer health observed_at": reducer.health()["observed_at"],
        "receipts migration migrated_at": migration["migrated_at"],
        "action receipt created_at": receipt["created_at"],
    }
    off_grammar = {
        name: value for name, value in stamps.items() if not UTC_TS.fullmatch(value)
    }
    assert off_grammar == {}


def test_orient_stamps_the_same_grammar(tmp_path: Path) -> None:
    generated = orient.compose(
        socket_path=tmp_path / "absent.sock",
        static_inventory_path=tmp_path / "absent.json",
        fetch=lambda _socket, _route: None,
        read_static=lambda _path: None,
        bd_head=lambda: {"available": False},
        steering_head=lambda: {"available": False},
    )["generated_at"]
    assert UTC_TS.fullmatch(generated)


def test_reducer_stamps_through_the_shared_helper(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(reducer_module, "utc_ts", lambda: SENTINEL)
    reducer = Reducer(
        tmp_path / "status.json",
        tmp_path / "token",
        lambda: {},
        tmp_path / "reducer.json",
    )
    assert reducer.refresh()["observed_at"] == SENTINEL
    assert reducer.health()["observed_at"] == SENTINEL


def test_action_receipts_stamp_through_the_shared_helper(
    tmp_path: Path, monkeypatch
) -> None:
    reducer = Reducer(
        tmp_path / "status.json",
        tmp_path / "token",
        lambda: {},
        tmp_path / "reducer.json",
    )
    reducer.refresh()
    monkeypatch.setattr(actions_module, "utc_ts", lambda: SENTINEL)
    receipt = _action_service(tmp_path, reducer).execute(_request("grammar-2"))
    assert receipt["created_at"] == SENTINEL


def test_health_transitions_stamp_through_the_shared_helper(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(health, "utc_ts", lambda: SENTINEL)
    assert _transition(tmp_path)["ts"] == SENTINEL
