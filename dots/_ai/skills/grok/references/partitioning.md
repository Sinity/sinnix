# Partitioning by Measurement

## Why measure first

Partitioning by intuition ("this directory looks big") or by uniform
line-count slicing produces regions that don't match how the code is actually
organized — an agent assigned a 5000-line arbitrary slice spanning three
unrelated modules can't build the coherent mental model that catches
cross-function invariant violations. Partitioning by *measured, real*
directory/file sizes, aligned to module boundaries, does.

## The sweep

Per crate/package/top-level component:

```bash
find <root>/<component> -name "*.<ext>" -not -name "*_test.*" | xargs wc -l | sort -rn
```

Drill into any subdirectory whose total still exceeds the target size for its
intended tier (below) by listing its own subdirectories the same way. Stop
drilling once a region is small enough for the tier it'll be assigned to, or
once you hit natural file-level granularity.

For languages/frameworks with a different natural exclusion (test files,
generated code, vendored dependencies), adjust the `-not -name` filter
accordingly — the goal is counting only the code a human/agent would actually
read, not padding the number with boilerplate.

`scripts/partition_by_size.sh <root> <target-lines>` automates this: it walks
a directory tree, sums `.rs`/`.py`/`.ts`/etc. files (configurable) per
subdirectory, and prints a flat region list where each region is under the
target — merging small siblings and splitting oversized ones by their own
subdirectories. Treat its output as a *starting point* to sanity-check against
real module boundaries, not a final answer to dispatch blindly.

## Target sizes by tier

These aren't arbitrary — they're back-derived from what worked across real
campaigns (a 25-region wave across ~411K lines, cross-checked against which
regions later needed a second narrow pass to find more):

| Tier | Target region size | Rationale |
|---|---|---|
| Opus, dense/subtle logic | 3K–8K lines | Admission pipelines, transaction boundaries, provenance/identity substrates, DB write chokepoints — code where the bug is in an interaction between two functions, not a local pattern. Needs room to hold cross-function state without losing the thread; going much bigger risks the same "skim, not read" failure a lower-tier model would have at any size. |
| Sonnet, coverage-shaped | up to ~15K lines | Mechanical/repetitive surfaces: RPC handler stubs, CLI command implementations, source-contract registrations. High volume but each unit is locally comprehensible — the risk isn't losing a cross-cutting invariant, it's simply not reading everything, so the region needs to be small enough that "read every file" is actually followed, not "read the first half and extrapolate." |
| Fast + tiny-context (e.g. Codex spark-tier), narrate-through | 1–4 files, 500–2500 lines | These models are optimized for speed over context depth and often ship instructions that actively discourage broad exploration. Give them a small, explicit file list and a forced-narration prompt (see `techniques.md`) rather than a directory to explore — they do well at close reading of a small, named target and poorly at self-directed scoping. |

If a region doesn't fit comfortably in its tier's target even after drilling
to file-level granularity (a single file larger than the target — this
happens, e.g. a 3000+ line schema-application engine), either accept the
larger unit for a first-pass Opus/Sonnet read and schedule a second
narrate-through pass split by internal function-group boundaries (grep for
`pub fn`/`impl` boundaries to find natural split points), or split by logical
half if the file has an obvious seam.

## Priority ordering — audit the cold spots first

Cross-reference the partition against what prior sweeps (thematic or
per-region) already touched. Not "has any agent looked at this file" but
"has this specific file had a *close* read" — a file mentioned only in a
grep-driven thematic sweep, or read as part of an oversized region an agent
explicitly flagged as "partially covered, ran out of room," is still
effectively unaudited. Cold-spot signals worth prioritizing:

- Directories with zero agent dispatches this campaign.
- Files an agent's own coverage statement named as "not reached" or
  "deprioritized for time" — these are self-reported gaps, the highest-
  confidence signal you have.
- The tooling that *verifies* the rest of the codebase (build scripts, CI
  gates, doctor/health checks) — bugs here invalidate the audit's own
  confidence in everything else, and it's routinely under-audited because it
  doesn't look like "the product."
- Anything explicitly deferred in a prior campaign's summary with a stated
  reason ("lower reimport-correctness stakes") — valid triage at the time,
  but worth a dedicated later wave once the higher-stakes work is done.

## No silent caps

If time/budget bounds coverage (you're auditing 40 of 60 candidate regions,
or skipping a tier), say so explicitly in the campaign's final report. A
partition that silently covers 70% and gets reported as "audited the
codebase" reads as complete when it wasn't — list what was deliberately
excluded and why, every time.
