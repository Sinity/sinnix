# Agent hook parity

This matrix records the current boundary between Claude Code and Codex hooks. It is reviewed against the generated Codex file at each configuration change.

| Capability                         | Claude Code | Codex       | Evidence and action                                                                                                                                                                                                        |
| ---------------------------------- | ----------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Session start and resume           | Enforced    | Enforced    | Both clients run their configured session recall and Polylogue session capture.                                                                                                                                            |
| User prompt capture                | Enforced    | Enforced    | Both clients send `UserPromptSubmit` to the shared Polylogue hook.                                                                                                                                                           |
| Pre-compaction handoff             | Enforced    | Enforced    | Both clients run `sinnix-context-handoff`.                                                                                                                                                                                   |
| Tool-use evidence                  | Enforced    | Enforced    | Both clients send `PreToolUse` and `PostToolUse` to the shared Polylogue hooks.                                                                                                                                            |
| Stop cleanup and capture           | Enforced    | Enforced    | Both clients clean orphan processes and capture the stop event.                                                                                                                                                          |
| Agent model dispatch guard         | Enforced    | Manual      | Claude has a structured `Agent` matcher and `pretooluse-agent-model.sh`. No equivalent Codex subagent matcher is exposed in the generated hook schema. Apply the shared explicit-model launch contract manually for Codex. |
| Bash checkout and force-push guard | Enforced    | Manual      | Claude has a structured `Bash` matcher and `pretooluse-bash.sh`. Codex exposes generic tool evidence but no command-policy matcher. Use the shared Git protocol and Beads safety rules manually.                           |
| Subagent completion ledger         | Enforced    | Unsupported | Claude exposes `SubagentStop`; the current Codex hook schema has no equivalent completion event. Do not emulate it through terminal scraping.                                                                              |

The generated Codex configuration is the authority for Codex-supported rows. This document is a parity record, not a second hook registry.
