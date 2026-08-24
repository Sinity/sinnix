---
name: orchestrate
description: Orchestrate parallel agent implementation, research, or continuous queue work through explicit ownership, model selection, AgentCTL jobs, structural review, and one integrated batch.
---

# Orchestrate

Coordinator doctrine: the orchestrating session specifies and reviews; workers
execute self-sufficiently; mechanics route through AgentCTL. Token spend is
judged per merged outcome (rough proxy, not a metric to game).

## Model doctrine

| Role | Route | Model | Effort |
|---|---|---|---|
| Specification, review, integration | this session | (session model) | default |
| Context-carrying analysis | fork | inherited | — |
| Implementation lane (well-specified beads) | `agentctl agent --backend codex` | gpt-5.6-luna | medium |
| Escalated lane (luna floundered) | same | gpt-5.6-terra | high |
| Design / debug / adversarial review | Agent tool or backend claude | claude-opus-5 | high |
| Review alternate (Claude quota tight) | backend codex | gpt-5.6-sol | high |
| Menial coordination (≥3 live lanes) | Agent tool | claude-haiku-4-5 | medium |
| Broad read-only sweeps | Agent tool | sonnet or luna | low/medium |

Rules: every dispatch names its model explicitly (only forks inherit).
Luna-first is quota-driven (separate Codex pool) AND review-driven
(cross-family review has uncorrelated failure modes). When a lane is stuck,
LOWER effort or switch model — never crank effort upward (spinning-in-
circles failure mode). Escalate luna → terra on the first flounder; don't
retry luna against the same failure.

## Dispatch mechanics (real verbs only)

- Durable work: `agentctl workspace create` (worktree under /realm/worktrees)
  then `agentctl agent --project P --checkout C --prompt-file F --backend B
  --model M --effort E`. Agent jobs are single-shot (no resume yet) and
  capped at 3600s — for longer arcs, have the lane checkpoint
  (`agentctl workspace checkpoint`) and re-dispatch a continuation prompt.
- Job lifecycle: `agentctl job {get,wait,logs,result,cancel}`. Completion
  notifications are authoritative — **never poll**. One bounded deadline
  wakeup only when a runtime cannot notify.
- In-session subagents (Agent tool) for read-only analysis, judged panels,
  and anything needing this session's context (forks).
- Every dispatch of long-running work states its expected duration WITH
  evidence, and sets a ~2× deadline watchdog; overshoot >50% is a finding.

## Lane contract

- A lane = one worker + one workspace + a **cluster of 3–5 related beads**
  (same region/theme; see [[bead-authoring]]). One integration branch per
  cluster; no per-lane PRs — one PR per coherent batch.
- The dispatch prompt carries task content only (bead ids, files, scope,
  verification selector); the standing lane rules live in the agent
  definition, not pasted per prompt. Communicate by **pointer** (bead ids,
  spec paths, commit SHAs), not by duplicating content.
- Workers commit each completed logical chunk, run their exact focused
  selector, and report with an anti-vacuity statement (what production
  dependency the work exercises; what was NOT done).

## Structural review (non-negotiable)

Never accept a lane on its own report. Review = diff + typed verify result
+ the lane's last message; transcripts only when something smells. Default
cadence: one review per integrated batch, spot-checks per lane, Opus
adversarial review for risky lanes. This applies to EVERY unsupervised
executor regardless of tier — capable models fail confidently too.

## Batching

Gather context → decide the coherent change → apply → verify once with the
narrowest command that exercises the changed surface. No fix-one-error-
at-a-time loops; when a check fails, diagnose the whole failure shape and
batch the fixes.

## Continuous queue mode

Working a ready queue end-to-end: claim highest-value
ready cluster via [[task-backend]] → dispatch lane → review → integrate →
complete with verification evidence → repeat. WIP law: at most 6 concurrent
implementation lanes, one merge-ready train; respect campaign caps where a
milestone declares them.

## Known gaps (do not script around them silently)

`agentctl task create` is the typed cross-project creation route; agent
jobs cannot exceed 3600s or resume (oy37.10 / spec items open). When these
land, update this skill in the same change.
