from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest
from sinnix_agent_gateway.captures import CaptureService
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_lib.layout import ACTIVITY_LANES, capture_lane_path


def make_inventory(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    activity_root = tmp_path / "activity"
    machine_root = tmp_path / "machine"
    lane_paths = {
        "mpris": capture_lane_path(activity_root, "mpris"),
        "clipboard": capture_lane_path(activity_root, "clipboard"),
        "router": machine_root / "router",
    }
    for lane, path in lane_paths.items():
        path.mkdir(parents=True)
        (path / f"{lane}-index.jsonl").write_text('{"ts":1,"seq":1}\n')
    inventory = tmp_path / "runtime-inventory.json"
    inventory.write_text(
        json.dumps(
            {
                "captures": [
                    {"name": lane, "path": str(path)}
                    for lane, path in lane_paths.items()
                ]
            }
        )
    )
    return inventory, lane_paths


def config(tmp_path: Path) -> tuple[GatewayConfig, dict[str, Path]]:
    inventory, lane_paths = make_inventory(tmp_path)
    return (
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={},
            runtime_inventory=inventory,
        ),
        lane_paths,
    )


def test_capture_lanes_tool_lists_runtime_declared_envelope_lanes(
    tmp_path: Path,
) -> None:
    gateway_config, lane_paths = config(tmp_path)
    service = CaptureService(gateway_config)

    result = service.lanes_visible()

    assert result == {
        "lanes": [
            {
                "name": "clipboard",
                "ref": "sinnix://captures/clipboard",
                "path": str(lane_paths["clipboard"]),
                "capture_root": str(lane_paths["clipboard"].parents[1]),
                "native_lane": "clipboard",
                "native_contract": "sinnix-capture-v1-sidecar",
            },
            {
                "name": "mpris",
                "ref": "sinnix://captures/mpris",
                "path": str(lane_paths["mpris"]),
                "capture_root": str(lane_paths["mpris"].parents[1]),
                "native_lane": "mpris",
                "native_contract": "sinnix-capture-v1-sidecar",
            },
            {
                "name": "router",
                "ref": "sinnix://captures/router",
                "path": str(lane_paths["router"]),
                "capture_root": str(lane_paths["router"].parent),
                "native_lane": "router",
                "native_contract": "sinnix-capture-v1-sidecar",
            },
        ],
        "total_declared_lanes": 3,
    }


def test_capture_query_groups_declared_lanes_by_inventory_root(tmp_path: Path) -> None:
    gateway_config, lane_paths = config(tmp_path)
    captured = tmp_path / "collector-commands.jsonl"
    collector = tmp_path / "sinnix-capture"
    collector.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        f"with pathlib.Path({str(captured)!r}).open('a') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "lanes = [sys.argv[index + 1] for index, value in enumerate(sys.argv) if value == '--lane']\n"
        "print(json.dumps({'records': [{'lane': lane} for lane in lanes]}))\n"
    )
    collector.chmod(0o700)
    service = CaptureService(
        GatewayConfig(
            state_dir=gateway_config.state_dir,
            projects={},
            runtime_inventory=gateway_config.runtime_inventory,
            capture_command=str(collector),
        ),
    )

    result = service.query(["mpris", "router"])

    assert result == {
        "records": [{"lane": "mpris"}, {"lane": "router"}],
        "lanes_queried": ["mpris", "router"],
        "truncated": False,
    }
    commands = [json.loads(line) for line in captured.read_text().splitlines()]
    assert commands == [
        [
            "query",
            "--capture-root",
            str(lane_paths["mpris"].parents[1]),
            "--since",
            "0.0",
            "--lane",
            "mpris",
        ],
        [
            "query",
            "--capture-root",
            str(lane_paths["router"].parent),
            "--since",
            "0.0",
            "--lane",
            "router",
        ],
    ]


def test_capture_query_reports_missing_collector_for_declared_lane(
    tmp_path: Path,
) -> None:
    gateway_config, lane_paths = config(tmp_path)
    service = CaptureService(
        GatewayConfig(
            state_dir=gateway_config.state_dir,
            projects={},
            runtime_inventory=gateway_config.runtime_inventory,
            capture_command=str(tmp_path / "missing-sinnix-capture"),
        ),
    )

    result = service.query(["mpris"])

    assert result == {
        "available": False,
        "failure_class": "collector_unavailable",
        "reason": "sinnix-capture query is unavailable",
        "command": [
            str(tmp_path / "missing-sinnix-capture"),
            "query",
            "--capture-root",
            str(lane_paths["mpris"].parents[1]),
            "--since",
            "0.0",
            "--lane",
            "mpris",
        ],
    }


def test_declared_file_lane_remains_visible_without_a_sidecar_guess(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "runtime-inventory.json"
    lane = tmp_path / "machine" / "telemetry.jsonl"
    lane.parent.mkdir(parents=True)
    lane.write_text("{}\n")
    inventory.write_text(
        json.dumps({"captures": [{"name": "telemetry", "path": str(lane)}]})
    )

    service = CaptureService(
        GatewayConfig(
            state_dir=tmp_path / "state", projects={}, runtime_inventory=inventory
        ),
    )

    assert service.lane("telemetry") == {
        "ref": "sinnix://captures/telemetry",
        "name": "telemetry",
        "path": str(lane),
        "native_contract": "runtime-declared-path",
    }
    assert service.query(["telemetry"]) == {
        "available": False,
        "failure_class": "native_contract_unavailable",
        "reason": "selected runtime capture paths have no admitted query reader",
        "lanes": ["telemetry"],
    }


def test_capture_query_uses_the_native_lane_derived_from_a_nested_declared_path(
    tmp_path: Path,
) -> None:
    root = tmp_path / "machine" / "peripherals"
    path = root / "logitech"
    path.mkdir(parents=True)
    (path / "logitech-index.jsonl").write_text('{"ts": 1, "seq": 1}\n')
    inventory = tmp_path / "runtime-inventory.json"
    inventory.write_text(
        json.dumps({"captures": [{"name": "peripherals-logitech", "path": str(path)}]})
    )
    captured = tmp_path / "collector-commands.jsonl"
    collector = tmp_path / "sinnix-capture"
    collector.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        f"pathlib.Path({str(captured)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        "print('[]')\n"
    )
    collector.chmod(0o700)
    service = CaptureService(
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={},
            runtime_inventory=inventory,
            capture_command=str(collector),
        ),
    )

    assert service.query(["peripherals-logitech"]) == {
        "records": [],
        "lanes_queried": ["peripherals-logitech"],
        "truncated": False,
    }
    assert json.loads(captured.read_text()) == [
        "query",
        "--capture-root",
        str(root),
        "--since",
        "0.0",
        "--lane",
        "logitech",
    ]


def test_freshness_uses_sidecar_progress_when_directory_mtime_is_stale(
    tmp_path: Path,
) -> None:
    gateway_config, lane_paths = config(tmp_path)
    lane = lane_paths["mpris"]
    old = time.time() - 3_600
    os.utime(lane, (old, old))
    index = lane / "mpris-index.jsonl"
    with index.open("a") as handle:
        handle.write('{"ts":2,"seq":2}\n')

    service = CaptureService(gateway_config)
    evidence = service.freshness("mpris")

    assert evidence["available"] is True
    assert evidence["progress_path"] == str(index)
    assert evidence["mtime"] > old


def test_freshness_uses_declared_file_and_reports_missing_directory_progress(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "runtime-inventory.json"
    direct_file = tmp_path / "machine" / "telemetry.jsonl"
    directory = tmp_path / "machine" / "empty-lane"
    direct_file.parent.mkdir(parents=True)
    directory.mkdir()
    direct_file.write_text("record\n")
    inventory.write_text(
        json.dumps(
            {
                "captures": [
                    {"name": "telemetry", "path": str(direct_file)},
                    {"name": "empty", "path": str(directory)},
                ]
            }
        )
    )
    service = CaptureService(
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={},
            runtime_inventory=inventory,
        ),
    )

    assert service.freshness("telemetry")["progress_path"] == str(direct_file)
    assert service.freshness("empty") == {
        "available": False,
        "reason": "capture lane has no admitted progress record",
        "lane": "empty",
    }


@pytest.mark.parametrize("payload", ["{", "[]", "{}", '{"captures":null}'])
def test_unusable_inventory_is_not_measured_as_zero_lanes(tmp_path, payload):
    from sinnix_agent_gateway.captures import CaptureInventoryUnavailableError

    gateway_config, _ = config(tmp_path)
    gateway_config.runtime_inventory.write_text(payload)
    service = CaptureService(gateway_config)
    with pytest.raises(CaptureInventoryUnavailableError):
        service.lanes_visible()


def test_missing_and_denied_inventory_are_not_empty(tmp_path, monkeypatch):
    from sinnix_agent_gateway.captures import CaptureInventoryUnavailableError

    gateway_config, _ = config(tmp_path)
    gateway_config.runtime_inventory.unlink()
    service = CaptureService(gateway_config)
    with pytest.raises(CaptureInventoryUnavailableError, match="unavailable"):
        service.lanes_visible()

    def denied(*args, **kwargs):
        raise PermissionError("synthetic denied inventory")

    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(CaptureInventoryUnavailableError, match="denied inventory"):
        service.lanes_visible()


def test_accessible_empty_inventory_is_valid(tmp_path):
    gateway_config, _ = config(tmp_path)
    gateway_config.runtime_inventory.write_text('{"captures": []}')
    service = CaptureService(gateway_config)
    assert service.lanes_visible() == {"lanes": [], "total_declared_lanes": 0}


def test_undeclared_capture_lanes_are_refused(tmp_path: Path) -> None:
    cfg, _ = config(tmp_path)
    service = CaptureService(cfg)
    for operation in (
        service.query,
        lambda lanes: service.lane(lanes[0]),
        lambda lanes: service.freshness(lanes[0]),
    ):
        with pytest.raises(ValueError, match="not declared"):
            operation(["future"])


@pytest.mark.parametrize("identity", ACTIVITY_LANES)
def test_managed_lane_contract_round_trips_shared_layout(
    tmp_path: Path, identity: str
) -> None:
    root = tmp_path / "custom-capture-root"
    path = capture_lane_path(root, identity)
    path.mkdir(parents=True)
    index = path / f"{identity}-index.jsonl"
    index.write_text('{"ts":1,"seq":1}\n')
    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps({"captures": [{"name": "display-name", "path": str(path)}]})
    )
    service = CaptureService(
        GatewayConfig(
            state_dir=tmp_path / "state", projects={}, runtime_inventory=inventory
        ),
    )
    lane = service.lane("display-name")
    assert lane["native_lane"] == identity
    assert lane["capture_root"] == str(root)
    assert service.freshness("display-name")["progress_path"] == str(index)


def test_retired_flat_managed_lane_is_not_admitted_as_empty(tmp_path: Path) -> None:
    lane = tmp_path / "activity" / "mpris"
    lane.mkdir(parents=True)
    (lane / "mpris-index.jsonl").write_text('{"ts":1,"seq":1}\n')
    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps({"captures": [{"name": "mpris", "path": str(lane)}]})
    )
    service = CaptureService(
        GatewayConfig(
            state_dir=tmp_path / "state", projects={}, runtime_inventory=inventory
        ),
    )
    result = service.query(["mpris"])
    assert result["available"] is False
    assert result["failure_class"] == "native_contract_unavailable"


def test_capture_query_reads_actual_native_cli_at_canonical_homes(
    tmp_path: Path,
) -> None:
    gateway_config, _ = config(tmp_path)
    command = os.environ.get("SINNIX_CAPTURE_TEST_EXECUTABLE", "sinnix-capture")
    service = CaptureService(
        GatewayConfig(
            state_dir=gateway_config.state_dir,
            projects={},
            runtime_inventory=gateway_config.runtime_inventory,
            capture_command=command,
        ),
    )
    result = service.query(["mpris", "clipboard"])
    assert "available" not in result, result
    records = {record["lane"]: record for record in result["records"]}
    assert set(records) == {"mpris", "clipboard"}
    assert all(record["records_since"] == 1 for record in records.values())
