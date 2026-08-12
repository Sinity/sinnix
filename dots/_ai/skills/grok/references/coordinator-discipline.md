# Coordinator Discipline

Running the fleet is the easy part. The coordinator's real job — the part
that determines whether a campaign produces a usable, trustworthy tracker
state or a pile of noise — is triage, dedup, consistent blocking judgment,
and batched, verified filing.

## Cross-reference before filing, every time

A large fleet independently rediscovers the same root cause more often than
intuition suggests — different regions bordering the same file, or the same
bug shape (taxonomy category D/E especially) showing up in unrelated
subsystems. Before creating a new tracker item:

1. Search the tracker for the affected file/function/mechanism.
2. If a match exists and the new report adds nothing new: skip filing, at
   most add a short confirming comment if the new report meaningfully
   sharpens the existing item's understanding (a more precise mechanism, a
   concrete reproduction the original lacked).
3. If a match exists but the new report _corrects_ or _extends_ it (a
   follow-up agent found the original characterization was half-wrong, or
   the fix scope needs widening): update the existing item's description or
   append a correction comment — don't let the correction sit only in a
   chat transcript. Say explicitly what changed and why.
4. If a match exists and the new report independently derives the _same_
   finding with additional supporting detail (a different code path proving
   the same bug, a concrete exploit chain the original lacked): a
   substantive comment adding that detail is worth it even though no new
   item is filed — that detail sharpens whoever picks up the fix.

## Decide blocking criteria up front, apply them consistently

If findings feed a gate on some high-stakes downstream operation (a
migration, a release, a destructive data operation), write down the blocking
criteria _before_ triaging the first finding, and apply them the same way to
finding #1 and finding #200. A criteria set that drifts partway through a
campaign (getting stricter or looser as fatigue sets in) produces an
inconsistent, hard-to-trust gate. A criteria set that worked well in
practice:

- Would this finding leave the operation's _output_ itself deficient or
  corrupted?
- Would this finding prevent _detecting_ a partial failure of the operation?
- Is this finding a basic safety precondition specifically for the
  operation (not just "a bug that exists"), independent of whether it's
  otherwise low-severity?

Findings that are real and severe but don't meet the criteria (dormant code,
disabled-by-default features, tooling bugs orthogonal to the gated
operation) still get filed — they're just not blockers. Say so explicitly in
the filing, including the one-line reasoning for why it isn't a blocker; a
reader six months later shouldn't have to re-derive the judgment call.

## Batch, don't drip

Export/commit/push the tracker's durable state file (or equivalent) once per
coherent unit of work — a whole triage pass, a whole wave's findings, a whole
hygiene sweep — not once per individual finding. A commit history with one
line per finding drowns out everything else in the log and makes it hard to
see the actual shape of a campaign later. Do every mutation for the unit of
work first, verify graph/lint invariants, then one export + one commit + one
push covering the whole batch, with a commit message that groups findings by
source region/report and states the blocking decisions made.

## Delegate the mechanical volume, keep the judgment

Filing dozens of findings — writing descriptions, quoting code, setting
labels, running the export/commit — is exactly the kind of high-tool-call,
low-judgment work worth delegating to a fork (if your runtime supports
forking with shared context) so the raw tool traffic doesn't fill the
coordinating session's own context. Give the delegate the triage criteria,
the existing-tracker cross-reference discipline, and the batching rule
explicitly — don't assume it'll reconstruct your conventions from nothing
even if it shares your context, since a fork forgets nothing but still
benefits from an explicit checklist for a long mechanical task.

## Verify, don't just relay

Before reporting a delegated wave's results to whoever's waiting on them:
check the commit actually landed and pushed, that the dependency graph (or
equivalent structural invariant) is clean, and spot-check a handful of the
claimed filings by reading their actual content — not just trusting the
delegate's summary. A summary describes intent; the artifact is the
evidence. This catches both honest mistakes and the rarer case of a
delegate's self-report drifting from what it actually did over a long run.
