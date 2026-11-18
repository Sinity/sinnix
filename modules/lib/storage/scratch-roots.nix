# Exact regenerable roots, shared with the Borg exclusion assertion.
[
  "tmp"
  "worktree"
  "worktrees" # Historical spelling: migrate only when it exists.
  "state/cache"
  # Downloaded weights are already excluded from Borg.
  "library/model/gguf"
  # Exact regenerable build/cache roots already excluded by backup.nix.
  "project/polylogue/repo/target"
  "project/polylogue-sinex-common/repo/target"
  "project/sinex/repo/target"
  "state/stashbox/analysis-cache"
  "state/stashbox/generated"
]
