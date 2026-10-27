# Beads upstream-patch exception

Beads is an accepted exception to the no-upstream-patches rule. At pinned upstream `gastownhall/beads` commit `2bb1e20de0f0072d7600656ea3cb7f606929dcc6`, a stock replacement does not preserve the gateway's full contract. Keep `owner-contracts.patch` and `standalone-context.patch`. The patch application is in `flake/package-set.nix`.

The feasibility review for `sinnix-emq2` inspected the pinned source, both patches, `sinnix_agent_gateway/beads.py`, `actions/beads.py`, and `generate_beads_inputs.py`. This decision applies to that pin, not to unexamined upstream releases. No stock implementation or performance benchmark was run. The decisive gaps are observable guarantees, so no performance claim is needed to reject replacement at this pin.

The decisive upstream sources are `internal/httpapi/update.go:updatePreconditionResult`, `internal/httpapi/batch_apply.go:applyPreconditionResult`, and `internal/httpapi/problem.go:PreconditionFailed` (the response discards the observed version, including from its detail), plus `internal/beads/context.go:buildRepoContext` (the Gitless context failure). Candidate alternatives were checked in `cmd/bd/query.go`, `sql.go`, `sql_proxied_server.go`, `batch.go`, and `serve.go`.

## Capability comparison

| Patch capability used by callers | Stock equivalent or gap at this pin | Disposition |
| --- | --- | --- |
| `owner schema` publishes the HTTP request schemas and `x-beads-owner-read`; generated inputs retain nullable fields, typed metadata, native operation identities and version guards. | `bd serve` publishes its OpenAPI document at `/v0`. That can supply the existing HTTP operation schemas, but has no analytical owner-read schema. The generator would need a replacement source for `OwnerReadInput`. | HTTP schema extraction is replaceable; analytical schema is missing. |
| `owner call` invokes the typed HTTP roles locally for all generated actions, preserving validation, actor, error envelopes and operation results without a listener. | `bd serve` exposes those native roles over HTTP. A supervised server and adapter could replace this transport; running one process per operation would need startup/latency measurement. | Transport alone does not justify the exception. |
| Guarded mutations and `applyBatch` preserve `expected_version`, status/assignee guards, symbolic backward bindings, typed JSON metadata, blocker policy and atomic rollback. | Stock HTTP `updateIssue`, lifecycle operations and `applyBatch` already have transaction-local guards. Stock text `bd batch` only supports a narrow grammar; it cannot carry the generated request union, and its `close` bypasses blocker policy. Raw SQL writes bypass native issue semantics. | Use HTTP for a possible replacement, never a read-then-write guard or a sequence of CLI writes. Atomic guards are already upstream. |
| Conflict responses retain `actual_version` from the transaction that refused a guarded write, with exact expected/actual decimal tokens and row-token domain/coverage disclosure. `_run` preserves the owner error in `details.owner_error`; native actions expose owner results. | Stock HTTP deliberately omits the observed version after rollback. Stock storage wraps a sentinel with text rather than retaining a typed observation. A later read cannot recover the refusing transaction's observation. Parsing error prose is not the published HTTP contract. | Blocking contract gap. A later read can race and would misrepresent the evidence. |
| Exact signed 64-bit row tokens leave owner reads and calls as decimal strings, including nested results and conflicts, without converting authored metadata numbers or identically named metadata keys. | Stock HTTP publishes numeric row revisions. A schema-aware Python adapter could losslessly convert JSON integers and add the same partial-coverage disclosure. | Replaceable at the adapter boundary; observed conflict data is still missing. Row tokens do not detect every kind of update. |
| `get(as_of)`, query `at`, native `beads.read` and closure resolve HEAD/ref/hash or RFC3339 time once, then pin issues, labels, comments and relationship includes to the same commit. Temporal output distinguishes exact commits from working fingerprints. | Stock `bd query`/HTTP query has no equivalent historical read product. `bd sql` can use Dolt `DOLT_HASHOF`, `DOLT_LOG` and table `AS OF` to reconstruct it, provided every table and include uses the resolved commit. | Possible SQL reimplementation, not an absent database primitive. Requires the analytical engine and temporal semantics to move into the gateway. |
| Working reads fingerprint the database before/after and reject `source_changed`; query checks the revision across owner pages. Task authority attestation reports working and committed revisions separately; maintenance uses before/after revisions. | Stock SQL can read `DOLT_HASHOF_DB()` and stock proxied single-query reads use a read transaction. Separate stock query/graph/include requests do not establish the shared observation. SQL multi-statement proxied execution reports `OK`, not a combined read product. | Could reconstruct with explicit fingerprint checks or one SQL observation; ordinary composed commands lose the current consistency checks. Working fingerprints remain non-replayable. |
| Dependency closure reports direction/relation/depth, missing members, node/edge truncation, completeness, frontier, leaves, cycles, readiness and counts. Provenance is separate from dependency membership, including metadata origin links. `beads.closure`, graph enrichment and native reads pass this evidence through. | Stock dependency tree/cycles/blocking/count endpoints supply components. They do not supply this combined, revision-bound product and completeness/provenance model. SQL could fetch pinned graph data for a replacement traversal. | Reimplementable with a pinned SQL graph engine; combining live endpoints or silently truncating is insufficient. |
| Owner filtering (boolean AST, native query expression and filters), ordering, projections, exact totals and grouped aggregation run before serialization. | Stock `bd query` supports native expressions and ordering; SQL supports predicates, projection, `COUNT` and `GROUP BY`. Matching all owner views, exclusions, filters and relative-time semantics requires a replacement planner. | SQL can preserve server-side aggregation; fetching every issue body to count would regress the contract and potentially performance. |
| Owner limit/offset paging returns `total_exact` and `has_more`, with explicit closure bounds. Gateway query collects pages at one revision and retains immutable client cursor pages. | Stock query offset is supported only in proxied-server mode and has ordering constraints; SQL has `LIMIT/OFFSET`. The gateway's retained snapshot/cursor service already owns client continuation. | Client cursors can remain unchanged; SQL pages must retain the resolved revision, totals, order and coverage semantics. |
| Explicit external `BEADS_DIR` works with cwd equal to the declared authority workspace under `/realm/state/tasks/*`, outside source Git. `where`/context identity is attested before actions. | Stock `buildRepoContext` finds `BEADS_DIR`, then fails `GetMainRepoRoot()` when neither cwd nor the store is in Git. `--db` does not supply the missing repo context. Running from a source checkout or adding Git to the store changes the reported context or storage setup. | Blocking gap for the existing standalone authority contract; upstream needs explicit Gitless context support. |
| Maintenance (`export`, Dolt push/pull, backup create/list/restore) retains owner commands and reports `per_step_commits`. | These commands are already stock. Their gateway pre/post attestation still depends on owner read and standalone context. | Keep commands unchanged; no atomic maintenance guarantee is claimed. |

The patch also fixes generic JSON wrapping to preserve authored numeric values and handle an empty object. The gateway decodes owner JSON and forwards native results, so a replacement must preserve those values. This is reproducible adapter work rather than an independent reason to retain a fork.

Two other changes in `owner-contracts.patch` affect native routed `bd show`: foreign stores use their own database despite the caller's environment, and unresolved foreign prefixes report `task_store_mismatch` with the searched store. The gateway's Beads adapter does not call `show` or rely on those diagnostics; it selects an explicit authority for every call. They are not reasons for this gateway feasibility decision. The patch's text-batch close fix likewise is not on the gateway's `owner call applyBatch` route.

## Generated native action inventory

`generate_beads_inputs.py` selects the following stock HTTP operation identities. Their local transport and token/error projection currently come from `owner call`; `actions/beads.py` generates the corresponding actions from these contracts:

- Writes: `createIssue`, `updateIssue`, `addComment`, `claimIssue`, `releaseIssue`, `closeIssue`, `reopenIssue`, `compareAndSetMetadata`, `batchCreateIssues`, `applyBatch`, `batchCloseIssues`, `claimNextIssue`, `addDependencies`, `removeDependency`, `rememberMemory`, `forgetMemory`.
- Reads: `getDependencyTree`, `listDependencyCycles`, `listMemories`, `getMemory`, `listRelatedIssues`, `listDependencies`, `countDependencyEdges`, `listBlockingAnnotations`.

The separate generated `OwnerReadInput` feeds `beads.read`. High-level query, get, closure, graph enrichment, authority attestation and maintenance revision reporting also call `owner read`. High-level live graph and memory projections additionally use stock CLI commands.

## Retirement condition and verification

Retire the exception when pinned upstream supplies Gitless explicit-store context and transaction-observed conflict versions, together with an equivalent analytical read API or a demonstrated stock-SQL implementation of the full snapshot, closure, filtering, aggregation and paging contract. HTTP transport is a viable candidate for native actions. Prove exact token/metadata handling, rollback and blocker behavior, historical table/include pinning, changed-source rejection and completeness before deleting either patch. Measure any alternative that adds process/server startup or graph/body materialization against the current route.

The focused retained-contract check is:

```sh
nix build --no-link -L .#checks.x86_64-linux.beads-owner-contract
```

The generated contract comparison is also part of `sinnix-agent-gateway-suite`; it runs `bd owner schema` and `generate_beads_inputs.py --check`. Gateway adapter tests alone use synthetic owners and do not prove stock compatibility.

After activation, the coordinator can verify the installed standalone read path without writing task state:

```sh
env -C /realm/state/tasks/sinnix/.beads BEADS_DIR=/realm/state/tasks/sinnix/.beads /run/current-system/sw/bin/bd --actor coordinator --readonly --json owner read <<'JSON'
{"roots":["sinnix-emq2"],"depth":0,"limit":1,"at":"HEAD","include":["comments","dependencies"]}
JSON
```

Require a successful response with `temporal.pinned: true`, `temporal.semantics: exact_revision`, the same resolved revision on the includes, and the requested task. Also compare `nixos-version --configuration-revision` to the coordinator's intended integration commit. This comment/documentation change requires no activation of its own; the command checks the retained installed behavior, not equivalence of a stock implementation.
