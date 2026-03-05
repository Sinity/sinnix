# Codex CLI Notes

Practical notes for orchestration based on `codex --help`, `codex exec --help`, and official Codex docs:
- Command-line options: <https://platform.openai.com/docs/codex/cli/command-line-options>
- Config and profiles: <https://platform.openai.com/docs/codex/cli/config>

## High-Value Flags
- `codex exec --json`: stream machine-readable events to stdout.
- `codex exec --output-last-message <file>`: deterministic final artifact capture.
- `codex exec --output-schema <file>`: enforce structured final output.
- `codex exec --ephemeral`: do not persist session files to disk.
- `codex exec -c model_reasoning_effort="xhigh"`: per-run reasoning override.

## Profiles
Define reusable modes in `~/.codex/config.toml` and select with `--profile`.
Example structure:
```toml
[profiles.spark_xhigh]
model = "gpt-5.3-codex-spark"
model_reasoning_effort = "xhigh"
```

## Operational Guidance
- For large fan-out runs, use `exec` + prompt files + per-agent logs.
- Prefer `--ephemeral` for disposable probing/benchmark runs.
- Use `--output-schema` for reducers/aggregation tasks to keep outputs parseable.
- In environments with custom wrappers, set `SINNIX_SKIP_AGENTS_RENDER=1` for probe commands to avoid wrapper side-effects.
