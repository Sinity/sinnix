---
name: enhance
description: Transform rough prompts into polished versions with optional execution
triggers:
  - "enhance this"
  - "improve prompt"
  - "make this better"
allowed-tools:
  - Read
  - Write
  - AskUserQuestion
  - Task
  - Glob
  - Skill
argument-hint: "<rough prompt or idea>"
---

# Prompt Enhancement

Transform rough input into well-crafted prompt, then optionally execute.

**Input**: $ARGUMENTS

---

## Modes

This skill has two variants based on invocation:

- `/enhance <prompt>` - Quick enhancement with auto-detected settings, immediate execution
- `/enhance --interactive <prompt>` - Interview-based enhancement with refinement loop

Default: Quick mode (most common use case)

---

## Quick Mode (Default)

### 1. Domain Detection

```
MATCH content:
  | programming terms, file refs, technical jargon → code
  | content creation, editing, style, audience     → writing
  | investigation, analysis, comparison            → research
  | strategy, steps, timeline                      → planning
  | ideation, brainstorming, design                → creative
  | _                                              → general
```

### 2. Mode Selection

```
MATCH detected:
  | short prompt (< 10 words)  → thorough
  | code domain                → code-focused
  | writing domain             → writing-focused
  | already structured         → minimal
  | _                          → balanced
```

### 3. Enhancement Techniques

**Minimal**: Fix ambiguity, clarify intent, remove confusion. Keep concise.

**Balanced**: Add context, define scope, include examples, add structure, specify output format.

**Thorough**: Edge cases, error handling, success criteria, deliverables, dependencies.

**Code-focused**: Language/framework/versions, input/output types, error handling, test scenarios.

**Writing-focused**: Audience, tone, structure, style examples.

### 4. Output & Execute

```
═══════════════════════════════════════════════════════════════
ENHANCED PROMPT:

[enhanced version]
═══════════════════════════════════════════════════════════════
```

Then execute the enhanced prompt immediately.

---

## Interactive Mode (--interactive)

### Phase 1: Analysis

- Identify domain
- Assess complexity and specificity
- Note implicit constraints

### Phase 2: Interview

Use AskUserQuestion to gather context (2-3 questions max):

**Question 1: Enhancement Mode**

- Auto (recommended), Minimal, Balanced, Thorough, Code-focused, Writing-focused

**Question 2: Context** (if gaps detected)

- Time constraints, Domain context, Target audience, Technical constraints

**Question 3: Clarifications** (if ambiguous)

- Specific clarifying question based on gaps

### Phase 3: Enhancement

Apply mode-specific techniques based on interview responses.

### Phase 4: Refinement Loop

Present enhanced prompt, ask for feedback:

- Perfect - use this
- Adjust tone/style
- Add more detail
- Simplify it
- Different approach

Loop until satisfied (max 5 iterations).

### Phase 5: Execute or Return

Ask: Execute now, or return for manual use?

---

## Enhancement Principles

- Preserve original intent faithfully
- Add specificity without bloating
- Match user's apparent expertise level
- Anticipate follow-up needs
- Don't add features user didn't ask for

---

## Examples

```bash
# Quick enhancement + execute
/enhance fix the auth bug

# Interactive with refinement
/enhance --interactive write docs for the API

# Already-detailed prompt gets minimal touch
/enhance implement JWT auth with refresh tokens using RS256,
        store in httpOnly cookies, 15min access / 7day refresh
```
