---
name: orchestrate
description: Orchestrate parallel agent implementation, research, or continuous queue work through explicit ownership, model selection, agentctl lanes and jobs, structural review, and one integrated batch.
---

# Orchestrate

Coordinator rule: the orchestrating session specifies and reviews; workers
execute self-sufficiently; mechanics route through `agentctl`, which does
what it is told and reports. Nothing dispatches on its own.

## The operating loop

1. Merge everything already in progress (`agentctl lane sync <project>`
   closes what merged). Excisions land as whole merges, not as a trickle of
   partial branches.
2. Run the corpus **once**, at the master boundary, through the declared
   operation: `agentctl job start polylogue verify_all`. Never a corpus run
   per lane.
3. Read `agentctl view <project>`, decide, dispatch the next wave:
   `agentctl refill <project> --limit N` or `agentctl lane start <project>
<bead>` per bead.

A declared `schedule` in a project descriptor is the only autonomous driver,
and the opt-in refill timer the only other one.

## Model selection

| Role                                       | Route                                   | Model            | Effort     |
| ------------------------------------------ | --------------------------------------- | ---------------- | ---------- |
| Specification, review, integration         | this session                            | (session model)  | default    |
| Context-carrying analysis                  | fork                                    | inherited        | —          |
| Implementation lane (well-specified beads) | `agentctl lane start … --backend codex` | gpt-5.6-luna     | medium     |
| Escalated lane (luna floundered)           | `agentctl lane rebase … --model …`      | gpt-5.6-terra    | high       |
| Design / debug / adversarial review        | Agent tool or backend claude            | claude-opus-5    | high       |
| Review alternate (Claude quota tight)      | backend codex                           | gpt-5.6-sol      | high       |
| Menial coordination (≥3 live lanes)        | Agent tool                              | claude-haiku-4-5 | medium     |
| Broad read-only sweeps                     | Agent tool                              | sonnet or luna   | low/medium |

Every dispatch names backend, model, and effort explicitly; only forks inherit.
Luna-first is quota-driven (a separate Codex pool) and review-driven
(cross-family review has uncorrelated failure modes). When a lane is stuck,
LOWER effort or switch model. Escalate luna → terra on the first flounder.

Multi-model redundancy runs only on a predeclared trigger: irreversible
action, destructive-data risk, no executable oracle, or concrete disagreement
after a first analysis. Otherwise one accountable decision-maker decides.
Majority voting is not a substitute for a strong judge when errors correlate.
Known correlated biases: deletion-aversion and merge-aversion. For
DELETE/MERGE-shaped decisions, supply the replacement or dedup context in the
prompt, or escalate to one strong judge.

References: `references/model-landscape-2026-08.md` (pricing, supervision
economics), `references/worker-contract.md` (the text compiled into every lane
prompt), `references/coordinator-contract.md` (stateless takeover),
`references/experiment-protocol.md`. `scripts/defect_priors.py` ranks hunt
targets — run it before a hunt wave.

## Dispatch mechanics

- Wave: `agentctl refill <project> --limit N [--dry-run]`. One bead:
  `agentctl lane start <project> <bead>`. Both compile the worker contract
  into the prompt.
- Continue or unblock a lane: `agentctl lane rebase <project> <bead>` queues
  a fresh agent into the existing worktree; uncommitted work there is the new
  agent's.
- Publication: the worker's `lane publish` (or `agentctl lane publish
<worktree>`) opens the PR and arms auto-merge; branch protection, the
  required check and review land it. `agentctl lane sync <project>` closes
  merged beads and removes their worktrees.
- Observation: ONE persistent watch on `agentctl events tail --follow`.
  Completion events are authoritative; no per-job wait loops.
- Heavy host operations run as declared operations so pueue's per-group
  parallelism bounds them. Session subagents bypass pueue entirely: bound
  them explicitly (one pytest at a time, `-n 2`) or route the heavy step
  through `agentctl job start`.
- The coordinator's judgment surface: scope-drift flags, schema flags,
  adversarial review of risky lanes, and oracle authorship — a read-only probe
  against real state. Fixture-green alone is not evidence for state-touching
  work.

## Lane contract

- A lane = one worker + one worktree + one independently verifiable change,
  bounded by ownership and expected runtime. Its bead count may be one or
  many (a dispatch group). One branch per lane; one PR per lane.
- The dispatch prompt carries task content only (bead ids, files, scope,
  verification selector). Standing rules live in the worker contract.
  Communicate by pointer — bead ids, spec paths, commit SHAs.
- Workers commit each completed chunk, run their exact focused selector, and
  report with an anti-vacuity statement: what production dependency the work
  exercises, and what was not done.

## Verification

- `devtools verify` selects from the checkout's one testmon datafile
  (`.cache/testmon/testmondata`) and writes back. `--all` runs every test and
  still updates fingerprints. `--quick` is the static gates alone.
- A corrupt or foreign-format datafile stops the run with `graph_unusable`:
  delete the datafile and rerun.
- Wrongly skipped tests are acceptable; a refusal is not. A stale graph means
  run everything and say so.
- A package or interpreter change invalidates selection: report a full run.
- A selected green proves the selected scope only. Never launder it into a
  whole-suite claim.

## Structural review

Never accept a lane on its own report. Review = diff + typed verify result +
the lane's last message; transcripts only when something smells. One review per
integrated batch, spot-checks per lane, an adversarial pass for risky lanes.
This applies to every unsupervised executor regardless of tier.

## Batching

Gather context → decide the coherent change → apply → verify once with the
narrowest command that exercises the changed surface. When a check fails,
diagnose the whole failure shape and batch the fixes.

## Continuous queue mode

Claim the highest-value ready cluster via [[task-backend]] → dispatch lane →
review → integrate → complete with verification evidence → repeat. Keep the
agent frontier full up to pueue's configured `agent` group capacity and one
merge-ready train. Heavy verification remains independently bounded by its
own groups.

## Runtime architecture

pueue executes and observes every job: it owns the queue, the process, the
terminal result, and cancellation (`pueue pause -g <group>` freezes a group;
the backpressure timer does this under host stall). worktrunk owns worktree
creation and removal. Publication is `gh pr create` plus `gh pr merge --auto
--squash`; GitHub owns review, required checks, and merge. Systemd owns only
calendar-timer wake-ups for declared `schedule` operations and the opt-in
refill timer. `agentctl` is in-process: no daemon, no socket, no judgment.
