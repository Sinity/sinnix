from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sinnix_agent_gateway.capabilities import Capability, PolicyError, Principal
from sinnix_agent_gateway.captures import CaptureService
from sinnix_agent_gateway.config import GatewayConfig


def make_inventory(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    activity_root = tmp_path / "activity"
    machine_root = tmp_path / "machine"
    lane_paths = {
        "mpris": activity_root / "mpris",
        "clipboard": activity_root / "clipboard",
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


@pytest.mark.parametrize("principal_name", ("observer", "agent-control", "operator"))
def test_principals_have_full_operator_authorized_capture_read_access(
    principal_name: str,
) -> None:
    principal = Principal.for_name(principal_name)

    assert principal.allowed_lanes is None
    principal.require_lane("clipboard")


def test_capture_lanes_tool_lists_runtime_declared_envelope_lanes(
    tmp_path: Path,
) -> None:
    gateway_config, lane_paths = config(tmp_path)
    service = CaptureService(gateway_config, Principal.for_name("observer"))

    result = service.lanes_visible()

    assert result == {
        "lanes": [
            {
                "name": "clipboard",
                "ref": "sinnix://captures/clipboard",
                "path": str(lane_paths["clipboard"]),
                "capture_root": str(lane_paths["clipboard"].parent),
                "native_lane": "clipboard",
                "native_contract": "sinnix-capture-v1-sidecar",
            },
            {
                "name": "mpris",
                "ref": "sinnix://captures/mpris",
                "path": str(lane_paths["mpris"]),
                "capture_root": str(lane_paths["mpris"].parent),
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


def test_filter_lanes_returns_requested_or_all_authorized_lanes() -> None:
    principal = Principal.for_name("observer")
    available = ["mpris", "clipboard", "router"]

    assert principal.filter_lanes(["clipboard"], available) == ["clipboard"]
    assert principal.filter_lanes(None, available) == available


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
        Principal.for_name("observer"),
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
            str(lane_paths["mpris"].parent),
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
        Principal.for_name("observer"),
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
            str(lane_paths["mpris"].parent),
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
        Principal.for_name("observer"),
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
        Principal.for_name("observer"),
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


def test_capture_read_without_a_lane_access_entry_is_a_config_error() -> None:
    from sinnix_agent_gateway import capabilities as caps

    original = dict(caps.PRINCIPAL_LANE_ACCESS)
    caps.PRINCIPAL_CAPABILITIES["fixture-principal"] = frozenset(
        {Capability.CAPTURE_READ}
    )
    try:
        with pytest.raises(PolicyError, match="no PRINCIPAL_LANE_ACCESS entry"):
            Principal.for_name("fixture-principal")
    finally:
        del caps.PRINCIPAL_CAPABILITIES["fixture-principal"]
        caps.PRINCIPAL_LANE_ACCESS.clear()
        caps.PRINCIPAL_LANE_ACCESS.update(original)
