from __future__ import annotations

from pathlib import Path

import pytest

from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.sessions import SessionError, SessionLogService, SessionSource


def session_service(tmp_path: Path) -> tuple[SessionLogService, Path]:
    root = tmp_path / "claude"
    root.mkdir()
    service = SessionLogService(
        GatewayConfig(state_dir=tmp_path / "state", projects={}),
        Principal.for_name("observer"),
        sources=(SessionSource("claude-code", root),),
    )
    return service, root


def test_session_list_read_and_search_preserve_provider_reference(tmp_path: Path) -> None:
    service, root = session_service(tmp_path)
    session = root / "project" / "session.jsonl"
    session.parent.mkdir()
    session.write_text('{"text":"gateway demonstration"}\n{"text":"second"}\n')

    listed = service.list("claude-code")
    reference = listed["sessions"][0]["reference"]
    read = service.read(reference, max_bytes=32)
    search = service.search("claude-code", "demonstration")

    assert reference == "claude-code:project/session.jsonl"
    assert read["reference"] == reference
    assert "gateway" in read["content"]
    assert search["matches"][0]["reference"] == reference
    assert search["truncated"] is False


def test_session_references_survive_a_provider_root_symlink(tmp_path: Path) -> None:
    canonical_root = tmp_path / "canonical-claude"
    canonical_root.mkdir()
    alias_root = tmp_path / "claude"
    alias_root.symlink_to(canonical_root, target_is_directory=True)
    session = canonical_root / "project" / "session.jsonl"
    session.parent.mkdir()
    session.write_text('{"text":"gateway demonstration"}\n')
    service = SessionLogService(
        GatewayConfig(state_dir=tmp_path / "state", projects={}),
        Principal.for_name("observer"),
        sources=(SessionSource("claude-code", alias_root),),
    )

    reference = service.list("claude-code")["sessions"][0]["reference"]

    assert reference == "claude-code:project/session.jsonl"
    assert service.read(reference, max_bytes=1)["reference"] == reference


def test_session_reference_rejects_path_escape(tmp_path: Path) -> None:
    service, root = session_service(tmp_path)
    (root / "session.jsonl").write_text("{}\n")

    with pytest.raises(SessionError, match="remain within"):
        service.read("claude-code:../session.jsonl")


def test_session_search_declares_prefix_bound(tmp_path: Path) -> None:
    service, root = session_service(tmp_path)
    (root / "session.jsonl").write_text("x" * 70_000 + "needle\n")

    result = service.search("claude-code", "needle")

    assert result["matches"] == []
    assert result["truncated"] is True
    assert result["scanned_bytes"] == 64_000
