---
name: lynchpin-ops
description: Operate Lynchpin as an internal Python API with direct module entrypoints for validation, warehouse rebuilds, calendar rendering, and session summaries.
triggers:
  - "lynchpin validate"
  - "lynchpin warehouse"
  - "lynchpin calendar"
  - "lynchpin session summary"
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

Use Lynchpin through direct `python -m lynchpin...` module entrypoints and
imports from the internal Python API.

- `python -m lynchpin.system.validate`
- `python -m lynchpin.system.materialize`
- `python -m lynchpin.views.warehouse`
- `python -m lynchpin.views.calendar_views`
- `python -m lynchpin.views.calendar_narratives`
- `python -m lynchpin.views.session_summaries`
- `python -m lynchpin.ingest.instrumentation`
- `python -m lynchpin.ingest.webhistory`

Rules:

1. Prefer direct `python -m lynchpin...` invocations over `just` wrappers for module-backed operator workflows.
2. Run from `/realm/project/sinity-lynchpin` when paths are repo-relative.
3. Do not use retired surfaces such as `lynchpin.views.export_dashboard_data`, packaged `lynchpin-*` wrappers, or `pipelines/webhistory/legacy`.
4. Report the exact command and output path for any materialized artefact.
