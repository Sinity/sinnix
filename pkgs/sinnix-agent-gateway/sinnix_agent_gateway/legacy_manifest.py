"""Pinned, source-verified Gateway V1 manifest metadata."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


LEGACY_MANIFEST_SCHEMA = "sinnix.gateway-legacy-tool-list.v1"


def load_legacy_manifest() -> dict[str, Any]:
    value = json.loads(files(__package__).joinpath("legacy_manifest_v1.json").read_text())
    if value.get("schema") != LEGACY_MANIFEST_SCHEMA:
        raise ValueError("legacy manifest has an unknown schema")
    tools = value.get("tools")
    if not isinstance(tools, list) or any(not isinstance(tool, str) for tool in tools):
        raise ValueError("legacy manifest tools must be a string list")
    if len(tools) != 49 or len(set(tools)) != len(tools):
        raise ValueError("legacy manifest must contain the 49 unique retired tools")
    if not isinstance(value.get("canonical_bytes"), int) or value["canonical_bytes"] < 1:
        raise ValueError("legacy manifest must declare canonical byte accounting")
    return value


LEGACY_MANIFEST = load_legacy_manifest()
