## Thinking in Markdown

Externalize reasoning to scratch files. Write liberally - context is expensive, files are cheap.

### When to Create Scratch Files

- **Always**: Non-trivial analysis, multi-step debugging, architectural decisions
- **Proactively**: Anything you figure out that took >1 tool call to discover
- **Especially**: Cross-session work, context-compaction-spanning tasks
- **Bootstrap when missing**: If a project lacks `.agent/scratch/`, create it early for any non-trivial work and ensure the project `.gitignore` ignores it before you start accumulating notes

### File Locations

| Scope                | Location                           | Use                                |
| -------------------- | ---------------------------------- | ---------------------------------- |
| Global/cross-project | `~/.claude/scratch/NNN-<topic>.md` | System-wide learnings, config work |
| Project-specific     | `.agent/scratch/NNN-<topic>.md`    | Project analysis, debugging notes  |

Project hygiene:

- Project-local scratch space should exist by default for active repos that receive agent-driven analysis
- If `.agent/scratch/` is absent, create it and add a matching `.gitignore` entry as part of the first substantial analysis pass
- **Never use `.claude/` for per-project auxiliary content.** Claude Code treats `.claude/` as a protected path and prompts for permission on every write. `.agent/` is the project-local convention; `.claude/` is reserved only for files Claude Code natively reads (`settings.local.json`, `commands/`, `agents/`, `skills/` if any).

### File Structure

```yaml
---
created: "ISO timestamp"
purpose: "brief description"
status: "active | complete | abandoned"
project: "sinex | polylogue | etc"  # if project-specific
---

# Topic

## Context
[what prompted this]

## Findings
[discoveries, analysis]

## Outcome
[results, decisions made]
```

### Proactive Usage

```
MATCH situation:
  | debugging session found root cause  → write scratch note
  | explored unfamiliar code area       → document what you learned
  | made non-obvious decision           → capture rationale
  | user asked "how does X work"        → write explanation, then summarize to user
```

When referring user to a scratch file, **always summarize the key points** in your response - don't just point at the file.

### Lifecycle

1. **Create liberally** - low cost, high value for future sessions
2. **Update as you go** - append findings during work
3. **Archive when complete**: `mv NNN-*.md archive/`
4. **Pin in CLAUDE.md** if ongoing relevance

### Pinning in Project CLAUDE.md

Projects can maintain a "Pinned Notes" section that **transcludes** scratch files using `@path` syntax:

```markdown
## Pinned Notes

@.agent/scratch/003-replay-bug-hunt.md
@.agent/scratch/007-schema-v5-migration.md
```

**Key behaviors:**

- `@` transcludes file content into CLAUDE.md at session startup
- Works with project-relative (`.agent/scratch/...`) and absolute (`@~/.claude/scratch/...`) paths
- Max 5 hops of recursive imports
- NOT evaluated inside code blocks - must be bare `@path` on its own line
- Run `/memory` to see what files are loaded
