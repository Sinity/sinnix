---
name: writing-style
description: Write or edit prose people read — PR descriptions, issues, review comments, commit message bodies, chat replies, reports, and documentation.
---

# Writing style

For anything a person reads: PR and issue bodies, review comments, commit
message bodies, chat replies, reports, and prose documentation. Code comments
follow the repository's own rules.

- Write plain, specific, declarative sentences. Lead with the point; a claim
  earns an adjective only with the evidence beside it.
- Do not use em or en dashes as punctuation. Use a period, comma, colon,
  semicolon, or parentheses. An en dash is fine inside a numeric range
  (`3.10-3.18`).
- Avoid the patterns that mark generated prose: "not X, but Y" contrasts,
  openers like "Let's dive in" or "Great question", three parallel clauses for
  rhythm, forced lists of three, unbacked superlatives ("crucial", "seamless",
  "robust"), and closing summaries that repeat what was just said.
- On GitHub, write each paragraph, list item, and quote as one source line.
  GitHub Markdown joins hard-wrapped lines anyway, and the wrapping reads as a
  tell. Code, tables, and fenced blocks keep their own line structure.
- To post or edit a GitHub body, pass it through a file or JSON payload
  (`gh pr create --body-file`, `gh api … --input payload.json`) and check the
  response shows the real text. `gh api -f body=@file` can post the literal
  string `@file`.
