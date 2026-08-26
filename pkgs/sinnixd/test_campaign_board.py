from datetime import UTC, datetime
from pathlib import Path

from sinnixd.campaign_board import (
    BOARD_SCHEMA_VERSION,
    build_campaign_board,
    load_or_refresh_campaign_board,
)


def _fleet() -> dict[str, object]:
    return {"rows": [{
        "job_id": "job-1", "project": "polylogue", "branch": "feature/lane",
        "bead": "sinnix://projects/polylogue/beads/polylogue-abc",
        "phase": "running", "terminal": False,
    }]}


def test_board_is_a_live_join_and_never_invents_unknown_prs(tmp_path: Path) -> None:
    board = build_campaign_board(
        state_dir=tmp_path / "state",
        project_roots={},
        now=datetime(2026, 8, 26, tzinfo=UTC),
        fleet=_fleet(),
        pull_requests={"polylogue": [
            {"repo": "Sinity/polylogue", "number": 4,
             "headRefName": "feature/lane", "state": "OPEN"},
            {"repo": "Sinity/polylogue", "number": 5,
             "headRefName": "gone", "state": "OPEN"},
        ]},
        beads={"polylogue": {"polylogue-abc": {"id": "polylogue-abc", "status": "open"}}},
    )
    assert board["schema_version"] == BOARD_SCHEMA_VERSION
    assert set(board["lanes"]) == {"job-1"}
    assert set(board["prs"]) == {"Sinity/polylogue#4", "Sinity/polylogue#5"}
    assert board["prs"]["Sinity/polylogue#4"]["bead_status"] == "open"
    assert "unknown" not in board["prs"]


def test_board_cache_uses_recent_render_until_forced(tmp_path: Path) -> None:
    path = tmp_path / "board.json"
    kwargs = {"state_dir": tmp_path / "state", "project_roots": {}, "fleet": _fleet(),
              "pull_requests": {}, "beads": {}}
    first = load_or_refresh_campaign_board(path, **kwargs)
    cached = load_or_refresh_campaign_board(path, **{**kwargs, "fleet": {"rows": []}})
    assert cached == first
    refreshed = load_or_refresh_campaign_board(
        path, force=True, **{**kwargs, "fleet": {"rows": []}}
    )
    assert refreshed["lanes"] == {}
