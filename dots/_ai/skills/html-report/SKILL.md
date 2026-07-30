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

## Workflow

1. Copy `templates/report.html` (same dir as this skill) and fill the marked
   slots: title, meta chips, stat tiles, sections. Keep its CSS variables.
2. Pick patterns from `references/patterns.md` (sortable table, filter box,
   tabs, timeline, badge set, annotated diff, SVG diagram, deck nav) — paste
   only what the artifact needs.
3. Name it `<topic>-<YYYY-MM-DD>.html`, place it next to the deliverable it
   documents (or scratch/`/realm/tmp` for throwaways).
4. Claude Code: send with `SendUserFile` (`display: "render"`). Other
   agents: print the path; `xdg-open` works.
5. Feeding back: HTML artifacts re-read fine as agent input; keep ids/classes
   semantic so a later agent can parse the DOM.

## Layout quick-reference

- Page shell: sticky header, optional sidebar TOC (`nav#toc`), max-width
  `72rem`, `1rem`-ish gaps. Wide tables scroll inside `overflow-x:auto`.
- Comparisons: CSS grid `grid-template-columns: repeat(auto-fit, minmax(20rem,1fr))`.
- Status color: use the badge classes (`.ok .warn .bad .info .todo`) — never
  raw reds/greens; they're theme-tuned in the template.
- Diagrams: hand-write inline SVG (boxes+arrows beat ASCII art); label every
  edge; `viewBox` only, no fixed px sizes.
