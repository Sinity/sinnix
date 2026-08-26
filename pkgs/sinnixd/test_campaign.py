from __future__ import annotations

from sinnixd.campaign import (
    CampaignLane,
    build_schedule,
    dedupe_lanes,
    runnable_groups,
)


def lane(group: str, *keys: str, beads: tuple[str, ...] | None = None) -> CampaignLane:
    return CampaignLane(
        group,
        beads or (group,),
        keys,
        f"packet-{group}",
        f"feature/{group}",
        {"group": group},
    )


def test_dedupe_compiled_beads_into_one_carrier_lane() -> None:
    first = lane("carrier", "parser", beads=("carrier", "member"))
    assert dedupe_lanes([first, first]) == (first,)


def test_key_dag_is_deterministic_and_keeps_disjoint_roots() -> None:
    schedule = build_schedule(
        [lane("b", "shared"), lane("a", "shared"), lane("free", "other")]
    )

    assert schedule.node_ids() == ("a", "b", "free")
    assert schedule.edges == (("a", "b"),)


def test_active_workspace_and_bead_are_typed_skips() -> None:
    schedule = build_schedule(
        [lane("workspace"), lane("bead", beads=("bead", "member"))],
        active_workspace_names={"packet-workspace"},
        active_bead_ids={"member"},
    )

    assert [skip.code for skip in schedule.skipped] == [
        "active-bead",
        "active-workspace",
    ]
    assert schedule.lanes == ()


def test_running_lane_key_overlap_is_a_typed_skip_with_keys() -> None:
    schedule = build_schedule(
        [lane("candidate", "module:polylogue.cost", "table:jobs")],
        active_conflict_keys={"table:jobs"},
    )

    assert schedule.lanes == ()
    assert schedule.skipped[0].code == "conflict-key-overlap"
    assert "table:jobs" in schedule.skipped[0].reason


def test_failed_predecessor_frees_key_for_next_lane() -> None:
    schedule = build_schedule([lane("a", "shared"), lane("b", "shared")])
    assert runnable_groups(schedule, {"a": {"terminal": True, "phase": "failed"}}) == (
        "b",
    )
