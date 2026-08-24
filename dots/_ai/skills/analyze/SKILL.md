---
name: analyze
description: Interactive codebase analysis with user steering (survey → narrate → synthesize)
---

# Interactive Code Analysis

Step-by-step codebase analysis with user steering. Unlike an autonomous
parallel exploration coordinated through `orchestrate`, this pauses for input
between phases.

Persist the phase state in a project-local `.agent/scratch/` analysis ledger.
The ledger is the resume handle after compaction. It records the target,
source survey, selected narration items, evidence paths, open questions,
findings, and the current phase. Do not create a second process launcher or
duplicate the shared agent-definition and receipt contracts from
`orchestrate` and `agent-runtime`.

**Target**: $ARGUMENTS

---

## Workflow

```
survey → >>> user input → narrate → >>> user input → synthesize → >>> (write|fix|continue)
```

At the start of each phase, read the existing ledger if present and append a
phase transition with the exact files and commands used. If compaction or an
interruption occurs, resume from the last completed transition instead of
restarting the survey. Use explicit global agent definitions and model/effort
choices for any delegated narration lane.

---

## Phase 1: Survey

**Goal**: List all items at current level without deep-diving.

```
FOR EACH item IN target:
  → name, path, size (LOC)
  → brief purpose (from docs/structure)
  → concern: High | Medium | Low
```

**Concern indicators**:

- **High**: >500 LOC, many deps, complex error handling, concurrent/distributed, macros
- **Medium**: moderate size, some complexity, non-trivial logic
- **Low**: small, straightforward, well-tested, stable

**Output**:

```markdown
## Survey: [target]

| Item | LOC | Purpose | Concern |
| ---- | --- | ------- | ------- |

**Recommended focus**: [highest-concern items]
```

```
ECHO(>>> Which item(s) to narrate? "all high" | "skip to synthesis" | specific selection)
```

---

## Phase 2: Narrate

**Goal**: Line-by-line verbalization of selected items.

```
FOR EACH selected_item:
  → read file
  → walk through systematically:
      - what each struct/function does
      - expected vs actual behavior
      - cross-reference checks (do related functions match?)
  → call out issues with categories:
      🚨 [Critical] file:line - description
      🏗️ [Structural] file:line - description
      📝 [Style] file:line - description
      ⚡ [Algorithmic] file:line - description
      🔧 [Debt] file:line - description
  → note non-issues that looked suspicious but are fine
```

```
ECHO(>>> Found N issues. Continue to more files? | Go deeper? | Move to synthesis?)
```

---

## Phase 3: Synthesize

**Goal**: Cross-reference and prioritize findings.

```
SEQUENTIAL:
  → collect all issues
  → check: do related components have same problems?
  → prioritize by:
      severity: data_integrity > logic_errors > code_smells
      scope: widespread > isolated
      fixability: clear_fix > needs_discussion
```

**Output**:

```markdown
## Synthesis

### High Priority (fix now)

1. [Issue] - [location] - [why urgent]

### Medium Priority (fix soon)

...

### Low Priority (tech debt)

...

### Patterns Observed

- [recurring patterns]

### Cross-Reference Checks

- [x] checked: [what was verified consistent]
- [!] inconsistent: [what doesn't match]
```

```
ECHO(>>> Write to file? | Start fixing? | Analyze more?)
```

---

## User Steering Commands

At any point:

- **"focus on X"** → narrow to specific area
- **"skip X"** → exclude from analysis
- **"go deeper on X"** → more detailed narration
- **"check X vs Y"** → cross-reference two things
- **"write findings"** → persist to markdown
- **"fix issue N"** → switch to implementation

---

## Comparison: interactive analysis vs orchestrated analysis

| Aspect       | analyze skill                    | orchestrated lanes     |
| ------------ | -------------------------------- | ---------------------- |
| Execution    | Interactive, pausable            | Autonomous, parallel   |
| User input   | After each phase                 | Only at start          |
| Best for     | Learning, targeted investigation | Broad coverage         |
| Context cost | Lower (you steer)                | Higher (full autonomy) |

---

## Begin

Starting Phase 1: Survey of **$ARGUMENTS**
