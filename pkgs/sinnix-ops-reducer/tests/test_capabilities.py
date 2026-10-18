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

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

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
        "verdict": "unknown",
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
        "verdict": "referenced-only",
    },
    {
        "ts": 50,
        "window_days": 90,
        "class": "scripts",
        "name": "sinnix-census",
        "evidence": {"atuin": {"n": 9, "last": 1}, "polylogue": None, "journald": None},
        "static_refs": [],
        "verdict": "shell-match-observed",
    },
]


def write_census(tmp_path, rows=CENSUS_LINES, index=INDEX):
    path = tmp_path / "usage-census.jsonl"
    selected = {}
    for row in sorted(rows, key=lambda r: r["ts"]):
        selected[(row["class"], row["name"])] = row
    snapshot = {
        "schema": "sinnix-usage-census-v2",
        "complete": True,
        "ts": int(time.time()),
        "window_days": 90,
        "row_count": len(selected),
        "rows": list(selected.values()),
        "snapshot_id": "fixture",
        "classes": sorted({r["class"] for r in selected.values()}),
        "declaration_revision": index["revision"],
        "coverage_gaps": [],
        "index_digest": hashlib.sha256(
            json.dumps(index, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    path.write_text(json.dumps(snapshot) + "\n", encoding="utf-8")
    return path


def write_index(tmp_path, index=INDEX):
    path = tmp_path / "capability-index.json"
    path.write_text(json.dumps(index), encoding="utf-8")
    return path


def test_service_census_joins_through_the_surface_name(tmp_path) -> None:
    view = capabilities.build(write_index(tmp_path), write_census(tmp_path))
    rows = {row["name"]: row for row in view["rows"]}
    assert rows["polylogue"]["census"]["verdict"] == "unknown"
    assert rows["polylogue"]["census"]["activation_matches"] == 40


def test_the_newest_census_run_wins(tmp_path) -> None:
    view = capabilities.build(write_index(tmp_path), write_census(tmp_path))
    census = {row["name"]: row["census"] for row in view["rows"]}
    assert census["sinnix-census"]["verdict"] == "referenced-only"
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
                "path": "/realm/activity/a11y",
            },
            {
                "kind": "agent-lane",
                "name": "claude",
                "description": "x",
                "invoke": "claude",
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
            "verdict": "shell-match-observed",
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
            "verdict": "shell-match-observed",
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
            "verdict": "unknown",
        },
        {
            "ts": 1,
            "window_days": 90,
            "class": "agent-lanes",
            "name": "claude",
            "evidence": {
                "atuin": {"n": 12, "last": 1},
                "polylogue": None,
                "journald": None,
            },
            "static_refs": [],
            "verdict": "shell-match-observed",
        },
    ]
    view = capabilities.build(
        write_index(tmp_path, index), write_census(tmp_path, census_lines, index)
    )
    census = {row["name"]: row["census"] for row in view["rows"]}
    assert census["cli.docling"]["verdict"] == "shell-match-observed"
    assert census["switch"]["verdict"] == "shell-match-observed"
    assert census["a11y"]["verdict"] == "unknown"
    assert census["a11y"]["path_written_in_window"] == 1
    assert census["claude"]["verdict"] == "shell-match-observed"
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


@pytest.mark.parametrize("kind, status", [("utf8", "invalid"), ("directory", "unavailable"), ("broken-link", "unavailable"), ("missing", "missing")])
def test_index_read_failures_keep_their_diagnosis(tmp_path, kind, status):
    path = tmp_path / "index.json"
    if kind == "utf8":
        path.write_bytes(b"\xff")
    elif kind == "directory":
        path.mkdir()
    elif kind == "broken-link":
        path.symlink_to(tmp_path / "missing-target")
    view = capabilities.build(path, None)
    assert view["index_status"]["status"] == status
    assert not view["index_present"]


def test_access_errors_remain_visible(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError("neutral denied")
    monkeypatch.setattr(Path, "read_text", denied)
    view = capabilities.build(tmp_path / "index.json", None)
    assert view["index_status"] == {"status": "unavailable", "reason": "neutral denied"}


def test_valid_empty_index_is_present_and_keeps_its_fingerprint(tmp_path):
    path = tmp_path / "index.json"
    value = {**INDEX, "rows": []}
    path.write_text(json.dumps(value))
    selected = capabilities.load_index(path)
    assert json.dumps(selected, sort_keys=True) == json.dumps(value, sort_keys=True)
    view = capabilities.build(path, None)
    assert view["index_present"]
    assert view["index_status"]["status"] == "selected"


def test_index_error_is_escaped_in_the_page(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError("<img src=x onerror=alert(1)>")
    monkeypatch.setattr(Path, "read_text", denied)
    view = capabilities.build(tmp_path / "index.json", None)
    body = render_capabilities({}, view, "neutral timestamp")
    assert "&lt;img" in body
    assert "<img src=x" not in body


def test_census_access_reason_survives_the_projection(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError("neutral census denied")
    monkeypatch.setattr(Path, "open", denied)
    view = capabilities.build(None, tmp_path / "census.jsonl")
    assert view["census_status"]["status"] == "unavailable"
    assert any("neutral census denied" in line for line in view["census_details"])


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
    assert "referenced-only" in html
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


def test_incomplete_snapshot_and_removed_row_cannot_mix_runs(tmp_path):
    path = write_census(tmp_path)
    first = json.loads(path.read_text())
    second = {
        **first,
        "snapshot_id": "second",
        "rows": [next(r for r in first["rows"] if r["class"] == "services")],
        "row_count": 1,
    }
    path.write_text(
        path.read_text()
        + json.dumps(second)
        + "\n"
        + '{"schema":"sinnix-usage-census-v2"'
    )
    view = capabilities.build(write_index(tmp_path), path)
    assert view["census_status"]["snapshot_id"] == "second"
    assert view["census_status"]["ignored_incomplete_tail"]
    assert view["censused"] == 1
    assert (
        next(r for r in view["rows"] if r["name"] == "sinnix-census")["census"] is None
    )


def test_legacy_and_new_declaration_are_historical(tmp_path):
    path = tmp_path / "legacy.jsonl"
    path.write_text(json.dumps(CENSUS_LINES[1]) + "\n")
    view = capabilities.build(write_index(tmp_path), path)
    assert view["censused"] == 0
    assert view["census_status"]["status"] == "historical-or-unavailable"
    path = write_census(tmp_path)
    view = capabilities.build(write_index(tmp_path, {**INDEX, "revision": "new"}), path)
    assert view["censused"] == 0
    assert view["census_status"]["status"] == "declaration-mismatch"
    # A new index with the same revision still requires the exact declaration digest.
    view = capabilities.build(
        write_index(tmp_path, {**INDEX, "rows": INDEX["rows"][:1]}), path
    )
    assert view["census_status"]["status"] == "declaration-mismatch"


def test_stale_and_malformed_snapshot_are_not_current(tmp_path):
    path = write_census(tmp_path)
    snapshot = json.loads(path.read_text())
    snapshot["ts"] = int(time.time()) - 15 * 86400
    path.write_text(json.dumps(snapshot) + "\n")
    view = capabilities.build(write_index(tmp_path), path)
    assert view["census_status"]["status"] == "stale"
    assert view["censused"] == 0
    snapshot["rows"].append({"class": "scripts", "name": "duplicate"})
    path.write_text(json.dumps(snapshot) + "\n")
    assert not capabilities.load_census(path)


def test_cli_and_page_preserve_selected_snapshot_gaps(tmp_path, capsys):
    from sinnix_ops_reducer.cli import capabilities_command

    index_path = write_index(tmp_path)
    census_path = write_census(tmp_path)
    snap = json.loads(census_path.read_text())
    snap["coverage_gaps"] = [{"class": "skills", "status": "unavailable"}]
    census_path.write_text(json.dumps(snap) + "\n")
    assert (
        capabilities_command(
            ["--index", str(index_path), "--census", str(census_path), "--json"]
        )
        == 0
    )
    view = json.loads(capsys.readouterr().out)
    assert view["census_status"]["snapshot_id"] == "fixture"
    assert view["census_status"]["coverage_gaps"] == snap["coverage_gaps"]
    html = render_capabilities({"host": "fixture"}, view, "now")
    assert "1 inventory/observation gaps" in html
    assert (
        capabilities_command(["--index", str(index_path), "--census", str(census_path)])
        == 0
    )
    assert "Census: selected" in capsys.readouterr().out


def test_wrapper_and_cheatsheet_use_the_same_selected_observation(
    tmp_path, monkeypatch
):
    import importlib.util
    import os
    import subprocess
    import sys
    from importlib.machinery import SourceFileLoader
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    index = write_index(tmp_path)
    report = write_census(tmp_path)
    launcher = tmp_path / "sinnix-ops-reducer"
    launcher.write_text(
        f'#!{sys.executable}\nfrom sinnix_ops_reducer.cli import capabilities_command\nimport sys\nraise SystemExit(capabilities_command(sys.argv[2:]+["--index",{str(index)!r},"--census",{str(report)!r}]))\n'
    )
    launcher.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(
            [str(Path(capabilities.__file__).resolve().parents[1]), *sys.path]
        ),
    )
    result = subprocess.run(
        [
            "bash",
            os.environ.get(
                "SINNIX_CAPABILITIES_WRAPPER", str(root / "scripts/sinnix-capabilities")
            ),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    wrapper = json.loads(result.stdout)
    loader = SourceFileLoader(
        "fixture_cheatsheet",
        os.environ.get(
            "SINNIX_CHEATSHEET_SOURCE", str(root / "scripts/sinnix-cheatsheet")
        ),
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    view = module.collect_capabilities()
    assert (
        view["census_status"]["snapshot_id"]
        == wrapper["census_status"]["snapshot_id"]
        == "fixture"
    )
    html, count = module.render_capability_sections(view)
    assert "Census: selected" in html and count > 0


def test_runtime_inventory_fingerprint_mismatch_is_historical(tmp_path):
    report = write_census(tmp_path)
    snapshot = json.loads(report.read_text())
    inventory = tmp_path / "runtime.json"
    inventory.write_text("{}")
    snapshot["declaration_sources"] = {
        "runtime_inventory": {"digest": hashlib.sha256(b"{}").hexdigest()}
    }
    report.write_text(json.dumps(snapshot) + "\n")
    assert (
        capabilities.build(
            write_index(tmp_path), report, runtime_inventory_path=inventory
        )["censused"]
        == 2
    )
    inventory.write_text('{"surfaces":{}}')
    view = capabilities.build(
        write_index(tmp_path), report, runtime_inventory_path=inventory
    )
    assert (
        view["censused"] == 0
        and view["census_status"]["status"] == "declaration-mismatch"
    )


def test_source_limits_and_raw_argument_exclusion_survive_reader_projection(tmp_path):
    path = write_census(tmp_path)
    snapshot = json.loads(path.read_text())
    target = next(r for r in snapshot["rows"] if r["class"] == "scripts")
    target["evidence"]["atuin"].update(
        status="partial",
        retention="unknown",
        since_ns=100,
        until_ns=200,
        raw_arguments="PRIVATE",
        transcript="PRIVATE",
    )
    path.write_text(json.dumps(snapshot) + "\n")
    view = capabilities.build(write_index(tmp_path), path)
    row = next(r for r in view["rows"] if r["name"] == "sinnix-census")["census"]
    assert row["sources"]["atuin"]["retention"] == "unknown"
    assert row["sources"]["atuin"]["status"] == "partial"
    assert row["sources"]["atuin"]["since_ns"] == 100
    assert "PRIVATE" not in json.dumps(view)


def test_malformed_declaration_fingerprint_degrades_without_crashing(tmp_path):
    report = write_census(tmp_path)
    snapshot = json.loads(report.read_text())
    snapshot["declaration_sources"] = {"runtime_inventory": "unsupported-shape"}
    report.write_text(json.dumps(snapshot) + "\n")
    view = capabilities.build(write_index(tmp_path), report)
    assert view["censused"] == 0
    assert view["census_status"]["status"] == "historical-or-unavailable"


def test_record_larger_than_old_tail_limit_is_selected_without_scanning_history(
    tmp_path,
):
    path = write_census(tmp_path)
    snapshot = json.loads(path.read_text())
    snapshot["padding"] = "x" * (17 * 1024 * 1024)
    encoded = (json.dumps(snapshot) + "\n").encode()
    history = b'{"legacy":true}\n' * 150_000
    path.write_bytes(history + encoded)
    progress = []
    census = capabilities.load_census(
        path, progress=lambda read, total: progress.append((read, total))
    )
    assert census.metadata["snapshot_id"] == "fixture"
    assert len(census) == 2
    assert progress[-1][0] <= len(encoded) + 64 * 1024
    assert progress[-1][0] < progress[-1][1]
    assert all(
        0 < after[0] - before[0] <= 64 * 1024
        for before, after in zip(progress, progress[1:], strict=False)
    )


def test_long_interrupted_tail_is_discarded_in_chunks_and_previous_snapshot_survives(
    tmp_path,
):
    import tracemalloc

    path = write_census(tmp_path)
    snapshot = path.read_bytes()
    history = b'{"legacy":true}\n' * 150_000
    tail = b'{"torn": "' + b"x" * (18 * 1024 * 1024)
    path.write_bytes(history + snapshot + tail)
    progress = []
    tracemalloc.start()
    try:
        census = capabilities.load_census(
            path, progress=lambda read, total: progress.append((read, total))
        )
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert census.metadata["snapshot_id"] == "fixture"
    assert census.metadata["ignored_incomplete_tail"]
    assert progress[-1][0] < progress[-1][1]
    assert peak < 2 * 1024 * 1024  # the torn tail must never accumulate as a record
    cancelled = capabilities.load_census(path, cancelled=lambda: True)
    assert cancelled.metadata["status"] == "cancelled"
    assert not cancelled
    assert "no absence inferred" in cancelled.metadata["coverage_gaps"][0]["reason"]


def test_evidence_reasons_outcomes_and_paths_are_visible_in_all_human_consumers(
    tmp_path, capsys
):
    import importlib.util
    from importlib.machinery import SourceFileLoader
    from pathlib import Path

    from sinnix_ops_reducer.cli import capabilities_command

    report = write_census(tmp_path)
    snapshot = json.loads(report.read_text())
    snapshot.update(since=100, until=200)
    snapshot["coverage_gaps"] = [
        {
            "source": "models",
            "status": "unavailable",
            "reason": "model owner unreachable",
        }
    ]
    target = next(row for row in snapshot["rows"] if row["class"] == "scripts")
    target["coverage_gaps"] = [
        {
            "source": "agentctl",
            "status": "unavailable",
            "reason": "no indexed exact capability mapping",
        }
    ]
    target["static_refs"] = ["scripts/real-consumer"]
    target["evidence"]["gateway"] = {
        "n": 2,
        "status": "partial",
        "count_basis": "lower-bound",
        "action": "files.read",
        "outcomes": {"ok": 1, "error": 1},
    }
    target["evidence"]["atuin"].update(
        status="partial",
        retention="unknown",
        since_ns=100,
        until_ns=200,
        limitation="literal history matches are not invocations",
    )
    report.write_text(json.dumps(snapshot) + "\n")
    index = write_index(tmp_path)
    view = capabilities.build(index, report)
    page = render_capabilities({"host": "fixture"}, view, "now")
    assert capabilities_command(["--index", str(index), "--census", str(report)]) == 0
    cli = capsys.readouterr().out
    root = Path(__file__).resolve().parents[3]
    loader = SourceFileLoader(
        "evidence_cheatsheet",
        os.environ.get(
            "SINNIX_CHEATSHEET_SOURCE", str(root / "scripts/sinnix-cheatsheet")
        ),
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    cheatsheet, _ = module.render_capability_sections(view)
    marker = f'data-census-snapshot-id="{snapshot["snapshot_id"]}"'
    assert marker in page and marker in cheatsheet
    for rendered in (page, cli, cheatsheet):
        for evidence in (
            "agentctl: unavailable",
            "no indexed exact capability mapping",
            "models: unavailable",
            "model owner unreachable",
            "gateway outcomes: error=1, ok=1",
            "lower-bound",
            "Reference: scripts/real-consumer",
            "window 100 to 200",
            "since_ns=100",
            "retention=unknown",
            "not invocations",
        ):
            assert evidence in rendered, evidence
    for html in (page, cheatsheet):
        assert "<details>" in html and "<summary>" in html
        assert "<details open" not in html  # concise until the reader expands evidence
