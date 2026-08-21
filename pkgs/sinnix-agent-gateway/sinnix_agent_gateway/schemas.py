from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GatewayModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectReadRequest(GatewayModel):
    project_id: str = Field(min_length=1, max_length=128)
    path: str = Field(min_length=1, max_length=4096)
    start_line: int = Field(default=1, ge=1, le=10_000_000)
    end_line: int | None = Field(default=None, ge=1, le=10_000_000)
    max_bytes: int = Field(default=64_000, ge=1, le=262_144)


class AgentLaunchRequest(GatewayModel):
    @model_validator(mode="before")
    @classmethod
    def reject_agent_environment_overlay(cls, value: Any) -> Any:
        if isinstance(value, dict) and "environment_overlay" in value:
            overlay = value["environment_overlay"]
            names = overlay.keys() if isinstance(overlay, dict) else ()
            if any(isinstance(name, str) and name.startswith("SINNIX_") for name in names):
                raise ValueError(
                    "agent environment overlay cannot override reserved SINNIX_* variables"
                )
            raise ValueError(
                "agent environment overlays are deferred until a service-private transport exists"
            )
        return value

    project_id: str = Field(min_length=1, max_length=128)
    prompt: str = Field(min_length=1, max_length=200_000)
    backend: str = Field(pattern="^(claude|codex|gemini|grok|antigravity)$")
    worktree: str | None = Field(default=None, min_length=1, max_length=4096)
    model: str | None = Field(default=None, max_length=256)
    reasoning_effort: str | None = Field(default=None, max_length=32)
    job_role: str | None = Field(default=None, max_length=512)
    work_item: str | None = Field(default=None, max_length=512)
    timeout_seconds: int = Field(default=14_400, ge=30, le=86_400)
    credential_profile: str = Field(
        default="subscription", pattern="^(subscription|api)$"
    )
    parent_job_id: str | None = Field(default=None, max_length=128)
    coordinator_job_id: str | None = Field(default=None, max_length=128)
    provider: str | None = Field(default=None, max_length=64)
    account_hash: str | None = Field(default=None, max_length=128)
    vendor_session_id: str | None = Field(default=None, max_length=256)
    polylogue_session_id: str | None = Field(default=None, max_length=256)
    kitty_socket: str | None = Field(default=None, max_length=4096)
    kitty_window_id: str | None = Field(default=None, max_length=128)
    hyprland_address: str | None = Field(default=None, max_length=256)
    quota_snapshot_id: str | None = Field(default=None, max_length=256)


JsonObject = dict[str, Any]
