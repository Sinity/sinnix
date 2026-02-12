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

### 2026-02-12: Audit Cleanup

- **Deleted**: `archive/` directory (~80K of abandoned modules and obsolete scripts; git history preserves all)
- **Enabled**: Hyprland debug logs (`disable_logs = false`) for crash/issue diagnostics
- **Removed**: Dead Python overlay entries (`aggdraw`, `dependency-injector`) — unused in sinnix, polylogue pins its own nixpkgs
- **Committed**: Untracked `scripts/kitty-scrollback-capture` and `scripts/kitty-scrollback-view` (phantom dependency from hyprland config)

### 2026-02-06: Polylogue Service Integration

- **Added**: `modules/services/polylogue.nix` - scheduled ingestion for AI chat archives
- **Enabled**: `sinnix.services.polylogue.enable` in sinnix-prime host
- **Updated**: `services.md` to document polylogue and fix stale entries (removed non-existent netdata.nix, added below.nix)
- **Implementation**: User-level systemd timer (15min interval) using Home Manager, respects XDG paths

### 2026-02-02: Comprehensive Refactoring & Dead Code Removal

- **Removed**: `mkDotsLink` from `lib/features.nix` (unused, `mkDotsFile` is preferred)
- **Removed**: 4 unused overlay helpers from `lib/overlay-helpers.nix` (`mkInputOverlayWith`, `mkNativeBuildInputsOverlay`, `mkOverrideAttrs`, `mkComposedOverlay`)
- **Added**: `mkDotsFileFor` helper for cleaner HM dotfile linking
- **Updated**: `home-manager.nix` extraSpecialArgs to pass pre-bound `mkDotsFileFor`
- **Refactored**: 5 modules to use `mkDotsFileFor config` pattern (editors, mcp-servers, common-apps, browser, theming)
- **Extracted**: Inline scripts from `storage.nix` to `scripts/` registry:
  - `encrypt-folder`, `decrypt-folder`, `mount-nextcloud`, `umount-nextcloud`
- **Extracted**: `lsp-root.nix` to `scripts/lsp-root` with package wrapper
- **Removed**: `modules/lib/lsp-root.nix` (obsolete)
- **Consolidated**: 5 activation blocks in `shell.nix` → 2 (`linkConfigs`, `rebuildBatCache`)
- **Added**: Shell alias `zed = "zeditor"`, removed wrapper script from `editors.nix`
- **Added tests**: `bundle-desktop`, `services-sinex`, `desktop-hyprland`
- **Added**: Header comments to 4 core modules (core.nix, home-manager.nix, performance.nix, storage.nix)
- **Documented**: Hyprland composite module pattern in features.md

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
