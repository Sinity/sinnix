---
name: agent-orchestration
description: >
  Orchestrate AI coding agents through direct local runtimes, native background
  sessions, Codex Cloud, or visible Kitty terminals. Use when coordinating
  multiple agent tasks, preserving task handles and logs, or choosing an
  unattended versus operator-visible execution lane.
metadata:
  short-description: Local, cloud, and terminal agent orchestration
---

# Agent Orchestration

Prefer native non-interactive runtimes for unattended work. Use Kitty only when
an operator needs a visible, interruptible prompt run. Read
[`references/runtime-modes.md`](references/runtime-modes.md) before launching;
it contains the verified commands, auth rules, and mode constraints. For
multi-agent fanout — worktree discipline, write-scope separation, pre-flight
and post-merge checklists, cross-item batching shapes, and the Codex model
contract — read
[`references/batch-and-worktree-execution.md`](references/batch-and-worktree-execution.md).

## Workflow

1. Choose direct local exec, a native background agent, Codex Cloud, or Kitty.
2. For Codex, use `gpt-5.6-terra` with high reasoning for unattended execution
   lanes. Use `gpt-5.6-luna` with high reasoning for the coordinating interactive
   session unless the operator selects another tier. Never inherit or guess a
   stale model default; inspect the launch receipt.
3. Set the working directory explicitly and preserve the returned session/task
   handle plus output artifacts.
4. Set model and effort explicitly when the lane supports them.
5. Use bounded concurrency for prompt batches; do not start unbounded workers.
6. Make each worker verify its own behavior. Require focused real-route tests,
   exact-path static checks, and a broader affected-area check when the change
   crosses modules or contracts. Resource containment exists to make this
   affordable; do not export all verification cost to the coordinator.
7. Require an anti-vacuity statement in implementation prompts: the worker must
   say what production dependency the test enters and what implementation
   mutation/removal makes it fail. Reject toy replicas, test-only validators,
   self-authored registries, and mocks that merely surround themselves.
8. Separate implementation from semantic certification when risk warrants. A
   green self-authored harness is evidence, not independent review.
9. Inspect results and diffs independently before applying or merging agent
   work. Worker verification is necessary, not sufficient.

## MCP Control Plane

When an MCP-capable client is available, prefer `agent-control` over direct
shell invocation. It exposes only `start_agent_job`, `list_agent_jobs`,
`agent_job_status`, `read_agent_job_output`, and `interrupt_agent_job`.

For a local operator CLI, use the same lifecycle through AgentCTL:

```bash
agentctl agent --project <project-id> --checkout <checkout-id> \
  --prompt-file <prompt-file> --backend <backend> --model <model> --effort high
agentctl job wait <job-id>
agentctl job result <job-id>
agentctl job cancel <job-id>
```

- Start work with an explicit backend, absolute workdir, bounded prompt, model,
  and reasoning effort where applicable.
- Persist and use only the returned `job_id`; do not control jobs by PID,
  process title, terminal window, or arbitrary artifact path.
- Use a second native job for independent semantic certification when the
  implementation has meaningful risk.
- The MCP adapter starts the existing attested runner asynchronously. It is the
  preferred agent-facing interface; the shell helpers below remain the operator
  and implementation layer.

## Helpers

- AgentCTL owns job lifecycle. Use its CLI or the MCP control plane for start,
  status, output, wait, and cancellation.
- `scripts/run_agent_prompt.sh` and `run_agent_prompt_job.py` are the private
  native backend translation layer for Sinnixd's typed attested-agent job. Do
  not use them as a second lifecycle surface.
- `scripts/agent_job_control.sh` remains a private compatibility bridge for
  the ops reducer until that caller consumes AgentCTL's job protocol.
- `scripts/launch_agent_tabs.sh`, `launch_agent_tabs_status.py`, and
  `build_plan_batch_prompts.py` retain direct batch and Kitty launch support
  while AgentCTL has no batch scheduling contract.
- Use `desktop-control-plane` and `sinnix-kitty-control` for optional visible
  terminal UI control. That skill owns terminal discovery, input, capture, and
  waits.
- `scripts/probe_agent_runtime.sh` checks backend availability when a paid or
  quota-sensitive launch needs direct vendor evidence.

## Backend capabilities

The native backends are intentionally explicit in job manifests and runtime
probes:

| Backend     | Headless entrypoint    | Default model         | Notes                                                                   |
| ----------- | ---------------------- | --------------------- | ----------------------------------------------------------------------- |
| Grok        | `grok-sinnix --single` | `grok-4.5`            | OAuth login, vendor state under `~/.grok`                               |
| Antigravity | `agy-sinnix --print`   | `gemini-3.1-pro-high` | Google keyring/browser login, MCP at `~/.gemini/config/mcp_config.json` |

Grok and Antigravity retain their vendor-managed binaries. The Sinnix wrappers
add scope containment without allowing vendor updates to overwrite the managed
entrypoints. `~/.local/state/sinnix/agent-jobs` is persisted so job manifests,
prompts, logs, and final artifacts remain available for inspection after a
reboot. Antigravity uses the coding and orchestration MCP tiers without the
slow deep-evidence tier because its print mode blocks indefinitely while an MCP
is still starting. Use `probe_agent_runtime.sh --agent <backend> --probe-model`
before a paid or quota-sensitive batch when the serving account or model
availability is uncertain.

Use `desktop-control-plane` for browser, Hyprland, screenshot, and focus-safe
desktop control.

## Fast fixed-scope audit fanout (Codex Spark)

`gpt-5.3-codex-spark` is a real, fast, small-context-window Codex model
(`~/.codex/models-v1.json`, `default_reasoning_level: "high"`) suited to
launching many concurrent narrow-scope reviewers rather than one broad one —
e.g. one instance per file or small file cluster, each told to narrate
through the code before reporting. `launch_agent_tabs.sh --spark` sets the
model and defaults reasoning effort to `xhigh`; combine with:

- `--sandbox read-only` — sandbox-enforced read-only, not just a prompt
  instruction, for pure-audit fanout.
- `--no-agents-md` — auto-provisions and caches (refreshed whenever the real
  `~/.codex/config.toml` changes) a scratch `CODEX_HOME` under
  `$XDG_STATE_HOME/sinnix/agent-orchestration/codex-home-no-agents-md`, copying
  `auth.json`/`config.toml`/`models-v1.json` but never the global `AGENTS.md`
  environment-memory file — appropriate when the global file's content (other
  projects, host-specific doctrine) would just spend a small model's context
  budget on irrelevant text. Use plain `--codex-home <path>` instead for any
  other custom profile. Do not combine the two.
- `--skip-git-repo-check` when a target isn't its own repo checkout.
- `--max-retries <n>` (default 3) — resilience against the shared
  `sinnix-agent-npm-bootstrap` launcher's regenerate-then-exec race (every
  wrapped-CLI invocation rewrites `~/.local/state/<tool>/launch.sh` in place;
  a sibling process executing that file during the rewrite gets `ETXTBSY`
  ("Text file busy"), a launcher-plumbing failure with nothing to do with the
  task). Fixed at the source via atomic rename (`scripts/sinnix-agent-npm-bootstrap`)
  so this should be rare after a rebuild, but the retry stays as defense in
  depth — it only retries on a detected `Text file busy` marker in the log,
  never a genuine task failure, and preserves prior attempts as
  `<name>.log.attempt<N>`.
- `--parallel <n>` — `run_batch_agent`'s loop uses `wait -n` (refill-a-slot,
  not wait-for-the-whole-batch), so concurrency stays at `n` continuously;
  don't hand-roll a batch-of-n-with-barrier loop, it serializes on the
  slowest member of every batch for no reason. Pick `n` conservatively
  (~5-10) — the launcher race above scales with how many `codex` processes
  start within the same second, and each instance still needs real CPU/API
  throughput.

Prompt design for narrow fixed-scope reviewers: point at literal absolute
file paths (spark's own system prompt discourages open-ended exploration
like `rg --files`/`ls -R`, so an unscoped "explore the codebase" prompt
fights the model's own instincts — hand it exact paths instead). Ask it to
narrate through the code section by section before concluding anything
(CLAUDE.md: "line-by-line narration forces attention" — catches issues in
code that looks fine at a glance). Naming specific things to check for
(silent error swallowing, unwired validation, resource leaks on error
paths, unconstructed enum variants, duplicated config resolution) measurably
improves recall without a large prompt, but always add an explicit
instruction not to limit itself to that list — the list is a floor, not a
ceiling. See `references/runtime-modes.md` for the exact command shape and a
worked fanout example.
