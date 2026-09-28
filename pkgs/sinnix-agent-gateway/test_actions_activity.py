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
    tmp_path: Path, principal: str = "operator"
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


def write_high_water(path: Path) -> None:
    """The capture writer's sidecar for ``path`` (sinnix_capture.writer)."""
    end, high, rows = 0, float("-inf"), []
    for line in path.read_bytes().splitlines(keepends=True):
        end += len(line)
        high = max(high, json.loads(line)["ts"])
        rows.append(f"{end:020d} {high:032.9f}\n")
    path.with_name(path.name + ".hw").write_text("".join(rows))


def test_recent_query_skips_a_large_older_prefix(tmp_path: Path) -> None:
    """Fails if a recent window spends its lane budget on the day's older prefix,
    or if the skip drops an in-window record appended out of ts order."""
    rt, lanes = runtime(tmp_path)
    noon = 1_800_000_000 - 1_800_000_000 % 86_400 + 43_200
    older = [
        {
            "ts": noon - 40_000 + i,
            "seq": i,
            "payload": {"category": "text", "text": "x" * 100},
        }
        for i in range(2_000)
    ]
    late = [
        {
            "ts": noon - 90,
            "seq": 4_000,
            "payload": {"category": "text", "text": "early"},
        },
        {"ts": noon - 30, "seq": 5_001, "payload": {"category": "text", "text": "b"}},
        {"ts": noon - 60, "seq": 5_000, "payload": {"category": "text", "text": "a"}},
    ]
    write_lane(lanes["clipboard"], "clipboard", older + late)
    day = time.strftime("%Y%m%d", time.gmtime(noon))
    day_file = lanes["clipboard"] / f"clipboard-{day}.jsonl"
    write_high_water(day_file)
    budget = 65_536
    assert day_file.stat().st_size > 3 * budget
    request = {
        "since": noon - 120,
        "until": noon,
        "kinds": ["clipboard"],
        "max_bytes_per_lane": budget,
    }
    data = call(rt, "activity.query", request, BY_NAME)["data"]
    assert [e["seq"] for e in data["events"]] == [5_001, 5_000, 4_000]
    assert data["truncated"] is False

    day_file.with_name(day_file.name + ".hw").unlink()
    unindexed = call(rt, "activity.query", request, BY_NAME)["data"]
    assert unindexed["truncated"] is True
