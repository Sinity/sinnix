# Agent hook parity

This matrix records the current boundary between Claude Code and Codex hooks. It is reviewed against the generated Codex file at each configuration change, including the configured primary Polylogue hooks spool shared by every writer.

| Capability                 | Claude Code | Codex    | Evidence and action                                                                                                                      |
| -------------------------- | ----------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Session start and resume   | Enforced    | Enforced | Both clients run configured recall and Polylogue session capture.                                                                        |
| User prompt capture        | Enforced    | Enforced | Both clients send `UserPromptSubmit` to Polylogue.                                                                                       |
| Pre-compaction handoff     | Enforced    | Enforced | Both clients run `sinnix-context-handoff`.                                                                                               |
| Tool-use evidence          | Enforced    | Enforced | Both clients send tool events to Polylogue.                                                                                              |
| Stop capture               | Enforced    | Enforced | Both clients capture the stop event through Polylogue.                                                                                   |
| Agent model dispatch guard | Enforced    | Manual   | Claude has the structured `Agent` matcher and `pretooluse-agent-model.sh`; Codex applies the explicit-model contract at AgentCTL launch. |
| Destructive Bash guard     | Enforced    | Manual   | Claude has the structured `Bash` matcher and `pretooluse-bash.sh`; Codex follows the shared Git protocol.                                |

The generated Codex configuration is the authority for Codex-supported rows. This document is a parity record, not a second hook registry.
