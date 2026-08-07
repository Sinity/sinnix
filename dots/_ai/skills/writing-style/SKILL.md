---
name: writing-style
description: Use when writing or editing GitHub issues, pull requests, review comments, commit messages, chat replies, or prose documentation.
---

## Writing Style

Applies to anything meant for a human reader: GitHub issues, PR bodies, PR
review comments, commit message bodies, chat replies, and prose docs. Code
comments follow the separate, stricter rule in the Doing Tasks section above
(default to none).

- **No em dashes (—) or en dashes used as punctuation (–).** Rewrite with a
  period, comma, colon, semicolon, or parentheses instead: an em dash almost
  always signals AI-generated prose to an experienced reader, and it reads as
  a tell even when the content is sound. En dashes are fine only inside a
  literal numeric range (`3.10-3.18`, `~0.01-0.02 s`) or a compound modifier
  where the surrounding text already uses that convention; never as a
  substitute for a comma or parenthetical break.
- **No manual mid-paragraph line breaks on GitHub.** GitHub Flavored Markdown
  collapses a single `\n` inside a paragraph into a space, so hard-wrapping
  prose at ~72-80 columns (an editor/terminal habit) does nothing visually
  but leaves a paragraph-per-line ambiguity in the source and is itself a
  common tell. Write each paragraph, list item, and blockquote line as one
  continuous line in the source; let the renderer wrap it. This applies to
  `gh issue`/`gh pr` bodies and comments, GitHub API `body` fields, and PR
  review comments, not to code, tables, or fenced blocks, which keep their
  own line semantics.
- **Avoid other AI writing tells**: no "Not X, but Y" or "It's not just X,
  it's Y" contrast framing; no throat-clearing openers ("Let's dive into",
  "I'd be happy to", "Great question"); no stacking three parallel adjectives
  or clauses for rhetorical rhythm; no forced rule-of-three lists where two
  items or a single sentence would do; no unearned superlatives ("crucial",
  "seamless", "robust") without a concrete claim backing them; no summary
  restating what was just said ("In summary...", "To wrap up..."). Prefer
  plain, specific, declarative sentences over flourish.
- **When editing existing GitHub content to fix style** (comment/PR/issue
  bodies via `gh api`/`gh pr edit`/`gh issue edit`), pass the body via a temp
  file or JSON payload (`--input`, or a `json.dumps` payload piped to
  `--input`) and verify the API response actually contains the rewritten
  text, not the literal file reference. `gh api -f body=@file` does not
  reliably interpolate file contents on all `gh` versions and can post the
  literal string `@file.md` as the visible comment (confirmed 2026-08-01,
  flatpak/xdg-desktop-portal comment 5151219119).

---
