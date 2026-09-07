---
name: orchestrate
description: Orchestrate parallel agent implementation, research, or continuous queue work through explicit ownership, model selection, agentctl batches and jobs, structural review, and one landed candidate per batch.
---

# Orchestrate

The root session owns priorities, scope and consequential decisions. Delegate
bounded supervision and implementation; automate observation and mechanics
through `agentctl`. A started batch lands itself; new dispatches require an
agent or operator decision.

## The operating loop

1. Inventory: `agentctl view <project>`, open manifests,
   `git worktree list`, `bd ready`, the project's rules.
2. Start one coherent set of two to four workers:
   `agentctl batch start <project> <bead>… [--worker a,b]…`.
3. Wait for the `<project>:land:<run>` finished event; never poll.
4. `agentctl batch status <run>`: landed with an acceptance record, or a
   named failure to act on.

The corpus runs once at the master boundary through the descriptor's
`corpus` operation or its schedule, never per worker.

## Model selection

| Assignment | Initial model | Effort |
| --- | --- | --- |
| Bounded supervision, evidence collection, settled implementation | `gpt-5.6-luna` | high |
| Substantial implementation, investigation, candidate review | `gpt-5.6-terra` | high |
| Unresolved architecture, design-critical implementation | `gpt-6-astra` | high |

These are starting assignments to revise from experience. Every dispatch names
backend, model and effort explicitly; only forks inherit. Check the actual
launch, including resumes, against the intended assignment. Read
[allocation guidance](references/model-landscape.md) before choosing or
escalating a model, and the [trial protocol](references/experiment-protocol.md)
before changing a default from observed outcomes.

Use additional independent analysis for a named unresolved question involving
irreversible action, destructive-data risk, no executable oracle, or concrete
disagreement. One accountable reviewer decides from the evidence.

References: [worker contract](references/worker-contract.md) (compiled into
every worker prompt), [coordinator contract](references/coordinator-contract.md)
(takeover, verbs, stages). Run `scripts/defect_priors.py` before a hunt wave.

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
  packet at `.agentctl/prompt.md`; file each result with
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
- Assign scope review, schema review and oracle authorship to bounded workers;
  escalate unresolved decisions to the root. A state-touching change needs
  evidence from its production route as well as fixtures.

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

The descriptor's `focused` operation runs without extra arguments. Use an
argumentless check such as `verify_quick`; put exact test selectors in the
beads' `verification_commands`. Static checks, selected tests and a full
corpus prove different scopes; retain the command and receipt for each.
For Polylogue's graph and selection behavior, use the `polylogue` skill.

## Structural review

Follow the project's declared review policy. When review is required, its
assigned reviewer reads the candidate diff, verification evidence and worker
results; the root resolves escalated questions. If an authorized policy omits
independent review, report that fact. Model tier does not establish correctness.

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
