"""Behaviour checks for the capability index merge and its CLI.

Two real contracts here, none of them a restatement of the code:

  1. The hub's own routes are the one capability kind Nix cannot see, because
     they are declared in Python. If the view is built from the index alone the
     hub becomes the only part of the system that is undiscoverable from the
     machine's own discovery surface.

  2. A capability the host has switched OFF must still appear. The index exists
     to answer "what can this machine do", and a disabled service is an answer.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from sinnix_ops_reducer import capabilities, pages
from sinnix_ops_reducer.cli import capabilities_command

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


def write_index(tmp_path, index=INDEX):
    path = tmp_path / "capability-index.json"
    path.write_text(json.dumps(index), encoding="utf-8")
    return path


def test_disabled_capabilities_stay_in_the_view(tmp_path) -> None:
    view = capabilities.build(write_index(tmp_path))
    rows = {row["name"]: row for row in view["rows"]}
    assert rows["airvpn-seed"]["enabled"] is False


def test_unknown_kinds_are_grouped_rather_than_dropped(tmp_path) -> None:
    view = capabilities.build(write_index(tmp_path))
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


@pytest.mark.parametrize(
    "kind, status",
    [
        ("utf8", "invalid"),
        ("directory", "unavailable"),
        ("broken-link", "unavailable"),
        ("missing", "missing"),
    ],
)
def test_index_read_failures_keep_their_diagnosis(tmp_path, kind, status):
    path = tmp_path / "index.json"
    if kind == "utf8":
        path.write_bytes(b"\xff")
    elif kind == "directory":
        path.mkdir()
    elif kind == "broken-link":
        path.symlink_to(tmp_path / "missing-target")
    view = capabilities.build(path)
    assert view["index_status"]["status"] == status
    assert not view["index_present"]


def test_access_errors_remain_visible(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError("neutral denied")

    monkeypatch.setattr(Path, "read_text", denied)
    view = capabilities.build(tmp_path / "index.json")
    assert view["index_status"] == {"status": "unavailable", "reason": "neutral denied"}


def test_hub_routes_are_capabilities_the_index_cannot_supply(tmp_path) -> None:
    rows = pages.hub_page_rows()
    assert {row["invoke"] for row in rows} == {href for href, _, _ in pages.PAGES}
    assert all(row["kind"] == "hub-page" and row["description"] for row in rows)
    view = pages.capability_view(write_index(tmp_path))
    assert len(view["rows"]) == len(INDEX["rows"]) + len(pages.PAGES)


def test_an_absent_index_still_lists_the_hub_and_says_so(tmp_path) -> None:
    """The hub's own routes are always there, so a non-empty view is not
    evidence the index was read."""
    view = pages.capability_view(tmp_path / "absent.json")
    assert not view["index_present"]
    assert view["counts"] == {"hub-page": len(pages.PAGES)}


def test_cli_prints_every_group_and_filters_by_kind(tmp_path, capsys) -> None:
    index = write_index(tmp_path)
    assert capabilities_command(["--index", str(index)]) == 0
    out = capsys.readouterr().out
    assert "Declaration index: selected" in out
    assert "airvpn-seed" in out and "future-kind" in out
    assert capabilities_command(["--index", str(index), "--kind", "service", "--json"]) == 0
    view = json.loads(capsys.readouterr().out)
    assert {row["kind"] for row in view["rows"]} == {"service"}


def test_the_wrapper_execs_the_reducer_view(tmp_path, monkeypatch) -> None:
    root = Path(__file__).resolve().parents[3]
    index = write_index(tmp_path)
    launcher = tmp_path / "sinnix-ops-reducer"
    launcher.write_text(
        f"#!{sys.executable}\n"
        "from sinnix_ops_reducer.cli import capabilities_command\n"
        "import sys\n"
        f"raise SystemExit(capabilities_command(sys.argv[2:] + ['--index', {str(index)!r}]))\n"
    )
    launcher.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join([str(Path(capabilities.__file__).resolve().parents[1]), *sys.path]),
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
    assert json.loads(result.stdout)["host"] == "fixture"
