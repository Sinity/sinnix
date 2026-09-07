---
name: meta
description: Audit and improve agent instructions, configuration, memory organization, and delegation using observed session friction. Use for self-audits or explicit requests to improve the agent setup.
---

# Improve the agent setup

## Scope and authority

For an audit request, inspect and recommend. When the user authorizes changes,
make scoped improvements and show the resulting diff; do not ask for the same
authorization again. Obtain direction for ambiguous destructive changes or
live activation beyond the request.

Use `writing-for-agents` for instructions and memory, `skill-authoring` for
skill lifecycle and routing, and `orchestrate` for delegation changes.

## Audit

1. Resolve the active files, symlinks, generated sources, and repository rules.
   Distinguish source configuration from what the current harness loaded.
2. Inventory global/project instructions, memory indexes, skills, agent
   definitions, and relevant runtime settings. Preserve unrelated work and
   avoid printing credentials or private transcripts.
3. Check instructions against current code and observed attempts. Look for
   contradictions, duplicated authorities, stale task state, misleading model
   defaults, broken pointers, and procedures that require unnecessary turns.
4. Prioritize defects by the decisions they change. Delegate bounded catalog
   checks; use strong judgment for architecture and disputed conclusions.
   A structural validator cannot establish that advice is correct.

## Improve

- Keep global instructions for cross-project constraints and project
  `CLAUDE.md` for stable semantics. Put procedures in their owning skill,
  task state in Beads, and job evidence in runtime artifacts.
- Update the existing owner before adding a field, rule, skill, or ledger.
  Replace contradictory advice in the same change and name what got shorter.
- Automate deterministic collection, validation, and formatting. Keep failure
  attribution, model selection, scope changes, and acceptance as decisions
  unless a specific policy is explicitly authorized and testable.
- Read session history through Polylogue or the harness-specific session
  skill. Use bounded evidence; distinguish measured activity from inferred
  cost or competence. Compare model attempts using actual launch identities
  and inherited work, not nominal task labels or closure counts.
- Preserve useful superseded memory in its archive. An unfinished task is
  not stale merely because it is old; verify its owner and current evidence.

## Verify and hand off

Validate changed skill structure and links, probe changed routing with
positive and negative requests, and review the full diff for private data.
For configuration changes, verify the generated surface through its owning
tools. Do not activate the host merely to claim a documentation change done.

Report coverage, material changes, exact checks, unresolved defects, and
whether changes are source-only, published, or active. Record task-shaped
follow-ups in the owning Beads project. Keep experimental allocation rules
bounded by a decision, stopping condition, and expiry.
