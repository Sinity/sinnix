## Session History & Continuity

### When to Look Up History

**Proactive triggers** (do without being asked):

- User references past work: "remember when...", "like before", "that thing we did"
- After context compaction loses relevant earlier work
- Task feels familiar but details are missing
- Error patterns that might have been solved before

**How to access**:

```bash
# Current project sessions
ls -lt ~/.claude/projects/<project>/*.jsonl | head -10

# Search across sessions
grep -r "pattern" ~/.claude/projects/*/

# Read specific session
cat ~/.claude/projects/<project>/<session-id>.jsonl | jq -r 'select(.type=="user") | .content' | head -100
```

### Persistent Learning

When accessing history, write down learnings to prevent re-discovery:

1. **Session summaries**: `.agent/history-summaries/<id>.md`
2. **Cross-session patterns**: `.agent/learnings.local.md`
3. **Recurring solutions**: Add to relevant CLAUDE.md (use the `meta` skill, `remember` flow)
