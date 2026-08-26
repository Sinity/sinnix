from __future__ import annotations

import json
from pathlib import Path

from sinnixd.reactor import CampaignReactor


def append(path: Path, event: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


class FakeBeadCloser:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Path]] = []

    def close(self, bead_id: str, reason: str, *, cwd: Path) -> tuple[bool, str | None]:
        self.calls.append((bead_id, reason, cwd))
        return True, None


def test_reactor_persists_only_cursor(tmp_path: Path) -> None:
    spool = tmp_path / "events.jsonl"
    board = tmp_path / "campaign-board.json"
    reactor = CampaignReactor(spool, board, tmp_path / "reactor")
    append(spool, {"kind": "attested-agent", "job_id": "lane-1"})

    assert reactor.run_once() == 1
    assert not board.exists()
    assert (tmp_path / "reactor" / "cursor.json").exists()


def test_merge_reaction_still_closes_from_decision_receipt(tmp_path: Path) -> None:
    spool = tmp_path / "events.jsonl"
    board = tmp_path / "campaign-board.json"
    root = tmp_path / "polylogue"
    root.mkdir()
    closer = FakeBeadCloser()
    reactor = CampaignReactor(
        spool, board, tmp_path / "reactor", project_roots={"polylogue": root},
        bead_closer=closer,
    )
    append(spool, {
        "kind": "merge_close", "repo": "Sinity/polylogue", "pr": "42",
        "state": "MERGED", "decision_receipt": {
            "bead_id": "polylogue-abc", "reason": "verified merge",
        },
    })

    assert reactor.run_once() == 1
    assert closer.calls == [("polylogue-abc", "verified merge", root)]
    assert not board.exists()
