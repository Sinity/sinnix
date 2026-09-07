---
name: html-report
description: Produce self-contained interactive HTML reports, reviews, censuses, dashboards, plans, incident timelines, or comparisons for human readers.
---

# HTML reports

Use this skill when a human-facing deliverable benefits from scanning, filtering,
drill-down, spatial comparison, or progressive disclosure. Use Markdown when the
artifact will be re-edited, is an append-only ledger, or is a small answer.

The detailed design and accessibility guide is in
[`references/design-guide.md`](references/design-guide.md). Load it before
writing the artifact. Load [`references/patterns.md`](references/patterns.md)
only for the interaction patterns the artifact needs.

## Workflow

1. Decide whether HTML is the canonical artifact or a view over a canonical
   Markdown/data source. Preserve the source when readers will re-edit it.
2. Gather the source evidence. Query systems for exact numbers, record the data
   as-of time separately from generation time, and mark measured, derived,
   inferred, and assumed claims.
3. Copy `templates/report.html`, keep its CSS variables and semantic shell, and
   compose one file with inline CSS, JavaScript, SVG, and data URIs only.
4. Add only the sections, controls, and patterns that serve the reader. Keep
   content readable with JavaScript disabled and make paths or queries useful
   without a network request.
5. For operator input, use the local annotation and copy-for-agent pattern.
   Never imply that `file://` input was received. Publish or send the file only
   when an exposed tool and the current authority permit it. Otherwise return
   the local path and say what was not published.
6. Place one-shot reports beside the deliverable. Place living or
   cross-referenced reports in `/realm/data/derived/reports/` and refresh its
   index with the bundled generator.

## Verification

- Extract the inline script to a temporary file and run `node --check`.
- Run the static checks in the design guide, including a `POP-TODO` census and
  proofread of SVG text.
- If an exposed browser or desktop route is available and authorized, render the
  local file and inspect the resulting DOM. A nonzero or timed-out browser
  process is not itself a pass, and a successful process is not proof that the
  required behavior ran. Check non-empty, fresh output and behavior-specific
  DOM evidence. If no route is available, report that rendering was not run.
- When revising a report, use `generators/check-superset.py` as an omission
  detector. Restore accidental drops or declare intentional scope removals,
  renames, and their reasons in the revision metadata; a heading is not
  immutable merely because an older version contained it.
- For recurring reports, regenerate from current inputs. Generators may collect
  and derive facts, but human judgments remain attributed authored assessments
  and must not be emitted as unconditional predicates.

## Delivery contract

State the output path, canonical source (if any), generation and data-as-of
times, evidence basis, verification commands and results, publication status,
and residual limitations. Do not claim interactive, rendered, or published
behavior that was not directly checked through an available route.
