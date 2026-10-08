---
name: claude-self-knowledge
description: Verify what the installed Claude Code harness does — versions, models, dispatch and forks, hooks, permissions, compaction, notifications, local state — or diagnose a surprising harness behavior.
---

# Claude harness facts

Model names, limits, flags, hook behavior, and context inheritance change
between releases. Establish them from the installed harness, not memory. Use
`orchestrate` for choosing models and `agent-runtime` for managed jobs.

## Establish the actual surface

1. `claude --version` and the relevant `--help`. The `claude` on PATH is a
   Sinnix wrapper; the real binary is under
   `~/.local/state/claude-code/npm/`. Attribute behavior to the wrapper or
   upstream only after checking which one acts.
2. Read the settings, hooks, and agent definition that apply, without
   printing credentials or whole environments.
3. For undocumented behavior, use the Claude Code guide agent or current
   official documentation when this session exposes one; the installed
   binary's strings settle what a specific version supports. Say which
   evidence was unavailable.
4. Compare the requested model, effort, and permissions with the effective
   launch. A hook echoing the requested model does not prove what the server
   ran.

## Local layout

Sinnix owns the sources: global instructions at `dots/_ai/AGENTS.md` (linked as
`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, and `~/.gemini/GEMINI.md`),
agent definitions and hooks under `dots/claude/`, shared skills under
`dots/_ai/skills/`, rendering under `modules/features/dev/agents/`, and
launcher profiles in `flake/data/agent-lanes.nix`. Instructions and skills are
live links, effective on the next read; generated settings and profiles
change at activation. Resolve `~/.claude/` links before editing anything.

The launchers declare `CLAUDE_CONFIG_DIR=$HOME/.config/claude`, with global
`.claude.json` inside that persisted directory so atomic replacement works.
Explicit custom roots remain supported. Check the active launch environment
before attributing a write failure to the declared layout.

## Dispatch and context

- Know whether a tool creates a fresh context or a fork, which model controls
  it takes, and how completion arrives. Another harness's subagent semantics
  do not carry over.
- Agent definitions carry standing role and tool limits; dispatch packets
  carry task scope. Read both before explaining an unexpected permission or
  model.
- Wait on the harness's completion notifications or the runtime's event
  stream, and use only the scheduling tools this session actually exposes.
- Keep decisions and results outside the conversation. After compaction,
  reconcile Beads, Git, and runtime records; a summary points to evidence, it
  does not prove an operation finished.

## History

Session history comes from Polylogue; `claude-sessions` reads raw transcripts
when the archive is unavailable. Subagent transcripts can outlive their
worktrees; locate them from the session's own records.

## Diagnosing a surprise

Keep the exact request, installed version, launch identity, observed result,
and expected contract together. Reproduce through the user-visible route with
the smallest safe input. Separate a harness limitation, a configuration
choice, a permission refusal, missing evidence, and a model error. Respect a
permission refusal instead of routing the same action around it.
