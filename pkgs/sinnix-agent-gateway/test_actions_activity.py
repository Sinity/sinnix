"""Typed captures, activity, sessions, memory and timeline actions."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from sinnix_agent_gateway.actions import activity
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.runtime import Runtime
from sinnix_agent_gateway.sessions import SessionLogService, SessionSource
from test_actions_machine import call
from test_captures import make_inventory

BY_NAME = {action.name: action for action in activity.ACTIONS}


def write_lane(path: Path, lane: str, records: list[dict]) -> None:
    for record in records:
        day = time.strftime("%Y%m%d", time.gmtime(record["ts"]))
        with (path / f"{lane}-{day}.jsonl").open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "schema": "sinnix-capture-v1",
                        "schema_version": 1,
                        "lane": lane,
                        "host": "h",
                        "raw_ref": None,
                        **record,
                    }
                )
                + "\n"
            )


def runtime(
    tmp_path: Path, principal: str = "observer"
) -> tuple[Runtime, dict[str, Path]]:
    inventory, lanes = make_inventory(tmp_path)
    inventory_data = json.loads(inventory.read_text())
    plain = tmp_path / "plain.jsonl"
    plain.write_text("")
    inventory_data["captures"].append({"name": "plain", "path": str(plain)})
    inventory.write_text(json.dumps(inventory_data))
    cfg = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        runtime_inventory=inventory,
        ops_socket_path=tmp_path / "ops.sock",
        capture_command="sinnix-capture-absent",
    )
    rt = Runtime.create(cfg, principal)
    root = tmp_path / "sessions"
    (root / "proj").mkdir(parents=True)
    (root / "proj" / "s1.jsonl").write_text(
        '{"text":"gateway demonstration"}\n{"text":"second"}\n'
    )
    rt.sessions = SessionLogService(
        cfg,
        rt.principal,
        sources=(
            SessionSource("claude-code", root),
            SessionSource("codex", tmp_path / "missing"),
        ),
    )
    rt.memory.sessions = rt.sessions
    rt.timeline.sessions = rt.sessions
    return rt, lanes


def test_captures_operations(tmp_path: Path) -> None:
    rt, _lanes = runtime(tmp_path)
    lanes = call(rt, "captures.query", {}, BY_NAME)["data"]
    assert [row["name"] for row in lanes["lanes"]] == [
        "clipboard",
        "mpris",
        "plain",
        "router",
    ]
    lane = call(
        rt,
        "captures.query",
        {"request": {"operation": "lane", "name": "mpris"}},
        BY_NAME,
    )["data"]["lane"]
    assert lane["ref"] == "sinnix://captures/mpris" and lane["native_lane"] == "mpris"
    missing = call(
        rt,
        "captures.query",
        {"request": {"operation": "lane", "name": "nope"}},
        BY_NAME,
    )
    assert missing["error"]["code"] == "not_found"
    plain = call(
        rt,
        "captures.query",
        {"request": {"operation": "query", "lanes": ["plain"]}},
        BY_NAME,
    )["data"]
    assert plain["available"] is False and plain["unavailable_lanes"] == ["plain"]
    absent = call(
        rt,
        "captures.query",
        {"request": {"operation": "query", "lanes": ["mpris"]}},
        BY_NAME,
    )["data"]
    assert (
        absent["available"] is False
        and absent["failure_class"] == "collector_unavailable"
    )


def test_activity_normalises_envelopes_and_reports_coverage(tmp_path: Path) -> None:
    rt, lanes = runtime(tmp_path)
    now = time.time()
    write_lane(
        lanes["clipboard"],
        "clipboard",
        [
            {
                "ts": now - 10,
                "seq": 1,
                "payload": {
                    "category": "text",
                    "text": "copied gateway text",
                    "source_window": {"class": "kitty", "title": "polylogue dev"},
                },
            },
            {
                "ts": now - 5,
                "seq": 2,
                "payload": {
                    "category": "image",
                    "source_window": {"class": "chromium", "title": "web"},
                },
            },
            {
                "ts": now - 90_000,
                "seq": 0,
                "payload": {"category": "text", "text": "old"},
            },
        ],
    )
    write_lane(
        lanes["mpris"],
        "mpris",
        [
            {
                "ts": now - 7,
                "seq": 9,
                "payload": {
                    "event": "heartbeat",
                    "player": "chromium",
                    "artist": "A",
                    "title": "T",
                },
            }
        ],
    )
    data = call(rt, "activity.query", {"limit": 10}, BY_NAME)["data"]
    assert [(e["lane"], e["seq"]) for e in data["events"]] == [
        ("clipboard", 2),
        ("mpris", 9),
        ("clipboard", 1),
    ]
    assert (
        data["events"][1]["text"] == "A - T"
        and data["events"][1]["application"] == "chromium"
    )
    assert data["events"][2]["terminal"] == "polylogue dev"
    assert data["lanes_contributed"] == ["clipboard", "mpris"] and data[
        "lanes_unavailable"
    ] == ["plain"]
    kitty = call(
        rt, "activity.query", {"application": "kitty", "text": "gateway"}, BY_NAME
    )["data"]
    assert [e["seq"] for e in kitty["events"]] == [1]
    only = call(rt, "activity.query", {"kinds": ["heartbeat"]}, BY_NAME)["data"]
    assert [e["lane"] for e in only["events"]] == ["mpris"]
    window = call(
        rt, "activity.query", {"since": now - 100_000, "until": now - 50_000}, BY_NAME
    )["data"]
    assert [e["seq"] for e in window["events"]] == [0]


def test_sessions_memory_timeline(tmp_path: Path) -> None:
    rt, _ = runtime(tmp_path)
    listed = call(
        rt,
        "sessions.query",
        {"request": {"operation": "list", "provider": "claude-code"}},
        BY_NAME,
    )["data"]
    assert listed["sessions"][0]["reference"] == "claude-code:proj/s1.jsonl"
    read = call(
        rt,
        "sessions.query",
        {
            "request": {
                "operation": "read",
                "reference": "claude-code:proj/s1.jsonl",
                "max_bytes": 10,
            }
        },
        BY_NAME,
    )["data"]
    assert read["content"] == '{"text":"g' and read["truncated"]
    continued = call(
        rt,
        "sessions.query",
        {
            "request": {
                "operation": "read",
                "reference": read["reference"],
                "offset": read["next_offset"],
            }
        },
        BY_NAME,
    )["data"]
    assert read["content"] + continued["content"] == (
        '{"text":"gateway demonstration"}\n{"text":"second"}\n'
    )
    assert continued["next_offset"] is None
    found = call(
        rt,
        "sessions.query",
        {
            "request": {
                "operation": "search",
                "provider": "claude-code",
                "query": "gateway",
            }
        },
        BY_NAME,
    )["data"]
    assert found["matches"][0]["line"] == 1
    bad = call(
        rt,
        "sessions.query",
        {"request": {"operation": "read", "reference": "claude-code:../x.jsonl"}},
        BY_NAME,
    )
    assert bad["error"]["code"] == "invalid_request"

    memory = call(
        rt,
        "memory.query",
        {"request": {"operation": "search", "query": "gateway"}},
        BY_NAME,
    )["data"]
    assert memory["matches"][0]["object_reference"] == "claude-code:proj/s1.jsonl"
    assert {s["source"]: s["availability"] for s in memory["sources"]}[
        "polylogue"
    ] == "unavailable"
    got = call(
        rt,
        "memory.query",
        {"request": {"operation": "get", "reference": "claude-code:proj/s1.jsonl"}},
        BY_NAME,
    )["data"]
    assert got["authority"] == "authoritative-local-session-jsonl"

    timeline = call(
        rt, "timeline.query", {"providers": ["claude-code"], "query": "second"}, BY_NAME
    )["data"]
    assert (
        timeline["time_basis"] == "session-file-mtime"
        and timeline["entries"][0]["snippet"] == '{"text":"second"}'
    )
    bad_time = call(rt, "timeline.query", {"start": "yesterday"}, BY_NAME)
    assert bad_time["error"]["code"] == "invalid_request"


def test_agent_control_cannot_read_sessions(tmp_path: Path) -> None:
    rt, _ = runtime(tmp_path, "agent-control")
    denied = call(
        rt,
        "sessions.query",
        {"request": {"operation": "list", "provider": "codex"}},
        BY_NAME,
    )
    assert denied["error"]["code"] == "policy_denied"


def test_session_listing_pages_a_snapshot_without_rescanning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    rt, _ = runtime(tmp_path)
    root = rt.sessions.sources[0].root
    original = root / "proj" / "s1.jsonl"
    os.utime(original, ns=(1, 1))
    recent = root / "s2.jsonl"
    recent.write_text("{}\n")
    os.utime(recent, ns=(2, 2))
    request = {"operation": "list", "provider": "claude-code", "limit": 1}
    first = call(rt, "sessions.query", {"request": request}, BY_NAME)
    assert first["data"]["sessions"][0]["reference"] == "claude-code:s2.jsonl"
    assert first["page"]["total"] == 2
    assert rt.results.read(first["result"]["result_id"])["page"] == first["page"]
    cursor = first["page"]["next_cursor"]

    newest = root / "s3.jsonl"
    newest.write_text("{}\n")
    os.utime(newest, ns=(3, 3))
    with monkeypatch.context() as patch:
        patch.setattr(
            rt.sessions, "inventory", lambda _: pytest.fail("continuation rescanned")
        )
        second = call(
            rt, "sessions.query", {"request": {**request, "cursor": cursor}}, BY_NAME
        )
    assert second["data"]["sessions"][0]["reference"] == "claude-code:proj/s1.jsonl"
    assert second["page"]["next_cursor"] is None
    assert second["page"]["snapshot_ref"] == first["page"]["snapshot_ref"]
    fresh = call(rt, "sessions.query", {"request": request}, BY_NAME)
    assert fresh["data"]["sessions"][0]["reference"] == "claude-code:s3.jsonl"

    wrong_scope = call(
        rt,
        "sessions.query",
        {
            "request": {
                **request,
                "provider": "codex",
                "cursor": cursor,
            }
        },
        BY_NAME,
    )
    assert wrong_scope["error"]["code"] == "stale_cursor"


def test_missing_session_provider_returns_typed_unavailable(tmp_path: Path) -> None:
    rt, _ = runtime(tmp_path)
    result = call(
        rt,
        "sessions.query",
        {
            "request": {
                "operation": "list",
                "provider": "codex",
            }
        },
        BY_NAME,
    )
    assert result["error"]["code"] == "unavailable"


@pytest.mark.parametrize("max_bytes", [4, 11, 13])
def test_session_read_continuation_preserves_utf8(
    tmp_path: Path, max_bytes: int
) -> None:
    rt, _ = runtime(tmp_path)
    text = '{"text":"aé😀z"}\n'
    (rt.sessions.sources[0].root / "proj" / "s1.jsonl").write_text(text)
    offset = 0
    pieces = []
    for _ in range(len(text.encode("utf-8"))):
        response = call(
            rt,
            "sessions.query",
            {
                "request": {
                    "operation": "read",
                    "reference": "claude-code:proj/s1.jsonl",
                    "offset": offset,
                    "max_bytes": max_bytes,
                }
            },
            BY_NAME,
        )
        assert response["result"]["outcome"] == "ok", response
        data = response["data"]
        pieces.append(data["content"])
        assert 0 < data["bytes"] <= max_bytes
        if data["next_offset"] is None:
            break
        assert data["next_offset"] == offset + data["bytes"]
        offset = data["next_offset"]
    else:
        pytest.fail("session continuation did not terminate")
    assert "".join(pieces) == text


def test_session_read_refuses_a_budget_that_cannot_fit_one_character(
    tmp_path: Path,
) -> None:
    rt, _ = runtime(tmp_path)
    (rt.sessions.sources[0].root / "proj" / "s1.jsonl").write_text("😀x")
    request = {"operation": "read", "reference": "claude-code:proj/s1.jsonl"}

    too_small = call(
        rt,
        "sessions.query",
        {
            "request": {
                **request,
                "max_bytes": 1,
            }
        },
        BY_NAME,
    )
    assert too_small["error"]["code"] == "invalid_request"
    assert "max_bytes" in too_small["error"]["message"]

    readable = call(
        rt,
        "sessions.query",
        {
            "request": {
                **request,
                "max_bytes": 4,
            }
        },
        BY_NAME,
    )["data"]
    assert readable["content"] == "😀" and readable["next_offset"] == 4
