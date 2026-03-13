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

### 2026-03-12: Launch-Trigger Early Capture and Lanzaboote Prep

- **Improved**: `scripts/launch-trigger-capture` now starts and pre-creates live monitor outputs before taking the initial snapshot, and records the last completed stage in `status.env` / `run.log` so sub-second Hyprland-triggered resets leave a clearer boundary
- **Added**: `lanzaboote` flake input and enabled Lanzaboote on `sinnix-prime`
- **Configured**: auto-generated Secure Boot keys persisted under `/var/lib/sbctl`
- **Added**: `sbctl` to the host system packages for verification and maintenance
- **Purpose**: make the next graphics-session reset more observable and reduce future BIOS/Secure-Boot lock-in friction

### 2026-03-12: Stability Lab for Reboot Forensics

- **Added**: `scripts/stability-lab` - persistent CPU/RAM/mixed stress runner with reboot-survivable evidence capture
- **Added**: `modules/features/cli/stability-lab.nix` - CLI feature that installs the runner and exports the canonical capture root
- **Enabled**: `sinnix.features.cli.stability-lab.enable` on `hosts/sinnix-prime`
- **Added tests**: `cli-stability-lab` to verify package install, session variable, and tmpfiles directory wiring
- **Purpose**: Prepare repeatable stability tests under `/realm/data/captures/stability-lab` for abrupt-reset diagnosis

### 2026-03-13: Reboot-No-More GPU Lab Wiring

- **Added**: `reboot-no-more` flake input sourced from `/realm/project/reboot-no-more`
- **Updated**: `modules/features/cli/stability-lab.nix` to install the packaged reboot-no-more lab suite instead of the old standalone GPU C helper
- **Removed**: bespoke `gpu-transition-lab` package from `flake/packages.nix`
- **Updated**: `launch-trigger-capture` process matching to recognize the reboot-no-more GPU lab binaries
- **Purpose**: Keep graphics-transition diagnostics in the dedicated reboot-forensics repo while exposing them through the existing sinnix stability workflow

### 2026-03-06: Consistency, Health Telemetry, and Flake Context Refactor

- **Added**: `flake/lib-context.nix` to centralize lib extension/bootstrap shared by `nixos.nix` and `test-lib.nix`
- **Added**: `flake/command-registry.nix`; `apps.nix` now generates flake apps from a single registry
- **Removed**: `mkDotsFile` helper export from `modules/lib/features.nix`; standardized on `mkDotsFileFor`
- **Added**: Optional `health` metadata support in `mkServiceModule`; updated services to self-declare sentinel health checks
- **Refactored**: `modules/introspection.nix` now derives service checks from enabled `sinnix.services.*.health` metadata
- **Added**: `mkGraphicalUserService` helper in `modules/lib/systemd-hardening.nix`; applied in `features/desktop/base.nix`
- **Fixed**: `scripts/kitty-grid` undefined function call (`collect_kitty_windows` -> `collect_target_windows`)
- **Fixed**: `modules/features/dev/mcp-servers.nix` qdrant wrapper command continuation
- **Fixed**: `scripts/sinnix-sentinel` transition/event logging contract (`events.jsonl`) and previous-health snapshot persistence
- **Improved**: `scripts/repo-map` now supports a real `--full` mode and updated canonical-file list
- **Updated**: `hosts/sinnix-ethereal/default.nix` now imports `./storage.nix` (swap config no longer orphaned)
- **Updated**: CI formatting step now uses `nix fmt -- --check`

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
