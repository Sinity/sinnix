# Clodex

`claude-clodex` runs the standard Sinnix Claude Code harness through Clodex's local selective proxy. It retains the full MCP profile, managed hooks, `CLAUDE.md`, scratch placement, and `agent.slice` containment. It uses the operator's ChatGPT or Codex subscription through device-code OAuth. No OpenAI API key is configured or required.

In proxy mode, native Claude model requests pass through to Anthropic unchanged. Only a Clodex model selected by alias is routed to OpenAI. This permits a session to switch between the two providers with `/model`.

## First-time setup

Run the following from a terminal. The device-code flow opens a browser authorization page. The resulting credential is stored by the managed local credential helper, encrypted to the persistent machine SSH identity. Later launches and refreshes are silent: no Secret Service or keyring dialog is involved. The Clodex configuration and non-secret recovery metadata live in `~/.clodex`, which is persisted by Sinnix.

```bash
clodex providers auth openai
clodex patch
systemctl --user start sinnix-clodex
```

The service declaration owns the `sol`, `terra`, and `luna` aliases. It reconciles them with `clodex models --alias` on every start, including removal of undeclared aliases, so manual alias registration is not part of setup. `clodex patch` is an explicit repair operation: the service checks its structured patch manifest and refuses readiness when the Claude Code version or patched bytes no longer match. It never rewrites the CLI during session startup.

## Daily use

Start a bridged full-profile session with:

```bash
claude-clodex
```

Select `/model sol`, `/model terra`, or `/model luna`. Select a native Claude model normally when it is preferable. The launcher always uses Clodex proxy mode. It deliberately does not set `ANTHROPIC_BASE_URL`, so Claude Code keeps its own Anthropic authentication and its normal provider routing remains available.

The `clodex` command is the managed Clodex CLI. It bootstraps the pinned runtime under `~/.local/state/clodex` and runs in the same agent resource class as the other agent CLIs. Use it for provider status, inspecting aliases with `clodex models --json`, and explicit repair with `clodex patch`. `sinnix-clodex.service` owns the long-running local proxy and starts automatically after later logins. The service has a condition on the OAuth provider registry, so its first start after authorization is explicit. Do not start a second `clodex server` manually for this workflow.

Routed accounting is published by the ops reducer from Clodex's bounded `~/.clodex/logs/inference-requests.jsonl` response-usage records. It reports aggregate request and token counters with source freshness; missing accounting is unavailable, never zero. Request bodies, credentials, and raw logs are not copied into reducer state.

Orchestrated lanes use the AgentCTL Codex backend directly, for example `agentctl batch start sinnix <bead> --backend codex --model gpt-5.6-terra --effort high`. Clodex is a Claude Code subscription bridge, not a second job scheduler.

## Operating limits

Clodex is a third-party compatibility layer. Claude Code's displayed spend is not authoritative for routed models, and ChatGPT/Codex OAuth has different cache behavior from a native Codex session. Prefer native Codex for autonomous work where the OpenAI Responses state lifecycle is important. Treat a failed re-patch after a Claude Code update as a compatibility issue: use native Claude or Codex until a compatible Clodex release is available.
