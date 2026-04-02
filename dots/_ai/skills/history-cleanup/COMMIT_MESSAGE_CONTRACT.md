# Commit Message Contract

This contract exists because "longer than before" is not the goal.

The goal is a commit message that is useful enough that a later operator can
usually trust `git log` before opening the diff.

## Purpose

A good rewritten commit message should answer three questions:

- what changed
- what effect that change had
- why the change was made, only when the evidence supports it

The message is not required to explain everything in the diff.
It is required to explain the dominant semantic change clearly and honestly.

## Subject Line

The subject line should:

- name the dominant change, not the process status
- prefer concrete verbs such as `split`, `extract`, `normalize`, `replace`,
  `retire`, `stabilize`, `route`, `validate`
- mention the central surface if it is recoverable from the patch
- stay short enough to scan quickly in `git log --oneline`

The subject line should not:

- say only `cleanup`, `finish`, `finalize`, `misc`, `updates`, `progress`
- pretend certainty about intent that the patch does not support
- mirror a planning note instead of the code change that landed

If a generic process verb really is the best available subject, the body must
compensate with concrete surfaces and effects.

## Body

The body is where the semantic payload lives.

Minimum useful body:

- one paragraph for smaller commits
- usually `25+` words

Preferred body for non-trivial commits:

- `40+` words
- at least two short paragraphs or one dense paragraph with clear effect language
- preferably a compact lead plus `2-4` bullets

Preferred structure for audit-grade rewrites:

- optional one-sentence lead line
- then `2-4` bullets
- bullets should usually cover:
  - concrete surfaces touched
  - the main change
  - behavioral effect or reason, when supported by the diff

Prefer compact audit-log structure over glossy explanatory prose.

The body should contain:

- the concrete surfaces that changed
- the behavioral, architectural, or operational effect
- the boundary of the change when the commit is mixed or wide

The body may contain:

- the rationale
- notes about preserved invariants
- why a specific decomposition or isolation mattered

The body should not:

- enumerate files mechanically
- repeat the subject with different adjectives
- claim "completed" or "finalized" unless the patch really justifies that
- invent motivation that is not visible from the patch or adjacent context
- open with filler such as `This commit`, `This change`, `Behaviorally`,
  `The practical effect is`, or `After the refactor`

## Evidence Rules

Primary evidence:

- changed code
- changed paths
- nearby commits when the boundary or rationale is unclear

Secondary evidence:

- existing commit message text
- plan notes
- surrounding commit-message context outside the owned packet

If the evidence does not support a confident `why`, omit it.
An honest omission is better than fabricated rationale.

## Quality Gates

Useful rewrite gate:

- body exists
- body is not just one vague sentence
- effect language is present
- message names at least one concrete surface or interface

Strong rewrite gate:

- body is comfortably detailed
- effect is explicit
- rationale is included when defensible
- subject is concrete rather than process-oriented
- structure is visible at a glance, usually via bullets
- body avoids filler phrasing

Typical failure flags:

- `no_bullets`
- `filler_phrasing`
- `no_body`
- `thin_body`
- `single_paragraph`
- `missing_effect_signal`
- `missing_concrete_surface`
- `vague_subject`
- `literal_newline_escape_in_subject`

These are the same failure modes the `message-quality-report` command looks for.

## Worker Output Shape

Recommended worker output for one commit:

```json
{
  "sha": "0123456789abcdef...",
  "confidence": "low|medium|high",
  "message": {
    "subject": "refactor: split query runtime from output routing",
    "body": "Move the query execution path into dedicated runtime helpers and route formatting through separate output bands.\n\nThis isolates fetch-time state from presentation concerns, which makes later query cleanup and packetized review easier to reason about."
  },
  "why_basis": "patch_only|patch_plus_neighbors",
  "notes": ["mixed semantics", "rationale inferred from adjacent follow-up"]
}
```

## Packet Guidance

For large repositories and 128k-context workers:

- prefer full diffs for owned commits
- add only message-only context at packet edges
- isolate heavy single commits
- chunk jumbo commits before asking for a final message

Do not spend worker budget duplicating full diffs for overlap unless there is a
clear need. Message-only edge context is usually the better tradeoff.
