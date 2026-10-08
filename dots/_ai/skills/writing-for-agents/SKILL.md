---
name: writing-for-agents
description: Write, revise, or audit text agents load — global and project instructions (AGENTS.md), skills, agent definitions, memory, task prose — and improve the agent setup from observed friction.
---

# Writing for agents

Instructions, skills, agent definitions, memory, and task text are live
infrastructure: every sentence is read by agents that act on it. The goal is
that the same situation produces the same behavior every run, at the smallest
standing cost. Skill lifecycle and validation belong to `skill-authoring`;
this skill owns the writing and the audit.

## Where text lives

- Global instructions (`/realm/projects/sinnix/repo/dots/_ai/AGENTS.md`, linked
  into each agent's home) hold cross-project rules. A repository's `AGENTS.md`
  is its only project instruction file and holds its stable semantics; Claude
  Code, Codex, and Gemini all read it, so no `CLAUDE.md` accompanies it.
  Skills hold procedures only some sessions need.
  Beads hold tasks, decisions, and their evidence. Memory holds stable facts
  and pointers nothing else records.
- Resolve an installed file to its source before editing. Live symlinks
  change on the next read, though a running agent keeps what it loaded;
  generated or copied files change only after their install or activation.
- The environment is a source of truth. Commands, generated references, and
  descriptors confess their own syntax; restating them creates a cache that
  goes stale. Record only what no lookup reveals: the convention, the reason,
  the trap.

## Standing cost

Always-loaded text (global and project instructions, every skill description)
costs attention on every turn whether it fires or not. Prune it hardest.

- A skill description is a router: front-load the words a request would use,
  one trigger per distinct branch, 35 words at most, no identity the body
  already carries.
- Push material only some branches need into the skill body, and material
  only some readers of the body need into a `references/` file behind a
  pointer. Keep a skill body near 120 lines.
- A pointer's wording decides whether the agent ever reaches its target.
  Sharpen weak wording before inlining the material.

## Writing

- One fact, one place. Duplicates drift; point to the owner instead.
- End each step on a condition the agent can check. "Every modified surface
  accounted for" gets done; "understanding reached" invites stopping early.
- State the positive target. A prohibition drags its subject into context;
  keep one only as a hard guardrail, paired with what to do instead.
- Apply the no-op test: delete any sentence that would not change behavior
  against the model's default. Replace emphasis with a missing rule.
- Name artifacts and behaviors, not rituals ("run the checks and keep the
  result", not "emit a proof-carrying receipt"). Reuse existing terms; coin a
  term only when it removes real ambiguity, define it at first use, and
  challenge a second meaning the moment one attaches.
- Test each distilled fact: what decision changes if it is wrong or absent?
  If none, delete it. Incident stories, dates, benchmark numbers, and vendor
  trivia rarely pass.
- Every edit to an always-loaded file deletes as deliberately as it adds.
  State what got shorter.

## Memory

One fact per file under the project memory directory, with a one-line entry
in `MEMORY.md`. Feedback and project memories carry **Why** and **How to
apply**. Update the existing file rather than adding a near-duplicate; archive
superseded eras with their evidence rather than deleting them.

## Auditing the setup

For an audit request, inspect and recommend; when changes are authorized,
make them and show the diff without asking again. Obtain direction for
ambiguous destructive changes or live activation beyond the request.

1. Resolve the active files, links, generated sources, and loaded state.
2. Inspect the surfaces implicated by the friction. Use observed invocations
   when needed to judge a skill's value; a small instruction fix does not need
   a complete setup census.
3. Check claims against current code and observed sessions: contradictions,
   duplicated authorities, stale mechanisms, broken pointers, procedures that
   cost turns without changing outcomes.
4. Fix by decision value: merge overlapping owners, delete what no longer
   changes behavior, move each rule to the narrowest scope that needs it.
5. Verify changed structure and references, check routing when its description
   changed, review the delta for private data, and confirm the installed surface
   through its owner. Report whether the change is source-only or active.
