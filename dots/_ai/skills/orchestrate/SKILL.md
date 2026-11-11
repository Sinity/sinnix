---
name: orchestrate
description: "Coordinate several agents on one goal: task groups, model choice, native agents, isolated worktrees, integration, verification, and publication."
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
    point (an independent review, a self-contained prompt that must not
    inherit bias) or a different model is needed.
    Pass an explicit `model` on a non-fork dispatch when the role default
    is not what you want; a fork always inherits the parent model.
  - In Codex, native spawn takes `model`, `reasoning_effort`, and `fork_turns`
    (`'none'` by default; `'all'` for deliberate full-history inheritance,
    with no model or effort override). Wait for a Codex worker with one
    `wait_agent` call whose timeout covers the work's expected duration;
    repeated short waits are polling.
- AgentCTL batch records are read-only history. Use `agent-runtime` for
  retained records and native jobs; use native agents for new work.
- Add workers only when independent work benefits from parallelism. Keep one
  owner for a small connected change; available slots are not a dispatch target.
- Concurrent agents are one shared budget (20 in Claude Code). An audit or
  investigation works in its own context and samples breadth; it starts helper
  agents only when a question splits into parts too large for one context, and
  then only a few, so other planned work still gets slots.
- Size the number of writers to what the build queue can verify. Unverified
  branches pile up and meet their errors together in one checkout, where they
  are debugged one at a time.

## Shape the work

- A task group (one worker's share) is defined by its accepted outcome: tasks that need the
  same source edits, evidence, or test selection go to one owner even when
  their file lists differ. The owner may change connected callers, tests,
  docs, schemas, and generated files to meet its criteria without asking
  again. `write_scope` is a conflict-planning estimate, not a fence; when an
  edit lands in another owner's area, keep it focused and name it in the
  report so the coordinator can order merges.
- Start independent work now. Work that builds on an unmerged change goes to
  that change's owner, or waits until the change is on the default branch:
  stacked work waits for the slower of the two and doubles conflict
  resolution. Give a shared contract one owner.
- The prompt names assigned outcomes, ownership, relevant source pointers,
  exclusions, and what to report. In Claude Code the Write tool refuses report
  files from subagents; a worker writes its report with a shell heredoc to the
  path the prompt names, then returns a short summary. Include the base and a test selector when
  needed; avoid copied instructions, complete manifests, and unchanged history.
- Ask the owner to read every assigned task, write the whole connected change
  in one pass, use proportional verification, and briefly review the delivery
  under the repository workflow. After fixes,
  review only the delta and affected invariants. Report unmet criteria honestly.
  Implementation, testing, and self-review stay with one owner, never split
  into handoffs or a separate reviewer stage.
- A worker owns its change until it is merged: when the check it needs is
  queued, it blocks on that job (`agentctl job wait <task> --job-id <id>`) and
  merges on the exact tested head, instead of ending its turn with the merge
  left to someone else. It reports useful progress while required hosted review
  is pending, then completes publication under the repository's actual gates.
  The wait and the merge are one chained command, never a hand-written
  script: `agentctl job wait <task> --job-id <id> && gh pr merge <n>
  --squash --match-head-commit <sha>`; where the forge runs the check, `gh pr
  checks <n> --required --watch --interval 60 && gh pr merge <n> --squash
  --match-head-commit <sha>`. GitHub auto-merge is not used: armed on clean,
  green heads it sometimes never fires. The watch polls once a minute because
  every agent on the account shares one hourly GitHub API limit.
- A review hold is recorded in the PR description with its open findings; the
  owner merges only the head that addresses them.
- Before merging, follow the repository's branch-update policy and let the
  forge squash it. Never build a squash commit locally on a different base
  than the branch was written on: it silently reverts whatever landed between
  the two bases.

## Models

| Work                                                        | Claude   | Codex            |
| ----------------------------------------------------------- | -------- | ---------------- |
| Evidence collection, supervision, settled implementation    | `sonnet` | everyday, medium |
| Substantial implementation, investigation, change review    | `opus`   | strong, medium   |
| Unresolved architecture, design-critical implementation     | `opus`   | strong, high     |

Codex model IDs are not repeated here: the everyday model is `model` and the
strong one `default_subagent_model` in `dots/codex/config.toml`. These are starting points; raise
effort or tier for a named problem. `scripts/probe_agent_runtime.sh` checks a
backend's availability and quota before a large dispatch, not before every
small task. [model-landscape.md](references/model-landscape.md) covers
verifying the model that actually ran, attributing outcomes, and running
allocation trials.

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
do not repeat the worker's review of an unchanged prompt. Run the full check on
the head being merged. Integration that needs repeated build-and-fix rounds
goes to a worker with a fresh context; the coordinator keeps the decisions.
Preserve stronger
evidence for actual deployment, reset, data loss, or paid vector preservation.
Add an independent reviewer only for a named risk, with one question and the
exact commit to review; required hosted review stays with the forge.

## Land

- Native work lands through the repository's normal route: one PR per coherent change whose title is the
  permanent squash subject and whose body explains the problem, behavior,
  verification, and residuals; use the repository's template when present.
  Repositories that publish to `master` directly fast-forward instead.
- Resolve conflicts by intent, traced to each side's commits, PRs, and tasks.
  Preserve both intents where possible, never invent behavior mid-merge, and
  commit after each resolution. Grep for leftover conflict markers after any
  autostash.
- Read the repository's required checks and conversation rules. Use one hosted
  review for the coherent delivery; address findings together, review the changed
  delta, and resolve threads with a fix or concrete refutation. Codex's review
  state is the Code Review row of its summary comment; its separate
  security-review usage-limit notice is unrelated. Request another
  review when protection requires it or a named new risk remains. An advisory
  review summary's commit or running state alone does not add a merge gate.
  Use the repository's protected merge route with the head commit you
  reviewed (`--match-head-commit`).
- Verify required gates and publication before claiming the change
  landed. A change has landed when its commit is on the default branch; a
  merge into any other branch has not landed. Report the
  commit or PR, useful check results, and residuals without a ceremonial list.
  Preserve WIP and clean only worktrees and watches you own.
- After landing, record the native verification and publication references in
  Beads, close the tasks whose criteria they meet, carry remaining work into
  named successors, and remove the worktrees you created.
