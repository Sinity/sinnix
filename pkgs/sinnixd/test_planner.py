from pathlib import Path
from types import SimpleNamespace

import pytest
from sinnixd import planner


def snapshot(
    group: str,
    keys: tuple[str, ...],
    *,
    inferred: tuple[str, ...] = (),
    atlas=(),
    checks=("check",),
):
    return SimpleNamespace(
        group=group,
        bead_ids=(group,),
        atlas_refs=atlas,
        dimensions=SimpleNamespace(
            conflict_keys=keys,
            inferred_conflict_keys=inferred,
            verification_commands=checks,
        ),
    )


def test_dispatch_plan_orders_groups_and_marks_review_gates(
    monkeypatch, tmp_path: Path
):
    roots = {"sinnix": tmp_path}
    monkeypatch.setattr(planner.PacketConfig, "load", lambda root: object())
    monkeypatch.setattr(
        planner,
        "SubprocessBdReader",
        lambda root: SimpleNamespace(ready=lambda: [{"id": "b"}, {"id": "a"}]),
    )
    snapshots = {
        "a": snapshot(
            "a",
            ("module:reactor",),
            inferred=("module:reactor",),
            atlas=("docs/atlas/x.md",),
        ),
        "b": snapshot("b", ("module:reactor",), checks=()),
    }
    monkeypatch.setattr(
        planner, "compile_launch_snapshot", lambda bead_id, **_: snapshots[bead_id]
    )
    monkeypatch.setattr(
        planner,
        "derived_workspace",
        lambda snap, config: (f"packet-{snap.group}", f"feature/{snap.group}"),
    )

    plan = planner.build_dispatch_plan(roots)

    assert [row["group"] for row in plan["groups"]] == ["a", "b"]
    assert plan["groups"][0]["orbit"] == "module"
    assert plan["groups"][0]["judgment_gate"] == ["atlas-context", "inferred-conflicts"]
    assert plan["groups"][1]["judgment_gate"] == ["missing-verification"]
    assert plan["edges"] == [["a", "b"]]
    assert len(plan["generation"]) == 32


def test_planner_rejects_non_positive_limit(tmp_path: Path):
    with pytest.raises(ValueError, match="positive"):
        planner.build_dispatch_plan({"sinnix": tmp_path}, limit=0)
