from __future__ import annotations

from sinnix_ops_reducer.attention import normalize_attention


def correlation(job_id: str, events: list[dict[str, object]]) -> dict[str, object]:
    return {
        "job_id": job_id,
        "lifecycle_events": events,
    }


def test_provider_events_share_schema_and_duplicate_sources_dedupe() -> None:
    event = {
        "event": "approval",
        "at": "2026-08-07T01:00:00Z",
        "payload": {"prompt": "secret"},
    }
    report = {
        "agent_gateway": {
            "jobs": [
                {"job_id": "claude-1", "backend": "claude"},
                {"job_id": "codex-1", "backend": "codex"},
            ],
            "correlations": [
                correlation("claude-1", [event, event]),
                correlation("codex-1", [event]),
            ],
        }
    }
    state = normalize_attention(report)
    assert state["pending_count"] == 2
    assert {item["state"] for item in state["pending"]} == {"waiting_approval"}
    assert all(
        "secret" not in str(item) and "payload" not in item for item in state["pending"]
    )


def test_terminal_event_clears_prior_attention() -> None:
    state = normalize_attention(
        {
            "agent_gateway": {
                "jobs": [
                    {
                        "job_id": "job-1",
                        "backend": "codex",
                        "correlation": {
                            "kitty_socket": "/tmp/kitty.sock",
                            "kitty_window_id": "42",
                            "hyprland_address": "0xabc",
                        },
                    }
                ],
                "correlations": [
                    correlation(
                        "job-1",
                        [
                            {
                                "event": "user_wait",
                                "at": "2026-08-07T01:00:00Z",
                                "payload": {},
                            },
                            {
                                "event": "completion",
                                "at": "2026-08-07T01:01:00Z",
                                "payload": {},
                            },
                        ],
                    )
                ],
            }
        }
    )
    assert state["pending"] == []


def test_oldest_item_has_verified_target_metadata() -> None:
    state = normalize_attention(
        {
            "agent_gateway": {
                "jobs": [
                    {
                        "job_id": "job-1",
                        "backend": "codex",
                        "correlation": {
                            "kitty_socket": "/tmp/kitty.sock",
                            "kitty_window_id": "42",
                            "hyprland_address": "0xabc",
                        },
                    }
                ],
                "correlations": [
                    correlation(
                        "job-1",
                        [
                            {
                                "event": "rate_limit",
                                "at": "2026-08-07T01:00:00Z",
                                "payload": {},
                            }
                        ],
                    )
                ],
            }
        }
    )
    item = state["pending"][0]
    assert item["state"] == "rate_limited"
    assert item["target"] == {
        "kitty_socket": "/tmp/kitty.sock",
        "kitty_window_id": "42",
        "hyprland_address": "0xabc",
    }
