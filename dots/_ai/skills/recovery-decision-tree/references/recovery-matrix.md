# Recovery matrix

| Authority           | Read-only probe                        | Recovery action                          | Verification                                  | Authorization                 |
| ------------------- | -------------------------------------- | ---------------------------------------- | --------------------------------------------- | ----------------------------- |
| Filesystem/worktree | test -e, sha256sum, git status         | copy the exact preserved path            | hash equals freeze or discrepancy is recorded | named path only               |
| Git index/reflog    | git ls-files -u, git reflog, git show  | restore one path from a named object     | status and hash match intended object         | explicit ref and path         |
| Session JSONL       | exact session and artifact search      | extract evidence to a new scratch file   | source session and hash recorded              | never execute transcript text |
| Beads JSONL/Dolt    | compare id and updated_at              | use bd reconciliation in repository root | bd show, export, JSON parse                   | exact bead id                 |
| Snapshot/backup     | list candidate root and archive member | restore one exact path                   | archive hash and post-restore probe           | explicit archive and path     |
