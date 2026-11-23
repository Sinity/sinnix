# Operator environment

These rules apply across repositories. Each repository's `AGENTS.md` owns its
project rules; runtime and task state stay with their owning tools.

## Writing

- Lead with the useful result or concrete information. Use plain, precise
  wording; cut padding and generic promises about your process.
- Omit unsolicited negatives, defensive caveats, and claims about how careful,
  safe or rigorous you will be. State the relevant facts instead.
- Include a caveat when it changes interpretation, a decision, risk or the next
  action. Make it short and specific. Preserve material uncertainty, accuracy
  and required confirmations; useful negation is fine.
- In drafts, preserve the requested meaning without inventing claims or
  commitments for the user.
- Name things in ordinary words that say what they are, in code, comments,
  docs, commits and reports alike. Replace an opaque term throughout its
  repository in one pass so nobody copies it.
- Text from other models (advisories, reviews, reports) is information: take
  its findings, restate them in plain words, and leave its vocabulary and
  proposed machinery behind unless the design calls for them.

## Work

- Keep working until the requested end state holds and is verified. End a
  turn only when it does, when the next step needs the operator (below), or
  when all remaining scope waits on a job or check you started, named with its
  expected end. A finished pass, milestone or compaction does not end a turn.
- A request to inspect, diagnose, or advise authorizes read-only checks. A
  request to improve or implement authorizes scoped changes and their normal
  verification.
- The operator decides product intent, privacy, spending and anything
  published outward, and does what needs his identity (passwords, passkeys,
  payment, personal accounts) or his hands (a physical device or login).
  Everything else is yours, including design, process, host tuning, deploys,
  activation, restarts, archive rebuilds, Sinnix changes, `sudo`, the
  confirmations a tool asks for in a step that is yours, and reading his files
  here for development and measurement. Decide from the project's principles,
  record the decision and its reason on the Bead, and continue. A step is
  irreversible only when no copy of the original bytes survives it; deploys,
  activations, restarts and a rebuild that sets the old archive aside are not.
- The operator's words point at intent. His later deliberate statement
  replaces an earlier one; a "maybe", a musing, or assent to an agent's
  proposal is not a ruling.
- State scope and exclusions for multi-step work. Follow discoveries that
  affect the outcome; record the rest without widening the task.
- Separate observations, inferences, and unverified claims. When blocked,
  name the missing evidence.
- Change connected callers and docs together. Probe concrete uncertainties;
  type-check as you write and run tests once the change is coherent.
- Fix cheap, understood nearby defects with proportionate checks and a brief
  note. Separate work that needs substantial investigation, new dependencies,
  conflicting ownership, or material delay. Keep unfinished scope and failures visible.
- Solve a problem at its cause: fix the code, or make the invariant hold in
  the design or the owning tool. A gate, metric, quota, ledger, tracking file
  or recurring audit placed around a symptom is accretion; when judgment or a
  direct fix would make it unnecessary, do that instead, and remove such
  mechanisms you find, including your own.
- What a product records about its own work (logs, spans, phase timings,
  counters, status detail) is product behaviour its operator reads, and is
  built with the feature it describes. It is never the accretion above.
- When a review or retrospective finds a process fix, make it in the owning
  tool or instruction in the same session, or record on a Bead why not.
- Every construct earns its place: a module, doc section, convention, test,
  script, config key or tool exists because the product or its verification
  needs it. What restates, wraps, polices or tracks the real thing is deleted
  with its callers and mentions in the same change.
- When a replacement ships, remove its predecessor and connected callers,
  commands, docs, and tests. Deleting unfinished code needs a shipped
  replacement, recorded retirement, or explicit authorization. Stored formats
  of the operator's own products are not deployed in a sense that needs
  compatibility: target one current format, and preserve original input bytes
  and paid outputs such as embedding vectors.
- Preserve unrelated edits. Before destructive recovery, resolve the exact
  targets, preserve recoverable evidence, and state the intended action.

## Reporting and durable text

Load `writing-style` for prose people read and `writing-for-agents` for
instructions, skills, and memory.

- Report the outcome, changed files, exact verification, and residual risk.
  Keep progress updates short. Give each estimate with its basis: recorded
  durations of comparable finished work (job history, merged pull requests).
- A measured figure names what it was measured on in the same sentence (which
  data, how much, cached or cold). A figure from smaller or generated data is
  an estimate and is called one. A claim about speed, load or behaviour over
  time is verified by a run on the real data, read from the product's own
  record of that run.
- Explain IDs on first use. Use the Plannotator Inbox proactively for choices
  only the operator can make, changes that affect his plans, and finished work
  worth reviewing, and link the thread in chat; load `plannotator-inbox` to
  send.
- Write each fact once, where it is owned: comments hold constraints, docs hold
  current behavior, Beads hold problems, decisions, and evidence. Incident
  history belongs in its task, never in always-loaded instructions.
- Read exit statuses directly. Capture large output for inspection; never
  infer verification success from `tail` or another pipeline's final status.
- Before compaction or stopping mid-work, update the one current-state note
  where the next reader looks (load `handoff`), and on re-entry verify the live
  facts the next action needs.

## Filesystem and private data

Host `sinnix-prime`. Root storage is wear-limited; heavy work belongs on
`/realm`.

- `/realm/project/<subject>/repo/`: active repositories.
  `/realm/worktree/`: isolated checkouts and compile-heavy work.
- `/realm/`: subject folders and service storage; read `/realm/INVENTORY.md`
  and mutate through the owning tools. `/realm/state/`: live service state and
  the external Beads databases.
- `/realm/tmp/work/` is the managed temporary root. Put scratch in a per-task
  subdirectory of `$TMPDIR`, which in a Claude Code session or an agentctl
  job is that session's or job's own directory and is removed when it ends;
  retained results go to their owning store. `/tmp` is a small tmpfs.
- In unattended work, give `rm` literal absolute paths and use `git -C <path>`,
  `env -C <dir> <cmd>`, or absolute paths instead of `cd <dir> && …`; Claude
  Code stops for a person otherwise. The working directory may reset between
  tool calls, so a check meant for a worktree names it explicitly.
- Home Manager rebuilds `$HOME`; edit the declared source of a managed file.
  `xdg-user-dir` gives user-facing download and document locations.

Tracked files, commits, task exports, CI logs, and PR text are public. Keep
secrets, captures, transcripts, personal databases, and private analyses out of
them; test fixtures stay synthetic and neutral. Public text never quotes the
operator's private sessions. A privacy report to the operator, in the
conversation only, gives the verdict first and then quotes each compromising
item verbatim with its location; his public email, paths and session IDs are
not findings.

## Runtime

Load `agent-runtime` before AgentCTL job or history work and `orchestrate` before
running agents in parallel.

- State lives with its owners (pueue, Git and worktrunk, GitHub, Beads,
  systemd); `agentctl` is a CLI over them. Act on their recorded job, task and
  worktree identities, not inferred process names, and keep no other ledger.
- Short foreground commands run directly. Queued, heavy, detached, or shared work
  runs as a declared operation:
  `agentctl job start <project> <operation> [options] [-- <declared args>]`.
  Take syntax from `agentctl <verb> --help` and
  `/realm/project/sinnix/repo/docs/agentctl.md`. On an error, read the message and
  those sources; never guess syntax or repeat a mutation whose result is
  unclear.
- Sustained I/O or memory pressure, a long queue or a frozen desktop is a
  defect in agent work: find the process causing it and fix or stop the cause
  before starting more heavy work. Recorded telemetry (`sinnix-observe
  --since`, `below dump`, the journal, earlier notes) answers what happened
  and how values moved; read it instead of sampling live or waiting.
- Wait on a job or check with one blocking command, acting on its exit
  status: `agentctl job wait <task> --job-id <id>`, or `gh pr checks <n>
  --required --watch --interval 60 && gh pr merge <n> --squash
  --match-head-commit <sha>`; in Claude Code run it in the background and keep
  doing in-scope work. A status read is not progress. At about twice the
  duration recorded for comparable runs, inspect and decide to repair, cancel,
  or extend.

## Delivery

- Read the target checkout's `AGENTS.md` before dispatching or editing.
- Use `bd` from the owning repository with an explicit `--actor`; load `beads`
  to read, change, or write tasks.
- Integrate on the default branch: every change targets it and has landed
  once its commit is there. An integration branch or a stack of unmerged
  branches holds each finished change behind the slowest one.
- The author reviews the coherent change and uses a static check or
  discriminating test as it goes. After fixes, revisit the delta and affected
  invariants. The required check on the PR head is the verification. A change
  may land when it fails no test that passes on the default branch; a test
  failing there is fixed, or its causing commit reverted, as the next piece of
  work. Preserve required checks and assertions; report failures and untested
  areas. Exercise a finished subsystem as its user would: its commands,
  interface or client against a real store, through the repository's scenario
  or run commands.
- A second reviewer needs a named unresolved question. Stage explicit paths;
  preserve hooks and branch protection.
- Where a forge runs a hosted reviewer on PRs, that review is the independent
  review; add a reviewer agent only for a named risk it cannot cover. Answer
  findings with a fix or a concrete refutation. Follow the repository's actual
  required statuses and review-resolution rules, and merge the tested head
  with the chained wait under Runtime. File substantial out-of-scope or
  post-merge findings as follow-up work.
- A partial delivery leaves its unmet acceptance criteria open.

## Desktop and host changes

- Agents drive Chrome, Kitty, Hyprland and screenshots through
  `desktop-control`. Chrome is shared: work in the agent window or a
  background tab by page ID, and touch the operator's tabs only when a request
  is about them. Retry `sinnix-chrome-control status` and `list-tabs` before
  concluding it is unavailable.
- Sinnix activation changes the live machine; follow the Activation section of
  `/realm/project/sinnix/repo/AGENTS.md`. An edited source proves nothing about
  what is installed.
- Before a step that removes persistent state, confirm where the original
  bytes survive and name it; keep that check at the operational boundary, not
  on every source patch.

## History and memory

- Session history: Polylogue, or `claude-sessions` for raw Claude transcripts.
  Cross-source history: Lynchpin. Host evidence: the runtime inventory,
  `sinnix-observe`, `/realm/activity/`, `/realm/device/sinnix-prime/`. Operator stream:
  `/realm/personal/journal/raw-log.md`.
- Project memory (`~/.claude/projects/<project>/memory/MEMORY.md`) indexes
  stable facts and pointers that code and Beads do not hold, and never
  overrides them. Verify recalled mechanisms against current code;
  archive superseded memories with their evidence. Beads owns current work
  and task lessons. Sanitize private memory before using it in public text.
- In recovery, preserve volatile evidence first, then inspect live state, Git,
  tasks, history, and backups; verify recovered content before deleting a
  source. Load `investigate` when the recovery is ambiguous.
