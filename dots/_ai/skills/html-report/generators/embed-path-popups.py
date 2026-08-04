#!/usr/bin/env python3
"""Bundle local file content into `a.path` popups, automatically.

Usage: embed-path-popups.py <report.html> [--limit N] [--in-place | --out FILE]

Problem this solves: the skill's "openable path" pattern pairs every
`file://` link with a `<template class="pop">` excerpt, because the link
alone is dead weight once the report ships anywhere other than a local
`file://` open (Artifact hosting, a teammate's machine, a screenshot).
Hand-typing that excerpt into the HTML source means reading the file INTO
the agent's own context just to retype a piece of it back out — expensive,
and it silently goes stale the next time the file changes.

This compiles a lightweight SOURCE marker into the bundled popup instead:

    <a class="path" href="file:///abs/path/to/thing.md" data-embed>label</a>

`data-embed` (bare, or `data-embed="4000"` to override the byte limit) marks
the link for bundling. Running this script reads the referenced file fresh
from disk and inserts `label<template class="pop"><pre><code>ESCAPED
EXCERPT</code></pre></template>` as a child of the anchor -- the popup
mechanism in templates/report.html renders it with zero further wiring.
Idempotent: a link that already has a `<template class="pop">` child is
left untouched (re-run safely after adding new `data-embed` links without
re-bundling ones you've hand-edited).

Only `file://` targets under the local filesystem are read; anything else
(http(s) links, mailto:, bare `#anchor`) is left alone even if it happens to
carry `data-embed`.
"""
from __future__ import annotations

import argparse
import html as html_mod
import re
import sys
import urllib.parse
from pathlib import Path

DEFAULT_LIMIT = 4000

# One anchor tag with a data-embed marker, no pre-existing template.pop child.
# Anchors are assumed single-line in report source (this skill's convention);
# a multi-line anchor is rare enough to fix by hand if it ever occurs.
ANCHOR_RE = re.compile(
    r'<a\s+class="path"\s+href="file://(?P<path>[^"]+)"(?P<pre_attrs>[^>]*?)'
    r'\s+data-embed(?:="(?P<limit>\d+)")?'
    r'(?P<post_attrs>[^>]*)>'
    r'(?P<label>(?:(?!</a>|<template).)*)'
    r'(?P<already>(<template class="pop">.*?</template>)?)'
    r'</a>',
    re.S,
)


def bundle(html_text: str, *, default_limit: int) -> tuple[str, list[str]]:
    log: list[str] = []

    def repl(m: re.Match[str]) -> str:
        if m.group("already"):
            log.append(f"skip (already bundled): {m.group('path')}")
            return m.group(0)
        raw_path = urllib.parse.unquote(m.group("path"))
        path = Path(raw_path)
        limit = int(m.group("limit") or default_limit)
        if not path.is_file():
            log.append(f"MISSING (left unbundled): {raw_path}")
            return m.group(0)
        text = path.read_text(errors="replace")
        truncated = len(text) > limit
        excerpt = text[:limit]
        if truncated:
            excerpt += f"\n\n... (truncated at {limit} chars — full file at the path above)"
        escaped = html_mod.escape(excerpt)
        log.append(f"bundled ({len(excerpt)} chars{' truncated' if truncated else ''}): {raw_path}")
        attrs = m.group("pre_attrs") + m.group("post_attrs")
        return (
            f'<a class="path" href="file://{m.group("path")}"{attrs}>'
            f'{m.group("label")}<template class="pop"><pre><code>{escaped}</code></pre></template></a>'
        )

    new_text = ANCHOR_RE.sub(repl, html_text)
    return new_text, log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", type=Path, help="HTML report to bundle popups into")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"default per-file char cap (default {DEFAULT_LIMIT})")
    ap.add_argument("--in-place", action="store_true", help="write back to the input file (default)")
    ap.add_argument("--out", type=Path, help="write to a different file instead of in place")
    args = ap.parse_args(argv)

    html_text = args.report.read_text()
    new_text, log = bundle(html_text, default_limit=args.limit)

    dest = args.out if args.out else args.report
    if new_text != html_text or args.out:
        dest.write_text(new_text)

    for line in log:
        print(line, file=sys.stderr)
    bundled = sum(1 for line in log if line.startswith("bundled"))
    missing = sum(1 for line in log if line.startswith("MISSING"))
    print(f"embed-path-popups: {bundled} bundled, {missing} missing, {len(log) - bundled - missing} already-bundled/skipped", file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
