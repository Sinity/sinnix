#!/usr/bin/env bash
# Agent calls require an explicit model; forks inherit it. Model selection
# belongs to the orchestrate skill. Echo the requested model on allowed calls.
set -euo pipefail
# Pass code with -c so stdin remains available for the hook payload.
PY_SCRIPT=$(
  cat <<'PY'
import json
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ti = payload.get("tool_input") or {}

sub = (ti.get("subagent_type") or "").lower()
model = ti.get("model")
name = ti.get("name")

if sub == "fork":
    sys.exit(0)

if model:
    label = sub or "general-purpose"
    who = f" (teammate name='{name}')" if name else ""
    print(json.dumps({
        "systemMessage": (
            f"dispatch-hygiene: Agent dispatch subagent_type='{label}'{who} "
            f"model='{model}'."
        )
    }))
    sys.exit(0)

label = sub or "general-purpose"
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            f"dispatch-hygiene: Agent dispatch to '{label}' requires an explicit model. "
            "Choose it through the orchestrate skill and pass model in the tool call. "
            "Forks inherit their model."
        ),
    }
}))
PY
)
python3 -c "$PY_SCRIPT"
