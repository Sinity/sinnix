"""Capabilities of the backend adapters shipped with agentctl.

This is the admission contract shared by prompt compilation and batch launch.
The runner remains responsible for translating an admitted request into the
backend's command line and protocol.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackendCapabilities:
    model_prefix: str
    structured_results: bool = False
    native_session_resume: bool = False


BACKEND_CAPABILITIES: dict[str, BackendCapabilities] = {
    "codex": BackendCapabilities(
        "gpt-", structured_results=True, native_session_resume=True
    ),
    "claude": BackendCapabilities(
        "claude-", structured_results=True, native_session_resume=True
    ),
    "gemini": BackendCapabilities("gemini-"),
    "antigravity": BackendCapabilities("gemini-"),
    "grok": BackendCapabilities("grok-"),
    # The managed Pi adapter is pinned to the OpenAI Codex OAuth provider.
    # It can return schema-validated JSON, but has no native resume handoff.
    "pi": BackendCapabilities("gpt-", structured_results=True),
}


def supported_backends() -> tuple[str, ...]:
    return tuple(sorted(BACKEND_CAPABILITIES))
