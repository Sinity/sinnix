---
name: orchestrate
description: Orchestrate parallel agent implementation, research, or continuous queue work through explicit ownership, model selection, agentctl lanes and jobs, structural review, and one integrated batch.
---

# Orchestrate

Coordinator rule: the orchestrating session specifies and reviews; workers
execute self-sufficiently; mechanics route through `agentctl`, which does
what it is told and reports. Nothing dispatches on its own.

## The operating loop

1. Inventory everything already in progress. Group compatible candidate
   commits into the smallest number of coherent integration batches; do not
   publish each lane independently.
2. Run the corpus **once**, at the master boundary, through the declared
   operation: `agentctl job start polylogue verify_all`. Never a corpus run
   per lane.
3. Read `agentctl view <project>`, decide, dispatch the next wave:
   `agentctl lane start <project> <bead>` for each ready ownership group.

A declared `schedule` in a project descriptor is the only autonomous driver,
and the opt-in refill timer the only other one.

## Model selection

| Role                                       | Route                                   | Model            | Effort     |
| ------------------------------------------ | --------------------------------------- | ---------------- | ---------- |
| Specification, review, integration         | this session                            | (session model)  | default    |
| Context-carrying analysis                  | fork                                    | inherited        | —          |
| Implementation and investigation lane      | `agentctl lane start … --backend claude` | claude-opus-5    | high       |
| Design / debug / adversarial review         | Agent tool or backend claude             | claude-opus-5    | high       |
| Review alternate (Claude quota tight)      | backend codex                           | gpt-5.6-sol      | high       |
| Menial coordination (≥3 live lanes)        | Agent tool                              | claude-haiku-4-5 | medium     |
| Broad read-only sweeps                     | Agent tool                              | sonnet or luna   | low/medium |

Every dispatch names backend, model, and effort explicitly; only forks inherit.
Use another family when an independent failure mode is worth its cost, not as
the default implementation route.

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

- Start one ownership group with `agentctl lane start <project> <leader-bead>`.
  Put closely related Beads in one dispatch group when they share files,
  evidence, or a verification boundary. Use `refill --dry-run` for discovery,
  not as an instruction to publish one PR per ready Bead.
- Continue or unblock a lane: `agentctl lane rebase <project> <bead>` queues
  a fresh agent into the existing worktree; uncommitted work there is the new
  agent's.
- Publication belongs to the coordinator after candidate commits have been
  integrated. Product repositories get one PR per coherent batch. Repositories
  that publish from their default branch get one verified direct integration.
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

- A lane = one worker + one worktree + one ownership group. It may complete
  several closely related Beads. Its branch produces candidate commits; it is
  not a publication unit.
- The dispatch prompt carries task content only (bead ids, files, scope,
  verification selector). Standing rules live in the worker contract.
  Communicate by pointer — bead ids, spec paths, commit SHAs.
- Workers commit the candidate, run the exact focused selector and quick gate,
  and report what production dependency the work exercises and what was not
  done. The coordinator integrates compatible candidates, resolves overlap,
  reviews the combined diff, and verifies the batch once.

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

Claim the highest-value ready ownership groups via [[task-backend]], keep the
agent frontier full, and drain completed candidates into one integration
batch. Heavy verification remains independently bounded by its own groups.

## Runtime architecture

pueue executes and observes every job: it owns the queue, the process, the
terminal result, and cancellation (`pueue pause -g <group>` freezes a group;
the backpressure timer does this under host stall). worktrunk owns worktree
creation and removal. Publication is `gh pr create` plus `gh pr merge --auto
--squash`; GitHub owns review, required checks, and merge. Systemd owns only
calendar-timer wake-ups for declared `schedule` operations and the opt-in
refill timer. `agentctl` is in-process: no daemon, no socket, no judgment.
