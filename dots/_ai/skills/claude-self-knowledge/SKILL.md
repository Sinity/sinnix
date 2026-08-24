---
name: claude-self-knowledge
description: Verify Claude model and harness capabilities, choose dispatch mechanics, locate local state, explain Claude Code behavior, or diagnose compaction, notification, permission, and model-resolution surprises.
---

# Claude self-knowledge

Core discipline first: **capability facts rot faster than model knowledge**.
Anything version-gated (harness features, model ids, pricing, limits) must be
verified against a live source — `claude --version`, the claude-code-guide
agent (docs lookup), the `claude-api` skill (API/pricing) — not recalled from
training or from this file when precision matters. This file is the map, not
the territory; its snapshot date is 2026-08-11.

## Models (the family, and what tier means)

- Tiers by capability/cost: **Haiku** (fast/cheap; use medium+ effort — low
  effort Haiku is weak), **Sonnet** (workhorse; default for implementation
  lanes), **Opus** (strong generalist), **Fable/Mythos** (Claude 5 tier above
  Opus; Fable = generally available with dual-use safety measures, Mythos =
  same model for approved orgs). Current ids via the `claude-api` skill; never
  hardcode ids into durable configs without a verification note.
- Reasoning **effort** (low..max) is orthogonal to model choice and often the
  cheaper lever: Sonnet at high effort beats Opus at low effort on many tasks.
- **Context and compaction**: long sessions get summarized ("compacted");
  in-flight state that lives only in conversation memory is what compaction
  loses. Durable state belongs in files, AgentCTL records, and Beads — the
  conversation is a steering console, not RAM. After compaction, re-orient
  from Polylogue, AgentCTL, and Git evidence rather than trusting the summary.
- **Thinking vs output**: extended thinking is usually invisible to the
  operator; anything decision-relevant discovered while thinking must be
  restated in the visible reply. Never rely on the operator having seen it.

## The Claude Code harness (what exists, one line each)

- **Subagents** (Agent tool): fresh context, own transcript
  (`~/.claude/projects/<proj>/<session>/subagents/agent-<id>.jsonl` — survives
  worktree cleanup; recovery source for lost files). Background by default;
  completion auto-notifies the parent (>=2.1.211) — never poll.
- **Forks** (`/subtask`): inherit full conversation + system prompt + model
  (prompt-cache reuse); for context-heavy side-tasks; cannot nest.
- **Agent teams** (adopted narrowly 2026-08-12, env-gated): a normal
  coordination shape for READ-ONLY research/synthesis tasks — the blinded
  pilot showed teams beat independent subagents there (3.45 vs 2.73 weighted,
  faster critical path; protocol in git history of docs/agent-teams-pilot.json).
  Implementation/write work keeps the ordinary subagent doctrine. Mechanics:
  teammates = full sessions, shared task list + SendMessage mailboxes; no
  resume of in-process teammates; one team per session; teammates don't
  inherit lead model (explicit model per teammate, as with any dispatch).
- **Agent definitions** (`.claude/agents/*.md`): body = the subagent's entire
  system prompt; frontmatter: `model`, `effort`, `tools`, `isolation:
worktree`, `skills`, `memory`, `maxTurns`, hooks. Bake standing contracts
  here, not into per-dispatch prompts.
- **Hooks** (settings.json): lifecycle interception (PreToolUse can inspect
  full tool input and deny/warn; SubagentStart/Stop; SessionStart; Stop).
  Hooks are how "always/whenever X" automation actually happens — memory and
  CLAUDE.md text cannot self-execute.
- **Skills**: instruction packages loaded on demand (this is one). Shared
  across Claude/Codex/Gemini via sinnix `dots/_ai/skills/`.
- **Headless**: `claude -p --output-format json [--json-schema]` for scripted
  judgment calls with validated structured output; `--resume` for continuity;
  `--bare` for deterministic CI-style runs.
- **Permissions**: allow/deny rules + modes (auto mode has a classifier that
  can deny actions; a denial is user feedback, not an obstacle to route
  around).

## This machine specifically

- Config chain: sinnix repo `dots/claude/` → out-of-store symlinks →
  `~/.claude/` (settings.json, CLAUDE.md, hooks are instant-propagating;
  ADDING new skills/hook files needs a home-manager switch — check
  `readlink -f` when unsure which regime a file is in).
- Enabled here: fork subagents + experimental agent teams (settings env).

## Dispatch doctrine (this machine)

Grounded in measured fanout ops (2026-08-02) + capability research
(2026-08-03, digest: polylogue
`.agent/scratch/2026-08-03-claude-code-dispatch-capabilities.md`).

- **Explicit model on every fresh Agent dispatch.** Sonnet default, Haiku for
  triage-grade read-only lanes, Fable/Opus permitted for judgment lanes
  (design review, adjudication, postmortem synthesis) as an explicit choice —
  never via inheritance. **Mechanically enforced, hard, for every dispatch
  type** (tightened 2026-08-11): a global PreToolUse hook DENIES any Agent
  dispatch — bespoke-prompt, named agent definition, or teammate spawn —
  that omits `model` at the call site. A named agent's own frontmatter
  `model:` does not exempt the call; every launch is auditable at the
  dispatch site. On every ALLOWED dispatch the hook emits a visible
  `systemMessage` confirming the resolved `subagent_type`/`model` (and
  teammate name) — affirmative feedback, visible across concurrent sessions.
- **Forks are exempt** (`/subtask`, `fork` type): they inherit context AND
  model by design (prompt-cache reuse). Right tool for context-heavy
  side-tasks; using a fork as a de-facto implementation lane violates the
  explicit-model rule in disguise. Forks cannot nest.
- **Teams caveats** (beyond the one-liner above): no resume of in-process
  teammates, one team per session, no nesting, teammates do NOT inherit the
  lead's model (specify per spawn; they DO inherit effort). Lab capability,
  not load-bearing process.
- **Never poll background agents** — completion notifications are automatic;
  Monitor only with an until-condition; ScheduleWakeup only for genuine
  wall-clock deadlines (CI grace windows, external state).
- AgentCTL records registered job state, including launch contract, checkout,
  result, cancellation, and recovery evidence. Polylogue retains session
  history; neither role is recreated from hook-derived transcript ledgers.
- For coordination, Beads owns work and dependencies; Polylogue blackboard
  assertions are durable asynchronous notes, not a delivered group chat.
- Wrappers: bare `claude` uses the lean profile; `claude-full` adds the full
  MCP profile, while `claude-browser` and backend variants select their named
  surfaces.
- Session history is ingested by Polylogue (`polylogued`); your own past
  behavior is queryable evidence — prefer archive queries over recollection
  for "what did I/agents do".

## Honest self-assessment heuristics

- You reconstruct rather than remember: prior-session knowledge comes from
  files, transcripts, and memory notes — treat unverified recall of your own
  past actions as hypothesis, not fact.
- Confidence and correctness diverge most on: version-gated features, negated
  instructions buried in long context, arithmetic over many items, and
  anything you'd rather were true (a fix you just wrote "surely" works —
  verify it).
- When behavior surprises (notification never arrived, tool result truncated,
  model seems wrong): suspect the harness layer first and check its actual
  contract (docs via claude-code-guide) before theorizing about the model.
