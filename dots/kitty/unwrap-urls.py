"""kitty hints kitten: open URLs that the emitting program hard-wrapped.

kitty's detect_urls reads the screen line by line, which is right for its own
soft wrapping. Some TUIs wrap long URLs themselves, emitting a newline and
indenting the continuation:

    Fetch(https://github.com/owner/Some-Very-Long-Repository-Nam
          e)

kitty then matches only the first fragment and opens a truncated URL. No
built-in option fixes it, because rejoining means guessing that indentation
is continuation rather than content.

The guess is deliberately narrow, since a wrong join opens a wrong address:
only extend a match that ends exactly at end-of-line, only across indented
lines whose content has no internal spaces, and at most MAX_CONTINUATIONS.
"""

from __future__ import annotations

import re


URL_RE = re.compile(r"(?:https?|ftp|file)://[^\s<>\"'`]+")

# A continuation is one run of URL-legal characters; internal spaces mean prose.
CONTINUATION_RE = re.compile(r"^([ \t]+)([^\s<>\"'`]+)[ \t]*$")

MAX_CONTINUATIONS = 4

# A fragment ending in one of these reads as complete, not cut mid-token.
COMPLETE_ENDINGS = set(".,;:!?)]}>\"'")


def _line_bounds(text: str, pos: int) -> tuple[int, int]:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return start, (len(text) if end == -1 else end)


def _rejoin(text: str, match: re.Match[str]) -> str:
    """Return the URL, extended across indented continuation lines."""
    url = match.group(0)
    _, line_end = _line_bounds(text, match.start())

    # Only a match that runs to end-of-line can have been cut by a wrap.
    if match.end() != line_end:
        return url
    if url[-1] in COMPLETE_ENDINGS:
        return url

    cursor = line_end
    for _ in range(MAX_CONTINUATIONS):
        if cursor >= len(text) or text[cursor] != "\n":
            break
        nxt_start = cursor + 1
        nxt_end = text.find("\n", nxt_start)
        nxt_end = len(text) if nxt_end == -1 else nxt_end
        cont = CONTINUATION_RE.match(text[nxt_start:nxt_end])
        if cont is None:
            break
        url += cont.group(2)
        cursor = nxt_end
        if url[-1] in COMPLETE_ENDINGS:
            break
    return url


def _strip_enclosing(url: str) -> str:
    """Drop punctuation the surrounding prose contributed.

    A closing bracket belongs to the URL only if the URL opened it, so this
    counts balance rather than stripping blindly -- real URLs contain
    parentheses (Wikipedia disambiguators).
    """
    pairs = {")": "(", "]": "[", "}": "{"}
    while url:
        last = url[-1]
        if last in ".,;:!?'\"":
            url = url[:-1]
            continue
        if last in pairs and url.count(pairs[last]) < url.count(last):
            url = url[:-1]
            continue
        break
    return url


def mark(text: str, args, Mark, extra_cli_args, *a):
    index = 0
    for m in URL_RE.finditer(text):
        joined = _strip_enclosing(_rejoin(text, m))
        if not joined:
            continue
        yield Mark(index, m.start(), m.end(), joined, {})
        index += 1
