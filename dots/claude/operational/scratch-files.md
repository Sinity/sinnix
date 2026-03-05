## Thinking in Markdown

Externalize reasoning to scratch files. Write liberally - context is expensive, files are cheap.

### When to Create Scratch Files

- **Always**: Non-trivial analysis, multi-step debugging, architectural decisions
- **Proactively**: Anything you figure out that took >1 tool call to discover
- **Especially**: Cross-session work, context-compaction-spanning tasks

### File Locations

| Scope | Location | Use |
|-------|----------|-----|
| Global/cross-project | `~/.claude/scratch/NNN-<topic>.md` | System-wide learnings, config work |
| Project-specific | `.claude/scratch/NNN-<topic>.md` | Project analysis, debugging notes |

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

@.claude/scratch/003-replay-bug-hunt.md
@.claude/scratch/007-schema-v5-migration.md
```

**Key behaviors:**

- `@` transcludes file content into CLAUDE.md at session startup
- Works with project-relative (`.claude/scratch/...`) and absolute (`@~/.claude/scratch/...`) paths
- Max 5 hops of recursive imports
- NOT evaluated inside code blocks - must be bare `@path` on its own line
- Run `/memory` to see what files are loaded
