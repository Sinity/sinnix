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

ROUND_ROBIN_ORDER = [
    "opt-hub-page",
    "opt-phone-deck",
    "opt-cli-only",
    "opt-nothing",
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

    def next_set(self, domain: str, *flags: str) -> dict:
        return json.loads(self.ok("next", domain, "--json", *flags).stdout)

    def status(self, domain: str, *flags: str) -> dict:
        return json.loads(
            self.ok("status", domain, "--json", "--seed", "7", *flags).stdout
        )

    def order(self, domain: str) -> list[str]:
        return [entry["id"] for entry in self.status(domain)["items"]]

    def matches(self, domain: str) -> dict[str, float]:
        return {entry["id"]: entry["matches"] for entry in self.status(domain)["items"]}

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
    assert [entry["id"] for entry in report["items"]] == ROUND_ROBIN_ORDER
    assert all(entry["se"] > 0 for entry in report["items"])
    assert all(entry["matches"] == 3 for entry in report["items"])
    assert 0.0 < report["stability"]["p_stable"] < 1.0
    assert report["evidence"]["connected"] is True
    assert report["evidence"]["unjudged_items"] == []

    # Six comparisons over four options do not reach the stopping threshold,
    # and the report says so with the measured number rather than a flag.
    assert report["evidence"]["settled"] is False
    assert report["evidence"]["reasons"] == [
        f"top-1 stability {report['stability']['p_stable']:.0%} is below the "
        f"{report['evidence']['stop_at']:.0%} threshold"
    ]


def test_next_offers_a_registered_pair_and_recording_it_extends_the_evidence(
    rank: Rank,
):
    assert rank.add("loop", FOUR_OPTIONS).returncode == 0
    offered = rank.next_set("loop", "--seed", "3")

    ids = [entry["id"] for entry in offered["set"]]
    labels = [entry["label"] for entry in offered["set"]]
    assert len(ids) == 2
    assert set(ids) <= {item_id for item_id, _ in FOUR_OPTIONS}
    assert labels == [dict(FOUR_OPTIONS)[item_id] for item_id in ids], (
        "the pair carries the operator-facing labels, not bare ids"
    )

    rank.record("loop", ids[0], ids[1], ids[0])
    evidence = rank.status("loop")["evidence"]
    assert evidence["operator_comparisons"] == 1
    assert sorted(evidence["unjudged_items"]) == sorted(
        item_id for item_id, _ in FOUR_OPTIONS if item_id not in ids
    )


def test_a_longer_agreeing_pass_reaches_a_settled_stop(rank: Rank):
    seed_round_robin(rank, "settled")
    for _ in range(6):
        for challenger in ("opt-phone-deck", "opt-cli-only", "opt-nothing"):
            rank.record("settled", "opt-hub-page", challenger, "opt-hub-page")

    report = rank.status("settled")
    assert report["evidence"]["operator_comparisons"] == len(ROUND_ROBIN) + 18
    assert report["stability"]["p_stable"] >= report["evidence"]["stop_at"]
    assert report["evidence"]["reasons"] == []
    assert report["evidence"]["settled"] is True
    assert [entry["id"] for entry in report["items"]] == ROUND_ROBIN_ORDER


def test_reversing_one_decisive_comparison_changes_the_order(rank: Rank):
    seed_round_robin(rank, "forward")
    seed_round_robin(rank, "flipped", flip=("opt-phone-deck", "opt-cli-only"))

    assert rank.order("forward") == ROUND_ROBIN_ORDER
    assert rank.order("flipped") == [
        "opt-hub-page",
        "opt-cli-only",
        "opt-phone-deck",
        "opt-nothing",
    ]


# -- criterion 2: reinvocation resumes ---------------------------------------


def test_reinvocation_resumes_without_duplicating_items_or_evidence(rank: Rank):
    seed_round_robin(rank, "resume")
    first_items = rank.item_ids("resume")
    first_comparisons = rank.comparison_ids("resume")
    first_report = rank.status("resume")

    # The skill's documented resume step: re-register the same roster, then
    # keep going.
    again = rank.add("resume", FOUR_OPTIONS)
    assert again.returncode == 0
    assert "added 0 new item(s)" in again.stdout

    assert rank.item_ids("resume") == first_items
    assert rank.comparison_ids("resume") == first_comparisons
    assert rank.status("resume")["items"] == first_report["items"]

    rank.record("resume", "opt-hub-page", "opt-cli-only", "opt-hub-page")
    assert rank.comparison_ids("resume")[: len(first_comparisons)] == first_comparisons
    assert (
        rank.status("resume")["evidence"]["operator_comparisons"]
        == len(ROUND_ROBIN) + 1
    )


# -- criterion 3: identity collisions ----------------------------------------


def test_duplicate_label_is_refused_and_records_are_not_merged(rank: Rank):
    seed_round_robin(rank, "labels")
    before = rank.comparison_ids("labels")
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

    # The same-label twin is a separate identity: it inherits none of the
    # comparisons recorded against the option it reads like.
    assert rank.comparison_ids("labels") == before
    assert rank.matches("labels") == {
        "opt-hub-page": 3,
        "opt-phone-deck": 3,
        "opt-cli-only": 3,
        "opt-nothing": 3,
        "opt-hub-page-2": 0,
    }


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
    assert rank.matches("revision")["opt-hub-page"] == 3
    assert rank.matches("revision")["opt-hub-page-v2"] == 0

    revised = rank.add(
        "revision", [("opt-phone-deck", "Ship it as a phone deck")], "--revise"
    )
    assert revised.returncode == 0
    labels = {entry["id"]: entry["label"] for entry in rank.status("revision")["items"]}
    assert labels["opt-phone-deck"] == "Ship it as a phone deck"
    assert rank.matches("revision")["opt-phone-deck"] == 3


# -- criterion 4: disconnected / insufficient evidence -----------------------


def seed_two_components(rank: Rank, domain: str) -> None:
    assert rank.add(domain, FOUR_OPTIONS).returncode == 0
    rank.record(domain, "opt-hub-page", "opt-phone-deck", "opt-hub-page")
    rank.record(domain, "opt-cli-only", "opt-nothing", "opt-cli-only")


def test_disconnected_evidence_is_reported_and_never_settled(rank: Rank):
    seed_two_components(rank, "split")
    report = rank.status("split")
    evidence = report["evidence"]

    assert evidence["components"] == 2
    assert evidence["connected"] is False
    assert evidence["settled"] is False
    assert any("disconnected" in reason for reason in evidence["reasons"])
    # The component field is what tells a reader which parts of the printed
    # order are mutually comparable at all. Its numbering is an arbitrary
    # label; the partition is the claim.
    component = {entry["id"]: entry["component"] for entry in report["items"]}
    assert component["opt-hub-page"] == component["opt-phone-deck"]
    assert component["opt-cli-only"] == component["opt-nothing"]
    assert component["opt-hub-page"] != component["opt-cli-only"]


def test_a_cross_component_comparison_connects_the_graph(rank: Rank):
    seed_two_components(rank, "bridge")
    before = rank.comparison_ids("bridge")

    # The skill's documented fix: ask one comparison across the two
    # components named by the `component` field.
    rank.record("bridge", "opt-phone-deck", "opt-cli-only", "opt-phone-deck")

    evidence = rank.status("bridge")["evidence"]
    assert evidence["components"] == 1
    assert evidence["connected"] is True
    assert not any("disconnected" in reason for reason in evidence["reasons"])
    assert rank.comparison_ids("bridge")[: len(before)] == before


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


def roster_names(roster: Path) -> list[str]:
    """The roster is a Nix list of bare strings, one per line."""
    return re.findall(r'^\s*"([^"]+)"\s*$', roster.read_text(), flags=re.MULTILINE)


def test_skill_is_installed_through_the_shared_roster(tmp_path: Path):
    assert SKILL_DIR.is_dir(), "the skill source directory must exist"
    assert "rank-options" in roster_names(ROSTER), (
        f"{ROSTER} does not list rank-options; the shared skill farm installs "
        f"only rostered names, so the directory alone ships nothing"
    )

    # The membership predicate reads the roster, not the directory: with the
    # entry dropped it reports absence even though the source tree is intact.
    dropped = tmp_path / "shared-agent-skills.nix"
    dropped.write_text(
        "\n".join(
            line
            for line in ROSTER.read_text().splitlines()
            if line.strip() != '"rank-options"'
        )
    )
    assert dropped.read_text() != ROSTER.read_text()
    assert "rank-options" not in roster_names(dropped)
    assert SKILL_DIR.is_dir()


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


def text_contains(root: Path, needle: str) -> list[str]:
    hits = []
    for path in root.rglob("*"):
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


def seed_private_options(rank: Rank, canary: str) -> None:
    options = [(f"opt-private-{i}", f"{canary} option {i}") for i in range(1, 5)]
    assert rank.add("private", options).returncode == 0
    rank.record("private", options[0][0], options[1][0], options[0][0])
    rank.record("private", options[1][0], options[2][0], options[1][0])
    rank.record("private", options[2][0], options[3][0], options[2][0])


def test_private_option_text_stays_out_of_the_tree(rank: Rank, tmp_path: Path):
    canary = f"canary-{uuid.uuid4().hex}"
    seed_private_options(rank, canary)

    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(rank.status("private"), indent=2))

    # The canary really is in the local state and in the report, so the
    # absence check below is about where it went, not about whether it was
    # ever used.
    assert canary in (rank.root / "private" / "items.jsonl").read_text()
    assert canary in report_path.read_text()

    # The scan finds a canary a file does carry, so finding none in the
    # repository is a fact about the repository.
    planted = tmp_path / "planted" / "options.jsonl"
    planted.parent.mkdir()
    planted.write_text(f'{{"id": "opt-leak", "label": "{canary} option 1"}}\n')
    assert text_contains(planted.parent, canary) == [str(planted)]

    assert text_contains(REPO_ROOT, canary) == []


def test_private_option_text_stays_out_of_the_diff(rank: Rank):
    git = shutil.which("git")
    if git is None or not (REPO_ROOT / ".git").exists():
        pytest.skip("no git checkout to diff")

    canary = f"canary-{uuid.uuid4().hex}"
    seed_private_options(rank, canary)

    for argv in (
        [git, "-C", str(REPO_ROOT), "status", "--porcelain"],
        [git, "-C", str(REPO_ROOT), "diff"],
        [git, "-C", str(REPO_ROOT), "diff", "--cached"],
    ):
        out = subprocess.run(argv, capture_output=True, text=True, timeout=120).stdout
        assert canary not in out, f"{argv} leaked the canary"
