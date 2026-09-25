# File catalog

`sinnix-file-catalog` maintains a JSON catalog of files and collections whose
observations need to remain joined to the object that was inspected. It only
changes the catalog; it never moves, renames, hashes, or deletes payloads.

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

This catalog remains a curated observation store. Batch import avoids repeated whole-catalog writes and lookup rebuilding, but publication still serializes one JSON document. Extraction caches and native application records remain with their owners; a corpus-scale search database is not implied by the catalog report.
