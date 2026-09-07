---
name: claude-self-knowledge
description: Verify Claude model and harness capabilities, choose dispatch mechanics, locate local state, explain Claude Code behavior, or diagnose compaction, notification, permission, and model-resolution surprises.
---

# Claude harness verification

Verify version-dependent capabilities against the installed harness or current
official documentation. Model names, prices, limits, flags, notification
behavior, and context inheritance are not durable facts of this skill.
Use `orchestrate` for model allocation and `agent-runtime` for managed jobs.

## Establish the actual surface

1. Read `claude --version` and the relevant `--help` output. Resolve the
   executable and wrapper before attributing behavior to the upstream CLI.
2. Inspect the applicable settings, agent definition, and launch input.
   Avoid printing credentials or full inherited environments.
3. Compare the requested model/effort and permissions with the effective
   launch. A hook echoing a requested model does not prove server resolution.
4. For undocumented behavior, use an exposed documentation tool or current
   official documentation. A Claude-specific guide agent or API skill is
   usable only if this session actually exposes it. State unavailable evidence.

## Dispatch and context

- Determine whether the active tool creates a fresh context or a fork, what
  model controls it accepts, and how completion is delivered. Do not assume
  another harness's subagent semantics apply.
- This environment's Claude Agent hook requires an explicit model for fresh
  dispatches and exempts forks. Inspect the installed hook and its settings
  binding when enforcement differs from the request.
- Agent definitions carry standing role/tool constraints. Dispatch packets
  carry task scope, ownership, and evidence. Read both before explaining an
  unexpected permission or model choice.
- Use the harness's completion notifications or the managed runtime's event
  stream. Do not invent Monitor or ScheduleWakeup calls when no such tool is
  exposed. Give long work a bound and an accountable owner.
- Preserve task decisions and results outside conversation context. After
  compaction, reconcile Beads, Git, and runtime evidence; a summary is a guide
  to evidence, not proof that an operation completed.

## Local configuration and history

Sinnix owns agent sources under `dots/claude/`, shared skills under
`dots/_ai/skills/`, and client rendering under
`modules/features/dev/agents/`. Resolve `~/.claude/` links before editing:
some sources are live-linked, others are generated or copied on activation.
Wrapper profiles come from `flake/data/agent-lanes.nix`.

Use Polylogue for session history and `claude-sessions` for bounded raw-JSONL
recovery when the archive is unavailable. Subagent transcripts may retain
evidence after a worktree disappears; locate them from the session's actual
records rather than assuming a fixed transcript layout.

Managed batch manifests retain ownership and result references; pueue owns
job execution; Beads owns work and dependencies. Use these existing sources
instead of creating a hook-derived dispatch ledger. Missing capture coverage
is not proof that an action never occurred.

## Diagnose a surprise

Keep the exact request, installed version, launch identity, observed result,
and expected contract together. Reproduce through the user-visible route with
the smallest safe input. Separate a harness limitation, configuration choice,
permission refusal, unavailable evidence, and a model implementation error.
Report decision-relevant conclusions visibly; do not rely on hidden reasoning
or confidence as evidence. Respect permission refusals rather than rerouting
the same action around them.
