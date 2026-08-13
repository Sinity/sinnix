#!/usr/bin/env bash
# PreToolUse hook (matcher: Agent) — enforce explicit model on subagent
# dispatches, and append a "dispatch_start" row to the fanout dispatch ledger
# for every Agent-tool call, before the deny/warn decision below. Both live in
# one hook because a second process cannot read the same stdin payload.
#
# Policy (global CLAUDE.md, "Claude Code Dispatch Doctrine"):
#   - fork subagents: exempt (they inherit context+model by design)
#   - EVERY other dispatch — named agent-definition types (review, lane,
#     triage, judge, Explore, Plan, claude-code-guide, ...), teammate spawns
#     (Agent calls carrying a `name`), and bespoke-prompt types
#     (general-purpose, claude, or no subagent_type) — HARD DENY without an
#     explicit `model` field at the call site. A named agent's own frontmatter
#     `model:` does not exempt the dispatch; the caller must pass model
#     explicitly, so every launch is auditable at the call site instead of
#     only in a definition file the caller may not have open.
#   - On ALLOW, emit a visible systemMessage confirming exactly which model
#     the dispatch used, so the operator has affirmative feedback (not just
#     an absence of a warning) for every launch, including from the
#     transcript/notification stream of concurrent sessions.
#
# Dispatch ledger: ~/.local/state/claude-code/dispatch-ledger.jsonl
# (append-only; a matching "dispatch_end" row is appended by the SubagentStop
# hook, subagentstop-dispatch-ledger.sh). Ledger writes are wrapped so a
# broken ledger can NEVER block or alter a dispatch decision.
#
# Reader recipes (jq), against ~/.local/state/claude-code/dispatch-ledger.jsonl:
#   dispatches by model:
#     jq -s 'map(select(.type=="dispatch_start")) | group_by(.model) | map({model:.[0].model, n:length})' <ledger>
#   dispatches by session:
#     jq -s 'map(select(.type=="dispatch_start")) | group_by(.session_id) | map({session_id:.[0].session_id, n:length})' <ledger>
#   inherited-model count:
#     jq -s '[.[] | select(.type=="dispatch_start" and .model=="inherited")] | length' <ledger>
set -euo pipefail
# NOTE: must NOT be `python3 - <<'PY' ... PY` — that form redirects the
# heredoc body onto python3's own stdin (it's how `python3 -` receives the
# script to run), consuming the hook payload before `json.load(sys.stdin)`
# ever sees it, so the whole hook silently no-ops while exiting 0. Building
# the script text via command substitution and passing it as a `-c` argument
# leaves the piped stdin intact for python to read.
PY_SCRIPT=$(
  cat <<'PY'
import datetime as _dt
import hashlib
import json
import os
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ti = payload.get("tool_input") or {}


def _write_ledger_start(payload: dict, ti: dict) -> None:
    # Best-effort dispatch-ledger row. MUST NEVER raise, print, or otherwise
    # perturb the PreToolUse decision protocol below.
    try:
        ledger = os.path.expanduser("~/.local/state/claude-code/dispatch-ledger.jsonl")
        os.makedirs(os.path.dirname(ledger), exist_ok=True)
        prompt = ti.get("prompt") or ""
        if not isinstance(prompt, str):
            prompt = json.dumps(prompt)
        row = {
            "type": "dispatch_start",
            "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "session_id": payload.get("session_id") or "unknown",
            "subagent_type": (ti.get("subagent_type") or "").lower() or None,
            "model": ti.get("model") or "inherited",
            "effort": ti.get("effort"),
            "isolation": ti.get("isolation"),
            "background": ti.get("run_in_background"),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8", "replace")).hexdigest(),
            "prompt_preview": prompt[:120],
        }
        with open(ledger, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


_write_ledger_start(payload, ti)

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
            f"dispatch-hygiene: confirmed — Agent dispatch subagent_type='{label}'{who} "
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
            f"dispatch-hygiene: Agent dispatch to '{label}' omits model. This is HARD "
            "enforced for every dispatch type as of 2026-08-11, not just bespoke-prompt "
            "ones — a named agent's own frontmatter model no longer exempts the call site. "
            "Re-dispatch with model=sonnet (implementation), model=haiku (triage-grade), or "
            "model=opus/fable as a deliberate judgment-lane choice. Only subagent_type=fork "
            "is exempt (inherits context+model by design)."
        ),
    }
}))
PY
)
python3 -c "$PY_SCRIPT"
