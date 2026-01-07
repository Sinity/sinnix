# Shared AI Assets

This directory is the canonical home for AI-facing configuration that should stay
consistent across tools (Codex CLI, Claude, OpenCode, VS Code, Zed).

Layout:
- instructions/: Core agent rules and repo guidance.
- prompts/: Reusable prompt snippets.
- agents/: Subagent prompt templates.

Notes:
- `AGENTS.md` is the canonical instruction set; `CLAUDE.md` is a compatibility symlink.
- `instructions/base.md` and `instructions/task-tracking.md` contain expanded references.
- Use `ai` to list, show, or launch prompts and agents from the CLI.
- Keep prompts tool-agnostic and avoid vendor-specific syntax.
