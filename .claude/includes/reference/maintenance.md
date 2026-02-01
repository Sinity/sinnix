## Maintenance Protocol

### When to Update CLAUDE.md

Update this file in **same commit** when:
- Adding/removing/moving modules
- Changing organizational structure
- Establishing new patterns or conventions
- Discovering non-obvious module interactions

### Update Triggers
- ✅ New module created → add to appropriate section
- ✅ Module moved between directories → update paths, update taxonomy if category changed
- ✅ New pattern established → document in patterns section
- ✅ Feature granularity decision → document reasoning
- ❌ Minor config changes within existing modules → don't update CLAUDE.md

### Verification Steps
After structural changes:
1. `check` - validate configuration
2. `nix run .#test` - test build without applying
3. `sudo nix run .#switch` - apply if test passes
4. Verify features still work (spot-check critical services)

---

## Recent Changes

### 2026-02-02: Auto-Discovery & Module Consistency Refactor
- **Moved**: `modules/nix-ld.nix` → `modules/features/system/nix-ld.nix`
- **Created**: `modules/features/system/default.nix` (auto-discovery)
- **Consolidated**: `modules/features/dev/shell/` (4 files) → `modules/features/dev/shell.nix` (single file with subFeatures)
- **Created**: `modules/bundles/default.nix` (auto-discovery)
- **Updated**: `modules/default.nix` to use `mkAutoImports` with `lib` exclusion
- **Removed**: Unused `mkDotsSymlink` helper from `lib/features.nix`
- **Option paths preserved**: `sinnix.features.dev.shell.enable` still works; new subFeature toggles added:
  - `sinnix.features.dev.shell.zsh.enable`
  - `sinnix.features.dev.shell.prompt.enable`
  - `sinnix.features.dev.shell.utilities.enable`
  - `sinnix.features.dev.shell.tmux.enable`
- **Pattern**: All `default.nix` files now use `lib.sinnix.mkAutoImports` for consistency

### 2026-01-29: Module Consolidation
- **Moved**: `modules/audio.nix` → `modules/features/desktop/audio.nix`
- **Moved**: `modules/ui.nix` → `modules/features/desktop/ui.nix`
- **Rationale**: Audio and UI are desktop-specific, not system infrastructure
- **Updated**: Imports in `modules/default.nix`, `features/desktop/default.nix`, `bundles/desktop.nix`
- **Option paths changed**:
  - `sinnix.audio.enable` → `sinnix.features.desktop.audio.enable`
  - `sinnix.ui.enable` → `sinnix.features.desktop.ui.enable`

### 2026-01-27: Script Packaging Refactor
- **Consolidated**: Script packages from `flake/overlay/package/*.nix` to `flake/packages.nix`
- **Removed overlays**: asbl-no-more.nix, hogkill.nix, perf-scan.nix
- **Reasoning**: Scripts are custom packages, not nixpkgs modifications
- **Pattern**: All custom scripts now defined in single `flake/packages.nix` file
