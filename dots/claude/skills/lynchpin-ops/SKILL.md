---
name: lynchpin-ops
description: Operate Lynchpin as an internal Python API with direct module entrypoints for validation, warehouse rebuilds, calendar rendering, session summaries, baseline analytics, life timelines, and codebase analysis.
triggers:
  - "lynchpin validate"
  - "lynchpin warehouse"
  - "lynchpin calendar"
  - "lynchpin session summary"
  - "lynchpin baseline"
  - "lynchpin life timeline"
  - "lynchpin analysis"
  - "lynchpin refresh"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
  - Edit
argument-hint: "<command> [args]"
---

# Lynchpin Ops

Unified skill for operating the Lynchpin personal data analysis hub.
Prefer composable Python module imports over CLI wrappers.

Canonical doctrine for this skill family lives at:

- `/realm/project/sinnix/dots/codex/skills/lynchpin-ops/README.md`
- `/realm/project/sinnix/dots/codex/skills/lynchpin-ops/METHODOLOGY.md`
- `/realm/project/sinnix/dots/codex/skills/lynchpin-ops/project-runs/README.md`

## Core Pattern

All Lynchpin data follows: **Source → Iterator[Dataclass] → @persistent_cache → Warehouse TABLE_SPEC**

```python
# Direct Python usage — compose freely
from lynchpin.sources.indices.gitstats import iter_commits
from lynchpin.sources.indices.analysis import iter_cross_project_metrics, iter_commit_facts
from lynchpin.sources.indices.coding_sessions import iter_coding_sessions
from lynchpin.sources.indices.spark_reviews import iter_spark_reviews
from lynchpin.sources.indices.sinex_analysis import iter_sinex_crate_metrics, iter_sinex_monthly_velocity
from lynchpin.sources.captures.activitywatch import iter_window_events, iter_afk_events
from lynchpin.sources.exports.health import iter_samsung_sleep
from lynchpin.sources.exports.spotify import iter_streams
```

## Available Source Modules

| Module | Yields | Domain |
|--------|--------|--------|
| `sources.indices.gitstats` | commits, repo info, tokei | Git analytics |
| `sources.indices.analysis` | commit facts, cross-project, module maps, hotspots, dependencies | Codebase analysis (artifact-backed) |
| `sources.indices.coding_sessions` | reconstructed coding sessions | Session analytics |
| `sources.indices.spark_reviews` | SPARK review results, reduction summary | LLM review artifacts (preserved) |
| `sources.indices.sinex_analysis` | Sinex crate metrics, monthly velocity | Sinex ecosystem analysis |
| `sources.captures.activitywatch` | window focus, AFK, web events | Desktop telemetry |
| `sources.captures.atuin` | shell commands | Shell history |
| `sources.captures.webhistory` | browser history entries | Web browsing |
| `sources.exports.health` | sleep, weight | Wearable data |
| `sources.exports.spotify` | streaming history | Music |
| `sources.exports.reddit` | comments, posts, saved, votes | Reddit |
| `sources.exports.polylogue` | markdown transcripts, run metadata | Chat archives |
| `sources.libraries.finance` | ledger transactions | Finance |
| `sources.libraries.dendron` | vault notes | Knowledge base |

## Orchestration Entrypoints

### Warehouse & Views
```bash
python -m lynchpin.views.warehouse refresh --format parquet    # Full warehouse rebuild
python -m lynchpin.views.warehouse refresh --sources analysis  # Analysis tables only
python -m lynchpin.views.calendar_views <start> <end>          # Render calendar views
python -m lynchpin.views.calendar_narratives <start> <end> --mode reflective
python -m lynchpin.views.session_summaries summarise <path>    # Session summaries
python -m lynchpin.views.velocity                              # Cross-project velocity
python -m lynchpin.views.ledgers artefact                      # Artefact ledger
```

### Baseline Analytics
```bash
python -m lynchpin.system.baseline                  # Default: auto mode
python -m lynchpin.system.baseline --mode live      # Live extraction
python -m lynchpin.system.baseline --mode bundle    # Read-only from bundle
python -m lynchpin.system.baseline --full           # Full history
python -m lynchpin.system.baseline --skip-git       # Skip git (faster)
```

**API**:
```python
from lynchpin.system.baseline import run_baseline, BaselineResult
result: BaselineResult = run_baseline(mode="auto", full=True)
```

**Artifacts**: `artefacts/core/baseline/latest/` — git_numstat.jsonl, activitywatch summaries, atuin, codex sessions, sleep

### Life Timeline
```bash
python -m lynchpin.system.life_timeline --start 2024-01 --end 2024-12
python -m lynchpin.system.life_timeline_digest      # Markdown digest
python -m lynchpin.system.life_timeline_oembed enrich # YouTube enrichment
python -m lynchpin.system.life_timeline_narrative    # LLM narrative
```

**API**:
```python
from lynchpin.system.life_timeline import run_life_timeline, LifeTimelineResult
result: LifeTimelineResult = run_life_timeline(start_month="2024-01", end_month="2024-12")
```

**Artifacts**: `artefacts/lifelog/life-timeline/`

### Codebase Analysis
```bash
python -m lynchpin.analysis refresh                 # DAG-orchestrated full refresh
python -m lynchpin.analysis refresh --dry-run       # Show execution plan
python -m lynchpin.analysis refresh --up-to sinex_structure  # Partial refresh
python -m lynchpin.analysis analysis-validate       # Validate artifacts
python -m lynchpin.analysis lynchpin-self            # Self-analysis
```

Individual analysis steps (for debugging):
```bash
python -m lynchpin.analysis sinex                   # Sinex structural
python -m lynchpin.analysis sinex-temporal           # Sinex velocity
python -m lynchpin.analysis cross                    # Cross-project metrics
python -m lynchpin.analysis commit-facts             # Commit fact table
python -m lynchpin.analysis spark-review-packets     # SPARK review packets
python -m lynchpin.analysis spark-review-reduce      # SPARK review reduction
```

**Artifacts**: `artefacts/analysis/derived/`

### Validation & Refresh
```bash
python -m lynchpin.system.validate hpi --quick
python -m lynchpin.views.warehouse refresh --format parquet
```

### Multi-Scale Interpretation Guidance

- Use `lynchpin.views.calendar_summary` and `lynchpin.views.calendar*` as the
  day-scale structured substrate.
- Use `lynchpin.system.life_timeline*` for month/life-scale synthesis.
- Treat both as current delivery surfaces, not as fixed architecture standards.
- When adding new higher-level understanding, prefer reusable structured facts
  and rollups over prompting directly from raw source rows.
- For activity understanding, start from raw ActivityWatch/Atuin/instrumentation
  signals and classify by purpose, not by app name alone.
- Treat the model's context window state as a first-class output: prefer
  compact context packets assembled from typed artifacts over ad hoc prompt
  stuffing.
- Do not use removed umbrella refresh commands such as
  `lynchpin.system.materialize`.

## Rules

1. Prefer direct `python -m lynchpin...` invocations over `just` wrappers.
2. Run from `/realm/project/sinity-lynchpin` when paths are repo-relative.
3. Do not use retired surfaces: `lynchpin.views.export_dashboard_data`, packaged `lynchpin-*` wrappers, `lynchpin.system.materialize`, `pipelines/webhistory/legacy`, or the deleted `refresh-core/wave1/wave2` CLI commands.
4. Report the exact command and output path for any materialized artefact.
5. For composable analysis, import source modules directly rather than shelling out to CLI.
