"""Row revision tokens cross the wire as exact decimal strings.

Beads row revisions are signed 64-bit integers that run past 2**53. A client
that decodes JSON numbers as doubles (ChatGPT's among them) receives a value
near the token that is not it, and its next guarded write is refused against
a row nothing else touched. The Beads owner serializes its declared row
tokens as strings before any lossy decoding. Revision preconditions accept those strings back unchanged.
Authored metadata and unrelated counters retain their native JSON types.
"""

from __future__ import annotations

import re
from typing import Annotated, Any

from pydantic import BeforeValidator

# Inputs that carry a revision back to its owner.
REVISION_INPUTS = frozenset({"expected_version"})
_TOKEN = r"^-?[0-9]{1,20}$"
_TOKEN_NOTE = (
    "Send the revision exactly as a read or write returned it: the decimal "
    "string, not a number."
)


MIN_VERSION = -(2**63)
MAX_VERSION = 2**63 - 1


def parse_version_token(value: Any) -> int:
    """Validate the wire token before Pydantic can coerce other number forms."""
    if isinstance(value, str):
        if re.fullmatch(_TOKEN, value) is None:
            raise ValueError("row version must be a signed decimal integer string")
        value = int(value)
    if type(value) is not int or not MIN_VERSION <= value <= MAX_VERSION:
        raise ValueError("row version must be a signed 64-bit integer")
    return value


VersionToken = Annotated[int, BeforeValidator(parse_version_token)]


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

    Declared native version fields use the shared validator before coercion.
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
                    {"type": "integer", "minimum": MIN_VERSION, "maximum": MAX_VERSION},
                ],
                "description": f"{_TOKEN_NOTE} {description}".strip(),
            }
    return result
