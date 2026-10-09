# File catalog

`sinnix-file-catalog` maintains a JSON catalog of files and collections whose
observations need to remain joined to the object that was inspected. It only
changes the catalog; it never moves, renames, hashes, or deletes payloads.

The tools are local to the Sinnix checkout. Run these examples from the checkout
with its scripts and Python library available:

```sh
export PATH="$PWD/scripts:$PATH"
export PYTHONPATH="$PWD/pkgs/sinnix-lib${PYTHONPATH:+:$PYTHONPATH}"
```

Terminal output quotes paths and escapes control characters. Pipe output retains
raw resolved paths and JSON data; display formatting does not change catalog bytes.

The catalog path is always explicit:

```sh
sinnix-file-catalog --catalog /path/catalog.json import observations.json
sinnix-file-catalog --catalog /path/catalog.json search transcript
sinnix-file-catalog --catalog /path/catalog.json show ASSET-UUID
sinnix-file-catalog --catalog /path/catalog.json relocate ASSET-UUID /new/path
sinnix-file-catalog --catalog /path/catalog.json validate
```

An observations file is a JSON list. Each item has `current_path`, `title`,
`description`, and at least one inspection with nonempty `method`, `scope`,
and `basis`. `kind` defaults to `file`; tags, uncertainty notes, relations,
and an ID are optional. An omitted ID receives a UUID when first imported.
Repeated imports update the existing asset by ID or current path and retain
unknown annotation fields.

Each imported inspection also receives the asset title and description as a
snapshot, preserving the authored context if the asset is edited later.

Each imported path must exist. The catalog records device, inode, size,
modification time, and mode. If an existing path has a different identity,
the import fails instead of replacing the identity associated with prior
inspections. A supplied `identity.sha256` is retained as an attributed value;
the command does not calculate hashes as part of import.

After an external same-filesystem rename, use `relocate`. The old path must be
absent, the new path must exist, and its recorded identity must match. The
command appends the old path to `previous_paths` and updates only catalog JSON.
Writes use an adjacent lock and an atomic replacement, so invalid input cannot
leave a partially written catalog.

Use `observe observations.json --expected-sha256 DIGEST` for reviewed location
changes. Each row names an asset ID, actor, basis, reason and explicit action:
`metadata`, `content_revision`, `collection_replacement` or `unavailable`.
Available locations also require the exact reviewed `expected_identity`.
The digest guards the whole catalog and refuses stale review before mutation.
Metadata observations retain earlier identities and inspections without claiming
byte continuity. Revisions retain the asset UUID, move earlier content evidence
into revision history, and give the current revision metadata-only coverage.
Missing paths, offline mounts, access denial and wrong object types are recorded
separately. Device numbers are observations; filesystem UUID and Btrfs subvolume
identity are recorded when available. These checks do not hash payloads.

Record an observation after inspecting a file, while its content and scope are
still available. Use specific descriptions, date roles and evidence for
relationships. Distinguish a whole still image, a sampled video frame, an
opening excerpt, embedded metadata and a filename-only classification. Keep
private annotations outside the repository.

`sinnix-file-catalog-report` renders an offline searchable HTML view from the
catalog and the HTML report template. It includes inspection limits, former
paths and links between related records:

```sh
sinnix-file-catalog-report --catalog /path/catalog.json \
  --template dots/_ai/skills/html-report/templates/report.html \
  --output /path/catalog.html
```

The renderer embeds the canonical data without external assets or network
requests. Search, inspection-method filters and related-file controls operate
locally. Original-file links require local filesystem access. Neither command
depends on a running indexing service.

## Parallel collection surveys

Workers write separate observation lists. Import a reviewed batch atomically:

```sh
sinnix-file-catalog --catalog /path/catalog.json import lane-a.json lane-b.json --on-conflict record
sinnix-file-catalog --catalog /path/catalog.json coverage --kind collection
sinnix-file-catalog --catalog /path/catalog.json search geology --kind collection --limit 20 --offset 0
```

Duplicate paths within one batch are refused so the coordinator must reconcile overlapping assignments. `record` preserves existing conflicting annotations and stores proposed values with their incoming inspection evidence in `annotation_conflicts`; compatible new fields and list observations are retained. `error` refuses a conflicting batch. The default `replace` retains the original update behavior for deliberate revisions. All modes enforce file identity and preserve inspection snapshots. A changed device number is still insufficient evidence to rebind an old observation.

Collection surveys can include `facets` (string-valued topic, role, maintenance_owner and preservation), `organization` (action and rationale, with optional proposed_path and dependencies), and evidence-bearing `related_paths`. Related paths do not require the destination to be cataloged and are not identity or equivalence assertions. Search includes all recorded annotations. The HTML report displays these fields, competing annotations, and filters for record kind and inspection coverage.

Optional `coverage` records have status (`sampled`, `metadata_only`, `complete`, `native_boundary`, or `unavailable`), a nonempty scope and unit, discovered_count (nonnegative integer or null), inspected_count (nonnegative integer), and optional string exclusions. Complete coverage requires a known denominator equal to the inspected count within the stated scope. Coverage without an explicit record is `unrecorded`; taxonomy inheritance never establishes inspection completion. The coverage command counts catalog records by kind, status and proposed action. It does not sum overlapping collection populations or imply a filesystem-wide denominator.

The production ownership and invalidation design for incremental extraction is in [Incremental file enrichment](file-enrichment.md). It is a contract for later implementation, not an installed queue.

This catalog remains a curated observation store. Batch import avoids repeated whole-catalog writes and lookup rebuilding, but publication still serializes one JSON document. Extraction caches and native application records remain with their owners; a corpus-scale search database is not implied by the catalog report.

## Readable enrichment in the offline report

The report presents retained enrichment as ordinary text: document type, language, topics, retrieval questions, recorded claims with their statuses and source locators, selected outlines, and extraction evidence. Repeated utility/questions are deduplicated for display; the complete original record remains embedded and available in the evidence details. Unknown fields and legacy enrichment shapes are preserved rather than rewritten to fit the presentation.

A claim's status is copied from its observation; rendering does not independently verify it. Missing status or locator is shown as missing. Source locators are escaped text, not executable links. Evidence paths are made into local-file links only when explicitly absolute and well-formed. Rendering never opens or stats those source files, executes received HTML, or visits remote resources. An untruncated extraction does not imply complete semantic review.

The document-type selector contains the types actually present in the catalog. It is a retrieval filter, not a replacement for the controlled collection-role ledger. Filters combine with record kind, method, coverage and text search; reset and relationship/hash navigation clear the type filter consistently. The page computes each static record's search text and method list once at initialization instead of reading its large evidence text again for every keystroke.

The renderer remains an offline projection of one JSON catalog. It sends no annotations, changes no source payloads, and preserves the complete catalog in its safe application/json block. Output-generation timestamps are distinct from individual inspection timestamps and from the original documents' publication dates.

## Coordinated placement changes

`prepare-relocation MOVES --output RECEIPT` binds every affected asset to the catalog digest and its observed pre-move identity. `relocate-batch RECEIPT` verifies every destination and publishes the catalog once. A stale catalog, collision or changed payload refuses the entire metadata transaction. `--record-existing-drift` explicitly retains earlier identity evidence without certifying its hashes for the currently observed object. `--retain-unavailable` records already absent historical assets without inventing a new current location.

`resolve HISTORICAL-PATH` uses retained collection boundaries and path history to resolve references without filesystem aliases. An address reused for a different cataloged object requires `--id ASSET-UUID`; unavailable records remain unavailable.

The report renderer accepts `--judgments` for authoritative current classifications, displayed separately from original asset observations. Shared role definitions normalize legacy categories while retaining their attributed wording. Raw catalog and navigation sources stay private. `sinnix-report-site` publishes an explicit manifest of individual files; it refuses directory links, unsafe URLs and sources beneath declared private roots. Subject homes own canonical analyses, while the site holds the selected publication projection.

## Current navigation checks

`sinnix-navigation-audit --manifest /path/navigation-audit.json` checks local
Markdown links in explicitly selected current entrance documents. The JSON
manifest has `schema_version: 1`, an absolute-path `documents` list, and an
optional absolute-path `external_roots` list. External roots are reported as
unprobed without accessing them. Remote links and code examples are excluded;
missing local destinations return a nonzero exit status. The tool is read-only
and does not scan imported packages or historical reports.

The workstation's private manifest is owned by the report catalog. Run its
declared `navigation_audit` operation after moving managed collections or
editing current entrances. `lake-lint` separately verifies declared managed
containers and rejects recreation of retired paths.
