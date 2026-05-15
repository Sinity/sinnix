---
name: evidence-harness
description: For bug investigations — build a reproduction harness that measures the suspected behaviour BEFORE touching production code. Use when investigating intermittent or load-dependent bugs, performance regressions, I/O storms, or any case where the user explicitly says "fix what the data implicates, not what the hypothesis flags". Prevents writing code for the wrong suspect.
metadata:
  short-description: Reproduction-first investigation; measure, then fix
---

# Evidence Harness

When a bug investigation has multiple plausible suspects, build a
reproduction harness that produces **numerical evidence** before
touching production code. The harness's measurements become the
regression pins after the fix lands.

**Arguments**: `$ARGUMENTS` — the suspected behaviour to measure
(e.g. "live ingest read amplification", "memory leak in X", "FTS
trigger storm under load").

Field-tested on PR #1010 of Sinity/polylogue: the user named 6 suspects
for an I/O storm; the harness confirmed exactly 1 and refuted the other 5. Without the harness, the fix would have been written for the wrong
suspect.

---

## When to use

- The symptom is observable but not deterministic (intermittent,
  load-dependent, only-in-production).
- The user explicitly says "fix what data implicates, not hypothesis."
- Multiple candidate root causes fit the symptom.
- A performance/I/O metric is the user-visible failure (MB/s, IOPS,
  latency, memory, lock-contention).

**Skip** for deterministic bugs where the failure is reproducible by
inspection (null deref, type error, off-by-one with a clear trace).

---

## Workflow

### 1. Static trace first

Read every code path that could produce the observed symptom. Build a
table:

| #   | Site                                             | Trigger       | Magnitude |
| --- | ------------------------------------------------ | ------------- | --------- |
| 1   | `fingerprint_file()` in `_needs_work_from_state` | mtime drifted | full file |
| …   | …                                                | …             | …         |

This narrows the search and gives the harness a target list.

### 2. Form hypotheses; rank them

For each candidate site from the trace, write a hypothesis:

- **H1**: site X triggers under condition Y, producing the symptom.
- **H2**: site Z triggers under condition W, producing the symptom.

Rank by how well each explains the symptom shape (e.g. "9.5 KB/op
metadata-heavy" rules out sequential large reads).

### 3. Build the harness

A reproduction harness is a test (or set of tests) that:

- **Counts** what each candidate site does — bytes, calls, time, locks
  acquired. Use thread-local counters wrapped around the production
  call sites via `unittest.mock.patch` or equivalent.
- **Reproduces the user's scenario** at a small scale where assertions
  are tractable. 50 files instead of 1000; 10 ops instead of 10k.
- **Asserts** a contract for each hypothesis. If the assertion fails,
  the hypothesis is confirmed.

Place harness infrastructure in `tests/infra/` so it's reusable.
Place scenarios in `tests/integration/`.

Example template (`tests/infra/io_counter.py` in polylogue):

```python
@contextmanager
def read_counter() -> Iterator[ReadCounter]:
    counter = ReadCounter()
    real_fingerprint = batch_support.fingerprint_file
    def counted_fingerprint(path):
        fp, last_nl = real_fingerprint(path)
        counter.record("fingerprint_file", path.stat().st_size)
        return fp, last_nl
    with patch.object(batch_support, "fingerprint_file", counted_fingerprint):
        yield counter
```

### 4. Run the harness; record findings

For each hypothesis, the harness produces a yes/no with a number:

```
S1 active append:        0 fingerprint_file calls, 0 full-stream blob   ✅ refuted
S2 single mtime drift:   1 fingerprint_file call (690 bytes)             ❌ confirmed
S3 subagent append:      0 fingerprint_file calls                        ✅ refuted
S4 50-file catch-up:     50 fingerprint_file calls (~35 KB total)        ❌ confirmed
```

Record the numbers in your working notes and in the PR body's
"What I decided NOT to fix and why" section.

### 5. Fix what the data implicates

Make the smallest possible production change that flips the failing
assertions to passing. Do NOT touch the refuted-hypothesis sites —
that's wasted code and adds risk.

### 6. Re-run the harness

Same scenarios; now they should all pass. Record before/after numbers
in the PR body:

| Scenario | Before fix               | After fix |
| -------- | ------------------------ | --------- |
| S1       | 0 / 0                    | 0 / 0     |
| S2       | 1 fingerprint (690 B)    | 0         |
| S4       | 50 fingerprints (~35 KB) | 0         |

### 7. Promote harness to regression test

The harness scenarios are not throwaways. They become the regression
suite. Commit them as `tests/integration/test_<bug>_regression.py`
with documentation linking back to the bug report or issue.

---

## What gets reported

In the PR body, include:

- **The static trace table** — every site that could produce the
  symptom.
- **The hypothesis ranking** — which suspect was most plausible
  pre-investigation.
- **The harness output** — confirmed vs refuted suspects with numbers.
- **The fix** — one line if possible.
- **Before/after measurements** — same scenarios, both columns.
- **"What I decided NOT to fix"** — refuted suspects with evidence.

The discipline is observable from the PR body. A PR that claims
evidence-driven investigation but doesn't enumerate refuted suspects
is hypothesis-driven masquerading.

---

## Anti-patterns

- **Skipping the harness because "the static trace is obvious".** It
  isn't — that's why the user reported the bug. The harness exists to
  refute your prior beliefs as much as confirm them.
- **Mixing fixes for confirmed and unconfirmed suspects.** Each
  unconfirmed fix is risk you didn't need. Wait for evidence.
- **Hand-crafted measurements (printf debugging).** Use a structured
  counter so the assertions are mechanical and the regression test is
  reusable.
- **Throwing the harness away after the fix.** The harness IS the
  regression test. Commit it.

---

## See also

- `skills/assured-close` — closure pattern that composes this skill for
  bug investigations.
- `skills/adversarial-loop` — verifies the closure once the harness
  shows green.
- `tests/infra/io_counter.py` in polylogue — reference implementation
  for read-counter harness.
- `tests/integration/test_live_read_amplification.py` in polylogue —
  reference reproduction scenarios.
