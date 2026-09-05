# Integration packet

This worktree is the integration branch of batch `{run_id}` on base `{base}`.
`git merge --no-ff` of `{branch}` stopped on conflicts in:

{conflicts}

Resolve them against the beads' intent, commit the merge, then merge every
remaining worker branch in this order with `git merge --no-ff --no-edit`:

{remaining}

Leave a clean tree with every listed branch merged. Do not rebase, push, or
touch Beads. Resolve honestly; a conflict you cannot resolve is reported, not
forced.

## Worker results

```json
{results}
```
