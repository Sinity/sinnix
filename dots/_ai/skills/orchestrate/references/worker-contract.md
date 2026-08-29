# Worker contract

Everything in this file is compiled verbatim into every dispatched lane's
prompt. Write only what the worker must do; coordinator material belongs in
`coordinator-contract.md`.

## The dispatch contract

1. **Implement from the launch snapshot.** The packet above carries the bead
   descriptions and acceptance criteria as they stood at dispatch time, the
   worktree and branch, and the files in scope. Where the packet names atlas
   sheets, read them for orientation rather than re-deriving the area.
2. **Verify your own work.** Fix, test, iterate until green inside this run.
   You own your defects. Do not spawn review subagents — hosted PR review and
   the test oracle are the structural check.
3. **Red first for bug fixes.** Demonstrate the failure, then fix it, then show
   green. Each new test names what mutation would make it red.
4. **Managed commands only** — the repo's own runner (`devtools test <sel>`),
   never bare pytest. Commit by path, push, never merge.
5. **Report once, honestly.** Per-bead and per-acceptance-criterion
   disposition, the exact commands and the result line that matters, diffstat,
   residual risk. Refuting a finding needs evidence. The report is the
   deliverable: going idle without one is a contract violation. Report in the
   job result only — PR and bead comments duplicate it into a stale copy.
   Piped exit codes lie (`cmd | tail` reports tail's status); use pipestatus or
   capture to a file before claiming a gate passed.
6. **No scope expansion.** Discoveries become filings or report notes, never
   inline extra work.
7. **Exit at current master.** Before reporting, fetch, rebase onto
   `origin/master`, rerun the quick gate in the rebased state, fix what it
   surfaces, and push. A conflict you cannot resolve honestly is reported as
   such, never forced to green. A failure you attribute to master is a claim
   that needs a command: run that gate against a clean `origin/master` checkout
   and quote its exit code, or own the failure. Host load is the other
   explanation and is yours to distinguish, not to assume.
8. **Machine trailer.** End the report with exact lines `LANE-BRANCH: <branch>`
   / `LANE-COMMIT: <sha>` / `LANE-QUICK: green|red|blocked-env` /
   `LANE-CLASSIFICATION: <one line per finding>`.

9. **Write the publication text.** You made the decisions, so you write them
   up: a conventional squash subject of at most 72 characters, a body giving
   Summary, Problem with its evidence, Solution, Verification with the exact
   commands and the line that matters, and honest residual risk. Add a
   close reason only when a bead genuinely closes. Write them to
   `.lane/title`, `.lane/body.md` and `.lane/close-reason.md` in your
   worktree. They are worktree scratch that harvest reads: leave them
   uncommitted, and never force-add a path the repository ignores. You do
   not publish; whoever integrates your lane judges the change and decides. Prose that oversells what you did will be caught
   against the diff.

10. **Do not damage live operator state** — scoped to the harm, not the surface.

Forbidden: deleting or overwriting installed tools, dotfiles, or anything
under `$HOME` outside your workspace; `switch`/`boot` or any system or
Home-Manager rebuild, which would deploy your branch to the live machine;
stopping, masking, or reconfiguring live services. Retiring an installed
tool means deleting it from the source tree and saying so; removing the live
copy is a coordinator act.

Allowed without asking: read-only live evidence — query the archive, read
`/realm/state`, `sinnix-observe`, and drive the browser in your own
`sinnix-chrome-control agent-window`. Leave the operator's tabs alone.

Allowed when the packet says so: writes to live state a bead explicitly
scopes, with the paths or services named. Absent that, report what you would
have done instead of doing it.

11. **Ship the declaration with the change.** Most work rejected at
    integration is not wrong logic — it is a change whose declaration was left
    out, so a gate refuses it. A new insight needs its rigor contract and field
    contracts; a new document needs its catalog entry; a durable-tier change
    needs its numbered migration and a derived one its lifecycle class; a new
    module needs a consumer that reaches it and a test that exercises it. The
    gate that will refuse you is the one to run before reporting.

12. **Purge, do not retain.** The codebase shrinks without losing
    functionality. Retiring a route deletes the module, its compatibility
    aliases and re-exports, its docs, and its tests in the same change. If one
    symbol still has a real consumer, move it to its true owner and delete the
    rest. Do not add a test asserting deleted code is gone — that is a fossil
    of the diff.

## Verification scope

Run selected verification from the seed inherited off the main checkout, never
the corpus and never a bootstrap from scratch; false negatives are caught at
the merge boundary. Finding no compatible seed is a refuse-and-report, not a
reason to run broad.
