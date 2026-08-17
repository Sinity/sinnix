"""`sinnix-ops-reducer emit-failure`: what systemd's OnFailure= actually runs.

Both halves matter. The socket path is the normal one and is what keeps a
single process owning the dedup state; the fallback is what stops a failure
from being lost precisely when the recorder is the thing that failed.
"""

from __future__ import annotations

import json
import socketserver
import threading
from pathlib import Path
from typing import Any

import pytest

from sinnix_ops_reducer import cli, health
from sinnix_ops_reducer.reducer import Reducer
from sinnix_ops_reducer.server import Handler

INVENTORY: dict[str, Any] = {
    "schema": "sinnix-runtime-inventory-v1",
    "observedServices": [
        {"kind": "service", "manager": "user", "unit": "usersurf.service"},
    ],
}


class UnixHTTPServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True

    def get_request(self):
        connection, _ = super().get_request()
        return connection, ("unix", 0)


@pytest.fixture
def reducer_socket(tmp_path: Path):
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps(INVENTORY))
    state = tmp_path / "state.json"
    ledger = tmp_path / "events.jsonl"
    reducer = Reducer(tmp_path / "status.json", tmp_path / "token", lambda: {})
    reducer.refresh()
    path = tmp_path / "ops.sock"
    server = UnixHTTPServer(str(path), Handler)
    server.reducer = reducer
    server.token = "fixture-token"
    server.is_unix = True
    server.hub_manifest = None
    server.inventory_path = inventory
    server.feedback = None
    server.emitter_factory = lambda: health.Emitter(state, ledger, lambda *_: None)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield {"socket": path, "state": state, "ledger": ledger, "inventory": inventory}
    finally:
        server.shutdown()
        server.server_close()


def transitions(ledger: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in ledger.read_text().splitlines()]


def test_the_failure_reaches_the_running_reducer(reducer_socket) -> None:
    exit_code = cli.emit_failure_command(
        [
            "--unit",
            "usersurf",
            "--result",
            "oom-kill",
            "--socket",
            str(reducer_socket["socket"]),
            "--inventory",
            str(reducer_socket["inventory"]),
        ]
    )
    assert exit_code == 0
    events = transitions(reducer_socket["ledger"])
    assert len(events) == 1
    # The bare unit name is completed, and the manager comes from the
    # inventory, so the key matches the one the sweep would use.
    assert events[0]["unit"] == "usersurf.service"
    assert events[0]["evidence"] == "manager=user;source=onfailure;result=oom-kill"
    assert json.loads(reducer_socket["state"].read_text()) == {
        "service:user:usersurf.service": {"status": "failed"}
    }


def test_a_dead_reducer_does_not_swallow_the_failure(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    state = tmp_path / "state.json"
    ledger = tmp_path / "events.jsonl"
    monkeypatch.setattr(health, "state_path", lambda: state)
    monkeypatch.setattr(health, "ledger_path", lambda: ledger)
    monkeypatch.setattr(health, "notify_desktop", lambda *args, **kwargs: True)
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps(INVENTORY))

    exit_code = cli.emit_failure_command(
        [
            "--unit",
            "usersurf.service",
            "--result",
            "exit-code",
            "--socket",
            str(tmp_path / "nothing-listening.sock"),
            "--inventory",
            str(inventory),
        ]
    )
    assert exit_code == 0
    assert "the reducer was unreachable" in capsys.readouterr().err
    events = transitions(ledger)
    assert len(events) == 1
    assert events[0]["unit"] == "usersurf.service"
    assert events[0]["schema"] == "sinnix-health-transition-v1"
    # Same key, same file, same shape as the socket path: one state store.
    assert json.loads(state.read_text()) == {
        "service:user:usersurf.service": {"status": "failed"}
    }
