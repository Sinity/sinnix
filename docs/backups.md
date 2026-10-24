# Backups

Everything is backed up locally to Borg repositories on the HDD at
`/outer-realm/backup/`. Nothing is stored off-site.

## Retention

`borgbackup-maintenance` checks hourly at :50 (with up to five minutes of
jitter). A completed pass is due again after 20 hours. Lock contention leaves
it due for the next attempt; missed timer events are caught up after boot.
A completion older than 48 hours is unhealthy.

Active series retain every archive from the last 48 hours, then 14 daily,
8 weekly and 12 monthly recovery points. These are counts of periods containing
backups, not elapsed-age limits. Retired series (`sinnix-prime-realm-*`,
`sinnix-prime-persist-*`, `machine-telemetry-dumps-*`) retain six monthly
milestones; archives older than 365 days expire even when the series has stopped.
A version present only in a removed recovery point is no longer recoverable.

Each pass records archive names and IDs before and after pruning under
`/persist/root/.cache/borg-drain/retention/`, and compacts the repositories to
release unreferenced chunks. Shared chunks remain until their last reference
is removed. `agentctl job start sinnix backup_retention_plan` previews the
installed policy; `agentctl job start sinnix backup_maintenance` runs it when due.
Both execute the native systemd service, so inspect its journal for archive
selection and statistics. A deferred run does not mean pruning completed.

`borgbackup-capacity` runs every six hours at :45, recording allocated repository
sizes and filesystem free bytes in `/persist/root/.cache/borg-drain/capacity.json`.
It alerts below 600 GiB free or less than 14 projected days remaining. Its
advisory projection uses net free-space consumption over up to eight days,
requires at least 24 hours of observations, and resets comparisons when the
filesystem UUID changes or an observation gains at least 100 GiB of headroom.
That large-reclamation reset prevents cleanup from hiding later growth; normal
daily compaction remains part of the net trend. Workload changes affect this estimate.
`agentctl job start sinnix backup_capacity` measures immediately. A low-headroom
exit still records the measurement; the unit's failure notification carries it.

For archive-level size diagnosis, `agentctl job start sinnix
backup_archive_inventory -- --repository <repository> --archive <archive>` reads
one archive's metadata and reports logical bytes by path prefix. Shared chunks
make these different from reclaimable physical bytes. Native verification can
request a new cut with `backup_snapshot`, then archive it with `backup_drain`;
inspect both native units and their admitted snapshot markers afterwards.

## What is backed up

| Source                   | How                                                                    | When                                           | Repository                |
| ------------------------ | ---------------------------------------------------------------------- | ---------------------------------------------- | ------------------------- |
| `/realm`                 | btrbk read-only snapshot, archived by the Borg job                     | snapshots 00/06/12/18:00, drain hourly at :05 and :25 | `borg-realm-v2`           |
| `/persist`               | btrbk read-only snapshot, archived by the Borg job                     | same as `/realm`                               | `borg-persist-v1`         |
| The ephemeral root       | snapshot the initrd takes before each wipe                             | daily                                          | `borg-root-snapshots-v1`  |
| Sinex blob store         | direct                                                                 | daily 05:40                                    | `borg-sinex-blobs-v1`     |
| Polylogue state          | hooks archived directly from a read-only snapshot of its subvolume     | daily 04:15                                    | `borg-polylogue-state-v1` |
| Telemetry database dumps | `--rsyncable` zstd copies in `state/db-dumps/`, archived with `/realm` | dumps 03:42, seal Sunday                       | `borg-realm-v2`           |

Left out of the `/realm` archive (`realmExcludes` in `modules/backup.nix`):
downloaded model weights (including embeddings), Steam libraries and runtimes,
`state/cache`, `state/containers`, `tmp`, worktrees, Cargo `target/` and
project `.venv` directories, Stash's caches and generated media, the ComfyUI
virtualenv, pytest caches and the trash. `/persist` leaves out user caches and
agent CLI installs (npm, `~/.codex/packages`). Every exclusion is an exact path
also listed for the coverage check; `--exclude-caches` and globs are not used,
because coverage cannot waive what they drop. Root snapshots leave out
`~/.cache`, `/root/.cache`, `/var/cache`, `/tmp` and every other mounted
filesystem (`rootSnapshotExcludes` in `modules/lib/backup/acknowledgement.nix`).

The drain checks hourly at :05 and :25 while source acquisition remains every
six hours. A long maintenance pass can hold the Borg lock across both attempts
in an acquisition hour; hourly retries prevent a six-hour wait after it releases.
When no new cuts are queued, the drain validates its existing acknowledgements
and leaves an ongoing repository integrity check running. Pending or unavailable
local handoff evidence requests native drain validation and can preempt a resumable
check. The coordinator uses local receipts for this scheduling hint; the native
children qualify archives under the Borg lock with their own credentials.

### Snapshots are kept until their archive is checked

A snapshot is deleted only after its own archive exists and a coverage check
confirms every path that should be in it is there. Paths deliberately excluded
from the archive are listed for the check too, so an exclusion is never read
as missing data. If the check fails, the snapshot stays and the job fails,
which keeps local snapshots piling up rather than losing data. Backup failures
are therefore also disk-space problems on `/realm`.

The newest admitted source cut remains until a successor is admitted, so an
independent audit has an immutable source. The Borg drain owns releases from
these handoff queues.

Polylogue hooks are read directly from a verified read-only Btrfs cut through
a private temporary path view that preserves `realm/state/polylogue/hooks` in
the archive. No hook cache is copied or synced. The cut is deleted only after
Borg exits successfully and its UUID, parent UUID and read-only flag still
match. Failures retain the cut under `state/cache/polylogue-backup-hooks/cuts`
for recovery; the temporary view is removed on exit. An absent hooks directory
is archived as empty, while unavailable roots and nested subvolumes fail.

### Telemetry

The collector writes `/realm/state/machine-telemetry/telemetry.sqlite`. Every
Sunday `machine-telemetry-seal` closes that file, makes it immutable under a
dated name, and starts a new one; `telemetry.sqlite.segments.json` lists the
sealed files and the active one, and Lynchpin reads that list. Each sealed file
is then compressed into `/realm/state/db-dumps/machine-telemetry/` and checked
with SQLite's structural check, both exactly once, with results kept under
`verified/`. The daily backup compresses only the small active file. Dumps are written
with `zstd --rsyncable`, so unchanged pages compress to identical bytes and
Borg stores mostly new data; the `/realm` snapshots archive them.

## Is it healthy?

For a preserved filesystem tree, run
`agentctl job start sinnix compare_preserved_tree -- -- /absolute/source/ /absolute/copy/`.
This runs native rsync with checksums, metadata comparison and dry-run deletion
reporting. It writes neither tree. Keep the trailing slashes and capture the
job's complete output and exit status. Exit zero means the comparison ran;
equality also requires no itemized changes or deletion entries. Record source
and destination identities before and after, and keep the source stable during
the comparison. This checks a tree copy, not a Borg archive.

- **Notifications.** A failed backup unit raises a critical desktop
  notification, repeated daily while it stays failed.
- **Do not trust `systemctl --failed` alone.** Every NixOS switch resets the
  failed state of all units. Use the hub's health view
  (`sinnix status`) or the journal.
- **Journal.** Drains log `backup_phase=create` and `backup_phase=verify`
  lines: `journalctl -u borgbackup-job-realm -u borgbackup-job-persist`.
- **Markers.** Per-repository state, including the latest archived snapshot
  and coverage results, lives in `/persist/root/.cache/borg-drain/`.
- **Snapshots piling up** in `/realm/.btrfs/snapshot/` or `/persist/.btrfs/snapshot/`
  means archives are not being accepted.

## Checks that run on their own

| Check                    | Unit                              | When                             | What it shows                                                                   |
| ------------------------ | --------------------------------- | -------------------------------- | ------------------------------------------------------------------------------- |
| Repository integrity     | `borgbackup-verify`               | Sunday 13:00                     | Borg's segment CRCs, advanced in time-limited partial passes                    |
| `/realm` coverage sample | `borgbackup-coverage-audit-realm` | hourly while due, at most weekly | all paths and metadata match, plus up to 128 files / 1 GiB of contents compared |
| Beads restore check      | `sinnix-borg-beads-check`         | Thursday 05:00                   | a real restore of the Beads database from the latest archive                    |
| Sealed telemetry         | `machine-telemetry-seal`          | Sunday 04:30                     | each sealed SQLite file passes a structural check once                          |

The coverage sample checks only the newest archive, so files that exist only
in older archives are covered by the repository check, not by a content
comparison.

## Restoring

The repositories use `repokey-blake2`. The passphrase is the agenix secret
`borg-passphrase` (`/run/agenix/borg-passphrase`); `docs/key-recovery.md`
covers recovering it without this machine.

```sh
export BORG_PASSCOMMAND='cat /run/agenix/borg-passphrase'
borg list file:///outer-realm/backup/borg-realm-v2
# Extract into an empty directory; paths are relative to the snapshot root.
mkdir -p /realm/tmp/restore && cd /realm/tmp/restore
borg extract file:///outer-realm/backup/borg-realm-v2::<archive> state/some/path
# Or stream one file without writing a tree:
borg extract --stdout file:///outer-realm/backup/borg-realm-v2::<archive> state/some/file > file
```

Run Borg as root. To test a restore of a small file against its recorded
digest, use `agentctl job start sinnix verify_snapshot_restore -- …`; for a
compressed telemetry dump, `agentctl job start sinnix verify_telemetry_restore
-- <file.sqlite.zst>`.

## Known gaps

- **No off-site copy.** A failed HDD loses every backup.
- **The HDD also holds `/outer-realm/archive`**, primary data with no other
  copy. When the disk fills, new archives fail and snapshots accumulate on
  `/realm`.
