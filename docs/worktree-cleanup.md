# Worktree cleanup

The daily `sinnix-worktree-reap` user service asks Worktrunk for worktrees integrated into each repository's default branch. Candidates must be at least one day old. Worktrunk recognizes merged, cherry-picked and squash-merged changes; an unmerged checkout stays registered.

Before each foreground removal, the command checks tracked, untracked and ignored files, refreshes integration, scans current process working directories, and rereads Git's worktree registration. Locked checkouts stay. Claude session locks are released only when the recorded PID is gone or its start time differs. An unreadable owner remains unknown and stops that repository's cleanup with a visible failure. Removal runs without force, process termination or project hooks.

Linux can hide a same-user process working directory even when its stat file is readable, for example for a non-dumpable user service manager. On a permission error, the command uses the host’s existing noninteractive sudo permission to read that one `/proc/<pid>/cwd` link. It adds no sudo policy. If that read also fails for a process that still exists, cleanup stops with a visible failure. Processes belonging to other users are outside this user service's observable session boundary. The scan checks working directories, not arbitrary open files or an application’s unsaved buffers. A process can still enter a checkout after the final probe; these checks do not reserve directories against arbitrary concurrent users.

Directories under `/realm/worktree` without `.git` are reported and retained with their permissions unchanged. Git's normal worktree removal deletes both the directory and its registration. A directory without `.git` therefore needs a separate ownership decision before deletion. Worktrunk owns its own removal trash and recovery semantics.

Failures are printed to the service journal and produce a nonzero exit status. Retained checkouts whose top-level directory is older than fourteen days are also reported for inspection; directory age alone does not establish inactivity or integration.

Run the isolated fixtures with `python3 scripts/tests/test_worktree_reap.py`, or use the `worktree-reap` flake check. The fixtures cover integration, retained files and locks, fresh process checks, unknown directories and visible command failure. They never invoke production cleanup.

## Compiler targets

The host's `sinnix-cargo-cache.service` provisions `/realm/state/cache/cargo`
as a nested Btrfs subvolume. It refuses an existing ordinary path or symlink;
activation must reconcile that path separately rather than convert or delete it.
Parent Realm snapshots retain worktree source and WIP without retaining this
subvolume's compiler outputs. Borg's existing whole-worktree exclusion remains
separate from local snapshot coverage.

`sinnix-cargo-target` selects a stable per-checkout target there. Its installed
default and the provisioning unit use the same configured Realm root. Polylogue and
Sinex devshells use it when installed; other hosts retain the ordinary `target/`
fallback. Explicit `CARGO_TARGET_DIR` values keep their existing lease. Direnv
uses the same selection for both projects, and AgentCTL forwards their declared
inherited target through `nix develop --command`. Devkit resolves Cargo's actual
target for test/report handling. Durable run history, Sinex service/test state
and independently retained historical binaries keep their current owners.

Every selection adds to the target, by reflink, the dependency units it
lacks. Cargo names each unit's outputs (`<profile>/.fingerprint/<package>-<hash>`,
`build/<package>-<hash>`, `deps/*-<hash>*`) by a hash of everything that decides
them: package source and version, features, profile, flags and toolchain. A
unit another target built is therefore exactly the one this target would build.
Sources are the repository's master-baseline checkout (Git config
`sinnix.baselineCheckout`, which `sinnix-master-baseline` sets), then the three
most recently built targets of other worktrees. A new checkout starts with every
dependency warm. When a rebase brings a profile, flag or toolchain change, the
lane's next job finds the new generation that the baseline already built, instead
of recompiling about 600 dependencies.

Only units of registry and Git packages are added. Units of path packages (those
without `source` in either `Cargo.lock`: workspace members and local patches) are
never copied. Cargo treats them as fresh when their dep-info is newer than their
sources, so a copy built in another checkout after this one's files were written
would pass for current code that differs. A source is read, and the target
written, only while each one's Cargo lock (`<profile>/.cargo-lock`) is free; a
busy one is retried at the next selection. A unit's outputs are copied before
its fingerprint, so an interrupted copy leaves units Cargo rebuilds. Units already
present are never replaced. Per source and profile, `.sinnix-merged/` in the
target records the source's `.fingerprint` mtime at the last complete merge, so a
selection reads a source again only after it has built a new unit.
Incremental state, uplifted outputs, Cargo test scratch in `target/tmp/` and
`.rustc_info.json` belong to no unit and are never copied.
Without reflinks or an idle source the target keeps what it has. The selector writes the target's
`CACHEDIR.TAG` (Cargo tags only a target directory it creates, and this one
exists first), and on every selection rewrites `checkout` beside the target
with the checkout path. That marker's mtime is the target's last selection.

The hourly `sinnix-cargo-target-evict` user service removes targets in the
background resource class. A target is idle for the newest of its marker,
target and profile `deps/` mtimes, and is never removed while any of its
Cargo build locks is held or within `minIdleHours` of use. It removes:

- a target whose marked checkout no longer has `.git`;
- a target idle longer than `maxIdleDays` (unmarked targets fall under this
  rule only), except a repository's master-baseline target, which supplies
  other targets' dependency units and is rebuilt only when the default branch moves (filesystem
  pressure still removes it);
- while the cache filesystem is fuller than `maxFilesystemUsePercent`, idle
  targets least recently used first, rereading usage after each committed
  removal. Targets share reflinked extents, so the filesystem's usage, not a
  per-target size, measures what removal frees.

The budgets are `sinnix.features.dev.languages.cargoCache` options; hosts set
their own. A target is renamed under its build lock before deletion, so a
build that starts later selects a fresh target.

Provisioning and target selection do not migrate warm targets or release old
snapshot references. Before activating a new cache root, inspect its existing
contents and target holders, preserve needed artifacts, then verify the installed
unit and effective target from a real declared job. Existing target leases remain
explicit until their owners release them.

Managed sessions and Cargo direnv environments default to `CARGO_INCREMENTAL=0`.
An explicit `CARGO_INCREMENTAL=1` enables incremental rebuilds. Declared AgentCTL operation values
still take precedence over inherited values. Workspace manifests own debuginfo
settings.
