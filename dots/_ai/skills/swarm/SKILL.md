---
name: swarm
description: Orchestrate parallel subagents to divide and conquer complex tasks
---

# Swarm Orchestration

Decompose complex tasks into parallelizable subtasks, launch appropriate subagents, collect and synthesize results.

**Task**: $ARGUMENTS

---

## Decision Framework

### Should You Swarm?

```
IF task decomposes into 3+ independent units
   AND parallelism provides real speedup
   AND synthesis of multiple perspectives adds value
THEN swarm
ELSE do it single-threaded
```

Don't swarm when: task is inherently sequential, or you'd spawn agents just to spawn them.

### Agent Selection

```
MATCH task_type:
  | needs_file_writes    → general-purpose
  | quick_search         → Explore
  | architecture_design  → Plan
  | code_review          → code-reviewer agents
  | mechanical_codegen   → boilerplate-scribe
  | deep_codebase_trace  → feature-dev:code-explorer
```

**Critical**: `Explore` and `Plan` agents CANNOT write files.

### Model Selection

```
MATCH complexity:
  | trivial (counting, grep, boilerplate)        → haiku
  | standard (surveys, reviews, most work)       → sonnet [DEFAULT]
  | high (security, race conditions, subtle bugs) → opus
```

### Thoroughness Scaling

```
quick:    1-3 agents, highest-impact targets only
medium:   4-6 agents, main areas covered
thorough: 7-12 agents, comprehensive coverage
```

---

## Preset Detection

```
MATCH keywords IN task:
  | "review", "PR", "check code"           → preset:review
  | "bug", "error", "debug", "broken"      → preset:bug-hunt
  | "refactor", "restructure", "migrate"   → preset:refactor
  | "implement", "build", "create"         → preset:implement
  | "understand", "explain", "how does"    → preset:explore
  | "audit", "security", "vulnerabilities" → preset:audit
  | "analyze", "deep review", "find bugs"  → preset:analyze
  | "fix all", "fix these", list of issues → preset:fix-all
  | _                                      → general protocol
```

---

## Presets

### preset:review

Multi-perspective code review.

```
PARALLEL launch:
  - code-reviewer      (style, best practices)
  - silent-failure-hunter (error handling gaps)
  - type-design-analyzer  (type safety issues)
  - IF thoroughness=thorough: test-analyzer

THEN SEQUENTIAL:
  - aggregate findings
  - deduplicate (multiple agents may flag same issue)
  - prioritize by severity
  - present unified report
```

### preset:bug-hunt

Debug investigation with hypothesis formation.

```
PHASE 1 - investigate (PARALLEL):
  - explore: "Find all code related to [error context]"
  - explore: "Trace execution path to this error"
  - general-purpose: "Search git history for recent changes"

PHASE 2 - synthesize (you do this):
  - combine findings
  - form root cause hypothesis
  - decide: can fix, need more info, or escalate

PHASE 3 - fix (IF requested, SEQUENTIAL):
  - implement fix
  - add regression test
  - run build/test
```

### preset:refactor

Safe parallel refactoring.

```
PHASE 1 - reconnaissance (SINGLE-THREADED):
  - map current architecture
  - identify refactoring units

PHASE 2 - plan (SINGLE-THREADED):
  - design approach
  - assign file boundaries (CRITICAL: no two agents touch same file)

PHASE 3 - execute (PARALLEL):
  FOR EACH independent_unit:
    - general-purpose agent with explicit file boundaries

PHASE 4 - integrate (SINGLE-THREADED):
  - check for conflicts
  - run unified build + tests
  - IF failures: fix or report
```

### preset:implement

Parallel feature development.

```
PHASE 1 - design (SINGLE-THREADED):
  - architecture decision
  - identify components: core logic, API/interface, tests

PHASE 2 - build (PARALLEL):
  FOR EACH component:
    - general-purpose agent

PHASE 3 - review (PARALLEL):
  - run preset:review on new code

PHASE 4 - iterate (SINGLE-THREADED):
  - fix issues from review
  - verify build/tests pass
```

### preset:explore

Multi-angle codebase understanding.

```
PARALLEL launch:
  - "Find entry points and main interfaces for [topic]"
  - "Trace data flow through [topic]"
  - "Find all dependencies and consumers of [topic]"
  - "Map architecture layers for [topic]"

THEN SINGLE-THREADED:
  - synthesize into coherent explanation
  - identify key files and functions
  - create mental model
```

### preset:audit

Security and quality scanning.

```
PARALLEL launch:
  - error handling issues (silent failures, swallowed exceptions)
  - type safety issues (unsafe casts, validation gaps)
  - secrets scan (hardcoded credentials, API keys)
  - injection vulnerabilities (SQL, XSS, command injection)
  - concurrency issues (race conditions, deadlocks)
  - tech debt markers (TODO, FIXME, HACK comments)

THEN SINGLE-THREADED:
  - categorize by severity and type
  - prioritize actionable items
  - generate remediation plan
```

### preset:analyze

Hierarchical code analysis (Survey → Narrate → Synthesize).

```
PHASE 0 - context (MANDATORY):
  - read parent-level survey if exists
  - identify targets from parent's concerns

PHASE 1 - survey (PARALLEL):
  FOR EACH target_component:
    - inventory structure (files, sizes, dependencies)
    - flag concerns (complexity, error patterns)
    - write results to survey markdown

PHASE 2 - triage (SINGLE-THREADED):
  - rank by concern: security > data_integrity > complexity
  - select narration targets based on thoroughness

PHASE 3 - narrate (PARALLEL):
  FOR EACH target_file:
    - read entire file
    - narrate section by section with finding categories:
        🚨 [Critical], 🏗️ [Structural], 📝 [Style], ⚡ [Algorithmic], 🔧 [Debt]
    - write narration to analysis markdown

PHASE 4 - synthesize (SINGLE-THREADED):
  - cross-reference findings
  - aggregate Critical + Structural to synthesis docs
  - identify next analysis targets
```

### preset:fix-all

Parallel issue resolution.

```
SETUP (SINGLE-THREADED):
  - parse list of issues
  - group by file/module (avoid conflicts)
  - assign one agent per group

EXECUTE (PARALLEL):
  FOR EACH issue_group:
    - general-purpose agent fixes all issues in group

INTEGRATE (SINGLE-THREADED):
  - run unified build + tests
  - report failures for manual attention
```

---

## General Protocol (No Preset Match)

```
PHASE 1 - analyze task:
  - identify parallelizable units
  - assess dependencies (what must be sequential?)
  - match subtasks to agent types

PHASE 2 - launch:
  - write SELF-CONTAINED prompts (agents have no conversation history)
  - include: specific paths, full context, expected output format
  - state clearly: RESEARCH vs IMPLEMENT

PHASE 3 - monitor:
  IF mode=background:
    - launch all with run_in_background: true
    - poll with TaskOutput (block: false)
  IF mode=supervised:
    - launch in batches
    - review between batches

PHASE 4 - integrate:
  - collect all outputs
  - check for conflicts
  - IF code_written: run build/test
  - synthesize results
```

---

## Subagent Prompting Rules

Every subagent prompt MUST be self-contained. They cannot see this conversation.

```
REQUIRED in every prompt:
  - specific file paths (absolute)
  - full context (what they need to know)
  - expected output format
  - explicit scope boundaries
  - RESEARCH vs IMPLEMENT clarity
```

---

## Output Format

```markdown
## Swarm Execution Summary

**Preset**: [preset or adaptive]
**Mode**: [background/supervised]
**Agents launched**: N

### Execution

| #   | Task | Agent Type | Model | Status |
| --- | ---- | ---------- | ----- | ------ |

### Results

[Key findings per agent]

### Synthesis

[Cross-agent patterns, unified conclusions]

### Next Steps

[Remaining work, recommended follow-up]
```

---

## Begin

1. Detect or use specified preset
2. Execute preset protocol (or general protocol)
3. Launch agents in PARALLEL where indicated (single message, multiple Task calls)
4. Complete SINGLE-THREADED phases yourself
5. Synthesize and report
