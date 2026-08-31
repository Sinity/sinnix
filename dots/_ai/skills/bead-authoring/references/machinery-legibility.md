# Machinery-legible bead standard

A bead meets this standard when the orchestration machinery can dispatch,
gate, and close it without a coordinator reconstructing intent. Derived from
measured failures (2026-08-30/31: stale authority stacks, prose blockers,
fixture-circular tests, label drift).

## Required on every open leaf

1. **Description is the single current contract.** Supersede by editing
   (`bd update -d`), never by stacking dated correction notes. Notes hold
   evidence and receipts only.
2. **Typed execution metadata**: `write_scope` (paths/areas the diff may
   touch — the scope-drift scanner enforces it), `conflict_keys`,
   `worker_model_class`, `verification_commands` (exact, runnable),
   `packet_intent` (one sentence).
3. **Honest edges.** Every blocking condition named in prose exists as a
   `blocks` edge to a real bead. No edge to a closed bead standing in for an
   unfixed condition. Duplicate ownership merged, not cross-referenced.
4. **Labels**: `horizon:*` always; campaign label when campaign-reachable;
   `execution-shape:leaf` on dispatchable items.
5. **Acceptance criteria are falsifiable** and name their anti-vacuity
   condition (what reverted change makes them red).
6. **Reality oracle where the deliverable touches real state**: a read-only
   command against live/clone data whose exit gates authorize (see the
   packet oracle field). Fixture tests alone are insufficient for
   state-touching work — measured twice: fixtures encoded the implementer's
   assumption and passed while reality failed.
7. **Right-sized**: an epic carries no leaf work in its own text; every
   near-term deliverable in an epic's AC has an owning child.

## Wave triage output format

For each bead: `KEEP` (meets standard) | `EDIT` (attach the exact bd
commands: update -d text, label add, dep add/remove, metadata) | `MERGE
into <id>` | `DECOMPOSE` (child specs) | `CLOSE` (evidence it is done or
obsolete — positive evidence of abandonment required, unfinished is not
obsolete). Mechanical edits may be applied by an apply pass; semantic
rewrites route to coordinator judgment.

8. **Ownership is in-repo, or the bead says where it is.** When the fix
   lives in another repository, the bead carries `owner:external-repo:<name>`
   (label) and either narrows to the in-repo surface or holds a blocks-edge
   to the tracked successor in the owning backend. Triage filters these out
   of dispatch; a lane discovering external ownership is a filing defect,
   not lane judgment. (Measured: 3 of 13 in pilot slice A — 2bc2/Beads,
   unsjb/sinnixd, ux8oj/AgentCTL — each previously cost a dispatched lane.)

## Pre-check before dispatching triage

Separate the zero-judgment gap (no METADATA at all) from semantic candidates
first — pilot lanes wasted effort independently rediscovering absent blocks:

    bd export | python3 -c '
    import json,sys
    for l in sys.stdin:
        b=json.loads(l)
        if b.get("status")!="open" or b.get("issue_type")=="epic": continue
        md=b.get("metadata") or {}
        if isinstance(md,str):
            import json as j; md=j.loads(md or "{}")
        missing=[k for k in ("write_scope","conflict_keys","worker_model_class","verification_commands","packet_intent") if not md.get(k)]
        if missing: print(b["id"], ",".join(missing))'

Beads listing all five go to a cheap apply pass (metadata drafted from the
description); partial/semantic defects go to triage lanes.

9. **No ceremony beads.** A bead whose deliverable is an announcement,
   declaration, date, or status about other work (rather than work) is a
   CLOSE candidate: the gates it summarizes are the statement. (Operator
   ruling on me-cxg, 2026-08-31.)
