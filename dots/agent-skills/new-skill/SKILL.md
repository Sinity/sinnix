---
name: new-skill
description: Create a new shared AI skill with proper structure and frontmatter
triggers:
  - "create skill"
  - "add skill"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
argument-hint: "<skill-name> [description]"
---

# Create New Skill

Help create a new shared skill (usable by both Claude and Codex) with proper structure.

**Input**: $ARGUMENTS

---

## Process

```
SEQUENTIAL:
  → parse skill name from input
  → determine scope: shared global (~/.config/claude/skills and ~/.codex/skills) or project-local (.claude/skills/)
  → gather requirements via questions if needed
  → create directory structure
  → write SKILL.md with frontmatter
  → add supporting files if needed
  → explain usage
```

---

## Skill Structure

```
skills/
└── <skill-name>/
    ├── SKILL.md           # Main skill file (required)
    ├── reference.md       # Supporting docs (optional)
    ├── templates/         # Template files (optional)
    └── scripts/           # Helper scripts (optional)
```

---

## SKILL.md Template

```yaml
---
name: <skill-name>
description: <when the assistant should auto-invoke this skill>
triggers:                    # Optional: keywords for auto-detection
  - "keyword one"
  - "keyword two"
allowed-tools:               # Optional: restrict available tools
  - Read
  - Write
  - Bash
argument-hint: "<arg1> [arg2]"  # Shown in skill help
context: fork                # Optional: run in isolated subagent
model: sonnet                # Optional: specific model
---

# Skill Title

Description of what this skill does.

**Input**: $ARGUMENTS

---

## Workflow

[Steps the skill follows]

---

## Output

[Expected output format]
```

---

## Frontmatter Options

| Field                      | Purpose                   | Example                            |
| -------------------------- | ------------------------- | ---------------------------------- |
| `name`                     | Skill identifier          | `deploy`                           |
| `description`              | When to auto-invoke       | `Deploy application to production` |
| `triggers`                 | Keywords for matching     | `["deploy", "ship it"]`            |
| `allowed-tools`            | Tool whitelist            | `["Bash", "Read"]`                 |
| `disallowed-tools`         | Tool blacklist            | `["Write"]`                        |
| `argument-hint`            | Usage hint                | `<environment> [--dry-run]`        |
| `context`                  | Execution context         | `fork` (isolated) or omit (main)   |
| `model`                    | Model override            | `haiku`, `sonnet`, `opus`          |
| `user-invocable`           | Can user invoke directly? | `false` (auto-only)                |
| `disable-model-invocation` | Prevent auto-invoke?      | `true` (user only)                 |

---

## Scope Decision

```
MATCH scope_need:
  | personal workflow      → ~/.config/claude/skills/ (shared with ~/.codex/skills/)
  | project-specific       → .claude/skills/
  | shareable package      → plugin with skills/
```

---

## Examples

**Simple skill (user-invoked only)**:

```yaml
---
name: format
description: Format code files
disable-model-invocation: true
argument-hint: "<file-pattern>"
---
```

**Auto-invoked skill**:

```yaml
---
name: explain-error
description: Explain error messages and suggest fixes
triggers:
  - "error"
  - "exception"
  - "failed"
---
```

**Isolated execution skill**:

```yaml
---
name: risky-operation
description: Run potentially dangerous operations in isolation
context: fork
allowed-tools: ["Bash"]
---
```

---

## Begin

1. Parse the skill name: `$0`
2. Ask clarifying questions if description unclear
3. Determine appropriate scope
4. Create skill with proper structure
5. Explain invocation: trigger by name or matching request text
