# Backups

Backups are Borg repositories on the HDD at `/outer-realm/backup/`. Nothing
is stored off-site.

## How the jobs run

Every backup unit runs one command of `sinnix-backup`, the Python package in
`pkgs/sinnix-backup/`: `drain persist|realm|genome`, `nightly`,
`take-snapshots`, `root-snapshots`, `sinex-stores`, `polylogue-dumps`,
`polylogue-state`, `hourly-persist`, `hourly-live`, `maintain`,
`expire-dumps`, `check-repositories`, `audit-realm` and
`check-beads-restore`. The capacity record runs its own
`sinnix-backup-capacity` script. Every command reads its paths, repositories,
exclusions and settings from `/etc/sinnix/backup.json`, which
`modules/backup.nix` builds; `modules/lib/backup/units.nix` declares the
units, their dependencies, deadlines and timers.

`sinnix.backup.archive.enable = false` pauses archive backups: every Borg
unit stays defined and starts by hand (`systemctl start <unit>`), but no
timer starts the drain coordinator, the hourly jobs, capacity, verification
or the Beads restore check, and the Borg freshness lanes leave the health
sweep. `btrbk.timer` keeps taking snapshots and deleting them by count. The
nightly dumps (Polylogue, telemetry) and the Sinex backup pair are started
only by the coordinator, so they pause too.

`sinnix-backup plan <label>` (`persist`, `realm` or `genome`) shows what the
drain would do, without taking the Borg lock or changing anything: the policy
hash, each queued snapshot with the archive name and complete `borg create`
arguments it would get, and the snapshots the drain would then delete. If a
local snapshot cannot be verified for deletion, `prune_error` gives the
reason and the archive queue is still shown.
`sinnix-backup maintain --dry-run` previews retention. The health probes run
`sinnix-backup freshness <label>`, `acquisition-freshness` and
`audit-status`.

The package's pytest suite (`pkgs/sinnix-backup/tests`, the `backup-suite`
check) runs each job against real Borg with `mount`, `btrfs` and `systemctl`
replaced by fakes, reading the policy file evaluated for a test host.
`backup-genome-files-cache` runs its files-cache test alone.

## Sinex

The running Sinex store (`/var/lib/sinex`, the `state/sinex` subvolume on
`/realm`, which the `/realm` snapshots do not include) is archived nightly.
The coordinator starts `sinex-backup.service` after the Persist archive.
Each start prepares a new run under
`/var/lib/sinex/daemon/backups/<run>`. The database and key dumps, committed
segment prefixes and producer state come from one held boundary. Staging
shares the segment's filesystem so Sinex can clone its extents without
writing a second copy of the segment. Sinex still hashes the staged prefixes
and verifies the held extents.

Two Borg jobs archive the main data into `borg-sinex-core-v1` and the keys
into `borg-sinex-keys-v1`. Both repositories must be initialized by hand
before the first run. The service releases the boundary only after reading
back both archives by name. If archival fails, the unit retains the staging
directory and hold for diagnosis. A retry prepares a fresh run.
`latest-complete.json` in the staging root points to the last pair completed
there. For earlier pairs, use the `complete.json` kept with each run.

Stopped Sinex deployments listed in `sinnix.services.sinex.retainedStores`
(today `/var/lib/sinex/old-2026-10-26`) are archived whole by the
`borgbackup-job-sinex-blobs` job until their import into the running Sinex has
been compared.

## Retention

`borgbackup-maintenance` runs after the archive jobs in the nightly
coordinator. A completed pass is due again after 20 hours. Lock contention
leaves it due for the next coordinator attempt. A completion older than 48
hours is unhealthy.

Active series retain every archive from the last 48 hours, then 14 daily,
8 weekly and 12 monthly recovery points. These are counts of periods containing
backups, not elapsed-age limits. Retired series (`sinnix-prime-realm-*`,
`sinnix-prime-persist-*`, `machine-telemetry-dumps-*`) retain six monthly
milestones; archives older than 365 days expire even when the series has stopped.
A version present only in a removed recovery point is no longer recoverable.

When removing a local copy that must survive rolling retention, archive the
specific files in the same repository under a `cold-history-*` name. Ordinary
maintenance selects only the configured rotating series, so that name keeps
the cold archive outside automatic expiry and lets Borg share chunks with the
rolling backups. Record the new archive ID and restore the files to verify
their bytes before releasing the local copy. Any later removal of the cold
archive needs its own custody decision.

For files already in a rolling archive, use Borg's `recreate --target` with
exact path selection and no recompression or rechunking. Verify the target's
membership and the original archive ID after the copy.

Each pass records archive names and IDs before and after pruning under
`/persist/root/.cache/borg-drain/retention/`. Compaction, which releases
unreferenced chunks, runs on the first pass at least 6.5 days after the last
one: at every pass it rewrote hundreds of gigabytes of segments a week to
return space. Shared chunks remain until their last reference is removed.
`agentctl job start sinnix backup_retention_plan` previews the installed policy
(`borgbackup-retention-plan` runs `sinnix-backup maintain --dry-run`);
`agentctl job start sinnix backup_maintenance` runs it when due.
Both run the systemd service, so inspect its journal for archive
selection and statistics. A deferred run does not mean pruning completed.

`borgbackup-capacity` runs every six hours at :45, recording allocated repository
sizes, filesystem free bytes and the time of the last compaction in
`/persist/root/.cache/borg-drain/capacity.json`. Free space falls every night
and the weekly compaction returns what pruning freed, so nightly figures say
nothing about growth. The forecast compares free space measured right after
each compaction, over at least six days. It alerts when that trend projects
the destination full within 30 days, the time to buy and seed another disk, or
when less space is free than one compaction cycle has consumed. A new
destination starts a new history.
`agentctl job start sinnix backup_capacity` measures immediately. A low-headroom
exit still records the measurement; the unit's failure notification carries it.

For archive-level size diagnosis, `agentctl job start sinnix
backup_archive_inventory -- --repository <repository> --archive <archive>` reads
one archive's metadata and reports logical bytes by path prefix. Shared chunks
make these different from reclaimable physical bytes. To check the path end to
end, take a new cut with `backup_snapshot`, then archive it with
`backup_drain`; inspect both units and their snapshot markers afterwards.

For local cleanup candidates, `agentctl job start sinnix filesystem_usage --
<absolute-path> ...` measures allocated directory bytes to depth two, without
crossing filesystem boundaries, at idle I/O priority. The filesystem index can
suggest roots, but its dated observations need a fresh measurement. Directory
totals include shared extents and do not predict reclaimed filesystem space;
`filesystem_accounting` provides compression and sharing details for explicit
paths. Neither measurement establishes that a directory is disposable.

## What is backed up

| Source                                        | How                                                                                                                                                                                      | When                                             | Repository                                  |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------- |
| `/realm`                                      | btrbk read-only snapshot, archived by the Borg job                                                                                                                                       | snapshots 00/06/12/18:00, drain nightly 03:05    | `borg-realm-v2`                             |
| `/persist`                                    | btrbk read-only snapshot, archived by the Borg job                                                                                                                                       | same as `/realm`                                 | `borg-persist-v1`                           |
| HDD genome workspace                          | dedicated btrbk cut, archived independently of `/realm`                                                                                                                                  | six-hour cuts only when changed, drained nightly | `borg-realm-v2`, `genome-*` series          |
| The ephemeral root                            | snapshot the initrd takes before each wipe                                                                                                                                               | nightly coordinator                              | `borg-root-snapshots-v1`                    |
| Running Sinex                                 | `sinex-backup`: a backup Sinex prepares at one held boundary (database, keys, segments, producer state), archived by two Borg jobs (see "Sinex" above)                                   | nightly coordinator                              | `borg-sinex-core-v1`, `borg-sinex-keys-v1`  |
| Retained Sinex deployments                    | the whole stopped deployment read in place, its PostgreSQL cluster included                                                                                                              | nightly coordinator                              | `borg-sinex-blobs-v1`                       |
| Polylogue state                               | hooks archived directly from a read-only snapshot of its subvolume                                                                                                                       | nightly coordinator                              | `borg-polylogue-state-v1`                   |
| Purchased embedding vectors                   | the purchased stores on `/neo-outer-realm/archive/polylogue/embeddings`, in the same archive as Polylogue state; they never change, so Borg stores them once                             | nightly coordinator                              | `borg-polylogue-state-v1`                   |
| Polylogue live archive                        | `state/polylogue-live` (except `index.db`) inside the `/realm` btrbk snapshot; an atomic snapshot is consistent for Polylogue                                                            | same as `/realm`                                 | `borg-realm-v2`                             |
| Polylogue live spools                         | `~/.local/state/polylogue` (hook, browser and collector spools; the AI Studio Drive token), persisted on `/persist`                                                                      | same as `/persist`                               | `borg-persist-v1`                           |
| Polylogue archive database, hourly            | `.dump` of the whole `archive.db` in one read transaction, streamed into a `polylogue-archive-*` archive; it follows whatever schema is deployed, so no table list exists to fall behind | hourly at :47                                    | `borg-live-small-v1`                        |
| Beads task databases and Sinex spools, hourly | the `state/tasks` tree (minus migration backups) and the producer spools, read in place                                                                                                  | hourly at :47                                    | `borg-live-small-v1`, `live-small-*` series |
| Telemetry database dumps                      | `--rsyncable` zstd copies in `state/db-dumps/`, archived with `/realm`                                                                                                                   | dumps before nightly cut, seal Sunday            | `borg-realm-v2`                             |

Each archive leaves out regenerable and re-acquirable paths; "Exclusions and
why" below lists them with their reasons.

The coordinator runs nightly at 03:05 and once 45 minutes after boot. The
persistent calendar catches a missed nightly window; the independent boot
trigger also catches a night interrupted after its calendar event fired. Both
triggers start the same service, which cannot overlap itself. Resume
an interrupted or failed pass manually with
`agentctl job start sinnix backup_drain` after checking its units and which
process holds the Borg lock.

It starts the configured telemetry and Polylogue SQLite dump units, then asks
`btrbk.service` for a normal acquisition containing those new dumps. If a dump
fails, it skips that additional cut and still attempts the independent archive
and maintenance jobs, returning failure at the end. The existing six-hour
btrbk schedule remains; no queued restore point is dropped or coalesced.

An acquisition receipt, written to disk before it counts, records only
successful dumps plus a completed btrbk acquisition. Its 20-hour freshness and dump/snapshot-policy hash
avoid repeating dumps and extra cuts when the boot and calendar wakes follow
each other. An interrupted archive phase reuses that acquisition while the
per-snapshot receipts decide its remaining queue. Changed policy,
missing/invalid receipts or a stale acquisition make dumps and acquisition due.
The running Sinex backup reuses its own `latest-complete.json` for 20 hours:
both archive names and IDs must form the completed hold's pair, with every
producer copied. Freshness comes from that receipt's write time. Missing,
invalid, incomplete, future-dated or stale receipts leave the backup due.
This avoids repeating its dump and segment copy on boot catch-up.
Direct Polylogue/Sinex archive calls and local dump expiry likewise reuse their
existing success markers only within 20 hours and with matching input policy.
Starting a unit by hand skips these checks.

The sequence first archives daily Polylogue state and the retained Sinex
deployments, then runs Realm, optional
genome, Persist, the running Sinex backup and root snapshot archival, followed
by retention maintenance, the due Realm coverage audit and verified local dump expiry. These jobs have
no independent timers on backup hosts. Telemetry-only hosts retain their dump
timer. Each job keeps its own resources, proof, due checks and deadline.
The coordinator owns no Borg lock while waiting for children; the children
acquire and release it themselves. Stopping the coordinator propagates to its
children, preserving their existing failed-cut and unacknowledged-source rules.
Adding or re-enabling the boot timer on a machine already past 45 minutes
can start this full sequence immediately during activation. With a retained
persistent trigger timestamp, systemd can instead suppress that already-past
boot expression; inspect the actual next trigger and service state.
The normal boot trigger is scheduled when the timer starts before 45 minutes.
Use the declared `backup_drain` operation for deployment recovery when no
automatic start is pending. Sequence activation and recovery with other
IO-heavy jobs and inspect the retained queue first.
Activation does not restart the coordinator or any other backup unit.
Polylogue state keeps its 90-minute deadline; Sinex blobs have a six-hour
start deadline instead of an infinite one. A timeout keeps canonical input
and failed hook cuts for recovery. Its overall deadline is 56h15m, or
80h15m with genome, so a large retained
backlog can extend beyond one night. The declared `backup_drain` caller uses `timeout_seconds = 0` (no outer
AgentCTL deadline), because supported positive caller timeouts stop at eight
hours. The systemd coordinator keeps its finite 80h15m maximum;
systemd remains the owner of child deadlines and cancellation.
This maximum is not a nightly SLA or
a waiver of the 36-hour source alert: a large retained backlog can fail that
alert while remaining safely resumable. A successful unit start alone is not
proof every source has an accepted archive; inspect the per-source receipts.

Daily direct-path archives run before complete historical snapshot queues so
a multi-day Realm/genome backlog cannot consume their daily start window.
That trades their runtime before Realm's space-sensitive drain; each drain
processes the finite queue of cuts still kept locally, newest first.

The Realm, Persist and genome drains take the global Borg lock once per
snapshot: for one cut's create, verification and acknowledgement, and again
for each snapshot deletion, which first rechecks that snapshot's archive and
identity because maintenance may have changed archives in between. When
another job holds the lock at startup, the drain waits within its systemd
deadline. After verifying the newest queued cut, the drain can release older
acknowledged cuts before archiving the rest of the backlog. The newest verified cut stays for
the independent audit. Other Borg
jobs waiting for the lock run between those steps, including while the drain
waits for the Btrfs cleaner and for I/O pressure to settle after a deletion.
Markers are written to a temporary file, fsynced, renamed into place, and the
parent directory is fsynced; nothing else on the filesystem is flushed.

The drain keeps the newest archived snapshot for the independent audit,
within the local count. When no cuts are queued it validates existing acknowledgements and leaves a
running repository integrity check alone. A pending snapshot, or a receipt it
cannot read, can preempt the resumable weekly check; the independent coverage
audit is never preempted. The coordinator decides this from local receipts
only; the drains check archives themselves under the Borg lock.

### Local snapshots are kept by count

`sinnix-backup take-snapshots`, which runs btrbk, keeps the newest eight
`/realm` and `/persist` snapshots (`localSnapshots` in `modules/backup.nix`)
and deletes older ones whether or not Borg has archived them, so a paused or
failing backup never pins deleted data on those filesystems. It deletes under
the Borg lock, taken without waiting: while a backup job holds it, the
deletion waits for the next snapshot run. A snapshot the drain is archiving or
the independent audit is reading also holds a shared lock on its directory and
stays until a later run. The drain archives the newest
snapshot first and skips a queued one that has meanwhile been deleted.

The drain also releases a cut as soon as its own archive exists and a coverage
check confirms every path that should be in it is there. Paths deliberately
excluded from the archive are listed for the check too, so an exclusion is
never read as missing data. If the check fails, the snapshot stays until the
count removes it. The newest archived cut stays until a newer one is archived
or the count removes it, so the independent audit has an unchanging source
while backups keep up; when they fall two days behind, the audit and the local
dump expiry wait for a new archive.

Genome cuts are not counted: the genome drain deletes each only after its own
checked archive.

The live Polylogue archive and every directory in
`sinnix.services.polylogue.retainedArchives` exclude only their derived
`index.db`, `index.db-wal` and `index.db-shm`. Keep that list complete when an
archive moves: queued snapshots still contain its earlier directory. Raw
segments, archive databases and purchased vectors remain covered.

Snapshot inputs are bind-mounted at stable paths under
`/run/borgbackup-snapshot-inputs`. Borg keeps `ctime,size,inode` validation;
Btrfs snapshots preserve inode numbers. Hourly jobs use a separate cache
directory and do not age the nightly Realm files cache.

The genome workspace can live at `sinnix.backup.genomeRoot` on the HDD while a
declared mount preserves `/realm/health/genome` for its callers. A Realm
snapshot does not cross that mount. The genome subvolume therefore has its
own immutable cuts, archive receipts and freshness check. Its `genome-*`
archives (`genome-genome.*`) share the Realm repository for deduplication and have independent
retention, so a Realm recovery point cannot displace a genome recovery point
from the same day. Genome uses Borg's `BORG_FILES_CACHE_SUFFIX=genome`
(`sources.genome.files_cache_suffix` in the policy file) to keep its files
metadata cache independent of Realm create-count aging. The
repository and chunk index stay shared, and `ctime,size,inode` validation
remains unchanged. This namespace starts cold; its first create can reread
the source before later unchanged cuts can benefit. No live cache is migrated.
Raw reads, supplied alignments, vendor files, manifests,
source/WIP and analysis results stay covered. Exclusions name the public
reference/catalogue caches, downloaded tools and dependency environments;
unclassified cache children remain covered.

`/neo-outer-realm/inbox/clips` (formerly `inbox/p2`, the media intake moved
off `/realm/inbox/download/p`) is unbacked bulk intake by operator choice.

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
compares SHA-256 and length, checking the accepted archive ID and source UUID
before and after. A missing, changed or unreadable archive leaves the local file.
Partial files, unknown names and sealed legacy artifacts are retained. The job
shares Borg's global lock and skips a night when it is held; it never delays
or makes a new dump depend on the backup disk. Run it through the declared
`backup_local_dumps` operation. Released bytes stay pinned by the local
snapshots until they are deleted (see the local count above).

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

Realm and Persist freshness alerts allow 30 hours from the accepted source
cut: the approved 24-hour archival cadence plus 6 hours of grace. The broader coordinator timeout does not extend this alert budget or establish
an eight-hour recovery-point objective.

Genome acquisition is `onchange`, so an old accepted cut can remain current.
On every successful btrbk acquisition, including an unchanged source,
the root producer atomically publishes a metadata-only inventory under the
receipt directory. It records the observed UTC time, current policy and source
identity, plus immutable snapshot UUIDs, generations, IDs and cut times. This
runs on the existing six-hour schedule and the coordinator's acquisition;
there is no extra observer timer. Private snapshot access stays with root.

The operator's probe reads that projection and the matching current-policy
accepted receipt. It opens neither private snapshots nor Borg credentials.
A failed btrbk producer, missing/corrupt/future observation or observation
older than 18 hours (three acquisition periods) fails the probe. With no newer
observed acquired generation it is healthy regardless of the old accepted
cut's age; otherwise the oldest pending newer cut has the 36-hour archival
budget. Future cut times fail, and new arrivals cannot reset old debt. An
archive accepted after inventory publication can be recognized immediately
without waiting for another acquisition. This describes the latest observed
acquired generation, not instantaneous live contents, a repository integrity
check or a claim that every write between acquisitions is already archived.

## Exclusions and why

`modules/backup.nix` declares each snapshot source's exclusions once
(`persistExclusions`, `realmExclusions`, `genomeExclusions`): exact paths
relative to the snapshot root, each marked `mayBeMissing` or not. From them
Nix derives Borg's `--exclude` patterns and the coverage policy's
`noncanonical` roots, the paths whose absence from an archive the coverage
check accepts. The policy goes into `/etc/sinnix/backup.json`, and its JSON,
entries and order included, is hashed into every archive record. Changing an
entry therefore makes the next archive of that source a new policy: Persist
runs a full content comparison, the Realm audit reports stale until it runs
again, and local dump expiry and genome freshness wait for an archive under
the new policy.

Borg matches an exclusion against the full path it walks, which begins with
the snapshot's bind mount, so plain entries are qualified with that path and
`**` patterns stay match-anywhere. Patterns keep Borg's default fnmatch style,
because `pp:` prefixes cannot express the Chrome extension wildcards.
`--exclude-caches`, `--exclude-if-present` and broad globs are not used: a tag
file or a directory name does not show that the contents beside it can be
recreated, and the coverage check waives only roots listed here. Borg stops
at an excluded directory, so a child cannot be included again under it; an
exclusion names the regenerable child itself, such as Steam's `steamapps`
rather than the whole Steam tree.

`/realm` leaves out, all marked `mayBeMissing`:

- Re-acquirable downloads. Model weight stores under `library/model`
  (`ollama`, `gguf`, `sherpa`, `photoprism`, `sd-checkpoints`, `tts`,
  `embedding`); the model directory itself stays covered, so authored control
  vectors and new, unclassified children are archived. Steam's games,
  runtimes and client package, which the client downloads again; `userdata`
  beside them (cloud saves and recordings) stays covered. The public genome
  reference downloads in `health/genome/cache`; the raw reads in `genotype/`
  cannot be regenerated and stay covered. Container image layers in
  `state/containers`, pulled again by the digests the modules pin; the
  containers keep their data on bind mounts under `library/` and `state/`,
  so a named volume created in `state/containers` would not be archived.
  Codex's downloaded app-server releases.
- `library/games/steam/steamapps` and `library/models`, earlier locations
  that older snapshots still hold.
- Caches and scratch: `state/cache`, and the top-level `tmp`, `worktree` and
  `worktrees`, which `/realm/INVENTORY.md` declares unbacked (agent checkouts'
  commits live in their origin repositories). A `tmp/` inside a dataset stays
  covered, and so does `inbox/`, where downloads land and exist nowhere else.
  The pytest caches at `/realm` and `/realm/project`, and the trash
  `.Trash-1000`.
- Build and environment trees that hold only rebuildable content: the named
  Cargo `target/` and project `.venv` directories, Stash's analysis cache,
  generated media and GPU virtualenv, and the ComfyUI virtualenv.
- The generated filesystem index under `state/fs-index/generations`. The
  authored judgments and references beside it stay covered. Run a fresh scan
  after restoring the authored inputs to regenerate the index.
- Polylogue's `index.db`, its WAL and SHM files, and `index-rebuild/` in the
  live archive and every directory in `sinnix.services.polylogue.retainedArchives`.
  Polylogue rebuilds the index from the archive and segment log. The backup
  takes the remaining files from the atomic snapshot.

Evaluation asserts that the scratch roots in
`modules/lib/storage/scratch-roots.nix` stay within these exclusions, and that no
exclusion covers a Beads task store, the ranking domains or
`library/model/control-vector`, or any of their parents.
The boot migration also moves generated filesystem indexes, downloaded Codex
releases, downloaded GGUF weights and Steam's installed games into nested
subvolumes. New Realm snapshots then stop holding their blocks after removal.
Steam's Proton data stays in the Realm snapshot.
Existing snapshots retain their original contents until they are deleted.

`/persist` leaves out, marked `mayBeMissing`: user caches (`~/.cache`, Hugging
Face, Spotify) and Borg's cache in `/root/.cache`; package registries and
environments fetched again on demand (Cargo's registry and git checkouts,
npm's cache and `npx`, `uv`, the Hermes agent's virtualenvs, Mason); agent CLI
installs the bootstrap reinstalls, while their ledgers stay covered; Hyprland
logs and systemd core dumps; AgentCTL launch inputs, transient launch
documents that do not belong in an archive, while job results and logs stay
covered; and Chrome's GPU, shader, dictionary and component caches. Two
exclusions are not marked: the Steam directory and `/var/lib/sinex` (Sinex
state, which Sinex's own tooling backs up) are left out of the archive, but
the check does not excuse them, so content there that an archive lacks keeps
the snapshot. The Chrome extension cache wildcards are excused only through
`chrome_extension_caches`, which accepts a wildcard that is a Chrome
extension ID (32 lowercase letters a to p) ending in one of the listed caches.

The genome source leaves out its public reference and catalogue caches,
downloaded tools, Python libraries, snpEff data, GWAS summary statistics and
`.direnv`; raw reads, alignments, vendor files, manifests, work in progress
and results stay covered.

Root snapshots leave out `rootSnapshotExcludes` (`modules/backup.nix`): other
mounted filesystems, `/nix`, the pseudo-filesystems, `/tmp`, `~/.cache`,
`/root/.cache` and `/var/cache`. The same list is the root coverage policy,
so an excluded path is never reported missing.

The Polylogue state archive leaves out the live databases the dump job copies
and their WAL and SHM files, so it never copies a database mid-write, plus the
live hook tree, which it reads from a read-only cut; retired database files
beside them stay covered. The hourly live-small archive leaves out
`migration-backups` and Dolt server logs under `state/tasks`.

## Is it healthy?

For a preserved filesystem tree, run
`agentctl job start sinnix compare_preserved_tree -- -- /absolute/source/ /absolute/copy/`.
This runs rsync with checksums, metadata comparison and dry-run deletion
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

| Check                    | Unit                              | When                             | What it shows                                                                                                                                |
| ------------------------ | --------------------------------- | -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Repository integrity     | `borgbackup-verify`               | Sunday 13:00                     | Borg's segment CRCs, advanced in time-limited partial passes                                                                                 |
| `/realm` coverage sample | `borgbackup-coverage-audit-realm` | nightly when due, at most weekly | all paths and metadata match, plus up to 128 files / 1 GiB of contents compared                                                              |
| Beads restore check      | `sinnix-borg-beads-check`         | Thursday 12:00                   | every task database restored from the latest realm archive and opened offline; waits up to three hours for the Borg lock and fails past that |
| Sealed telemetry         | `machine-telemetry-seal`          | Sunday 04:30                     | each sealed SQLite file passes a structural check once                                                                                       |

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

Borg archive, maintenance and restore-check commands use a stable
`BORG_HOST_ID` built from the hostname and machine ID. Borg recognizes and
removes abandoned locks from that identity. The weekly check's systemd
`TimeoutStartSec=4h30m` ends overrunning checks and records a unit failure.

The Beads restore check shares the Borg lock with archive jobs, maintenance,
independent coverage checks and manual commands. It keeps its three-hour lock
wait because `After=` orders systemd starts but cannot order manual commands.

Snapshot archives use the source cut time for Borg retention, including delayed
backfills. The drain and acknowledgement marker still order snapshots by Btrfs
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
stays in memory and shares the Borg lock. For a compressed telemetry dump, `agentctl job start sinnix verify_telemetry_restore
-- <file.sqlite.zst>`.

## Known gaps

- **No off-site copy.** A failed HDD loses every backup.
- **The HDD also holds `/outer-realm/archive`**, primary data with no other
  copy. When the disk fills, new archives fail and snapshots accumulate on
  `/realm`.
