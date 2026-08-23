---
name: agent-orchestration
description: Coordinate AgentCTL-managed coding workspaces and attested agents, while preserving semantic work partitioning, prompt design, independent review, and operator-visible terminal recipes.
---

# Agent Orchestration

AgentCTL is the sole lifecycle authority for registered workspaces and agent jobs. Use the `agent-control` MCP routes when available; otherwise use `agentctl`. Never create a second manifest, PID registry, process tree, terminal ledger, batch controller, or local cancellation path.

Read [`references/batch-and-worktree-execution.md`](references/batch-and-worktree-execution.md) before multi-agent work. It covers semantic partitioning, write ownership, commit discipline, verification, and delivery.

## AgentCTL workflow

Create or adopt each worktree through AgentCTL, then start one explicit agent job for it:

```bash
agentctl workspace create <project> <lane> --branch feature/<lane>
agentctl agent --project <project> --checkout <checkout-id> \
  --prompt-file <prompt-file> --backend codex --model gpt-5.6-terra --effort high
agentctl job wait <job-id>
agentctl job result <job-id>
```

Use the returned `job_id` for `get`, `logs`, `result`, `wait`, and `cancel`. For a batch, submit one job per prepared prompt and retain only those AgentCTL IDs in the coordinator's report. AgentCTL reuses the same IDs across listing, reconciliation, logs, results, and cancellation. Resume work by starting a new attested job against the registered workspace with a follow-up prompt.

Use `workspace checkpoint` before recovery, `stack`/`restack` for dependent work, `publish`/`land`/`finish` for reviewed work, and `dispose` for a clean no-PR verification workspace. Worktree agents commit every verified logical chunk.

## Dispatch rules

- State the isolation model and file ownership before dispatch.
- Set backend, model, and effort explicitly. Codex coordinators use `gpt-5.6-luna` at high reasoning; unattended workers use `gpt-5.6-terra` at high reasoning unless the operator chooses otherwise.
- Require focused real-route verification and an anti-vacuity statement from every worker. Independently review meaningful diffs.
- Keep commands foreground in each worker turn. Do not launch a background command and wait across turns.
- `scripts/build_plan_batch_prompts.py` remains a prompt-construction helper. `scripts/probe_agent_runtime.sh` remains a direct vendor availability probe for paid or quota-sensitive dispatches. The private `scripts/run_agent_prompt.sh` is Sinnixd's backend adapter, not a user API.

## Visible terminal work

Use `desktop-control-plane` and `sinnix-kitty-control` when an operator needs a visible, interruptible terminal. The terminal is UI only. Start, inspect, and cancel attested work through AgentCTL, never by Kitty window or PID.
