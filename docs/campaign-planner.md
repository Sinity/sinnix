# Campaign planner

`sinnixd-planner` is a read-only, scheduled snapshot of the current Beads
frontier. It compiles the same packet snapshots used by `campaign run`, then
writes `/realm/tmp/work/dispatch-plan.json` with a stable generation, ordered
groups, conflict keys, subsystem orbits, dependency edges, and judgment-gate
flags. It never launches an agent or changes task state.

The campaign reactor owns the periodic user timer. Refill consumes the artifact
through the typed campaign runner, whose admission and workspace checks remain
the sole launch path. The live coordinator is therefore a review desk: it
judges review-ready work and handles exceptions, rather than maintaining a
standing frontier or rediscovering dispatch order after compaction.
