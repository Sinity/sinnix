"""Behaviour checks for the hub pages the hub server renders.

The control surface mirrors the action API's admission rule: a lifecycle
button may exist only where the runtime inventory declares
`operatorRestart`. If these two ever disagree the hub starts offering
buttons the action API answers with 403.
"""

from __future__ import annotations

from html import unescape
from typing import Any

from sinnix_hub_server import pages
from sinnix_hub_server.pages.probes import project_of
from sinnix_hub_server.pages.services import lifecycle_controls, policy_controls

INVENTORY: dict[str, Any] = {
    "schema": "sinnix-runtime-inventory-v2",
    "units": {
        "controllable": {
            "unit": "controllable.service",
            "manager": "user",
            "kind": "service",
            "resourceClass": "background-maintenance",
            "notifyOnFailure": True,
            "operatorRestart": True,
            "activation": {"mode": "direct"},
        },
        "read-only": {
            "unit": "read-only.service",
            "manager": "system",
            "kind": "service",
            "resourceClass": "system",
            "notifyOnFailure": True,
            "operatorRestart": False,
            "activation": {"mode": "direct"},
        },
    },
}

MANIFEST: dict[str, Any] = {
    "schema": "sinnix-hub-manifest-v1",
    "host": "fixture",
    "port": 8880,
    "reportsPort": 8883,
    "reportsDir": "/nonexistent",
    "frontends": [],
    "links": [],
}


def test_project_of_names_checkouts_and_worktrees() -> None:
    assert project_of("/realm/project/sinex/crates") == "sinex"
    assert project_of("/realm/worktree/agent-123/src") == "agent-123"
    assert project_of("/var/tmp") is None


def test_every_route_renders_a_complete_document_without_a_snapshot() -> None:
    for route in pages.ROUTES:
        html = pages.render(route, MANIFEST, None, INVENTORY, "snapshot absent")
        assert "<title>" in html, route
        assert "</html>" in html, route


def test_pages_degrade_rather_than_fail() -> None:
    services = pages.render("/services/", MANIFEST, None, INVENTORY)
    # systemd is not reachable from a hermetic build, so every unit reads as
    # not-installed; the button correspondence itself is asserted below against
    # the function that decides it.
    assert "'unit','read-only.service'" not in services
    assert "'unit','controllable.service'" not in services
    assert "unavailable" in pages.render("/", MANIFEST, None, INVENTORY, "absent")


def test_route_aliases_and_non_routes() -> None:
    assert pages.is_page_route("/work")
    assert pages.canonical("/work") == "/work/"
    assert not pages.is_page_route("/v1/snapshot")
    assert not pages.is_page_route("/reports/")


def test_manifest_of_the_wrong_schema_is_treated_as_absent(tmp_path) -> None:
    good = tmp_path / "manifest.json"
    good.write_text('{"schema": "sinnix-hub-manifest-v1", "host": "fixture"}')
    bad = tmp_path / "other.json"
    bad.write_text('{"schema": "something-else", "host": "fixture"}')
    assert pages.load_manifest(good)["host"] == "fixture"
    assert pages.load_manifest(bad) == {}
    assert pages.load_manifest(tmp_path / "missing.json") == {}
    assert pages.load_manifest(None) == {}


def test_lifecycle_controls_mirror_the_action_api_admission_rule() -> None:
    assert "act(" not in lifecycle_controls(
        "x.service", restartable=False, installed=True, active=True
    )
    assert "<button" not in lifecycle_controls(
        "x.service", restartable=True, installed=False, active=False
    )
    active = lifecycle_controls(
        "x.service", restartable=True, installed=True, active=True
    )
    assert active.count("<button") == 2
    assert "'start'" not in active
    inactive = lifecycle_controls(
        "x.service", restartable=True, installed=True, active=False
    )
    assert inactive.count("<button") == 1
    assert "'stop'" not in inactive


def test_policy_controls_only_offer_declared_properties() -> None:
    assert policy_controls("x.service", {}) == ""
    assert policy_controls("x.service", {"Slice": "app.slice"}) == ""
    controls = policy_controls(
        "x.service", {"CPUWeight": 5, "MemoryHigh": "8G", "Slice": "app.slice"}
    )
    assert controls.count("setPolicy(") == 2
    assert '"CPUWeight", "5"' in unescape(controls)
    assert '"MemoryHigh", "8G"' in unescape(controls)
    assert "Slice" not in controls
    assert "act('reset_policy','unit',\"x.service\"" in unescape(controls)
