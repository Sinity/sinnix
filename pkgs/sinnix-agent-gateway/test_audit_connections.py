from __future__ import annotations

import gc
import os
import sqlite3

import pytest
from sinnix_agent_gateway.audit import AuditService
from sinnix_agent_gateway.config import GatewayConfig


def service(tmp_path):
    return AuditService(GatewayConfig(state_dir=tmp_path, projects={}))


def test_audit_connections_close_without_garbage_collection(tmp_path):
    audit = service(tmp_path)
    gc.collect()
    enabled = gc.isenabled()
    gc.disable()
    try:
        before = set(os.listdir("/proc/self/fd"))
        for _ in range(20):
            receipt = audit.append("fixture.query", "ok", {})
            assert audit.receipt(receipt["event_id"])["operation"] == "fixture.query"
            assert audit.operation("fixture.change", "unsent")["state"] == "unknown"
            assert audit.verify()["valid"]
        assert set(os.listdir("/proc/self/fd")) == before
    finally:
        if enabled:
            gc.enable()
        gc.collect()


@pytest.mark.parametrize("fail", [False, True])
def test_connection_transaction_and_cleanup(tmp_path, fail):
    audit = service(tmp_path)

    class Interrupted(Exception):
        pass

    try:
        with audit._connect() as connection:
            connection.execute("begin immediate")
            connection.execute("create table fixture_transaction (value integer)")
            connection.execute("insert into fixture_transaction values (1)")
            if fail:
                raise Interrupted
    except Interrupted:
        assert fail
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("select 1")
    with audit._connect() as reopened:
        exists = reopened.execute(
            "select count(*) from sqlite_master where name='fixture_transaction'"
        ).fetchone()[0]
        assert exists == (0 if fail else 1)
        if not fail:
            assert reopened.execute(
                "select value from fixture_transaction"
            ).fetchone() == (1,)


def test_connection_closes_when_pragma_setup_fails(tmp_path, monkeypatch):
    audit = service(tmp_path)
    connect = sqlite3.connect
    opened = []

    class BrokenSetup(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql == "pragma journal_mode=wal":
                raise sqlite3.OperationalError("synthetic setup failure")
            return super().execute(sql, *args, **kwargs)

    def broken_connect(*args, **kwargs):
        connection = connect(*args, **kwargs, factory=BrokenSetup)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", broken_connect)
    with pytest.raises(sqlite3.OperationalError, match="synthetic setup failure"):
        with audit._connect():
            pytest.fail("setup failure must not enter the operation")
    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].cursor()
