---
name: enhance
description: Rewrite rough prompts into high-leverage agent prompts, preserving intent while adding missing context, constraints, output shape, acceptance criteria, and optional execution.
metadata:
  short-description: Prompt enhancement and execution
---

# Prompt Enhancement

Turn a rough request into a prompt that a capable agent can execute with less
ambiguity and fewer wasted turns. Preserve the user's actual intent; do not
smuggle in a safer, smaller, or unrelated task.

## Invocation

- `enhance <prompt>`: produce an enhanced prompt, then execute it unless the user
  clearly asked to only rewrite.
- `enhance --no-execute <prompt>` or "just enhance": return the prompt for manual
  use.
- `enhance --interactive <prompt>`: ask only the missing questions that materially
  change the prompt, then rewrite and optionally execute.

If the input is already strong, do a light polish rather than expanding it.

## Fast Workflow

1. **Classify the job**
   - `code`: implementation, debugging, refactor, review, tests, repo work.
   - `research`: compare, investigate, summarize sources, decide.
   - `writing`: docs, email, narrative, editing, tone/style.
   - `planning`: roadmap, spec, migration, workflow.
   - `creative`: ideation, design, naming, exploration.
   - `general`: everything else.

2. **Extract intent**
   - Objective: what should be true at the end.
   - Constraints: explicit "do/don't", tools, budget, style, dates, audience.
   - Unknowns: gaps that would change the answer or implementation.
   - Success signals: tests, acceptance criteria, deliverable shape, quality bar.

3. **Add only useful specificity**
   - Clarify scope boundaries and non-goals.
   - Add relevant environment/context already known in the conversation.
   - Specify output format only when it helps.
   - Add verification or acceptance criteria for code/system tasks.
   - Add source and recency requirements for research tasks.
   - Add audience, tone, and structure for writing tasks.

4. **Compression pass**
   Remove redundant phrasing, generic best-practice filler, and instructions that
   a competent agent would already infer. The final prompt should be denser, not
   merely longer.

## Output Format

For normal use:

```text
ENHANCED PROMPT
[ready-to-run prompt]

WHY THIS IS BETTER
- [1-3 concise bullets explaining meaningful improvements]
```

For complex code/system work, use this richer shape:

```text
ENHANCED PROMPT
[role/task/context paragraph]

Scope:
- [included work]
- [excluded work]

Constraints:
- [hard requirements and known pitfalls]

Execution:
- [ordered steps or strategy]

Acceptance Criteria:
- [observable completion checks]

Output:
- [what to report back]

WHY THIS IS BETTER
- [1-3 concise bullets]
```

If executing immediately, add a short line after the prompt:

```text
Executing this enhanced prompt now.
```

Then carry out the work using the enhanced prompt.

## Interactive Mode

Ask questions only when the answer materially changes the enhanced prompt and
cannot be inferred from context. Limit to three short questions. Prefer direct
questions over elaborate forms.

Good questions choose between real tradeoffs:

- "Should this optimize for speed of implementation or long-term maintainability?"
- "Is the deliverable a user-facing explanation, a patch, or a plan?"
- "Should the agent execute after rewriting, or return the prompt only?"

Avoid asking about details that can be discovered from the repo, current files,
or available context.

## Domain Hints

### Code

Include repository context, files/components if known, constraints on mutation,
verification commands, and commit/PR expectations. Say whether to implement,
review, explain, or plan.

### Research

Require current sources when facts may have changed. Ask for citations or source
links when useful. Separate evidence from inference.

### Writing

Specify audience, purpose, tone, structure, length, and what must be preserved.
For editing, request a brief change summary if the user needs to evaluate style.

### Planning

Make the plan decision-complete: scope, sequence, interfaces or deliverables,
risks, tests, rollout, and assumptions.

## Guardrails

- Do not contradict explicit user constraints.
- Do not invent facts, files, APIs, or external evidence.
- Do not turn a quick request into ceremony.
- Do not overfit to one agent brand unless the user named that agent.
- If the user's prompt is harmful, unsafe, or impossible, improve it into the
  nearest safe/useful request and state the boundary briefly.
