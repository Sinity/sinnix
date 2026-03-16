---
name: lynchpin-ops
description: >
  Operate Lynchpin as an internal Python API with direct module entrypoints for
  validation, warehouse rebuilds, calendar dossier generation, session
  summaries, instrumentation ingest, and related read-model tasks.
metadata:
  short-description: API-first Lynchpin operator workflows
---

# Lynchpin Ops

This skill owns the evolving doctrine at:

- `/realm/project/sinnix/dots/codex/skills/lynchpin-ops/README.md`
- `/realm/project/sinnix/dots/codex/skills/lynchpin-ops/METHODOLOGY.md`
- `/realm/project/sinnix/dots/codex/skills/lynchpin-ops/project-runs/README.md`

Use this skill when the task is about Lynchpin control-plane workflows and the
canonical surface should be the internal `lynchpin.*` Python modules rather
than `just` wrappers or packaged `lynchpin-*` binaries.

## Canonical Surface

- Repo-local module CLIs via `python -m lynchpin.<module>`
- Python imports from `lynchpin.sources.*`, `lynchpin.views.*`,
  `lynchpin.system.*`, and `lynchpin.ingest.*`
- Runbooks in `/realm/project/sinity-lynchpin/docs/reference/`

`just` is no longer the canonical workflow surface for baseline or life
timeline work. Use it only for generic repo utilities that still exist in the
project `justfile`.

## Rules

0. Read `README.md` and `METHODOLOGY.md` before substantial trajectory or interpretation work.
1. Prefer direct `python -m lynchpin...` invocations or imports over `just`.
2. Use `lynchpin-baseline` and `lynchpin-life-timeline` when the task is one of
   those heavier workflows.
3. Do not revive removed packaged wrappers such as `lynchpin-validate`,
   `lynchpin-materialize`, `lynchpin-calendar`, `lynchpin-warehouse`, or
   `lynchpin-session-summaries`.
4. Do not revive removed legacy paths such as
   `lynchpin.views.export_dashboard_data`, flat terminal-capture migration
   commands, or `pipelines/webhistory/legacy`.
5. When examples drift, trust live `--help` output and the repo runbooks over
   historical command snippets.
6. Run repo-local commands from `/realm/project/sinity-lynchpin`.
7. For non-trivial runs, record the exact module command, key arguments, and
   output paths.
8. Treat current report surfaces as provisional delivery layers; the durable
   target is reusable trajectory artifacts and context packets.

## Common Module Entry Points

- `python -m lynchpin.system.validate`
- `python -m lynchpin.system.baseline` — see `lynchpin-baseline`
- `python -m lynchpin.system.life_timeline` — see `lynchpin-life-timeline`
- `python -m lynchpin.views.warehouse`
- `python -m lynchpin.views.calendar_views`
- `python -m lynchpin.views.calendar_narratives`
- `python -m lynchpin.views.session_summaries`
- `python -m lynchpin.views.ledgers`
- `python -m lynchpin.views.project_bundles`
- `python -m lynchpin.views.velocity`
- `python -m lynchpin.views.knowledge_graph`
- `python -m lynchpin.ingest.instrumentation`
- `python -m lynchpin.ingest.webhistory`
- `python -m lynchpin.ingest.wykop_export`

## Common Invocations

```bash
python -m lynchpin.system.validate hpi --quick
python -m lynchpin.views.warehouse refresh --sources activitywatch,atuin
python -m lynchpin.views.calendar_views 2026-03-07 2026-03-13 --output artefacts/calendar/views
python -m lynchpin.views.calendar_narratives 2026-03-07 2026-03-13 --mode reflective
python -m lynchpin.views.session_summaries summarise docs/reference/sessions/example.md
```

## Workflow Guidance

### Validation and Refresh

- Run `python -m lynchpin.system.validate hpi --quick` before broad rebuilds or
  when source health is in doubt.
- Use `python -m lynchpin.views.warehouse refresh` when the task is "refresh
  the derived read models", not when you only need a single source or view.

### Warehouse

- Use `python -m lynchpin.views.warehouse build|materialize|refresh` for the
  canonical read-model rebuild.
- Treat the warehouse as query surface only; raw data stays under `/realm/data`.

### Calendar and Narratives

- Use `python -m lynchpin.views.calendar_views START END` for dossier
  rendering, not retired dashboard exporters.
- Use `python -m lynchpin.views.calendar_narratives START END ...` for
  prompt-driven summaries that sit on top of those day views.
- Treat `lynchpin.views.calendar_summary` as the main day-scale structured
  substrate. If you are adding higher-level understanding, prefer promoting
  stable facts and rollups out of it rather than prompting directly from raw
  source rows.
- For activity understanding, start from raw ActivityWatch/Atuin/instrumentation
  signals and classify by purpose, not by app name alone.

### Life Timeline and Multi-Scale Work

- Use `python -m lynchpin.system.life_timeline*` for month/life-scale
  historical synthesis.
- Treat `lynchpin.views.calendar*` and `lynchpin.system.life_timeline*` as
  current delivery surfaces, not as fixed architecture standards.
- When adding new higher-level analysis, prefer shared structured artifacts or
  warehouse tables that can feed day/week/month/quarter/year views, instead of
  inventing a one-off narrative path.
- Treat the model's context window state as a first-class output: prefer
  compact context packets assembled from typed artifacts over ad hoc prompt
  stuffing.
- Do not reintroduce removed umbrella refresh commands such as
  `lynchpin.system.materialize`.

### Sessions

- Use `python -m lynchpin.views.session_summaries summarise INPUT_PATH` only
  when an API key/runtime is available.
- Keep Polylogue responsible for rendering chat exports into canonical
  Markdown before summarization.

### Instrumentation and Webhistory

- Use `python -m lynchpin.ingest.instrumentation ...` for terminal/audio/screen
  metadata and audits.
- Use `python -m lynchpin.ingest.webhistory ...` for browser-history rebuilds.
