"""Core regex-based slop filter. Pure functions, no I/O beyond load_rules."""

from __future__ import annotations

import importlib.resources
import re
from dataclasses import dataclass

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern
    replacement: str  # "" = strip match; "STRIP_SENTENCE" = drop containing sentence


def load_rules(path: str | None = None) -> list[Rule]:
    """Parse phrases.txt (or an override path) into compiled Rules.

    Format: one rule per line, tab-separated `<regex>\\t<replacement>`.
    A line with no tab is a bare strip-match pattern (replacement = "").
    Blank lines and lines starting with '#' are ignored.
    """
    if path is None:
        text = (
            importlib.resources.files("sinnix_deslop")
            .joinpath("phrases.txt")
            .read_text()
        )
    else:
        with open(path, encoding="utf-8") as f:
            text = f.read()

    rules: list[Rule] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" in line:
            pattern_src, replacement = line.split("\t", 1)
        else:
            pattern_src, replacement = line, ""
        try:
            pattern = re.compile(pattern_src, re.IGNORECASE | re.MULTILINE)
        except re.error as e:
            raise ValueError(
                f"phrases.txt:{lineno}: invalid regex {pattern_src!r}: {e}"
            ) from e
        rules.append(Rule(pattern=pattern, replacement=replacement))
    return rules


def _strip_sentences_matching(text: str, pattern: re.Pattern) -> str:
    sentences = _SENTENCE_SPLIT.split(text)
    kept = [s for s in sentences if not pattern.search(s)]
    return " ".join(kept)


def deslop(text: str, rules: list[Rule] | None = None) -> str:
    """Apply every rule in order. Returns the cleaned text.

    Whitespace is normalized (collapsed runs of spaces, trimmed) after
    stripping, since removed phrases usually leave a double space behind.
    """
    if rules is None:
        rules = load_rules()

    out = text
    for rule in rules:
        if rule.replacement == "STRIP_SENTENCE":
            out = _strip_sentences_matching(out, rule.pattern)
        elif rule.replacement == "":
            out = rule.pattern.sub("", out)
        else:
            out = rule.pattern.sub(rule.replacement, out)

    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r" +\n", "\n", out)
    return out.strip()
