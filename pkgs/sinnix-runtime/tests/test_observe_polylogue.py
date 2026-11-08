"""Polylogue daemon status: read through `polylogue status --json`, gaps otherwise."""

import json

from sinnix_runtime.observe.sources import polylogue

STATUS = {
    "pid": 4242,
    "uptime_seconds": 60,
    "busy": True,
    "passes": 3,
    "mode": {"state": "standalone"},
    "last_pass": {"inputs_changed": 2, "messages_written": 5, "seconds": 0.5},
    "store": {"sessions": 7, "messages": 70, "unused": [["field:x", 1]]},
}


def fake_polylogue(tmp_path, body: str, code: int = 0):
    script = tmp_path / "polylogue"
    script.write_text(f"#!/bin/sh\necho '{body}'\nexit {code}\n")
    script.chmod(0o755)
    return script


def archive(tmp_path, monkeypatch):
    root = tmp_path / "archive"
    root.mkdir()
    (root / "archive.db").write_bytes(b"x" * 10)
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"polylogue": {"archiveRoot": str(root)}}))
    monkeypatch.setenv("SINNIX_RUNTIME_INVENTORY_FILE", str(inventory))
    return root


def test_status_is_read_from_the_daemon(tmp_path, monkeypatch):
    root = archive(tmp_path, monkeypatch)
    script = fake_polylogue(tmp_path, json.dumps(STATUS))
    monkeypatch.setenv("SINNIX_OBSERVE_POLYLOGUE", str(script))
    result = polylogue.collect_polylogue_status()
    assert result["available"] is True
    assert result["unit"] == "polylogue-live.service"
    assert (
        result["pid"] == 4242
        and result["busy"] is True
        and result["mode"] == "standalone"
    )
    assert result["store"]["messages"] == 70
    assert "unused" not in result["store"]
    files = {row["name"]: row for row in result["archive"]["files"]}
    assert result["archive"]["root"] == str(root)
    assert files["archive.db"] == {
        "name": "archive.db",
        "path": str(root / "archive.db"),
        "state": "present",
        "bytes": 10,
    }
    assert files["index.db"]["state"] == "missing"


def test_daemon_failure_is_a_gap(tmp_path, monkeypatch):
    archive(tmp_path, monkeypatch)
    script = fake_polylogue(tmp_path, "daemon is not running", code=6)
    monkeypatch.setenv("SINNIX_OBSERVE_POLYLOGUE", str(script))
    result = polylogue.collect_polylogue_status()
    assert result["available"] is False
    assert result["gaps"] == ["polylogue.status.failed"]
    assert result["error"] == "daemon is not running"


def test_unreadable_answer_is_a_gap(tmp_path, monkeypatch):
    archive(tmp_path, monkeypatch)
    monkeypatch.setenv(
        "SINNIX_OBSERVE_POLYLOGUE", str(fake_polylogue(tmp_path, "not json"))
    )
    assert polylogue.collect_polylogue_status()["gaps"] == [
        "polylogue.status.unreadable"
    ]
