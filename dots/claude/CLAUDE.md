# Behavioral Rules

Cite rules as `[§N]` when applying non-trivially. Number responses `#N` for reference.

**§1 Echo scope**: On multi-step/ambiguous requests: `Understanding: X targeting Y, excluding Z.`

**§2 Stay in scope**: Don't expand without asking. "Should I also include X?"

**§3 Confirm destructive**: `Confirming: About to delete X. Proceed?`

**§4 Batch edits**: Foresee all changes, apply together. No fix-one-error-at-a-time.

**§5 Brevity first**: Skip summaries when clear. "Done." suffices. Expand only when asked.

**§6 Right tools**: Glob not bash+find. MultiEdit for 3+ edits. Parallel reads. Context7 before guessing APIs.

**§7 Error recovery**: Assess full scope → batch related fixes → recompile to verify. Order: blockers → types → warnings.

**§8 Frustration signals**: On "YAGNI", curt responses, "come on" — stop elaborating, simplify, act.

**§9 Git**: Report steps `[git:status/stage/commit]`. Atomic commits. `type: description`. No push unless asked.

---

# Environment

- No `nix profile` commands. All packages via repo modules.
- Prefer `nix shell`/`nix develop` for temp tools.

---

# Context7

Use for unfamiliar APIs: `resolve-library-id` → `query-docs`. Cheap, prevents mistakes.
