---
name: html-report
description: Produce self-contained interactive HTML reports, reviews, censuses, dashboards, plans, incident timelines, or comparisons for human reading, including workshop-style Claude Artifacts.
---

# HTML output ("the unreasonable effectiveness of HTML")

> **Naming note**: the `Artifact` tool's built-in instructions say to skip
> `artifact-design` "if the page is a workshop document built from the
> workshop skill's template" — this skill, `html-report`, is that skill.
> There is no separate skill literally named `workshop`. If you're about to
> call `Artifact` for a report/dashboard/census/review/comparison and haven't
> loaded this skill yet, load it now before writing any HTML.

Markdown is the default agent output format; for anything a human will _read_
rather than _re-edit_, it is usually the wrong ceiling. Self-contained HTML
gives information density (tables, grids, badges, swatches), spatial layout
(side-by-side, timelines, SVG diagrams), and progressive disclosure
(`<details>`, tabs, sortable/filterable tables) that markdown flattens into
scroll. Token cost is no longer a reason to prefer markdown.

The structural ideas below — semantic zoom, hover popups, sidenotes, metadata
blocks carrying status and epistemic confidence, progressive enhancement —
solve "one document, many reading depths". Deliberately _not_ adopted: link
archiving and backlink graphs (meaningless in a single file), ornament
without a job, and reader mode (the A−/A+ and theme controls already cover
it).

## When to use HTML

Human-facing deliverables: status/census/audit reports, code reviews,
incident timelines, architecture explainers, comparisons and decision
matrices, dashboards, presentation decks, prototypes. If the reader will
scan, filter, drill down, or compare — HTML.

## When markdown still wins (real reasons, not habit)

- **Anything agents or humans will re-edit** — diffs and merges matter.
- **Append-only audit tables / ledgers** — git-diffable rows are the value.
- **Dendron/PKM vault notes** — the vault indexes `.md` frontmatter + FTS.
- **Commit messages, PR bodies, issue/bead comments** — the platform renders md.
- Tiny answers where a paragraph suffices.

When both matter (durable note + rich view), the markdown stays canonical and
the HTML is a _view_ — never maintain the same prose in both.

## Semantic zoom (the organizing principle)

Build **one page readable at many depths**, and let the reader choose how
deep to go rather than choosing for them.

    title -> stat tiles -> metadata block -> lead paragraph -> section headers
      -> tables -> body prose -> collapsed <details> -> hover popups -> the file itself

Each layer must be _complete at its own level_ — someone who reads only the
tiles and the lead should come away with something true, not a teaser. This is
what lets one artifact serve both "just tell me" and "show me everything",
which is the exact tension in agent output. Depth is opt-in; nothing important
may exist _only_ behind a hover.

## Provenance: timestamps, staleness, and epistemic basis

A generated report's numbers rot, and the reader cannot tell by looking. Two
mechanisms, both in the template:

**Timestamps that age themselves.** `<time class="age" datetime="…">` renders as
`<date> (<age> ago)` at view time, with the absolute value in the tooltip. Add `data-stale-days="7"` and it turns amber with a ⚠ once past that
budget. Always carry two: **generated** (when the document was written) and
**data as of** (when the figures were actually measured) — they are frequently
not the same day, and only the second one matters for trust.

**Epistemic basis per claim.** The useful axis for agent output is not
_how sure am I_ but _what does this rest on_:

| tag                                            | meaning                                               |
| ---------------------------------------------- | ----------------------------------------------------- |
| `<span class="ev ev-measured">measured</span>` | a query/command was run; the number came back         |
| `<span class="ev ev-derived">derived</span>`   | computed from measurements shown elsewhere in the doc |
| `<span class="ev ev-inferred">inferred</span>` | reasoned from evidence, not directly observed         |
| `<span class="ev ev-assumed">assumed</span>`   | taken on faith, untested                              |

Tag anything a reader might act on. `assumed` is not an admission of failure —
an _unlabelled_ assumption is.

**Scope the tag, don't float it.** In prose, wrap exactly the certified words in
a claim tint — `<span class="claim claim-m">…words…<span class="ev
ev-measured">measured</span></span>` (`claim-m/d/i` = measured/derived/inferred;
template-native, `box-decoration-break:clone` keeps multi-line claims tinted). In
tables and stat tiles the tag scopes the whole row/tile — state that convention
once in the meta `basis` row with a one-line inline demo.

**Measured is the default; tag the exceptions.** In a report where nearly every
number was queried, an identical green chip on all of them carries no
information and buries the few that are derived or inferred — declare
"measured unless tagged" once in the basis row, then tag only departures.

Also carry gwern's **status** vocabulary when the document will be revisited:
`notes` → `draft` → `in-progress` → `finished`.

## Paths, popups, and code

**Paths should be openable.** `<a class="path" href="file:///abs/path">` opens
from a `file://` page; `vscode://file/<abs-path>:<line>` opens at a line in the
editor from anywhere. Render them monospace so they stay copyable.

**Popups are quotes, not fetches.** Give any element a child
`<template class="pop">` and it previews on hover, focus, or click-to-pin (Esc
closes; ctrl/cmd-click still follows the link). The content is inline, so it
works from `file://` forever and makes zero requests — but _you_ must paste the
excerpt in while you have the file open. That constraint is a feature: the
preview is a quote you actually took, not a promise to read later.

The `<template>` must be a **direct child** of the element it previews. A
sibling silently binds the popup to the surrounding paragraph instead.

**Bundle popups with a compiler, not by hand, for `a.path` links.** A `file://`
link only opens for a reader on the _same machine_ with the _same absolute
paths_ — someone else's machine, an Artifact-hosted copy, or a screenshot all
leave it dead, and the popup is what keeps the reference useful anyway. But
hand-typing the excerpt means reading the file into your own context just to
retype a piece of it back out, and it goes stale on the next edit. Instead,
mark the link `data-embed` (bare, or `data-embed="4000"` to override the
per-file char cap) while composing the report — no excerpt, just the marker —
then run `generators/embed-path-popups.py <report.html>` once before shipping;
it reads each marked file fresh from disk and inserts the popup for you.
Idempotent (a link with an existing `<template class="pop">` child is left
alone), so re-run it after adding more `data-embed` links without disturbing
hand-edited ones. Reserve manual excerpt-typing for the rare case where you
want to quote a _specific_ passage rather than a file's head.

**Code blocks** use `<figure class="code">` with a `<figcaption>` carrying the
filename, `<span class="lang">` for the language (gets the accent color), and a
copy button; `<pre class="ln">` numbers lines when each is wrapped in
`<span class="line">`, and `hl` marks the lines that matter. Highlight tokens
with `tk-k`/`tk-s`/`tk-c`/`tk-n`/`tk-f` **as you write** — you already know
which token is a keyword, so shipping a runtime highlighter would be a
dependency bought for nothing.

**Quotes are never the same box as your own narration.** In any
back-and-forth structure (corrections, timelines, review threads), wrapping
both your paraphrase and the words someone actually said in one
identically-styled box leaves the reader parsing every sentence to tell
which is which. Fix it structurally: narration is a **plain paragraph**,
no border, no background — exactly like the rest of your prose. The moment
you're relaying words someone actually wrote or said, switch to
`<blockquote class="q">…<cite>who, when</cite></blockquote>` — it renders in
an italic serif face (the template's one deliberate typographic pairing) with
an oversized opening quotation mark, so _quote-ness_ reads at a glance,
independent of who's speaking. Add `.user` or `.ext` to recolor the left bar
by speaker; the serif treatment itself never changes, because "is this a
quote" and "who said it" are different facts and should look like different
facts. A short quote inside a running sentence doesn't need the full block —
`<span class="iq">` gives it a tinted italic run with no box.

**Sidenotes** (`<span class="sn" tabindex="0"><template class="pop">…`) are a
small superscript marker using the _same_ popup mechanism as path/evidence
previews, not a separate margin-column trick. A true wide-margin sidenote
needs a page layout that reserves real margin space; a
`left: calc(50% + Nrem)` guess relative to the viewport has no real containing
block in a single-column report layout and drifts off-position. One
interaction pattern for every aside beats maintaining a second, fragile one.

## Operator input: annotations, corrections, questionnaires

A report can collect input, not just display it — annotation fields on
findings rows, approve/defer/reject decision widgets, small questionnaires.
`file://` has no backend, so nothing the operator types can reach you on its
own; the pattern is autosave-to-`localStorage` (so edits survive reopening
_that_ file — same mechanism as the template's theme/font-size persistence)
plus a "copy for agent" button that serializes every tagged field to JSON in
a visible textarea and the clipboard, for the operator to paste back into the
chat. True realtime sync would need either a companion server (breaks the
self-contained contract) or Claude Artifact runtime capabilities (a separate,
narrower mechanism, only for pages published via the `Artifact` tool — see
the `artifact-capabilities` skill if that's genuinely what's being built).
Full snippets — core script, annotation cells, decision widgets, questionnaire
fieldset — in `references/patterns.md` under "Annotations, corrections &
handback". Use whenever the deliverable is a decision queue, a review the
operator will mark up, or a plan needing a go/no-go per item — this turns
"send a report, then wait for prose feedback" into "send a report, get a
structured answer back in one paste."

## Marking what changed between passes

When you _revise_ a report across sessions — a living workspace, a status page
you update weekly — the reader needs to know which parts are new without
diffing. Put `data-added="YYYY-MM-DD"` (and `data-changed="…"` when you rewrite
in place) on any `section`, `tr`, `details`, or paragraph you add in a later
pass. The template stamps each one with a quiet date, remembers the reader's
last visit per file, tints anything newer, and offers "show only new".

Two rules make it work: **tag at the granularity the reader cares about**
(a section or a table row, not every `<p>`), and **only set `data-changed` for
a real revision** — re-stamping untouched blocks makes the whole mechanism
noise. Undated blocks are simply "was already there", which is the right
default for the original pass.

## Improving this skill as you use it

This skill is expected to get better through use, not through occasional
rewrites. `references/field-notes.md` is the staging area: after building an
artifact, if you hit a template bug, lost a cycle to a silent failure,
invented a pattern the skill lacked, or got a correction from the operator —
**append a note**. Most sessions add nothing; that is fine.

Notes get folded into `SKILL.md` / `patterns.md` / the template once confirmed
or once the file grows past ~15 entries, and are deleted when folded. Verify
before folding: a note is one agent's experience and may be wrong.

## Shipping checks (run before delivering any artifact)

Each of these exists because its absence shipped a real defect:

1. **`node --check` the extracted `<script>`.** One syntax error silently kills
   every interactive feature — theme, TOC, sort, popups — with nothing logged.
   Write the extractor as a helper file and invoke it plainly (heredoc/redirect
   one-liners get refused in sandboxed worktree agents).
2. **Headless-render and judge the DOM, not the exit code.**
   `timeout 180 google-chrome-stable --headless=new --no-sandbox --disable-gpu
--user-data-dir=<fresh tmp> --virtual-time-budget=4000 --dump-dom` — run with
   the Bash sandbox off (it only reads a local file); chrome may hang after a
   complete dump, so exit 124 with a full DOM is a PASS. Before asserting,
   confirm the dump is non-empty **and newer than the HTML** — a killed chrome
   leaves a zero-byte or stale file that reads as a pass. Then grep for evidence
   the JS ran: populated `nav#toc`, `ago)` in rewritten times, `haspop`,
   `tabindex="0"` on popup hosts, filled `data-calc` values.
3. **Grep for `POP-TODO`.** The template's stat tiles carry a query-popup slot
   with that sentinel; any survivor means a headline number shipped without its
   query.
4. **Timestamps come from the clock, never the narrative.** Run
   `date -u +%Y-%m-%dT%H:%M:%SZ` at write time for `generated`, and re-execute
   the headline queries at that moment so `data as of` is a real measurement
   time. Agents systematically underestimate elapsed wall-clock (hours read as
   "a few sections"), and `time.age` renders against the viewer's real clock, so
   a guessed value is visibly wrong the moment the page opens. Never increment
   from a prior revision's estimate.
5. **Proofread SVG `<text>` content separately** — it is outside every
   automated check above.
6. **When revising or superseding an existing report, run
   `generators/check-superset.py OLD.html NEW.html`** (with `--rename
"old=new"` for each deliberately retitled section) and ship only on exit 0. LLM iteration smears: regeneration-from-memory silently drops whatever
   wasn't actively recalled — a real lineage lost seven units including two
   whole sections before this check existed (2026-08-12). Every dropped
   heading must be either restored or a _declared_ rename; "I rewrote it
   better" is what the leak looks like from the inside.

## Data-derived reports (when the content came from a system)

A report computed from a database, an archive, a test run, or a live system is
a different artifact from one written from memory, and it earns a different
standard: **every number should be traceable to the query that produced it.**

The failure mode is specific and common. An analysis gets written by _reading_
the source material — scrolling a transcript, skimming logs — and produces
confident round numbers with a quiet disclaimer that they are approximate. That
disclaimer is the tell: the data existed and was queryable, and the report
guessed anyway. If a system can answer the question exactly, asking it is not
extra rigour, it is the job.

So, in order of importance:

1. **Query, don't estimate.** If the number is in a database, select it. Reserve
   `ev-inferred` for things genuinely not measurable, and label those honestly
   instead of dressing them up as measurements.
2. **Attach the query to the number.** See "Query-attributed metric" in
   `references/patterns.md` — a `<template class="pop">` on the tile carrying the
   exact invocation. The reader can verify; the next agent can regenerate; and a
   number whose query no longer runs becomes visibly stale rather than silently
   wrong.
3. **Show the holes.** When a query _should_ have produced a number and did not
   — timeout, missing surface, unimplemented view — show the gap. A visible hole
   is information about the system; a substituted estimate is not.
4. **Separate measured from derived from inferred**, and put the split in the
   metadata block. A report that is 90% measured and says so is far more useful
   than one that is 100% confident and 60% measured.

When the reporting _is_ the demonstration — showing what a tool can do — this
matters twice over, because an unverifiable claim about a tool's capability is
worth less than a small verifiable one. Prefer three numbers the reader can
reproduce over thirty they cannot.

## Generators: a recurring report shape is a program, not a document

A report that will be produced more than once — a backlog state page, a fleet
dashboard, a filesystem census — should be emitted by a script, not hand-written
each time. Hand-authored recurring reports rot in a specific way: sections get
updated at different moments and start contradicting each other, and claims
outlive the evidence that once supported them. The generator genre fixes both
structurally. Reference implementation: polylogue's
`devtools workspace beads-state-report` (the "Beads backlog — state of the
graph" artifact), which demonstrates every rule below at 1,500-entity scale.

- **Findings are conditional predicates, not prose.** Each finding is emitted
  by a condition the generator checks at render time — a claim that stops being
  true stops being printed. No hand-authored judgment can silently outlive its
  evidence.
- **A provenance table maps every section to its origin**: measured from input /
  derived reconstruction / authored framing / operator-supplied constant. The
  framing sentences are deliberately data-free.
- **`--fresh` semantics**: the generator re-exports its input first; without it,
  the report describes whatever the input file last held, and says so.
- **The regenerate command is printed in the artifact** — a report that names
  its own generator is one command from current.

Placement: repo-coupled generators (beads state, test dashboards) live in that
repo's own tooling. Repo-agnostic ones live inside this skill at
`generators/` — first resident: `reports-index.py`, which builds the index page
over a reports directory (see Corpus conventions below). One-off investigations
(incident forensics, a design review) stay hand-authored — the generator tax is
only worth paying for shapes that recur.

## Corpus conventions (many reports, one directory)

Reports accumulate; a directory of twenty undated-vs-dated, superseded-vs-live
files with no index is its own legibility failure (observed live, 2026-08-02).

- **Durable home**: `/realm/data/derived/reports/` (workflow step 3). Keep the
  generated index current: `python3 generators/reports-index.py
/realm/data/derived/reports` (idempotent; run it after adding a report).
- **Supersession is explicit.** A replaced report gets a `superseded-by` meta
  row + banner pointing forward (and the successor a `supersedes` row back).
  Never leave two siblings that both look current. For artifacts, republish the
  same `file_path` so the URL stays stable instead of minting a sibling.
- **Living workspaces get a stable filename** (no date suffix) — the date
  belongs in the metadata block, the filename is the bookmark. One-shot reports
  keep `<topic>-<YYYY-MM-DD>.html`.
- **Companions row**: a report belonging to a suite links its siblings in the
  meta block (see the atlas), never summarizes them inline.

## Visual identity (which report is this, at a glance)

The template's structure, controls, and semantic colors are a house style and
never vary. The **accent is per-subject**: set `data-accent` on `<html>` —
`forensic` (amber) / `ops` (violet) / `finance` (teal) / `archive` (magenta) /
`design` (olive) / unset = infra blue. Pick deliberately; six reports that all
ship the default blue are indistinguishable in a tab strip, which defeats the
point of having an identity at all. Status colors (`ok/warn/bad/info/todo`) are
semantic and identical in every report — identity never rides on them.

For any chart beyond the template's histogram/dist-bar patterns, load the
`dataviz` skill before writing chart code — it owns chart form, palettes, and
accessibility; this skill owns the page around the chart.

## Contract (every HTML artifact)

1. **One file, zero external requests.** All CSS/JS inline; images as
   inline SVG or `data:` URIs. It must open from `file://` forever.
2. **Both themes.** Style via CSS custom properties;
   `@media (prefers-color-scheme: dark)` + a `data-theme` toggle.
3. **Degrade without JS.** JS enhances (sort, filter, TOC); content must be
   fully readable with JS off. Use `<details>` not JS accordions.
4. **Semantic structure.** `<header> <nav> <main> <section> <table>`; h2/h3
   hierarchy (the template autobuilds the TOC from it).
5. **Density over prose.** Tables beat bullet lists; badges beat adjectives;
   stat tiles beat opening paragraphs; `<details>` beats "see appendix".
6. **Evidence links.** File paths as `<code>`; keep them copyable.
7. **Readable at arm's length.** Base `--fs` is `17px` and every other size is
   `rem`/`em` relative to it. Do not lower it, and never reintroduce an
   absolute `px` font-size — that is how a dense report becomes unreadable.
   The A−/A+ buttons step `--fs` and persist it, so per-reader preference is
   already handled; shrinking the default to fit more on screen is not.

## Living workspaces (multi-session analysis)

A distinct genre from the one-shot report: working memory for an analysis that
spans crashes, compactions, and sessions. Its job is **not losing branches** —
the failure mode is depth-first exploration that silently drops the rest.
Markdown handles the prose but flattens exactly the structure that matters, so
this is a strong HTML case even though an agent re-edits it.

Required elements, beyond the ordinary report shell:

- **A lead register** — one filterable/sortable table, one row per lead, with
  an explicit state badge: `open` · `in-flight` · `landed` · `dud` ·
  `rejected`. Duds and rejections stay in the table _with the reason_; deleting
  them invites re-exploration. This table is the artifact's spine.
- **Frontier at the top** — what is genuinely unexplored, stated as the first
  thing a cold reader sees, above any narrative.
- **Standing rules learned the hard way** — method corrections (e.g. "spot-check
  a sample before believing any aggregate") outlive individual findings.
- **Self-corrections kept visible** — when re-measuring overturns an earlier
  claim, show both. A workspace that only shows current belief teaches nothing
  about which claims were fragile.
- **Provenance per claim** — a PR number, bead id, commit, or the command that
  produced the figure. Unsourced numbers in a resumed session are unusable.
- **Summary tiles are computed, not typed.** Any headline countable from the
  document's own rows uses `data-calc="count:SELECTOR"` / `sum:SELECTOR` so a
  revision cannot leave the summary contradicting the body (confirmed failure
  mode: one workspace simultaneously claimed 128, 24, and 101+27 for the same
  count in three hand-maintained places). Hand-write only numbers that come
  from outside the document.

Keep it one file. Split-per-thread markdown was the previous shape and its cost
was that the index and the threads drifted.

### Beads / PR repos specifically

Where a repo tracks work in Beads or GitHub, the workspace is a _view over_
that tracker, never a competing one. Rows carry the bead id / `#NNNN`; anything
that becomes real work moves to the tracker and the row's state changes to
point at it. If a row has lived as `open` with no id for a session or two, that
is the signal to bead it or kill it.

## Workflow

1. Copy `templates/report.html` (same dir as this skill) and fill the marked
   slots: title, meta chips, stat tiles, sections. Keep its CSS variables.
2. Pick patterns from `references/patterns.md` (sortable table, filter box,
   tabs, timeline, badge set, annotated diff, SVG diagram, deck nav,
   annotation/decision/questionnaire widgets + handback button) — paste only
   what the artifact needs.
3. Name it `<topic>-<YYYY-MM-DD>.html`, place it next to the deliverable it
   documents. If it's meant to persist or be cross-referenced (a case-study
   series, a wiki-style artifact, anything you or another agent will link back
   to later), its durable home is `/realm/data/derived/reports/` — not
   `/realm/tmp`, which has no expiry of its own but sits inside a tree whose
   sibling directories are auto-reaped on a 7-day tmpfiles timer. Reserve
   scratch/`/realm/tmp` for genuinely single-use output you will not need to
   reference again.
4. Deliver it. **Publishing as an Artifact is the DEFAULT step of shipping
   any HTML report** (operator standing instruction) — same breath as the
   durable-home copy, without waiting to be asked. Artifacts stay
   private-to-the-operator until shared. Skim first for genuinely sensitive
   content (credentials, unredacted personal data, material the operator
   hasn't seen if you didn't author it this turn) — internal paths and
   ordinary engineering detail are not a reason to hold back. Also send via
   `SendUserFile` (`display: "render"`): the immediate look vs the thing
   that still exists next week. Skip the publish only when the tool is
   unavailable (print the path; `xdg-open` works), the content is throwaway,
   or the operator asked local-only.
5. Updating a living workspace across sessions: republish the **same
   `file_path`** to redeploy to the same `Artifact` URL rather than minting a
   new one each pass — that's what makes the browsable-later property work
   for a document that gets revised repeatedly.
6. Feeding back: HTML artifacts re-read fine as agent input; keep ids/classes
   semantic so a later agent can parse the DOM.

## Layout quick-reference

- Page shell: sticky header, optional sidebar TOC (`nav#toc`), max-width
  `80rem`, `1rem`-ish gaps. Wide tables scroll inside `overflow-x:auto`.
- Prose blocks are capped at `76ch` by the template — long lines are the other
  half of readability, alongside font size.
- Comparisons: CSS grid `grid-template-columns: repeat(auto-fit, minmax(20rem,1fr))`.
- Status color: use the badge classes (`.ok .warn .bad .info .todo`) — never
  raw reds/greens; they're theme-tuned in the template.
- Sortable numeric columns: EVERY cell needs `data-v` — one bare "—" cell
  downgrades the whole column to string compare, which reorders wrongly rather
  than failing. Give n/a cells an out-of-band sentinel (`data-v="-1"`).
- Diagrams: hand-write inline SVG (boxes+arrows beat ASCII art); label every
  edge; `viewBox` only, no fixed px sizes.
