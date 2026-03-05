# Runtime Modes

## Batch Mode

Use when reproducibility and machine-ingestable logs are primary.

Traits:
- deterministic CLI invocation,
- easy to rerun in scripts,
- no UI dependency.

## Kitty Mode

Use when you need live observability and manual interruption.

Traits:
- one tab/window per agent,
- remote launch through `kitty @ launch`,
- compatible with Hyprland workflow routing.

Hyprland tip:
- launch in separate Kitty OS windows (`--launch-type os-window`) and move windows to a dedicated workspace using your existing `hyprctl dispatch` patterns.
- this skill does not hardcode `hyprctl` behavior because workspace naming/layouts differ by setup.

## Model Selection

- Spark lane: `--model gpt-5.3-codex-spark`
- Higher-depth lane: switch `--model` to a larger Codex model when synthesis quality dominates latency.
