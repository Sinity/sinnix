from __future__ import annotations

import re
from pathlib import Path

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|authorization|password|secret|token)\b\s*[:=]\s*([^\s,;]+)"
)
_KEY_SHAPE = re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{12,}\b")


def redact(value: str) -> str:
    value = _SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}=[REDACTED]", value)
    return _KEY_SHAPE.sub("[REDACTED]", value)


def public_error(exc: Exception) -> str:
    if not isinstance(exc, ValueError):
        return "gateway operation failed"
    message = redact(str(exc)).strip()
    if not message:
        return "gateway operation failed"
    home = str(Path.home())
    message = message.replace(home, "$HOME")
    return message[:1000]
