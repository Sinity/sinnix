"""Behaviour checks for the hub pages the reducer renders.

Two things here are real contracts rather than restatements of the code
(carried over from flake/tests/hub-render.py when the renderer moved into this
package):

  1. The scope command reducer is a parser. `sinnix-scope` hands systemd a
     launch line wrapped in `env`, assignments, `nice`, `ionice`, a supervisor
     re-exec and possibly `nix develop --command`; the workload view is only
     worth reading if what comes out the other side is the command the operator
     typed. Every case below is a shape observed on the live host.

  2. The control surface mirrors the action API's admission rule: a lifecycle
     button may exist only where the runtime inventory declares
     `observe.restartable`. If these two ever disagree the hub starts offering
     buttons the action API answers with 403.
"""

from __future__ import annotations

from typing import Any

from sinnix_ops_reducer import pages
from sinnix_ops_reducer.pages.probes import project_of, scope_class, shorten_command
from sinnix_ops_reducer.pages.services import lifecycle_controls
from sinnix_ops_reducer.pages.work import scope_block

CLASSES = ["nix-build", "background", "build", "agent"]

INVENTORY: dict[str, Any] = {
    "schema": "sinnix-runtime-inventory-v1",
    "commandClasses": {name: {} for name in CLASSES},
    "surfaces": {
        "controllable": {
            "unit": "controllable.service",
            "manager": "user",
            "kind": "service",
            "resourceClass": "background-maintenance",
            "observe": {"enable": True, "restartable": True},
            "activation": {"mode": "direct"},
        },
        "read-only": {
            "unit": "read-only.service",
            "manager": "system",
            "kind": "service",
            "resourceClass": "system",
            "observe": {"enable": True, "restartable": False},
            "activation": {"mode": "direct"},
        },
    },
}

MANIFEST: dict[str, Any] = {
    "schema": "sinnix-hub-manifest-v1",
    "host": "fixture",
    "port": 8880,
    "aiServices": ["read-only", "absent"],
    "reportsDir": "/nonexistent",
    "frontends": [],
    "links": [],
}


def test_shorten_command_reduces_launch_wrappers() -> None:
    assert (
        shorten_command(
            "/nix/store/aaa-bash-5.3/bin/bash /nix/store/bbb-sinnix-scope-script "
            "--internal-supervise -- nice -n 5 ionice -c 2 -n 7 -- xtask test -p sinexd"
        )
        == "xtask test -p sinexd"
    )
    assert (
        shorten_command(
            "/nix/store/aaa-bash-5.3/bin/bash /nix/store/bbb-sinnix-scope-script "
            "--internal-supervise -- nice -n 10 ionice -c 3 -- nix develop --command xtask test"
        )
        == "xtask test"
    )
    assert (
        shorten_command(
            "/nix/store/ccc-coreutils/bin/env SINNIX_AGENT_SCOPED=1 SINNIX_AGENT_SCOPE_UNIT= "
            "/home/operator/.local/state/codex/launch.sh --profile lean"
        )
        == "launch.sh --profile lean"
    )
    assert (
        shorten_command(
            "nats-server -js -c /var/cache/project/dev-state/config/nats/nats.conf"
        )
        == "nats-server -js -c …/nats/nats.conf"
    )
    assert shorten_command(None) == "unnamed command"


def test_project_of_names_checkouts_and_worktrees() -> None:
    assert project_of("/realm/project/sinex/crates") == "sinex"
    assert project_of("/realm/worktrees/agent-123/src") == "agent-123"
    assert project_of("/var/tmp") is None


def test_scope_class_prefers_the_longest_matching_class() -> None:
    ordered = sorted(CLASSES, key=len, reverse=True)
    assert (
        scope_class("sinnix-nix-build-1786553380794796579-1234.scope", ordered)
        == "nix-build"
    )
    assert scope_class("sinnix-build-1786553380794796579-1234.scope", ordered) == "build"


def test_every_route_renders_a_complete_document_without_a_snapshot() -> None:
    for route in pages.ROUTES:
        html = pages.render(route, MANIFEST, None, INVENTORY, "snapshot absent")
        assert "<title>" in html, route
        assert "</html>" in html, route


def test_pages_degrade_rather_than_fail_and_name_unregistered_backends() -> None:
    services = pages.render("/services/", MANIFEST, None, INVENTORY)
    # systemd is not reachable from a hermetic build, so every unit reads as
    # not-installed; the button correspondence itself is asserted below against
    # the function that decides it.
    assert "'unit','read-only.service'" not in services
    assert "'unit','controllable.service'" not in services
    assert "absent" in pages.render("/ai/", MANIFEST, None, INVENTORY)
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
    active = lifecycle_controls("x.service", restartable=True, installed=True, active=True)
    assert active.count("<button") == 2
    assert "'start'" not in active
    inactive = lifecycle_controls(
        "x.service", restartable=True, installed=True, active=False
    )
    assert inactive.count("<button") == 1
    assert "'stop'" not in inactive


def test_scope_controls_distinguish_plain_scopes_from_attested_jobs() -> None:
    plain = scope_block(
        {
            "unit": "sinnix-build-123-456.scope",
            "manager": "user",
            "job_id": None,
            "class": "build",
            "slice": "build.slice",
            "memory": None,
            "memory_high": None,
            "memory_max": None,
            "elapsed": 5.0,
            "command": "xtask test",
            "cwd": "/realm/project/sinex",
            "project": "sinex",
        },
        {},
        {},
    )
    assert "act('stop','scope','sinnix-build-123-456.scope'" in plain
    job = scope_block(
        {
            "unit": "sinnix-agent-job-abc.scope",
            "manager": "user",
            "job_id": "abc",
            "class": None,
            "slice": "agent.slice",
            "memory": None,
            "memory_high": None,
            "memory_max": None,
            "elapsed": 5.0,
            "command": "claude",
            "cwd": None,
            "project": None,
        },
        {
            "abc": {
                "backend": "claude",
                "model": "sonnet",
                "worktree": "/realm/worktrees/abc",
                "declared": {},
            }
        },
        {},
    )
    assert "act('interrupt','job_id','abc'" in job
    assert "act('stop','scope'" not in job
