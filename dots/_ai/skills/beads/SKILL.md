---
name: beads
description: "Read, claim, update, relate, close, or write Beads tasks with bd: ready work, notes, dependency edges, acceptance criteria, campaign epics, and follow-up filing."
---

# Beads

On this host, run `/run/current-system/sw/bin/bd` from the owning repository.
Long-lived project devshells can retain an older Beads build in PATH. The
commands below use `bd` as shorthand for the installed host executable.

Task state lives outside every checkout, in the Beads/Dolt database under
`/realm/state/tasks/<project>`, reached through the repository's `.beads`
redirect (`bd where` shows it). `bd` is the only write path. The current
directory selects the local store; prefix routes resolve another store's IDs,
so an edge may name a foreign ID. Pass `--actor <name>` (or set
`BEADS_ACTOR`); the default records the operator as author. Task mutations
create no Git commits and never belong on a feature branch. Task text is
public: no operator quotes, private paths, session IDs or personal data.

## Structure

A store has three levels: a release milestone, area epics, work items.

- **Area epics** are few and fixed. They mirror the product's subsystems under
  the names its docs use. An epic's description says what belongs in it and
  which doc pages own its design; it holds no work, notes or acceptance rows.
- **A work item is one coherent change one owner lands as one pull request**,
  or one operation run, or one decision. Work that needs the same source
  edits, evidence or test selection is one item whatever plan or report it
  came from. Split only where two owners could work at once on different
  files, or one part can be verified without the other.
- **A change across repositories is one item** in the store of the product
  whose behaviour changes, with a `repo:<name>` label for each other
  repository it touches. A prerequisite in another store is a `blocks` edge.
- **The release** is one milestone whose blockers are exactly what must be
  true to ship.

## Fields

- **Type:** `epic`, `milestone`, `feature` (a designed capability not built),
  `task` (a change to something built), `bug` (behaviour contradicts its doc
  page; name the sentence), `decision` (a question with options; closes with
  the answer), `spike` (one stated question; closes with the finding).
- **Priority:** 0 data is being lost or the host harmed now; 1 on the release
  path; 2 scheduled designed work; 3 after the release; 4 designed and
  unscheduled.
- **Status:** `in_progress` only through `--claim` by the owner who will land
  the item. `deferred` means designed and not scheduled; the description's
  last line says what would schedule it. `blocked` is derived from edges.
- **Title:** the outcome in plain words, no plan codes or ritual.
- **Description:** one paragraph with the outcome and why it matters, then
  `Scope:` with module names, then `Not in scope:` when a reader would assume
  otherwise. It is the single current contract: edit it, and correct related
  claims from the same investigation, instead of stacking amendments.
- **Design:** the modules touched, the approach and the rejected alternative
  with its reason, the invariants, the check command. Date file:line
  citations. Leave it empty when the doc page says it all.
- **Spec:** `--spec-id docs/<page>.md#<heading>`, the section that owns the
  behaviour.
- **Acceptance:** the native field, numbered lines, each observable and
  naming its check (a test or a command). Read them adversarially: could an
  executor satisfy the words and miss the point?
- **Estimate:** `--estimate` minutes of one worker, from comparable finished
  changes; unset without evidence.
- **Notes:** one dated paragraph of current state, replaced when the state
  changes. `--notes` and `--design` replace the field.
- **Comments:** dated evidence that outlives the current state (a measurement
  with its command, a disproved hypothesis, a ruling in paraphrase), appended
  with `bd comment`.
- **Labels:** `operation`, `operator`, `repo:<name>`. Area membership is the
  parent edge; plans and dates are not labels.
- **Metadata:** only keys a tool reads: `split_from` and `residual_of` (as
  `sinnix://projects/<project>/beads/<id>`).
- **Edges:** one parent, `blocks` for a real prerequisite, `discovered-from`
  for where a finding came from. A relation worth knowing otherwise is a
  sentence in the description.

Pass prose containing Markdown, backticks or shell metacharacters through a
file (`--body-file <path>`, `--design-file`, or `--stdin`). `--file` means
something else: it creates one task per `##` heading.

## Kinds of item

- **Code change:** acceptance is behaviour on the default branch. It closes
  when its commit is there and the named checks passed there.
- **Operation** (label `operation`): a deploy, live run, measurement on real
  data or host step. The description is the fixed list of checks to run
  against the deployment; it is blocked by the code items it exercises and
  closes with the run's evidence.
- **Operator decision** (type `decision`, label `operator`): the question, the
  options, the recommendation and what it holds up. It blocks its dependents
  and closes with the answer. Technical decisions go in the design field of
  the item they shape.
- **Designed, unscheduled capability:** a deferred `feature` at priority 4;
  small ones in one area share an item that lists each with its doc pointer.

## Workflow

1. **Select** with `bd ready`, `bd show <id>`, `bd graph --open <epic>`. Ready
   means dependency-ready; check the design for an operational window or
   consent. Status is a claim: check an item's statement about the code at
   head before dispatching it or accepting it as done.
2. **Claim** with `bd update <id> --claim`. An owner that stops early runs
   `bd unclaim <id>` and updates the notes.
3. **Change** on one branch and one pull request whose body ends with
   `Task: <id>`; set `--external-ref gh-<number>`.
4. **Close** when the acceptance rows are met under the project's delivery
   rules: `bd close <id> -r "<commit> #<pr>: <result>"`. Rows not met move to
   a successor with `residual_of` first. A close refused by an open blocker
   means close the blocker, or `--force` with the reason stated.
5. **Findings on the way** are fixed in the same change when they share its
   edits. Otherwise file a new item under its area at discovery time, with a
   real title and a `discovered-from` edge; never a note on an unrelated item.
6. **Coordinator checkpoint:** `bd orphans` (merged and still open),
   in-progress items whose owner has no session, worktree or pull request,
   `bd stale`, `bd lint`, `bd epic status`.

A wide refactor that cannot land in one change is split by callers: each item
moves a set of callers and deletes the old form for them, and the last deletes
what remains. A program too unclear to slice becomes `spike` or `decision`
items ordered by `blocks` edges, one sharp question each.

Bulk rewrites go through `bd export`, an edited JSONL and `bd import` (upsert;
labels and edges merge, so removals need `bd update --remove-label` and
`bd dep remove`). Keep the export as the restore copy.

## Writes that report an unclear result

A `bd` write that ends with a connection loss or "result indeterminate" may
have applied. Read the item (`bd show`, or `bd list` for a create) before
retrying, so the write is never applied twice.
