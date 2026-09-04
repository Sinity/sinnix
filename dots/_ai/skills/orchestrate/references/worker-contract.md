# Worker contract

Everything in this file is compiled verbatim into every dispatched lane's
prompt. Write only what the worker must decide; what a gate enforces is not
repeated here.

## The dispatch contract

1. **Implement from the launch snapshot.** The packet above carries the bead
   descriptions and acceptance criteria as they stood at dispatch time, the
   worktree and branch, and the files in scope. Where the packet names atlas
   sheets, read them for orientation rather than re-deriving the area.
2. **Verify your own work.** Focused runs are `devtools test <selection>`.
   Run the static gate with `lane verify`; it submits the declared
   `verify_quick` operation to pueue and waits for that task. Do not invoke
   `devtools verify --quick` directly inside a lane. Do not start or wait for
   affected or complete verification. GitHub starts affected verification
   after publication, and the coordinator starts one complete run after the
   merge batch. The harness refuses both tiers inside a lane. Fix, test,
   iterate until green. Do not spawn
   review subagents — hosted PR review and the test oracle are the check.
   `devtools verify` selects from the checkout's one testmon datafile
   (`.cache/testmon/testmondata`) and writes back; a corrupt or foreign
   datafile stops the run with `graph_unusable` — delete the datafile and
   rerun. A selected green proves the selected scope only; say which
   selection ran.
3. **Red first for bug fixes.** Demonstrate the failure, then fix it, then show
   green. Each new test names what mutation would make it red.
4. **Fail-closed needs a derivation, not a reflex.** Before adding a guard
   that refuses input, measure what the real corpus contains: a refusal path
   must name the evidence that legitimate data never hits it. A guard that
   refuses real production records is a defect, not safety. Where behavior
   differs between synthetic fixtures and the live archive, run the relevant
   reader against the live archive read-only and report the counts.
5. **Commit by path, push, publish.** When the work is complete and the
   quick gate is green in the rebased state, run `lane publish` (or
   `agentctl lane publish <worktree>`): it pushes, opens the PR under the
   bead's type-prefixed subject, and arms `gh pr merge --auto --squash`.
   Branch protection and the required check decide when it lands; never
   merge by hand.
6. **Report once, honestly.** Per-bead and per-acceptance-criterion
   disposition, the exact commands and the result line that matters, diffstat,
   residual risk. Refuting a finding needs evidence. The report is the
   deliverable: going idle without one is a contract violation. Report in the
   job result only (`lane done report.md` emits it). Piped exit codes lie
   (`cmd | tail` reports tail's status); use pipestatus or capture to a file
   before claiming a gate passed.
7. **No scope expansion.** Discoveries become filings or report notes, never
   inline extra work.
8. **Exit at current master.** Before reporting, fetch, rebase onto
   `origin/master`, rerun the quick gate in the rebased state, fix what it
   surfaces, and push. A conflict you cannot resolve honestly is reported as
   such, never forced to green. A failure you attribute to master is a claim
   that needs a command: run that gate against a clean `origin/master`
   checkout and quote its exit code, or own the failure. When comparing
   failing sets with master, disable order randomization on both sides
   (`-p no:randomly`) and compare the sets, not the totals.
9. **Machine trailer.** End the report with exact lines `LANE-BRANCH: <branch>`
   / `LANE-COMMIT: <sha>` / `LANE-QUICK: green|red|blocked-env` /
   `LANE-CLASSIFICATION: <one line per finding>`.
10. **Write the PR body.** Summary, Problem with its evidence, Solution,
    Verification with the exact commands and the line that matters, and
    honest residual risk, in `.lane/body.md` in your worktree (uncommitted;
    `.lane/` is never committed). The subject is derived from the bead; the
    body file is what `lane publish` sends.
11. **Do not damage live operator state.** Forbidden: deleting or overwriting
    installed tools, dotfiles, or anything under `$HOME` outside your
    workspace; `switch`/`boot` or any system or Home-Manager rebuild; stopping,
    masking, or reconfiguring live services. Retiring an installed tool means
    deleting it from the source tree and saying so. Allowed without asking:
    read-only live evidence — query the archive, read `/realm/state`,
    `sinnix-observe`, and your own `sinnix-chrome-control agent-window`; leave
    the operator's tabs alone. Writes to live state only when the packet names
    the paths or services; absent that, report what you would have done.
12. **Ship the declaration with the change.** A new insight needs its rigor
    contract and field contracts; a new document its catalog entry; a
    durable-tier change its numbered migration and a derived one its lifecycle
    class; a new module a consumer that reaches it and a test that exercises
    it. The gate that will refuse you is the one to run before reporting.
13. **Purge, do not retain.** Retiring a route deletes the module, its
    compatibility aliases and re-exports, its docs, and its tests in the same
    change. If one symbol still has a real consumer, move it to its true
    owner and delete the rest. Do not add a test asserting deleted code is
    gone.
