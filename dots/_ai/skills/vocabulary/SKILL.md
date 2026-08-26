---
name: vocabulary
description: Clarify disputed or overloaded terminology, maintain a repository glossary, prevent unnecessary jargon, and record hard-to-reverse vocabulary decisions.
---

# Vocabulary

The failure mode here is not missing terminology but overloaded
and ritual terminology: one word naming many mechanisms (34 `*Receipt`
classes; "authority" across three domains; "generation" naming two unrelated
things), and tracker prose in a ceremonial register the operator cannot
parse. This skill is the active discipline against both.

## The glossary

Each repo keeps ONE hand-maintained glossary page, ≤ ~40 lines
(`docs/vocabulary.md` or a section of the architecture spine): one sentence
per term — what it IS mechanically, and the incident that justified it.
Not generated, not a restatement surface; it earns its size by staying
small. The polylogue anchor set: Origin vs Provider vs Source vs
material_origin is the canonical worked example of distinctions that repay
their glossary lines daily.

## During any design or writing session

- **Challenge overloads immediately.** A term already meaning something else
  in the glossary gets flagged in the moment: "'receipt' here means the
  verify run record or the backup manifest?" Do not let a second meaning
  attach quietly.
- **Sharpen fuzzy terms** by proposing the precise one, and stress-test
  relationships with concrete edge-case scenarios.
- **Cross-reference the code.** When someone states how something works,
  check whether the code agrees; surface contradictions rather than
  recording them.
- **Update the glossary inline** the moment a term is resolved — not in a
  batch later.

## Stopping new jargon (anti-regeneration rules)

1. Name the artifact or behavior, never the ritual: "run the checks on the
   live archive and store the result", not "emit a proof-carrying receipt".
2. No new noun for a mechanism that already has one; check the glossary
   before coining.
3. No new durable table, receipt class, or result vocabulary for a one-shot
   operation — one generic journal; run → drain → delete.
4. Agent-coined terms get a plain-language introduction at first use in any
   operator-facing text: "run record (receipt)".
5. A leading word must recruit pretrained priors ([[writing-for-agents]]);
   a coinage that needs a paragraph of definition is a cost, not a hook.

## Decisions, sparingly

Record a decision durably (architecture-spine decision log in polylogue;
docs/adr or equivalent elsewhere) only when all three hold: hard to
reverse; surprising without context; the result of a real trade-off among
genuine alternatives. Anything less is a commit message. A rejected design
gets a decision entry only when a future explorer would otherwise
re-propose it.

## What this skill is not

Not a rename campaign. Mass renames of working code cost more than the
overload; the discipline is: stop the bleeding (rules above), fix names
opportunistically when touching the surface anyway, and reserve deliberate
renames for the worst operator-facing offenders (bead titles, CLI output,
status surfaces).
