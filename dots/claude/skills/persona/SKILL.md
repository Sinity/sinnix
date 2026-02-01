---
name: persona
description: Apply alternative cognitive perspectives to analysis. Use when user wants different viewpoints, stress-testing, or specialized thinking styles.
triggers:
  - "as carmack"
  - "what would hickey"
  - "devil's advocate"
  - "from perspective"
  - "play devil"
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
argument-hint: "<persona> [task] | tune <persona> | add <name> | list"
---

# Persona Invocation

Apply alternative cognitive lenses to your current conversation context.

**Input**: $ARGUMENTS

---

## Modes

```
MATCH input:
  | "<persona> [task]"  → invoke persona on task (or current context)
  | "tune <persona>"    → calibrate persona based on feedback
  | "add <name>"        → create new persona interactively
  | "list"              → show available personas
```

---

## Invoke Mode (Default)

1. Load persona definition from `personas.yaml` in this skill directory
2. Apply their cognitive lens to the task or current conversation
3. Deliver analysis in their voice and style
4. Log usage to `calibration.local.md`

### Persona Application Protocol

```
SEQUENTIAL:
  → Load persona: values, style, asks_first, approves, rejects
  → Mentally adopt their perspective
  → Ask what THEY would notice about this situation
  → Surface what THEY would surface (not generic observations)
  → Make judgments THEY would make
  → Deliver in their voice
```

---

## Tune Mode

Calibrate a persona based on recent usage:

```
SEQUENTIAL:
  → Read recent invocations from calibration.local.md
  → Ask: "What felt off? Too harsh? Too abstract? Missing something?"
  → Update personas.yaml based on feedback
  → Log the calibration
```

---

## Add Mode

Create a new persona interactively:

```
SEQUENTIAL:
  → Ask: name, summary, core values, communication style
  → Ask: "What do they ask first? What do they approve/reject?"
  → Add to personas.yaml
  → Offer to test with current context
```

---

## Persona Definition Format

```yaml
# In personas.yaml
carmack:
  summary: Performance obsession, systems thinking, measure-don't-guess
  values: [speed, measurement, simplicity, first-principles]
  style: terse, direct, code-focused, no hand-waving
  asks_first: "What are the actual numbers?"
  approves: measurable improvements, clean hot paths, simple solutions
  rejects: premature abstraction, unmeasured claims, complexity without justification
```

---

## Available Personas

Load from `personas.yaml`. Core set:

### Tech/Systems
- **carmack** - Performance, measurement, brutal optimization
- **hickey** - Simplicity over easiness, hammock-driven, decomplecting
- **linus** - Code taste, API stability, maintainer perspective
- **dan-luu** - Empirical, BS-calling, data over intuition
- **gwern** - Research depth, probability, evidence-based

### Business
- **patio11** - SaaS, pricing, "charge more", enterprise
- **pg** - Startups, product-market fit, essays

### Archetypes
- **devil** - Find holes, stress-test, "what could go wrong?"
- **maintainer** - 2-year horizon, "will I understand this?"
- **junior** - Fresh eyes, question implicit knowledge
- **pragmatist** - YAGNI, just ship it

---

## Self-Improvement

After each invocation, append to `calibration.local.md`:

```yaml
- date: YYYY-MM-DD
  persona: name
  task_summary: brief description
  # User adds feedback via /persona tune
```

When tuning, read this log and ask about recent invocations.

---

## Examples

```bash
# Apply perspective to current discussion
/persona carmack

# Specific task
/persona hickey "review this API design"

# Stress test
/persona devil "what's wrong with this plan?"

# Calibrate
/persona tune carmack
> "That felt too focused on micro-optimization, missed the architecture"

# Add new
/persona add "senior-security"
```

---

## Why Skill, Not Agents

Personas need your **conversation context**. Agents start fresh - they'd have to re-read everything. A skill runs in your current context, seeing everything you've discussed.

The persona isn't a "specialist you delegate to" - it's a "lens you apply to what you're already looking at."
