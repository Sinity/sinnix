---
name: drive
description: Self-driving iterative execution - enhance a goal into the best next move, stress-test it, execute, externalize results, then forge the next self-prompt and continue. Use when the user says "drive", "keep going", "iterate on this", "take it further", wants to nod along while the agent picks directions, or asks for N autonomous iterations. Composes enhance (prompt forging) and grilling (adversarial stress) into a recurrence loop with optional auto-iteration.
---

# Drive: recurrent self-directed execution

The user gives a goal or an open frontier, not a task list. You repeatedly
choose the most promising next move, execute it thoroughly, make the results
durable, and then choose again. The user steers by interjection, not by being
asked for permission at every step.

This skill composes two siblings rather than replacing them:

- **enhance** remains the one-shot prompt-forging tool. Drive uses its
  workflow (intent kernel, executor fit, mission-first, compress) to forge
  each iteration's execution prompt.
- **grilling** remains the pure user-interrogation mode. Drive uses its
  question discipline (facts are looked up, decisions belong to the user,
  one question at a time) but points the interrogation at its own plan
  first, escalating to the user only what survives the filter.

## Invocation

```
/drive <goal>              gated recurrence (default): ask before each next iteration
/drive --auto[=N] <goal>   auto-iterate up to N iterations (default 5) without asking
/drive --once <goal>       single iteration, no recurrence (enhance + execute + report)
/drive --grill <goal>      run a full user-facing grilling FIRST, then start iterating
/drive --plan-only <goal>  produce iteration 1's enhanced prompt and stop
```

Mid-flight controls (the user can say these at any time, including as
interjections while you work): `pause` / `stop`, `auto` (switch to
auto-iteration), `gate` (switch back to asking), `redirect: <new direction>`.
Treat any interjection as immediate steering: fold it into the current
iteration, never queue it for later.

## The iteration contract

Every iteration has seven steps. Do not skip steps; do not let one iteration
sprawl into several directions at once.

### 1. Orient

Re-read the durable state first: the ledger (below), the tracker (Beads where
`bd where` succeeds), and any living report. Assume the session is ephemeral
and a compaction may have occurred since the last iteration. The ledger, not
your memory, is the authority on what has been done and what is frontier.

### 2. Reflect and choose

List 3-5 candidate directions with one line each. Pick one, or amalgamate,
and state the reasoning in a sentence or two. Selection heuristics, in order:

- **Leverage**: prefer the move that changes the cost of every later move
  (a mechanism, a sequencing decision, a reusable recipe) over the move that
  only consumes a work item.
- **Falsification**: prefer the move most likely to overturn a current
  belief early; a direction that can only confirm what you already think is
  worth less than one that can surprise you.
- **Durability**: prefer work whose output lands in carriers that outlive
  the session (tracker items, committed files, published reports).
- **Momentum**: an in-flight thread with warm context beats a cold start of
  equal value.

Parked candidates are recorded in the ledger with a word on why, so future
iterations do not re-derive them.

### 3. Forge the prompt (enhance)

Write the iteration's execution prompt using enhance's method: recover the
intent kernel, make it decision-complete for yourself as executor, name the
acceptance criteria and what would falsify success, compress once. Show it
compactly in your reply. It should be the smallest prompt that reliably
produces the intended result, not a ceremony.

### 4. Grill it (self first, user rarely)

Attack your own plan before executing, using the grilling stance turned
inward. Run the checklist:

- What premise, if wrong, wastes the whole iteration? Can it be checked in
  one cheap probe before committing? Then probe first.
- What is being assumed that the codebase, tracker, history, or live system
  could answer? Look it up now; asking the user facts is a defect.
- Which decisions genuinely belong to the user (product intent, risk
  acceptance, priority between real tradeoffs)?

The user-question rule inherits from both parents: escalate only decisions
that are the user's to make AND materially change the iteration. In gated
mode, ask at most one or two, one at a time, with your recommended answer.
In auto mode, do not block: take your recommended answer, and record it as an
explicit **assumption** in the digest so the user can veto it retroactively.

### 5. Execute thoroughly

Carry the forged prompt to its done-state. Batch related work; verify with
the narrowest command that exercises the changed surface; keep the ordinary
working rules (repo conventions, commit discipline, no scope drift beyond
the forged prompt).

### 6. Actualize (make it durable)

The session is ephemeral; the iteration is only as real as its externalized
residue. Before closing the iteration, push results into their durable
carriers:

- **Tracker first** (Beads where present): new findings become items or
  notes on the owning items; anything that would make a later executor
  faster (evidence, file:line anchors, recipes, impact estimates, named
  design decisions) goes into the item, not just the conversation. Follow
  the repo's export/commit discipline for tracker state.
- **Ledger**: update it every iteration (see format below).
- **Living report** (optional, for multi-audience work): revise in place,
  not append-only; republish to the same artifact URL so the link stays
  stable. The report is a view; the tracker and ledger are the state.
- **Code/files**: commit per the repo's rules when the iteration produced
  verified changes.

### 7. Close: next prompt + gate

End the iteration's reply with:

1. a compact **digest** (direction chosen and why; what happened; durable
   artifacts produced, with ids/paths; assumptions taken in lieu of
   questions; anything that surprised you);
2. the **next self-prompt**, forged to the same standard, with one or two
   parked alternatives named;
3. the **gate**: in gated mode, ask whether to run it. In auto mode,
   continue immediately unless a stopping condition fired.

## Auto-iteration stopping conditions

In `--auto`, continue by default; stop and hand back when any of these fire:

- **Cap**: N iterations completed (default 5; the user can raise it).
- **Blocked on the user**: a genuine user-owned decision gates all promising
  directions. Say exactly what the decision is and what you recommend.
- **Diminishing returns**: an iteration produced no new durable artifact and
  the reflection step cannot name a direction materially better than the
  parked ones. Do not manufacture busywork to keep the loop alive.
- **Risk boundary**: the best next move is destructive, outward-facing
  (publishing, mass edits, force operations), or irreversible. These always
  gate regardless of mode.
- **Contradiction**: new evidence overturned a load-bearing earlier
  conclusion. Stop so the user sees the correction before more work builds
  on it (record it in the ledger's self-corrections section either way).

On stopping, produce a final digest across all iterations, not just the last.

## The ledger

Working memory lives in a file, updated every iteration, structured not
prose. Default location: the project's scratch convention
(`.agent/scratch/drive-<topic>.md`), or `~/.claude/scratch/` for
cross-project work.

```markdown
---
created: <date>
goal: <the user's original goal, verbatim enough to re-derive intent>
mode: gated | auto(N)
status: active | stopped(<reason>)
---
## FRONTIER      what is genuinely unexplored / the next prompt
## ITERATIONS    one compact block per iteration: direction, outcome, artifacts
## PARKED        directions considered and skipped, with the one-line why
## ASSUMPTIONS   decisions taken on the user's behalf in auto mode (vetoable)
## SELF-CORRECTIONS  overturned claims, kept visible with both versions
## RULES         standing constraints the user has stated mid-flight
```

After any compaction: re-read the ledger before doing anything else.

## Failure modes to avoid

- **Recurrence theater**: iterations that summarize, reorganize, or re-plan
  previous iterations instead of producing new work. Each iteration must
  move the frontier.
- **Direction churn**: abandoning a thread mid-way because reflection
  surfaced something shinier. A started direction is finished or explicitly
  parked with its state recorded; it does not evaporate.
- **Asking as procrastination**: gating on a question whose answer you can
  probe, or which does not change the next iteration. The gate is for
  direction consent, not for reassurance.
- **Auto-mode scope creep**: auto grants continuation, not wider authority.
  The risk boundary and the repo's ordinary rules bind exactly as in gated
  mode.
- **Ledger rot**: a ledger updated at the start of the session and never
  again. Step 6 is part of every iteration, not optional.
