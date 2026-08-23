---
name: claude-sessions
description: Extract readable prose from raw Claude Code session JSONL — list sessions and render a session's user/assistant text (optionally thinking and tool one-liners) without the tool-result bulk. Use when a session's accumulated understanding must be preserved, re-read, summarized, or handed to another agent, and Polylogue ingestion is unavailable or too indirect. Stopgap: prefer Polylogue search/read for archived history once it is operational.
---

# Claude sessions (raw JSONL stopgap)

Raw transcripts live at `~/.claude/projects/<munged-project-dir>/<session>.jsonl`.
Most bytes are tool results and harness metadata; the durable value is the
prose. This skill's helper extracts exactly that.

## Commands

```bash
scripts/sinnix-claude-session list [--project=-realm-project-polylogue] [--limit N]   # use = form: names start with a dash
scripts/sinnix-claude-session prose <session-id-or-path> [--thinking] [--tools] [--sidechains] [--out FILE]
```

- `list` shows sessions newest-first with size and the first real user
  message, across all projects or one.
- `prose` renders user + assistant text as markdown. `--tools` adds one-line
  tool-call summaries (name + command/path hint); `--thinking` includes
  thinking blocks as quoted asides; tool results are always omitted (bulk,
  not prose). Session ids may be unique prefixes; ambiguity is reported.

## Judgment

- A prose dump of a long session is still large; for handoffs, extract then
  summarize, or pass `--out` and read selectively.
- `--sidechains` includes subagent transcripts — usually noise for
  understanding the main line of work.
- The stripped-reopenable-forked-session idea (condense a session by
  filtering its JSONL and resuming it) is deliberately NOT implemented here:
  resuming a hand-edited transcript is untested against the harness and
  belongs to a careful experiment, not a routine tool.
