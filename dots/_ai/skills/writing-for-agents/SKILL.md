---
name: writing-for-agents
description: Write or revise skills, CLAUDE.md/AGENTS.md, memory files, and agent-facing references, especially when instructions are stale, bloated, weakly routed, or ignored.
---

# Writing for agents

Reference for any document an agent consumes. The packaging differs (skill,
CLAUDE.md, memory file, reference); the writing does not: the same levers make
the agent take the same process every run. On this estate these documents are
live infrastructure — dots-propagated instantly, loaded into every session —
so every line has a per-session token cost and a drift risk.

## Context pointers

A **pointer** is an in-context reference to out-of-context material: a skill
description, a CLAUDE.md line naming a doc, a `[[memory]]` link. The pointer's
wording — not its target — decides whether the agent ever reaches the
material. A load-bearing target behind weak wording is a variance bug:
sharpen the wording first; inline the material only if sharpening fails.

Pointer rules (they pay rent every turn, so prune hardest here):
- Front-load the trigger word; one trigger per genuinely distinct branch;
  collapse synonyms that rename the same branch.
- Cut identity the body already carries.
- In THIS harness every listed skill's description is always loaded — there
  is no zero-cost invocation class. The budget lever is description length.

## The two loads

- **Context load**: always-loaded material (CLAUDE.md lines, skill
  descriptions) costs tokens and attention every turn, firing or not.
- **Cognitive load**: the operator remembering what exists and when to reach
  for it. Not a cost to minimize — it is the price of operator agency. Spend
  it where judgment matters; remove it where it does not.

Material behind a pointer escapes context load for the price of the pointer's
line. The estate's instruction-reduction program (five CLAUDE.md files,
2,268 → ~1,000 lines) is this trade executed at scale.

## Information hierarchy

Three tiers: in-file **steps** (what the agent does, in order) → in-file
**reference** (consulted on demand) → **disclosed reference** (a `references/`
file behind a pointer). Push down whatever only some branches reach; keep
inline what every branch needs. Keep skill bodies ≤ ~120 lines. Co-locate:
a concept's definition, rules, and caveats under one heading — scattered
material fragments one meaning across many places.

## Completion criteria

End every step on a condition the agent can check. Two levers:
- **Clarity**: "understanding reached" invites stopping early; "every
  modified surface accounted for" does not.
- **Demand**: the criterion's wording drives how much digging happens.
  "every rule applied" binds flat reference exactly as "every step done"
  binds a sequence.

Estate examples of the standard: anti-vacuity statements in lane reports;
"cite the changed files, exact verification commands, and what was not run."

## Leading words

A **leading word** is a compact pretrained concept the agent thinks with
(tight loop, red twin, tracer bullet, frontier). Repeated as a token it
anchors behavior cheaply. Hunt for restatements a leading word retires.
Two cautions, both estate doctrine:
- A coined word recruits no priors — you pay its definition everywhere. This
  is how the jargon debt (receipt ×8 meanings, authority ×3) accumulated.
  Before coining, check the [[vocabulary]] glossary; never mint a new noun
  for a mechanism that already has one.
- **Negation is weak**: "don't do X" drags X into context and half-reads as
  an instruction. State the positive target; keep prohibitions only as hard
  guardrails, paired with the positive.

## Pruning

- **Single source of truth** per meaning; duplication drifts. On this estate
  AGENTS.md is a symlink to CLAUDE.md for exactly this reason.
- **The environment is a source of truth**: `devtools --list-commands`,
  `agentctl --help`, `bd --help`, generated reference docs, `.agentctl/
  project.toml`. A document restating them is a cache that goes stale — the
  estate's recorded failure class (six stale CLAUDE.md claims, skills
  teaching nonexistent verbs). Cache only what no lookup confesses: the
  unwritten convention, the reason, the gotcha.
- **No-op test** (model-relative): does the sentence change behavior versus
  the model's default? "Be thorough" fails; delete the sentence, or replace
  the weak word with a stronger one (relentless), not with emphasis.
- **Sediment**: stale layers settle because adding feels safe and removing
  feels risky. Every instruction-file edit should delete at least as
  deliberately as it adds; a refresh that only appends is suspect.

## Estate specifics

- Skills follow [[skill-authoring]] mechanics (frontmatter, validator,
  forward-probe routing tests). This skill owns the prose craft; that one
  owns the lifecycle.
- Memory files: one fact per file, one-line index entry in MEMORY.md, link
  liberally with `[[name]]`; archive superseded eras rather than deleting.
- Bead prose is agent-consumed too: titles name the artifact or behavior,
  never the ritual (see [[bead-authoring]]).
- When editing any always-loaded file, state in the change what got SHORTER.
