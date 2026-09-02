# Sinity Environment Contract

Stable cross-project operating rules. Machine inventory, project status, job
state, and task queues are queryable (`agentctl`, project MCPs); do not
duplicate them here. Project semantics live in each repository's `CLAUDE.md`.

## Working stance

- Be a finisher. Carry work to a verified done-state unless a concrete blocker
  remains; name the blocker and what would change it, or proceed.
- **There is no end of session.** The harness compacts and continues, so "this
  is a long session", "late in the session", or "a big change to start now" are
  not reasons and must never appear in a decision. A task that is worth doing
  is worth starting on the turn you identify it. Filing a bead instead of doing
  the work is right only when someone else must decide or the evidence is
  elsewhere — never because the work looks large from here. Context budget is
  the real constraint, it is checkable, and it survives compaction.
- A concerning discovery is the next work item, not a stopping point. Check the
  fact that decides the question, not a proxy for it. Escalate only for
  genuinely irreversible-and-ambiguous steps, missing authority/consent, or
  evidence that does not exist on this machine.
- Preserve intent; never substitute a smaller, safer, or more familiar product
  decision. Prefer one canonical route: when a replacement is established,
  remove the retired route's commands, wrappers, docs, and tests in the same
  change.
- Unfinished is not obsolete. Deleting an apparently unused path needs positive
  evidence of abandonment (shipped replacement, recorded decision, explicit
  retirement) — inspect history, tasks, and design docs first; otherwise
  complete it or file the completion.
- Work evidence-first: inspect source, live state, history, and recorded
  results rather than extending an assumption. Separate observed fact from
  inference; name what would change an uncertain conclusion.

## Scope, batching, communication

- On multi-step requests, state the understood scope and exclusions, then
  proceed. Batch related edits; diagnose the whole failure shape before fixing
  one error at a time. Don't expand scope opportunistically — record follow-ups.
- Report changed files, exact verification commands, and residual risk. Never
  claim a broad invariant from a narrow check.
- Don't truncate command output by default (`| tail`, `| grep -c`); let it
  print, or capture to a file and read deliberately, with a stated reason.
- `pkill -f`/`pgrep -f` match the invoking shell's own command line: if the
  pattern's literal text appears anywhere else in the same compound command
  (a relaunch, a grep), you kill your own shell (exit 144). Issue `pkill -f`
  as a standalone command with one character bracketed (`'app[.]py'`).
- Load the `writing-style` skill for human-facing prose (issues, PRs, commits,
  docs, chat).

### Say less — especially in artifacts

Endemic failure: narrating instead of stating. Worst in durable text (code
comments, CLAUDE.md, contracts, bead descriptions, PR bodies), where every
future reader pays the cost.

- **Comments state constraints, not history.** Why this must hold, or a
  non-obvious invariant. Never what happened, who found it, when, or how many
  attempts it took. `# 2026-08-26: caught after two lanes both...` is noise.
- **Docs and contracts are reference, not retrospective.** Say what to do and
  what is true. Incident stories belong in the bead or the retro, cited by ID
  if needed at all.
- **Beads: problem, evidence, wanted outcome.** Reproduction over narration.
  No "MEASURED TRUTH" preambles, no session storytelling, no restating the
  same finding in three registers.
- **PR bodies: what changed, why it is correct, residual risk.** Not the
  review's plot.
- **One statement per fact**, everywhere. Do not restate a conclusion in a
  summary line under it.
- **A fix leaves no scar.** Once a mistake is corrected, the correction is the
  only thing worth writing: state what is true now. "Dispatch is a verb" —
  never "a verb, not a script", never a warning against the retired route,
  never a dated note about who got it wrong. Naming the wrong path keeps it
  alive in every future reader's context and half-reads as an instruction.
  Guardrails against genuine harm are the exception, and they are short.
- In chat: answer, don't preface; report outcomes, not journeys; no
  self-congratulation ("damning", "textbook", "earned its keep").

Write it once, in the shortest form that survives without you.

### Don't coin vocabulary

These documents are agent-authored, so invented terms accrete: a phrase gets
used twice, then cited, then treated as canonical, and every later reader pays
to decode it. Use ordinary words.

- Before naming a concept, check whether plain English already says it. "The
  publication queue is invisible" beats coining a term for it.
- A new term earns its place only if it names something real that is genuinely
  awkward to say otherwise, AND it is defined where it is first used. Otherwise
  write the idea out.
- Never define a term in one document and use it undefined in another.
- Domain words with outside meaning (worktree, squash-merge, cgroup,
  idempotent, fail-closed) are not jargon — use them freely.
- Deleting a coined term is not a loss of precision if the sentence still says
  the same thing in plain words. It usually does.

## Machine and filesystem orientation

Host `sinnix-prime`: i7-13700K, RTX 3080, 32 GB, NixOS unstable. Root SATA SSD
is wear-limited — no gratuitous writes; NVMe is `/realm`.

- `/realm/project/` — active repos (sinnix, polylogue, sinex, sinity-lynchpin…)
- `/realm/data/` — canonical personal data lake (read for evidence; write only
  through owning tools; see `/realm/data/INVENTORY.md`)
- `/realm/state/` — live service state (polylogue archive, external task DBs
  under `/realm/state/tasks/<project>`)
- `/realm/tmp/work/` — throwaway analysis output (aged 30d); never heavy work
  in `/tmp` (small tmpfs). `/realm/worktrees/` — compile-heavy checkouts.
- Downloads land in `/realm/inbox/download`; query freedesktop dirs with
  `xdg-user-dir`, don't assume `~/Downloads`.
- Home is impermanent (rebuilt each boot from `/persist` + Home Manager).

Rebuild sinnix ONLY via its devshell wrappers (`switch` / `boot` / `test-vm`,
or `cd /realm/project/sinnix && nix develop --command switch`) — never bare
`nh os switch`; the wrapper owns idle scheduling and the build slice.

## Runtime and workspaces

`agentctl` is the one interface for durable machine work, workspaces,
coding-agent jobs, and task backends (verb surface: `agentctl --help` — it
grows; don't cache it). Load the `agent-runtime` skill before nontrivial
runtime/workspace operations and `orchestrate` before multi-agent work.

- Ordinary short foreground commands run directly. Detached, queued,
  resource-heavy, or shared work goes through declared project operations:
  `agentctl job start <project> <operation>`.
- Never hand-construct `systemd-run`, cgroup placement, memory envelopes, or
  background reapers; never infer ownership from process names — act on
  returned job/workspace/session IDs and preserve them in reports.
- Don't duplicate a heavy job; attach to the identical active operation.
- Every agent dispatch names backend, model, and effort explicitly.
- Checkpoint a workspace before risky integration, compaction, or recovery.
- Authority map: Git = commits/worktrees; systemd = live processes; GitHub =
  PR/review/merge; the external task backend (`bd`, Beads per
  project under `/realm/state/tasks/`) = task state. Reconcile disagreements;
  never invent a second truth. Feature branches never carry task state.
- Long-running dispatches carry a time contract: state expected duration with
  evidence and act at ~2x with a decision, never silent waiting. Completion
  notifications are authoritative; do not poll.

## Campaign coordination (stateless takeover)

When coordinating a lane campaign (any project), the protocol and live state
live OUTSIDE your context — read them, never reconstruct:

- **Protocol**: `/realm/project/sinnix/dots/_ai/skills/orchestrate/references/coordinator-contract.md`
  — start with its capability table, which names the `agentctl` verb for each
  need so you do not hand-roll a worse copy. Worker rules in its sibling
  `worker-contract.md`.
- **Live state**: `agentctl campaign status` is the lane view; `sinnixd-reactor`
  dispatches each lane's next action and logs its refusals to
  `/realm/tmp/work/campaign-board.json`.
- **Dispatch**: `agentctl campaign run` for a wave, `packet launch` for one
  bead. **Harvest**: the declared `harvest` operation — review receipt, then
  authorize to publish. `agentctl --plain` prints payloads as text.
- A fresh session resumes a campaign from those files plus the project's
  memory index; nothing campaign-critical may live only in a chat context.

## Ambient control (browser, desktop, terminal)

One browser — the operator's Chrome, CDP on `127.0.0.1:9222`, shared profile.
"Your/agent browser" → `sinnix-chrome-control agent-window` (hidden workspace,
F7 toggles). "My browser/tabs" → act on his existing pages, high authority,
never navigate/close what he is using. Desktop → `sinnix-hypr-control`,
`sinnix-keyboard-control`, `sinnix-screenshot-control`; terminals →
`sinnix-kitty-control` first. Load `desktop-control-plane` for recipes.
`sinnix-observe` gives a live correlated probe.

## Evidence planes

Control plane for action; evidence plane for history — never reconstruct
history from the current screen when a store answers directly:

- AI-session history → Polylogue (MCP/CLI; raw JSONL under
  `~/.claude/projects/` as fallback).
- Cross-source personal/system history → Lynchpin.
- Host/runtime truth → `/etc/sinnix/runtime-inventory.json`, `sinnix-observe`,
  `/realm/data/captures/**`.
- Operator stream → `/realm/data/knowledgebase/logs.raw-log.md` (rawlog).

Look history up proactively on "remember when…", after compaction, or when an
error feels previously solved; write durable insights down (scratch note,
memory, or the owning CLAUDE.md) instead of re-deriving next session.

## Git and publication

- Feature branches unless the repo explicitly publishes from its default
  branch. Stage by path; inspect `git diff --cached`; never `git add -A` on
  significant changes; never `--no-verify` unasked.
- Treat tracked files, commits, task exports, CI logs, and PR text as public.
  Never commit secrets, captures, transcripts, personal datasets, or generated
  personal analyses; review the complete staged diff as public content.
- Preserve user work: dirty trees are normal; state destructive intent before
  any delete/reset/force-push/rewrite/kill. Clean up your own transient
  artifacts (stashes, scratch branches) once verified captured elsewhere.
- Publish/land through `agentctl workspace publish|land` where the project
  adapter provides them; never bypass hosted checks or protected-branch policy.
  Load `review-land` for adversarial review + publication procedure.

## Verification

- Tests protect behavior, contracts, invariants, reproduced bugs, and security
  boundaries — never textual fossils of a refactoring diff, and never
  pattern-matching of natural language as enforcement.
- Selected/affected verification proves only its selected scope; a full corpus
  is a deliberate batch/master checkpoint. Never launder selected greens into
  whole-suite claims.
- Classify inherited failures before claiming completion; state exactly what
  ran and what did not.

## Investigation and recovery

Freeze volatile evidence before mutation; reproduce the user-visible route;
for recovery inspect live state → Git/checkpoints → task/history stores →
backups, verifying restored content before deleting sources. Load
`investigate` for incidents and ambiguous recovery.

## Memory

Persistent memory lives per-project under `~/.claude/projects/<p>/memory/`
(one fact per file, indexed one line each in `MEMORY.md`; superseded material
goes to `archive/`). Update or delete stale memories on contact; verify a
recalled mechanism still exists before recommending it.
