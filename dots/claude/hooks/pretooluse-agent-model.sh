#!/usr/bin/env bash
# Claude Agent and Codex spawn_agent calls need deliberate dispatch inputs.
# A hook can validate the request but cannot observe the effective child model.
set -euo pipefail
# Pass code with -c so stdin remains available for the hook payload.
PY_SCRIPT=$(
  cat <<'PY'
import json
import re
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"dispatch-hygiene: {reason}",
        }
    }))


def message(text: str) -> None:
    print(json.dumps({"systemMessage": f"dispatch-hygiene: {text}"}))


tool_name = payload.get("tool_name")
tool_input = payload.get("tool_input")

# Codex calls this hook only for its exact native spawn tool. Do not interpret
# any other local tool as a dispatch or interfere with resumes/follow-ups.
if tool_name == "spawn_agent":
    if not isinstance(tool_input, dict):
        deny("spawn_agent has no structured input.")
        sys.exit(0)

    fork_turns = tool_input.get("fork_turns")
    model = tool_input.get("model")
    effort = tool_input.get("reasoning_effort")
    agent_type = tool_input.get("agent_type")
    has_model = isinstance(model, str) and bool(model.strip())
    has_effort = isinstance(effort, str) and bool(effort.strip())

    if agent_type not in (None, "default"):
        deny(
            "spawn_agent named roles may replace requested model or effort; use the "
            "existing role runner or AgentCTL route instead of native overrides."
        )
        sys.exit(0)

    if fork_turns == "all":
        if has_model or has_effort:
            deny(
                "spawn_agent with fork_turns='all' inherits context and must not "
                "also request model or reasoning_effort."
            )
        else:
            message(
                "spawn_agent explicitly inherits parent context and model; the "
                "effective child model is not observed by this hook."
            )
        sys.exit(0)

    bounded = fork_turns == "none" or (
        isinstance(fork_turns, str) and re.fullmatch(r"[1-9][0-9]*", fork_turns)
    )
    if not bounded:
        deny(
            "fresh spawn_agent requires explicit bounded fork_turns='none' or a "
            "positive decimal string; use explicit fork_turns='all' only to inherit."
        )
        sys.exit(0)
    if not has_model:
        deny("fresh spawn_agent requires a non-empty explicit model.")
        sys.exit(0)
    if model.strip().lower() == "inherit":
        deny("fresh spawn_agent requires a selected model, not model='inherit'.")
        sys.exit(0)
    if not has_effort:
        deny("fresh spawn_agent requires an explicit reasoning_effort.")
        sys.exit(0)
    if effort not in {"low", "medium", "high", "xhigh", "max", "ultra"}:
        deny(
            "fresh spawn_agent reasoning_effort must be one of low, medium, high, "
            "xhigh, max, or ultra."
        )
        sys.exit(0)
    message(
        "fresh spawn_agent requested model and reasoning_effort with bounded "
        "context; effective child settings are not observed by this hook."
    )
    sys.exit(0)

# Claude's observed Agent payload exposes subagent_type and model in
# tool_input, but no effort selection. Leave every other tool untouched.
if tool_name != "Agent":
    sys.exit(0)
if not isinstance(tool_input, dict):
    sys.exit(0)

sub = (tool_input.get("subagent_type") or "").lower()
model = tool_input.get("model")
name = tool_input.get("name")
has_model = isinstance(model, str) and bool(model.strip())
label = sub or "general-purpose"
who = f" (teammate name='{name}')" if name else ""

if sub == "fork":
    if has_model:
        deny(
            "Claude Agent fork inherits its model and must not claim a model override; "
            "the effective child model is not observed by this hook."
        )
    else:
        message(
            f"Claude Agent fork to '{label}'{who} explicitly inherits its context and "
            "model; effective model and effort are not observed by this hook."
        )
    sys.exit(0)

if has_model:
    message(
        f"Claude Agent dispatch to '{label}'{who} requested model='{model}'; effective "
        "model and effort are not observed by this hook."
    )
    sys.exit(0)

deny(
    f"Claude Agent dispatch to '{label}' requires a non-empty explicit model. "
    "Effort is not present in this Agent payload and remains owned by its role or runner."
)
PY
)
python3 -c "$PY_SCRIPT"
