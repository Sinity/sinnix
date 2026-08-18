"""Core helper contracts: atomic JSON, ledger, lock, systemd parser."""

import json
import threading

import pytest
from sinnix_lib.atomic_json import modify_json, read_json, write_json_atomic
from sinnix_lib.ledger import append_jsonl, iter_jsonl, receipt
from sinnix_lib.lock import LockBusy, flock
from sinnix_lib.systemd import _parse_blocks


def test_atomic_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    write_json_atomic(p, {"a": 1})
    assert read_json(p) == {"a": 1}
    assert not list(tmp_path.glob("*.tmp"))


def test_read_json_heals_torn_writes(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("{not json")
    assert read_json(p, default={}) == {}


def test_modify_json_writes_on_clean_exit_only(tmp_path):
    p = tmp_path / "s.json"
    with modify_json(p, default={}) as doc:
        doc["k"] = "v"
    assert read_json(p) == {"k": "v"}
    with pytest.raises(RuntimeError):
        with modify_json(p) as doc:
            doc["k"] = "clobbered"
            raise RuntimeError
    assert read_json(p) == {"k": "v"}


def test_ledger_append_and_torn_tail(tmp_path):
    p = tmp_path / "l.jsonl"
    append_jsonl(p, {"n": 1})
    append_jsonl(p, {"n": 2})
    with p.open("a") as fh:
        fh.write('{"torn": ')
    assert [r["n"] for r in iter_jsonl(p)] == [1, 2]


def test_receipt_shape(monkeypatch):
    monkeypatch.setenv("INVOCATION_ID", "abc123")
    r = receipt("drain", "completed", items=3)
    assert r["run_id"] == "abc123"
    assert r["operation_kind"] == "drain" and r["state"] == "completed"
    assert r["items"] == 3 and r["ts"].endswith("Z")


def test_flock_nonblocking_busy(tmp_path):
    p = tmp_path / "l"
    entered = threading.Event()
    release = threading.Event()

    def holder():
        with flock(p):
            entered.set()
            release.wait(5)

    t = threading.Thread(target=holder)
    t.start()
    entered.wait(5)
    # flock is per-open-file-description; a second open in this process
    # still contends because the helper opens its own fd.
    with pytest.raises(LockBusy):
        with flock(p, blocking=False):
            pass
    release.set()
    t.join()


def test_systemd_block_parser():
    text = "Id=a.service\nActiveState=active\n\nId=b.service\nActiveState=failed\nResult=exit-code\n"
    got = _parse_blocks(text)
    assert got["a.service"]["ActiveState"] == "active"
    assert got["b.service"]["Result"] == "exit-code"


def test_json_compact(tmp_path):
    p = tmp_path / "c.json"
    write_json_atomic(p, {"b": 1, "a": 2})
    raw = p.read_text().strip()
    assert raw == json.dumps({"a": 2, "b": 1}, sort_keys=True, separators=(",", ":"))
