"""Spool contract tests: exactly-once, duplicate no-op, crash parking."""

import json

import pytest
from sinnix_lib import spool as spool_module
from sinnix_lib.spool import Spool


@pytest.fixture()
def spool(tmp_path):
    return Spool(tmp_path / "inbox")


def test_process_exactly_once_and_done(spool):
    spool.submit("a.json", b"{}")
    seen = []
    counts = spool.drain(lambda p: seen.append(p.name))
    assert counts["processed"] == 1 and seen == ["a.json"]
    assert (spool.root / "done" / "a.json").exists()
    # Redelivery of the same token is a counted no-op.
    spool.submit("a.json", b"{}")
    counts = spool.drain(lambda p: seen.append(p.name))
    assert counts["duplicate"] == 1 and len(seen) == 1


def test_failure_parks_with_error_sidecar(spool):
    spool.submit("bad.json", b"{}")

    def boom(_):
        raise RuntimeError("no")

    counts = spool.drain(boom)
    assert counts["failed"] == 1
    failed = spool.root / "failed" / "bad.json"
    assert failed.exists()
    error = failed.with_name("bad.json.error")
    assert "RuntimeError" in error.read_text()
    assert error.stat().st_mode & 0o777 == 0o600
    # A failed item's token is NOT recorded: moving it back retries it.
    (spool.root / "bad.json").write_bytes(failed.read_bytes())
    counts = spool.drain(lambda p: None)
    assert counts["processed"] == 1


def test_token_ledger_survives_restart(spool, tmp_path):
    spool.submit("x", b"1")
    spool.drain(lambda p: None)
    reborn = Spool(tmp_path / "inbox")
    reborn.submit("x", b"1")
    assert reborn.drain(lambda p: None)["duplicate"] == 1


def test_private_and_incomplete_files_are_invisible(spool):
    submitted = spool.submit("private.json", b"{}")
    assert submitted.stat().st_mode & 0o777 == 0o600
    (spool.root / "half.part").write_bytes(b"...")
    (spool.root / ".private.json.atomic-tmp-interrupted").write_bytes(b"...")
    assert list(spool.pending()) == [submitted]


def test_token_ledger_is_jsonl(spool):
    spool.submit("y", b"1")
    spool.drain(lambda p: None)
    lines = (spool.root / "processed-tokens.jsonl").read_text().splitlines()
    assert json.loads(lines[0])["token"] == "y"


def test_successful_processing_syncs_its_deduplication_token(spool, monkeypatch):
    """The token reaches stable storage before an item becomes done.

    Mutation: drop ``fsync=True`` from ``Spool._record`` and this assertion
    fails, leaving a crash window where a redelivery can repeat a side effect.
    """
    spool.submit("durable", b"1")
    calls = []
    original = spool_module.append_jsonl

    def record(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(spool_module, "append_jsonl", record)
    assert spool.drain(lambda _item: None)["processed"] == 1
    assert calls == [{"fsync": True}]
