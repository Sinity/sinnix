---
name: orchestrate
description: Coordinate several agents on one goal — ownership groups, model choice, native agents, forks or AgentCTL batches, integration review, and landing the result.
---

# Orchestrate

The coordinator owns priorities, scope, allocation, integration, and the
consequential decisions: retries, conflicting evidence, acceptance, and
destructive actions. Workers own coherent slices of the change and report once
when done. Spend coordinator attention on review and on deciding what runs
next, not on supervising progress.

## Choose the route

- **Native agents** for investigation, bounded help, and cohesive
  implementation. Give each one its own worktree (under `/realm/worktree/`)
  or a disjoint area of a shared checkout; the coordinator integrates.
  - In Claude Code, prefer forks (`subagent_type: "fork"`) for
    implementation: they inherit the conversation and the parent model. A
    fork that hits its 200-turn cap is resumed with a short continue message.
    Keeping workers alive and paced is covered under "Run the fleet" below.
  - Dispatch every editing agent with `isolation: "worktree"`. An agent's
    shell working directory resets to the session's project directory
    between calls, so a worktree named only in the prompt lets checks
    silently run against the main checkout.
  - Use a fresh `general-purpose` agent only when a clean context is the
    point (an independent review, a self-contained packet that must not
    inherit bias) or a different model is needed. Prefer Opus 5.5 to Fable 5.1.
    Every non-fork dispatch passes an explicit `model`; the
    dispatch hook refuses one without it.
  - In Codex, native spawn takes `model`, `reasoning_effort`, and `fork_turns`
    (`'none'` by default; `'all'` for deliberate full-history inheritance,
    with no model or effort override).
- **AgentCTL batch** (`agentctl batch start`) for independent groups that
  need isolated worktrees on one base, unattended queueing, or an explicit
  backend. Its landing task integrates, checks, and publishes;
  `agent-runtime` covers the batch verbs, stages, and recovery.
- Add workers only when independent work benefits from parallelism. Keep one
  owner for a small connected change; available slots are not a dispatch target.

## Shape the work

- An ownership group is defined by its accepted outcome: tasks that need the
  same source edits, evidence, or test selection go to one owner even when
  their file lists differ. The owner may change connected callers, tests,
  docs, schemas, and generated files to meet its criteria without asking
  again. `write_scope` is a conflict-planning estimate, not a fence; when an
  edit lands in another owner's area, keep it focused and name it in the
  report so the coordinator can order merges.
- A dependency that governs integration or acceptance is not a prerequisite
  for writing the first patch. Start independent code now; serialize only
  what truly shares a contract, and give that seam one owner.
- The packet names assigned outcomes, ownership, relevant source pointers,
  exclusions, and what to report. Include the base and a test selector when
  needed; avoid copied instructions, complete manifests, and unchanged history.
- Ask the owner to read every assigned task, write the whole connected change
  in one pass, use proportional verification, and briefly review the delivery
  ([worker-contract.md](references/worker-contract.md), step 4). After fixes,
  review only the delta and affected invariants. Report unmet criteria honestly.
  Implementation, testing, and self-review stay with one owner, never split
  into handoffs or a separate reviewer stage.
- A worker reports useful progress while required hosted review is pending,
  then completes publication under the repository's actual gates.

## Models

| Work                                                        | Codex                | Claude   |
| ----------------------------------------------------------- | -------------------- | -------- |
| Evidence collection, supervision, settled implementation    | `gpt-6-luna`, medium | `sonnet` |
| Substantial implementation, investigation, candidate review | `gpt-6.1-sol`, medium | `opus` (5.5) |
| Unresolved architecture, design-critical implementation     | `gpt-6.1-sol`, high   | `opus` (5.5) |

These are starting points. Prefer Sol 6.1 to Astra 6 for workers; raise effort
or tier for a named problem. `scripts/probe_agent_runtime.sh` checks a backend's
availability and quota before a large dispatch, not before every small task.
[model-landscape.md](references/model-landscape.md)
covers verifying the model that actually ran, attributing outcomes, and
running allocation trials.

## Run the fleet (Claude Code)

- `claude-quota` reads the account's 5-hour and weekly usage, their resets,
  and the burn rate; the statusline shows the 5-hour figure. Size new
  dispatches against what is left before the reset.
- A usage limit ends the coordinator's turn and stops background agents
  mid-task. A managed `StopFailure` hook waits for the reset and then wakes
  the coordinator. When woken, run `claude-agents --state quota`
  and resume each unfinished agent with a short continue message.
- `claude-agents` lists this session's subagents: idle minutes, state,
  context size, cache expiry, and their last message. An `ended` agent
  costs nothing; leave it. Stop one that is hung with TaskStop.

## Integrate

Review composition and changed seams, using worker evidence for unchanged
parts. Check the requested outcome, affected invariants, and honest test scope;
do not repeat the worker's review of an unchanged packet. Run broader regression
at a useful integration milestone or for a concrete risk. Keep ordinary known
failures visible without blocking independent progress. Preserve stronger
evidence for actual deployment, reset, data loss, or paid vector preservation.
Add an independent reviewer only for a named risk, with one question and a
pinned candidate; required hosted review stays with the forge.

## Land

- Batches land with `agentctl batch land <run>`. Native work lands through the
  repository's normal route: one PR per coherent change whose title is the
  permanent squash subject and whose body explains the problem, behavior,
  verification, and residuals; use the repository's template when present.
  Repositories that publish to `master` directly fast-forward instead.
- Resolve conflicts by intent, traced to each side's commits, PRs, and tasks.
  Preserve both intents where possible, never invent behavior mid-merge, and
  commit after each resolution. Grep for leftover conflict markers after any
  autostash.
- Verify actual required gates and publication before claiming the change
  landed. A stacked merge counts as landed on the default branch. Report the
  commit or PR, useful check results, and residuals without a ceremonial list.
  Preserve WIP and clean only worktrees and watches you own.
- After landing, file native task evidence with `agentctl evidence file`,
  close the tasks whose criteria the evidence meets (with PR and merge SHA),
  carry the rest into named successors, and remove the worktrees you created.
