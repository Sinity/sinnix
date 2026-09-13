"""Typed captures, activity, sessions, memory and timeline actions."""

from __future__ import annotations

import json
import time
from pathlib import Path

from sinnix_agent_gateway.actions import activity
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.runtime import Runtime
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
