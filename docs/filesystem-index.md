# Filesystem index: scope and integrity

`sinnix-fs` owns a directory inventory, bounded content observations, and materialized views of separately authored judgments. It is not a storage owner, an application-archive replacement, or an automatic deduplicator.

## Content identity

Content schema v2 separates full-file `sha256` from `sample_sha256`. Files at or below the 8 MiB full-hash bound receive `fingerprint_kind: sha256-full`; larger files receive `sha256-head-tail-size-v1`, calculated from the first MiB, last MiB, and decimal file size. `fingerprint_bytes` states the payload bytes read. Matching samples are candidates, not evidence of byte equality.

The legacy v1 scanner put both algorithms in a column named `sha256`. Importing a v1 observation must interpret that field using the recorded size: above 8 MiB it is a sample and is demoted to `sample_sha256`. Unknown schemas, errors and malformed digest values do not become content IDs. The raw input remains a versioned observation; clients must not reinterpret legacy columns without the schema.

`duplicates` contains only full-file digest groups. `sampled_duplicate_candidates` is separate and carries an explicit limitation. Even a full-hash match is not deletion authorization: source acquisitions, application ownership, independently retained replicas and preservation obligations still matter.

Before and after each fingerprint, lstat/fstat identity and modification metadata are compared. Symlinks and nonregular files are not opened as payloads; nonblocking, no-follow reads prevent ordinary stream substitution from hanging fingerprinting. Empty files remain represented. Content excerpts have their own bounded-read budget. These checks detect ordinary races; they are not cryptographic claims about a hostile filesystem or guarantees that data has not changed since a historical observation.

## View-only repair

From the declared project environment, the source command is:

```sh
PYTHONPATH=pkgs/sinnix-lib python3 scripts/sinnix-fs content-views --index-dir /path/to/index
```

This transaction replaces only the two comparison views in `content.duckdb`. It recognizes the legacy and typed column layouts; it does not rescan payloads, rewrite the `files` table, edit JSONL/Parquet, or rebuild authored/inherited judgments. Do not break an active writer's database lock to run it. Updating source does not activate a NixOS service or replace an older packaged scanner; a later legacy rebuild can restore its legacy views until the package is updated normally.

## Collection boundaries, not invisible data

The content scanner stops at configured native or temporary collection boundaries, including temporary work, Polylogue's live and retired native archive, and Stashbox's store. It emits a `kind: collection_boundary` row with `exclusion_reason`, no digest and no invented descendant count. A boundary does not mean empty, deleted, unimportant, unbacked, or disposable. Native owner queries and the directory inventory remain distinct access paths.

Pruning happens before entering the excluded child directory. Exclusions match path components, so a rule for one directory cannot swallow a similarly prefixed sibling. Build/dependency-directory exclusions also leave explicit boundary records. Missing roots, non-directory roots, and unreadable directories produce error observations, rather than an indistinguishable empty result. Directory inventory traversal uses a deque while preserving breadth-first ordering.

This remains bounded generic content inspection, not a claim that every native record or filesystem byte was indexed. Do not enable deeper traversal merely to make a missing native adapter appear to work.

## Judgments and publication

Authored judgment and reference ledgers are not regenerable simply because they share a directory with derived indexes. Ledger materialization uses the JSON readers already supplied by the declared DuckDB runtime; it does not install extensions or require a per-user extension cache at runtime. Prefix inheritance matches the named path or descendants separated by `/`, not lexical lookalikes. Content-addressed judgment joins use only full-file digests, never legacy large-file samples.

Materialization uses explicit nullable schema columns. Malformed JSON fails staged publication rather than being silently skipped. Existing artifacts remain in place when staging or validation fails; there is no claim that several separately published filesystem artifacts form one global transaction.

The focused tests under `pkgs/sinnix-fs/tests` use synthetic small files and isolated real DuckDB databases. Counterexamples include equal head/tail/size with a different middle, legacy sample demotion, in-flight changes, missing roots, FIFOs, aliases, malformed JSON, quoted filesystem paths, non-traversed collections, and prefix siblings. Test dependencies belong to the existing Nix script-suite declaration, not an undeclared host installation.

## Direct authored classifications

The `judgments` actions read the existing `judgments.jsonl` without opening DuckDB, rescanning directories or reading the classified payload:

```sh
PYTHONPATH=pkgs/sinnix-lib python3 scripts/sinnix-fs judgments --index-dir /path/to/index explain /absolute/path
PYTHONPATH=pkgs/sinnix-lib python3 scripts/sinnix-fs judgments --index-dir /path/to/index audit
PYTHONPATH=pkgs/sinnix-lib python3 scripts/sinnix-fs judgments --index-dir /path/to/index report
```

`explain` separates topic, role, maintenance_owner and preservation facets from legacy fields. Resolution uses operator precedence within a target, then decision time, followed by the most-specific matching path for each field. An explicit unknown child rule masks broader assumptions. Equal-ranked disagreements are returned as ambiguous rather than selected by row order. This is the conservative direct-lookup contract; existing SQL materializations are not refreshed by the call.

The reply includes source lines, full decisions, record hashes and ledger identity. Lexical resolution deliberately does not dereference aliases, assert path existence, hash contents, or match content-addressed decisions from a guessed digest. `audit --check-paths` explicitly opts into location metadata checks, without enumerating descendants. Absent historical paths remain history; they are not automatically rewritten to similarly named current directories.

Reads are bounded to 8 MiB and 25,000 records. Malformed JSON fails the command without a partial result. Invalid definitions, including filename-shaped sha256 targets and timezone-free timestamps, are reported and excluded from lookup while remaining untouched on disk. Exit 2 indicates input/access failure; exit 1 indicates audit findings or ambiguous explanation.

`report` emits a rebuildable Markdown collection-facet projection; the JSONL remains its only source of truth. Preserve original rows and actor attribution when adding fresh observations. A maintenance owner is not the topic of all data it stores, and a preservation constraint is not a backup certificate or deletion permission.

`judgments import observations.jsonl` validates an entire incoming batch, locks the ledger, and atomically appends previously unseen definitions. Existing historical rows, including invalid historical definitions, remain intact; invalid incoming definitions refuse the whole batch. Retries of identical records are idempotent. Methods, actors, timestamps and evidence are supplied explicitly by the caller; importing an agent observation does not turn it into an operator decision. The combined ledger must stay within the reader's size and record bounds. Import does not refresh DuckDB or reports.

The SQL `coverage` table summarizes inherited legacy `subject` decisions over indexed path rows. It does not measure content inspection or the current four collection facets. Use the file catalog's explicit inspection coverage for survey progress, and retain the scan's own completeness and exclusion information separately.

## Portable note references

`note-links` is a read-only repair planner for legacy wiki-style Markdown references. It reads only explicitly selected current roots and reference-only roots:

```sh
PYTHONPATH=pkgs/sinnix-lib python3 scripts/sinnix-fs note-links \
  --root /path/to/current-notes \
  --reference-root /path/to/historical-references \
  --exclude-component native-workspace
```

Bare references resolve by a unique retained frontmatter ID, explicit alias, or exact scoped filename. Current roots precede historical roots. Path-qualified references require an exact scoped path; there is no basename fallback. Self-references, ambiguous names, unknown pipe syntax, and heading anchors are left unchanged. Frontmatter, code, comments, embeds and escaped references are not rewritten. The parser supports a narrow string-only frontmatter subset and never evaluates YAML tags or anchors.

The output lists source hashes, target hashes and exact character-span proposals. It performs no writes. Reference-only roots supply targets but never source edits; native Git workspaces and declared exclusions remain explicit boundaries. File, byte, directory and depth budgets bound work. An incomplete or malformed scope emits no applicable changes rather than making uniqueness claims over a partial scan. Exit 2 means incomplete input/coverage, exit 1 means references were observed, and exit 0 means none were found.

Applying a chosen proposal remains a separate operation: revalidate every identity-resolution input, preserve source preimages, reject concurrent changes, and check that all intended link destinations still resolve. Preserve newline encoding, original note IDs, and all non-link text. A historical reference remains a historical snapshot even after it becomes clickable; restoring a Git blob does not promote its plans or conclusions into current authority.

## Controlled role categories and retained detail

The role facet uses `collection-role-v1`, declared in `ROLE_VOCABULARY` by the filesystem owner. `judgments vocabulary` returns the codes and definitions without opening a ledger or a classified path. Topics remain open-ended; maintenance ownership and preservation constraints retain their own semantics. A role code is never a deletion policy, freshness claim, backup certificate or validation of source assertions.

A category describes the broad function; `detail` retains the original descriptive wording. Normalizing a role is a new attributed rule observation referencing its source decisions, not a claim that all original descriptions are synonymous or freshly inspected. Preserve all prior records, actor attribution and source dates. The direct resolver exposes retained details and full winning evidence. Unknown child classifications continue to mask inherited values; operator precedence and ambiguous equal-ranked decisions are unchanged.

New imports reject unknown known-role codes and non-text details before modifying the ledger. The explicit `--allow-legacy-roles` option admits historical source definitions without pretending they are normalized. Effective noncanonical roles and ambiguity remain audit findings; superseded historical wording is not treated as an active error merely because its bytes remain in the ledger. `--expected-sha256` refuses a reviewed import if the current ledger identity changed.

```sh
python3 scripts/sinnix-fs judgments vocabulary
python3 scripts/sinnix-fs judgments report --group-by role
python3 scripts/sinnix-fs judgments report --role capture
python3 scripts/sinnix-fs judgments import reviewed.jsonl --expected-sha256 HASH
```

Path and role reports are projections of the same ledger, including source detail. They do not require native-store traversal or rebuilding large SQL materializations. Existing older binaries can still read the additive records, but do not acquire new validation or grouping behavior until their source/package is updated.
