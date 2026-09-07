# HTML report design guide

Load this reference when composing or reviewing an HTML report. The template
owns the house style, controls, and semantic colors. The report owns the
evidence, structure, and subject accent.

Contents: reading depth; provenance; paths and quotations; operator input;
revisions; living workspaces; visual contract; recurring reports; shipping checks.

## Semantic zoom

Build one page that works at several reading depths:

```text
title → stat tiles → metadata → lead → sections → tables → details → source
```

Each layer must be true and useful on its own. A reader who sees only the
tiles and lead must not receive a teaser or an unsupported conclusion. Use
tables for dense comparisons, badges for status, stat tiles for measured
headline values, and `<details>` for secondary depth. Keep the page useful
with JavaScript disabled.

## Provenance and epistemic basis

Carry both `generated` and `data as of` timestamps. The latter is when the
figures were measured and determines freshness. Use the template's `<time
class="age" datetime="...">` and `data-stale-days` where staleness matters.

Tag claims by basis:

- `measured`: a query or command returned the value;
- `derived`: computed from measurements shown elsewhere;
- `inferred`: reasoned from evidence but not directly observed;
- `assumed`: accepted without verification.

In a mostly measured report, state "measured unless tagged" in the metadata
instead of repeating an uninformative chip. Scope each exception to the exact
claim, table row, or tile it qualifies. Include the report status when it will
be revisited: `notes`, `draft`, `in-progress`, or `finished`.

For data-derived reports, query instead of estimating. Attach the exact query
or command to each important number in a popup or evidence link. Show missing
coverage and failed queries as gaps. Do not convert an unavailable value into a
round estimate.

## Paths, popups, and code

Use `<a class="path" href="file:///absolute/path">` for local paths. Add
`vscode://file/<absolute-path>:<line>` only when that route is known to be
available. A local path is useful only on a machine with the same file, so
include a short inline preview when the reader may not have it.

For a popup, put `<template class="pop">...</template>` directly inside its
host. Popups contain quoted material already read, not a promise to fetch
later. For path links, mark them `data-embed` or `data-embed="4000"` and run:

```bash
python3 generators/embed-path-popups.py <report.html>
```

The generator reads the current file head, is idempotent, and leaves missing
paths visibly unbundled. Use a hand-written excerpt only when a specific
passage is needed. Sidenotes use the same popup mechanism. A real margin note
needs layout space; a viewport-relative offset does not create that space.
Review embedded excerpts for private data before delivery or publication.

Keep quotations visually distinct from analysis. Use the template's
`<blockquote class="q">` with a source citation for quoted passages and
ordinary paragraphs for your interpretation. Do not style a paraphrase as an
exact quotation.

Code uses `<figure class="code">`, a filename caption, a language span, and a
copy button. Number lines with `<span class="line">` inside `<pre class="ln">`
and mark important lines with `hl`. Use the template token classes while
writing rather than adding a runtime syntax-highlighter dependency.

## Operator input

For reviews, decision queues, and plans, use the annotation, decision, and
questionnaire patterns in the skill's `references/patterns.md`. A `file://` page has no
backend. Save input to `localStorage` for reopening the same file and provide
a visible copy-for-agent control that serializes fields to JSON. Never imply
that local edits were received by an agent. A connected publisher may provide a
different return path only when its exposed contract and authority support it.

## Revisions and supersession

Mark genuinely new or changed blocks with `data-added="YYYY-MM-DD"` or
`data-changed="..."` at the granularity the reader needs. Do not restamp
untouched content. Living reports keep a stable filename; one-shot reports use
`<topic>-<YYYY-MM-DD>.html`.

When revising, run:

```bash
python3 generators/check-superset.py OLD.html NEW.html
```

Use it as an omission detector. Inspect every dropped heading. Restore an
accidental omission, pass `--rename "old=new"` for a real rename, or record a
deliberate scope removal and its reason in the revision metadata. Superseded
reports carry a `superseded-by` pointer and banner; successors point back with
`supersedes`. Living artifacts are republished at the same path when a
publisher supports stable paths.

## Living workspaces

A multi-session analysis needs a filterable lead register with one row per
lead and an explicit state: `open`, `in-flight`, `landed`, `dud`, or
`rejected`. Keep duds and rejections with their reasons. Put the genuinely
unexplored frontier before the narrative. Preserve standing method rules and
self-corrections, showing both an earlier claim and the measurement that
changed it. Give every claim a bead, commit, PR, source path, or command.

Compute summary counts from the rows with `data-calc="count:SELECTOR"` or
`sum:SELECTOR`; hand-write only values from outside the document. In a tracked
repo, the workspace is a view over Beads or GitHub, not a competing tracker.

## Contract and visual identity

Every artifact is one file with inline CSS and JavaScript, inline SVG or data
URIs, no external requests, and a readable static fallback. Use semantic
`<header>`, `<nav>`, `<main>`, `<section>`, and `<table>` elements with a clear
h2/h3 hierarchy. Style both themes through custom properties, support the
template's theme toggle, and keep the base font at 17px with other sizes in
`rem` or `em`. Wide tables scroll inside a bounded container.

Set `data-accent` on `<html>` deliberately: `forensic`, `ops`, `finance`,
`archive`, or `design`; unset uses infrastructure blue. Accent identifies the
subject. Status classes `ok`, `warn`, `bad`, `info`, and `todo` retain their
semantic colors. For sortable numeric columns, every cell needs `data-v`; use
an out-of-band sentinel such as `-1` for n/a. Inline SVG uses a `viewBox`, no
fixed dimensions, and labels every edge. Proofread SVG `<text>` separately.

## Recurring reports

Recurring shapes should be generated. Put repo-coupled generators in that
repo's tooling and repo-agnostic generators in this skill's `generators/`.
The generator should:

- re-export inputs for `--fresh` runs and state what input it used;
- map each section to measured, derived, authored, or operator-supplied input;
- print the regenerate command in the artifact;
- emit findings from checked conditions only when they are factual predicates.

Judgments remain authored assessments with an author and evidence. A generator
may collect their inputs, but must not silently turn a judgment into an
unconditional finding. Keep recurring reports in
`/realm/data/derived/reports/`, run `python3 generators/reports-index.py
/realm/data/derived/reports`, and make the index reflect current files.

## Shipping checks

Before delivery:

1. Extract the inline script and run `node --check`.
2. Confirm no `POP-TODO` remains in headline tiles.
3. Take generation time from the clock. Bind data-as-of to actual source
   measurement time; preserve supplied timestamps and identify supplied data.
   Never invent a query run to make historical evidence look fresh.
4. If an exposed, authorized browser or desktop route exists, inspect a fresh,
   non-empty DOM capture for behavior-specific evidence such as a populated
   TOC, rewritten ages, popup hosts, and calculated values. Keep command exit
   status separate from DOM evidence. Do not treat a timeout or empty/stale
   dump as success.
5. Proofread SVG text, paths, captions, and claims separately.
