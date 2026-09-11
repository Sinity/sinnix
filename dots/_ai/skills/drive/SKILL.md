---
name: drive
description: Drive autonomous iterative work when the user says keep going, iterate, or take it further: choose the best next move, stress-test it, execute, externalize results, and continue.
---

# Drive

Turn an open goal into useful completed passes. The user can steer with
`pause`/`stop`, `auto`, `gate`, or `redirect: <direction>` at any time.

```
/drive <goal>              continue authorized useful work
/drive --auto[=N] <goal>   continue; stop at N when an explicit cap is given
/drive --once <goal>       execute one pass
/drive --grill <goal>      grill the goal, then continue
/drive --plan-only <goal>  show the first execution prompt and stop
```

For each pass, read existing durable state, choose the highest-value next move,
and forge a compact execution prompt with the goal, acceptance evidence, and a
failure condition. Check facts in the repository or tracker before asking the
user. Then execute the move, using the narrowest relevant verification and the
declared job for shared or heavy work.

Record the chosen direction, result, artifacts, assumptions, and next frontier
where the normal work already lives. Beads, committed files, and reports are
durable evidence; do not create a second tracker or a separate dispatch
ledger. A scratch note is optional when it materially improves resumption of a
long or interrupted drive. Historical options can remain in the conversation
unless they change a later decision.

Ask only a material user-owned question in the requested interactive mode. In
auto mode, make the recommended assumption explicit and continue. Gate before
destructive, irreversible, or outward-facing work only when it lacks existing
authorization or requires a new material choice; honor authorization already
given. Stop when a new fact overturns the plan. Do not broaden authority merely
because auto mode is enabled.

## Resume ledger

When a scratch ledger is useful, use `.agent/scratch/drive-<topic>.md` (or the
project's established scratch location):

```markdown
---
goal: <the user's goal>
mode: gated | auto(N)
status: active | stopped(<reason>)
---

## FRONTIER
<next move>

## PASSES
<direction, outcome, artifacts, verification>

## ASSUMPTIONS
<decisions taken in auto mode>

## RULES
<constraints added during the drive>
```

Update it after a meaningful pass, not as a ceremony. On compaction, read it
before acting when one exists. Stop after an explicit cap, when no durable progress remains,
when a user decision gates all useful moves, or at a risk boundary. Report the
outcome, durable paths/ids, verification actually run, residuals, and the
proposed next move.
