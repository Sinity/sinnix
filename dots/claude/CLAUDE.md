# Sinity Environment Contract

Stable cross-project operating rules. Machine inventory, project status, job
state, and task queues are queryable (`agentctl`, project MCPs); do not
duplicate them here. Project semantics live in each repository's `CLAUDE.md`.

## Working stance

- Be a finisher. Carry work to a verified done-state unless a concrete blocker
  remains; name the blocker and what would change it, or proceed. Session
  length is never a reason to defer — context budget is, and it is checkable.
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
- Load the `writing-style` skill for human-facing prose (issues, PRs, commits,
  docs, chat).

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
  PR/review/merge; the external task backend (`agentctl task …`, Beads per
  project under `/realm/state/tasks/`) = task state. Reconcile disagreements;
  never invent a second truth. Feature branches never carry task state.
- Long-running dispatches carry a time contract: state expected duration with
  evidence and act at ~2x with a decision, never silent waiting. Completion
  notifications are authoritative; do not poll.

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
