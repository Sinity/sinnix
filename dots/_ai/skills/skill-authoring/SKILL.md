---
name: skill-authoring
description: Create, restructure, validate, or retire a shared agent skill — routing description, SKILL.md layout, references, the validator, and routing probes.
---

# Skill authoring

Shared skills live in `/realm/projects/sinnix/repo/dots/_ai/skills/<name>/`. Claude
and Hermes read that directory through a live link, so text edits apply on the
next read. Codex gets one link per skill, created at Sinnix activation, so a
new, renamed, or deleted skill reaches Codex only after `switch`. The prose
craft is in `writing-for-agents`; this skill covers the package.

## Lifecycle

1. Collect a few real requests that should route to the skill and a few
   near misses that should not. Check whether an existing skill already owns
   the route; extending it beats adding a sibling.
2. Write the frontmatter: `name` in lowercase-hyphen form matching the
   directory, and a `description` of at most 35 words that leads with the
   words those requests use.
3. Keep `SKILL.md` near 120 lines, well under the validator's 500-line limit.
   Put variant detail, long examples, and checklists in `references/`, linked
   one level deep; put executables in `scripts/`. No README, changelog, or
   install notes, and no copy of the global or repository instructions.
4. Validate: `dots/_ai/skills/skill-authoring/scripts/validate_skill.py dots/_ai/skills`
   checks frontmatter, duplicate names, description length, file size, and
   links. It says nothing about whether the advice is right.
5. When the name or description changes, check routing with a trigger and
   near miss. Body-only edits need relevant structure/reference checks.
6. Regenerate the environment reference after any change to the skill set or a
   description: from the Sinnix root, `nix run .#sinnix-agent-environment-doc
-- --output docs/agent-environment.md`. An executable
   added or removed under a skill also updates
   `docs/agent-skill-executables.md`.

## Retiring or merging

Retire a skill only when another skill or a tool owns its route, or the route
itself is gone. Move its load-bearing rules to the owner, update every
reference (other skills, global instructions, docs, flake tests that copy its
scripts), and delete the directory. Record the reason in the commit.

Before publishing, confirm: the name matches its directory; the description
routes the trigger requests and not the near misses; every link resolves; the
validator is clean; nothing private is in the text.
