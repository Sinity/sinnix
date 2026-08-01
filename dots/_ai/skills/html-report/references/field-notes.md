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

### 2026-07-31 — an analysis that guessed numbers the system could have answered
**What happened:** A session autopsy stated its own basis as "inferred exact turn
counts — the transcript is long enough that a precise tally isn't fully
trustworthy; treat round numbers as roughly, not exactly." The subject session was
sitting in a queryable archive that holds the exact count (1,861 messages), and the
report never queried it.
**Root cause / mechanism:** The report was produced by *reading* the source
material rather than *querying* it. The honest-sounding disclaimer masked a
methodology choice: approximation was accepted because measurement felt like extra
work. Provenance tags made the guess look rigorous rather than exposing it.
**Fix or pattern:** New `## Data-derived reports` section in SKILL.md and a
`Query-attributed metric` pattern — attach the exact invocation to each headline
number via `<template class="pop">`, so a figure is verifiable, regenerable, and
visibly stale when its query stops working. Corollary worth keeping: when a query
*should* have produced a number and failed, show the hole. A visible gap is
information about the system; a substituted estimate is not.

### 2026-07-31 — a stale/empty headless dump read as a passing verification
**What happened:** Under heavy host load (load avg 32), `timeout 45 google-chrome-stable
--headless=new --dump-dom > dom.html` exited cleanly having written **zero bytes**. A later
assertion script silently re-read an *earlier* dump from before the fixes, and reported
"time not rewritten" for a bug that had already been fixed — then reported a pass on a file
that no longer matched the artifact.
**Root cause / mechanism:** The dump is a redirect, so a killed/slow chrome leaves a
zero-byte or stale file rather than an error. Nothing in the assertion step checks that the
DOM it is reading came from the current artifact.
**Fix or pattern:** Before asserting, check the dump is non-empty and newer than the HTML
(`ls -la` both, or `[ dom.html -nt report.html ]`), and print its byte count in the same
command that produces it. Give the `timeout` real headroom on a loaded box — 45s was not
enough, 180s was. Also worth knowing: a *correct* `<time datetime>` in the future renders as
"2h ahead", which is the tell that the timestamp was written in local time and labelled `Z`.

### 2026-07-31 — the popup binder leaves non-anchor elements keyboard-unreachable
**What happened:** Six `<div class="tile qa">` carrying `<template class="pop">` bound
correctly on hover/click, but the headless DOM showed `tabindex="-1"` on every one of
them — the popups could not be reached by keyboard at all, silently failing the
"depth is opt-in but reachable" property the skill claims for the mechanism.
**Root cause / mechanism:** `el.tabIndex=el.tabIndex||0;` in the popup binder. A `<div>`'s
default `tabIndex` is `-1`, which is **truthy**, so `||` keeps it. The line only does the
right thing for elements that already default to `0`. Anchors were fine, which is why the
bug survived — the pattern was introduced for `a.path` and the query-attributed-metric
tile is the first common non-anchor host.
**Fix or pattern:** `if(el.tabIndex<0)el.tabIndex=0;` in `templates/report.html`. Verify by
grepping the headless dump for `tabindex="0"` and matching the count to the number of
`<template class="pop">` hosts — `tabindex="-1"` in that grep is the failure signature,
and its *presence* still proves the binder ran, so it reads as success if you only check
that popups were bound at all.

### 2026-08-01 — hand-picked "generated" timestamps drift stale across revisions
**What happened:** A living-workspace report was republished four times across a long
session (rev.1 → rev.4). Each revision's `generated`/`data as of` `<time class="age">`
datetime was set by estimating/incrementing a plausible-looking clock value
("16:55Z", "21:05Z", "22:43Z", "01:10Z next day") rather than by querying the actual
current time. The operator noticed the artifact platform's own "last edited 6m ago"
indicator disagreed sharply with the report's self-reported age.
**Root cause / mechanism:** `time.age`'s relative-age JS computes against the
**viewer's real `Date.now()`** at render time, not against whatever the agent believed
"now" was while writing the datetime attribute. An agent session that spans many tool
calls and background subagent waits has no reliable felt sense of elapsed wall-clock
time — several real hours can pass while the agent's mental model advances "a few
sections." A guessed timestamp that undershoots real elapsed time renders as stale/
"ago"-mismatched the moment someone actually loads the page, and the drift compounds
with every revision that estimates from the previous estimate rather than reality.
**Fix or pattern:** Before writing/updating any `time.age` datetime, get the actual
current time from a real clock — `date -u +%Y-%m-%dT%H:%M:%SZ` in the Bash tool is
sufficient (cross-checked here against external HTTPS `Date:` response headers from
two independent hosts and found accurate) — never estimate or increment from a prior
revision's timestamp. This matters most for living workspaces revised many times in
one long session, where the temptation to eyeball "roughly N minutes since last time"
is strongest and the compounding error is largest.

## 2026-07-31 — headless-render check: harness sandbox kills Chrome silently
`google-chrome-stable --headless --dump-dom file://…` under the sandboxed Bash tool
produced 0-byte DOM (new-headless) or exit 144/hang (old headless), with no useful stderr.
Re-running the identical command with sandbox disabled rendered fine. Symptom to recognize:
`--dump-dom` returns empty output instantly or hangs on profile init. Fix: run the render
check with the sandbox off (it only reads the local file), fresh `--user-data-dir` under
/realm/tmp, `--virtual-time-budget=4000`, and `timeout 90` (chrome may not exit after
dumping; exit 124 with a full DOM is a PASS, not a failure).
