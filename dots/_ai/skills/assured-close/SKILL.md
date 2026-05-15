---
name: assured-close
description: Close a GitHub issue using the AC-matrix + adversarial-loop pattern. Use when finalizing any reopened or scope-heavy issue, especially when you want the close-out to survive future audits. Refuses abandonment — no "future work" / "phase 2" / "incremental" without an open issue number.
metadata:
  short-description: AC-driven issue closure with adversarial verification
---

# Assured Close

Close an issue so that a future audit cannot legitimately reopen it.
The pattern is evidence-driven, AC-internalizing, and adversarial-loop-verified.

**Arguments**: `$ARGUMENTS` — the issue number to close (e.g. `818`).

This is the methodology distilled from PRs #1002/#1004/#1006/#1010 on
Sinity/polylogue, which closed four issues by catching three coherence
gaps that human review missed. See
`feedback_adversarial_coherence_gaps.md` and `feedback_close_discipline.md`
in project memory.

---

## When to use

- An issue is reopened during an audit (the close-discipline pattern).
- The issue has a broad AC list and "phase 1 landed" close-outs you don't
  trust.
- The issue body + comments together exceed 50 lines and the comments
  reframe scope.

**Do not use** for trivial fixes (single-line typo, one-test rename). The
overhead isn't worth it for those.

---

## Workflow

### 1. Internalize acceptance criteria

```bash
gh issue view N --comments
```

Comments are part of the spec — per CLAUDE.md "Issue comments are part
of the spec." Read all of them. Comments often reframe, narrow, or
expand the original AC list.

Produce a **verbatim AC matrix** in your working notes:

| AC   | What                                  | Current state |
| ---- | ------------------------------------- | ------------- |
| N-A1 | (verbatim from issue body or comment) | ✅ / ❌ / ⚠️  |
| N-A2 | …                                     | …             |

Every unmet AC must be classified into exactly one of:

- ✅ done (this PR addresses it)
- ➡️ explicit out-of-scope **with reason and follow-up issue #NNN**
- ⚠️ tracked-elsewhere **with #NNN**

If you cannot make this classification for some AC, you do not understand
the issue well enough to close it. Re-read.

### 2. Recon the current state

Static-trace the code surface for each AC. Confirm or correct the
"Current state" column with `file:line` evidence. Do not trust the
issue's "remaining scope" comments — they were written before any of
this PR's commits.

### 3. Plan and implement

- One PR per coherent slice. Multiple atomic commits OK, but the PR
  squash-merge subject is the durable history line.
- For each AC marked ❌ Missing or ⚠️ Decision required, do the
  implementation **and** add a test that pins the contract.
- Track decisions made (e.g., "raw artifacts not redacted by design")
  as explicit-decision rows in the AC matrix, with rationale.

### 4. Run the adversarial loop

Invoke the `adversarial-loop` skill against the closure. Iterate until
clean (≤5 iterations). Each iteration is an independent subagent with
no memory of prior findings.

### 5. Write the PR body

Required sections (per `docs/architecture.md` PR discipline):

- **Summary** (one paragraph).
- **Problem** — evidence/motivation, not "user asked." Link the audit
  comment if reopened-from-audit.
- **Solution** — AC matrix verbatim with current-state column, files
  changed, decisions documented under "Explicit Decisions" or similar.
- **Verification** — exact commands run, the output line that matters.
  Not "tests pass."
- **Adversarial review notes** — number of iterations, real gaps fixed
  in each iter, dismissed findings with reasons.
- **What I decided NOT to fix and why** — a table of suspects refuted
  during investigation, with the empirical evidence.

### 6. Close-discipline gate (before merge)

Walk the AC matrix one more time. For each row marked ➡️ out-of-scope
or ⚠️ tracked-elsewhere:

- Does the cited #NNN issue actually exist on GitHub?
  `gh issue view NNN`
- Does it have real scope (not just "TODO: figure this out")?
- Is its title specific enough that a future reader can act on it?

If any answer is no, stop and file the missing issue. Do not merge.

Per `feedback_close_discipline.md` saved in memory: "future work" /
"phase 2" / "incremental" / "deferred to follow-up" — without a specific
open issue number — is abandonment, not deferral.

### 7. After merge

The squash-merge commit body **is** the closeout. `Closes #N` in the
PR body auto-closes the issue and the AC matrix lands on master as the
durable history record. No separate closeout comment needed unless you
want to add a brief "patterns I'd reuse" note.

---

## Heuristics

- **One coherence gap per adversarial iteration** is the productive
  steady state. If iter 1 finds zero, you either have a very simple
  closure or the reviewer wasn't adversarial enough — re-run with a
  tighter prompt.

- **Resist the urge to widen scope.** Discoveries that aren't on the
  AC list become follow-up issues, not surprise additions to this PR.

- **Reproduction before fix for bugs.** Compose the `evidence-harness`
  skill — write a test that demonstrates the bug, see it fail, then fix.

- **Honest registry-wide tests beat targeted tests.** A test that
  classifies every entity (every endpoint, every tool, every check)
  and asserts each conforms is a regression net that catches drift you
  weren't looking for. See
  `tests/unit/mcp/test_envelope_contracts.py` and
  `tests/integration/test_blob_lifecycle_e2e.py` in polylogue for
  templates.

---

## Anti-patterns

- Closing with "remaining edges are incremental" — that's the
  abandonment pattern. Refuse to write this even if it matches the
  vibe of recent project closes.
- AC matrix that uses paraphrased AC language. Use the verbatim text
  from the issue or its comments. Paraphrase loses the spec.
- Skipping the adversarial loop because "I've already checked
  everything." The whole point is the independent review.
- Filing the follow-up issue **after** merge instead of before. The
  discipline gate happens before merge.

---

## See also

- `skills/adversarial-loop` — the review-iteration mechanism.
- `skills/evidence-harness` — reproduction-first investigation for bugs.
- `feedback_close_discipline.md` in project memory.
- `feedback_adversarial_coherence_gaps.md` in project memory.
