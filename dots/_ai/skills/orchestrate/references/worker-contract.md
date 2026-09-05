# Worker contract

Compiled verbatim into every batch worker's prompt. A worker implements the
beads in its launch snapshot, on the branch and in the worktree the snapshot
names, and exits with one result document.

## What a worker does

1. **Implement from the launch snapshot.** The `beads` entries carry the
   descriptions and acceptance criteria as they stood at dispatch. When
   `bead_bodies` is `digest`, read each full body with `bd show <id> --json`
   and check its sha256 of `<title>\n<description>` against `digest`; a
   mismatch is reported, not implemented. Atlas sheets named in the snapshot
   are orientation, not scope.
2. **Stay in the worktree.** Commit by path on the worker branch; never write
   to another checkout, `$HOME` outside the workspace, or live services.
   `.agentctl/` holds the prompt, schema and result and is never committed.
3. **Verify the candidate.** Run the snapshot's `verification_commands` and
   the project's focused checks in the foreground. Bug fixes show red before
   green. A selected green proves the selected scope only; say which
   selection ran. Piped exit codes lie (`cmd | tail`); capture the status.
4. **Do not publish, do not claim beads.** No push, no PR, no merge, no
   rebase onto a newer base, no rebuild of the host. No `bd update`,
   `claim`, `close` or `comment`: `batch start` claimed the beads and
   `batch land` closes them from the acceptance record.
5. **No scope expansion.** Discoveries go into `unresolved`, never into
   extra work.
6. **Exit with a clean tree and the result document.** The final message is
   the JSON below and nothing else; a worker whose result does not validate
   has failed, whatever its exit status.

## The result

Validated against `dots/claude/agents/schemas/worker.schema.json`:

```json
{
  "candidate_sha": "<40-hex HEAD of the worker branch>",
  "beads": [
    {
      "id": "<bead id>",
      "criteria": [
        {
          "text": "<the acceptance criterion as written>",
          "status": "satisfied | unsatisfied | superseded",
          "evidence": "<command and result line, path:line, or why superseded>"
        }
      ]
    }
  ],
  "unresolved": ["<finding or follow-up not implemented>"],
  "verification": [{ "command": "<exact command>", "receipt": "<result line>" }]
}
```

- `candidate_sha` must equal `git rev-parse HEAD` in the worktree when the
  result is filed.
- Every bead in the snapshot appears in `beads` with every criterion. A bead
  is closed at landing only when all its criteria are `satisfied` or
  `superseded`; anything else leaves it open with the residual as a comment.
- Refuting a criterion or a finding needs evidence, not a claim.
