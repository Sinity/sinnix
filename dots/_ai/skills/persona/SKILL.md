---
name: persona
description: Apply a named cognitive lens from the bundled persona catalogue to stress-test plans, designs, or reviews. Use when you want a Carmack, Hickey, Linus, devil's-advocate, maintainer, security, or pragmatist perspective on the current context.
metadata:
  short-description: Perspective shifts for reviews and stress tests
---

# Persona

Use this skill to apply a deliberate perspective shift to the current conversation context.

The catalogue lives in `references/personas.yaml`.

## When To Use

1. Stress-test a plan or design from a specific angle.
2. Ask what a particular thinker would notice that a generic review would miss.
3. Compare multiple viewpoints on the same problem without spinning up fresh subagents.

## Workflow

1. Read the chosen persona from `references/personas.yaml`.
2. Use its `values`, `asks_first`, `approves`, and `rejects` fields to frame the analysis.
3. Keep the output grounded in the actual code, plan, or evidence at hand.
4. If the user wants multiple personas, compare them explicitly rather than blending them.

## Guardrails

1. Treat personas as lenses, not authorities.
2. Prefer concrete observations over theatrical roleplay.
3. Keep the persona's voice recognizable, but do not invent facts to fit it.
4. Use this skill in the current thread; a fresh subagent loses the conversation state that makes the lens useful.

## Examples

- Carmack: measure-first performance or systems critique
- Hickey: simplicity and decomplecting pass
- Linus: maintainer and code-taste pass
- Devil: adversarial hole-finding
- Security: trust-boundary and attack-surface pass
- Pragmatist: YAGNI and shipping-pressure pass

## Maintenance

If a persona is genuinely useful enough to keep, update `references/personas.yaml` deliberately. Do not keep mutable calibration logs or other runtime state inside the skill directory.
