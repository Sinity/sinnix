# History Cleanup Methodology

This document captures the reusable process behind the `sinex` history-analysis,
commit-message rewrite, and structural split/merge/reorder preparation work.

It is intentionally broader than the local `sinex` launch pack. It defines the
reusable methodology for the shared `history-cleanup` skill rather than living
inside a target repository package.

## Core Principle

Treat history cleanup as two separate products:

1. `message rewrite`
   Improve commit messages, bodies, attribution, and auditability.
2. `structural surgery`
   Prepare actual split / merge / reorder execution packs.

Do not blur them. A branch can be:

- message-rewritten but not structurally ready
- structurally analyzed but not determinized
- fully turn-key for a structural rewrite

This distinction has to stay explicit in every manifest and status note.

## Canonical Location Model

The reusable toolkit lives under `sinnix/dots/_ai/skills/history-cleanup/`.
The durable project run corpora are currently hardcoded to an external root:

- `/realm/inbox/history-rewrite-project-runs/<project>/`

The target repository may still keep:

- a symlink
- or a thin pointer note

but the canonical worked record should stay outside the repo rather than being
tracked inside the skill tree.

## Success Criteria

The process is done only when all of the following are true:

- the current `HEAD` is covered, not just an older snapshot
- the dirty tree has been cleaned or explicitly carved out first
- a pre-rewrite backup exists outside the repo
- canonical corpora exist for all targeted commits
- atomicity coverage exists for all targeted commits
- structural residue is either:
  - converted into executable specs, or
  - explicitly isolated as a deliberate out-of-scope optional pack
- if structural surgery is in scope:
  - disposable replay completed successfully
  - every structural exec step proved the exact planned source SHA band before
    applying
  - final tracked-tree equivalence between source repo `HEAD` and rewritten repo
    `HEAD` is proven
- readiness docs and manifests agree with the actual state
- no stale "turn-key" claim remains in any canonical entry point

## Phase Model

### Phase 0: Freeze the Surface

Before touching history:

- identify current branch, `HEAD`, upstream divergence, and dirty files
- decide whether top-of-branch new commits belong in the target corpus
- clean and commit the dirty tree first if those changes should survive the rewrite
- record backup refs and external backups before any destructive history operation

Minimum outputs:

- branch/status snapshot
- backup ref
- external mirror clone or bundle

## Phase 1: Build the Evidence Corpus

Inputs are not just git diffs.

Collect and canonicalize:

- current git history
- commit metadata
- current tree state
- session logs when intent or authorship matters
- plan files when they sharpen scope
- existing audit notes if present

This phase exists so later work does not depend on fuzzy memory.

### Repository-Local Semantics Must Be Captured Early

Before workers start rewriting messages or planning structural surgery, record
the local semantic rules that are easy to misread from diffs alone.

Examples:

- project-specific test policy
- generated-noise directories
- house style around fixture setup
- whether a helper attribute is actually expensive or only looks expensive

For `sinex`, one important example is:

- keep `#[sinex_test]` as the default test attribute
- if a test does not need sandbox facilities, omit the `TestContext` parameter
- that omission makes the abstraction effectively zero-cost, so "switch back to
  raw `#[test]` to avoid overhead" would be the wrong interpretation

Do not turn a repo-local semantic note into a blanket history rule. The point
is to avoid misreading intent, not to impose a second policy layer over the
historical commit stream. If a source commit migrates tests, preserve that
migration; if it does not, do not invent one.

These repo-local rules should be written down in the bootstrap artifacts before
any agent starts turning history into narratives.

### Repository History Surface Must Be Quantified Before Packet Sizing

Before choosing worker ownership ranges, derive a hard-data surface for the
target repository:

- full log text
- full diff log
- numstat log
- per-commit patch line / byte / file-count summary
- packet-budget simulation for the intended worker model

This exists to prevent fake certainty around worker sizing.

Do not decide "32 commits per worker" or "48 commits per worker" until the repo
surface exists. In some repos that geometry is fine. In others it is
structurally impossible.

For `polylogue`, a concrete measurement on `1074` commits showed:

- median single-commit patch size already around `3.5k` patch-token-equivalent
- p90 around `31k`
- p95 around `54k`
- p99 around `147k`

That means a 128k-context worker cannot be assigned by raw commit count alone
if the contract requires full patch reading.

The consequence is:

- packetization must be token-budgeted
- merge commits should be handled separately
- heavy single commits should be isolated
- jumbo commits should be decomposed into file-group subpackets plus reduction
- packet edges should usually receive message-only context instead of duplicated
  full diffs

## Phase 2: Carve History into Waves

Use waves for scalability.

Idealized wave rules:

- process contiguous history bands
- choose worker ownership from measured transport size, not raw commit count
- for low/medium-diff repos, `24-48` owned commits per worker can be acceptable
- for high-diff repos or 128k-context workers, derive packets from a full-diff
  budget first and expect much smaller owned ranges
- use only small boundary overlap between workers: `0-2` commits
- do not rely on overlap for context
- instead, require each worker to read sliding adjacent local windows such as:
  - read `1..4`, emit `1..3`
  - read `4..7`, emit `4..6`
  - read `7..10`, emit `7..9`

That gives contextual reading without duplicate ownership.

Use `prepare-wave` to generate:

- manifest
- range input files
- cheap surface facts
- `.sqlx` and semantic churn split

### Idealized Wave Geometry

Recommended default geometry:

- one "message rewrite" wave and one "structural prep" wave can coexist, but do
  not mix their outputs
- `6-8` workers per wave is usually the sweet spot
- start from input-budget targets, not fixed commit counts
- for 128k-context workers, a practical first pass is usually about `40-60k`
  input-token-equivalent of diff material per packet, leaving headroom for
  instructions and output
- when the repo-surface analysis shows p90 single-commit diffs already consume
  most of that budget, switch to `heavy` single-commit packets and `jumbo`
  decomposition rather than forcing larger ranges
- in low/medium-diff repos, `16-32` owned commits can still be reasonable after
  measurement
- `48` owned commits is acceptable only when the measured diff surface proves it
  fits
- boundary overlap should be only `0-2` commits
- contextual reading should come from sliding local windows, not ownership
  overlap

For very large commits:

- do not enlarge the worker range
- instead, let the worker subdivide the commit internally by file groups
- preserve one commit-level output row, but allow multiple internal review
  bundles for that row

## Phase 3: Run Strict Commit-Message Rewrite Waves

Worker contract for rewrite waves:

- read the full patch for every owned commit
- read adjacent commits when the `why` or boundary is unclear
- discount generated noise such as `.sqlx` unless it is itself the semantic change
- produce full commit messages, not just subjects
- include bodies that explain:
  - what changed
  - behavioral effect
  - why, when defensible from patch + nearby context
- record process metadata per item:
  - full patch confirmed
  - surrounding context used
  - why basis recorded
  - strict-process attested

Do not allow vague completion language like:

- "done"
- "complete"
- "finalize"

unless the diff really supports that.

### Commit Message Contract And Quality Gate

Use [COMMIT_MESSAGE_CONTRACT.md](/realm/project/sinnix/dots/_ai/skills/history-cleanup/COMMIT_MESSAGE_CONTRACT.md)
as the explicit bar for rewrite quality.

Minimum gate before a message row is considered good:

- subject names the dominant change, not just process status
- body exists
- body explains effect, not only mechanics
- body names at least one concrete surface when recoverable from the patch

Recommended gate for large or mixed commits:

- body is usually `40+` words
- body is split into at least two short paragraphs unless the commit is truly simple
- `why` is included when adjacent context makes it defensible

If a rewritten corpus does not pass that bar, do not call it finished merely
because every commit has a non-empty body.

Run `message-quality-report` against candidate corpora before applying a
rewrite map. This exists specifically because earlier rewrite passes could look
better than baseline while still remaining too vague to function as a semantic
index.

### Rewrite Proof Obligation

A rewrite row is only "strict" when all of the following are true:

- full patch was actually read
- generated churn was discounted consciously
- adjacent context was checked where the commit boundary or rationale was muddy
- the body says what changed, what behavior it affected, and why
- the message is good enough that a later audit can usually trust `git log`
  before opening the diff

That last point matters. The target is not "better than before". The target is
"history becomes a semantic index".

## Phase 4: Normalize and Canonicalize

After each wave:

- normalize worker outputs into one canonical corpus
- preserve all useful metadata, even if some worker schemas drift
- emit:
  - canonical JSON
  - CSV
  - summary JSON
  - rewrite map JSON

This is where ad hoc worker outputs stop being authoritative. The canonical
corpus becomes the source of truth.

### Batch Finalization Is A First-Class Step

Do not leave duplicate batch outputs, partial recovery batches, or scratch
normalizers as operator folklore.

The toolkit must provide one deterministic finalization step that:

- chooses a canonical winner when multiple files cover the same batch
- verifies that the full target commit set is covered exactly once
- emits the merged canonical corpus
- emits the rewrite map used for the actual history rewrite

This exists because detached worker pools are operationally messy in practice.
The safety boundary is the finalized corpus on disk, not the worker process
graph.

## Phase 5: Atomicity Analysis

Atomicity analysis asks different questions than message rewriting.

For every covered commit band:

- what should likely be split?
- what should likely be merged?
- what should likely be reordered?
- what is merely noisy generated fallout?

Important rule:

- `.sqlx` cache refreshes should usually be isolated into their own commits
- they should not drown the semantic change surface
- atomicity reports must separate semantic churn from generated churn explicitly

Use heuristics only as triage, never as final judgment.

Heuristics are good for:

- narrowing which bands deserve attention first
- spotting giant mixed commits
- spotting revert/reapply or remove/restore sequences

Heuristics are not good for:

- deciding final split boundaries
- deciding final target commit messages
- deciding final merged children

Those require real patch reading.

## Phase 6: Structural Planning

Structural planning converts prose into execution packs.

There are four kinds of structural specs:

- `split`
- `merge`
- `reorder`
- `redetail`

Every spec needs:

- stable ID
- source namespace
- explicit source selections or source atoms
- resolved source SHAs
- target commit messages with full bodies
- date policy
- executability state

Structural planning must also preserve repo-local semantic rules. Do not let a
cleanup plan silently rewrite toward a superficially "lighter" pattern that the
project does not actually want.

For example, in `sinex`, a test that does not need `TestContext` should stay as
`#[sinex_test]` without the parameter, not be migrated to raw `#[test]` under a
false "avoid TestContext overhead" rationale.

### Local Structural Equivalence Gate

Before admitting any nontrivial structural op into the full replay, validate it
locally at band scope.

For one op:

- create a disposable worktree at the op's `anchor_sha`
- apply only that op against the exact source band tail
- compare the resulting `HEAD^{tree}` to the original `anchor_sha^{tree}`

This is the real admission gate for a split/merge/reorder op. If the local
band-end trees do not match exactly, the op is invalid.

Important consequence:

- do **not** push forward into a full replay and start hand-clearing later
  conflicts
- fix the op itself until the local band-end tree is exact

In practice, this means:

- use `compare-repo-trees` or direct tree-object comparison against the
  historical refs, not the checked-out worktree file set
- treat a clean contiguous repartition as a control case when debugging a bad
  merge spec
- remember that exact equivalence is a **constraint**, not the design goal
- after a control case proves equivalence, continue refining the child
  boundaries until the replacement commits are semantically good as well

## Phase 7: Disposable Replay Validation

Structural planning is **not** enough.

Before any landing claim:

- run the compiled plan in a disposable clone
- preserve the failed or successful result branch outside the repo
- verify final tracked-tree equivalence, not just “rebase completed”

Minimum validation proof:

- the runner checked the exact planned source SHA band before every
  `apply-structural-op` exec
- a tracked-tree scorecard was emitted between source repo `HEAD` and rewritten
  repo `HEAD`
- if the scorecard is not exact-equivalent, the plan is invalidated for landing
  and the launch pack must say so explicitly

Completion of the disposable replay is only a transport-level success. The
actual success criterion is semantic equivalence of the resulting tip tree.

### Do Not Spend Hours Clearing Global Conflicts Blindly

If the full replay starts producing repeated conflicts, do not treat that as
normal forward progress.

First ask:

- is a locally validated op actually exact?
- did a broad semantic reconstruction slip into the executable pack?
- is the failing band truly equivalent at its band end?

The correct order is:

1. local op validation
2. exact repair of bad ops
3. full disposable replay

not:

1. optimistic full replay
2. marathon conflict clearing
3. late discovery that the plan was invalid

## Phase 8: Landing

Only after disposable validation proves equivalence:

- take a fresh backup of the real repo
- run the structural rewrite against the real repo
- verify identities, dates, and final tracked-tree state again
- archive prep-era files so the launch pack only shows current truth

But the only authority for historical intent is the source commit stream
itself. Current house style helps interpret commits; it does not override them.

### Split Specs

A split spec is not ready until each child commit has a concrete assignment:

- source group keys
- explicit include paths
- include path globs
- or another mechanically applicable source rule

If the split still depends on hunk-level sorting inside shared files, it is not
machine-executable yet.

In ideal form, each split child also has:

- a short semantic title
- a full body explaining the child boundary
- a source-partition rationale
- an explicit note on what is intentionally excluded into sibling children

### Merge Specs

A merge spec is not ready until each target child has:

- ordered source selections or atoms
- a final message
- clear semantics about whether it is:
  - pass-through
  - squash ordered atoms
  - merge after a prerequisite split

### Reorder Specs

A reorder spec is not ready until:

- the final permutation is explicit
- the fate of every original commit is explicit
- if collapse occurs, the resulting message exists

Typical reorder failure mode:

- the proposal names a new causal order
- but does not say whether the old revert / reapply commit survives, folds in, or disappears

That is still manual residue, not an executable reorder.

## Determinization Ladder

When a structural candidate is not executable yet, handle it in this order:

1. simplify the plan
2. reuse a broader already-executable band if it subsumes the narrower one
3. collapse over-split children into one coherent child
4. only then leave it as manual residue

This matters because many "manual" blockers are fake difficulty introduced by
over-clever planning.

Typical examples:

- a split range that is cleaner as one remainder child after one obvious child
  has already been extracted
- a merge cluster that should just become one merged stabilization commit
- a narrow split that is already better covered by an overlapping broader
  executable runtime band

## Phase 7: Determinize the Residue

This is the phase most likely to be faked if not watched carefully.

The rule is:

- every remaining `needs_manual_review` item gets a bounded owner
- owners must read full patches and adjacent context
- owners must either:
  - convert it to executable form
  - or keep it manual with a precise blocker reason

Do not stop at "manual review exists".

Residue must be one of:

- resolved into executable spec
- intentionally demoted to optional opportunity pack
- or explicitly tracked as a live blocker

Nothing else is acceptable.

## Phase 8: Separate Optional Opportunity Packs from Core Blockers

This distinction matters.

Some surgery opportunities are valuable but not required for a trustworthy
structural rewrite launch.

Examples:

- second-tier merge opportunities
- aesthetic reorder cleanups
- moderate split improvements where the current history is already coherent enough

If a pack is optional:

- label it optional explicitly
- remove it from blocker accounting
- keep it machine-readable, but not in the critical path

Do not silently mix optional opportunities with actual blockers.

## Phase 9: Build the Launch Pack

The launch pack is the only place allowed to make readiness claims.

It should contain:

- manifest
- execution status note
- canonical readiness JSON/MD
- structural execution schema
- translated plan manifest
- message rewrite maps
- current-to-rewritten SHA map
- deterministic structural execution packs
- blocker ledger
- optional opportunity ledger
- rollback references

If any older file contradicts the launch pack, archive or demote it.

### Launch-Pack Contract

The launch pack must answer, without cross-reading random notes:

- what is already applied
- what is only prepared
- what remains blocked
- which files are canonical
- which older artifacts are archived or superseded

If a future operator has to grep the tree to understand readiness, the launch
pack is not good enough yet.

## Phase 10: Execute in Two Passes

Recommended order:

1. pure message rewrite pass
2. structural pass

Do not execute both in one opaque jump.

Why:

- message rewrite has different correctness criteria
- it is easier to validate date and identity preservation independently
- structural surgery remains easier to reason about once the history already has audit-grade messages

## Phase 11: Validate After Each Destructive Step

Minimum validation after a rewrite pass:

- commit count alignment
- author identity preservation
- committer identity preservation
- author date preservation
- committer date preservation
- changed vs unchanged message counts
- branch state and cleanliness

After structural execution, also validate:

- every source atom landed exactly once
- no accidental commit loss
- no duplicated source ranges
- resulting order matches the deterministic plan

## Agent Strategy

### Worker Roles

Use workers for bounded outputs, not vague exploration.

Good worker scopes:

- one wave half
- one residue family
- one group of related split ranges
- one cluster of merge/reorder bands

Bad worker scopes:

- "make wave 4 ready"
- "fix all remaining residue"

### Main-Agent Responsibilities

Workers do bounded reading and proposal writing.
The main agent owns:

- carving waves
- assigning ranges
- enforcing schema and process contract
- integrating worker outputs
- resolving schema drift
- deciding whether a candidate is truly blocked or just over-split
- maintaining the blocker ledger
- updating the canonical launch-pack state

Do not outsource canonical state management to workers.

### Worker Contract

Every worker prompt should say:

- exact owned output files
- exact candidate IDs or bands
- full-patch reading is mandatory
- adjacent context reading is mandatory when needed
- `.sqlx` is noise unless semantic
- no actual history rewrite
- explicit schema target
- only keep manual review when real ambiguity remains

### Idealized Worker Prompt Shape

Every worker prompt should include:

- exact input file
- exact output file
- exact candidate IDs or commit range
- explicit ban on performing rewrite operations
- instruction to read full patches, not just `--stat`
- instruction to ignore `.sqlx` / other generated churn unless it is the point
- instruction to use adjacent commits for context
- instruction to emit full commit bodies
- instruction to checkpoint if the range is long
- instruction to return schema-valid JSON only

For `codex exec` packet runs, prefer a generated prompt file plus a one-line
request:

- generate `prompt.md` per packet
- invoke `codex exec` with a single-line request that `@`-mentions that prompt
  file
- pass a packet-specific JSON Schema via `--output-schema`
- keep one durable status file per packet so the operator can see pending /
  running / failed / completed state without opening raw agent output

The point is to make packet execution inspectable and replayable rather than
burying the real contract inside a shell history line.

And for structural work specifically:

- "if the current plan seems over-split, propose a simpler executable child
  rather than preserving needless ambiguity"

### Checkpointing

Ideal form:

- workers checkpoint partial JSON early
- then refine

In practice, if subagents run in isolated workspaces, plan around the fact that
partial files may only become visible on completion.

So:

- keep worker scopes small enough to finish
- prefer more workers with narrower assignments over fewer oversized workers

### Idealized Parallel Topology

For a mature run, use three concurrent lanes:

- `lane A`: strict message-rewrite workers
- `lane B`: structural determinization workers
- `lane C`: main-agent integration / validation / canonicalization

This prevents the common failure mode where worker output accumulates faster
than it is normalized.

## Artifact Taxonomy

The process stays manageable only if artifacts are stratified.

Recommended layout:

- `canonical/`
  - final corpora
  - readiness
  - launch pack
- `agent-work/`
  - worker outputs awaiting integration
- `archive/`
  - superseded intermediate snapshots

Reusable tooling and methodology should stay outside the target repo, in the
canonical toolkit home:

- `/realm/project/sinnix/dots/_ai/skills/history-cleanup/`

Within `canonical/launch-pack/`, separate:

- `core executable packs`
- `optional packs`
- `status / readiness`
- `translation / mapping artifacts`

## Date Policy

Default policy:

- preserve author dates
- preserve committer dates
- do not restamp history as "today"

For reordered commits:

- preserve original dates whenever possible
- if strict monotonicity is needed, use minimal deterministic committer offsets
- record that choice explicitly in the plan

For split children:

- use the original source commit date by default
- if multiple children require ordering hints, use minimal deterministic offsets and document them

For merges:

- prefer the oldest source commit date when one merged child represents the full
  causal band
- if a merged band becomes multiple children, keep the source-band dates and use
  minimal deterministic offsets only when needed to preserve their final order

## Attribution Policy

Keep authorship analysis separate from git author fields.

Track:

- git author / committer identities
- co-author trailer presence
- session-log evidence
- day-window agent dominance if needed
- confidence score

Use that metadata to improve auditability, but do not let uncertain attribution
block structural prep.

## Dirty Tree Policy

Never start destructive history work on a dirty tree unless the dirt is
explicitly excluded.

Preferred sequence:

1. inspect dirty tree
2. cluster it into coherent commits
3. commit it with the same message-quality standard as the rewritten history
4. verify clean tree
5. back up repo
6. start rewrite work

## Canonical Ready State

A repo is truly turn-key for history surgery only when:

- current `HEAD` coverage is current, not stale
- message rewrite pass is applied or ready as one explicit map
- structural plans are determinized for the in-scope core pack
- blocker ledger is empty
- optional pack is explicitly separated
- launch pack agrees with reality

If any of those are false, the repo is not turn-key yet.

## Recommended Idealized Workflow

1. Clean dirty tree and commit it.
2. Back up repo locally and externally.
3. Build history waves with surface metadata.
4. Run strict reword waves with full-patch review.
5. Normalize wave outputs into canonical corpora.
6. Build rewrite maps and attribution metadata.
7. Run atomicity analysis over the canonical corpora.
8. Convert atomicity findings into detailed structural plans.
9. Determinize all manual residue with bounded workers.
10. Separate core blockers from optional opportunities.
11. Build one canonical launch pack.
12. Execute pure reword pass.
13. Translate structural plans onto new SHAs if needed.
14. Validate preservation of identities and dates.
15. Execute structural rewrite only when blocker ledger is empty.

## Tool-Assisted Workflow

The helper CLI exists to reduce mechanical toil, not to replace judgment.

Recommended usage pattern:

1. `derive-history-surface`
   dump raw history transport artifacts and compute packet-budget stats
2. `prepare-global-style-pass`
   build a repo-wide style-derivation corpus plus prompt/schema/run script for
   a wide-context worker; use this when you want one durable repo-local style
   guide before packet fan-out
3. `build-message-packets`
   generate token-budgeted packet manifests with full owned diffs and
   message-only edge context
4. `prepare-packet-exec`
   materialize `prompt.md`, one-line request, schema, status, and proposal paths
5. `packet-exec-status`
   inspect wave state before and during execution
6. `run-packet-exec`
   run `codex exec` against pending packets and capture schema-valid proposal
   JSON
7. `normalize-wave`
   convert heterogeneous worker outputs into one canonical corpus when a wave is
   still range-based rather than packet-based
8. `build-rewrite-map`
   produce pure message rewrite maps once a wave is canonically reworded
9. `analyze-series`
   use only as triage for suspicious bands
10. `scaffold-split`
    create initial structural grouping for giant commits
11. `emit-rebase-todo`
    only after deterministic structural execution packs already exist

Important boundary:

- `analyze-series` is only a prefilter
- `scaffold-split` is support, not a decision-maker
- `emit-rebase-todo` is a compiler for a human-approved plan

## Tooling Fit

The supporting CLI helps with:

- history-surface derivation
- repo-wide style-pass preparation
- packetized message-exec preparation
- packet execution status
- packet execution running
- wave carving
- wave status
- normalization
- rewrite-map generation
- review-bundle generation
- split scaffolding
- rebase todo emission

It does not replace:

- full patch reading
- structural judgment
- blocker accounting
- launch-pack honesty

That judgment layer is the methodology, not the script.

## Wide-Window Variant

If you have a worker with a true large context window, do not simply increase
packet size until the window is full.

Use the extra budget in this order:

1. derive one repo-wide style guide from the whole commit-surface corpus
2. enlarge owned diff packets to cover coherent feature arcs
3. enlarge edge-context commit-message bands
4. keep a hard commit-count cap so one packet still maps to one understandable
   local narrative

The CLI now exposes this explicitly through `--window-profile`.

Recommended defaults:

- `spark-128k`
  - narrow packets
  - shallow edge context
  - no commit-count cap unless explicitly set
- `wide-1m-750k`
  - large arc-level packets
  - deeper edge context
  - hard normal-packet cap of `24` commits

The point of the wide profile is not "single-call whole-history rewriting".
It is:

- fewer packets
- less jumbo/reducer machinery
- better naming consistency across a whole feature arc
- ability to inject one repo-wide style guide into every packet prompt

## Reusable Output Set

For another project, the minimum durable artifact set should be:

- methodology doc
- canonical wave corpora
- before/after rewrite ledger
- process metadata with strictness and attribution
- atomicity coverage audit
- detailed structural plans
- deterministic executable packs
- launch-pack manifest
- status note
- rollback references

If those outputs do not exist, the work may be happening, but it is not yet
operationally reusable.

## Reuse Checklist for Another Project

Before reusing this process elsewhere, adapt:

- generated-noise filters for that repo
  - example: `.sqlx`, lockfiles, vendored snapshots, codegen
- canonical top-level area mapping
- date policy if the repo has unusual merge history
- session-log sources if authorship or intent matter
- launch-pack blocker definitions

But keep the overall shape the same:

- corpus
- waves
- strict rewrite
- atomicity
- determinization
- launch pack
- execution

## Anti-Patterns

Do not repeat these:

- claiming "turn-key" before residue is determinized
- mixing message rewrite readiness with structural readiness
- leaving blocker counts only in prose
- allowing optional opportunities to masquerade as blockers
- trusting heuristic bands as executable specs
- letting `.sqlx` or similar generated churn dominate the analysis
- rewriting history before the dirty tree is resolved
- failing to preserve dates and identities

## Current Relationship to `sinex`

This methodology was distilled from the `sinex` cleanup run, but it is intended
to outlive it.

The local `sinex` launch pack is a concrete instance.
This document is the reusable playbook.
