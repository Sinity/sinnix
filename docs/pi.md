# Pi

`pi` is the managed Pi coding-agent launcher for context experiments and interactive coding work. It runs in `agent.slice`, loads Sinnix's shared instructions and skills, and uses only Pi's native ChatGPT Plus/Pro Codex OAuth provider. It does not use `OPENAI_API_KEY` or an OpenAI Platform API key.

Run `pi`, then use `/login` and choose **ChatGPT Plus/Pro (Codex Subscription)**. Pi stores and refreshes its private OAuth credential, sessions, model catalog and settings under `~/.pi`; Sinnix persists that directory but does not render or inspect credential contents. Use `/logout` in Pi to revoke its saved credential.

Pi sessions are branchable JSONL files. Use `/tree`, `/fork`, and `/clone` for context-policy experiments. `pi --list-models` shows the subscription-backed models currently available to the installed Pi version and account.

Pi can also run an explicit AgentCTL ownership group with `--backend pi`. Pass a model ID listed by `pi --list-models`, for example:

```bash
agentctl batch start sinnix <bead-id> --backend pi --model gpt-5.5 --effort high
```

The AgentCTL adapter pins Pi to Codex OAuth, records Pi's JSON event stream in the task log, and extracts a JSON final answer for normal batch-result validation. Pi does not yet offer provider-enforced JSON Schema output, so the batch result validator remains the acceptance boundary.
