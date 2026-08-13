"""Behaviour checks for the hub renderer.

Two things here are real contracts rather than restatements of the code:

  1. The scope command reducer is a parser. `sinnix-scope` hands systemd a
     launch line wrapped in `env`, assignments, `nice`, `ionice`, a supervisor
     re-exec and possibly `nix develop --command`; the workload view is only
     worth reading if what comes out the other side is the command the operator
     typed. Every case below is a shape observed on the live host.

  2. The control surface mirrors the ops-reducer's admission rule: a lifecycle
     button may exist only where the runtime inventory declares
     `observe.restartable`. If these two ever disagree the hub starts offering
     buttons the action API answers with 403.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_loader(
    "hub_render",
    importlib.machinery.SourceFileLoader("hub_render", sys.argv[1]),
)
hub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hub)

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:
    if actual != expected:
        failures.append(f"{label}: expected {expected!r}, got {actual!r}")


# ---- the command reducer -------------------------------------------------

check(
    "supervised xtask under nice+ionice",
    hub.shorten_command(
        "/nix/store/aaa-bash-5.3/bin/bash /nix/store/bbb-sinnix-scope-script "
        "--internal-supervise -- nice -n 5 ionice -c 2 -n 7 -- xtask test -p sinexd"
    ),
    "xtask test -p sinexd",
)
check(
    "devshell-routed command",
    hub.shorten_command(
        "/nix/store/aaa-bash-5.3/bin/bash /nix/store/bbb-sinnix-scope-script "
        "--internal-supervise -- nice -n 10 ionice -c 3 -- nix develop --command xtask test"
    ),
    "xtask test",
)
check(
    "agent launch behind env assignments",
    hub.shorten_command(
        "/nix/store/ccc-coreutils/bin/env SINNIX_AGENT_SCOPED=1 SINNIX_AGENT_SCOPE_UNIT= "
        "/home/operator/.local/state/codex/launch.sh --profile lean"
    ),
    "launch.sh --profile lean",
)
check(
    "long paths keep their tail, not their store hash",
    hub.shorten_command(
        "nats-server -js -c /var/cache/project/dev-state/config/nats/nats.conf"
    ),
    "nats-server -js -c …/nats/nats.conf",
)
check("empty command", hub.shorten_command(None), "unnamed command")

check("project from a checkout", hub.project_of("/realm/project/sinex/crates"), "sinex")
check(
    "project from an agent worktree",
    hub.project_of("/realm/worktrees/agent-123/src"),
    "agent-123",
)
check("no project outside the roots", hub.project_of("/var/tmp"), None)

# `.scope` classification comes from the unit name, which sinnix-scope builds
# from the command class -- the reason an ad-hoc heavy command is identifiable
# at all. Multi-word class names must not be mistaken for their prefix.
classes = ["nix-build", "background", "build", "agent"]
check(
    "nix-build scope is not read as a build scope",
    hub.scope_class(
        "sinnix-nix-build-1786553380794796579-1234.scope",
        sorted(classes, key=len, reverse=True),
    ),
    "nix-build",
)
check(
    "build scope",
    hub.scope_class(
        "sinnix-build-1786553380794796579-1234.scope",
        sorted(classes, key=len, reverse=True),
    ),
    "build",
)

# ---- the control surface mirrors the reducer's admission rule ------------

inventory = {
    "schema": "sinnix-runtime-inventory-v1",
    "commandClasses": {name: {} for name in classes},
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
manifest = {
    "schema": "sinnix-hub-manifest-v1",
    "host": "fixture",
    "port": 8880,
    "aiServices": ["read-only", "absent"],
    "reportsDir": "/nonexistent",
    "frontends": [],
    "links": [],
}

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    os.environ["XDG_RUNTIME_DIR"] = str(root)
    sys.argv = [
        "sinnix-hub-render",
        "--manifest",
        str(root / "manifest.json"),
        "--inventory",
        str(root / "inventory.json"),
        "--snapshot",
        str(root / "absent.json"),
        "--heavy-lease",
        str(root / "absent-lease.json"),
        "--out",
        str(root / "www"),
    ]
    check("renderer exit status without a snapshot", hub.main(), 0)

    pages = {
        name: (root / "www" / name).read_text(encoding="utf-8")
        for name in (
            "index.html",
            "work/index.html",
            "services/index.html",
            "ai/index.html",
        )
    }
    for name, text in pages.items():
        if "<title>" not in text:
            failures.append(f"{name} is not a complete document")

    services = pages["services/index.html"]
    check(
        "a non-restartable unit never reaches the action API",
        "'unit','read-only.service'" in services,
        False,
    )
    check(
        "an unloadable unit offers nothing either",
        "'unit','controllable.service'" in services,
        # systemd is not reachable from a hermetic build, so every unit reads
        # as not-installed; the button correspondence itself is asserted below
        # against the function that decides it.
        False,
    )
    check(
        "an AI service with no surface is named rather than dropped",
        "absent" in pages["ai/index.html"],
        True,
    )
    check(
        "a missing snapshot degrades the dashboard instead of failing",
        "unavailable" in pages["index.html"],
        True,
    )

# The admission rule itself: a lifecycle verb is offered only for an installed
# unit the inventory marks restartable, and the offered verbs match the unit's
# current state so the API is never asked to start something already running.
check(
    "a running but non-restartable unit is offered no action at all",
    "act("
    in hub.lifecycle_controls(
        "x.service", restartable=False, installed=True, active=True
    ),
    False,
)
check(
    "restartable but unknown to systemd",
    "<button"
    in hub.lifecycle_controls(
        "x.service", restartable=True, installed=False, active=False
    ),
    False,
)
active_controls = hub.lifecycle_controls(
    "x.service", restartable=True, installed=True, active=True
)
check("an active unit offers stop and restart", active_controls.count("<button"), 2)
check("an active unit is not offered start", "'start'" in active_controls, False)
inactive_controls = hub.lifecycle_controls(
    "x.service", restartable=True, installed=True, active=False
)
check("an inactive unit offers start alone", inactive_controls.count("<button"), 1)
check("an inactive unit is not offered stop", "'stop'" in inactive_controls, False)

# A plain sinnix-scope placement (no job_id) is offered a stop
# button targeting the reducer's scope admission path; a gateway-job scope
# (job_id set, manifest attested) keeps its existing interrupt control and is
# NOT offered a redundant scope-stop.
plain_scope = hub.scope_block(
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
check(
    "a plain scope offers a stop button targeting its own unit name",
    "act('stop','scope','sinnix-build-123-456.scope'" in plain_scope,
    True,
)
job_scope = hub.scope_block(
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
check(
    "an attested gateway job offers interrupt",
    "act('interrupt','job_id','abc'" in job_scope,
    True,
)
check(
    "an attested gateway job is not also offered a scope-stop button",
    "act('stop','scope'" in job_scope,
    False,
)

if failures:
    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    raise SystemExit(1)
print("hub-render: all checks passed")
