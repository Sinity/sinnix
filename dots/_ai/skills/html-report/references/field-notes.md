# Field notes

Append-only log of things learned by *using* this skill. Every agent that
builds an artifact with it should consider adding an entry; most sessions will
add none, and that is correct.

This file exists because the failure mode of a skill is silent decay: an agent
hits friction, works around it in its own artifact, and the workaround dies
with the session. A note here costs one edit and survives.

## What earns an entry

- **A bug in the template or a snippet.** Highest value — it is affecting every
  artifact until fixed.
- **A trap that cost you a debugging cycle**, especially one where the failure
  was silent rather than an error.
- **A pattern you invented** because the skill had no answer, that you would
  reach for again.
- **A rendering/compat surprise** in a real browser.
- **An operator correction** about form, density, or wording.

## What does not

- "I used the sortable table and it worked."
- Restating what SKILL.md already says.
- Artifact-specific content decisions.

## Format

    ### YYYY-MM-DD — one-line title
    **What happened:** …
    **Root cause / mechanism:** …
    **Fix or pattern:** … (say if it is already folded into the skill)

## Consolidation rule

When a note has been confirmed by a second session, or when this file passes
~15 entries, fold the durable lessons into `SKILL.md` / `patterns.md` /
`templates/report.html` and **delete the folded notes**. This file is a
staging area, not an archive — an unbounded log stops being read, which
defeats the point. Note the consolidation date at the top of what remains.

Verify before folding: a note is one agent's experience, and may be wrong or
specific to its situation.

---

### 2026-07-31 — the template's own JS was dead from a stray paren
**What happened:** Sortable tables did nothing. `node --check` on the extracted
script block showed `SyntaxError: Unexpected token ')'` — one extra `)` at the
end of the table-sort IIFE.
**Root cause:** A syntax error anywhere in the single `<script>` block kills
*everything* in it — theme toggle, auto-TOC, filters, sorting. It fails
silently in the page; nothing logs unless you open devtools. The bug had been
shipping in every generated artifact.
**Fix:** Corrected in the template. **Always run
`python3 -c "extract <script>" && node --check` before shipping an artifact** —
one command, catches the whole class. Better: render it headless
(`google-chrome-stable --headless --dump-dom --user-data-dir=<temp>`) and grep
the DOM for evidence the JS ran (a populated `nav#toc`, rewritten `time.age`).

### 2026-07-31 — popup `<template>` must be a direct child, not a sibling
**What happened:** A path link with a preview showed no popup indicator; the
preview had silently bound to the enclosing `<p>`.
**Root cause:** The binding selector is `:has(> template.pop)`, which matches
the template's *direct parent*. Putting the `<template>` after `</a>` makes the
paragraph the host.
**Fix:** Documented in SKILL.md. The `haspop` class is the tell — if an `<a>`
did not get it, the binding went somewhere else.

### 2026-07-31 — a headless render is a real test, not ceremony
**What happened:** Three separate defects (dead JS, mis-bound popup, unverified
staleness logic) were caught in about a minute by dumping the DOM and grepping
for expected side-effects.
**Pattern:** Assert on *evidence that JS ran*, not on the markup you wrote:
`nav#toc` has children, `time.age` text contains "ago", `class="path haspop"`
exists, `.stale` applied where the budget was exceeded. This is the cheapest
verification available for a self-contained page and should be routine.

### 2026-07-31 — 15px base font was too small for a dense report
**What happened:** Operator feedback, unprompted: "font size is too small."
**Root cause:** The template optimised for density at the cost of readability,
and every other size was an absolute-ish `rem` off a 15px root, so there was no
single knob to fix it.
**Fix:** One `--fs` variable (17px floor), everything relative to it, plus A−/A+
controls persisted to localStorage. Density should come from layout — tables,
tiles, disclosure — never from shrinking text.

### 2026-07-31 — decision-widget radios silently merge across rows without unique `name`
**What happened:** Building a 6-row decision queue from the patterns.md widget: the
snippet hardcodes `name="d1"`, and pasting it per-row without renaming makes every
row one radio group — selecting a decision in row 3 clears row 1. No error, just
wrong data in the handback JSON.
**Root cause:** HTML radio grouping is by `name`, but the snippet reads like a
self-contained unit. `data-field` being unique is NOT enough — `name` must be too.
**Fix or pattern:** Caution line added to patterns.md next to the widget (folded).

### 2026-07-31 — judge headless verification by captured DOM, not exit code
**What happened:** `google-chrome-stable --headless=new --no-sandbox --disable-gpu
--dump-dom` printed the complete post-JS DOM, then hung until `timeout` killed it
(exit 124). First run without `--no-sandbox`/`=new` hung with nothing captured.
**Fix or pattern:** Wrap in `timeout 60`, always pass `--headless=new --no-sandbox
--disable-gpu --user-data-dir=<temp>`, and assert on the dumped DOM's contents
(TOC links, "ago)" times, `haspop`) — a nonzero exit with a full DOM is a pass.
Also: `pkill -f <pattern>` to clean up a stuck chrome will match your own shell if
the pattern appears in your command line — run cleanup in a separate call.

### 2026-07-31 — sortable columns that mix numbers and "n/a" sort as strings
**What happened:** A census table's headline column (row counts) had numeric cells
with `data-v` and "not applicable" cells rendered as `&mdash;` with no `data-v`.
Clicking the header appeared to work but produced a nonsense order: the sort
comparator only does numeric comparison when *both* values are numbers, so a
single dash cell downgrades every comparison against it to `localeCompare`.
**Root cause / mechanism:** `val(td)` in the template returns `+td.dataset.v` when
present and `td.textContent` otherwise, so a column is only numerically sortable
if **every** cell carries `data-v`. Mixed columns fail silently — the table still
reorders, just wrongly, which is worse than not sorting at all.
**Fix or pattern:** Give non-applicable cells an explicit out-of-band sentinel —
`<td data-v="-1">&mdash;</td>` — so they cluster predictably at one end and the
real values sort numerically. Verify by clicking the header twice in the headless
probe and asserting the ascending and descending `data-v` sequences are reverses
of each other; eyeballing one direction hides this.

### 2026-07-31 — `rg -rn` silently rewrites its own output
**What happened:** A grep for reader references printed lines where the searched
column name had been replaced by the letter `n`, briefly suggesting a schema that
did not exist.
**Root cause / mechanism:** `-r` is ripgrep's `--replace`, not "recursive". `rg -rn PAT path`
parses as replace-with-`n`. There is no error; the output just quietly lies.
**Fix or pattern:** ripgrep is recursive by default — `-r` is never the flag you
want for that. When an audit grep returns something surprising, re-run it with the
flags spelled long before believing the result.
