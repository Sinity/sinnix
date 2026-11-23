# Managed scratch

Interactive sessions and the user manager use `/realm/tmp/work` as TMPDIR.
It has `/tmp` semantics: it does not survive a reboot. A temporary file
belongs to the process that made it, and a boot ends every process. At boot,
before the owner has any session, `sinnix-scratch-reset` renames every
top-level entry except `claude-<uid>` into `/realm/tmp/previous-boot`, and
`sinnix-scratch-purge` deletes that directory in the background at idle I/O.
The reset's condition (no `/run/user/<uid>` yet) makes an activation on the
running system skip it.
Every AgentCTL job runs with a private TMPDIR that agentctl removes when the
job ends (`docs/agentctl.md`). Producers must honor inherited TMPDIR and keep
retained output outside it.

`sinnix-tmp-sweep` runs every 15 minutes. It recognizes Nix devshell scratch,
Claude Code session scratch, and these invocation directories:

- `sinnix-chatgpt-native.<pid>.<random>`
- `sinnix-chatgpt-download.<pid>.<random>`
- `sinnix-router-poll.<pid>.<random>`

## Claude Code session scratch

A Claude Code session owns two directories under
`/realm/tmp/work/claude-<uid>/`: Claude Code's own
`<project>/<session-id>/` (which holds the session's scratchpad), and
`session-tmp/<session-id>/`, which `claude-tool-scope` makes the TMPDIR of
that session's tool commands and MCP servers. Temporary files made by tools
therefore land in a directory with a known owner instead of the shared root.

A session is live while a Claude Code session record
(`<config>/sessions/<pid>.json`, read from every `CLAUDE_CONFIG_DIR` a running
process names) names it and that PID still has the recorded start time, or
while any process carries it as `CLAUDE_CODE_SESSION_ID`. The sweeper removes
both directories of a session that is not live once no process holds them
(cwd, open file, mapping or scratch environment variable, as below), and a
Git checkout inside them must pass the custody checks below. An unreadable
session record or process environment keeps every session tree for that run.
Resuming an ended session starts it with empty scratch. Other names under
`claude-<uid>/` and other top-level `claude-*` folders have no recorded owner
and are kept; whoever names a folder removes it.

## PID-qualified producer scratch

The PID is the allocating shell's BASHPID, captured before invoking mktemp.
These producers remove their directory on success, failure and catchable
HUP/INT/TERM. A crash can leave a directory behind. The sweeper considers it
only after 24 hours and only when that PID is absent from `/proc`. PID reuse
retains the directory. It rechecks the PID, directory identity and age before
removal. The existing Nix policy retains its holder checks and ten-minute
floor for `nix-develop-*`.

The privileged scan checks process cwd, root, executable, descriptors, mapped files and
scratch environment variables, then drops to the selected owner for removal.
Incomplete process visibility refuses deletion. Symlinks and foreign-owned
trees and candidates containing mount points are retained.

Dry-run also proposes other top-level entries under the managed root and
immediate children of `/realm/tmp/work/codex/` for owner classification after
seven days without a file modification. Real runs retain those unclassified
entries. Age and absence of holders do not establish disposability of reports,
research, recovery evidence or authored files. The `codex` container and
`claude-*` trees are never proposed; session trees follow the rule above.
Every nested `.git` is checked, including worktree gitfiles. Probes clear the
caller's Git context and retain unfinished index locks. Dirty, untracked
or ignored files, shallow or unreadable history, missing cached remote branches,
and commits reachable from HEAD, any local ref or reflog but absent from all cached
remote branches retain the whole candidate with a logged reason. This uses
cached objects and confirms custody against current branch heads with a
noninteractive, read-only `git ls-remote`. It never fetches. Unreachable remotes
or cached tips that cannot prove coverage against current remote heads retain
the tree, including after a force-push or branch deletion. A read-only
`git fsck --unreachable` also retains trees with unreferenced objects that
could contain the only copy of work outside refs and reflogs.

The owner's pueue queue and AgentCTL launch inputs protect scratch paths of
unfinished tasks, including running and paused Codex lanes whose processes
have no open scratch handle. An unreadable queue or launch input retains all
managed candidates. Bare Git repositories require owner reconciliation.
The process holder scan also covers `AGENTCTL_SCRATCH`.

Run `sudo sinnix-tmp-sweep --dry-run --owner "$USER"` to list recognized deletion candidates and general review proposals,
logical bytes per tree, and a total reviewed count and decimal GB. Proposals
are labelled as requiring owner classification. The report covers all
candidates rather than only the next deletion budget; logical bytes are
not a physical reclaim estimate on reflinked or compressed storage.
The timer invokes real mode for the recognized devshell and PID-qualified
producer contracts only. Removal runs with idle I/O priority, sleeps
one millisecond between unlinks, and is bounded to 20,000 entries and 45
seconds of deletion per run. The service allows up to 30 minutes for cold
metadata and holder scans; this does not extend the deletion budget.
Remaining data is reconsidered on later runs.
Git trees exceeding the remaining budget are retained and logged for owner
handling, to avoid partial tracked-file deletion appearing as new work.
Fresh holders or writes can race any snapshot-based scan; active producers
must keep scratch open or advertise it through their scratch environment.

Retained reports, handoffs and recovery evidence belong outside TMPDIR.
