from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from sinnix_agent_gateway.beads import BeadsError, BeadsService
from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig


def beads_service(tmp_path: Path, principal_name: str) -> tuple[BeadsService, Path]:
    project = tmp_path / "project"
    project.mkdir()
    captured = tmp_path / "beads-command.jsonl"
    runner = tmp_path / "bd"
    runner.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        f"with pathlib.Path({str(captured)!r}).open('a') as output:\n"
        "    output.write(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd(), 'actor': os.environ.get('BEADS_ACTOR')}) + '\\n')\n"
        "print(json.dumps({'issues': [{'id': 'fixture-1'}]}))\n"
    )
    runner.chmod(0o700)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={
            "fixture": ProjectConfig(
                project_id="fixture", path=project, observer_read=True
            )
        },
        beads_command=str(runner),
    )
    return BeadsService(config, Principal.for_name(principal_name)), captured


def command(path: Path) -> dict[str, object]:
    return json.loads(path.read_text().splitlines()[-1])


def test_observer_reads_beads_through_readonly_native_command(tmp_path: Path) -> None:
    beads, captured = beads_service(tmp_path, "observer")

    result = beads.read("fixture", "list", {"status": "open", "limit": 20})

    assert result == {
        "project_id": "fixture",
        "operation": "list",
        "result": {"issues": [{"id": "fixture-1"}]},
    }
    invocation = command(captured)
    assert invocation["cwd"] == str(tmp_path / "project")
    assert invocation["actor"] == "sinnix-gateway:observer"
    assert invocation["argv"] == [
        "--directory",
        str(tmp_path / "project"),
        "--json",
        "--readonly",
        "list",
        "--flat",
        "--status",
        "open",
        "--limit",
        "20",
    ]


def test_beads_keeps_native_stderr_separate_from_json_response(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    runner = tmp_path / "bd"
    runner.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        "print('native warning', file=sys.stderr)\n"
        "print(json.dumps({'issues': [{'id': 'fixture-1'}]}))\n"
    )
    runner.chmod(0o700)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={
            "fixture": ProjectConfig(
                project_id="fixture", path=project, observer_read=True
            )
        },
        beads_command=str(runner),
    )

    result = BeadsService(config, Principal.for_name("observer")).read(
        "fixture", "ready", {"limit": 20}
    )

    assert result["result"] == {"issues": [{"id": "fixture-1"}]}


def test_operator_create_uses_append_notes_not_replacement(tmp_path: Path) -> None:
    beads, captured = beads_service(tmp_path, "operator")

    beads.write(
        "fixture",
        "create",
        {
            "title": "Gateway fixture",
            "description": "Exercise native owner routing.",
            "append_notes": "Created by the gateway fixture.",
            "labels": ["exec:now", "lane:gateway"],
        },
    )

    invocation = command(captured)
    assert invocation["actor"] == "sinnix-gateway:operator"
    assert "--readonly" not in invocation["argv"]
    assert "--append-notes" in invocation["argv"]
    assert "--notes" not in invocation["argv"]
    assert "exec:now,lane:gateway" in invocation["argv"]


def test_observer_cannot_write_beads(tmp_path: Path) -> None:
    beads, _ = beads_service(tmp_path, "observer")

    with pytest.raises(PolicyError, match="task.write"):
        beads.write("fixture", "claim", {"id": "fixture-1"})


def test_beads_rejects_unknown_operations_and_unstructured_updates(tmp_path: Path) -> None:
    beads, _ = beads_service(tmp_path, "operator")

    with pytest.raises(BeadsError, match="unknown Beads read operation"):
        beads.read("fixture", "sql")
    with pytest.raises(BeadsError, match="requires id and at least one"):
        beads.write("fixture", "update", {"id": "fixture-1"})
    with pytest.raises(BeadsError, match="malformed"):
        beads.write("fixture", "claim", {"id": "--bad"})


def test_gateway_config_loads_beads_command(tmp_path: Path) -> None:
    config_path = tmp_path / "gateway.json"
    config_path.write_text(
        json.dumps(
            {
                "stateDir": str(tmp_path / "state"),
                "projects": {},
                "beadsCommand": "/fixture/bd",
            }
        )
    )

    assert GatewayConfig.load(config_path).beads_command == "/fixture/bd"
