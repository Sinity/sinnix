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
