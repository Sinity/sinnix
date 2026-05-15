---
name: adversarial-loop
description: Iterate independent adversarial subagent reviews against a closure (diff, PR body, AC matrix) until the reviewer cannot find legitimate gaps. Caps at 5 iterations. Use when finalizing work that has an explicit AC list — issue closures, refactors with invariants, PRs claiming "all of X is now covered".
metadata:
  short-description: Independent adversarial review until convergence
---

# Adversarial Review Loop

Spawn independent adversarial subagents until one cannot find a
legitimate gap in your closure. Each iteration runs with a cold
context — no chain-of-thought from prior iterations — so the reviewers
don't share blind spots.

**Arguments**: `$ARGUMENTS` — the scope: "PR #N", "branch X", or
"the diff against master."

Field-tested on PRs #1002/#1004/#1006/#1010 of Sinity/polylogue, where
the loop caught **four coherence gaps** that human review missed (catalog
routing, IPv6 origin allowlist, session-tree tool/resource envelope
drift, mtime-drift fingerprint storm).

---

## When to use

- After implementing a closure that claims to satisfy an explicit AC
  list.
- After a refactor that claims to preserve an invariant.
- When a PR title contains "all", "every", "registry-wide", or
  "honest closure of X".
- Before opening a PR or merging one you authored, to verify your
  own claims.

**Skip** when the change is too small to have an adversarial surface
(typo, one-line fix, comment-only change).

---

## Loop protocol

```
ITERATION i (i = 1..5):
  1. Spawn an Explore subagent with the adversarial prompt template.
     Each subagent runs cold — do not pass prior findings.
  2. Read its findings. Classify EACH finding:
     - real gap     → fix it; add a regression test; commit; go to i+1
     - borderline   → document the dismissal in the PR body or fix it
     - noise        → silently dismiss only if you can articulate why
  3. If zero real gaps remain: EXIT loop. Loop converged.
  4. Otherwise re-iterate with the fix in place.

If i = 5 and the reviewer still finds real gaps:
  STOP. Surface the remaining findings to the user with your
  classification. Do not silently abandon — the iteration cap
  exists to prevent infinite loops, not to mask unresolved gaps.
```

**Independence rule**: Iteration N+1's prompt must not reference
iteration N's findings. Each reviewer must independently re-derive
what to attack. Coherence gaps are easy to miss when you absorb prior
framing.

---

## Prompt template

```
You are an adversarial reviewer for {SCOPE}. Iteration {i}. You have
NOT seen prior reviewers' findings — form your own opinion.

## Read first

1. {Issue body + ALL comments via gh issue view N --comments}
2. {The diff: git diff origin/master...{branch}}
3. {The plan or AC matrix path}
4. {PR body: gh pr view N --json body -q .body}

## Attack the closure

For each AC in the matrix:
- Is the claim verifiable from the diff?
- Is the test that pins the claim actually present?
- Does the test fail if the implementation regresses? (Mentally
  invert the implementation. Would the assertion catch it?)
- Are the "out of scope" decisions justified, or are they hiding
  abandonment behind close-discipline framing?

Look especially for:
- ACs marked ✅ where the test exists but doesn't constrain behavior
  (paper coverage).
- Coherence gaps: two related decisions in two files that each look
  right alone but are inconsistent together.
- Closeout language hedging ("incremental", "follow-up", "phase 2")
  without an issue number.
- Test parametrization that doesn't actually cover all combinations.
- Edge cases the implementation didn't consider (IPv6, hash collisions,
  TOCTOU, FK cascades, etc.).
- Referenced follow-up issues that don't actually exist on GitHub
  (verify with `gh issue view #NNN`).

Output: a list of findings, each with:
- AC reference (e.g. "N-A6")
- Severity: real gap / borderline / noise
- File:line evidence — be concrete, not vague
- Recommended fix

If you find nothing legitimate, say so explicitly: "No legitimate gaps
found across all M ACs after iteration {i} review."

Be skeptical but precise. Reviewers who find nothing are usually wrong;
reviewers who find everything are also usually wrong. Find what's
actually there. ≤1500 words.
```

---

## Classifying findings

**Real gap** — the closure's claim doesn't match the code. Fix in next
commit. Example: AC says "all 8 endpoints token-gated and tested", but
only 1 has an explicit test.

**Borderline** — defensible but worth recording. Either fix or document
the dismissal in the PR body's "Adversarial review notes" section so
future-you can second-guess. Example: a mock has a field that doesn't
exist on the real dataclass (harmless but noisy).

**Noise** — false positive, e.g. reviewer misread the code or applied
the wrong AC. Silently dismiss only if you can articulate why. If you
can't, treat as borderline.

The most valuable findings are **coherence gaps**: two related decisions
in two files that drift apart. The registry-wide test pattern (e.g.
`test_envelope_contracts.py::TOOL_CONTRACT` in polylogue) is the
structural defense against this class.

---

## What to record

In the PR body's "Adversarial review notes" section, list:

- Number of iterations run.
- For each iteration: real-gap finding and the commit that fixed it,
  OR "no real gaps found" if it converged that round.
- Borderline findings dismissed with one-sentence reason.

Loop discipline is observable from this section. A PR that claims an
adversarial loop ran but doesn't enumerate findings is paper coverage.

---

## Anti-patterns

- **Passing prior findings to the next iteration.** Defeats the
  independence rule.
- **Skipping the loop because "it's a small change".** If it's truly
  small, the loop is cheap (iter 1 converges fast).
- **Treating every borderline finding as real.** Iteration converges
  faster when you correctly classify noise. But err toward "fix" when
  uncertain.
- **Using a generic reviewer prompt.** Tailor the "Look especially
  for" section to the actual closure's risk surface.

---

## See also

- `skills/assured-close` — the full issue-closure flow that invokes
  this skill.
- `feedback_adversarial_coherence_gaps.md` in project memory — the
  pattern this loop catches.
