---
name: enhance
description: Rewrite rough requests into high-leverage prompts while preserving intent. Use for quick prompt polishing, executable code/research prompts, external-agent handoffs, or non-overlapping prompt portfolios with fresh context and honest deliverable contracts.
metadata:
  short-description: Prompt rewriting, handoffs, and prompt portfolios
---

# Prompt Enhancement

Turn the user's request into the smallest prompt that reliably produces the
intended result. Preserve ambition and constraints. Enhancement is not license
to substitute an easier task, add ceremony, or make a short request verbose.

## Modes

Select the lightest mode that fits:

- **Rewrite**: polish one prompt. This remains the default and should often be
  short.
- **Execution prompt**: make a code, research, planning, writing, or creative
  task decision-complete for a capable agent.
- **Handoff**: prepare a prompt and evidence/context packet for an agent that
  does not share the current runtime.
- **Portfolio**: prepare several distinct prompts, with overlap, priority, and
  dependency control.

Use handoff or portfolio mode when the user asks for agent packets, browser
chats, prompt series, queued model work, or reusable agent delegation. In those
modes, read `references/agent-handoffs.md` completely before producing files or
launching work. Do not load it for an ordinary rewrite.

## Invocation and execution

- `enhance <prompt>`: return the enhanced prompt, then execute it unless the
  user clearly asks only for rewriting or preparation.
- `enhance --no-execute <prompt>` or “just enhance”: return the prompt only.
- `enhance --interactive <prompt>`: ask only questions whose answers materially
  change the result, then rewrite and optionally execute.
- `enhance --handoff <request>`: produce an external-agent prompt plus its
  context and deliverable contract.
- `enhance --portfolio <request>`: produce a non-overlapping set of prompts and
  a short dispatch manifest.

If the user asked for prompt files or handoff artifacts, creating those files
is the execution; do not also perform the delegated mission unless requested.

## Workflow

### 1. Recover the intent kernel

Extract:

- the end state the user actually wants;
- explicit scope, exclusions, authority, urgency, and quality bar;
- the expected deliverable: answer, decision, design, patch, package, or
  verified change;
- facts that are known versus details that must be discovered;
- observable success and unacceptable failure modes.

Do not force the user to restate context already available in the conversation,
repository, tracker, or referenced evidence.

### 2. Fit the prompt to the executor

Identify who will run it and what that executor can actually do:

- repository/filesystem access;
- command execution and test verification;
- network or source access;
- attachment input/output support;
- context window and likely duration;
- authority to mutate code, trackers, branches, or external systems.

Never ask a browser-only model to claim tests passed. Never give a read-only
researcher an implicit mutation contract. When capabilities are uncertain,
require explicit evidence and honest limitation reporting.

### 3. Gather only authoritative context

Inspect available source, tracker records, history, and current state before
naming files, APIs, or acceptance criteria. State the authority order when
stale notes or generated packets may conflict with live code.

For external agents, record context freshness (commit, date, source paths) and
use a targeted pack by default. A whole repository is appropriate only when the
mission genuinely crosses it or the executor can navigate it without shallow
summarization.

### 4. Build the prompt mission-first

Put a readable description of the actual job at the top. Opaque identifiers
such as issue or Bead ids are supporting references, not the mission title.

Use only the sections the task needs:

1. **Mission** — the concrete outcome in ordinary language.
2. **Context and authority** — relevant evidence, snapshot identity, and what
   wins if sources disagree.
3. **Scope and non-goals** — boundaries that prevent drift or duplication.
4. **Constraints** — capability, safety, architecture, time, and verification
   limits.
5. **Work requested** — useful strategy or investigation order, without
   scripting every obvious move.
6. **Acceptance criteria** — observable behavior and falsification, not diff
   trivia.
7. **Deliverable contract** — what the human/integrator receives and how
   uncertainty is represented.

For implementation tasks, require tests that exercise the production route and
state what implementation mutation/removal would make them fail. For research,
separate evidence from inference and require current primary sources when the
facts can change.

### 5. Make the output useful without opening artifacts

When a package, patch, or file is requested, also require substantive direct
output: what was done, why, important decisions, evidence, verification status,
and residual risk. A generated archive is not an adequate explanation.

Conversely, do not ask for an elaborate package when a concise answer or single
patch is the natural deliverable.

### 6. Compress and adversarially read once

Remove:

- generic “be thorough” filler;
- repeated constraints;
- instructions a competent executor already infers;
- stale file/line assertions not verified from source;
- output formatting that adds no integration value.

Then check: could the executor satisfy the wording while missing the user's
real outcome? Tighten that loophole, and stop.

## Output shapes

### Ordinary rewrite

```text
ENHANCED PROMPT
[ready-to-run prompt]

WHY THIS IS BETTER
- [one to three meaningful improvements]
```

If the prompt was already strong, lightly polish it and say so. Do not expand
it into the full sectioned template.

### Complex execution prompt

```text
ENHANCED PROMPT
[mission-first prompt with only relevant sections]

WHY THIS IS BETTER
- [one to three meaningful improvements]
```

### Handoff or portfolio

Follow `references/agent-handoffs.md`. Return the prompt file(s), context-pack
manifest or attachment instructions, and dispatch/integration notes. Each
prompt must remain understandable without knowing an issue id.

When executing after enhancement, say `Executing this enhanced prompt now.` and
then carry out the work. Do not print a long enhanced prompt merely to narrate
work the user asked you to perform unless seeing the prompt is itself useful.

## Interactive questions

Ask at most three questions, and only when the answers cannot be discovered and
would materially change the prompt. Good questions choose real tradeoffs:

- implementation versus analysis-only;
- one cohesive package versus several independent outputs;
- speed versus a specific durability or compatibility requirement.

Do not ask about repository facts, current files, tracker state, or agent
capabilities that can be inspected.

## Guardrails

- Preserve the user's actual ambition, priority, and exclusions.
- Do not invent files, APIs, test results, citations, or external evidence.
- Keep verification claims proportional to what the executor can run.
- Do not leak private context into external-agent packs; inspect publication
  and account boundaries first.
- Do not overfit to an agent brand unless the user named it.
- Do not confuse many prompts with useful parallelism; duplicate scopes waste
  quota and complicate integration.
- If the request is harmful, impossible, or needs authority the user has not
  granted, improve it into the nearest safe, honest request and state the
  boundary.
