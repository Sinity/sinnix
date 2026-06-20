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

### 2026-05-24: Runtime Inventory Consolidation

- **Renamed**: `modules/runtime-policy.nix` → `modules/runtime.nix`
- **Replaced**: split `/etc/sinnix/runtime-policy.json` and `/etc/sinnix/observability.json` with `/etc/sinnix/runtime-inventory.json`
- **Moved**: generated service/capture/mount/backup inventory from `introspection.nix` into the runtime inventory contract
- **Updated**: `sinnix-observe`, `sinnix-scope`, machine telemetry, and Lynchpin to consume the single runtime inventory
- **Added**: `modules/lib/runtime-defaults.nix` so package fallbacks reuse the same class/slice/command defaults as NixOS evaluation
- **Purpose**: remove the troubleshooting-era split between placement policy and observability inventory; runtime ownership now has one present-tense contract

### 2026-05-24: Declared Runtime Surfaces

- **Renamed**: `modules/workload-policy.nix` → `modules/runtime.nix`
- **Added**: `sinnix.runtime.surfaces` as the owner-declared registry for runtime units, managers, kinds, resource classes, observability, and capture outputs
- **Unified**: resource class descriptions and systemd service settings under `sinnix.runtime.inventory.classes.<name>`
- **Added**: runtime-surface assertions for duplicate manager/unit pairs, unknown resource classes, and unit-kind suffix mismatches
- **Tightened**: `mkRuntimeServiceConfig` now fails on unknown unit lookups instead of silently falling back to the generic `system` class
- **Replaced**: service-local `observe` options, `unitClasses`, `observedUnits`, and `observedSlices` with surfaces-derived runtime inventory JSON
- **Updated**: `sinnix-observe`, `sinnix-scope`, machine telemetry, and config tests to consume `/etc/sinnix/runtime-inventory.json`
- **Purpose**: make runtime ownership explicit in the module that creates each unit, instead of reconstructing live surfaces from troubleshooting-era side registries

### 2026-05-23: Build and Runtime Policy Realization

- **Added**: `modules/build-policy.nix` as the owner of Nix daemon settings, build scratch, sccache, GC, and store optimisation
- **Added**: runtime resource class service settings plus `mkRuntimeServiceConfig` so services derive scheduler/resource policy from the canonical runtime registry
- **Moved**: Sinex development cache relocation from generic `sinnix-scope` into project-kind direnv setup
- **Removed**: unproven Nix experimental features and recovery-era boot timeout kernel params
- **Purpose**: make build/runtime policy present-tense and centralized instead of duplicated across one-off service overrides

### 2026-05-23: Observability Contract Cleanup

- **Removed**: dormant `sinnix-sentinel` service, package, script, VM check, and test surface
- **Removed**: stale `sinnix-oomd-watch` polling timer and syslog-index `oomd-events` output
- **Replaced**: service `health` metadata with present-tense `observe` metadata
- **Added**: generated service/capture inventory consumed by operator reports and Lynchpin; later folded into `/etc/sinnix/runtime-inventory.json`
- **Purpose**: keep Sinnix responsible for capture mechanics and live inventory while leaving analysis in Lynchpin

### 2026-05-23: Present-Tense Baseline Cleanup

- **Removed**: automatic PSI pressure intervention from below; below remains the protected recorder and `sinnix-observe` remains available for manual forensics
- **Removed**: recovery boot specialisations, stale UKI cleanup, and frozen-scope thaw timer from the host baseline
- **Removed**: unpromoted Python sentinel sidecar package
- **Reduced**: Chrome and editor Wayland flags to the current color-management disable only; Vulkan/ANGLE defaults are no longer suppressed
- **Updated**: CLI feature documentation to match the current module tree

### 2026-05-07: Protected Agent Sessions and OOMD Kill Visibility

- **Added**: `agent.slice` as a protected user-manager slice for Claude, Codex, Gemini, and Forge frontends
- **Updated**: managed agent wrappers now launch through `sinnix-scope agent -- ...` instead of `background`
- **Removed**: `systemd-oomd` PSI kills from build/background/nix-build slices after runtime evidence showed kills with ~24G MemAvailable and one victim at 4M current memory
- **Kept**: build/background/nix-build slices remain weighted, latency-sheddable, and clearly attributed; actual low-memory intervention belongs to earlyoom
- **Improved**: `sinnix-observe` now reports `agent.slice` as `interactive-agent`
- **Added**: `scripts/sinnix-oomd-watch`, its oneshot service, and a polling timer to persist oomd/cgroup OOM events under `/realm/data/captures/syslog/oomd-events` and send desktop notifications without a resident journal reader
- **Purpose**: preserve the agent and terminal recovery surface while avoiding PSI false-positive kills under low actual memory usage

### 2026-03-06: Consistency, Health Telemetry, and Flake Context Refactor

- **Added**: `flake/lib-context.nix` to centralize lib extension/bootstrap shared by `nixos.nix` and `test-lib.nix`
- **Added**: `flake/command-registry.nix`; `apps.nix` now generates flake apps from a single registry
- **Removed**: `mkDotsFile` helper export from `modules/lib/features.nix`; standardized on `mkDotsFileFor`
- **Added**: Initial service metadata support in `mkServiceModule`; later replaced by the current `observe` contract
- **Refactored**: `modules/introspection.nix` gained generated service metadata output, later superseded by `/etc/sinnix/runtime-inventory.json`
- **Added**: `mkGraphicalUserService` helper in `modules/lib/systemd-hardening.nix`; applied in `features/desktop/base.nix`
- **Fixed**: `scripts/kitty-grid` undefined function call (`collect_kitty_windows` -> `collect_target_windows`)
- **Fixed**: `modules/features/dev/mcp-servers.nix` qdrant wrapper command continuation
- **Fixed**: earlier system-health transition/event logging and previous-state snapshot persistence
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
  - `encrypt-folder`, `decrypt-folder`
- **Extracted**: `lsp-root.nix` to `scripts/lsp-root` with package wrapper
- **Removed**: `modules/lib/lsp-root.nix` (obsolete)
- **Consolidated**: 5 activation blocks in `shell.nix` → 2 (`linkConfigs`, `rebuildBatCache`)
- **Added**: Shell alias `zed = "zeditor"`, removed wrapper script from `editors.nix`
- **Added tests** for desktop and Sinex module evaluation
- **Added**: Header comments to 4 core modules (core.nix, home-manager.nix, performance.nix, storage.nix)
- **Documented**: Hyprland composite module pattern in features.md

### 2026-02-02: Auto-Discovery & Module Consistency Refactor

- **Moved**: `modules/nix-ld.nix` → `modules/features/system/nix-ld.nix`
- **Created**: `modules/features/system/default.nix` (auto-discovery)
- **Consolidated**: `modules/features/dev/shell/` (4 files) → `modules/features/dev/shell.nix` (single file with subFeatures)
- **Standardized**: feature auto-discovery under `modules/features/`
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
- **Updated**: Imports in `modules/default.nix` and `features/desktop/default.nix`
- **Option paths changed**:
  - `sinnix.audio.enable` → `sinnix.features.desktop.audio.enable`
  - `sinnix.ui.enable` → `sinnix.features.desktop.ui.enable`

### 2026-01-27: Script Packaging Refactor

- **Consolidated**: Script packages from `flake/overlay/package/*.nix` to `flake/packages.nix`
- **Removed overlays**: asbl-no-more.nix, hogkill.nix, perf-scan.nix
- **Reasoning**: Scripts are custom packages, not nixpkgs modifications
- **Pattern**: All custom scripts now defined in single `flake/packages.nix` file
