---
name: orchestrate
description: Orchestrate parallel agent implementation, research, or continuous queue work through explicit ownership, model selection, agentctl batches and jobs, structural review, and one landed candidate per batch.
---

# Orchestrate

Coordinator rule: the orchestrating session specifies and reviews; workers
execute self-sufficiently; mechanics route through `agentctl`, which does
what it is told and reports. A started batch lands itself; nothing else
dispatches on its own.

## The operating loop

1. Inventory: `agentctl view <project>`, open manifests, `wt list`,
   `bd ready`, the project's rules.
2. Start one coherent set of two to four workers:
   `agentctl batch start <project> <bead>… [--worker a,b]…`.
3. Wait for the `<project>:land:<run>` finished event; never poll.
4. `agentctl batch status <run>`: landed with an acceptance record, or a
   named failure to act on.

The corpus runs once at the master boundary through the descriptor's
`corpus` operation or its schedule, never per worker.

## Model selection

| Role                                  | Route                                     | Model            | Effort     |
| ------------------------------------- | ----------------------------------------- | ---------------- | ---------- |
| Specification, review, integration    | this session                              | (session model)  | default    |
| Context-carrying analysis             | fork                                      | inherited        | —          |
| Implementation and investigation      | `agentctl batch start … --backend claude` | claude-opus-5    | high       |
| Design / debug / adversarial review   | Agent tool or backend claude              | claude-opus-5    | high       |
| Review alternate (Claude quota tight) | backend codex                             | gpt-5.6-sol      | high       |
| Menial coordination (≥3 live workers) | Agent tool                                | claude-haiku-4-5 | medium     |
| Broad read-only sweeps                | Agent tool                                | sonnet or luna   | low/medium |

Every dispatch names backend, model, and effort explicitly; only forks inherit.
Use another family when an independent failure mode is worth its cost, not as
the default implementation route. Codex sessions: `gpt-5.6-luna` at high for
the coordinating seat, `gpt-5.6-terra` at high for unattended workers;
`gpt-5.5` is retired for new work.

Multi-model redundancy runs only on a predeclared trigger: irreversible
action, destructive-data risk, no executable oracle, or concrete disagreement
after a first analysis. Otherwise one accountable decision-maker decides.
Majority voting is not a substitute for a strong judge when errors correlate.
Known correlated biases: deletion-aversion and merge-aversion. For
DELETE/MERGE-shaped decisions, supply the replacement or dedup context in the
prompt, or escalate to one strong judge.

References: `references/model-landscape.md` (pricing, supervision
economics), `references/worker-contract.md` (the text compiled into every
worker prompt, and the result schema), `references/coordinator-contract.md`
(stateless takeover, verbs, stages), `references/experiment-protocol.md`.
`scripts/defect_priors.py` ranks hunt targets — run it before a hunt wave.

## Dispatch mechanics

- A batch is several workers on one base commit landed as one candidate.
  `batch start` validates the members, writes the run manifest
  (`~/.local/state/agentctl/runs/<run>.json`), claims the beads, creates one
  worktree per worker, queues the workers in group `agent` and the landing
  task behind them.
- A worker is one ownership group: a seed bead plus its open
  `dispatch_group` members, or `--worker a,b` named explicitly. Beads that
  share files, evidence, or a verification boundary go in one worker; write
  scopes must be disjoint across workers.
- Claude subagents as workers: `batch start … --workers external` makes the
  same manifest, claims and worktrees and stashes the landing task. Run one
  `lane` subagent per worker in the worktree the manifest names, with the
  packet at `.lane/prompt.md`; file each result with
  `agentctl batch result <run> <worker> <result.json>`. The last result
  enqueues the landing task. Before trusting a subagent's output, confirm its
  worktree is the linked one the manifest names and is on the worker branch.
- Continue or unblock a worker: `agentctl batch resume <run> --worker <w>`
  queues a fresh agent into the existing worktree; uncommitted work there is
  the new agent's.
- Landing (`batch land`) integrates the worker branches, runs the candidate
  verification once, runs one reviewer on the candidate diff, publishes by
  the descriptor's policy, records acceptance and closes the beads whose
  criteria are all satisfied. Re-run it by hand after fixing a named failure.
- Observation: ONE persistent watch on `agentctl events tail --follow`.
  Completion events are authoritative; no per-job wait loops.
- Heavy host operations run as declared operations so pueue's per-group
  parallelism bounds them. Session subagents bypass pueue entirely: bound
  them explicitly (one pytest at a time, `-n 2`) or route the heavy step
  through `agentctl job start`.
- The coordinator's judgment surface: scope-drift flags, schema flags,
  adversarial review of risky workers, and oracle authorship — a read-only
  probe against real state. Fixture-green alone is not evidence for
  state-touching work.

## Worker contract

- A worker = one agent + one worktree + one ownership group. It may complete
  several closely related beads. Its branch is a candidate; the landing task
  publishes.
- The packet carries task content only (bead ids, files, scope, verification
  selector). Standing rules live in `references/worker-contract.md` and the
  `lane` agent definition. Communicate by pointer — bead ids, spec paths,
  commit SHAs.
- Workers commit every logical chunk in the foreground, run the focused
  selector, and exit with the result document: `candidate_sha`, each
  acceptance criterion marked with evidence, `unresolved`, `verification`.

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

Never accept a worker on its own result. The landing task's reviewer reads
the candidate diff, the verify receipt and the worker results; spot-check
workers yourself, and add an adversarial pass for risky ones. This applies to
every unsupervised executor regardless of tier.

## Batching

Gather context → decide the coherent change → apply → verify once with the
narrowest command that exercises the changed surface. When a check fails,
diagnose the whole failure shape and batch the fixes.

## Continuous queue mode

Start the highest-value ready ownership groups as batches via
[[task-backend]] for selection, keep the agent frontier full, and let each
batch land. Heavy verification remains independently bounded by its own
groups.

## Runtime architecture

pueue executes and observes every job: it owns the queue, the process, the
terminal result, and cancellation (`pueue pause -g <group>` freezes a group;
the backpressure timer does this under host stall). worktrunk owns worktree
creation and removal. GitHub owns review, required checks, and merge where the
project publishes through PRs. Beads owns tasks and claims. Systemd owns only
calendar-timer wake-ups for declared `schedule` operations. `agentctl` is
in-process: no daemon, no socket, no judgment.
