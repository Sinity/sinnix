from __future__ import annotations

import re
from pathlib import Path

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|authorization|password|secret|token)\b\s*[:=]\s*([^\s,;]+)"
)
_KEY_SHAPE = re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{12,}\b")
_SECRET_VALUE = re.compile(
    r"(?i)(-----BEGIN |eyJ[A-Za-z0-9_-]{20,}\.|(?:password|passwd|pwd)=|(?:postgres|mysql|mongodb|redis)://[^:\s/]+:[^@\s/]+@)"
)
# Word tokens, not substrings: KEYBOARD must stay visible, KAGGLE_KEY must not.
_SECRET_NAME = re.compile(
    r"(?i)(^|_)("
    r"KEY|KEYS|TOKEN|SECRET|PASSWORD|PASSWD|PASSPHRASE|PASS|PSK|SEED|"
    r"APIKEY|AUTH|CREDENTIAL|PRIVATE|COOKIE|CERT|CERTIFICATE|BEARER|JWT|"
    r"DB|DATABASE"
    r")(_|$)"
)
REDACTED = "[REDACTED]"


def redact(value: str) -> str:
    value = _SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}={REDACTED}", value)
    return _KEY_SHAPE.sub(REDACTED, value)


def env_name_is_secret(key: str) -> bool:
    return bool(key) and _SECRET_NAME.search(key) is not None


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
