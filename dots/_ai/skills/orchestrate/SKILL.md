---
name: orchestrate
description: Orchestrate parallel implementation, research, or queue work with explicit ownership, model selection, agentctl batches, verification, and one landed candidate per batch.
---

# Orchestrate

The root session owns priorities, scope, allocation, and consequential
decisions. Delegate bounded supervision and implementation; automate mechanics
through `agentctl`. Each concern has one accountable supervisor: consolidate
normal successes, but report terminal failures and decision blockers promptly
before unrelated queue work continues. A completed worker checkpoints its work,
files its result, and exits; it does not need a perpetual status turn.

## Dispatch and evidence

Read [allocation and dispatch guidance](references/model-landscape.md). Native
dispatch defaults to `fork_turns='none'`; deliberate full-history inheritance
uses explicit `fork_turns='all'` with no model or effort override. A bounded
packet expresses intent; check execution against owning launch/session metadata.

## The operating loop

1. Inventory: `agentctl view <project>`, active jobs, manifests,
   `git worktree list`, `bd ready`, and the project's rules.
2. Finish or recover existing candidates before starting new work. Start one
   coherent, non-overlapping set of two to four workers only when it has a
   concrete delivery:
   `agentctl batch start <project> <bead>… [--worker a,b]…`.
3. Use one event watch per campaign concern and wait for the
   `<project>:land:<run>` completion event; do not poll.
4. Read `agentctl batch status <run>`: landed with an acceptance record, or a
   named failure with its next owner.

The corpus runs once at the master boundary through the descriptor's
`corpus` operation or its schedule, never per worker.

## Model selection

| Assignment                                                       | Initial model   | Effort |
| ---------------------------------------------------------------- | --------------- | ------ |
| Bounded supervision, evidence collection, settled implementation | `gpt-5.6-luna`  | high   |
| Substantial implementation, investigation, candidate review      | `gpt-5.6-terra` | high   |
| Unresolved architecture, design-critical implementation          | `gpt-6-astra`   | high   |

These are starting assignments to revise from experience. Read
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
- Continue, recover, and land through the verbs and stages in the
  [coordinator contract](references/coordinator-contract.md); it owns watches,
  resumes, result filing, and publication mechanics.

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

## Continuous queue mode

Use [[task-backend]] to select the highest-value ready ownership groups, then
let each useful batch land. Prioritize finishing candidates over filling slots;
heavy verification remains independently bounded by its own groups.

## Runtime architecture

pueue executes and observes every job: it owns the queue, the process, the
terminal result, and cancellation (`pueue pause -g <group>` freezes a group;
the backpressure timer does this under host stall). worktrunk owns worktree
creation and removal. GitHub owns review, required checks, and merge where the
project publishes through PRs. Beads owns tasks and claims. Systemd owns only
calendar-timer wake-ups for declared `schedule` operations. `agentctl` is
in-process: no daemon, no socket, no judgment.
