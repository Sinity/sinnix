---
name: lynchpin-baseline
description: Rebuild baseline analytics (git index, ActivityWatch, Atuin, Codex sessions, sleep) via lynchpin.system.baseline
user_invocable: true
---

# lynchpin-baseline

Rebuild the baseline analytics suite from local datasets with
`lynchpin.system.baseline`.

## Canonical Entrypoint

```bash
python -m lynchpin.system.baseline \
  --mode auto \
  --output-dir artefacts/core/baseline/latest
```

Run from `/realm/project/sinity-lynchpin`. If you are outside the repo, prefix
with `direnv exec /realm/project/sinity-lynchpin`.

## Modes

- `--mode auto` (default): prefers bundle under `--session-root`, falls back to live extraction
- `--mode bundle`: read-only from bundle exports
- `--mode live`: query live local sources (ActivityWatch SQLite, Atuin DB, Codex sessions, git repos)

## Key Options

| Option | Default | Purpose |
| --- | --- | --- |
| `--session-root` | `/realm/data/sinity-lynchpin/baseline-inputs/latest` | Bundle input directory |
| `--health-root` | `/realm/data/exports/health/processed` | Merged wearable exports |
| `--output-dir` | `artefacts/core/baseline/latest` | Output directory |
| `--full` | off | Use full available history |
| `--window-days` | `90` | Default live window when `--since` is omitted |
| `--since` / `--until` | none | Bound live extraction window |
| `--skip-git` | off | Skip git summaries (faster) |
| `--include-web-sample` | off | Snapshot ActivityWatch web bucket |

## Common Compositions

```bash
# latest auto refresh
python -m lynchpin.system.baseline --mode auto --output-dir artefacts/core/baseline/latest

# scoped live window
python -m lynchpin.system.baseline \
  --mode live \
  --since 2026-01-01T00:00:00Z \
  --until 2026-03-01T00:00:00Z \
  --output-dir artefacts/core/baseline/2026-01_to_2026-03

# frozen bundle rerun
python -m lynchpin.system.baseline \
  --mode bundle \
  --session-root /realm/data/sinity-lynchpin/baseline-inputs/2026-03-01 \
  --output-dir artefacts/core/baseline/2026-03-01
```

## Expected Artifacts

- `artefacts/core/baseline/latest/git_numstat.jsonl` — per-file git numstat
- `artefacts/core/baseline/latest/git_activity_summary.json` — commit/churn metrics
- `artefacts/core/baseline/latest/activitywatch_window_summary.json` — app usage
- `artefacts/core/baseline/latest/activitywatch_afk_summary.json` — AFK segments
- `artefacts/core/baseline/latest/atuin_summary.json` — shell command density
- `artefacts/core/baseline/latest/codex_sessions_summary.json` — Codex session index
- `artefacts/core/baseline/latest/sleep_summary.json` — sleep metrics
- `artefacts/core/baseline/latest/activity_timeline.json` — cross-source timeline

## When to Run

- Before warehouse/calendar work when the git index needs refresh
- After new data exports land (health, codex sessions)
- As part of a broader refresh: `python -m lynchpin.system.materialize --baseline`

## API

```python
from lynchpin.system.baseline import run_baseline, BaselineResult
result: BaselineResult = run_baseline(
    session_root=Path("..."),
    health_root=Path("..."),
    output_dir=Path("..."),
    mode="auto",
    full=True,
)
```
