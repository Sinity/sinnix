# Runtime Modes

## Batch Mode

Use when reproducibility and machine-ingestable logs are primary.

Traits:

- deterministic CLI invocation,
- easy to rerun in scripts,
- no UI dependency.

Supported agents:

- `codex exec` — full exec mode with `--ephemeral`, `--json`, `--output-schema`.
- `claude --print` — non-interactive one-shot mode.
- `gemini` — non-interactive mode.

## Kitty Mode

Use when you need live observability and manual interruption.

Traits:

- one tab/window per agent,
- remote launch through `kitty @ launch`,
- compatible with Hyprland workflow routing.

Hyprland tip:

- launch in separate Kitty OS windows (`--launch-type os-window`) and move windows to a dedicated workspace using your existing `hyprctl dispatch` patterns.
- this skill does not hardcode `hyprctl` behavior because workspace naming/layouts differ by setup.

## Agent-Specific Invocation

| Agent  | Batch command                                | Interactive command         |
| ------ | -------------------------------------------- | --------------------------- |
| codex  | `codex exec -C <dir> [--model M] - < prompt` | Same, launched in Kitty tab |
| claude | `claude --print -p "$(cat prompt)"`          | `claude` in Kitty tab       |
| gemini | `gemini < prompt`                            | `gemini` in Kitty tab       |

## Model Selection (Codex)

- Spark lane: `--model gpt-5.3-codex-spark`
- Higher-depth lane: switch `--model` to a larger Codex model when synthesis quality dominates latency.
- Use profiles: `codex exec --profile spark_xhigh` for pre-configured model+effort combos.

## Decision Table

1. Need explicit model control? → Use `codex exec` workflow.
2. Need strict machine output contracts (`--output-schema`)? → Prefer `codex exec`.
3. Need fast iterative collaboration in one thread? → Use in-session subagents.
4. Need live observability and manual steering? → Use Kitty mode.
5. Need unattended repeatable run with stable artifacts? → Use batch mode.
