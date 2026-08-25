from __future__ import annotations

import json
from pathlib import Path

import pytest
from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.capability_index import (
    CapabilityIndexError,
    CapabilityIndexService,
)
from sinnix_agent_gateway.config import GatewayConfig


def index_path(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    path = tmp_path / "capability-index.json"
    path.write_text(
        json.dumps(
            {
                "schema": "sinnix-capability-index-v1",
                "host": "test-host",
                "revision": "test-revision",
                "rows": rows,
            }
        )
    )
    return path


def service(
    tmp_path: Path,
    rows: list[dict[str, object]],
    principal_name: str = "observer",
    max_result_bytes: int = 262_144,
) -> CapabilityIndexService:
    return CapabilityIndexService(
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={},
            capability_index=index_path(tmp_path, rows),
            max_result_bytes=max_result_bytes,
        ),
        Principal.for_name(principal_name),
    )


def test_search_filters_index_rows_with_provenance_and_pagination(
    tmp_path: Path,
) -> None:
    capability_index = service(
        tmp_path,
        [
            {
                "kind": "script",
                "name": "sinnix-observe",
                "description": "Inspect machine state",
                "enabled": True,
                "invoke": "sinnix observe",
            },
            {
                "kind": "service",
                "name": "agent-gateway",
                "description": "Serve an MCP gateway",
                "enabled": True,
                "invoke": "systemctl --user status sinnix-agent-gateway.service",
            },
            {
                "kind": "script",
                "name": "sinnix-disabled",
                "description": "Inspect disabled state",
                "enabled": False,
            },
        ],
    )

    result = capability_index.search("inspect", kind="script", enabled=True, limit=1)

    assert result["available"] is True
    assert result["source"] == {
        "schema": "sinnix-capability-index-v1",
        "host": "test-host",
        "revision": "test-revision",
    }
    assert result["total"] == 1
    assert result["next_cursor"] is None
    assert result["rows"] == [
        {
            "kind": "script",
            "name": "sinnix-observe",
            "description": "Inspect machine state",
            "enabled": True,
            "invoke": "sinnix observe",
        }
    ]


def test_search_shrinks_page_to_response_bound(tmp_path: Path) -> None:
    capability_index = service(
        tmp_path,
        [
            {
                "kind": "script",
                "name": "small",
                "description": "small",
                "enabled": True,
            },
            {
                "kind": "script",
                "name": "large",
                "description": "x" * 400,
                "enabled": True,
            },
        ],
        max_result_bytes=700,
    )

    result = capability_index.search(limit=2)

    assert result["available"] is True
    assert [row["name"] for row in result["rows"]] == ["small"]
    assert result["next_cursor"] == 1


def test_search_returns_empty_page_for_no_match(tmp_path: Path) -> None:
    capability_index = service(
        tmp_path,
        [
            {
                "kind": "script",
                "name": "sinnix-observe",
                "description": "Inspect",
                "enabled": True,
            }
        ],
    )

    result = capability_index.search("missing")

    assert result["available"] is True
    assert result["total"] == 0
    assert result["rows"] == []


def test_describe_reports_ambiguous_names_and_exact_kind(tmp_path: Path) -> None:
    capability_index = service(
        tmp_path,
        [
            {"kind": "script", "name": "status", "description": "Show script status"},
            {"kind": "command", "name": "status", "description": "Show command status"},
        ],
    )

    ambiguous = capability_index.describe("status")
    exact = capability_index.describe("status", kind="script")

    assert ambiguous["ambiguous"] is True
    assert len(ambiguous["rows"]) == 2
    assert exact["ambiguous"] is False
    assert exact["rows"][0]["kind"] == "script"


def test_gateway_config_loads_capability_index_path(tmp_path: Path) -> None:
    config_path = tmp_path / "gateway.json"
    expected = tmp_path / "configured-index.json"
    config_path.write_text(
        json.dumps(
            {
                "stateDir": str(tmp_path / "state"),
                "projects": {},
                "capabilityIndex": str(expected),
            }
        )
    )

    assert GatewayConfig.load(config_path).capability_index == expected


def test_missing_index_is_an_honest_unavailable_result(tmp_path: Path) -> None:
    capability_index = CapabilityIndexService(
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={},
            capability_index=tmp_path / "missing.json",
        ),
        Principal.for_name("observer"),
    )

    assert capability_index.search() == {
        "available": False,
        "reason": "capability index is unavailable",
    }


def test_agent_control_can_search_but_unknown_principal_cannot(tmp_path: Path) -> None:
    agent_control = service(
        tmp_path,
        [{"kind": "script", "name": "status", "description": "Show status"}],
        principal_name="agent-control",
    )
    denied = CapabilityIndexService(
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={},
            capability_index=index_path(
                tmp_path,
                [{"kind": "script", "name": "status", "description": "Show status"}],
            ),
        ),
        Principal("restricted", frozenset(), None),
    )

    assert agent_control.search()["available"] is True
    with pytest.raises(PolicyError, match="capability.read"):
        denied.search()


def test_invalid_index_request_is_rejected(tmp_path: Path) -> None:
    capability_index = service(
        tmp_path,
        [{"kind": "script", "name": "status", "description": "Show status"}],
    )

    with pytest.raises(CapabilityIndexError, match="limit"):
        capability_index.search(limit=0)
    with pytest.raises(CapabilityIndexError, match="cursor"):
        capability_index.search(cursor=-1)
