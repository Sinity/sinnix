from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GatewayModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectReadRequest(GatewayModel):
    project_id: str = Field(min_length=1, max_length=128)
    path: str = Field(min_length=1, max_length=4096)
    start_line: int = Field(default=1, ge=1, le=10_000_000)
    end_line: int | None = Field(default=None, ge=1, le=10_000_000)
    max_bytes: int = Field(default=64_000, ge=1, le=262_144)


class AgentLaunchRequest(GatewayModel):
    project_id: str = Field(min_length=1, max_length=128)
    prompt: str = Field(min_length=1, max_length=200_000)
    backend: str = Field(pattern="^(claude|codex|gemini|grok|antigravity)$")
    model: str | None = Field(default=None, max_length=256)
    reasoning_effort: str | None = Field(default=None, max_length=32)
    job_role: str | None = Field(default=None, max_length=512)
    work_item: str | None = Field(default=None, max_length=512)
    timeout_seconds: int = Field(default=14_400, ge=30, le=86_400)
    credential_profile: str = Field(default="subscription", pattern="^(subscription|api)$")


JsonObject = dict[str, Any]
