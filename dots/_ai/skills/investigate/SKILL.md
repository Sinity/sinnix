---
name: investigate
description: Investigate bugs, regressions, incidents, performance problems, missing artifacts, and contested claims through reproduction, measurement, evidence preservation, and direct verification.
---

# Investigate

One discipline with three entries: a bug to diagnose, an incident to recover
from, a claim to verify. All three share the spine: **freeze evidence, build a
feedback loop, measure before touching production code**.

## Freeze first (incidents)

Before resolving conflicts, restoring files, or restarting services in an
incident: capture the current state (copy the conflicted worktree, save the
journal slice, snapshot the receipt/log) somewhere mutation cannot reach.
Recovery actions destroy evidence; a five-minute freeze is cheaper than a
lost cause. Then recover by checking authorities in order: filesystem and
worktree → git index and reflog → agent session records (claude-sessions,
Polylogue when live) → external Beads state → snapshots and backups.

## The diagnosis loop (hard bugs)

**Phase 1 — build a feedback loop. This is the skill; everything else is
mechanical.** A **tight** loop is one command that goes red on THIS bug:
fast (seconds), deterministic, agent-runnable. On this estate the loop
runner is `devtools test <selector>` — it carries the checkout guard,
frozen clock, and isolated fixtures (`workspace_env`); bare pytest silently
drops all three (`POLYLOGUE_ALLOW_BARE_PYTEST=1` exists for the genuine
one-off; needing it twice means the harness is missing something — fix the
harness). For non-test loops: a curl against a dev daemon, a CLI invocation
diffed against known-good output, a replayed captured artifact, a bounded
property loop. Flaky bugs: raise the reproduction rate (loop ×100,
parallelize, narrow timing) until debuggable.

Completion criterion: you can name one command, already run at least once,
that asserts the user's exact symptom — not "runs without erroring". No
red-capable command, no hypotheses. If you cannot build one, say so, list
what you tried, and ask for the artifact or access that would enable it.

**Phase 2 — reproduce and minimise.** Watch it go red. Then shrink to the
smallest scenario that still fails, cutting one element at a time; done when
every remaining element is load-bearing. The minimised repro becomes the
regression fixture.

**Phase 3 — hypothesise.** 3–5 ranked, falsifiable hypotheses ("if X is the
cause, changing Y makes it disappear") BEFORE testing any. One plausible
idea anchors; a ranked list doesn't. Show the list to the operator if
present; proceed on your ranking if not. Record disproved hypotheses on the
owning bead — the next session must not re-derive them.

**Phase 4 — instrument.** Each probe maps to one prediction; change one
variable at a time. Debugger/REPL beats logs; targeted logs beat log-
everything. Tag debug logs with a unique prefix so cleanup is one grep.
Performance: measure first (baseline harness, profiler, query plan), then
bisect — logs are usually the wrong instrument (absorbed from
the measure-first discipline: build the measuring harness BEFORE touching production
code; fix what the data implicates, not what the hypothesis flags).

**Phase 5 — fix + regression test at a production-reachable seam.** The
test must exercise the real bug path as production reaches it — a test
against a dead or parallel implementation certifies nothing (oracle-
integrity doctrine; this repo has four recorded wrong deletions from
grep-level reasoning). Red before the fix, green after. Where the check has
a registry home, give it a **red twin** — the mutation that proves the
detector notices. **If no correct seam exists, that is the finding**: file
it as a bead; do not ship a false-confidence test.

**Phase 6 — cleanup.** Original repro re-run green; tagged instrumentation
grepped out; throwaway harnesses deleted or moved to the scratch dir; the
confirmed hypothesis stated in the commit/PR/bead so the next debugger
inherits it.

## Verifying claims ("is X still true")

Check the fact that decides the question, not a proxy. Preconditions
inherited from notes or earlier passes are re-verified, not obeyed. Where
beads or docs make measured claims, re-measure before relying on them;
where they conflict with code, code wins and the stale carrier gets fixed
in the same change or a filed follow-up.

## Boundaries

Read-only by default: an investigation's deliverable is the assessment.
Do not apply fixes until asked (or the task is explicitly a fix). Never
mutate live archives, durable tiers, or services to test a theory —
copy to scratch and experiment there.
