# Model allocation and attribution

The table in `../SKILL.md` gives starting assignments, not capability rankings.
Choose from the decisions that remain open, the size of the implementation,
the evidence available, and the authority the worker needs. Writing the
specification is part of the work; count it when comparing choices.

## What actually ran

- A requested model, a role name, a prompt label, or a batch manifest states
  intent. The model that ran is established only by the launch or session
  metadata, checked for every attempt including resumes. Missing evidence
  stays unknown; do not infer capability, savings, or attribution from
  requested configuration.
- A role or runner may pin its own model and tools. Read its definition
  before assuming a per-dispatch override took effect.
- AgentCTL queued launches set backend, model, and effort explicitly.
- Instruction and skill files reached through live symlinks change on the next
  read, though a running agent keeps what it already loaded. Generated
  configuration changes only after its install or activation.
- Do not restart a running agent only to change its recorded model.

## Before dispatch

Revalidate any design or allocation judgment already recorded on the task
against current code; note the evidence and open choices in a dated task note.
A detailed packet does not make its design decisions settled. Name the
delivery the worker can finish with its authority, and keep every criterion,
including operational proof another owner must supply. Give a bounded design
task its own owner when its answer makes the implementation tractable; keep
design and implementation together when each needs the other's feedback.

## After an attempt

Join the launch, prompt, starting commit, result, and verification through
their run, worker, and attempt references. Launch arguments, commits, timing,
and recorded check results are observations; a worker's criterion statuses
are claims; a reviewer's assessment is an attributed judgment. Record
consequential hints, respecification, reviewer fixes, and inherited work in
the task note, and count them in the delivery's cost, not only the model that
made the final commit.

## Escalation

Inspect the concrete residual before changing models. When attempts fail
alike, compare prompts, roles, and launch metadata first. Reopen a design
judgment when implementation exposes a missing decision; move a concrete
implementation miss against settled requirements to a stronger tier with the
failing case and the preserved work. State what the next attempt must resolve;
repetition without a new diagnosis does not justify another retry or a higher
effort.

## Allocation trials

Test an allocation rule on work already worth doing, recorded in the owning
task rather than a separate ledger. A trial needs one decision it could
change, eligibility rules, assignment chosen before seeing outcomes
(alternating or randomized), comparable effort and review, outcome evidence,
a stopping rule, and an expiry. Resuming another model's work is an
intervention, not an independent sample. Close with the supported decision
(keep, revise for the observed task shape, or inconclusive), update the
instruction that uses it, and leave the outcomes in the task.
