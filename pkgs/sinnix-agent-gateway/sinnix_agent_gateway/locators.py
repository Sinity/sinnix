"""Natural locators in, canonical refs out.

Every action that targets a resource accepts either its canonical
``sinnix://`` ref or the locator a person would naturally give (a path, a
window title, a unit name). Resolution yields exactly one ref; zero matches
fail ``not_found``; several matches fail ``conflict`` with the candidates so
the caller can retry with a ref. Effectful actions never guess.
"""

from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from .results import ProtocolError
from .schemas import GatewayModel

FILE_REF_PREFIX = "sinnix://files/"


class Candidate(GatewayModel):
    ref: str
    label: str
    detail: dict[str, Any] = Field(default_factory=dict)


def ambiguous(kind: str, candidates: list[Candidate]) -> ProtocolError:
    return ProtocolError(
        "conflict",
        f"{kind} locator matches {len(candidates)} resources; pass one candidate ref",
        details={
            "kind": kind,
            "candidates": [candidate.model_dump() for candidate in candidates[:20]],
        },
    )


def not_found(kind: str, locator: Any) -> ProtocolError:
    return ProtocolError(
        "not_found",
        f"no {kind} matches the locator",
        details={"kind": kind, "locator": locator},
    )


def encode_file_ref(path: str) -> str:
    token = base64.urlsafe_b64encode(path.encode()).decode().rstrip("=")
    return f"{FILE_REF_PREFIX}{token}"


def decode_file_ref(ref: str) -> str:
    if not ref.startswith(FILE_REF_PREFIX):
        raise ProtocolError("invalid_request", "ref is not a host file ref")
    token = ref[len(FILE_REF_PREFIX) :]
    try:
        padded = token + "=" * (-len(token) % 4)
        path = base64.b64decode(padded.encode(), altchars=b"-_", validate=True).decode(
            "utf-8"
        )
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise ProtocolError("invalid_request", "file reference is malformed") from exc
    if not path or len(path) > 4_096 or not path.startswith("/"):
        raise ProtocolError("invalid_request", "file reference is malformed")
    return path


class FileLocator(GatewayModel):
    """A host file or directory by absolute path or canonical ref."""

    path: str | None = Field(
        default=None,
        min_length=1,
        max_length=4_096,
        description="Absolute host path; ~ expands to the gateway user's home.",
    )
    ref: str | None = Field(
        default=None,
        pattern=r"^sinnix://files/[A-Za-z0-9_-]{1,8192}$",
        description="Canonical host-file ref returned by an earlier call.",
    )

    @model_validator(mode="after")
    def exactly_one(self) -> FileLocator:
        if (self.path is None) == (self.ref is None):
            raise ValueError("give exactly one of path or ref")
        return self

    def resolve(self) -> tuple[str, str]:
        """Return ``(absolute_path, canonical_ref)`` without touching the disk."""
        if self.ref is not None:
            path = decode_file_ref(self.ref)
            return path, self.ref
        raw = Path(self.path or "").expanduser()
        if not raw.is_absolute():
            raw = Path.home() / raw
        path = str(raw)
        return path, encode_file_ref(path)
