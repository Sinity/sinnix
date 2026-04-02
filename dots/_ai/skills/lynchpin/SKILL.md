---
name: lynchpin
description: Operate Lynchpin's scaffold-first retrospective workflow. Use when you need to refresh retrospective scaffold JSON, inspect DuckDB or Polylogue evidence for a period, or improve `artefacts/retrospective/narratives/*` without relying on the obsolete baseline-era split.
metadata:
  short-description: Scaffold-first Lynchpin retrospective workflow
---

# Lynchpin

Use this skill for retrospective and evidence work in `/realm/project/sinity-lynchpin`.

This is the one current Lynchpin skill. The old `lynchpin-baseline`, `lynchpin-ops`, and narrative-only split are retired.

## Canonical Flow

1. Pick the period and the scaffold tree you are working in.
2. Refresh scaffold JSON with `python -m lynchpin.scripts.generate_scaffold`.
3. Read the scaffold payload before jumping to ad hoc warehouse queries.
4. Use live DuckDB or Polylogue queries only to verify or deepen specific claims.
5. Update the target narrative in `artefacts/retrospective/narratives/`.
6. Keep exact commands, query text, and output paths with your notes or evidence bundle.

## Scaffold First

The scaffold generator is the canonical entrypoint:

```bash
cd /realm/project/sinity-lynchpin

# Refresh one day into the working scaffold tree
python -m lynchpin.scripts.generate_scaffold \
  --day 2026-03-28 \
  --output artefacts/retrospective/scaffold_ \
  --force

# Refresh a range
python -m lynchpin.scripts.generate_scaffold \
  --start 2026-03-01 \
  --end 2026-03-31 \
  --output artefacts/retrospective/scaffold_v3 \
  --force
```

The repo currently has multiple scaffold corpora:

- `artefacts/retrospective/scaffold_`
- `artefacts/retrospective/scaffold_v1`
- `artefacts/retrospective/scaffold_v2`
- `artefacts/retrospective/scaffold_v3`

Do not assume the script default output is the authoritative corpus. Point `--output` at the exact scaffold tree you intend to maintain.

## Evidence Surfaces

Primary evidence, in order:

1. Scaffold JSON for the target period.
2. Direct Polylogue/session-profile evidence plus `processed_git_*`, `processed_delivery_telemetry`, `processed_focus_spans`, and app/shell timelines.
3. `processed_chat_activity`, `processed_project_attention`, `processed_context_switches`, and `processed_circadian`.
4. `trajectory_*` tables only as corroborating convenience surfaces.

Avoid the old baseline flow. `lynchpin.system.baseline` is not the current canonical workflow.

## Common Commands

```bash
# Warehouse spot checks
duckdb artefacts/lynchpin/warehouse.duckdb -c "SHOW TABLES"
duckdb artefacts/lynchpin/warehouse.duckdb -c \\
  "SELECT date, total_commits, active_hours, commit_density_per_active_hour FROM processed_delivery_telemetry WHERE date BETWEEN DATE '2026-03-01' AND DATE '2026-03-31' ORDER BY date"

# Raw evidence bundle for a narrative pass
python3 scripts/run_narrative_evidence.py \
  --start 2026-03-16 \
  --end 2026-03-17 \
  --providers claude-code codex \
  --outdir /realm/project/sinity-lynchpin/.claude/scratch/narratives
```

## Working Paths

- Project root: `/realm/project/sinity-lynchpin`
- Warehouse: `artefacts/lynchpin/warehouse.duckdb`
- Scaffold corpora: `artefacts/retrospective/scaffold_` and `artefacts/retrospective/scaffold_v*`
- Narrative output: `artefacts/retrospective/narratives/`
- Archive/reference material: `artefacts/retrospective/archive/`

`artefacts/retrospective/archive/_narratives` is style/reference material only. Do not treat it as authoritative truth.

## Rules

1. Start from scaffold, not from stale baseline artefacts.
2. Prefer DuckDB queries over ad hoc Python iterators for spot analysis.
3. Keep every material claim anchored to a command, query, or scaffold path you can point to later.
4. If scaffold and live data disagree, inspect the underlying source rather than papering over the mismatch.
5. Never rely on `_narratives` or trajectory-only summaries when direct evidence is available.
