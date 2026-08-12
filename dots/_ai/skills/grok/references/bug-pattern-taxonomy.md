# Recurring Bug-Pattern Taxonomy

Six root causes that accounted for a disproportionate share of real findings
across large campaigns. Put these in every dispatch prompt as the specific
things to watch for — a generic "find bugs" instruction under-performs a
prompt naming concrete shapes. Each entry includes a grep-shaped starting
point; grep finds _candidates_, not verdicts — every hit still needs a real
read to confirm it's load-bearing and not already handled elsewhere.

## A. Hard-fail silently downgraded to soft-degrade

The language's error type has no distinction between "this must abort" and
"this may gracefully degrade." A `.unwrap_or_else(|e| { warn!(...); default()
})` on something that should hard-fail converts an intended abort into silent
continuation with a default/empty value — and the log line makes it _look_
handled.

Grep starting points: `unwrap_or_else`, `unwrap_or_default`, `.ok()` on a
`Result`, `let _ =` on a fallible call, `.flatten()` immediately after a
`query_map`/iterator-of-Results (silently drops per-item errors).

Ask per hit: if this really failed, does anything downstream notice? Would an
operator have any way to distinguish "genuinely nothing to do" from "this
silently failed"?

## B. Migration didn't carry forward the old invariant

Old mechanism → new mechanism, where the old one enforced something (a
guard, a check, a dedup key) that the replacement quietly dropped. Often
visible as a stale doc comment still describing the old mechanism's
guarantee, or a test that still exercises the old code path and passes
trivially because nothing calls the new path the same way.

Grep starting points: recently-touched files (`git log --oneline -p` on the
region) for a removed function whose callers were redirected elsewhere;
doc comments containing words like "replaces", "migrated from", "formerly".

Ask per hit: what did the old code guarantee that isn't visibly re-asserted
in the new code? Did anyone diff the two invariant sets, or just diff the
code?

## C. Capability-flag-gated dual path, only one branch tested

A generic parameter or feature flag selects between a "real" implementation
and a test/fixture one. If production _always_ takes one branch and the test
suite _always_ takes the other, the production branch has effectively zero
test coverage regardless of the suite's line-coverage number.

Grep starting points: generic type parameters with a `#[cfg(test)]`-only
alternate implementation; `if cfg!(test)` or equivalent branching; a trait
with exactly two implementors, one named `Mock`/`Fake`/`Test`/`Fixture`.

Ask per hit: does any test actually construct the type with the _production_
implementation and exercise the branch a real deployment takes?

## D. Same conceptual value independently re-resolved

The same config value, threshold, path, or key is computed via two (or more)
independent call sites rather than threaded through from one canonical
resolution. They agree today by coincidence of current defaults; nothing
prevents future drift, and when a fix lands it's easy to fix one site and
miss the sibling.

Grep starting points: the same environment-variable name or config key read
via more than one direct `env::var`/config-lookup call across the codebase;
the same computed path (cache dir, work dir, checkpoint path) built via
different helper functions in different modules.

Ask per hit: is there a single canonical resolver this _should_ route
through instead? If one site got a bugfix, would the sibling need the
identical fix applied separately?

## E. Verification/coverage artifact that looks load-bearing but isn't

Tests, checks, and audit-report generators that appear to protect an
invariant but actually validate against their own hardcoded mirror of the
implementation (a tautological test), or that display real queried state
without gating pass/fail on it (a vacuous check — see `techniques.md`'s
"reading the verification tooling as code" section for the exact shape to
hunt).

Grep starting points: a test asserting `implementation_output ==
hardcoded_literal_that_was_clearly_copy_pasted_from_the_implementation`; an
`is_healthy()`/`all_ok`-style boolean built from `.unwrap_or(true)` /
`.unwrap_or(false)` defaults that make an absent signal read as passing; a
health/doctor check whose queried-and-displayed fields are a strict superset
of the fields actually used in the pass/fail decision.

Ask per hit: if the underlying implementation were deliberately broken right
now, would this check/test actually go red?

## F. Declared type surface exceeds what's ever constructed

An enum, especially one crossing an API/RPC/view boundary, declares more
variants than any non-test code path ever constructs. Downstream consumers
write exhaustive match arms for variants that can never actually arrive,
creating false confidence that a category is handled when it's structurally
dead.

Grep starting points: for each variant of a suspect enum, grep the whole
workspace for `EnumName::Variant` construction sites; if the only hits
outside the enum's own definition are match arms and test fixtures, the
variant is dead in production.

Ask per hit: was this variant ever wired to a real producer, or was it
speculative API surface that never got a caller? If a consumer branches on
it, does that branch represent unreachable code, or a real gap where the
producer should exist but doesn't?

## Filing discipline for taxonomy hits

State which category (A–F) a finding matches in its filed description —
this makes cross-region pattern detection possible later ("we have twelve
category-D findings, the _real_ fix is a shared resolver helper, not twelve
independent point fixes") and helps a coordinator recognize when a wave of
individually-small findings actually points at one structural remedy.
