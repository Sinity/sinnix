---
name: investigate
description: Diagnose a bug, regression, flaky test, performance problem, incident, or missing artifact, or verify a contested claim, through reproduction, measurement, and preserved evidence.
---

# Investigate

Three entry points share one discipline: a bug to diagnose, an incident to
recover from, a claim to verify. Preserve the evidence, build a feedback loop,
and measure before changing production code. The deliverable is the
assessment; apply a fix only when the task is a fix.

## Incidents: freeze first

Recovery destroys evidence. Before resolving conflicts, restoring files, or
restarting services, copy the current state somewhere mutation cannot reach:
`scripts/freeze.sh --repo <path> --out <dir> [--conflict <file>…]` captures
status, reflog, diffs, and named conflicted files with hashes
([checklist](references/freeze-checklist.md)). Then recover by consulting
authorities in order, filesystem and worktree, Git index and reflog, session
transcripts, Beads, snapshots and backups, using
`scripts/recover-probe.sh` to probe them read-only
([matrix](references/recovery-matrix.md)). The freeze authorizes no repair;
each mutation names its exact target and is verified against the frozen state.

## Bugs: the diagnosis loop

1. **Build a loop.** One command that goes red on this exact symptom: fast,
   deterministic, runnable by you. Use the repository's focused test runner
   (it carries the project's isolation and fixtures), a request against a dev
   service, a CLI run diffed against known-good output, or a replayed
   artifact. For a flaky bug, raise the reproduction rate (repeat, parallelize,
   narrow timing) until it is debuggable. Done when you have run a command
   that asserts the symptom. If you cannot build one, say what you tried and
   ask for the artifact or access that would allow it.
2. **Minimize.** Cut one element at a time until every remaining element is
   needed. The minimal case becomes the regression fixture.
3. **Hypothesize.** Write three to five ranked, falsifiable hypotheses ("if X,
   then changing Y removes it") before testing any; one idea anchors, a list
   does not. Record disproved ones on the owning task.
4. **Instrument.** One prediction per probe, one variable at a time. A
   debugger beats logs; targeted logs beat logging everything; tag debug
   output with a unique prefix so removal is one grep. For performance,
   measure first (profiler, query plan, a baseline harness) and fix what the
   data implicates.
5. **Fix at a production-reachable seam.** The regression test must travel
   the path production takes; a test against a parallel or dead
   implementation proves nothing. Red before the fix, green after. If no such
   seam exists, that is the finding: file it rather than ship a test that
   cannot fail.
6. **Clean up.** Re-run the original reproduction, remove instrumentation and
   throwaway harnesses, and state the confirmed cause in the commit, PR, or
   task.

## Claims: "is X still true?"

Check the fact that decides the question, not a proxy. Re-verify
preconditions inherited from notes or earlier passes; re-measure measured
claims before relying on them. When a document disagrees with the code, the
code wins, and the document is fixed in the same change or a filed task.

## Boundaries

Never mutate live archives, durable state, or running services to test a
theory; copy to scratch and experiment there.
