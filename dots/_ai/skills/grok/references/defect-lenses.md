# Defect-lens catalogue — accumulated techniques and measured yields

Each lens is a distinct attention allocator. exp-001 (2026-08-25, polylogue)
showed two lenses reading the same 594 lines found completely disjoint defect
sets — each walked past the other's top finding. Treat lenses as sampling
distributions over defect space: portfolio and union, never one mega-prompt
by default (union-prompt attention dilution is an open experiment, exp-010).

Update yields here as campaigns measure them. Yield = overseer-verified
filings; tokens from the run record.

| Lens | Attention target | Measured yield | Notes |
|---|---|---|---|
| Signature sweep | taxonomy-family patterns chased to verdict | 2/594-line module; 3 across broad sweeps | crisp on greppable families; verified-per-candidate high |
| Narrate-through | every block's invariants, in order, no skipping | 3/594-line module (1 downgraded at gate) | catches lifecycle/consistency invisible to grep; can overclaim severity |
| Crash-timeline walk | every durable-effect sequence's crash windows | 12 filings + 25 healed-windows negative ledger (Opus) | strongest per-run yield to date; needs recovery-path checking to avoid filing healed windows |
| Differential-twin | near-duplicate code / parallel vocabularies, diffed on real inputs | 2 filings, live-DB measured (Opus) | live-data denominators make these filings unusually strong |
| Caller-contract audit | each public fn: callers' beliefs vs actual contract (flags, formats, destinations, exceptions) | 9 verified (6 P1) on 2,503-LOC CLI surface, probe-backed, first run | strongest per-LOC P1 yield measured; pairs naturally with dynamic probing |
| Error-path-only read | ONLY except/fallback/else branches | untested | unhappy paths get a fraction of normal reading attention |
| State-machine extraction | implicit states; absorbing/unreachable/illegal transitions | untested | would have caught poison-record re-read loops |
| Docstring-vs-code diff | stated claims vs implementation | 1 (found via sweep) | cheap; pairs well with any lens |
| Resource lifecycle | every acquire's release on every path | 1 (found via narration) | systematize: connections, fds, locks, tmp files |
| Clock/TOCTOU | wall vs monotonic; check-vs-use gaps | untested | |
| Unit/dimension | ms/s, bytes/chars, token-count boundaries | untested | 7-fork timestamp divergence suggests fertile |
| Mutation-guided | surviving mutants as defect/dead-code prior | infra exists (mutmut) | free prior; run where coverage thin |

Target-selection priors (before dispatching any lens): LOC × thin test
coverage (testmon graph: files→covering-tests) × recent churn × load-bearing
role. Re-running the same lens on the same module is a legitimate arm
(sampling variance — exp-010c), not a mistake.

Verification ladder for filings: worker self-verification → cheap
refute-to-verify pass (a worker attempts to disprove each filing; exp-011)
→ overseer gate on survivors → red-first test in the fix lane → merged.
Two filings out of ~25 died at the overseer gate on day one — the gate is
load-bearing; never skip it.
