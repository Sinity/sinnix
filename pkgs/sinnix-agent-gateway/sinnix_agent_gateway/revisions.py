"""Row revision tokens cross the wire as exact decimal strings.

Beads row revisions are signed 64-bit integers that run past 2**53. A client
that decodes JSON numbers as doubles (ChatGPT's among them) receives a value
near the token that is not it, and its next guarded write is refused against
a row nothing else touched. Every revision the gateway returns is therefore a
string, and every revision precondition accepts that string back unchanged.
"""

from __future__ import annotations

from typing import Any

# Inputs that carry a revision back to its owner.
REVISION_INPUTS = frozenset({"expected_version"})
_TOKEN = r"^-?[0-9]{1,20}$"
_TOKEN_NOTE = (
    "Send the revision exactly as a read or write returned it: the decimal "
    "string, not a number."
)


def is_revision_key(key: object) -> bool:
    return isinstance(key, str) and (
        key == "revision" or key.endswith("_revision") or key in REVISION_INPUTS
    )


def lossless_revisions(value: Any) -> Any:
    """A copy of a response whose integer revisions are decimal strings."""
    if isinstance(value, dict):
        return {
            key: str(item)
            if is_revision_key(key)
            and isinstance(item, int)
            and not isinstance(item, bool)
            else lossless_revisions(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [lossless_revisions(item) for item in value]
    return value


def _is_integer_schema(schema: Any) -> bool:
    if not isinstance(schema, dict):
        return False
    if schema.get("type") == "integer":
        return True
    options = schema.get("anyOf")
    return isinstance(options, list) and any(
        isinstance(option, dict) and option.get("type") == "integer"
        for option in options
    )


def token_input_schema(schema: Any) -> Any:
    """Publish revision preconditions as strings; integers are still accepted.

    The native models validate in lax mode, so the decimal string becomes the
    exact integer the owner compares.
    """
    if isinstance(schema, list):
        return [token_input_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    result = {key: token_input_schema(item) for key, item in schema.items()}
    properties = result.get("properties")
    if isinstance(properties, dict):
        for name in REVISION_INPUTS & properties.keys():
            field = properties[name]
            if not _is_integer_schema(field):
                continue
            description = str(field.get("description") or "").strip()
            properties[name] = {
                "anyOf": [
                    {"type": "string", "pattern": _TOKEN},
                    {"type": "integer"},
                ],
                "description": f"{_TOKEN_NOTE} {description}".strip(),
            }
    return result

