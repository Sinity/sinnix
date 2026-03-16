# Lynchpin Ops Methodology

## Thesis

The point of Lynchpin is not to emit reports.

The point is to build a progressively improving understanding stack that:

- starts from raw local signals,
- climbs toward higher-level typed representations,
- assembles compact model-facing context from those representations,
- and feeds improved interpretation back into durable code and artifacts.

## Operating Doctrine

### 1. Report Surfaces Are Disposable

`calendar_*`, `life_timeline*`, and other current report surfaces are useful
delivery layers and evidence about previous attempts.

They are not the architecture to preserve.

### 2. Raw Signal First

Start with the richest underlying signals:

- ActivityWatch window/AFK/web spans,
- terminal instrumentation sessions/events,
- Atuin commands,
- git commits and coding sessions,
- chat/session timestamps and transcript metadata,
- webhistory and Takeout traces,
- health, finance, location, and note signals.

Normalize those before trying to narrate them.

### 3. Classify by Purpose

The meaningful label is usually not the app name.

Prefer labels like:

- coding,
- research,
- writing,
- planning,
- admin,
- social,
- media,
- recovery.

Infer them from combinations of title, domain, cwd, repo, command text,
adjacent spans, transcript/session context, and known project/topic mappings.

### 4. Build Activity Chains

One of the first non-trivial substrates should be activity chains:

- adjacent spans/events stitched into coherent chains,
- mode shifts marked explicitly,
- boundaries carrying confidence and evidence,
- multi-scale sessionization possible on top.

This is closer to how time was actually lived than isolated spans or daily sums.

### 5. Context State Is a Product

What should enter the model context window is itself a first-class artifact.

Do not treat prompt assembly as ephemeral glue.

The system should build compact, budgeted context packets such as:

- current-state packet,
- recent-days packet,
- active-period packet,
- dominant-projects packet,
- active-themes packet,
- coverage/uncertainty packet,
- claims/hypotheses packet.

These should be assembled from typed artifacts, not from raw source dumps.

### 6. Heuristics First, ML Second

Start with explicit rules:

- regex and tag rules,
- domain/title token extraction,
- path/repo/project matching,
- adjacency and gap thresholds,
- scoring rules with evidence weights.

Add heavier methods where they clearly improve reusable representations:

- changepoint detection,
- clustering,
- anomaly detection,
- sequence models,
- supervised classifiers when a real labeling loop exists.

## Preferred Build Ladder

1. `sources/*`
   - canonical inputs, typed iterators.
2. `metrics/*`
   - deterministic feature extractors and quality metrics.
3. `trajectory.signal`
   - normalized spans/events across sources.
4. `trajectory.rules`
   - project/topic/mode heuristics.
5. `trajectory.chains`
   - coherent activity chains and sessionization.
6. `trajectory.day|period|episode`
   - typed artifacts at increasing scales.
7. `context.*`
   - budgeted model-facing context packets and state.
8. interpretation
   - narrative, hypotheses, comparative analysis.
9. feedback
   - push stable new logic back down into modules or packet builders.

## What To Keep In Model Context

The ideal context window state is:

- compact,
- task-conditioned,
- evidence-bearing,
- uncertainty-aware,
- incrementally refreshable.

It should usually include:

- current or queried period summary,
- most relevant recent chains,
- dominant projects/topics/modes,
- notable transitions/anomalies,
- missingness/coverage warnings,
- active hypotheses or tensions,
- only the minimum supporting evidence needed.

It should usually exclude:

- large raw transcripts,
- raw event streams,
- undifferentiated top-N dumps,
- artifacts that can be retrieved later more selectively.

## Existing Seeds, Not Final Forms

Some current repo surfaces are useful seeds:

- `lynchpin.views.calendar_summary`
- `lynchpin.system.meta`
- `lynchpin.views.session_summaries`
- `lynchpin.views.knowledge_graph`

But none of them yet constitute the final context substrate.

## Durable Notes

Interpretive method updates and major architecture realizations should be written
into this skill or into `project-runs/`, not left only in transient chat.
