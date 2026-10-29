# Backups

Everything is backed up locally to Borg repositories on the HDD at
`/outer-realm/backup/`. Nothing is stored off-site.

## Retention

`borgbackup-maintenance` runs after the native archive jobs in the nightly
coordinator. A completed pass is due again after 20 hours. Lock contention
leaves it due for the next coordinator attempt. A completion older than 48
hours is unhealthy.

Active series retain every archive from the last 48 hours, then 14 daily,
8 weekly and 12 monthly recovery points. These are counts of periods containing
backups, not elapsed-age limits. Retired series (`sinnix-prime-realm-*`,
`sinnix-prime-persist-*`, `machine-telemetry-dumps-*`) retain six monthly
milestones; archives older than 365 days expire even when the series has stopped.
A version present only in a removed recovery point is no longer recoverable.

Each pass records archive names and IDs before and after pruning under
`/persist/root/.cache/borg-drain/retention/`. Compaction, which releases
unreferenced chunks, runs on the first pass at least 6.5 days after the last
one: at every pass it rewrote hundreds of gigabytes of segments a week to
return space. Shared chunks remain until their last reference is removed. `agentctl job start sinnix backup_retention_plan` previews the
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
weekly compaction remains part of the net trend. Workload changes affect this estimate.
`agentctl job start sinnix backup_capacity` measures immediately. A low-headroom
exit still records the measurement; the unit's failure notification carries it.

For archive-level size diagnosis, `agentctl job start sinnix
backup_archive_inventory -- --repository <repository> --archive <archive>` reads
one archive's metadata and reports logical bytes by path prefix. Shared chunks
make these different from reclaimable physical bytes. Native verification can
request a new cut with `backup_snapshot`, then archive it with `backup_drain`;
inspect both native units and their admitted snapshot markers afterwards.

For local cleanup candidates, `agentctl job start sinnix filesystem_usage --
<absolute-path> ...` measures allocated directory bytes to depth two, without
crossing filesystem boundaries, at idle I/O priority. The filesystem index can
suggest roots, but its dated observations need a fresh measurement. Directory
totals include shared extents and do not predict reclaimed filesystem space;
`filesystem_accounting` provides compression and sharing details for explicit
paths. Neither measurement establishes that a directory is disposable.

## What is backed up

| Source                   | How                                                                    | When                                             | Repository                         |
| ------------------------ | ---------------------------------------------------------------------- | ------------------------------------------------ | ---------------------------------- |
| `/realm`                 | btrbk read-only snapshot, archived by the Borg job                     | snapshots 00/06/12/18:00, drain nightly 03:05    | `borg-realm-v2`                    |
| `/persist`               | btrbk read-only snapshot, archived by the Borg job                     | same as `/realm`                                 | `borg-persist-v1`                  |
| HDD genome workspace     | dedicated btrbk cut, archived independently of `/realm`                | six-hour cuts only when changed, drained nightly | `borg-realm-v2`, `genome-*` series |
| The ephemeral root       | snapshot the initrd takes before each wipe                             | nightly coordinator                              | `borg-root-snapshots-v1`           |
| Sinex content stores     | read in place: the running store and the dated earlier one             | nightly coordinator                              | `borg-sinex-blobs-v1`              |
| Sinex database dump      | `pg_dump` into `state/db-dumps/sinex`, archived with `/realm`          | dump daily at midnight                           | `borg-realm-v2`                    |
| Polylogue state          | hooks archived directly from a read-only snapshot of its subvolume     | nightly coordinator                              | `borg-polylogue-state-v1`          |
| Telemetry database dumps | `--rsyncable` zstd copies in `state/db-dumps/`, archived with `/realm` | dumps before nightly cut, seal Sunday            | `borg-realm-v2`                    |

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

The coordinator runs nightly at 03:05 and once 45 minutes after boot. The
persistent calendar catches a missed nightly window; the independent boot
trigger also catches a night interrupted after its calendar event fired. Both
triggers target the same native service, which cannot overlap itself. Resume
an interrupted or failed pass manually with
`agentctl job start sinnix backup_drain` after checking its native units and
shared-lock holder.

It starts the configured telemetry and Polylogue SQLite dump units, then asks
`btrbk.service` for a normal acquisition containing those new dumps. If a dump
fails, it skips that additional cut and still attempts the independent archive
and maintenance jobs, returning failure at the end. The existing six-hour
btrbk schedule remains; no queued restore point is dropped or coalesced.

A durable acquisition receipt records only successful dumps plus a completed
native btrbk acquisition. Its 20-hour freshness and dump/snapshot-policy hash
avoid repeating dumps and extra cuts when the boot and calendar wakes follow
each other. An interrupted archive phase reuses that acquisition while the
native per-snapshot receipts govern its remaining queue. Changed policy,
missing/invalid receipts or a stale acquisition make dumps and acquisition due.
Direct Polylogue/Sinex archive calls and local dump expiry likewise reuse their
existing success markers only within 20 hours and with matching input policy.
Manual native unit calls retain their original behavior.

The sequence first archives daily Polylogue state and optional Sinex blobs,
then runs Realm, optional genome, Persist and root snapshot archival, followed
by retention maintenance,
the due Realm coverage audit and verified local dump expiry. These jobs have
no independent timers on backup hosts. Telemetry-only hosts retain their dump
timer. Each native job keeps its own resources, proof, due checks and deadline.
The coordinator owns no Borg lock while waiting for children; the children
acquire and release it themselves. Stopping the coordinator propagates to its
children, preserving their existing failed-cut and unacknowledged-source rules.
Adding or re-enabling the boot timer on a machine already past 45 minutes
can start this full sequence immediately during activation. With a retained
persistent trigger timestamp, systemd can instead suppress that already-past
boot expression; inspect the actual next trigger and native service state.
The normal boot trigger is scheduled when the timer starts before 45 minutes.
Use the declared `backup_drain` operation for deployment recovery when no
automatic start is pending. Sequence activation and recovery with other
IO-heavy jobs and inspect the retained queue first.
The coordinator is not restarted merely because its script changes.
Polylogue state keeps its 90-minute deadline; Sinex blobs have a six-hour
start deadline instead of an infinite one. A timeout keeps canonical input
and failed hook cuts for recovery. Its overall deadline is 56h15m, or
80h15m with genome, so a large retained
backlog can extend beyond one night. The declared `backup_drain` caller uses `timeout_seconds = 0` (no outer
AgentCTL deadline), because supported positive caller timeouts stop at eight
hours. The native systemd coordinator retains its finite 80h15m maximum;
systemd remains the owner of child deadlines and cancellation.
This maximum is not a nightly SLA or
a waiver of the 36-hour source alert: a large retained backlog can fail that
alert while remaining safely resumable. A successful unit start alone is not
proof every source has an accepted archive; inspect the per-source receipts.

Daily direct-path archives run before complete historical snapshot queues so
a multi-day Realm/genome backlog cannot consume their daily start window.
That trades their runtime before Realm's space-sensitive drain; no historical
cut is dropped, and each native drain still processes its finite lossless queue.

The drain keeps the newest archived snapshot for the independent audit.
When no cuts are queued it validates existing acknowledgements and leaves a
running repository integrity check alone. Pending or unavailable local
handoff evidence can preempt the resumable weekly check; the independent
coverage audit is never preempted. The coordinator uses local receipts for
this scheduling hint; children qualify archives under the Borg lock.

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

The genome workspace can live at `sinnix.backup.genomeRoot` on the HDD while a
declared mount preserves `/realm/health/genome` for its callers. A Realm
snapshot does not cross that mount. The genome subvolume therefore has its
own immutable cuts, archive receipts and freshness check. Its `genome-*`
archives (`genome-genome.*`) share the Realm repository for deduplication and have independent
retention, so a Realm recovery point cannot displace a genome recovery point
from the same day. Raw reads, supplied alignments, vendor files, manifests,
source/WIP and analysis results stay covered. Exclusions name the public
reference/catalogue caches, downloaded tools and dependency environments;
unclassified cache children remain covered.

`/neo-outer-realm/inbox/p2` is unbacked bulk intake by operator choice.

Polylogue hooks are read directly from a verified read-only Btrfs cut through
a private temporary path view that preserves `realm/state/polylogue/hooks` in
the archive. No hook cache is copied or synced. The cut is deleted only after
Borg exits successfully and its UUID, parent UUID and read-only flag still
match. Failures retain the cut under `state/cache/polylogue-backup-hooks/cuts`
for recovery; the temporary view is removed on exit. An absent hooks directory
is archived as empty, while unavailable roots and nested subvolumes fail.

### Telemetry

The coordinator's final `borgbackup-local-dumps` job keeps at least the seven newest daily
dumps in each telemetry or PostgreSQL environment stream. Additional dumps
must be older than seven days by both filename timestamp and modification time.
Before deleting each local file, the job restores its entire archived copy and
compares SHA-256 and length, checking the admitted archive ID and source UUID
before and after. A missing, changed or unreadable archive leaves the local file.
Partial files, unknown names and sealed legacy artifacts are retained. The job
shares Borg's global lock and skips contention; it does not delay admission or
make a new dump depend on the backup disk. Run it through the declared
`backup_local_dumps` operation. Released bytes can remain pinned by the latest
source snapshot until its normal successor is admitted.

The collector writes `/realm/state/machine-telemetry/telemetry.sqlite`. Every
Sunday `machine-telemetry-seal` closes that file, makes it immutable under a
dated name, and starts a new one; `telemetry.sqlite.segments.json` lists the
sealed files and the active one, and Lynchpin reads that list. Each sealed file
is then compressed into `/realm/state/db-dumps/machine-telemetry/` and checked
with SQLite's structural check, both exactly once, with results kept under
`verified/`. The daily backup compresses only the small active file. Dumps are written
with `zstd --rsyncable`, so unchanged pages compress to identical bytes and
Borg stores mostly new data; the `/realm` snapshots archive them.

Receipt metadata under `/persist/root/.cache/borg-drain` is root-owned and
traversable by the operator's `users` group (0750). Published receipts remain
read-only to that group. Creating jobs and tmpfiles use the same directory
policy, including the exact Realm, Persist and Genome `.by-snapshot` receipt
namespaces. Tmpfiles also migrates existing namespace directories before probes
run; it does not recursively change receipt files. Borg repositories, key
material and chunk caches remain root-private.

Realm and Persist freshness alerts allow 36 hours from the accepted source
cut: the approved 24-hour archival cadence plus 12 hours of grace. The former
eight-hour check described a six-hour archive schedule that no longer exists.
The broader coordinator timeout does not extend this alert budget or establish
an eight-hour recovery-point objective.

Genome acquisition is `onchange`, so an old accepted cut can remain current.
On every successful native btrbk acquisition, including an unchanged source,
the root producer atomically publishes a metadata-only inventory under the
receipt directory. It records the observed UTC time, current policy and source
identity, plus immutable snapshot UUIDs, generations, IDs and cut times. This
runs on the existing six-hour schedule and the coordinator's acquisition;
there is no extra observer timer. Private snapshot access stays with root.

The operator's probe reads that projection and the matching current-policy
accepted receipt. It opens neither private snapshots nor Borg credentials.
A failed native producer, missing/corrupt/future observation or observation
older than 18 hours (three acquisition periods) fails the probe. With no newer
observed acquired generation it is healthy regardless of the old accepted
cut's age; otherwise the oldest pending newer cut has the 36-hour archival
budget. Future cut times fail, and new arrivals cannot reset old debt. An
archive accepted after inventory publication can be recognized immediately
without waiting for another acquisition. This describes the latest observed
acquired generation, not instantaneous live contents, a repository integrity
check or a claim that every write between acquisitions is already archived.

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
| `/realm` coverage sample | `borgbackup-coverage-audit-realm` | nightly when due, at most weekly | all paths and metadata match, plus up to 128 files / 1 GiB of contents compared |
| Beads restore check      | `sinnix-borg-beads-check`         | Thursday 05:00                   | a real restore of the Beads database from the latest archive                    |
| Sealed telemetry         | `machine-telemetry-seal`          | Sunday 04:30                     | each sealed SQLite file passes a structural check once                          |

The coverage sample checks only the newest archive, so files that exist only
in older archives are covered by the repository check, not by a content
comparison.

The weekly repository checker has four hours of partial-check budgets and a
4h30m service deadline. The main realm pass gets 7,200 seconds, plus another
1,800-second pass from the no-argument check script. Checks resume Borg's
saved segment cursor and verify segment CRCs. They do not cryptographically
verify archive contents. The backup resource class sets I/O priority 7 and
IOWeight 20; it sets no device bandwidth cap. A full-pass horizon therefore
needs measured throughput; 40 MB/s is not an enforced limit.

Snapshot archives use the source cut time for Borg retention, including delayed
backfills. The drain and acknowledgement marker still order snapshots by native
generation, so clock skew can make retention time differ from freshness order.
Existing archives keep their recorded timestamps. Retention counts are unchanged.

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
digest, use:

```sh
agentctl job start sinnix verify_snapshot_restore -- --scope realm --target <private-receipt.json> --version new
```

For a Persist archive, select `--scope persist`. The scope binds the archive name and
installed backup owner together. The private receipt supplies the exact archive ID,
snapshot UUID, relative path, byte count and complete SHA-256 digest. Extraction
stays in memory and shares the backup mutex. For a compressed telemetry dump, `agentctl job start sinnix verify_telemetry_restore
-- <file.sqlite.zst>`.

## Known gaps

- **No off-site copy.** A failed HDD loses every backup.
- **The HDD also holds `/outer-realm/archive`**, primary data with no other
  copy. When the disk fills, new archives fail and snapshots accumulate on
  `/realm`.
