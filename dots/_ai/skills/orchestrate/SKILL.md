---
name: orchestrate
description: Orchestrate parallel implementation, research, or queue work with explicit ownership, model selection, agentctl batches, verification, and one landed candidate per batch.
---

# Orchestrate

The root session owns priorities, scope, allocation, and consequential
decisions. Use native agents for investigation, bounded help, and cohesive
implementation: they work in the shared checkout with disjoint write scopes,
while the coordinator commits the result. Use an AgentCTL external batch when
independent ownership groups need isolated worktrees and one integrated
candidate. Queued workers handle unattended work or execution through another
backend. Shared heavy commands are declared jobs. Each concern has
one accountable supervisor; a completed worker reports its result and exits.

## Dispatch and evidence

Read [allocation and dispatch guidance](references/model-landscape.md). Native
dispatch defaults to `fork_turns='none'`; deliberate full-history inheritance
uses explicit `fork_turns='all'` with no model or effort override. A bounded
packet expresses intent; check execution against owning launch/session metadata.

## The operating loop

1. Inventory the relevant rules, task state, active jobs/runs, and checkout.
2. Choose native work for a bounded or cohesive change, or an external AgentCTL
   batch for independent isolated groups. Allocate only as many owners as the
   dependency graph and host capacity justify; there is no fixed worker count.
3. Use one event watch per concern for queued work and wait for completion;
   native work is observed directly. Do not poll.
4. Read the result and acceptance evidence, then commit native changes or land
   the external candidate. For task-bound native delivery, file the result
   through `agentctl evidence file` after publication; `docs/agentctl.md` owns
   its contract. Select focused checks for the changed contract; affected or
   full-corpus runs require an explicit request.

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

References: [worker contract](references/worker-contract.md) (for external
batch workers), [coordinator contract](references/coordinator-contract.md)
(takeover, verbs, stages). Run `scripts/defect_priors.py` when a hunt needs
that prior evidence.

## Dispatch mechanics

- An external batch is several independent workers on one base commit landed as
  one candidate.
  `batch start` validates the members, writes the run manifest
  (`~/.local/state/agentctl/runs/<run>.json`), claims the beads, creates one
  worktree per worker, queues the workers in group `agent` and the landing
  task behind them.
- A worker is one ownership group: a seed bead plus its open
  `dispatch_group` members, or `--worker a,b` named explicitly. Beads that
  share files, evidence, or a verification boundary go in one worker; write
  scopes must be disjoint across workers.
- External workers use `batch start … --workers external`; the manifest names
  their worktrees and packets. File each result with `batch result`; the last
  result enqueues landing. Confirm each result is bound to the manifest's
  worktree and branch before landing.
- Continue, recover, and land through the verbs and stages in the
  [coordinator contract](references/coordinator-contract.md); it owns watches,
  resumes, result filing, and publication mechanics.

## External batch worker contract

- A worker = one agent + one worktree + one ownership group. It may complete
  several closely related beads. Its branch is a candidate; the landing task
  publishes.
- The packet carries task content only (bead ids, files, scope, verification
  selector). Standing rules live in `references/worker-contract.md` and the
  `lane` agent definition. Communicate by pointer — bead ids, spec paths,
  commit SHAs.
- External workers commit their logical chunks, run the verification selected
  by the task, and exit with the result document: `candidate_sha`, each
  acceptance criterion marked with evidence, `unresolved`, `verification`.

## Verification

Use the descriptor's declared operation when a task selects one; put exact
test selectors in the bead's `verification_commands`. Static checks, selected
tests, and broad suites prove different scopes; retain the command and receipt
for each check that actually ran.
For Polylogue's graph and selection behavior, use the `polylogue` skill.

## Structural review

Follow the project's declared review policy. When review is required, its
assigned reviewer reads the candidate diff, verification evidence and worker
results; the root resolves escalated questions. If an authorized policy omits
independent review, report that fact. Model tier does not establish correctness.

## Continuous queue mode

Use [[task-backend]] to select ready ownership groups, then choose native work
or an external batch according to cohesion, isolation, unattended execution,
and backend needs. Prioritize finishing work over filling slots; heavy
verification remains independently bounded by its declared job group.
