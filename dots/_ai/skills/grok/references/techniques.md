# Reading Techniques

These are the actual close-reading methods to put in a dispatch prompt, not
abstract advice — each is stated as something to instruct an agent to
literally do.

## Narration (forces attention)

The single highest-yield technique for catching bugs that pattern-matching
prompts miss. Instruct the agent to walk through the target file(s) and, for
every function or logical block, state in its own words what it does and what
invariant or assumption it's relying on — for the *whole* file, not just the
parts that look suspicious at a glance. Bugs hide precisely in the parts
nobody looks closely at; forcing a restatement of intent for every block
surfaces the gap between "what this code is supposed to guarantee" and "what
it actually does" even when nothing about the code's surface shape looks
wrong.

Minimal prompt shape:

```
Read this/these exact file(s) completely: <absolute path(s)>

Before concluding anything, narrate through the code section by section: for
each function or logical block, briefly state what it does and what
invariant or assumption it's relying on. Do this for the WHOLE file.

Then, based on that narration, report any real issues — [bug-shape list from
bug-pattern-taxonomy.md]. Give line numbers, quote the code, explain the
concrete failure scenario. If you narrated the whole file and found nothing
real, say so plainly.
```

Works especially well as a cheap second pass with a fast/small model against
a narrow 1-4 file target — the model doesn't need deep judgment to narrate
correctly, and narration is what surfaces the invariant worth judging.

This complements, rather than duplicates, the `analyze` skill's interactive
survey→narrate→synthesize workflow — `analyze` is for a user-steered single
session; this is the same core technique baked into an unattended, fan-out-
capable dispatch prompt for a whole campaign wave.

## Cross-referencing related functions

A single call site conforming to a convention is not proof the convention
holds elsewhere. When a region contains sibling implementations of the same
concept — multiple handlers for related RPC methods, multiple source drivers,
multiple repository methods touching the same table — explicitly instruct the
agent to diff them against each other, not just read each in isolation. This
is how the strongest class of findings in real campaigns turned up: one
sibling had a fix applied, another (structurally identical) sibling didn't
(e.g. a leak-prevention fix landed in one API endpoint but not three others
with the same shape).

## get → modify → put race audit

For any code that reads a value, computes something from it, and writes it
back (config merges, state-machine transitions, checkpoint saves, cache
invalidation), explicitly ask: what happens if another writer's mutation lands
between the read and the write? Distributed/concurrent systems hide races
exactly in this shape. Ask the agent to name the specific interleaving that
would corrupt state, not just note "there could be a race" — a named
interleaving is falsifiable and triageable; a vague race concern isn't.

## Adversarial refutation ("try to refute this")

For a candidate finding that seems too easy or too obvious, have a second
pass (a different agent instance, or the same one in a follow-up turn)
actively try to prove the finding is a false positive — check for a
compensating control elsewhere, a test that already covers it, a runtime
guarantee that makes the theoretical bug unreachable in practice. A finding
that survives an honest refutation attempt is much stronger evidence than one
that was never challenged. Don't skip this for high-severity findings you're
about to file as tracker blockers — being wrong about a blocker wastes real
downstream time.

## Doc-vs-code diff

Any doc comment, docstring, or module-level comment making a claim about
behavior ("mismatch → DLQ", "covers full and mixed notation", "never
swallows a failure") is a testable assertion, not just documentation — verify
it against the actual code path it describes. This surfaced real bugs
repeatedly: comments describing an intended guarantee that the code beneath
them had silently stopped providing (deliberately weakened without the
comment being updated, or never actually implemented as described).

## Reading the verification tooling as code, not as ground truth

Doctor/health checks, verify commands, and CI gates are code like anything
else, and are routinely under-scrutinized because their own output ("✓ All
checks passed") reads as authoritative. The specific failure shape to hunt:
a check that queries and *displays* real state but never actually gates
pass/fail on it (an `is_healthy()` that ignores half its own struct's
fields; a check whose `all()` over an empty collection vacuously returns
true; a dry-run mode whose "passed" flag doesn't reflect a printed error a
human would have to separately notice). Treat every verification/gate
function you encounter as itself a first-class audit target, not an oracle.
