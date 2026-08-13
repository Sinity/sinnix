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


def test_remote_readonly_cannot_see_clipboard_lane(tmp_path: Path) -> None:
    """sinnix-lpuv's actual point: remote-readonly is served over the
    OpenAI tunnel to ChatGPT, an external channel -- it must never see
    content-bearing lanes even though it holds CAPTURE_READ."""
    principal = Principal.for_profile("remote-readonly")
    assert principal.allowed_lanes is not None
    assert "clipboard" not in principal.allowed_lanes
    assert "mpris" in principal.allowed_lanes

    with pytest.raises(PolicyError):
        principal.require_lane("clipboard")

    principal.require_lane("mpris")  # does not raise


def test_local_agent_control_and_remote_operator_are_unrestricted() -> None:
    for profile in ("local-agent-control", "remote-operator"):
        principal = Principal.for_profile(profile)
        assert principal.allowed_lanes is None
        principal.require_lane("clipboard")  # does not raise


def test_capture_lanes_tool_lists_only_allowed_lanes_not_every_lane_on_disk(
    tmp_path: Path,
) -> None:
    cfg = config(tmp_path)
    principal = Principal.for_profile("remote-readonly")
    service = CaptureService(cfg, principal)

    result = service.lanes_visible()

    assert result["lanes"] == ["mpris", "router"]  # not clipboard
    assert result["total_lanes_on_disk"] == 3  # honest about what exists but isn't shown


def test_filter_lanes_denies_explicit_out_of_scope_request_rather_than_silently_dropping(
    tmp_path: Path,
) -> None:
    cfg = config(tmp_path)
    principal = Principal.for_profile("remote-readonly")

    # An explicit ask for a denied lane is a policy error, not a silently
    # empty/filtered result -- the caller should learn it asked for
    # something out of scope, not get a confusingly incomplete answer.
    with pytest.raises(PolicyError):
        principal.filter_lanes(["clipboard"], ["mpris", "clipboard", "router"])

    # Mixing an allowed and a denied lane in one request is still a hard
    # error on the whole request, not a partial silent success.
    with pytest.raises(PolicyError):
        principal.filter_lanes(["mpris", "clipboard"], ["mpris", "clipboard", "router"])

    # Omitting `lanes` entirely resolves to everything the profile may see.
    assert principal.filter_lanes(None, ["mpris", "clipboard", "router"]) == [
        "mpris",
        "router",
    ]


def test_capture_read_without_a_lane_access_entry_is_a_config_error() -> None:
    """A profile granted CAPTURE_READ in PROFILE_CAPABILITIES but missing
    from PROFILE_LANE_ACCESS is an oversight worth failing loudly on, not a
    silent unrestricted/denied default -- catches exactly the class of bug
    this bead exists to prevent (a new profile added later that forgets the
    lane-permission side of the model)."""
    from sinnix_agent_gateway import capabilities as caps

    original = dict(caps.PROFILE_LANE_ACCESS)
    caps.PROFILE_CAPABILITIES["fixture-profile"] = frozenset({Capability.CAPTURE_READ})
    try:
        with pytest.raises(PolicyError, match="no PROFILE_LANE_ACCESS entry"):
            Principal.for_profile("fixture-profile")
    finally:
        del caps.PROFILE_CAPABILITIES["fixture-profile"]
        caps.PROFILE_LANE_ACCESS.clear()
        caps.PROFILE_LANE_ACCESS.update(original)
