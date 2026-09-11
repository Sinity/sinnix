# Model allocation from observed work

Choose from the remaining decisions, implementation scope, available evidence,
and worker authority. The assignments in `../SKILL.md` are starting choices,
not capability rankings. Preparing a specification is work; include it when
comparing dispatch choices.

## Dispatch and inheritance

- Native Codex spawn exposes `model`, `reasoning_effort`, and `fork_turns`;
  backend is harness-determined. Claude's tool may lack an effort field, so
  use the current role/runner schema. AgentCTL queued launches explicitly set
  backend, model, and effort.
- Explicit model-controlled native dispatch uses the default agent role and a
  self-contained packet of role instructions. Role-constrained work uses the
  existing runner or AgentCTL route after inspecting its config; a native
  model/effort request cannot be assumed to override that role.
- Native dispatch defaults to `fork_turns='none'`. Deliberate full-history
  inheritance requires explicit `fork_turns='all'`, the same parent model, and
  no model or effort override; an omitted fork setting is invalid for that
  decision. A requested override never proves the child used it.
- Named roles may pin model and effort only where the current tool/runner
  schema supports them. Prompt labels, role names, and external batch manifests
  express intent; verify effective backend/model/effort in owning launch/session
  metadata, including every resume attempt. Missing evidence is explicitly
  unknown; persisted/requested config is not provider-resolved per-turn
  telemetry, so do not infer savings, capability, or attribution from it.
- Read the installed-mode contract: edits through a live symlink take effect
  immediately, though already-loaded context may not refresh; copied/generated
  config needs its owning install or activation, and a fresh context may still
  be required. Source edits alone are not proof of loaded state. Do not stop or
  restart an in-flight agent solely to reattribute its model.
- Use queued AgentCTL workers for durable isolated implementation/publication
  with explicit launch fields. Use native dispatch for bounded interactive
  analysis or shared integration only when the selected model is controllable;
  trivial read-only work need not become a batch. Do not add wrappers or ledgers.

## Before dispatch

Read the current bead and code. Revalidate existing design and allocation
judgments in its metadata or notes. These are
agent judgments: cite the evidence and unresolved choices in a dated bead note.
A detailed packet does not establish that its design decisions are settled.
Use existing fields and notes; add metadata only for a demonstrated consumer.

Name the delivery the worker can finish with its authority and available
evidence. Retain every acceptance criterion; identify any operational proof
that requires another owner or window. Such a criterion remains open after a
code-only delivery. Allocate a bounded design task when its answer makes an
implementation tractable; keep design and implementation together when their
feedback is necessary to resolve the problem.

Select explicit backend/model/effort using the main skill's assignments and
record why when departing from them. Check the current launch schema; the
effective values are established only by owning launch/session metadata.

## After an attempt

Join the exact launch, prompt snapshot, starting commit, result, and
verification by their existing run, worker, and attempt references. A resume
can change model and inherit code or hints, so inspect every attempt. Missing
launch or usage evidence stays explicitly unknown.

Keep machine facts separate from judgments. Launch arguments, commits, process
timing and recorded check results are observations. Worker criterion statuses
are claims; reviewer assessments and explanations of failure are attributed
judgments with evidence. Record consequential hints, respecification, reviewer
fixes and inherited work in the owning bead note with attempt references.

Assess reviewed delivery against the promised scope. Publication, criterion
supersession, and task closure answer different questions. Preserve partial
acceptance and missing proof; a changed criterion creates a changed comparison.
Review, interventions, and inherited work belong to the whole delivery's cost,
not solely to the model that produced the final commit. Do not infer savings
from elapsed time, queue slots, or labels.

## Escalation and cost

On an unresolved attempt, inspect the concrete residual before changing models.
Resolve missing authority, infrastructure or evidence through their owners.
Reopen a design judgment when implementation exposes a missing decision; use a
bounded architecture task or design-critical implementation assignment. For a
concrete implementation miss against settled requirements, consider Terra or
Astra with the failing case and preserved work. State what the next attempt
must resolve. Repetition without a new diagnosis does not justify more retries
or a higher effort setting.

Use observed usage and current applicable pricing for cost comparisons; include
specification, failed attempts, review, interventions, and inherited work.
Queue delay and agent runtime are separate measurements. Historical completion
rates confound task selection, revisions, inheritance, and infrastructure.
Apply the trial protocol before changing a default; keep model choice with the
accountable agent rather than an automatic router or completion leaderboard.
