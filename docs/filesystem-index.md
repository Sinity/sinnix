# Filesystem index

`sinnix fs` (package `sinnix-fs`) keeps an inventory of directories, bounded
content fingerprints, and views of the authored file judgments. It does not own
any storage and never deletes or deduplicates anything. The weekly
`sinnix-fs-index.service` runs `sinnix-fs run --out-dir /realm/state/fs-index`.

## Commands

```text
sinnix fs run --out-dir INDEX         # fresh scan into a new generation
sinnix fs ledger --index-dir INDEX    # reuse the last scan, refresh classifications
sinnix fs status --index-dir INDEX    # validity, freshness, coverage, last attempt
sinnix fs query --index-dir INDEX 'SELECT * FROM coverage'   # read-only SQL
sinnix fs judgments explain|audit|report|import|vocabulary
sinnix fs note-links --root DIR [--reference-root DIR]       # plan wiki-link repairs
sinnix realm-layout-check --refs            # literal /realm paths in source must exist
```

## Generations

Each `run` or `ledger` builds a complete generation in a private directory,
reopens and validates every database and Parquet file, then switches one
`current` pointer. A failed attempt leaves the previous generation in place and
keeps its own candidate for inspection; `status` lists such leftovers and says
whether a writer is still active. Older generations are kept until reviewed.
`ledger --retained-inputs PATH` rebuilds from a retained scan and records that
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

`sinnix realm-layout-check --refs` finds literal `/realm` paths in sinnix,
Lynchpin and Polylogue source and exits 1 when a referenced path is missing.
Test fixtures and docstrings are classified `fixture` and `cosmetic` and not
checked, so a missing example is not a broken consumer. An unreachable
repository exits 2.

## Tests

`pkgs/sinnix-fs/tests` uses small synthetic files and real DuckDB databases,
including same-sample-different-middle files, legacy digest demotion, files
changing during a scan, FIFOs, aliases and malformed JSON.
