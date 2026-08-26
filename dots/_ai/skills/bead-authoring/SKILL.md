---
name: bead-authoring
description: Write or mature Beads tasks, specifications, acceptance criteria, dependency edges, and campaign slices so implementation can proceed without re-deriving intent.
---

# Bead authoring

The rule here is design-first: invest in beads until implementation
is the easy part, executable by a cheaper model without re-deriving intent.
A bead is a prompt for a future executor ([[prompting]]'s decision-
completeness applies in full) AND a durable record a cold reader must be
able to trust.

## The bead itself

- **Title names the artifact or behavior, never the ritual.** "Check X on
  the live archive after rebuild", not "acceptance: emit proof-carrying
  receipt". Verbs beat nouns; on jargon see [[writing-for-agents]].
- **Description is mission-first**: one paragraph of what outcome and why it
  matters, in ordinary language, before any mechanism. An id is a
  reference, never the mission.
- **Design says how and names the seams**: modules touched, the approach
  chosen and the one rejected (one line each), invariants that must hold,
  the focused verification selector (`devtools test <sel>` or equivalent).
  Cite file:line evidence — but date it ("as of 2026-08-23"); a dated stale
  pointer is diagnosable, an undated one is a trap.
- **Acceptance criteria are falsifiable and observable**: behavior, not diff
  shape; each AC checkable by a named command or inspection. Adversarial
  read before saving: can an executor satisfy the wording while missing the
  point? Include **non-goals** — scope substitution is the default failure.
- **Notes carry dated facts**: measurements, disproved hypotheses, operator
  rulings. Never hand-frozen snapshots of other beads' status — derive
  status from the graph (a known trap: pasted "current open
  blockers" lists that silently rot).

## Slicing

- **Tracer bullets**: each implementation bead cuts a narrow COMPLETE path
  through the layers (schema → logic → surface → test), demoable on its
  own, sized for one fresh worker context. Never a horizontal layer slice.
- **Wide refactors are the exception — sequence expand–contract**: expand
  (add the new form beside the old, nothing breaks) → migrate call sites in
  batches sized by blast radius, each batch a bead blocked by the expand →
  contract (delete the old form) blocked by every batch. Maps directly onto
  the generated-surface and schema-slot conflict machinery.
- **Blocking edges are the plan.** Wire them as real `bd` dependencies, not
  prose; the frontier (open, unblocked, unclaimed) is then queryable and
  the sequencing enforces itself. A bead with no blockers can start now.
- **Dispatch groups**: beads sharing a file, area, fix pattern, or required
  context get `dispatch_group=<leader-id>` metadata (leader's notes list the
  members) — one lane executes the group, one integration branch, one
  review. A lane is one independently verifiable change; its bead count may
  be one or many. Declare the shared files so collision detection has
  something to check.

## Decision beads (foggy programs)

For a program too foggy to slice, chart decisions, not deliverables: each
decision bead is one sharply-stated question whose resolution is a recorded
choice; blocking edges order them; the answer lands in the bead and closes
it. **Fog discipline**: if you cannot state the question precisely yet,
leave it as a named fog line in the parent epic — do not pre-slice fog into
fake tickets. Graduate fog to a bead the moment it sharpens. (A known
epic DESIGN/NOTES sections already carry fog lines; keep them there, not as
placeholder children.)

## Campaign structure

- Epics are closure gates over member dependency edges, not containers —
  membership by `blocks` edges + labels; `bd graph --open <epic>` is the
  closure authority, never child counts.
- One authority: the graph. No markdown mirrors, no scope ledgers, no
  duplicated boilerplate pasted across epics (write once in the root, point
  from members).
- A prototype or experiment that settled a design question gets kept as
  primary source (scratch branch or scratch file) with a pointer from the
  bead — the validated decision goes in the bead, the artifact stays
  findable.

## Maturing existing beads

When upgrading a backlog (the current mandate): verify measured claims
before propagating them; rewrite ritual-register titles; convert prose
dependencies into edges; split partially-done scope to successors instead
of letting a bead half-close; and check each AC against the falsifiability
bar above. A bead whose AC cannot be checked by a named command is not done
being written.
