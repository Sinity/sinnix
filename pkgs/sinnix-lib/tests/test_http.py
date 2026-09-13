"""Framing and bounded JSON contracts for the shared HTTP body helper."""

from __future__ import annotations

import io

import pytest
from sinnix_lib.http import RequestBodyError, read_body, read_json_object


class ShortReader:
    def __init__(self, data: bytes, chunk_size: int = 1) -> None:
        self._stream = io.BytesIO(data)
        self.chunk_size = chunk_size
        self.requests: list[int] = []

    def read(self, size: int) -> bytes:
        self.requests.append(size)
        return self._stream.read(min(size, self.chunk_size))


@pytest.mark.parametrize(
    ("headers", "reason"),
    [
        ({}, "missing_content_length"),
        ({"Content-Length": ""}, "invalid_content_length"),
        ({"Content-Length": "wat"}, "invalid_content_length"),
        ({"Content-Length": "+1"}, "invalid_content_length"),
        ({"Content-Length": "1.0"}, "invalid_content_length"),
        ({"Content-Length": "1,2"}, "conflicting_content_length"),
        ({"Content-Length": ["1", "2"]}, "conflicting_content_length"),
        (
            {"Content-Length": "1", "Transfer-Encoding": "chunked"},
            "conflicting_framing",
        ),
        ({"Transfer-Encoding": "chunked"}, "unsupported_transfer_encoding"),
    ],
)
def test_rejects_invalid_or_ambiguous_framing(headers, reason):
    with pytest.raises(RequestBodyError) as raised:
        read_body(headers, io.BytesIO(b"{}"), max_bytes=100)
    assert raised.value.reason == reason


def test_same_duplicate_content_length_is_allowed():
    assert (
        read_body({"Content-Length": "2, 2"}, io.BytesIO(b"ok"), max_bytes=2) == b"ok"
    )
    assert (
        read_body({"Content-Length": ["2", "2"]}, io.BytesIO(b"ok"), max_bytes=2)
        == b"ok"
    )


def test_negative_integer_header_container_is_rejected():
    with pytest.raises(RequestBodyError) as raised:
        read_body({"Content-Length": -1}, io.BytesIO(), max_bytes=10)
    assert raised.value.reason == "negative_content_length"


def test_optional_missing_length_means_empty_body_without_reading():
    reader = ShortReader(b"unexpected")
    assert read_body({}, reader, max_bytes=10, require_content_length=False) == b""
    assert reader.requests == []


def test_zero_length_body_is_exact():
    reader = ShortReader(b"trailing")
    assert read_body({"Content-Length": "0"}, reader, max_bytes=0) == b""
    assert reader.requests == []


def test_maximum_is_checked_before_reading():
    reader = ShortReader(b"123")
    with pytest.raises(RequestBodyError) as raised:
        read_body({"Content-Length": "3"}, reader, max_bytes=2)
    assert raised.value.reason == "body_too_large"
    assert reader.requests == []


def test_short_reads_are_accumulated_to_exact_length():
    reader = ShortReader(b"hello", chunk_size=2)
    assert read_body({"Content-Length": "5"}, reader, max_bytes=5) == b"hello"
    assert reader.requests == [5, 3, 1]


def test_eof_before_declared_length_is_rejected():
    with pytest.raises(RequestBodyError) as raised:
        read_body({"Content-Length": "3"}, io.BytesIO(b"ab"), max_bytes=3)
    assert raised.value.reason == "truncated_body"


def test_reader_returning_non_bytes_is_rejected():
    class BadReader:
        def read(self, size: int):
            return "x"

    with pytest.raises(RequestBodyError) as raised:
        read_body({"Content-Length": "1"}, BadReader(), max_bytes=1)
    assert raised.value.reason == "invalid_body_reader"


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (b"", "invalid_json"),
        (b"[]", "json_not_object"),
        (b"null", "json_not_object"),
        (b"{bad}", "invalid_json"),
        (b'{"x": NaN}', "invalid_json"),
        (b"\xff", "invalid_json"),
    ],
)
def test_json_object_is_bounded_and_typed(raw, reason):
    with pytest.raises(RequestBodyError) as raised:
        read_json_object(
            {"Content-Length": str(len(raw))}, io.BytesIO(raw), max_bytes=100
        )
    assert raised.value.reason == reason


def test_json_object_parses_utf8_and_short_reads():
    raw = b'{"message":"caf\xc3\xa9","n":2}'
    assert read_json_object(
        {"content-length": str(len(raw))}, ShortReader(raw, chunk_size=3), max_bytes=100
    ) == {"message": "café", "n": 2}


def test_reader_os_error_is_typed():
    class BrokenReader:
        def read(self, size: int) -> bytes:
            raise OSError("closed")

    with pytest.raises(RequestBodyError) as raised:
        read_body({"Content-Length": "1"}, BrokenReader(), max_bytes=1)
    assert raised.value.reason == "invalid_body_reader"
