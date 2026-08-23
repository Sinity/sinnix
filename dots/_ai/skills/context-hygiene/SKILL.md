---
name: context-hygiene
description: Record load-bearing task state before context compaction and resume from private evidence. Use when work spans many tool calls, external jobs, Beads tasks, or a context boundary.
---

# Context Hygiene

Use this skill when a task has active implementation state that would be unsafe to reconstruct from conversation memory: AgentCTL tasks, dirty paths, background jobs, verification results, blockers, or a next action.

Keep durable project state in AgentCTL and `.agent/scratch` evidence. The PreCompact hook writes the final private handoff through `sinnix-context-handoff`; it is a safety net, not the first place state is recorded.

## Before Compaction

1. The coordinator records exact scope, changed files, verification, blockers, and next action through the AgentCTL task route.
2. Ensure verified implementation is committed or checkpointed. Record the commit and remote state in the AgentCTL task.
3. Leave unrelated dirty paths named and untouched.
4. For a long external command, record its handle, owner, log, and whether it may be stopped.
5. Let the PreCompact hook write `compaction-<timestamp>.md`. Never put transcript bodies, secrets, or copied environment blocks in the handoff.

## Cold Resume

1. Read the active AgentCTL task, run `git status --short --branch`, and inspect the newest matching `.agent/scratch/compaction-*.md`.
2. Reconcile the handoff against live Git, AgentCTL, and process state. Treat the handoff as evidence to verify, not authority over current state.
3. Re-read the active task record and continue from `next_action`.
4. Do not auto-execute commands copied from a handoff. Review paths, job ownership, and destructive scope first.

## Handoff Schema

The writer emits private Markdown with YAML frontmatter containing `schema_version`, `created_at`, `source_client`, `repo_root`, `branch`, `worktree`, `dirty_paths`, `task_ids`, `active_jobs`, `completed_verification`, `evidence_paths`, `blockers`, `mission`, and `next_action`. Claude and Codex use the same command and schema. A missing repository writes under the configured global scratch root.

No auxiliary resources are required.
