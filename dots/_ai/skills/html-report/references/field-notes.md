# Field notes

Append-only log of things learned by _using_ this skill. Every agent that
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

> **Consolidated 2026-08-02** (17 entries folded, none remaining; the previous
> commit holds the originals verbatim). Where they went: shipping-check
> lessons (script syntax, headless-DOM judgment, dump freshness,
> sandbox/timeout flags, clock-sourced timestamps, Write-not-heredoc helpers,
> SVG text proofreading) → SKILL.md "Shipping checks". Claim-tint scope
> (round 2 superseding round 1) + tabindex popup fix + `.tile.qa` query slot +
> computed `data-calc` tiles → `templates/report.html`. Hand-placed SVG layout
> rules, era-band/hatch time series, entity chips, segmented decision buttons,
> radio `name` uniqueness, mixed-column `data-v` sentinel → `patterns.md`
> (+ SKILL layout quick-ref). Query-vs-guess methodology → SKILL.md
> "Data-derived reports". Artifact-publish-by-default → SKILL.md workflow
> step 4. The `rg -rn` trap was general tool hygiene, not skill material —
> dropped.

### 2026-08-03 — `file://` links are dead when the report ships via Artifact

**What happened:** operator correction on a report published via the `Artifact` tool: every
`<a class="path" href="file:///...">` link was non-functional — clicking did nothing useful,
since the page was served from claude.ai's Artifact hosting, not opened locally. The report
had bare path links with no `<template class="pop">` child, so there was no fallback either.
**Root cause / mechanism:** the skill's "openable path" pattern (SKILL.md, "Paths, popups, and
code") assumes the reader opens the HTML file locally via `file://`, where such links resolve
on the reader's own filesystem. That assumption silently breaks the moment the same artifact
is _also_ published via `Artifact` (which the skill's own workflow step 4 says to do by
default) — the Artifact-hosted copy runs in a browser sandbox with no access to the operator's
local files, and `file://` navigation from an `https://` origin is blocked outright by the
browser besides. A report that is _both_ saved locally _and_ published (the normal case now)
needs to work in both contexts, and only the popup half of the pattern survives Artifact
hosting.
**Fix or pattern:** treat the popup as load-bearing, not optional, for any `a.path` in a report
that will be published via `Artifact` — the `href="file:///..."` still helps the local-file
reader and costs nothing, but every such link should also carry a `<template class="pop">`
with a real excerpt. A same-session follow-up correction sharpened the fix further: hand-typing
that excerpt means reading the file into the agent's own context just to retype a piece back
out (the operator called this out directly — "without abusrd stuff like you retyping
everything"). **Folded**: `generators/embed-path-popups.py` compiles a bare `data-embed` marker
into the bundled popup by reading the file fresh from disk, and SKILL.md's "Paths, popups, and
code" section now names it as the default path — manual excerpt-typing is the exception, for
quoting one specific passage rather than a file's head.

## 2026-08-03 — POP-TODO grep matches the template's own SLOT comment

The shipping-check grep for `POP-TODO` fires on the stat-tiles SLOT comment
("the shipping check greps for the POP-TODO sentinel") even after every tile is
filled — delete that comment block when filling the tiles, or the check
false-positives. Consider rewording the template comment to not contain the
literal sentinel.
