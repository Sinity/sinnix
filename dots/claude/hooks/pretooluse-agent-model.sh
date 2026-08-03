#!/usr/bin/env bash
# PreToolUse hook (matcher: Agent) — enforce explicit model on subagent
# dispatches. Policy (global CLAUDE.md, "Claude Code Dispatch Doctrine"):
#   - fork subagents: exempt (they inherit context+model by design)
#   - named agent types (custom defs / built-ins like Explore, Plan,
#     claude-code-guide): the definition may carry the model -> soft warn only
#   - bespoke-prompt types (general-purpose, claude, or no subagent_type):
#     HARD DENY without an explicit model. These were 473/504 of measured
#     dispatches and the entire model-inheritance leak.
set -euo pipefail
python3 - <<'PY'
import json, sys
try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ti = payload.get("tool_input") or {}
sub = (ti.get("subagent_type") or "").lower()
if sub == "fork" or ti.get("model"):
    sys.exit(0)
bespoke = sub in ("", "general-purpose", "claude", "default")
if bespoke:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "dispatch-hygiene: bespoke-prompt Agent dispatches MUST carry an "
                "explicit model (this is enforced, not advisory). Re-dispatch with "
                "model=sonnet (implementation), model=haiku (triage-grade), or "
                "model=opus/fable only as a deliberate judgment-lane choice. "
                "Forks and named agent definitions are exempt."
            ),
        }
    }))
    sys.exit(0)
print(json.dumps({
    "systemMessage": (
        f"dispatch-hygiene: Agent call to '{sub}' omits model; the agent "
        "definition's frontmatter model applies if declared, otherwise this "
        "inherits the session model. Prefer explicit model per lane."
    )
}))
PY
