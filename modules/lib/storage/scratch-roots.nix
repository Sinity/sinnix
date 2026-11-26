# Regenerable roots covered by named Borg exclusions.
[
  "tmp"
  "worktree"
  "worktrees" # Historical spelling: migrate only when it exists.
  "state/cache"
  # Installed game files only. Proton saves can live in the sibling
  # compatdata directory, which must stay in Realm snapshots.
  "library/game/steam/steamapps/common"
  # Downloaded weights are already excluded from Borg.
  "library/model/gguf"
  # Keep the authored judgments and references beside the generated index.
  "state/fs-index/generations"
  "state/codex/home/packages"
  # Exact regenerable build/cache roots already excluded by backup.nix.
  "project/polylogue/repo/target"
  "project/polylogue-sinex-common/repo/target"
  "project/sinex/repo/target"
  "state/stashbox/analysis-cache"
  "state/stashbox/generated"
]
