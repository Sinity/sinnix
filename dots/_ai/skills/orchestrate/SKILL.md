---
name: orchestrate
description: Orchestrate parallel agent implementation, research, or continuous queue work through explicit ownership, model selection, AgentCTL jobs, structural review, and one integrated batch.
---

# Orchestrate

Coordinator rule: the orchestrating session specifies and reviews; workers
execute self-sufficiently; mechanics route through AgentCTL. Token spend is
judged per merged outcome (rough proxy, not a metric to game).

## Model selection

| Role                                       | Route                            | Model            | Effort     |
| ------------------------------------------ | -------------------------------- | ---------------- | ---------- |
| Specification, review, integration         | this session                     | (session model)  | default    |
| Context-carrying analysis                  | fork                             | inherited        | —          |
| Implementation lane (well-specified beads) | `agentctl agent --backend codex` | gpt-5.6-luna     | medium     |
| Escalated lane (luna floundered)           | same                             | gpt-5.6-terra    | high       |
| Design / debug / adversarial review        | Agent tool or backend claude     | claude-opus-5    | high       |
| Review alternate (Claude quota tight)      | backend codex                    | gpt-5.6-sol      | high       |
| Menial coordination (≥3 live lanes)        | Agent tool                       | claude-haiku-4-5 | medium     |
| Broad read-only sweeps                     | Agent tool                       | sonnet or luna   | low/medium |

Rules: every dispatch names its model explicitly (only forks inherit).
Luna-first is quota-driven (separate Codex pool) AND review-driven
(cross-family review has uncorrelated failure modes). When a lane is stuck,
LOWER effort or switch model — never crank effort upward (spinning-in-
circles failure mode). Escalate luna → terra on the first flounder; don't
retry luna against the same failure. Multi-model redundancy runs only on a
predeclared trigger — irreversible action, destructive-data risk, no
executable oracle, or concrete disagreement after a first analysis; otherwise
one accountable decision-maker decides (broad "run 2-3 models on anything
that matters" recreates the review spiral). Majority voting is NOT a
substitute for a strong judge when errors are correlated: exp-008
(2026-08-26) measured 3×luna majority at 4/6 vs opus 5/6 on adjudication
rows — voting canceled the one correct minority verdict because two lunas
made the SAME error. Known correlated biases: deletion-aversion (every
judge, opus included, refused a gold DELETE whose justification lived in
the replacement plan) and merge-aversion (MOVE chosen over MERGE without
duplication evidence). For DELETE/MERGE-shaped decisions, supply the
replacement/dedup context in the prompt or escalate to one strong judge;
redundancy only buys anything against uncorrelated failure modes. External evidence, current pricing, and supervision
economics: `references/model-landscape-2026-08.md`. The standard dispatch
contract (self-verifying workers, no review chains, report-or-it-didn't-happen)
and the measured process smells that killed the 2026-08 coordinator:
`references/worker-contract.md`. Experiment registry rules (stopping rules,
expiry, piggyback-first): `references/experiment-protocol.md`. Hunt target
ranking: `scripts/defect_priors.py` (bandit priors over module × lens; run
it before any hunt wave — never pick targets by intuition).

## Dispatch mechanics (real verbs only)

- Dispatch: `agentctl campaign run` for a wave, `agentctl packet launch
  <bead>` for one bead. An interrupted lane (timeout, preemption) resumes
  with `agentctl lane resume <workspace>` — never hand-write continuation
  prompts or derive checkout digests.
- Publication: `agentctl lane publish <workspace> [--close]` — the one
  verb; it mints, routes, arms auto-merge, and hands off to the reactor.
  Never hand-compose authorize parameter JSON. Flagged receipts arrive as
  judgment items; clean ones publish themselves.
- Observation: ONE persistent Monitor on `agentctl events tail --follow`
  (typed kinds: lane, harvest, needs-merge, alert). Completion events are
  authoritative — no per-job wait loops, no polling.
- In-session subagents (Agent tool) for read-only analysis, judged panels,
  and forks for context-carrying work.
- Heavy host operations (full corpus runs, rehearsals) run as declared
  operations so admission can see them — out-of-band heavies make the
  preemptor kill innocent jobs. Long arcs state expected duration with
  evidence; overshoot >50% is a finding.
- The coordinator's judgment surface: scope-drift flags, schema flags,
  adversarial reviews of risky lanes, and oracle authorship (a read-only
  probe against real state that gates authorize — fixture-green alone is
  not evidence for state-touching work).

## Lane contract

- A lane = one worker + one workspace + **one independently verifiable
  change**, bounded by ownership, conflict keys, and expected runtime — its
  bead count may be one or many (bead count is tracker shape, not work
  size; see [[bead-authoring]]). One integration branch per lane; one PR
  per coherent batch.
- The dispatch prompt carries task content only (bead ids, files, scope,
  verification selector); the standing lane rules live in the agent
  definition, not pasted per prompt. Communicate by **pointer** (bead ids,
  spec paths, commit SHAs), not by duplicating content.
- Workers commit each completed logical chunk, run their exact focused
  selector, and report with an anti-vacuity statement (what production
  dependency the work exercises; what was NOT done).

## Structural review (non-negotiable)

Never accept a lane on its own report. Review = diff + typed verify result

- the lane's last message; transcripts only when something smells. Default
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
jobs cannot exceed 3600s (oy37.10). Resume exists: `agentctl lane resume`
(and `job retry --hint` / `job resume --session-id` underneath) — a lane
interrupted by timeout or preemption continues in place.
