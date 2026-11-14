# Worktree cleanup

Checkout retirement is an explicit owner action through `agentctl worktree clean`.
Integration, age and the absence of running processes do not establish that
a checkout is released: its owner may need it between native jobs. Confirm that
work is complete and preserve its working bytes and useful compiler outputs
before requesting retirement. See [the command contract](agentctl.md) for
recovery refs and preservation checks.

## Compiler targets

The host's `sinnix-cargo-cache.service` provisions `/realm/state/cache/cargo`
as a nested Btrfs subvolume. It refuses an existing ordinary path or symlink;
activation must reconcile that path separately rather than convert or delete it.
Parent Realm snapshots retain worktree source and WIP without retaining this
subvolume's compiler outputs. Borg's existing whole-worktree exclusion remains
separate from local snapshot coverage.

`sinnix-cargo-target` selects a stable target per real checkout path there. Its installed
default and the provisioning unit use the same configured Realm root. Polylogue and
Sinex devshells use it when installed; other hosts retain the ordinary `target/`
fallback. An explicit `CARGO_TARGET_DIR` selects a deliberate distinct target. Direnv
uses the same selection for both projects, and AgentCTL forwards their declared
inherited target through `nix develop --command`. Devkit resolves Cargo's actual
target for test/report handling. Durable run history, Sinex service/test state
and independently retained historical binaries keep their current owners.

Writable targets belong to one real checkout. Even sequential reuse of a whole
target across checkouts is unsafe: Cargo's relative dep-info paths and source
mtimes can make another checkout's stale path-package build appear current.
Dependency-only seeding below preserves independent writable targets.

An empty target is seeded once, by reflink, from one idle target: the selector
tries the three most recently built targets of other worktrees and uses the
first idle one. Once the target contains build artifacts, Cargo owns
it: later selections neither add another source's units nor replace its files.

Artifact filenames are not content hashes. Builds can produce the same filename
with different metadata and dependency requirements, so independently merging
units can pair a crate with an incompatible dependency build. Seeding takes all
source and destination profile locks together and copies every output before
any fingerprint. Only registry and Git package units are copied. Path packages
(workspace members and local patches, without `source` in either `Cargo.lock`)
stay local, because another checkout's newer dep-info could otherwise make
outdated code appear current. Incremental state, uplifted outputs, test scratch
in `target/tmp/` and `.rustc_info.json` are not copied.

Without reflinks or an idle source the target keeps what it has. The selector writes the target's
`CACHEDIR.TAG` (Cargo tags only a target directory it creates, and this one
exists first), and on every selection rewrites `checkout` beside the target
with the checkout path. That marker's mtime is the target's last selection.

The hourly `sinnix-cargo-target-evict` user service removes a target only after
its marked checkout path is gone. An existing checkout keeps its target,
regardless of idle age or filesystem use; a source directory without `.git`
still counts as existing. Unknown or mismatched checkout markers are retained.
Interrupted renamed entries meet the same checks.

The grace period uses the newest marker, target and profile `deps/` mtime.
`sinnix.features.dev.languages.cargoCache.minIdleHours` keeps recently selected
or built targets after checkout removal. Cargo build locks also prevent removal.
A qualified target is renamed under its build lock before deletion, so a build
that starts later selects a fresh target.

Provisioning and target selection do not migrate warm targets or release old
snapshot references. Before activating a new cache root, inspect its existing
contents and target holders, preserve needed artifacts, then verify the installed
unit and effective target from a real declared job. Existing target leases remain
explicit until their owners release them.

Managed sessions and Cargo direnv environments default to `CARGO_INCREMENTAL=0`.
An explicit `CARGO_INCREMENTAL=1` enables incremental rebuilds. Declared AgentCTL operation values
still take precedence over inherited values. Workspace manifests own debuginfo
settings.
