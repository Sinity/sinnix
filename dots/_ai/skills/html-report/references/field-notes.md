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
