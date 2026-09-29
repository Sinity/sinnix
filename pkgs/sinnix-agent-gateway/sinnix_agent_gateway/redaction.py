from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sinnix_lib.secrets import env_name_is_secret

_SECRET_WORDS = r"api[_-]?key|authorization|password|secret|token"
# An optional auth scheme belongs to the value: "Authorization: Bearer x"
# must hide x, not the word Bearer. Quotes end a value.
_SECRET_ASSIGNMENT = re.compile(
    rf"(?i)\b({_SECRET_WORDS})\b\s*[:=]\s*(?:(?:bearer|basic|token)\s+)?([^\s,;\"']+)"
)
# A structured field is secret when its name is, or ends in, one of the words:
# token, client_secret and OPENAI_API_KEY are; idempotency_key is not.
_SECRET_KEY = re.compile(rf"(?i)(?:.*[_-])?(?:{_SECRET_WORDS})\Z")
_KEY_SHAPE = re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{12,}\b")
_SECRET_VALUE = re.compile(
    r"(?i)(-----BEGIN |eyJ[A-Za-z0-9_-]{20,}\.|(?:password|passwd|pwd)=|(?:postgres|mysql|mongodb|redis)://[^:\s/]+:[^@\s/]+@)"
)
REDACTED = "[REDACTED]"


def redact(value: str) -> str:
    value = _SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}={REDACTED}", value)
    return _KEY_SHAPE.sub(REDACTED, value)


def key_is_secret(key: Any) -> bool:
    return isinstance(key, str) and _SECRET_KEY.match(key) is not None


def redact_structure(value: Any) -> Any:
    """Redact a JSON-shaped value before it is serialized.

    Values under secret-named keys are replaced whole, and free-text redaction
    runs on each string value. Applied to serialized JSON instead, a pattern
    such as ``token=abc"`` swallows the closing quote and corrupts the
    document.
    """
    if isinstance(value, Mapping):
        return {
            key: REDACTED if key_is_secret(key) else redact_structure(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_structure(item) for item in value]
    if isinstance(value, str):
        return redact(value)
    return value


def redact_env(env: dict[str, str], *, value_limit: int = 2_000) -> dict[str, str]:
    """Redact secret-bearing process environment entries.

    Names matching secret tokens (including KEY/PSK/DB as words) are always
    redacted. Remaining values still pass through assignment/key-shape and
    credential-shaped value filters.
    """
    redacted: dict[str, str] = {}
    for key, value in env.items():
        if env_name_is_secret(key) or _SECRET_VALUE.search(value):
            redacted[key] = REDACTED
            continue
        redacted[key] = redact(value)[:value_limit]
    return redacted


def public_error(exc: Exception) -> str:
    if not isinstance(exc, ValueError):
        return "gateway operation failed"
    message = redact(str(exc)).strip()
    if not message:
        return "gateway operation failed"
    home = str(Path.home())
    message = message.replace(home, "$HOME")
    return message[:1000]
