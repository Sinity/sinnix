"""The sweep's routing table and its derived, store-nothing pass."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sinnixd.publication_sweep import (
    PullState,
    decide,
    parse_trailers,
    sweep,
)

NOW = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)


def pull(**overrides: object) -> PullState:
    base: dict[str, object] = {
        "number": 7,
        "head": "a" * 40,
        "created_at": NOW.isoformat(),
        "mergeable": "MERGEABLE",
        "ci_red": False,
        "review_clean": False,
        "review_findings": 0,
        "bead_id": "polylogue-x1",
        "receipt_ref": "harvest-abc",
    }
    base.update(overrides)
    return PullState(**base)  # type: ignore[arg-type]


def test_trailers_roundtrip() -> None:
    bead, receipt = parse_trailers("body\n\n---\nReceipt: harvest-1\nBead: p-9\n")
    assert (bead, receipt) == ("p-9", "harvest-1")
    assert parse_trailers("no trailers here") == (None, None)


def test_clean_review_merges() -> None:
    assert decide(pull(review_clean=True), now=NOW) == "merge"


def test_findings_never_merge_even_with_thumbs_up() -> None:
    # A +1 alongside inline findings must not read as clean: the findings
    # are the review.
    verdict = decide(pull(review_clean=True, review_findings=3), now=NOW)
    assert verdict == "findings"


def test_conflict_and_ci_red_outrank_review() -> None:
    assert decide(pull(mergeable="CONFLICTING", review_clean=True), now=NOW) == (
        "conflict"
    )
    assert decide(pull(ci_red=True, review_clean=True), now=NOW) == "ci-red"


def test_young_pr_without_review_waits() -> None:
    assert decide(pull(), now=NOW + timedelta(minutes=5)) == "wait"


def test_absent_review_fails_open_after_grace() -> None:
    verdict = decide(pull(), now=NOW + timedelta(minutes=31))
    assert verdict == "merge-review-absent"


class FakeRun:
    """Answers the exact gh/bd invocations the sweep makes."""

    def __init__(self, pr_rows: list[dict[str, object]]) -> None:
        self.pr_rows = pr_rows
        self.merged: list[int] = []
        self.closed: list[str] = []

    def __call__(self, argv, **_kwargs):  # type: ignore[no-untyped-def]
        joined = " ".join(argv)
        if argv[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.pr_rows), "")
        if "reactions" in joined:
            return subprocess.CompletedProcess(argv, 0, json.dumps(["+1"]), "")
        if "comments" in joined:
            return subprocess.CompletedProcess(argv, 0, "0", "")
        if argv[:3] == ["gh", "pr", "merge"]:
            self.merged.append(int(argv[3]))
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[0] == "bd":
            self.closed.append(argv[2])
            return subprocess.CompletedProcess(argv, 0, "closed", "")
        raise AssertionError(f"unexpected command: {joined}")


def test_sweep_merges_clean_pr_and_closes_its_bead(tmp_path: Path) -> None:
    fake = FakeRun(
        [
            {
                "number": 41,
                "headRefOid": "b" * 40,
                "createdAt": NOW.isoformat(),
                "mergeable": "MERGEABLE",
                "body": "text\n\n---\nReceipt: harvest-9\nBead: polylogue-z2\n",
                "statusCheckRollup": [],
            },
            {
                # No Receipt trailer: not a harvest publication, untouched.
                "number": 42,
                "headRefOid": "c" * 40,
                "createdAt": NOW.isoformat(),
                "mergeable": "MERGEABLE",
                "body": "dependabot",
                "statusCheckRollup": [],
            },
        ]
    )
    receipt = sweep(
        "owner/repo",
        project="polylogue",
        project_root=tmp_path,
        spool=tmp_path / "events.jsonl",
        run=fake,
        now=NOW,
    )
    assert fake.merged == [41]
    assert fake.closed == ["polylogue-z2"]
    assert [action["verdict"] for action in receipt["actions"]] == ["merge"]
    events = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text().splitlines()
    ]
    assert events[0]["kind"] == "publication-sweep"
    assert events[0]["outcome"] == "merge"
    # Anti-vacuity: dropping the trailer filter would merge PR 42 and turn
    # fake.merged into [41, 42].
