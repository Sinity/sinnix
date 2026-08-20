# Clodex

`claude-clodex` runs the standard Sinnix Claude Code harness through Clodex's local selective proxy. It retains the full MCP profile, managed hooks, `CLAUDE.md`, scratch placement, and `agent.slice` containment. It uses the operator's ChatGPT or Codex subscription through device-code OAuth. No OpenAI API key is configured or required.

In proxy mode, native Claude model requests pass through to Anthropic unchanged. Only a Clodex model selected by alias is routed to OpenAI. This permits a session to switch between the two providers with `/model`.

## First-time setup

Run the following from a terminal. The device-code flow opens a browser authorization page. The resulting credential is stored by the managed local credential helper, encrypted to the persistent machine SSH identity. Later launches and refreshes are silent: no Secret Service or keyring dialog is involved. The Clodex configuration and non-secret recovery metadata live in `~/.clodex`, which is persisted by Sinnix.

```bash
clodex providers auth openai
clodex models --alias sol=clodex:openai-oauth:gpt-5.6-sol
clodex models --alias terra=clodex:openai-oauth:gpt-5.6-terra
clodex models --alias luna=clodex:openai-oauth:gpt-5.6-luna
clodex patch
systemctl --user start sinnix-clodex
```

Use `clodex models --list` to inspect the registered names. `clodex patch` makes the aliases first-class Claude Code models, reports their correct context windows, and permits them in Claude Code subagents. The patch is version-specific, so run `clodex patch` again after the Claude Code CLI updates.

## Daily use

Start a bridged full-profile session with:

```bash
claude-clodex
```

Select `/model sol`, `/model terra`, or `/model luna`. Select a native Claude model normally when it is preferable. The launcher always uses Clodex proxy mode. It deliberately does not set `ANTHROPIC_BASE_URL`, so Claude Code keeps its own Anthropic authentication and its normal provider routing remains available.

The `clodex` command is the managed Clodex CLI. It bootstraps the pinned runtime under `~/.local/state/clodex` and runs in the same agent resource class as the other agent CLIs. Use it for provider status, model aliases, and re-patching. `sinnix-clodex.service` owns the long-running local proxy and starts automatically after later logins. The service has a condition on the OAuth provider registry, so its first start after authorization is explicit. Do not start a second `clodex server` manually for this workflow.

## Operating limits

Clodex is a third-party compatibility layer. Claude Code's displayed spend is not authoritative for routed models, and ChatGPT/Codex OAuth has different cache behavior from a native Codex session. Prefer native Codex for autonomous work where the OpenAI Responses state lifecycle is important. Treat a failed re-patch after a Claude Code update as a compatibility issue: use native Claude or Codex until a compatible Clodex release is available.
