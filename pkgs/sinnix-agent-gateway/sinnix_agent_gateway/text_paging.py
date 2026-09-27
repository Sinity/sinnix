"""Helpers for lossless UTF-8 text paging over byte-oriented sources."""

from __future__ import annotations

import codecs


def decode_utf8_page(data: bytes, *, final: bool) -> tuple[str, int]:
    """Decode one page and return text plus the number of source bytes consumed.

    When ``final`` is false, an incomplete trailing UTF-8 sequence stays out of
    the returned text and byte count so the next page can start at that byte.
    """
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    text = decoder.decode(data, final=final)
    return text, len(data) - len(decoder.getstate()[0])
