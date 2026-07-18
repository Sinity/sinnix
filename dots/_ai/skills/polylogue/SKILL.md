---
name: polylogue
description: Query the Polylogue AI-session archive (Claude, Codex, ChatGPT, Gemini…) for past-work reconstruction. Use when the user references past agent sessions ("what was I doing", "we decided this before", "which session touched file X"), asks for a postmortem of a failed run, wants cost/usage accounting, or after context compaction when history must be recovered from evidence rather than memory.
---

# Polylogue

Polylogue archives every AI session on this machine and serves them through
MCP tools (preferred) and the `polylogue` CLI. Use it instead of guessing what
happened in prior sessions.

The MCP surface is a six-tool protocol-native algebra (polylogue-t46.8): the
default read role exposes exactly `query` / `read` / `get` / `explain` /
`context` / `status`. Authenticated write/review/admin roles additionally get
`write` (mutations), `judge` (assertion-candidate review), `run` (execute a
saved query), and `maintenance` (backfill/reindex operations) — up to 10
tools total, never the ~97 individual per-operation tools this skill
described before polylogue-t46.8.2/t46.8.3 landed (PR #3095). This requires
that PR merged and the daemon/MCP client restarted; if `mcp__polylogue__*`
still lists ~90+ tool names, the old surface is still deployed and this
skill's recipes below will not resolve — fall back to whatever tool names are
actually listed in that case.

## Two rules agents get wrong

1. **Archive root.** Repo-local `.claude/settings.json` may set
   `POLYLOGUE_ARCHIVE_ROOT=/tmp/polylogue-archive` (cloud-lane sandbox). Any
   live-archive CLI command needs
   `export POLYLOGUE_ARCHIVE_ROOT=$HOME/.local/share/polylogue` first, or you
   silently query an empty archive. The MCP server is already pointed at the
   live archive.
2. **Refs over dumps.** Cite `session_id` / `message_id` refs and fetch full
   text only for messages you will act on. Never paste whole transcripts into
   context or reports.

## Intent recipes

Each maps an intent to the tool call that answers it, over the six/ten-tool
surface. The same "resume" recipe also exists as the MCP prompt
`resume_context`.

**Resume work in a repo** —
`context(intent="resume", repo_path=<abs cwd>, cwd=<abs cwd>, recent_files=[...])`
returns session lineage, ranked resume candidates, project git branch/recent
commits, and provenance-gated assertion guidance in one call — this replaces
the old `find_resume_candidates` → `get_resume_brief` → `agent_coordination_brief`
→ `blackboard_list` chain.

**What did we decide about X** —
`query(expression='assertions where kind:decision AND text:"X"')` for recorded
decisions, then `query(expression='messages where text:"X"', projection="sessions")`
for undocumented discussions (ranked/top-k session search). Recorded
assertions outrank inferred prose; `status:candidate` rows are agent-proposed
and unreviewed — label them.

**Sessions that touched a file** —
`query(expression='files where path:<p>')` for per-action rows, or
`query(expression='"<p>"', projection="sessions")` for ranked prose mentions.
Path matching is substring — use repo-relative fragments.

**Cost accounting** — `status(scope="archive", include=("provider_usage",), ref=<origin or omit>)`
returns model-rollup usage without a billing estimate. Honesty rules:
`cost_usd` figures elsewhere in the archive are API-list-equivalent
(subscription credits are a separate view; cache reads are ~free on Claude
Max/Pro); Codex `input` includes cached tokens and `output` includes
reasoning — lanes are disjoint, never sum naively.

**Session-level listing/ranking without a saved view** —
`query(projection="sessions", origin=…, tag=…, repo=…, since=…, until=…, sort=…)`
for an exhaustive listing (omit `expression`), or add `expression="<text>"` for
ranked (top-k) search. This is the six-tool replacement for the old
`search`/`list_sessions` tools.

**A single object by ref** — `get(ref="session:<id>")` /
`read(ref="session:<id>", view="topology")` for lineage.

## Known gaps in the six/ten-tool surface (as of polylogue-t46.8.3, PR #3095)

These capabilities existed as individual tools before the cutover and do not
yet have a six/ten-tool equivalent — do not invent a call that references
them by their old names:

- **Postmortem/pathology reports** (`get_postmortem_bundle`,
  `get_pathologies`, `find_abandoned_sessions`, `find_stuck_sessions`) — no
  replacement yet. Use `query(expression='actions where output:failed', ...)`
  and read the hits directly as a manual substitute.
- **Personal-state listing** (`list_marks`, `list_annotations`,
  `list_saved_views`, `list_recall_packs`, `list_workspaces`,
  `list_corrections`, `blackboard_list`) — `write()` can create these
  objects (e.g. `operation="save_saved_view"`, `operation="blackboard_post"`)
  and `run(ref="saved-query:<id>")` can execute a saved view, but nothing in
  the current six/ten-tool surface lists them back. Track the ids you create.
- **Cost/usage rollups** (`cost_rollups`, `session_costs`) — only the compact
  `status(scope="archive", include=("provider_usage",))` summary is
  available; per-session or time-bucketed rollups are not.
- **Coordination status** (`agent_coordination_brief`) remains available as
  an MCP *prompt*, not a tool — invoke it as a prompt when the harness
  surfaces it; `status(scope="coordination")` is declared but not yet wired.

## Query DSL (CLI and `query`)

```
polylogue find 'repo:polylogue since:7d "schema migration"'
polylogue 'sessions where repo:sinex | actions where output:failed | group by tool | count'
```

Fields: `repo:` `origin:` `tag:` `path:` `tool:` `action:` `since:`/`until:`
`title:` `contains:` `near:"…"` `id:`. Unit sources for `query(expression=…)`
(no `projection` or `projection="default"`): `messages` / `actions` /
`blocks` / `assertions` / `files` / `runs` / `observed-events` /
`context-snapshots` / `delegations` — NOT `sessions` (use
`query(projection="sessions", …)` for session-level rows instead). Bare
unquoted words are rejected on the CLI — signal intent with `find`, quotes, or
field syntax. Filter by `--origin` (e.g. `claude-code-session`,
`codex-session`), never `--provider`.

## Freshness

`polylogued` ingests continuously; check `polylogued status` if results look
stale. Raw session JSONL also lives under `~/.claude/projects/<project>/` for
anything not yet ingested.
