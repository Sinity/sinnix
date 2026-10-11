---
name: beads
description: Read, claim, update, relate, close, or write Beads tasks with bd — ready work, notes, dependency edges, acceptance criteria, campaign epics, and follow-up filing.
---

# Beads

Task state lives outside every checkout, in the Beads/Dolt database under
`/realm/state/tasks/<project>`, reached through the repository's `.beads`
redirect (`bd where` shows it). `bd` is the only write path. The current
directory selects the local store;
configured native prefix routes can resolve foreign IDs. An unresolved foreign
prefix reports `task_store_mismatch` with the requested prefix and searched
store. Run from the owning repository, or use `-C`, for local reads and writes.
Pass `--actor <name>` (or set `BEADS_ACTOR`);
the default records the operator as author. Task mutations create no Git
commits and never belong on a feature branch.

## Reading

- `bd ready`, `bd list --status …`, `bd show <id>`, `bd graph --open <epic>`.
  The dependency graph is the authority: an epic is a closure gate over its
  `blocks` edges, so child counts and labels do not measure its completion.
- Ready means dependency-ready, not necessarily executable now. Check the
  design for an operational window, live authority, or operator consent
  before claiming.
- Status is a claim, not proof. Check a task's concrete claim against the
  code at head before dispatching it or accepting it as done; open tasks are
  often already fixed and closed ones sometimes are not.

## Changing

- Claim before working (`bd update <id> --claim`) and release what you will
  not finish. `agentctl batch start` claims its members and `batch land`
  closes the satisfied ones; batch workers never touch Beads.
- Record dated facts as you go with `bd note`: measurements, disproved
  hypotheses, operator decisions. Keep one current-state note per task,
  consolidating on contact, so a cold reader never mistakes a superseded
  amendment for the current plan. Never paste other tasks' status into a
  note; derive it from the graph.
- Turn prose dependencies into edges (`bd dep add`) the moment you notice
  them. Link follow-up scope to its origin with `discovered-from` or
  `supersedes`; for a split or residual, set `split_from` or `residual_of`
  metadata to `sinnix://projects/<project>/beads/<id>`. Origin links are not
  prerequisites; add `blocks` separately when one is.
- Pass task prose that contains Markdown, backticks, or shell metacharacters
  through a file (`--body-file <path>`, or `--stdin`), never through shell
  interpolation. `--file` means something else: it creates one task per `##`
  heading.
- List-valued metadata (`verification_commands`, `affected_paths`,
  `write_scope`, `acceptance_criteria`) takes a JSON array of non-empty
  strings or a `;`-separated string.

## Closing

Close when acceptance criteria are met under the project's delivery rules.
Leave a compact evidence note: the commit or PR and useful result, or current
code evidence for an already-completed task. Operational criteria stay open
until their live evidence exists. Record known failures and unrelated follow-up
scope honestly without blocking other completed tasks or narrating a checklist.

Split unfinished scope into a successor rather than stretching the closure.
A close refused by an open blocker means close the blocker first, or
`--force` deliberately with the reason stated. Batch housekeeping from one
wave into a few commands.

## Writing a task

A task is a prompt for an executor and a record for a cold reader. Write
enough that neither has to reconstruct intent.

- **Title** names the artifact or behavior ("Check X on the rebuilt archive"),
  never the ritual ("acceptance: emit receipt").
- **Description** opens with one plain paragraph: the outcome and why it
  matters. It is the single current contract; supersede it by editing, not by
  stacking correction notes.
- **Design** names the seams: modules touched, the chosen approach and the
  rejected one, invariants that must hold, and the focused verification
  command. Date file:line citations ("as of 2026-09-27").
- **Acceptance criteria** describe observable behavior, each checkable by a
  named command or inspection, with non-goals. Read them adversarially: could
  an executor satisfy the words and miss the point? Store them once in
  `metadata.acceptance_criteria` as `{id, text}` rows with stable IDs.
- **Operational proof** (a live run, a measurement, an operator window) stays
  an explicit criterion; a code-only delivery leaves it open.
- Add metadata only when something consumes it.

## Shaping work

- Slice implementation as tracer bullets: each task a narrow, complete path
  through schema, logic, surface, and test, sized for one worker. Group tasks
  that share files, evidence, or a verification boundary with
  `dispatch_group=<leader-id>` so one worker delivers them together; each keeps
  its own close. Remove the metadata when the leader closes.
- Sequence wide refactors expand, migrate, contract: add the new form, move
  callers in batches, then delete the old form, each step blocked by the one
  before.
- For a program too unclear to slice, file decision tasks: one sharp question
  each, ordered by `blocks` edges, closed by the recorded answer. A question
  you cannot yet state precisely stays a line in the parent epic until it
  sharpens.
- File a discovered follow-up at discovery time, linked to its origin, with a
  real title and edges. A ten-second follow-up with a ritual title costs more
  than it saves.
