"""Bounded, length-delimited HTTP request-body primitives.

This module deliberately knows nothing about a server or response status.  It
validates the framing a handler received, consumes exactly the declared number
of bytes, and turns malformed input into one typed protocol error for the
adapter to map to its own response vocabulary.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, BinaryIO, Literal, cast


BodyErrorReason = Literal[
    "missing_content_length",
    "invalid_content_length",
    "negative_content_length",
    "conflicting_content_length",
    "conflicting_framing",
    "unsupported_transfer_encoding",
    "body_too_large",
    "truncated_body",
    "invalid_body_reader",
    "invalid_json",
    "json_not_object",
]


class RequestBodyError(ValueError):
    """A request body violated the bounded framing or JSON contract."""

    def __init__(self, reason: BodyErrorReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _header_values(headers: Mapping[str, Any], name: str) -> list[Any]:
    """Return all values for *name*, tolerating common header containers."""
    wanted = name.casefold()
    get_all = getattr(headers, "get_all", None)
    if callable(get_all):
        values = get_all(name)
        if values is not None:
            if isinstance(values, (str, bytes)):
                return [values]
            return list(values)

    values: list[Any] = []
    for key, value in headers.items():
        if str(key).casefold() != wanted:
            continue
        if isinstance(value, (list, tuple)):
            values.extend(value)
        else:
            values.append(value)
    return values


def _content_length(headers: Mapping[str, Any], *, require: bool) -> int:
    values = _header_values(headers, "Content-Length")
    if not values:
        if require:
            raise RequestBodyError(
                "missing_content_length", "Content-Length is required"
            )
        return 0

    numbers: list[int] = []
    for value in values:
        # RFC 9110 permits a comma-separated list only when every member is
        # the same decimal length.  Do not accept signs, whitespace inside a
        # value, or Python's broader integer syntax.
        if isinstance(value, bool):
            raise RequestBodyError("invalid_content_length", "invalid Content-Length")
        if isinstance(value, int):
            if value < 0:
                raise RequestBodyError(
                    "negative_content_length", "negative Content-Length"
                )
            numbers.append(value)
            continue
        if not isinstance(value, (str, bytes)):
            raise RequestBodyError("invalid_content_length", "invalid Content-Length")
        if isinstance(value, bytes):
            try:
                value = value.decode("ascii")
            except UnicodeDecodeError as error:
                raise RequestBodyError(
                    "invalid_content_length", "invalid Content-Length"
                ) from error
        for item in value.split(","):
            token = item.strip()
            if not token or not token.isascii() or not token.isdecimal():
                raise RequestBodyError(
                    "invalid_content_length", "invalid Content-Length"
                )
            try:
                number = int(token, 10)
            except ValueError as error:  # defensive: isdecimal is narrower
                raise RequestBodyError(
                    "invalid_content_length", "invalid Content-Length"
                ) from error
            numbers.append(number)

    if not numbers:
        raise RequestBodyError("invalid_content_length", "invalid Content-Length")
    if len(set(numbers)) != 1:
        raise RequestBodyError(
            "conflicting_content_length", "conflicting Content-Length values"
        )
    length = numbers[0]
    # A syntactically valid decimal cannot be negative, but retain a distinct
    # reason for custom header containers that supply an integer value.
    if length < 0:
        raise RequestBodyError(
            "negative_content_length", "negative Content-Length"
        )
    return length


def _validate_transfer_encoding(
    headers: Mapping[str, Any],
    *,
    has_content_length: bool,
    reject_conflicting_framing: bool,
) -> None:
    values = _header_values(headers, "Transfer-Encoding")
    if not values:
        return
    codings: list[str] = []
    for value in values:
        if not isinstance(value, (str, bytes)):
            raise RequestBodyError(
                "unsupported_transfer_encoding", "invalid Transfer-Encoding"
            )
        if isinstance(value, bytes):
            try:
                value = value.decode("ascii")
            except UnicodeDecodeError as error:
                raise RequestBodyError(
                    "unsupported_transfer_encoding", "invalid Transfer-Encoding"
                ) from error
        codings.extend(part.strip().casefold() for part in value.split(","))
    if not codings or any(not coding for coding in codings):
        raise RequestBodyError(
            "unsupported_transfer_encoding", "invalid Transfer-Encoding"
        )
    if has_content_length and reject_conflicting_framing:
        raise RequestBodyError(
            "conflicting_framing",
            "Content-Length and Transfer-Encoding cannot both frame a request",
        )
    # This helper has no chunk decoder and therefore cannot safely consume a
    # transfer-coded body.  ``identity`` is the sole harmless coding.
    if any(coding != "identity" for coding in codings):
        raise RequestBodyError(
            "unsupported_transfer_encoding",
            "transfer-coded request bodies are unsupported",
        )


def read_body(
    headers: Mapping[str, Any],
    reader: BinaryIO,
    *,
    max_bytes: int,
    require_content_length: bool = True,
    reject_conflicting_framing: bool = True,
) -> bytes:
    """Read exactly one bounded request body from *reader*.

    ``reader`` must provide ``read(size)`` and may return short reads.  The
    function never reads beyond the declared length.  A missing length is
    treated as a zero-length body only when ``require_content_length=False``;
    that option is intended for routes whose protocol explicitly permits an
    empty body.
    """
    if max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")
    values = _header_values(headers, "Content-Length")
    _validate_transfer_encoding(
        headers,
        has_content_length=bool(values),
        reject_conflicting_framing=reject_conflicting_framing,
    )
    length = _content_length(headers, require=require_content_length)
    if length > max_bytes:
        raise RequestBodyError(
            "body_too_large",
            f"request body is {length} bytes; maximum is {max_bytes}",
        )

    chunks: list[bytes] = []
    remaining = length
    while remaining:
        try:
            chunk = reader.read(remaining)
        except (OSError, ValueError) as error:
            raise RequestBodyError(
                "invalid_body_reader", "request body could not be read"
            ) from error
        if not isinstance(chunk, bytes):
            raise RequestBodyError(
                "invalid_body_reader", "request body reader returned non-bytes"
            )
        if not chunk:
            raise RequestBodyError(
                "truncated_body", "request body ended before Content-Length"
            )
        if len(chunk) > remaining:
            # A compliant reader must honor read(size).  Refuse a violating
            # adapter rather than silently accepting bytes belonging to the
            # next request on a persistent connection.
            raise RequestBodyError(
                "invalid_body_reader", "request body reader returned too many bytes"
            )
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_json_object(
    headers: Mapping[str, Any],
    reader: BinaryIO,
    *,
    max_bytes: int,
    require_content_length: bool = True,
    reject_conflicting_framing: bool = True,
) -> dict[str, Any]:
    """Read a bounded UTF-8 JSON object using :func:`read_body`."""
    raw = read_body(
        headers,
        reader,
        max_bytes=max_bytes,
        require_content_length=require_content_length,
        reject_conflicting_framing=reject_conflicting_framing,
    )
    try:
        value = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise RequestBodyError("invalid_json", "request body is not valid JSON") from error
    if not isinstance(value, dict):
        raise RequestBodyError("json_not_object", "request body must be a JSON object")
    return cast(dict[str, Any], value)


def _reject_constant(value: str) -> Any:
    raise ValueError(f"non-standard JSON constant: {value}")
