from __future__ import annotations

import runpy
import stat
from pathlib import Path

MODULE = runpy.run_path(
    str(Path(__file__).parents[3] / "scripts" / "sinnix-quest-player")
)


def test_player_state_is_private_durable_json(tmp_path: Path) -> None:
    path = tmp_path / "state" / "player-session.json"
    MODULE["write_json"](path, {"z": 1, "a": ["session"]})

    assert MODULE["read_json"](path) == {"a": ["session"], "z": 1}
    assert path.read_text(encoding="utf-8") == '{"a":["session"],"z":1}\n'
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_unreadable_player_state_is_reported_as_unavailable(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    try:
        MODULE["read_json"](path)
    except OSError as error:
        assert str(path) in str(error)
    else:
        raise AssertionError("missing player state was accepted")
