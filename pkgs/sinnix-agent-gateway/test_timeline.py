from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.sessions import SessionLogService, SessionSource
from sinnix_agent_gateway.timeline import TimelineError, TimelineService


def timeline_service(
    tmp_path: Path,
    principal_name: str,
    *,
    max_result_bytes: int = 262_144,
    suffix: str = "",
) -> TimelineService:
    claude = tmp_path / "claude"
    codex = tmp_path / "codex"
    claude.mkdir(parents=True)
    codex.mkdir()
    claude_session = claude / "fixture.jsonl"
    codex_session = codex / "fixture.jsonl"
    claude_session.write_text(f'{{"text":"timeline needle{suffix}"}}\n')
    codex_session.write_text(f'{{"text":"other timeline needle{suffix}"}}\n')
    os.utime(claude_session, ns=(1_700_000_000_000_000_000,) * 2)
    os.utime(codex_session, ns=(1_700_000_100_000_000_000,) * 2)
    config = GatewayConfig(
        state_dir=tmp_path / "state", projects={}, max_result_bytes=max_result_bytes
    )
    principal = Principal.for_name(principal_name)
    sessions = SessionLogService(
        config,
        principal,
        (SessionSource("claude-code", claude), SessionSource("codex", codex)),
    )
    return TimelineService(principal, sessions)


def test_timeline_query_preserves_raw_source_time_basis_and_unavailability(
    tmp_path: Path,
) -> None:
    timeline = timeline_service(tmp_path, "observer")

    result = timeline.query(
        start="2023-11-14T22:13:20Z",
        end="2023-11-14T22:15:00Z",
        query="timeline needle",
    )

    assert result["time_basis"] == "session-file-mtime"
    assert [entry["source"] for entry in result["entries"]] == ["codex", "claude-code"]
    assert all(
        entry["authority"] == "authoritative-local-session-jsonl"
        for entry in result["entries"]
    )
    assert result["entries"][0]["object_reference"] == "codex:fixture.jsonl"
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


def test_timeline_query_bounds_large_snippets(tmp_path: Path) -> None:
    timeline = timeline_service(
        tmp_path,
        "observer",
        max_result_bytes=1_024,
        suffix="x" * 2_000,
    )

    result = timeline.query(query="timeline needle")

    assert result["truncated"] is True
    assert (
        len(json.dumps(result, sort_keys=True, separators=(",", ":")).encode())
        <= timeline.sessions.config.max_result_bytes
    )
    assert len(result["entries"]) < 2


def test_timeline_query_rejects_ambiguous_range_and_unknown_source(
    tmp_path: Path,
) -> None:
    timeline = timeline_service(tmp_path, "operator")

    with pytest.raises(TimelineError, match="timezone"):
        timeline.query(start="2023-11-14T22:13:20")
    with pytest.raises(TimelineError, match="start must not be after end"):
        timeline.query(start="2023-11-15T00:00:00Z", end="2023-11-14T00:00:00Z")
    with pytest.raises(TimelineError, match="unknown timeline source"):
        timeline.query(providers=["invented"])


def test_timeline_query_requires_session_authority(tmp_path: Path) -> None:
    timeline = timeline_service(tmp_path, "agent-control")

    with pytest.raises(PolicyError, match="session.read"):
        timeline.query()
