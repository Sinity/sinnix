"""Which environment entries are secrets, and masking their values in bytes.

One name rule serves every Sinnix owner that persists or displays a process
environment: AgentCTL keeps these values out of launch inputs and job logs,
and the agent gateway redacts them from what it reports.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping

# Word tokens, not substrings: KEYBOARD must stay visible, KAGGLE_KEY must not.
_SECRET_NAME = re.compile(
    r"(?i)(^|_)("
    r"KEY|KEYS|TOKEN|SECRET|PASSWORD|PASSWD|PASSPHRASE|PASS|PSK|SEED|"
    r"APIKEY|AUTH|CREDENTIAL|PRIVATE|COOKIE|CERT|CERTIFICATE|BEARER|JWT|"
    r"DB|DATABASE"
    r")(_|$)"
)
# Shorter values ("1", "yes", a port) would mask ordinary output.
MIN_MASKED_LENGTH = 8


# Git's config injection: GIT_CONFIG_KEY_<n> holds a config key name.
_NOT_SECRET = re.compile(r"GIT_CONFIG_KEY_[0-9]+\Z")


def env_name_is_secret(name: str) -> bool:
    return (
        bool(name)
        and _NOT_SECRET.match(name) is None
        and _SECRET_NAME.search(name) is not None
    )


def secret_values(environment: Mapping[str, str]) -> tuple[bytes, ...]:
    """The maskable values of an environment's secret-named entries.

    An absolute path (SSH_AUTH_SOCK, a *_DB location) names where something
    is, not a credential, and masking it would only hide diagnostics.
    """
    values = {
        value.encode()
        for name, value in environment.items()
        if env_name_is_secret(name)
        and len(value.encode()) >= MIN_MASKED_LENGTH
        and not value.startswith("/")
    }
    # Longest first, so a value containing another is masked whole.
    return tuple(sorted(values, key=len, reverse=True))


def _mask(length: int) -> bytes:
    """A same-length stand-in, so byte offsets into masked text stay valid."""
    label = b"[REDACTED]"
    if length < len(label):
        return b"*" * length
    return label[:-1] + b"*" * (length - len(label)) + b"]"


def mask_secret_values(data: bytes, values: Iterable[bytes]) -> bytes:
    for value in values:
        if value and value in data:
            data = data.replace(value, _mask(len(value)))
    return data


def masked_window(
    read: Callable[[int, int], bytes],
    offset: int,
    limit: int,
    values: tuple[bytes, ...],
) -> bytes:
    """Read ``limit`` bytes at ``offset`` with no secret straddling the edges.

    ``read(start, length)`` returns file bytes. The page is read with an
    overlap of the longest secret on each side, masked, then cut back, so a
    value split across two pages is masked in both.
    """
    if not values:
        return read(offset, limit)
    margin = max(len(value) for value in values) - 1
    start = max(0, offset - margin)
    window = read(start, (offset - start) + limit + margin)
    masked = mask_secret_values(window, values)
    head = offset - start
    return masked[head : head + min(limit, max(0, len(window) - head))]
