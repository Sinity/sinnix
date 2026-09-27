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
Give a native implementation worker one coherent ownership group and authority
to fix in-scope defects. Name the candidate base, assigned Beads, relevant
source seam, excluded scope, shared focused selection, and completion evidence.
Define ownership by the accepted outcome, not by a file list: connected callers,
tests, docs, schemas and generated sources needed to meet its criteria are in
scope without another permission round. Keep `write_scope` advisory for conflict
planning. Escalate changed criteria, real cross-owner conflicts, and live or
destructive actions.
Ask it to inspect its final diff against the base, trace affected production
callers and any predecessor path, fix what that inspection finds, then report
each unmet criterion with its actual blocker. Do not turn implementation,
testing, and self-check into separate handoffs for the same owner.

## The operating loop

1. Inventory the relevant rules, task state, active jobs/runs, and checkout.
2. Choose native work for a bounded or cohesive change, or an external AgentCTL
   batch for independent isolated groups. Allocate only as many owners as the
   dependency graph and host capacity justify; there is no fixed worker count.
   Put beads that need the same source edits or test selection in one ownership
   group. Finish its coherent source patch before running the focused selection.
3. Use one event watch per concern for queued work and wait for completion;
   native work is observed directly. Do not poll.
4. Read the result and acceptance evidence, then commit native changes or land
   the external candidate. One receipt may satisfy several beads when it tests
   their shared contract; do not repeat an unchanged selection for each bead.
   For task-bound native delivery, file the result after publication with
   `agentctl evidence file`; `docs/agentctl.md` owns its contract. Select
   focused checks for the changed contract; affected or full-corpus runs
   require an explicit request.

## Model selection

| Assignment                                                       | Initial model   | Effort |
| ---------------------------------------------------------------- | --------------- | ------ |
| Bounded supervision, evidence collection, settled implementation | `gpt-6-luna`  | medium |
| Substantial implementation, investigation, candidate review      | `gpt-6-sol` | medium |
| Unresolved architecture, design-critical implementation          | `gpt-6-astra`   | high   |

These are starting assignments to revise from experience. Read
[allocation guidance](references/model-landscape.md) before choosing or
escalating a model. Use Astra only when a specific unresolved architecture or
design decision warrants it.

Raise effort for a concrete problem that needs it; medium is the ordinary
starting point. Use independent analysis for a named unresolved question
involving irreversible action, destructive-data risk, no executable oracle,
or concrete disagreement. One accountable reviewer decides from the evidence.

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
  share a reproduced failure family, invariant, files, evidence, or a
  verification boundary go in one worker even when their initial file lists
  differ. Keep write scopes disjoint across workers.
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
- External workers commit their logical chunks, run the focused verification
  once after the owned patch is coherent, and exit with the result document:
  `candidate_sha`, each acceptance criterion marked with evidence, `unresolved`,
  `verification`.

## Verification

Use the descriptor's declared operation when a task selects one; put exact
test selectors in the bead's `verification_commands`. Static checks, selected
tests, and broad suites prove different scopes; retain the command and receipt
for each check that actually ran.
For Polylogue's graph and selection behavior, use the `polylogue` skill.

## Review at integration

The coordinator reads the integrated diff, assigned Beads, and verification
evidence before landing. It traces the consequential call paths, fixes or
returns concrete defects, and rechecks only affected evidence. This is ordinary
integration work, including when the project omits an independent review gate.
Add a separate reviewer only for a named unresolved risk, concrete dispute, or
declared project policy. Give that reviewer one question and a pinned candidate;
another pass requires a material diff change or an unresolved finding.

## Continuous queue mode

Use [[task-backend]] to select ready ownership groups, then choose native work
or an external batch according to cohesion, isolation, unattended execution,
and backend needs. Prioritize finishing work over filling slots; heavy
verification remains independently bounded by its declared job group.
