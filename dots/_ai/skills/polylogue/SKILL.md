---
name: polylogue
description: Query the Polylogue AI-session archive (Claude, Codex, ChatGPT, Gemini…) for past-work reconstruction. Use when the user references past agent sessions ("what was I doing", "we decided this before", "which session touched file X"), asks for a postmortem of a failed run, wants cost/usage accounting, or after context compaction when history must be recovered from evidence rather than memory.
---

# Polylogue

Polylogue archives every AI session on this machine and serves them through
MCP tools (preferred; ~96 tools under `mcp__polylogue__*`) and the `polylogue`
CLI. Use it instead of guessing what happened in prior sessions.

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

Each maps an intent to the tool sequence that answers it. The same recipes
exist as MCP prompts (`resume_context`, `postmortem_last`, `decisions_about`,
`unacknowledged_failures`, `sessions_touching_file`, `cost_of`) — invoke those
when the harness surfaces prompts.

**Resume work in a repo** — `find_resume_candidates(repo_path=<abs cwd>)` →
`get_resume_brief(session_id=<top hit>)` → `agent_coordination_brief(view="self")`
for concurrent-agent awareness → `blackboard_list(scope_repo=<repo>, unresolved=True)`
for notes/handoffs addressed to agents.

**Postmortem the last failure** — `find_abandoned_sessions(repo_path=…)` +
`find_stuck_sessions(since="14d")` → pick the session →
`get_postmortem_bundle(repo=…, since=…)` → `get_pathologies(repo=…, since=…)`.
Report what failed with tool_result refs, what remained undone, smallest next action.

**What did we decide about X** —
`list_assertion_claims(kinds="decision,judgment,lesson")` →
`query_units(expression='assertions where kind:decision AND text:"X"')` →
`search(query='near:"X"')` for undocumented decisions. Recorded assertions
outrank inferred prose; `status:candidate` rows are agent-proposed and
unreviewed — label them.

**Failures nobody acknowledged** —
`query_units(expression='sessions where repo:<r> since:7d AND exists action(output:failed)')`
→ `find_stuck_sessions(since="7d")` → per hit, `list_marks(session_id=…)` /
annotations; an existing mark means acknowledged.

**Sessions that touched a file** —
`query_units(expression='sessions where repo:<r> AND exists file(action:file_edit AND path:<p>)')`
(or `files where path:<p>` for per-action rows) → `search(query='"<p>"')` for
prose mentions. Path matching is substring — use repo-relative fragments.

**Cost accounting** — `cost_rollups(since=…)` → `session_costs(since=…, limit=10)`
→ `provider_usage(detail="summary")`. Honesty rules: `cost_usd` is
API-list-equivalent (subscription credits are a separate view; cache reads are
~free on Claude Max/Pro); Codex `input` includes cached tokens and `output`
includes reasoning — lanes are disjoint, never sum naively.

## Query DSL (CLI and `query_units`)

```
polylogue find 'repo:polylogue since:7d "schema migration"'
polylogue 'sessions where repo:sinex | actions where output:failed | group by tool | count'
```

Fields: `repo:` `origin:` `tag:` `path:` `tool:` `action:` `since:`/`until:`
`title:` `contains:` `near:"…"` `id:`. Unit sources: `sessions` / `messages` /
`actions` / `blocks` / `files` / `assertions` / `runs` / `observed-events`.
Bare unquoted words are rejected — signal intent with `find`, quotes, or field
syntax. Filter by `--origin` (e.g. `claude-code-session`, `codex-session`),
never `--provider`.

## Freshness

`polylogued` ingests continuously; check `polylogued status` if results look
stale. Raw session JSONL also lives under `~/.claude/projects/<project>/` for
anything not yet ingested.
