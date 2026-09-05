"""Typed process actions over /proc."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sinnix_agent_gateway.actions import processes
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.locators import ProcessLocator
from sinnix_agent_gateway.runtime import Runtime
from test_actions_machine import call

BY_NAME = {action.name: action for action in processes.ACTIONS}


def runtime(tmp_path: Path, principal: str = "operator") -> Runtime:
    return Runtime.create(
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={},
            ops_socket_path=tmp_path / "ops.sock",
        ),
        principal,
    )


@pytest.fixture
def child():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        env={
            **os.environ,
            "GATEWAY_TOKEN": "sk-abcdefghijklmnopqrstuvwxyz",
            "PLAIN": "value",
        },
    )
    yield proc
    if proc.poll() is None:
        proc.kill()
    proc.wait()


def test_locator_resolves_pid_and_rejects_stale_ref(tmp_path: Path) -> None:
    row, ref = ProcessLocator(pid=os.getpid()).resolve()
    assert ref == f"sinnix://processes/{os.getpid()}/{row['start_ticks']}"
    assert ProcessLocator(ref=ref).resolve()[1] == ref
    with pytest.raises(Exception, match="not_found|no process"):
        ProcessLocator(ref=f"sinnix://processes/{os.getpid()}/1").resolve()


def test_list_get_tree(tmp_path: Path, child: subprocess.Popen) -> None:
    rt = runtime(tmp_path, "observer")
    listing = call(rt, "processes.list", {"pid": child.pid}, BY_NAME)["data"]
    assert listing["total"] == 1 and listing["processes"][0]["ppid"] == os.getpid()
    assert "time.sleep" in listing["processes"][0]["cmdline"]
    named = call(rt, "processes.list", {"name": "time.sleep(60)"}, BY_NAME)["data"]
    assert child.pid in {row["pid"] for row in named["processes"]}

    detail = call(rt, "processes.get", {"target": {"pid": child.pid}}, BY_NAME)["data"]
    assert detail["parent"]["pid"] == os.getpid()
    assert detail["env"]["PLAIN"] == "value"
    assert detail["env"]["GATEWAY_TOKEN"] == "[REDACTED]"
    assert detail["rss_bytes"] > 0 and detail["threads"] >= 1 and detail["cwd"]

    tree = call(
        rt, "processes.tree", {"root": {"pid": os.getpid()}, "max_depth": 2}, BY_NAME
    )["data"]
    assert child.pid in {node["pid"] for node in tree["roots"][0]["children"]}


def test_signal_and_wait(tmp_path: Path, child: subprocess.Popen) -> None:
    rt = runtime(tmp_path)
    still = call(
        rt,
        "processes.wait",
        {"target": {"pid": child.pid}, "timeout_seconds": 0.3},
        BY_NAME,
    )["data"]
    assert still["exited"] is False
    sent = call(
        rt,
        "processes.signal",
        {
            "target": {"pid": child.pid},
            "request": {"operation": "signal", "signal": "TERM"},
            "reason": "test",
            "idempotency_key": "term-1",
        },
        BY_NAME,
    )
    assert sent["result"]["outcome"] == "ok", sent
    child.wait(timeout=5)
    gone = call(
        rt,
        "processes.wait",
        {"target": {"ref": sent["data"]["ref"]}, "timeout_seconds": 1},
        BY_NAME,
    )
    assert gone["error"]["code"] == "not_found" or gone["data"]["exited"] is True


def test_signal_is_operator_only_and_never_self(tmp_path: Path) -> None:
    denied = call(
        runtime(tmp_path, "observer"),
        "processes.signal",
        {
            "target": {"pid": os.getpid()},
            "request": {"operation": "signal"},
            "idempotency_key": "k",
        },
        BY_NAME,
    )
    assert denied["error"]["code"] == "policy_denied"
    refused = call(
        runtime(tmp_path),
        "processes.signal",
        {
            "target": {"pid": os.getpid()},
            "request": {"operation": "signal"},
            "idempotency_key": "k",
        },
        BY_NAME,
    )
    assert refused["error"]["code"] == "policy_denied"
