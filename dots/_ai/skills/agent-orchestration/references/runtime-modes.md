# Runtime Modes

## Contents

- [Choose a Lane](#choose-a-lane)
- [Direct Local Execution](#direct-local-execution)
- [Codex Cloud](#codex-cloud)
- [Prepared Prompt Batches](#prepared-prompt-batches)
- [Kitty Sessions](#kitty-sessions)

## Choose a Lane

| Need | Lane |
| --- | --- |
| Deterministic local run and log | Direct `codex exec` or Claude `--print` |
| Resumable unattended Claude work | Claude native `--background` |
| Hosted/offloaded repository work | Codex Cloud |
| Several prepared prompt files | `launch_agent_tabs.sh --mode batch` |
| Visible prompt run with process-level interruption | Kitty |

Keep Kitty out of unattended execution paths. Native runtimes have fewer focus
and window-management failure modes.

## Direct Local Execution

### Codex

Use `gpt-5.6-terra` with high reasoning for unattended execution. The
interactive coordinating default is `gpt-5.6-sol` with high reasoning. Set the
repository, model, and effort explicitly on every run and verify the launch
receipt reports the requested model:

```bash
codex exec -C <repo> \
  --model gpt-5.6-terra \
  -c 'model_reasoning_effort="high"' \
  - < <prompt-file>
```

Persist the session by omitting `--ephemeral`. Resume it from the repository so
Codex applies the expected current-directory filtering and instructions:

```bash
cd <repo>
codex exec resume <session-id> \
  --model gpt-5.6-terra \
  -c 'model_reasoning_effort="high"' \
  - < <follow-up-prompt-file>
```

Use `codex exec resume --last ...` only when the newest matching session is
unambiguous. Add `--json`, `--output-schema <file>`, or
`--output-last-message <file>` when a machine-readable or durable artifact is
required.

Execution prompts must require worker-owned verification: focused real-route
tests, exact-path static checks, and an affected-area check proportional to the
change. They must also name the anti-vacuity mutation that would make the test
fail. More RAM is a reason to verify concurrently under cgroup limits, not a
reason to accept narrow self-confirming tests.

### Claude

Sinnix manages Claude through `claude-full`. Run from the repository; Claude
has no `--workdir` option. Unset `ANTHROPIC_API_KEY` by default so the managed
CLI uses subscription authentication:

```bash
cd <repo>
env -u ANTHROPIC_API_KEY claude-full --print \
  --model <model> \
  --effort high \
  -p "$(cat <prompt-file>)"
```

Keep `ANTHROPIC_API_KEY` only when API-key billing is explicitly intended.

For resumable unattended work, use Claude's native background mode instead of
putting the process in a Kitty tab:

```bash
cd <repo>
env -u ANTHROPIC_API_KEY claude-full --background \
  --model <model> \
  --effort high \
  "$(cat <prompt-file>)"
```

Manage native background sessions through the bootstrap launcher that owns the
installed Claude runtime:

```bash
~/.local/state/claude-code/launch.sh agents --json
~/.local/state/claude-code/launch.sh logs <agent-id>
~/.local/state/claude-code/launch.sh stop <agent-id>
```

Save the returned agent ID; `logs` and `stop` require it.

## Codex Cloud

Submit a hosted task with an explicit environment. The command returns the task
ID used by every later operation:

```bash
codex cloud exec --env <env-id> --branch <branch> "<prompt>"
codex cloud list --env <env-id> --json
codex cloud status <task-id>
codex cloud diff <task-id>
codex cloud apply <task-id>
```

For best-of-N tasks, pass `--attempts <n>` to `exec`, then select an attempt
with `codex cloud diff --attempt <n> <task-id>` and
`codex cloud apply --attempt <n> <task-id>`. Inspect the diff before `apply`;
`apply` changes the current checkout.

The Cloud CLI does not select or report the serving model. Treat model identity
as unknown even when the local Codex default is explicit. Use Cloud for bounded
repository work whose acceptance boundary can be executed inside the checkout;
do not make it the sole authority for architecture or trust-boundary decisions.

For non-trivial Cloud work:

1. Name real production symbols, data paths, or existing test node IDs. Require
   zero-collection, missing-node, and corrupt-reference failures where a runner
   composes existing tests.
2. Include the adversarial ordering or fault that distinguishes the requested
   behavior from a favorable happy path. Assert the final externally visible
   system state, not only an intermediate artifact.
3. Explicitly forbid toy stores, substitute DDL, and reimplemented production
   algorithms when the task is test or verification infrastructure.
4. Prefer `--attempts 2` when two independent diffs are worth the extra run;
   otherwise schedule a separate semantic review.
5. Apply only in an isolated worktree, then audit against current source and the
   task contract before running focused checks. Never apply directly over a
   dirty canonical checkout.

## Prepared Prompt Batches

`launch_agent_tabs.sh` reads `<prompt-dir>/<name>.prompt` and writes per-task
logs and last-message artifacts under the output directory. Bound direct batch
concurrency with a positive integer:

```bash
scripts/launch_agent_tabs.sh \
  --agent codex \
  --mode batch \
  --parallel 4 \
  --model <model> \
  --reasoning-effort high \
  --workdir <repo> \
  --prompt-dir <prompt-dir> \
  --output-dir <output-dir> \
  task-a task-b task-c task-d
```

`--parallel` greater than one is valid only with `--mode batch`. Claude runs
through the helper unset `ANTHROPIC_API_KEY` unless
`--claude-api-key-auth` explicitly opts into API-key auth.

## Kitty Sessions

Use Kitty only when a human or coordinator needs a visible prompt run with
process-level interruption. `launch_agent_tabs.sh` still invokes the
non-interactive prompt runner; use `agent_instance_control.sh` or a manually
launched interactive agent when conversational mid-turn steering is required.
The launcher uses `kitty @ launch --keep-focus`, so dispatch does not take focus
from the operator. Route separate OS windows silently when isolation is useful:

```bash
scripts/launch_agent_tabs.sh \
  --agent codex \
  --mode kitty \
  --launch-type os-window \
  --workspace <workspace> \
  --model <model> \
  --reasoning-effort high \
  --workdir <repo> \
  --prompt-dir <prompt-dir> \
  --output-dir <output-dir> \
  task-a task-b
```

`--workspace` requires Kitty `os-window` mode and
`sinnix-hypr-control`. Do not use `--parallel` in Kitty mode — Kitty launches
are fire-and-forget, so N prompt names already run as N concurrent workers;
bound the fanout by how many prompts you pass.

For parallel worktree fanouts, three flags remove the mode's historical
drawbacks:

- `--persist-windows` keeps each window open after the runner exits (drops to
  an interactive shell in the task workdir with the exit code printed) and
  writes `<name>.exit` markers to the output dir.
- `--per-task-workdir-base <dir>` resolves each task's workdir as
  `<dir>/<prompt-name>` — one git worktree per lane; makes `--workdir`
  optional.
- `--job-prefix <p>` passes attested job identity (`--job-id <p><name>`,
  `--work-item <name>`) to the runner so `agent_job_control.sh` can
  list/interrupt lanes by ID.

Aggregate completion afterwards with
`launch_agent_tabs.sh --status --output-dir <output-dir>` (DONE / FAILED /
RUNNING per task, read from exit markers and logs; batch mode writes the same
markers). Caveat: workers launched in Kitty die with the Kitty instance; use
batch mode when survivability matters more than visibility.

```bash
scripts/launch_agent_tabs.sh \
  --agent codex \
  --mode kitty \
  --launch-type os-window \
  --workspace 6 \
  --persist-windows \
  --per-task-workdir-base /realm/worktrees \
  --job-prefix fanout- \
  --prompt-dir <prompt-dir> \
  --output-dir <output-dir> \
  lane-a lane-b lane-c
```
