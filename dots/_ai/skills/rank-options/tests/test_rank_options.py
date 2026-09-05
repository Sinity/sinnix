"""The rank-options workflow, driven exactly as the skill instructs.

Every assertion goes through the shipped `scripts/sinnix-rank` process rather
than importing `rank_core` directly: the skill's contract is the CLI's
behaviour -- its identity refusals, its evidence block, its exit codes -- and
a test that reached past the CLI would pass while the documented commands
were broken.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
SKILLS_ROOT = SKILL_DIR.parent
REPO_ROOT = Path(os.environ.get("SINNIX_REPO_ROOT", SKILLS_ROOT.parents[2]))
RANK = REPO_ROOT / "scripts" / "sinnix-rank"
RANK_CORE = REPO_ROOT / "pkgs" / "sinnix-rank-core"
ROSTER = REPO_ROOT / "flake" / "data" / "shared-agent-skills.nix"
VALIDATOR = SKILLS_ROOT / "skill-authoring" / "scripts" / "validate_skill.py"

FOUR_OPTIONS = [
    ("opt-hub-page", "Render the comparison as a hub page"),
    ("opt-phone-deck", "Ship it as a phone drill deck"),
    ("opt-cli-only", "Keep it a terminal-only pass"),
    ("opt-nothing", "Do not build a comparison surface at all"),
]

# A round robin over the four options: every pair judged once, so the fit is
# connected and every item carries evidence.
ROUND_ROBIN = [
    ("opt-hub-page", "opt-phone-deck", "opt-hub-page"),
    ("opt-hub-page", "opt-cli-only", "opt-hub-page"),
    ("opt-hub-page", "opt-nothing", "opt-hub-page"),
    ("opt-phone-deck", "opt-cli-only", "opt-phone-deck"),
    ("opt-phone-deck", "opt-nothing", "opt-phone-deck"),
    ("opt-cli-only", "opt-nothing", "opt-cli-only"),
]


class Rank:
    """One `SINNIX_RANK_ROOT` and the CLI calls made against it."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.env = dict(os.environ)
        self.env["SINNIX_RANK_ROOT"] = str(root)
        self.env["PYTHONPATH"] = str(RANK_CORE)

    def run(self, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(RANK), *argv],
            capture_output=True,
            text=True,
            env=self.env,
            timeout=120,
        )

    def ok(self, *argv: str) -> subprocess.CompletedProcess:
        result = self.run(*argv)
        assert result.returncode == 0, f"{argv} failed: {result.stderr}"
        return result

    def add(self, domain: str, options, *flags: str) -> subprocess.CompletedProcess:
        path = self.root / f"{domain}-items.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(
                json.dumps({"id": item_id, "label": label}) + "\n"
                for item_id, label in options
            )
        )
        return self.run("add", domain, "--items", str(path), *flags)

    def record(self, domain: str, left: str, right: str, winner: str) -> str:
        return self.ok(
            "record", domain, "--set", f"{left},{right}", "--winner", winner
        ).stdout.strip()

    def status(self, domain: str, *flags: str) -> dict:
        return json.loads(
            self.ok("status", domain, "--json", "--seed", "7", *flags).stdout
        )

    def order(self, domain: str) -> list[str]:
        return [entry["id"] for entry in self.status(domain)["items"]]

    def comparison_ids(self, domain: str) -> list[str]:
        path = self.root / domain / "comparisons.jsonl"
        return [
            json.loads(line)["id"]
            for line in path.read_text().splitlines()
            if line.strip()
        ]

    def item_ids(self, domain: str) -> list[str]:
        path = self.root / domain / "items.jsonl"
        return [
            json.loads(line)["id"]
            for line in path.read_text().splitlines()
            if line.strip()
        ]


@pytest.fixture
def rank(tmp_path: Path) -> Rank:
    return Rank(tmp_path / "ranking")


def seed_round_robin(
    rank: Rank, domain: str, *, flip: tuple[str, str] | None = None
) -> None:
    assert rank.add(domain, FOUR_OPTIONS).returncode == 0
    for left, right, winner in ROUND_ROBIN:
        if flip == (left, right):
            winner = right if winner == left else left
        rank.record(domain, left, right, winner)


# -- criterion 1: cold fixture -> stable ids, real comparisons, fitted order --


def test_cold_fixture_produces_a_fitted_order_with_uncertainty_and_stopping(rank: Rank):
    seed_round_robin(rank, "cold")
    report = rank.status("cold")

    assert rank.item_ids("cold") == [item_id for item_id, _ in FOUR_OPTIONS]
    assert report["evidence"]["operator_comparisons"] == len(ROUND_ROBIN)
    assert [entry["id"] for entry in report["items"]] == [
        "opt-hub-page",
        "opt-phone-deck",
        "opt-cli-only",
        "opt-nothing",
    ]
    assert all(entry["se"] > 0 for entry in report["items"])
    assert 0.0 <= report["stability"]["p_stable"] <= 1.0
    assert report["evidence"]["connected"] is True
    assert report["evidence"]["unjudged_items"] == []
    assert isinstance(report["evidence"]["settled"], bool)


def test_reversing_one_decisive_comparison_changes_the_order(rank: Rank):
    seed_round_robin(rank, "forward")
    seed_round_robin(rank, "flipped", flip=("opt-phone-deck", "opt-cli-only"))
    assert rank.order("forward") != rank.order("flipped")


# -- criterion 2: reinvocation resumes ---------------------------------------


def test_reinvocation_resumes_without_duplicating_items_or_evidence(rank: Rank):
    seed_round_robin(rank, "resume")
    first_items = rank.item_ids("resume")
    first_comparisons = rank.comparison_ids("resume")

    # The skill's documented resume step: re-register the same roster, then
    # keep going.
    again = rank.add("resume", FOUR_OPTIONS)
    assert again.returncode == 0
    assert "added 0 new item(s)" in again.stdout

    assert rank.item_ids("resume") == first_items
    assert rank.comparison_ids("resume") == first_comparisons

    rank.record("resume", "opt-hub-page", "opt-cli-only", "opt-hub-page")
    assert rank.comparison_ids("resume")[: len(first_comparisons)] == first_comparisons
    assert (
        rank.status("resume")["evidence"]["operator_comparisons"]
        == len(ROUND_ROBIN) + 1
    )


# -- criterion 3: identity collisions ----------------------------------------


def test_duplicate_label_is_refused_and_records_are_not_merged(rank: Rank):
    seed_round_robin(rank, "labels")
    collision = rank.add("labels", [("opt-hub-page-2", FOUR_OPTIONS[0][1])])

    assert collision.returncode == 2
    assert "already item opt-hub-page" in collision.stderr
    assert rank.item_ids("labels") == [item_id for item_id, _ in FOUR_OPTIONS]

    allowed = rank.add(
        "labels",
        [("opt-hub-page-2", FOUR_OPTIONS[0][1])],
        "--allow-duplicate-labels",
    )
    assert allowed.returncode == 0
    ids = rank.item_ids("labels")
    assert ids.count("opt-hub-page") == 1
    assert ids.count("opt-hub-page-2") == 1


def test_changed_option_under_an_existing_id_is_refused(rank: Rank):
    seed_round_robin(rank, "revision")
    before = rank.item_ids("revision")

    changed = rank.add("revision", [("opt-hub-page", "A different option entirely")])
    assert changed.returncode == 2
    assert "--revise" in changed.stderr
    assert rank.item_ids("revision") == before

    # A new option takes a new id; the old id's comparisons keep their meaning.
    fresh = rank.add("revision", [("opt-hub-page-v2", "A different option entirely")])
    assert fresh.returncode == 0
    assert rank.item_ids("revision")[-1] == "opt-hub-page-v2"
    assert rank.status("revision")["evidence"]["operator_comparisons"] == len(
        ROUND_ROBIN
    )

    revised = rank.add(
        "revision", [("opt-phone-deck", "Ship it as a phone deck")], "--revise"
    )
    assert revised.returncode == 0
    labels = {entry["id"]: entry["label"] for entry in rank.status("revision")["items"]}
    assert labels["opt-phone-deck"] == "Ship it as a phone deck"


# -- criterion 4: disconnected / insufficient evidence -----------------------


def test_disconnected_evidence_is_reported_and_never_settled(rank: Rank):
    assert rank.add("split", FOUR_OPTIONS).returncode == 0
    rank.record("split", "opt-hub-page", "opt-phone-deck", "opt-hub-page")
    rank.record("split", "opt-cli-only", "opt-nothing", "opt-cli-only")

    evidence = rank.status("split")["evidence"]
    assert evidence["components"] == 2
    assert evidence["connected"] is False
    assert evidence["settled"] is False
    assert any("disconnected" in reason for reason in evidence["reasons"])


def test_no_comparisons_is_reported_as_no_evidence(rank: Rank):
    assert rank.add("empty", FOUR_OPTIONS).returncode == 0
    evidence = rank.status("empty")["evidence"]

    assert evidence["operator_comparisons"] == 0
    assert evidence["settled"] is False
    assert sorted(evidence["unjudged_items"]) == sorted(
        item_id for item_id, _ in FOUR_OPTIONS
    )
    assert any("no operator comparisons" in reason for reason in evidence["reasons"])


def test_status_text_output_names_the_unsettled_reasons(rank: Rank):
    assert rank.add("prose", FOUR_OPTIONS).returncode == 0
    rank.record("prose", "opt-hub-page", "opt-phone-deck", "opt-hub-page")
    text = Rank.ok(rank, "status", "prose").stdout

    assert "NOT settled" in text
    assert "disconnected comparison components" in text


# -- criterion 5: installed through the shared roster ------------------------


def roster_names() -> list[str]:
    return re.findall(r'"([^"]+)"', ROSTER.read_text())


def test_skill_is_installed_through_the_shared_roster():
    assert SKILL_DIR.is_dir(), "the skill source directory must exist"
    assert "rank-options" in roster_names(), (
        f"{ROSTER} does not list rank-options; the shared skill farm installs "
        f"only rostered names, so the directory alone ships nothing"
    )


def test_skill_passes_package_validation():
    findings = json.loads(
        subprocess.run(
            [sys.executable, str(VALIDATOR), str(SKILLS_ROOT)],
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout
    )["findings"]
    mine = [f for f in findings if "rank-options" in f["path"]]
    assert mine == []


# -- criterion 6: private option text never reaches tracked output -----------


def repo_text_contains(needle: str) -> list[str]:
    hits = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if ".git" in path.parts:
            continue
        try:
            if needle in path.read_text(encoding="utf-8", errors="ignore"):
                hits.append(str(path))
        except OSError:
            continue
    return hits


def test_private_option_text_stays_in_local_ranking_state(rank: Rank, tmp_path: Path):
    canary = f"canary-{uuid.uuid4().hex}"
    options = [(f"opt-private-{i}", f"{canary} option {i}") for i in range(1, 5)]
    assert rank.add("private", options).returncode == 0
    rank.record("private", options[0][0], options[1][0], options[0][0])
    rank.record("private", options[1][0], options[2][0], options[1][0])
    rank.record("private", options[2][0], options[3][0], options[2][0])

    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(rank.status("private"), indent=2))

    # The canary really is in the local state, so the absence checks below are
    # about where it went, not about whether it was ever used.
    assert canary in (rank.root / "private" / "items.jsonl").read_text()
    assert canary in report_path.read_text()

    assert repo_text_contains(canary) == []

    git = shutil.which("git")
    if git is None or not (REPO_ROOT / ".git").exists():
        pytest.skip("no git checkout to diff")
    for argv in (
        [git, "-C", str(REPO_ROOT), "status", "--porcelain"],
        [git, "-C", str(REPO_ROOT), "diff"],
        [git, "-C", str(REPO_ROOT), "diff", "--cached"],
    ):
        out = subprocess.run(argv, capture_output=True, text=True, timeout=120).stdout
        assert canary not in out, f"{argv} leaked the canary"
