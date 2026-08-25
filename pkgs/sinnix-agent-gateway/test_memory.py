from __future__ import annotations

from pathlib import Path

import pytest
from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.memory import MemoryError, MemoryService
from sinnix_agent_gateway.sessions import SessionLogService, SessionSource


def memory_service(tmp_path: Path, principal_name: str) -> MemoryService:
    claude = tmp_path / "claude"
    codex = tmp_path / "codex"
    claude.mkdir(parents=True)
    codex.mkdir()
    (claude / "fixture.jsonl").write_text('{"text":"memory needle"}\n')
    (codex / "fixture.jsonl").write_text('{"text":"other memory needle"}\n')
    config = GatewayConfig(state_dir=tmp_path / "state", projects={})
    principal = Principal.for_name(principal_name)
    sessions = SessionLogService(
        config,
        principal,
        (SessionSource("claude-code", claude), SessionSource("codex", codex)),
    )
    return MemoryService(principal, sessions)


def test_memory_search_preserves_raw_source_provenance_and_unavailability(
    tmp_path: Path,
) -> None:
    memory = memory_service(tmp_path, "observer")

    result = memory.search("memory needle")

    assert {match["source"] for match in result["matches"]} == {
        "claude-code",
        "codex",
    }
    assert all(
        match["authority"] == "authoritative-local-session-jsonl"
        for match in result["matches"]
    )
    unavailable = {
        row["source"]: row
        for row in result["sources"]
        if row["availability"] == "unavailable"
    }
    assert (
        unavailable["polylogue"]["reason"]
        == "upstream is intentionally unavailable on this host"
    )
    assert (
        unavailable["sinex"]["reason"]
        == "upstream is intentionally unavailable on this host"
    )
    assert (
        unavailable["lynchpin"]["reason"]
        == "no gateway semantic adapter is registered yet"
    )


def test_memory_get_returns_bounded_source_object(tmp_path: Path) -> None:
    memory = memory_service(tmp_path, "operator")
    reference = memory.search("memory needle", providers=["claude-code"])["matches"][0][
        "object_reference"
    ]

    result = memory.get(reference, max_bytes=8)

    assert result["source"] == "claude-code"
    assert result["authority"] == "authoritative-local-session-jsonl"
    assert result["truncated"] is True
    assert result["bytes"] == 8


def test_memory_search_rejects_unknown_source_and_denied_principal(
    tmp_path: Path,
) -> None:
    memory = memory_service(tmp_path, "operator")

    with pytest.raises(MemoryError, match="unknown memory source"):
        memory.search("needle", providers=["invented"])

    denied = memory_service(tmp_path / "denied", "agent-control")
    with pytest.raises(PolicyError, match="session.read"):
        denied.search("needle")
