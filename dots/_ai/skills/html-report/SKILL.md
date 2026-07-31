---
name: html-report
description: Produce agent output for human reading as self-contained interactive HTML instead of markdown — templates, layout system, and interactivity patterns. Use for reports, reviews, censuses, dashboards, plans, incident timelines, comparisons.
---

# HTML output ("the unreasonable effectiveness of HTML")

Markdown is the default agent output format; for anything a human will *read*
rather than *re-edit*, it is usually the wrong ceiling. Self-contained HTML
gives information density (tables, grids, badges, swatches), spatial layout
(side-by-side, timelines, SVG diagrams), and progressive disclosure
(`<details>`, tabs, sortable/filterable tables) that markdown flattens into
scroll. Token cost is no longer a reason to prefer markdown. (Thariq
Shihipar, "Using Claude Code: The unreasonable effectiveness of HTML",
2026-05; gallery at thariqs.github.io/html-effectiveness.)

The structural ideas below — semantic zoom, hover popups, sidenotes, metadata
blocks carrying status and epistemic confidence, progressive enhancement — are
adapted from **gwern.net** (`gwern.net/design`), which has been solving
"one document, many reading depths" for longer than anyone else. Deliberately
*not* adopted: link archiving and backlink graphs (meaningless in a single
file), dropcaps and Art Nouveau ornament (decoration without a job here), and
reader mode (the A−/A+ and theme controls already cover it).

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
the HTML is a *view* — never maintain the same prose in both.

## Semantic zoom (the organizing principle)

Borrowed from gwern.net, which solves the length problem without fragmenting a
document: build **one page readable at many depths**, and let the reader choose
how deep to go rather than choosing for them.

    title -> stat tiles -> metadata block -> lead paragraph -> section headers
      -> tables -> body prose -> collapsed <details> -> hover popups -> the file itself

Each layer must be *complete at its own level* — someone who reads only the
tiles and the lead should come away with something true, not a teaser. This is
what lets one artifact serve both "just tell me" and "show me everything",
which is the exact tension in agent output. Depth is opt-in; nothing important
may exist *only* behind a hover.

## Provenance: timestamps, staleness, and epistemic basis

A generated report's numbers rot, and the reader cannot tell by looking. Two
mechanisms, both in the template:

**Timestamps that age themselves.** `<time class="age" datetime="…">` renders as
`2026-07-30 22:14 (3d ago)` at view time, with the absolute value in the
tooltip. Add `data-stale-days="7"` and it turns amber with a ⚠ once past that
budget. Always carry two: **generated** (when the document was written) and
**data as of** (when the figures were actually measured) — they are frequently
not the same day, and only the second one matters for trust.

**Epistemic basis per claim.** gwern tags pages with confidence on the
Kesselman scale; for agent output the useful axis is not *how sure am I* but
*what does this rest on*:

| tag | meaning |
| --- | --- |
| `<span class="ev ev-measured">measured</span>` | a query/command was run; the number came back |
| `<span class="ev ev-derived">derived</span>` | computed from measurements shown elsewhere in the doc |
| `<span class="ev ev-inferred">inferred</span>` | reasoned from evidence, not directly observed |
| `<span class="ev ev-assumed">assumed</span>` | taken on faith, untested |

Tag anything a reader might act on. `assumed` is not an admission of failure —
an *unlabelled* assumption is. In practice this pays for itself: re-measuring
something previously tagged `inferred` is where a large share of real findings
come from.

Also carry gwern's **status** vocabulary when the document will be revisited:
`notes` → `draft` → `in-progress` → `finished`.

## Paths, popups, and code

**Paths should be openable.** `<a class="path" href="file:///abs/path">` opens
from a `file://` page; `vscode://file/<abs-path>:<line>` opens at a line in the
editor from anywhere. Render them monospace so they stay copyable.

**Popups are quotes, not fetches.** Give any element a child
`<template class="pop">` and it previews on hover, focus, or click-to-pin (Esc
closes; ctrl/cmd-click still follows the link). The content is inline, so it
works from `file://` forever and makes zero requests — but *you* must paste the
excerpt in while you have the file open. That constraint is a feature: the
preview is a quote you actually took, not a promise to read later.

The `<template>` must be a **direct child** of the element it previews. A
sibling silently binds the popup to the surrounding paragraph instead.

**Code blocks** use `<figure class="code">` with a `<figcaption>` carrying the
filename, `<span class="lang">` for the language (gets the accent color), and a
copy button; `<pre class="ln">` numbers lines when each is wrapped in
`<span class="line">`, and `hl` marks the lines that matter. Highlight tokens
with `tk-k`/`tk-s`/`tk-c`/`tk-n`/`tk-f` **as you write** — you already know
which token is a keyword, so shipping a runtime highlighter would be a
dependency bought for nothing.

**Quotes are never the same box as your own narration.** This is the single
most common legibility failure in a report with any back-and-forth structure
(corrections, timelines, review threads): wrapping *both* the paraphrase
you're writing and the words someone actually said in one identically-styled
box. A reader can't tell which is which without parsing every sentence.
Fix it structurally, not by remembering: narration is a **plain paragraph**,
no border, no background — exactly like the rest of your prose. The moment
you're relaying words someone actually wrote or said, switch to
`<blockquote class="q">…<cite>who, when</cite></blockquote>` — it renders in
an italic serif face (the template's one deliberate typographic pairing) with
an oversized opening quotation mark, so *quote-ness* reads at a glance,
independent of who's speaking. Add `.user` or `.ext` to recolor the left bar
by speaker; the serif treatment itself never changes, because "is this a
quote" and "who said it" are different facts and should look like different
facts. A short quote inside a running sentence doesn't need the full block —
`<span class="iq">` gives it a tinted italic run with no box.

**Sidenotes** (`<span class="sn" tabindex="0"><template class="pop">…`) are a
small superscript marker using the *same* popup mechanism as path/evidence
previews, not a separate margin-column trick. A true wide-margin sidenote
needs a page layout that reserves real margin space (gwern's does); a
`left: calc(50% + Nrem)` guess relative to the viewport has no real containing
block in a single-column report layout, and drifts off-position — verified
broken in production, not a hypothetical — the moment a real viewport hits
the boundary the guess assumed. One interaction pattern for every aside beats
maintaining a second, fragile one.

## Operator input: annotations, corrections, questionnaires

A report can collect input, not just display it — annotation fields on
findings rows, approve/defer/reject decision widgets, small questionnaires.
`file://` has no backend, so nothing the operator types can reach you on its
own; the pattern is autosave-to-`localStorage` (so edits survive reopening
*that* file — same mechanism as the template's theme/font-size persistence)
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

When you *revise* a report across sessions — a living workspace, a status page
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

Before shipping any artifact, run the two checks that file's own notes were
written from — extract the `<script>` and `node --check` it, then headless-render
and grep the DOM for evidence the JS actually ran. A syntax error anywhere in
the script block silently kills every interactive feature on the page.

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
  `rejected`. Duds and rejections stay in the table *with the reason*; deleting
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

Keep it one file. Split-per-thread markdown was the previous shape and its cost
was that the index and the threads drifted.

### Beads / PR repos specifically

Where a repo tracks work in Beads or GitHub, the workspace is a *view over*
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
   documents (or scratch/`/realm/tmp` for throwaways).
4. Deliver it. When the `Artifact` tool is available (Claude Code sessions),
   **publish by default** — artifacts are private until the operator shares
   them, and a browsable link (`claude.ai/code/artifacts`) is more useful long
   after the turn ends than a file sitting in scratch. Skim the content first
   for anything genuinely sensitive (credentials, unredacted personal data,
   material the operator hasn't seen if you didn't author it this turn) —
   internal paths, hostnames, and ordinary project/engineering detail are not
   a reason to hold back. Also send it with `SendUserFile`
   (`display: "render"`) so it previews inline in the same turn — the two
   aren't redundant: `SendUserFile` is the immediate look, `Artifact` is the
   thing that still exists next week. Skip the `Artifact` publish only when
   the tool genuinely isn't available (other agents/harnesses: print the
   path; `xdg-open` works), the content is explicitly scratch/throwaway, or
   the operator asked to keep it local.
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
- Diagrams: hand-write inline SVG (boxes+arrows beat ASCII art); label every
  edge; `viewBox` only, no fixed px sizes.
