---
name: grok
description: >
  Run a large, systematic codebase audit campaign — measure the codebase,
  partition it into regions sized for genuine coverage, dispatch a fleet of
  agents across model tiers (including cheap/fast/tiny-context models), triage
  findings against a recurring bug-pattern taxonomy, and file them into the
  project tracker with consistent blocking criteria. Use for "audit the whole
  codebase", "find bugs before we ship/wipe/migrate", "exhaustively review
  this", or when a single agent's context can't hold the target. Not for a
  quick one-file review (use a single review agent) or an interactive,
  user-steered exploration (use `analyze`) or a routed one-shot dev task (use
  `swarm`).
metadata:
  short-description: Large-scale systematic codebase audit campaigns
---

# Grok — Systematic Codebase Audit

Deep, evidence-grounded understanding of a codebase at scale, produced by
measuring it, partitioning it into regions a single agent can actually hold,
fanning out a mixed fleet of models against those regions, and running a
disciplined triage/filing loop on what comes back. This is the campaign
playbook distilled from real large audits (hundreds of agent-dispatches,
hundreds of findings) — every technique and pitfall here was hit for real, not
theorized.

**Target**: $ARGUMENTS

## Is this the right skill?

```
IF you need ONE file/module reviewed                → dispatch a single `review` agent directly, skip this skill
IF the user wants to steer phase-by-phase             → use `analyze` (survey→narrate→synthesize, interactive)
IF it's a routed one-shot dev task (implement/fix/PR)  → use `swarm`
IF you need broad, systematic coverage of a real
   codebase, sized past what one agent's context holds → this skill
```

Grok is the campaign layer: it owns measurement-driven partitioning,
multi-tier model dispatch (including non-Claude fast/cheap models), a bug
taxonomy to triage against, and coordinator discipline for filing hundreds of
findings without duplicating or losing them. It does not reinvent
`agent-orchestration`'s launch mechanics or `analyze`'s narrate technique —
it cites both and adds what large campaigns need on top.

## Workflow

```
measure → partition → dispatch (wave 1: broad regions)
        → triage + file
        → dispatch (wave 2: narrow narrate-through, cheap models, second pass on hot spots)
        → triage + file
        → hygiene pass (tracker structure)
        → verify (spot-check every subagent/fork's claimed work)
```

Waves are independent — run wave 1 alone for a first pass, or skip straight to
wave 2 for a targeted narrate-through sweep of a specific area. Don't force
every campaign through all phases if the target doesn't warrant it.

### 1. Measure

Never partition by guesswork or directory names alone. Get real numbers first:

```bash
find <root> -name "*.rs" -not -name "*_test.rs" | xargs wc -l | sort -rn
```

(swap the extension/exclusion for the target language). Do this per-crate/
per-package, then drill into whichever subdirectories are still too large to
read exhaustively. `scripts/partition_by_size.sh` automates this sweep and
proposes region boundaries at a target size — see
[`references/partitioning.md`](references/partitioning.md) for the full
methodology and worked sizing targets per model tier.

### 2. Partition

Boundaries follow real module/directory seams, not arbitrary line-count
slices — a region should be small enough for one agent to read every line and
hold a coherent mental model, not just fit under a number. Target sizes by
model tier (justified in the partitioning reference):

| Tier | Target region size | Shape |
|---|---|---|
| Opus / dense logic | 3K–8K lines | subtle invariants, provenance, admission, DB write chokepoints |
| Sonnet / coverage | up to ~15K lines | mechanical/repetitive surfaces (handlers, CLI commands) |
| Fast+tiny-context (e.g. Codex spark tier) | 1–4 files, ~500–2500 lines | narrow narrate-through second pass |

### 3. Dispatch

Give every region agent: exact absolute file paths (don't make it discover
them — that burns its own budget and, for small/fast models, actively fights
their instinct to avoid broad exploration), the specific bug shapes to watch
for (the taxonomy below), an explicit instruction to read *every* file
completely, and — critically — permission to report partial coverage honestly
rather than end in silence. See
[`references/model-tiering.md`](references/model-tiering.md) for which model
fits which region shape and the concrete launch mechanics (including non-
Claude backends) that actually worked, with the concurrency/staggering
lessons learned the hard way.

### 4. Triage and file

Every finding gets checked against the bug-pattern taxonomy
([`references/bug-pattern-taxonomy.md`](references/bug-pattern-taxonomy.md))
and against the existing tracker before filing — a large fleet independently
rediscovers the same root cause more often than you'd expect. Coordinator
discipline (batching, blocking-criteria consistency, dedup, single-commit
export) is in
[`references/coordinator-discipline.md`](references/coordinator-discipline.md).

### 5. Narrate-through second pass

A first broad pass (thematic grep-shaped sweep, or a Sonnet/Opus region read
under time pressure) reliably misses things a close, forced-attention re-read
catches — especially in files an earlier agent's own report flagged as
"partially read" or "deprioritized for time." The **narration technique**
(state what each block does and what invariant it relies on, for the *whole*
file, before concluding anything) is cheap to run with fast/small models
against narrow single-file or 2–4-file targets. Full technique and prompt
template in [`references/techniques.md`](references/techniques.md).

### 6. Hygiene

After a large filing wave, the tracker itself needs a pass: `bd lint` (or
equivalent) for structural completeness, formalizing prose-only
cross-references into real dependency/relate edges, attaching orphans to the
right parent, backfilling labels. This is graph/metadata work, not
re-investigation — keep the two separate.

### 7. Verify

Trust but verify. A subagent or fork's summary describes what it *intended*
to do; before reporting a campaign's results as done, spot-check a handful of
its claimed filings for real content, and independently confirm the
mechanical invariants (dependency graph has no cycles, lint is clean, the
commit actually landed and pushed).

## Pitfalls

Real failure modes hit running these campaigns — shell escaping, launcher
concurrency races, a background-detach mistake that silently breaks `wait`,
agent turn-budget exhaustion, and more — are logged in
[`references/pitfalls.md`](references/pitfalls.md). Read it before a first
run; it will save you from re-discovering each one the expensive way.

## Begin

1. Measure the target (§1).
2. Propose a partition and region-to-tier assignment; state it before
   dispatching so scope is explicit.
3. Dispatch wave 1, or jump straight to a narrate-through wave 2 if the ask is
   narrower.
4. Triage, cross-reference, file — batched, not per-finding.
5. Run the hygiene pass if this is a large multi-wave campaign.
6. Verify and report a dense summary: counts, standout findings, what was
   deliberately skipped and why.
