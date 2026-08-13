"""The sinnix-capture-v1 JSONL envelope shape shared by every capture lane.

Bumping SCHEMA_VERSION is an envelope-shape change (fields added/removed/
retyped here), not a per-lane payload change -- coordinate with lynchpin's
capture readers before bumping.
"""

from __future__ import annotations

SCHEMA = "sinnix-capture-v1"
SCHEMA_VERSION = 1

ENVELOPE_FIELDS = (
    "schema",
    "schema_version",
    "lane",
    "ts",
    "host",
    "seq",
    "payload",
    "raw_ref",
)


def build_envelope(
    *,
    lane: str,
    ts: float,
    host: str,
    seq: int,
    payload: dict,
    raw_ref: str | None,
) -> dict:
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "lane": lane,
        "ts": ts,
        "host": host,
        "seq": seq,
        "payload": payload,
        "raw_ref": raw_ref,
    }
