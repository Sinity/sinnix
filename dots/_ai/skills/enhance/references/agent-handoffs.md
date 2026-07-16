# External-agent handoffs and prompt portfolios

Use this reference only for an executor that does not share the current runtime
or when preparing several queued prompts.

## Start from executor reality

Record what the target agent can and cannot do. Browser-hosted models commonly
can read attachments and produce files but cannot run the repository, inspect
live services, or verify tests. Ask them for complete code and concrete tests,
but require `unverified` rather than fictional green results. A local coding
agent should normally receive a worktree, exact branch, owned/avoided files,
verification responsibility, and commit expectations instead of a source ZIP.

Continuation in the same chat is useful for repairing a specific missing file,
contradiction, or packaging failure because the executor retains its analysis.
Use a fresh chat for independent work or when accumulated context is causing
shallow answers.

## Context-pack design

Every pack should have a manifest stating:

- repository/project and snapshot commit;
- creation time and dirty-patch status;
- included and deliberately omitted paths;
- selected tracker/design records;
- privacy/account boundary;
- checksum when the pack will move between systems.

Prefer the smallest pack that preserves the mission's dependency graph:

- targeted source, tests, schemas, and design records for a bounded change;
- a tracked-file repository snapshot for architecture-wide work;
- a git bundle only when history is part of the question;
- live data only when necessary, minimized, and explicitly authorized.

Do not attach several redundant representations of the same repository. Large
XML concats, full chat archives, or unrelated historical packs often encourage
shallow summarization. Put the actual mission in the prompt, not at the end of
an attachment.

For code that is changing concurrently, package a named commit plus a separate
working-tree patch, or package a clean integration branch. Never call an
unidentified tarball “current.”

## Prompt contract for a browser-only implementation agent

The prompt should contain:

- a readable mission title and description before issue ids;
- the attachment filename, snapshot commit, and authority order;
- the exact vertical slice and explicit non-goals;
- architecture and safety constraints verified from source;
- acceptance criteria tied to observable production routes;
- an instruction to include concrete tests but not claim execution;
- a requirement for substantive direct output in addition to generated files.

When an integration package is worthwhile, request one cohesive archive:

```text
HANDOFF.md       mechanism, decisions, changed files, AC matrix, commands, risk
PATCH.diff       apply-ready unified diff against the named snapshot
FILES/           complete files only when needed to disambiguate the patch
EVIDENCE.md      source/research evidence when the mission depends on it
```

Reject placeholders, ellipses, pseudocode presented as code, invented APIs,
and a directory of unrelated partial patches. If the full scope is unsafe,
request one end-to-end smaller slice plus a decision-complete continuation
plan.

## Portfolio construction

Before producing several prompts:

1. Inventory active, queued, completed, and integration-pending work.
2. Cluster candidate missions by code/data/resource footprint.
3. Remove duplicates and identify dependency order.
4. Prefer independent, high-leverage vertical slices.
5. Mark analysis-only adjudication when competing packages or designs must be
   reconciled before implementation.
6. Give each job a readable title, priority, expected integration lane, and
   reason it fits the target executor.

Produce a compact dispatch manifest with prompt filename, scope, dependencies,
snapshot, intended executor, expected artifact, and integration owner/status.
Prompt count is not throughput; useful integrated output is throughput.

## Repair prompts

When a first run is incomplete, quote the specific deficiency and preserve the
valid work:

- missing or corrupt output package;
- patch not based on the supplied snapshot;
- placeholders or omitted files;
- no substantive explanation;
- architecture conflict discovered by the integrator;
- tests that do not exercise the production dependency.

Ask the same chat to audit its prior answer against the original acceptance
criteria, repair only the deficient parts, regenerate the cohesive package, and
summarize what changed. Do not restart with a vague “try again.”

## Final quality check

- Is the real job visible in the first paragraph?
- Can a human understand the prompt without knowing the tracker id?
- Is the context fresh, identified, and no broader than useful?
- Are executor limitations explicit and verification claims honest?
- Does the requested output include both substantive explanation and an
  integration artifact when appropriate?
- Are portfolio items non-overlapping or intentionally clustered?
- Is there a clear next owner for verification and integration?
