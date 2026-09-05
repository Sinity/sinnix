# Review packet

Review the candidate `{candidate}` against base `{base}` in this worktree:
`git diff {base}..{candidate}` is the whole change surface, `git log
{base}..{candidate}` its history. The workers' own results follow. Read the
diff completely, run what you need to refute their claims, and answer with
one JSON object conforming to the judge schema: `verdict` is `pass` only when
the change is correct, complete for its beads' acceptance criteria and safe to
publish; `evidence` cites paths and lines; `unsupported` lists what you could
not establish. Do not modify files, Beads, or the repository.

## Worker results

```json
{results}
```
