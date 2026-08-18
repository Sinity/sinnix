"""Behaviour checks for the capability index merge and its page.

Three real contracts here, none of them a restatement of the code:

  1. The census keys services by RUNTIME SURFACE name, not by the
     `sinnix.services.<name>` the index rows are named after. `polylogue` the
     service is `polylogued` the surface. Joining on the row name alone reports
     the entire service class as uncensused, which looks exactly like a census
     that has never run.

  2. The hub's own routes are the one capability kind Nix cannot see, because
     they are declared in Python. If the page ever renders from the index alone
     the hub becomes the only part of the system that is undiscoverable from the
     machine's own discovery surface.

  3. A capability the host has switched OFF must still appear, marked off. The
     index exists to answer "what can this machine do", and a disabled service
     is an answer -- silently dropping it is how the operator ends up
     rediscovering a capability that shipped disabled two years ago.
"""

from __future__ import annotations

import json
from typing import Any

from sinnix_ops_reducer import capabilities, pages
from sinnix_ops_reducer.pages.capabilities import render_capabilities

INDEX: dict[str, Any] = {
    "schema": capabilities.SCHEMA,
    "host": "fixture",
    "revision": "abcdef0123456789",
    "rows": [
        {
            "kind": "service",
            "name": "polylogue",
            "description": "AI chat archiver",
            "invoke": "systemctl --user status polylogued.service",
            "enabled": True,
            "owner": "modules/services/polylogue.nix",
            "docs": None,
            "unit": "polylogued.service",
            "manager": "user",
            "surfaces": [
                {"name": "polylogued", "unit": "polylogued.service", "manager": "user"}
            ],
        },
        {
            "kind": "service",
            "name": "airvpn-seed",
            "description": "Seedbox VPN egress",
            "invoke": None,
            "enabled": False,
            "owner": "modules/services/airvpn-seed.nix",
            "docs": None,
        },
        {
            "kind": "script",
            "name": "sinnix-census",
            "description": "Evidence-joined usage census",
            "invoke": "sinnix census",
            "enabled": None,
            "owner": "scripts/sinnix-census",
            "docs": None,
            "tier": "default",
        },
        {
            "kind": "loom",
            "name": "future-kind",
            "description": "A kind this table does not know yet",
            "invoke": None,
            "enabled": None,
            "owner": "modules/loom.nix",
            "docs": None,
        },
    ],
}

CENSUS_LINES = [
    {
        "ts": 100,
        "window_days": 90,
        "class": "services",
        "name": "polylogued",
        "evidence": {"atuin": None, "polylogue": None, "journald": {"n": 40}},
        "static_refs": [],
        "verdict": "active",
    },
    {
        "ts": 100,
        "window_days": 90,
        "class": "scripts",
        "name": "sinnix-census",
        "evidence": {
            "atuin": {"n": 0, "last": None},
            "polylogue": None,
            "journald": None,
        },
        "static_refs": ["modules/services/census.nix"],
        "verdict": "unused-in-window",
    },
    {
        "ts": 50,
        "window_days": 90,
        "class": "scripts",
        "name": "sinnix-census",
        "evidence": {"atuin": {"n": 9, "last": 1}, "polylogue": None, "journald": None},
        "static_refs": [],
        "verdict": "active",
    },
]


def write_census(tmp_path, rows=CENSUS_LINES):
    path = tmp_path / "usage-census.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def write_index(tmp_path, index=INDEX):
    path = tmp_path / "capability-index.json"
    path.write_text(json.dumps(index), encoding="utf-8")
    return path


def test_service_census_joins_through_the_surface_name(tmp_path) -> None:
    view = capabilities.build(write_index(tmp_path), write_census(tmp_path))
    rows = {row["name"]: row for row in view["rows"]}
    assert rows["polylogue"]["census"]["verdict"] == "active"
    assert rows["polylogue"]["census"]["journal_lines"] == 40


def test_the_newest_census_run_wins(tmp_path) -> None:
    view = capabilities.build(write_index(tmp_path), write_census(tmp_path))
    census = {row["name"]: row["census"] for row in view["rows"]}
    assert census["sinnix-census"]["verdict"] == "unused-in-window"
    assert census["sinnix-census"]["static_refs"] == 1


def test_new_kinds_get_census_verdicts_through_the_kind_to_class_map(tmp_path) -> None:
    """sinnix-census's index-derived extension (features, commands,
    capture-lanes, agent-lanes) is only visible on this page if CENSUS_CLASSES
    maps each new kind to the class the census actually emits."""
    index = {
        "schema": capabilities.SCHEMA,
        "host": "fixture",
        "revision": "abc",
        "rows": [
            {
                "kind": "feature",
                "name": "cli.docling",
                "description": "x",
                "invoke": None,
                "enabled": True,
                "owner": "modules/features/cli/docling.nix",
                "docs": None,
            },
            {
                "kind": "command",
                "name": "switch",
                "description": "x",
                "invoke": "switch",
                "enabled": None,
                "owner": "flake/command-registry.nix",
                "docs": None,
            },
            {
                "kind": "capture-lane",
                "name": "a11y",
                "description": "x",
                "invoke": None,
                "enabled": True,
                "owner": "modules/services/capture-a11y.nix",
                "docs": None,
                "path": "/realm/data/activity/a11y",
            },
            {
                "kind": "agent-lane",
                "name": "claude-lean",
                "description": "x",
                "invoke": "claude-lean",
                "enabled": None,
                "owner": "flake/data/agent-lanes.nix",
                "docs": None,
            },
        ],
    }
    census_lines = [
        {
            "ts": 1,
            "window_days": 90,
            "class": "features",
            "name": "cli.docling",
            "evidence": {
                "atuin": {"n": 3, "last": 1},
                "polylogue": None,
                "journald": None,
            },
            "static_refs": [],
            "verdict": "active",
        },
        {
            "ts": 1,
            "window_days": 90,
            "class": "commands",
            "name": "switch",
            "evidence": {
                "atuin": {"n": 50, "last": 1},
                "polylogue": None,
                "journald": None,
            },
            "static_refs": [],
            "verdict": "active",
        },
        {
            "ts": 1,
            "window_days": 90,
            "class": "capture-lanes",
            "name": "a11y",
            "evidence": {
                "atuin": None,
                "polylogue": None,
                "journald": None,
                "filesystem": {"n": 1, "last": 2},
            },
            "static_refs": [],
            "verdict": "active",
        },
        {
            "ts": 1,
            "window_days": 90,
            "class": "agent-lanes",
            "name": "claude-lean",
            "evidence": {
                "atuin": {"n": 12, "last": 1},
                "polylogue": None,
                "journald": None,
            },
            "static_refs": [],
            "verdict": "active",
        },
    ]
    view = capabilities.build(
        write_index(tmp_path, index), write_census(tmp_path, census_lines)
    )
    census = {row["name"]: row["census"] for row in view["rows"]}
    assert census["cli.docling"]["verdict"] == "active"
    assert census["switch"]["verdict"] == "active"
    assert census["a11y"]["verdict"] == "active"
    assert census["a11y"]["path_written_in_window"] == 1
    assert census["claude-lean"]["verdict"] == "active"
    assert view["censused"] == 4


def test_kinds_without_a_census_class_carry_no_verdict(tmp_path) -> None:
    view = capabilities.build(write_index(tmp_path), write_census(tmp_path))
    rows = {row["name"]: row for row in view["rows"]}
    assert rows["future-kind"]["census"] is None
    assert view["censused"] == 2


def test_unknown_kinds_are_grouped_rather_than_dropped(tmp_path) -> None:
    view = capabilities.build(write_index(tmp_path), write_census(tmp_path))
    assert "loom" in {group["kind"] for group in view["groups"]}
    assert view["counts"]["loom"] == 1


def test_an_index_of_the_wrong_schema_is_treated_as_absent(tmp_path) -> None:
    good = write_index(tmp_path)
    bad = tmp_path / "other.json"
    bad.write_text(json.dumps({**INDEX, "schema": "something-else"}), encoding="utf-8")
    assert capabilities.load_index(good)["host"] == "fixture"
    assert capabilities.load_index(bad) == {}
    assert capabilities.load_index(tmp_path / "missing.json") == {}
    assert capabilities.load_index(None) == {}


def test_a_missing_census_degrades_to_verdictless_rows(tmp_path) -> None:
    view = pages.capability_view(write_index(tmp_path), tmp_path / "absent.jsonl")
    assert view["censused"] == 0
    assert view["index_present"]
    assert len(view["rows"]) == len(INDEX["rows"]) + len(pages.PAGES)


def test_hub_routes_are_capabilities_the_index_cannot_supply() -> None:
    rows = pages.hub_page_rows()
    assert {row["invoke"] for row in rows} == {href for href, _, _ in pages.PAGES}
    assert all(row["kind"] == "hub-page" and row["description"] for row in rows)
    assert "/capabilities/" in {row["invoke"] for row in rows}


def test_the_page_shows_disabled_capabilities_marked_off(tmp_path) -> None:
    view = pages.capability_view(write_index(tmp_path), write_census(tmp_path))
    html = render_capabilities({"host": "fixture"}, view, "now")
    assert "airvpn-seed" in html
    assert ">off<" in html
    assert "unused-in-window" in html
    # Every kind present in the merged view reaches the document.
    for group in view["groups"]:
        assert group["label"] in html, group["kind"]
    assert "</html>" in html


def test_the_page_says_so_when_the_index_is_absent(tmp_path) -> None:
    """The hub's own routes are always there, so a rendered page is not
    evidence the index was read; the absence has to be said out loud."""
    view = pages.capability_view(tmp_path / "absent.json", tmp_path / "absent.jsonl")
    assert not view["index_present"]
    assert view["counts"] == {"hub-page": len(pages.PAGES)}
    html = render_capabilities({"host": "fixture"}, view, "now")
    assert "Capability index unavailable" in html
    assert "capabilities" in html
    assert "</html>" in html


def test_capabilities_is_a_page_route_and_renders_from_the_shell() -> None:
    assert pages.is_page_route("/capabilities/")
    assert pages.canonical("/capabilities") == "/capabilities/"
    html = pages.render(
        "/capabilities/",
        {"host": "fixture"},
        None,
        None,
        None,
        capability_index_path=None,
        usage_census_path=None,
    )
    assert "<title>" in html and "</html>" in html
    # Unique to this page: a route that fell through to the dashboard would
    # still be a complete document, and the assertion above would not notice.
    assert "Capability index unavailable" in html
