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

A checkout's first selection seeds its new target from the repository's
master-baseline checkout (Git config `sinnix.baselineCheckout`, which
`sinnix-master-baseline` sets): a reflink copy taken while holding Cargo's
build lock on the source, so it shares extents and Cargo reuses the
dependency artifacts. With incremental compilation disabled, seeding prunes
every profile's `incremental/` tree,
including cross-compilation profiles. Cargo test scratch in `target/tmp/`
and `.rustc_info.json` are always omitted before copying. Build-script output directories remain reusable.
Disabled incremental state and checkout-specific compiler probes are regenerated.
Without reflinks, a baseline target, or the lock within
five minutes, the target starts empty. The selector writes the target's
`CACHEDIR.TAG` (Cargo tags only a target directory it creates, and this one
exists first), so worktree cleanup can retire it with its checkout.

Provisioning and target selection do not migrate warm targets or release old
snapshot references. Before activating a new cache root, inspect its existing
contents and target holders, preserve needed artifacts, then verify the installed
unit and effective target from a real declared job. Existing target leases remain
explicit until their owners release them.

Managed sessions and Cargo direnv environments default to `CARGO_INCREMENTAL=0`.
An explicit `CARGO_INCREMENTAL=1` enables incremental rebuilds and preserves
profile incremental state in new seeds. Declared AgentCTL operation values
still take precedence over inherited values. Workspace manifests own debuginfo
settings.
