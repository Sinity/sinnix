# Filesystem index

`sinnix fs` (package `sinnix-fs`) keeps an inventory of directories, bounded
content fingerprints, and views of the authored file judgments. It does not own
any storage and never deletes or deduplicates anything. The weekly
`sinnix-fs-index.service` runs `sinnix fs scan --out-dir /realm/state/fs-index`.

## Commands

```text
sinnix fs scan --out-dir INDEX         # fresh scan into a new generation
sinnix fs refresh --index-dir INDEX    # reuse the last scan, refresh classifications
sinnix fs status --index-dir INDEX    # validity, freshness, coverage, last attempt
sinnix fs query --index-dir INDEX 'SELECT * FROM coverage'   # read-only SQL
sinnix fs classify explain|audit|report|import|vocabulary
sinnix fs links notes --root DIR [--reference-root DIR]       # plan wiki-link repairs
sinnix fs layout --refs            # literal /realm paths in source must exist
```

## Generations

Each `scan` or `refresh` builds a complete generation in a private directory,
reopens and validates every database and Parquet file, then switches one
`current` pointer. A failed attempt leaves the previous generation in place and
keeps its own candidate for inspection; `status` lists such leftovers and says
whether a writer is still active. Older generations are kept until reviewed.
`refresh --retained-inputs PATH` rebuilds from a retained scan and records that
the scan was not fresh.

DuckDB sessions use a 512 MiB buffer and two workers and spill to disk beside
the database. Read-only queries run in DuckDB's safe mode and cannot write
files.

## Content fingerprints

Files up to 8 MiB get a full SHA-256 (`fingerprint_kind: sha256-full`). Larger
files get `sample_sha256` from the first MiB, the last MiB and the size
(`sha256-head-tail-size-v1`). Matching samples are candidates only; the
`duplicates` view uses full digests, and `sampled_duplicate_candidates` is
separate. Even a full-digest match does not mean a copy may be deleted.

Each file's identity and modification time are checked before and after it is
read; symlinks and special files are never opened. Version-1 scans stored both
kinds of digest in one `sha256` column; on import, values for files over 8 MiB
are treated as samples.

## Coverage and boundaries

The scanner stops at configured boundaries (temporary work trees, Polylogue's
archive, Stashbox's store, build and dependency directories) and records a
`collection_boundary` row with the reason, never a guessed file count. A
boundary does not mean empty or unimportant. Missing roots, unreadable
directories and files that fail to read are recorded as errors, and
`status` reports coverage as incomplete when any exist. Directory totals above
an error are marked incomplete too. Roots are resolved to absolute paths
before matching exclusions, so an alias cannot bypass a boundary.

## Judgments

`judgments.jsonl` in the index directory holds authored
records, not derived data. `judgments` reads them directly, without DuckDB or
a rescan:

- `explain PATH`: the winning value for each facet (topic, role,
  maintenance_owner, preservation) with its source line. Operator decisions
  win, then the latest, then the most specific path. Equal-ranked
  disagreements are reported as ambiguous. An explicit `unknown` on a child
  masks a parent's value.
- `audit [--check-paths]`: invalid, ambiguous and noncanonical records; with
  `--check-paths`, also paths that no longer exist (history is kept as is).
- `report [--group-by role] [--role R] [--current-only]`: a Markdown
  projection of the ledger.
- `import FILE [--expected-sha256 HASH] [--allow-legacy-roles]`: validates the
  whole batch, locks the ledger and appends new records atomically; repeating
  an import is a no-op.
- `vocabulary`: the role codes (`collection-role-v2`). A role is a broad
  function; `detail` keeps the original wording.

Reads are capped at 8 MiB and 25,000 records. Exit 2 means an input or access
failure; exit 1 means audit findings or an ambiguous answer. A role,
maintenance owner or preservation note is never deletion permission or a
backup guarantee. The SQL `coverage` table summarizes legacy `subject`
decisions; inspection progress lives in the [file catalog](file-catalog.md).

## Note links

`note-links` plans repairs for wiki-style Markdown links in the chosen roots,
using unique front-matter IDs, aliases or exact filenames; `--reference-root`
directories provide targets but are never edited. It prints proposals with
source and target hashes and writes nothing. Ambiguous, self-referencing or
anchored links are left alone, and an incomplete scan yields no proposals.
Exit 2 means incomplete input, 1 that links were found, 0 none.

## Literal references

`sinnix fs layout --refs` finds literal `/realm` paths in sinnix,
Lynchpin and Polylogue source and exits 1 when a referenced path is missing.
The audit retains fixtures, examples, help text, historical inputs, selectors
and output locations with their source roles. Only required input literals
assert current availability. Explicit optional, historical, migration, pattern
and output roles use an inline `# sinnix-path: ROLE` marker at their consumer;
unknown roles fail the audit. `--refs --json` reports every role and the missing
required paths. Missing examples and retired-address migration guards do not
claim a broken consumer. An unreachable repository exits 2.

## Tests

`pkgs/sinnix-fs/tests` uses small synthetic files and real DuckDB databases,
including same-sample-different-middle files, legacy digest demotion, files
changing during a scan, FIFOs, aliases and malformed JSON.

## Maintenance

`sinnix fs maintain plan` emits a bounded JSON plan without traversing payloads.
It reports mounted-volume availability and the 15% Realm / 10% outer-volume
targets. `sinnix fs maintain admission` admits discretionary work at or above
10% / 5%, and exits 1 below either floor or when a required observation is
unavailable. The fresh-scan CLI and scheduled filesystem/Lynchpin refresh units
select their Realm output volume for this live condition. `--volume /outer-realm`
checks an outer-disk writer explicitly; an offline selected destination defers.
An unrelated full media disk does not block Realm-only work. The existing timers
retry on their next firing; there is no separate paused-job scheduler. Manual
Lynchpin operations, retained-input recovery, captures, backups and maintenance
remain available. No running job is interrupted and no space is reserved.
`sinnix fs maintain forecast` and the maintenance plan read capacity history
through the machine-telemetry segment owner. Its existing collector records
exact block counts and fragment size every five minutes, with filesystem UUID,
mount root, host and observed boot/mount identity. Existing sealed history is
retained; files predating this table remain explicit coverage absences.
The reader holds the owner's shared lock, validates membership and opens SQLite
read-only. Missing or changed members make the forecast unavailable.

The projection horizon is 30 days and requires 30 days of comparable observations,
with no gap over 30 minutes and a latest observation at most 15 minutes old.
UUID, mount root or total-capacity changes split the series. It sums positive
decreases in available bytes over the observed span; cleanup increases do not
cancel consumption. Rates, projections and threshold-crossing times use exact
rationals. The output names the selected segment/row identities, actual coverage
and assumptions. Until this history exists it reports insufficient history.
Admission uses current availability independently of this projection.

Offline outer mounts
are not activated for a capacity check. Mount IDs and an open mount descriptor
bind each capacity observation, so an unmount race cannot silently probe a
different filesystem. Filesystem availability is not an
estimate of exclusive or reclaimable Btrfs extents.

One executable lifecycle is `uv cache prune`: uv owns dangling entries
and in-use refusal. The plan binds the physical cache root's device, inode
and owner. Apply checks the exact plan SHA-256, refuses a replaced or symlinked
root, and pins the reviewed directory through an inherited descriptor. No force
flag or command from the plan is executed. Queue the operation with
`agentctl job start sinnix filesystem_maintenance -- PLAN --expected-sha256 SHA`.
The native exit status and output remain visible; a filesystem-space delta
includes concurrent activity and is not attributed wholly to pruning.

Historical scan inputs, manifests, AgentCTL events, genomes and uncertain
subvolumes are retained. The maintenance surface does not authorize deleting
them by age, size or a generated label. Their owners must establish exact
rebuildability, references and preservation before another lifecycle can retire
them. Plans are transient review inputs, not another state database.

Use `sinnix fs maintain account ABSOLUTE_PATH...` through the declared
`filesystem_accounting` operation for compression and sharing measurements.
It invokes the packaged native `compsize` and `btrfs filesystem du` tools with
noninteractive read-only root access, retains their complete output and exit
statuses, and returns incomplete on either failure. Physical roots and native
output distinguish requested addresses from current extent observations.
`compsize` counts referenced extents once, including compression; those
extents can also belong to files outside the selected set. Reported bytes
therefore do not equal reclaimable bytes. Neither measurement is a backup
check or deletion decision.

`plan --owner nix-store` selects native Nix garbage collection. Review native
unreachable paths with the `filesystem_store_gc_plan` operation, then apply the
digest-bound plan through `filesystem_maintenance`. The local Nix daemon owns
GC roots, concurrent temporary roots and collection locks. This route never
removes profile or generation roots and never uses forced store-path deletion.
Nix configuration environment overrides are removed before calling the fixed
local daemon route. Its complete output and failure status remain in the receipt.
