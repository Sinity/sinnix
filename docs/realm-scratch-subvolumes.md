# Realm scratch subvolumes

`realm-scratch-subvolumes.service` converts classified regenerable directories
on Realm into nested Btrfs subvolumes during early boot. Btrbk snapshots the
Realm top subvolume (`subvolume .`); nested subvolumes appear as empty directory
boundaries in those snapshots. Subsequent writes and deletions in scratch no
longer stay pinned by Realm snapshots awaiting the Borg drain. Existing
snapshots retain their original contents until the normal backup drain removes
them.

The path list is declared in `modules/lib/storage/scratch-roots.nix`; the
service in `modules/lib/storage/scratch-subvolumes.nix` is imported by storage
infrastructure for Btrfs Realm mounts. A backup assertion requires every root
to remain both Borg-excluded and classified as regenerable.
Every target is an exact root already excluded by `realmExcludes` in
`modules/backup.nix`:

- `tmp`, `worktree`, the historical `worktrees`, and `state/cache`.
- Cargo targets in Polylogue, Polylogue-Sinex Common, Sinex, and the two Spec
  build roots.
- Stash's `state/stashbox/analysis-cache` and `state/stashbox/generated`.

Missing paths are skipped. Core tmpfiles rules use `v` for `tmp`, `worktree`,
and `state/cache`, creating subvolumes on fresh Btrfs installs while preserving
existing directories and subvolumes. Other targets remain owned by their
producers. No persistence bind redirects these roots.

The service requires `realm.mount` and runs before `local-fs.target`, tmpfiles,
Realm scaffolding, the operator's user manager, and every declared filesystem
mount below or sourced from a target. This includes the Polylogue pytest tmpfs
and `/var/cache/sinex` bind. Ordinary system services start after sysinit;
user services and Pueue start under the user manager. `DefaultDependencies=no`
avoids a dependency cycle with the early filesystem phase. It is wanted,
rather than required, by `local-fs.target`, so failure is recorded in the
journal and boot continues. Manual starts are refused, switch does not restart
it, and the command also refuses to migrate after `basic.target` has started.
Activation installs the policy; migration happens on the next boot.

For an ordinary directory the command creates `<path>.subvol-new`, uses
`cp -a --one-file-system --reflink=always`, and snapshots any existing nested
subvolumes into their corresponding positions. This retains nested subvolume
boundaries, No_COW flags, and read-only properties without copying file data.
Empty destination files first receive matching No_COW flags, as Btrfs refuses
reflinks between CoW and No_COW files. A reflink failure aborts preparation. File ownership, permissions, timestamps,
links, and extended attributes are preserved. Mounted trees and bind sources
are rejected.

After preparation is flushed, `renameat2(RENAME_EXCHANGE)` atomically exchanges
the old directory and prepared subvolume. The public path always names a
complete tree. The old tree is renamed to `<path>.pre-subvol-<UTC timestamp>`
and deleted, including its nested subvolumes. Before the exchange, any error
leaves the original untouched and removes the preparation. After the exchange,
the replacement holds all contents; a cleanup failure retains the old tree or
preparation path for reconciliation. A crash can leave those artifacts too.
An already converted root is a no-op. An ordinary root with migration artifacts
is refused on subsequent boots; inspect the journal and both trees before
recovery. Never start this migration against active worktrees or caches.

## Verification

Build the isolated loopback-Btrfs VM check and inspect the rendered host unit:

```sh
nix build --no-link -L .#checks.x86_64-linux.realm-scratch-subvolumes
nix eval --raw '.#nixosConfigurations.sinnix-prime.config.systemd.units."realm-scratch-subvolumes.service".text'
```

After the coordinator installs the intended revision and reboots:

```sh
nixos-version --configuration-revision
systemctl show realm-scratch-subvolumes.service -p Result -p ExecMainStatus -p ActiveState
journalctl -b -u realm-scratch-subvolumes.service
sudo btrfs subvolume show /realm/tmp
sudo btrfs subvolume show /realm/worktree
sudo btrfs subvolume show /realm/state/cache
# Only if the historical path exists:
if test -e /realm/worktrees; then sudo btrfs subvolume show /realm/worktrees; fi
sudo btrfs subvolume list -o /realm
findmnt --mountpoint /realm/tmp/polylogue-pytest
findmnt --mountpoint /var/cache/sinex
```

Run `btrfs subvolume show` for each existing additional target from the module
list as well. Inspect the _next scheduled_ btrbk snapshot after reboot (do not
select an older snapshot):

```sh
sudo btrbk list snapshots
# Set this to the exact new Realm snapshot path reported above:
snapshot=/realm/.btrfs/snapshot/realm.YYYYMMDDTHHMMSS+ZZZZ
for relative in tmp worktree worktrees state/cache \
  project/polylogue/repo/target project/polylogue-sinex-common/repo/target \
  project/sinex/repo/target \
  state/stashbox/analysis-cache state/stashbox/generated; do
  if test -d "/realm/$relative"; then
    sudo test -d "$snapshot/$relative" || exit 1
    entries=$(sudo find "$snapshot/$relative" -mindepth 1 -maxdepth 1 -print -quit) || exit 1
    test -z "$entries" || exit 1
  fi
done
```

The directory boundary remains; its contents must be absent. This live check
establishes exclusion by the real snapshot producer. The VM check proves
content and metadata preservation, nested subvolume handling, idempotence,
snapshot exclusion, and refusal on preparation failure, active mounts, symlinks,
and interrupted preparations.
