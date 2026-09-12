from __future__ import annotations

from pathlib import Path

import pytest
from conftest import assert_unavailable_upstreams
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
    assert_unavailable_upstreams(result["sources"])


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


def test_memory_limit_can_be_filled_by_one_matching_provider(tmp_path: Path) -> None:
    memory = memory_service(tmp_path, "observer")
    (tmp_path / "claude" / "second.jsonl").write_text('{"text":"memory needle"}\n')
    (tmp_path / "codex" / "fixture.jsonl").write_text("{}\n")

    result = memory.search("needle", providers=["claude-code", "codex"], limit=2)

    assert len(result["matches"]) == 2
    assert {match["source"] for match in result["matches"]} == {"claude-code"}


def test_memory_search_exposes_per_source_continuations(tmp_path: Path) -> None:
    memory = memory_service(tmp_path, "observer")
    (tmp_path / "claude" / "fixture.jsonl").write_bytes(
        b"x" * (64 * 1_024 - 1) + "éneedle\n".encode()
    )
    key = b"m" * 32
    first = memory.search(
        "éneedle",
        providers=["claude-code"],
        scan_bytes=64 * 1_024,
        cursor_key=key,
    )
    assert first["matches"] == [] and first["next_cursors"]["claude-code"]
    second = memory.search(
        "éneedle",
        providers=["claude-code"],
        source_cursors=first["next_cursors"],
        scan_bytes=64 * 1_024,
        cursor_key=key,
    )
    assert "éneedle" in second["matches"][0]["text"]
