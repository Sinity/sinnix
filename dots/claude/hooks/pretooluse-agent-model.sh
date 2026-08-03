#!/usr/bin/env bash
# PreToolUse hook (matcher: Agent) — warn on subagent dispatches that omit an
# explicit model. Soft warning only (never blocks): the standing dispatch rule
# is "no silent model inheritance" (sonnet/haiku for implementation lanes,
# fable/opus only as an explicit judgment-lane choice; forks exempt because
# they inherit by design). Repo-level policy may harden this to a deny; the
# global default stays advisory so built-in flows are never broken.
set -euo pipefail
python3 - <<'PY'
import json, sys
try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ti = payload.get("tool_input") or {}
sub = (ti.get("subagent_type") or "").lower()
if sub == "fork":
    sys.exit(0)  # forks inherit parent model by design
if ti.get("model"):
    sys.exit(0)
print(json.dumps({
    "systemMessage": (
        "dispatch-hygiene: this Agent call omits an explicit model and will "
        "inherit the session model. Standing rule: pick the model per lane "
        "(sonnet default, haiku for triage, fable/opus only as an explicit "
        "judgment-lane choice). Add model=... unless inheritance is truly intended."
    )
}))
PY
