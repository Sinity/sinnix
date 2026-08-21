from __future__ import annotations

import json
from pathlib import Path

import pytest
from sinnix_agent_gateway.capabilities import Capability, PolicyError, Principal
from sinnix_agent_gateway.captures import CaptureService
from sinnix_agent_gateway.config import GatewayConfig


def make_lake(root: Path) -> None:
    for lane, records in {
        "mpris": [{"lane": "mpris", "payload": {"title": "song"}}],
        "clipboard": [{"lane": "clipboard", "payload": {"text": "secret"}}],
        "router": [{"lane": "router", "payload": {"bytes": 100}}],
    }.items():
        lane_dir = root / lane
        lane_dir.mkdir(parents=True)
        (lane_dir / "2026-08-13.jsonl").write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )


def config(tmp_path: Path) -> GatewayConfig:
    root = tmp_path / "captures"
    make_lake(root)
    return GatewayConfig(state_dir=tmp_path / "state", projects={}, captures_root=root)


@pytest.mark.parametrize("principal_name", ("observer", "agent-control", "operator"))
def test_principals_have_full_operator_authorized_capture_read_access(
    principal_name: str,
) -> None:
    principal = Principal.for_name(principal_name)

    assert principal.allowed_lanes is None
    principal.require_lane("clipboard")


def test_capture_lanes_tool_lists_every_authorized_lane(tmp_path: Path) -> None:
    service = CaptureService(config(tmp_path), Principal.for_name("observer"))

    result = service.lanes_visible()

    assert result["lanes"] == ["clipboard", "mpris", "router"]
    assert result["total_lanes_on_disk"] == 3


def test_filter_lanes_returns_requested_or_all_authorized_lanes() -> None:
    principal = Principal.for_name("observer")
    available = ["mpris", "clipboard", "router"]

    assert principal.filter_lanes(["clipboard"], available) == ["clipboard"]
    assert principal.filter_lanes(None, available) == available


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
