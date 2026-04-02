---
name: meta
description: Meta-level introspection - analyze session, improve setup, persist learnings
---

# Meta-Level Introspection

Shift to meta-level: analyze this session's patterns, improve the setup, persist learnings.

**Arguments**: $ARGUMENTS

---

## Capabilities

### Analyze (default)

Review current session for friction, successes, and gaps. Propose concrete improvements.

### Improve

Make specific changes to CLAUDE.md, skills, hooks, or settings. Show diff, get approval, apply.

### Audit

Inventory all config files. Find: orphaned skills, outdated info, conflicts, misplaced content.

### Remember `<thing>`

Quick path to CLAUDE.md. Infer scope (global vs project) from context, or ask. Show diff, apply.

---

## Key Concepts

**CLAUDE.md vs Skills**

```
CLAUDE.md = eager (always loaded, costs tokens every session)
Skills    = lazy (loaded on demand)
```

Rule: If it's static knowledge → CLAUDE.md. If it's a workflow → skill.

**Subagents**

- Don't inherit conversation history
- Use when: different model, tool restrictions, or isolation needed
- Personas should be skills (need conversation context), not agents

**What goes where**
| Content | Location |
|---------|----------|
| Behavioral rules | Global CLAUDE.md |
| Cross-project patterns | `~/.claude/{world-model,operational}/` |
| Project-specific | Project CLAUDE.md or `.claude/{modules,development,reference}/` |
| Interactive workflows | `skills/` |
| Isolated/different-model tasks | `agents/` |
| Preserved but unused | `archive/` |

---

## Config Layout

### Global `~/.claude/`

```
CLAUDE.md                 # Core behavioral contract
├── @includes/...         # Modular pieces (use _index.md as manifest)
settings.json             # Permissions
skills/*/SKILL.md         # Lazy-loaded workflows
agents/*.md               # Subagent definitions
archive/{skills,includes} # Preserved, not loaded
```

### Project `.claude/`

```
CLAUDE.md                 # Project patterns (loaded when in dir)
.claude/
├── includes/             # Modular project docs (_index.md pattern)
├── settings.json         # Project permissions
└── scratch/              # Working notes (pin via @path in CLAUDE.md)
```

### Include Pattern

- `@path/to/file.md` transcludes content
- `_index.md` in folder imports siblings — comment out to disable
- Max 5 recursive hops
- Not evaluated inside code blocks

---

## Project CLAUDE.md Structure

```markdown
# Project Name

> Brief: what this is, when to update

## Quick Reference

[Commands, key paths]

## Patterns (DO/DON'T)

[With code examples]

## Troubleshooting

[Error → fix format]

## Pinned Notes

@.claude/scratch/topic.md
```

**Heuristic**: If you've explained something twice, it should be documented.

---

## Session Log Access

Session logs are stored as JSONL files at `~/.claude/projects/<project-path>/`.

### Listing Sessions

```bash
# Recent sessions for a project
ls -lt ~/.claude/projects/-realm-project-sinex/*.jsonl | head -10

# Project paths use dash-delimited absolute paths
# /realm/project/sinex → -realm-project-sinex
```

### Extracting User Messages

```bash
# Get genuine conversational prompts (< 400 chars, not pasted plans)
jq -c 'select(.type=="user")' session.jsonl | while read -r line; do
  content=$(echo "$line" | jq -r '.message.content | if type == "array" then .[0] | select(.type=="text") | .text else . end')
  len=${#content}
  if [ "$len" -gt 5 ] && [ "$len" -lt 400 ]; then
    case "$content" in
      "null"|"[Request"*|"<local"*|"<command"*|"Implement the following plan"*) ;;
      *) echo "$content" ;;
    esac
  fi
done
```

### Key Observations

- User messages have `.type == "user"` and content in `.message.content`
- Content is either a string or array of `{type: "text", text: "..."}` objects
- Pasted plans appear as single large text blocks (> 500 chars typically)
- System commands (`/clear`, etc.) appear as `<command-name>` prefixed entries
- Tool interruptions appear as `[Request interrupted by user for tool use]`

---

## Applying This

When doing meta work:

1. This skill gives you the architectural understanding
2. Use any capability above based on what's needed
3. Ask for steering if unclear ("should I analyze first or go straight to changes?")
4. Propose concrete changes with diffs before applying
