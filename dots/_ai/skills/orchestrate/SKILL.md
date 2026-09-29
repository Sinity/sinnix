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
  implementation. Give each one its own worktree (under `/realm/worktrees/`)
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
    inherit bias) or a different model is needed; Fable costs most and needs
    a stated reason. Every non-fork dispatch passes an explicit `model`; the
    dispatch hook refuses one without it.
  - In Codex, native spawn takes `model`, `reasoning_effort`, and `fork_turns`
    (`'none'` by default; `'all'` for deliberate full-history inheritance,
    with no model or effort override).
- **AgentCTL batch** (`agentctl batch start`) for independent groups that
  need isolated worktrees on one base, unattended queueing, or an explicit
  backend. Its landing task integrates, checks, and publishes;
  `agent-runtime` covers the batch verbs, stages, and recovery.
- Run as many owners as there are disjoint ownership groups the host can
  carry. There is no fixed worker count, and no worker per task.

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
- The packet names the base commit, assigned tasks, the source seam,
  exclusions, the shared focused selection, and what to report. It does not
  repeat the repository's `AGENTS.md` (verification cadence, PR rules); the
  worker reads it. Pass
  pointers (task IDs, paths, SHAs), not pasted state.
- Ask the owner to read every assigned task, write the whole connected change
  in one pass, run the focused selection once, run the self-review loop of
  [worker-contract.md](references/worker-contract.md) step 4 before every push
  or result, and report each unmet criterion with its actual blocker.
  Implementation, testing, and self-review stay with one owner, never split
  into handoffs or a separate reviewer stage.
- A worker that opens a PR waits for the hosted review of its head and answers
  every thread before it reports.

## Models

| Work                                                        | Codex                | Claude   |
| ----------------------------------------------------------- | -------------------- | -------- |
| Evidence collection, supervision, settled implementation    | `gpt-6-luna`, medium | `sonnet` |
| Substantial implementation, investigation, candidate review | `gpt-6-sol`, medium  | `opus`   |
| Unresolved architecture, design-critical implementation     | `gpt-6-astra`, high  | `opus`   |

These are starting points. Raise effort or tier for a named problem, not by
default. `scripts/probe_agent_runtime.sh` checks a backend's availability and
quota before a large dispatch. [model-landscape.md](references/model-landscape.md)
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
- Subagent prompt caches last an hour; waking an agent after that rewrites
  its whole context. While agents wait on long work, schedule a 20-minute
  recurring CronCreate job that runs `claude-agents --idle 38-60 --state ended`
  and sends each agent still waiting on something the message "Cache
  keep-alive. If what you are waiting for has not arrived, reply only
  'waiting'." Delete the job when no agent is waiting.

## Integrate

Pin the candidate (`git diff <base>...<head>`), then review it on separate
axes. One passing axis does not excuse another.

1. **Scope**: every acceptance criterion is satisfied, deferred to a named
   successor, or shown to be misframed; non-goals are respected; nothing was
   quietly swapped for an easier task.
2. **Correctness**: the repository's rules first, then concrete defects with
   an input and a wrong outcome.
3. **Test honesty**: tests reach the production path at a real seam; no
   assertion recomputes its expectation the way the code does; a new detector
   has a mutation that turns it red.
4. **Operational safety**: the repository's schema and migration regime is
   followed; a deletion removes its declarations (commands, hooks, config
   keys, docs) with it.
5. **Evidence**: what actually ran, with the command and result line, what did
   not, and whether a green covered everything or only a selection.

List every defect on every axis before fixing or returning any, then fix or
return them in one batch together with their sibling sites, and recheck only
the affected evidence. The forge's hosted review is the independent reviewer
(global rules, Delivery); add a reviewer agent only for a named risk it
cannot cover, with one question and a pinned candidate.

## Land

- Batches land with `agentctl batch land <run>`. Native work lands through the
  repository's normal route: one PR per coherent change whose title is the
  permanent squash subject (72 characters or fewer, imperative) and whose body
  has Summary, Problem, Solution, Verification (exact commands and the line
  that matters), Self-review (the author's last pass), and residuals.
  Repositories that publish to `master` directly fast-forward instead.
- Resolve conflicts by intent, traced to each side's commits, PRs, and tasks.
  Preserve both intents where possible, never invent behavior mid-merge, and
  commit after each resolution. Grep for leftover conflict markers after any
  autostash.
- Before reporting a change landed, run this checklist loudly (global rules,
  Reporting):
  1. The exact head passed the repository's quick gate before it was pushed.
  2. No hosted review was running on the previous head when you pushed, and
     the push carried every open finding.
  3. The forge shows zero unresolved review threads (query it, do not recall
     it); each was answered by a fix commit or a concrete refutation.
  4. The hosted review completed on the exact head you armed. A head still
     unreviewed after its automatic re-request is reported, not waited on.
  5. Auto-merge is armed with `--match-head-commit` on that head.
  6. A stacked PR merged into its parent only with its threads resolved, and
     the work counts as landed only when
     `git merge-base --is-ancestor <merge-sha> origin/<default>` succeeds.
  7. The worktrees you created are removed, no Git process of yours is left
     holding an `index.lock`, and `git stash list` is as you found it.
  8. Every claim in the report carries its evidence: a command and its
     result line, or a PR and merge SHA.
- After landing, file native task evidence with `agentctl evidence file`,
  close the tasks whose criteria the evidence meets (with PR and merge SHA),
  carry the rest into named successors, and remove the worktrees you created.
