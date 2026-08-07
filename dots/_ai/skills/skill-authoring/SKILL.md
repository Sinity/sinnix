---
name: skill-authoring
description: Design, validate, update, and retire routed Codex skills. Use when creating a skill, repairing weak routing metadata, adding references, or deciding whether an older skill is superseded.
---

# Skill Authoring

Treat a skill description as a router and the body as a compact operating guide. Keep load-bearing procedure in `SKILL.md`, move detailed examples to one-level references, and avoid duplicating global agent instructions.

## Lifecycle

1. Define concrete user requests that should trigger the skill and requests that should not.
2. Write a specific frontmatter `name` and `description`, then keep the main file below 500 lines.
3. Add only directly useful references, scripts, or assets. Check every relative link.
4. Validate structure with `scripts/validate_skill.py <skills-root>`. The validator checks frontmatter, duplicate names, size, and references. It does not judge prose with magic-phrase rules.
5. Forward-test routing with representative trigger and non-trigger requests. Record what was observed, including false positives and misses.
6. Update an existing skill in place when it still owns the capability. Retire a skill only when a shipped replacement owns the same route, and record the reason in the owning task.

## Reference Layout

Use `references/` for checklists, examples, and variant-specific detail. Keep links one level deep from `SKILL.md`. Do not add README, changelog, or installation documents to a skill package.

Use the [lifecycle checklist](references/lifecycle-checklist.md) before publishing or retiring a skill.

## Evidence

For every routing change, record the before and after description, the request used for the probe, the selected skill or miss, and the reason for the result. Structural validation is separate evidence from routing behavior.
