"""The keybind adapter's contract, driven through both scripts as processes."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from conftest import BINDINGS_NIX, FIXTURE_BINDINGS, FORGE, Adapter

DOMAIN = "keybinds"


def ids_by_chord(records) -> dict[str, str]:
    return {record["chord"]: record["id"] for record in records}


# -- criterion 1: stable identities ------------------------------------------


def test_ids_survive_reordering_and_unrelated_additions(adapter: Adapter):
    before = ids_by_chord(adapter.inventory_records())

    reordered = list(reversed(FIXTURE_BINDINGS))
    reordered.append(
        ("SUPER + P", "Show the process list", 'hl.dsp.exec_cmd("kitty -e btop")')
    )
    adapter.write_inventory(reordered)
    after = ids_by_chord(adapter.inventory_records())

    for chord, item_id in before.items():
        assert after[chord] == item_id
    assert "SUPER + P" in after


def test_ids_ignore_a_store_path_move_but_follow_the_declarative_identity(
    adapter: Adapter,
):
    before = ids_by_chord(adapter.inventory_records())

    rebuilt = [
        (chord, intent, action.replace("0" * 32, "1" * 32))
        for chord, intent, action in FIXTURE_BINDINGS
    ]
    adapter.write_inventory(rebuilt)
    assert ids_by_chord(adapter.inventory_records()) == before

    rechorded = [
        ("SUPER + SHIFT + O" if chord == "SUPER + O" else chord, intent, action)
        for chord, intent, action in FIXTURE_BINDINGS
    ]
    adapter.write_inventory(rechorded)
    changed = ids_by_chord(adapter.inventory_records())
    assert changed["SUPER + SHIFT + O"] != before["SUPER + O"]
    assert changed["SUPER + Q"] == before["SUPER + Q"]


def test_the_fixture_layout_matches_what_home_manager_renders(adapter: Adapter):
    live = Path.home() / ".config/hypr/hyprland.lua"
    if not live.is_file():
        return
    result = adapter.ok("--inventory", str(live), "inventory", "--json")
    records = json.loads(result.stdout)
    assert len(records) > 10
    assert all(record["chord"] and record["intent"] for record in records)


# -- criterion 2: usage priors are bounded, labelled, and honest about gaps ---


def test_absent_and_measured_zero_usage_are_distinct_records(adapter: Adapter):
    records = adapter.inventory_records()
    by_chord = ids_by_chord(records)
    adapter.write_usage({by_chord["SUPER + Q"]: 0})

    usage = json.loads((adapter.rank_root / DOMAIN / "usage-prior.json").read_text())[
        "records"
    ]

    measured = usage[by_chord["SUPER + Q"]]
    absent = usage[by_chord["SUPER + O"]]
    assert measured["state"] == "measured"
    assert measured["count"] == 0
    assert absent["state"] == "unavailable"
    assert absent["reason"]
    assert measured != absent


def test_usage_prior_is_bounded_and_carries_its_source(adapter: Adapter):
    by_chord = ids_by_chord(adapter.inventory_records())
    adapter.write_usage({by_chord["SUPER + O"]: 10_000_000, by_chord["SUPER + Q"]: 0})

    manifest = adapter.manifest()
    priors = {
        row["chord"]: row["provenance"]["prior_theta"] for row in manifest["bindings"]
    }
    assert priors["SUPER + O"] == manifest["usage_prior_cap"]
    assert priors["SUPER + Q"] == -manifest["usage_prior_cap"]
    assert priors["F7"] == 0.0  # unavailable is unknown, not zero-count

    for row in manifest["bindings"]:
        assert row["provenance"]["usage"]["state"] in ("measured", "unavailable")
        assert row["provenance"]["usage"]["source"]


def test_compositor_dispatches_report_usage_as_unavailable(adapter: Adapter):
    adapter.adapter("usage", "--source", "atuin", "--atuin-db", "/nonexistent.db")
    usage = json.loads((adapter.rank_root / DOMAIN / "usage-prior.json").read_text())[
        "records"
    ]
    by_chord = ids_by_chord(adapter.inventory_records())

    close_window = usage[by_chord["SUPER + Q"]]
    assert close_window["state"] == "unavailable"
    assert "compositor dispatch" in close_window["reason"]


# -- criterion 3: comparisons dominate a conflicting prior -------------------


def priority_of(manifest: dict, chord: str) -> float:
    return next(
        row["priority"] for row in manifest["bindings"] if row["chord"] == chord
    )


def value_of(manifest: dict, chord: str) -> float:
    return next(row["value"] for row in manifest["bindings"] if row["chord"] == chord)


def seed_opposite(adapter: Adapter, winner_chord: str, loser_chord: str) -> dict:
    adapter.adapter("sync")
    by_chord = ids_by_chord(adapter.inventory_records())
    adapter.write_usage({by_chord["SUPER + O"]: 500, by_chord["F7"]: 500})
    threshold = int(adapter.manifest()["evidence_threshold"])
    adapter.record(DOMAIN, by_chord[winner_chord], by_chord[loser_chord], threshold)
    return adapter.manifest()


def test_opposite_comparisons_flip_priority_under_identical_usage(tmp_path: Path):
    forward = seed_opposite(Adapter(tmp_path / "fwd"), "SUPER + O", "F7")
    reverse = seed_opposite(Adapter(tmp_path / "rev"), "F7", "SUPER + O")

    assert value_of(forward, "SUPER + O") > value_of(forward, "F7")
    assert value_of(reverse, "F7") > value_of(reverse, "SUPER + O")
    assert priority_of(forward, "SUPER + O") > priority_of(forward, "F7")
    assert priority_of(reverse, "F7") > priority_of(reverse, "SUPER + O")


def test_comparisons_displace_a_contradicting_usage_prior(adapter: Adapter):
    adapter.adapter("sync")
    by_chord = ids_by_chord(adapter.inventory_records())
    # Usage says SUPER + O is the one; the operator says otherwise, repeatedly.
    adapter.write_usage({by_chord["SUPER + O"]: 5000, by_chord["F7"]: 1})

    prior_only = adapter.manifest()
    assert value_of(prior_only, "SUPER + O") > value_of(prior_only, "F7")
    assert (
        next(r for r in prior_only["bindings"] if r["chord"] == "F7")["provenance"][
            "basis"
        ]
        == "usage-prior"
    )

    threshold = int(prior_only["evidence_threshold"])
    adapter.record(DOMAIN, by_chord["F7"], by_chord["SUPER + O"], threshold)

    after = adapter.manifest()
    assert value_of(after, "F7") > value_of(after, "SUPER + O")
    row = next(r for r in after["bindings"] if r["chord"] == "F7")
    assert row["provenance"]["basis"] == "comparisons"
    assert row["provenance"]["evidence_weight"] == 1.0
    assert row["provenance"]["usage"]["count"] == 1  # the prior is kept, not erased


# -- criterion 4: only current bindings, with their real fields --------------


def test_manifest_rows_carry_chord_action_intent_priority_uncertainty_provenance(
    adapter: Adapter,
):
    adapter.adapter("sync")
    manifest = adapter.manifest()
    actions = {chord: action for chord, _, action in FIXTURE_BINDINGS}

    assert len(manifest["bindings"]) == len(FIXTURE_BINDINGS)
    for row in manifest["bindings"]:
        assert row["action"] == actions[row["chord"]]
        assert row["intent"]
        assert isinstance(row["priority"], float)
        assert row["uncertainty"] > 0
        assert set(row["provenance"]) >= {
            "basis",
            "evidence_weight",
            "comparisons",
            "prior_theta",
            "usage",
        }
    priorities = [row["priority"] for row in manifest["bindings"]]
    assert priorities == sorted(priorities, reverse=True)


def test_a_deleted_binding_leaves_the_manifest_though_its_ranking_state_remains(
    adapter: Adapter,
):
    adapter.adapter("sync")
    by_chord = ids_by_chord(adapter.inventory_records())
    retired = by_chord["SUPER + V"]
    adapter.record(DOMAIN, retired, by_chord["SUPER + Q"], 4)
    assert retired in {row["id"] for row in adapter.manifest()["bindings"]}

    adapter.write_inventory([b for b in FIXTURE_BINDINGS if b[0] != "SUPER + V"])
    manifest = adapter.manifest()

    assert retired not in {row["id"] for row in manifest["bindings"]}
    assert "SUPER + V" not in {row["chord"] for row in manifest["bindings"]}
    # The evidence is still on disk; only the manifest dropped it.
    items = (adapter.rank_root / DOMAIN / "items.jsonl").read_text()
    comparisons = (adapter.rank_root / DOMAIN / "comparisons.jsonl").read_text()
    assert retired in items
    assert retired in comparisons


# -- criterion 5: deck-forge consumes the manifest deterministically ---------


def forge_deck(adapter: Adapter, manifest_path: Path, seed: str = "11") -> dict:
    result = adapter.ok(
        "--dry-run",
        "--seed",
        seed,
        "--trials",
        "4",
        "--manifest",
        str(manifest_path),
        "keybinds",
        script=FORGE,
    )
    return json.loads(result.stdout)


def test_deck_forge_promotes_the_top_manifest_entries_in_order(adapter: Adapter):
    adapter.adapter("sync")
    manifest_path = adapter.tmp / "manifest.json"
    adapter.adapter("manifest", "--output", str(manifest_path))
    manifest = json.loads(manifest_path.read_text())

    deck = forge_deck(adapter, manifest_path)
    assert deck["engine"] == "forced_choice"
    assert [trial["prompt"] for trial in deck["trials"]] == [
        f"What does {row['chord']} do?" for row in manifest["bindings"][:4]
    ]
    for trial in deck["trials"]:
        assert trial["options"][trial["correct"]] in {
            row["intent"] for row in manifest["bindings"]
        }
        assert len(set(trial["options"])) == 4

    assert forge_deck(adapter, manifest_path)["trials"] == deck["trials"]


def test_swapping_the_top_two_fitted_scores_swaps_the_drill_order(adapter: Adapter):
    adapter.adapter("sync")
    manifest_path = adapter.tmp / "manifest.json"
    adapter.adapter("manifest", "--output", str(manifest_path))
    manifest = json.loads(manifest_path.read_text())
    baseline = forge_deck(adapter, manifest_path)

    rows = manifest["bindings"]
    rows[0]["priority"], rows[1]["priority"] = rows[1]["priority"], rows[0]["priority"]
    rows[0], rows[1] = rows[1], rows[0]
    swapped_path = adapter.tmp / "swapped.json"
    swapped_path.write_text(json.dumps(manifest))
    swapped = forge_deck(adapter, swapped_path)

    assert swapped["trials"][0]["prompt"] == baseline["trials"][1]["prompt"]
    assert swapped["trials"][1]["prompt"] == baseline["trials"][0]["prompt"]


def test_deck_forge_refuses_a_manifest_it_does_not_recognise(adapter: Adapter):
    stray = adapter.tmp / "stray.json"
    stray.write_text(json.dumps({"schema": "something-else", "bindings": []}))
    result = adapter.run(
        "--dry-run", "--manifest", str(stray), "keybinds", script=FORGE
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    assert "not a sinnix.keybind.manifest/1" in result.stderr


# -- criterion 6: nothing here touches the source or the compositor ----------


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_whole_flow_leaves_bindings_nix_and_the_compositor_alone(
    adapter: Adapter, tmp_path: Path
):
    before = digest(BINDINGS_NIX)

    # A poisoned compositor CLI: if anything reaches for it, the run fails and
    # the marker says so.
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir()
    marker = tmp_path / "compositor-touched"
    for name in ("hyprctl", "hyprland", "sinnix-hypr-control"):
        stub = stub_dir / name
        stub.write_text(f'#!/bin/sh\necho "$0 $*" >> {marker}\nexit 97\n')
        stub.chmod(0o755)
    adapter.env["PATH"] = f"{stub_dir}{os.pathsep}{adapter.env['PATH']}"

    adapter.adapter("sync")
    adapter.write_usage({ids_by_chord(adapter.inventory_records())["F7"]: 3})
    manifest_path = adapter.tmp / "manifest.json"
    adapter.adapter("manifest", "--output", str(manifest_path))
    forge_deck(adapter, manifest_path)

    assert not marker.exists()
    assert digest(BINDINGS_NIX) == before


def test_git_reports_no_change_to_the_declarative_source(adapter: Adapter):
    adapter.adapter("sync")
    adapter.adapter("manifest")
    if shutil.which("git") is None:
        return  # packaged fixture without a checkout; the digest check stands
    result = subprocess.run(
        [
            "git",
            "-C",
            str(BINDINGS_NIX.parent),
            "status",
            "--porcelain",
            "--",
            str(BINDINGS_NIX),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        return  # not a checkout (packaged fixture); the digest check above stands
    assert result.stdout.strip() == ""
