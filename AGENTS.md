# Sinnix Configuration

> **Compressed understanding of sinnix NixOS configuration structure, patterns, and organizational rules.** Updated with every structural change.

---

## Module Taxonomy

Sinnix modules follow a clear hierarchy based on **purpose and abstraction level**:

```
modules/
├── *.nix              # Infrastructure & platform (system-level)
├── features/          # User-facing capabilities (what users interact with)
├── services/          # Long-running systemd daemons
├── bundles/           # Convenience presets (groups of features)
└── lib/               # Helper functions
```

### Decision Tree: Where Does My Config Belong?

```
MATCH config_type:
  | System infrastructure (networking, storage, nix settings)
    → modules/*.nix (top-level)

  | User-facing application or capability
    → modules/features/{cli,desktop,dev}/*.nix

  | Systemd daemon (primary purpose is background service)
    → modules/services/*.nix

  | Convenience preset (enables multiple features)
    → modules/bundles/*.nix

  | Reusable helper function
    → modules/lib/*.nix
```

---

## Top-Level Modules (Infrastructure)

Files at `modules/*.nix` represent **system-level cross-cutting concerns** that run before/beneath user features:

| Module | Purpose | Category |
|--------|---------|----------|
| foundation.nix | User identity, paths, projects, localization | Identity |
| core.nix | Nix config, caches, GC, security, firewall | Core System |
| networking.nix | Network config, DNS, hosts | Infrastructure |
| storage.nix | Filesystem mounts, drives, BTRFS | Infrastructure |
| performance.nix | CPU governor, I/O scheduler, OOM policy | Tuning |
| diagnostics.nix | System monitoring, metrics collection | Operations |
| log-hygiene.nix | Log cleanup, journal size limits | Operations |
| secrets.nix | Agenix secret integration | Security |
| home-manager.nix | Home Manager integration glue | Integration |
| nix-ld.nix | Dynamic linker for non-NixOS binaries | Compatibility |
| default.nix | Import aggregator (entry point) | Entry Point |

**Rule**: If it affects **how the system operates** (not what users do on it), it's top-level.

---

## Features (User-Facing)

Organized by domain under `modules/features/`:

### CLI (`features/cli/`)
- **core.nix**: Shell (zsh), terminal tools, prompt, shell integration

### Desktop (`features/desktop/`)
- **activitywatch.nix**: Activity tracking daemon + web UI
- **audio.nix**: PipeWire, audio devices, routing (moved from top-level)
- **base.nix**: Core desktop services (clipboard, notifications, launcher)
- **browser.nix**: Qutebrowser config, userscripts, profiles
- **common-apps.nix**: GUI utilities (file manager, image viewer, etc.)
- **crypto.nix**: Cryptocurrency tools (Monero)
- **gaming.nix**: Steam, game launchers
- **hyprland/**: Window manager config (bindings, rules, lock screen)
- **media.nix**: mpv, audio/video tools, codecs
- **mime.nix**: File associations, default applications
- **reboot-notifier.nix**: Systemd reboot notifications
- **storage.nix**: File managers, disk usage tools (distinct from top-level storage.nix which handles mounts)
- **terminal.nix**: Terminal emulators (foot, kitty)
- **theming.nix**: Stylix integration, GTK/Qt themes
- **ui.nix**: Fonts, cursor themes, Wayland base environment (moved from top-level)
- **waybar.nix**: Status bar configuration

### Dev (`features/dev/`)
- **editors.nix**: VS Code, Zed, Neovim config
- **git.nix**: Git config, aliases, tools
- **languages.nix**: Language toolchains (Python, Rust, Node, etc.)
- **mcp-servers.nix**: Model Context Protocol server configs
- **shell.nix**: Development shell tools (atuin, direnv, etc.)

**Rule**: If users **directly interact** with it, it's a feature.

---

## Services (Daemons)

Long-running systemd services in `modules/services/`:

| Service | Purpose | Has UI? |
|---------|---------|---------|
| sinex.nix | Data capture platform (Rust/NATS/PostgreSQL) | No (background) |
| netdata.nix | System monitoring metrics collection | Yes (web UI) |
| terminal-capture.nix | Shell session recording (transparent capture) | No (background) |
| transmission.nix | BitTorrent daemon | Yes (web UI) |

**Rule**: Primary purpose is **daemon**, UI is secondary/optional. Compare with `features/desktop/activitywatch.nix` where user wants **tracking**, daemon is implementation detail.

---

## Bundles (Presets)

Convenience wrappers in `modules/bundles/`:

- **desktop.nix**: Enables all desktop features + audio + UI in one toggle
- **dev.nix**: Enables all development tools

**Rule**: Bundles only **enable other modules**, never add their own config.

Example:
```nix
# modules/bundles/desktop.nix
config = lib.mkIf cfg.enable {
  sinnix = {
    features.desktop.audio.enable = true;
    features.desktop.ui.enable = true;
    features.desktop.hyprland.enable = true;
    features.desktop.browser.enable = true;
    # ... etc
  };
};
```

---

## Flake Organization

### `flake/` Directory

- **apps.nix**: Flake apps (switch, test, update, clean, check, etc.)
- **dev-shell.nix**: Development shell with pre-commit hooks
- **formatter.nix**: Nixpkgs-fmt configuration
- **nixos.nix**: NixOS configuration integration (imports modules/)
- **packages.nix**: Custom packages (shell scripts wrapped with dependencies)
- **tests.nix**: System tests
- **overlay/**: Nixpkgs overlays (package modifications, external integrations)
  - **package/**: Package overlays (individual files per package)
  - **patch/**: Patches for upstream packages

### Overlay vs Package: When to Use Each

**Use overlays** (`flake/overlay/package/*.nix`) when:
- Overriding existing nixpkgs packages (e.g., chromium with custom flags)
- Patching upstream packages (e.g., aw-server-rust with fix)
- Integrating external flake outputs into pkgs namespace

**Use packages** (`flake/packages.nix`) when:
- Creating custom shell scripts wrapped with dependencies
- Building standalone utilities specific to sinnix
- Adding new packages not in nixpkgs

**Example**:
```nix
# flake/packages.nix - custom scripts
packages.asbl-no-moar = pkgs.writeShellApplication {
  name = "asbl-no-moar";
  runtimeInputs = [ pkgs.bash pkgs.coreutils pkgs.procps ];
  text = ''exec ${pkgs.bash}/bin/bash ${inputs.self}/scripts/asbl-no-moar "$@"'';
};

# flake/overlay/package/chromium.nix - override existing package
final: prev: {
  chromium = prev.chromium.override {
    commandLineArgs = "--enable-features=TouchpadOverscrollHistoryNavigation";
  };
}
```

---

## Scripts Management

Scripts live in two places with distinct purposes:

1. **Source code**: `scripts/` directory (shell/Python scripts)
2. **Package definitions**: `flake/packages.nix` (wrappers with dependencies)

Each script requires:
- Source file in `scripts/`
- Package wrapper in `flake/packages.nix` with `runtimeInputs`
- Path reference via `${inputs.self}/scripts/name`

This pattern ensures scripts have proper PATH and dependencies without polluting the global environment.

---

## Host Configuration

Host-specific configs in `hosts/{hostname}/`:

- **sinnix-prime**: Desktop workstation (Intel i7-13700K, RTX 4080)
- **sinnix-ethereal**: Secondary machine

Each host:
1. Imports shared modules via `../modules`
2. Sets machine-specific options (boot, storage, display, input)
3. Enables bundles/features selectively

Example:
```nix
# hosts/sinnix-prime/default.nix
{
  imports = [
    ../../modules
    ./boot.nix
    ./display.nix
    ./storage.nix
    ./input.nix
  ];

  sinnix = {
    bundles.desktop.enable = true;
    bundles.dev.enable = true;
    services.sinex.enable = true;
  };
}
```

---

## Dotfiles Management

Dotfiles in `dots/` directory:

- **Mechanism**: Home Manager out-of-store symlinks (`mkOutOfStoreSymlink`)
- **Benefit**: Edits propagate instantly without rebuild
- **Key paths**:
  - `dots/claude/` → `~/.config/claude` (Claude Code config)
  - `dots/codex/` → `~/.config/codex` (Codex CLI config)
  - `dots/nvim/` → `~/.config/nvim` (Neovim LazyVim)
  - `dots/vscode/User/` → VS Code settings
  - `dots/qutebrowser/` → Qutebrowser config + userscripts
  - `dots/hyprland/` → Hyprland config (some declarative in modules)

---

## Module Development Patterns

### Feature Module Boilerplate

```nix
# modules/features/domain/feature.nix
{ mkFeatureModule, lib, pkgs, ... }:
mkFeatureModule {
  path = [ "domain" "feature" ];  # Creates sinnix.features.domain.feature.enable
  description = "Brief description of feature";
  configFn = { config, pkgs, lib, ... }: {
    # NixOS config
    programs.example.enable = true;

    # Home Manager config
    home-manager.users.${config.sinnix.user.name} = {
      programs.example.settings = { ... };
    };
  };
}
```

### Service Module Boilerplate

```nix
# modules/services/daemon.nix
{ lib, config, pkgs, ... }:
let
  cfg = config.sinnix.services.daemon;
in {
  options.sinnix.services.daemon = {
    enable = lib.mkEnableOption "Daemon service";
  };

  config = lib.mkIf cfg.enable {
    systemd.services.daemon = {
      description = "Daemon Service";
      wantedBy = [ "multi-user.target" ];
      serviceConfig = {
        Type = "simple";
        ExecStart = "${pkgs.daemon}/bin/daemon";
        Restart = "on-failure";
      };
    };
  };
}
```

---

## Common Workflows

### Rebuild System
```bash
cd /realm/project/sinnix
direnv allow                    # Activate devshell
check                          # Validate config
sudo nix run .#switch          # Apply changes
```

### Add New Feature
```bash
# 1. Create module
vim modules/features/desktop/new-feature.nix

# 2. Import in default.nix
vim modules/features/desktop/default.nix  # Add to imports

# 3. Enable in host or bundle
vim hosts/sinnix-prime/default.nix        # Add sinnix.features.desktop.new-feature.enable

# 4. Test
check && sudo nix run .#test

# 5. Update AGENTS.md
vim AGENTS.md  # Add to feature list
```

### Add New Package Overlay
```bash
# 1. Create overlay file
vim flake/overlay/package/my-package.nix

# 2. Add to overlay list
vim flake/overlay/package/default.nix  # Add to mkOverlay list

# 3. Test
nix build .#nixosConfigurations.sinnix-prime.config.system.build.toplevel
```

### Add New Script
```bash
# 1. Create script
vim scripts/my-script
chmod +x scripts/my-script

# 2. Add package wrapper
vim flake/packages.nix  # Add writeShellApplication entry

# 3. Test
nix run .#my-script
```

---

## Project Environment

### Paths (defined in foundation.nix)
```nix
config.sinnix.paths = {
  realmRoot = "/realm";
  dataRoot = "/realm/data";
  capturesRoot = "/realm/data/captures";
  exportsRoot = "/realm/data/exports";
  projectRoot = "/realm/project/sinnix";
  dotsRoot = "/realm/project/sinnix/dots";
};

config.sinnix.projects = {
  root = "/realm/project";
  sinnix = "/realm/project/sinnix";
  sinex = "/realm/project/sinex";
  lynchpin = "/realm/project/sinity-lynchpin";
  polylogue = "/realm/project/polylogue";
  knowledgebase = "/realm/project/knowledgebase";
};
```

### Environment Variables (exported globally)
```bash
SINNIX_ROOT=/realm/project/sinnix
SINEX_ROOT=/realm/project/sinex
LYNCHPIN_REPO_ROOT=/realm/project/sinity-lynchpin
POLYLOGUE_ROOT=/realm/project/polylogue
KNOWLEDGEBASE_ROOT=/realm/project/knowledgebase
```

---

## Maintenance Protocol

### When to Update AGENTS.md

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
- ❌ Minor config changes within existing modules → don't update AGENTS.md

### Verification Steps
After structural changes:
1. `check` - validate configuration
2. `nix run .#test` - test build without applying
3. `sudo nix run .#switch` - apply if test passes
4. Verify features still work (spot-check critical services)

---

## Troubleshooting

### Module Not Found
```
error: attribute 'X' missing
```
**Fix**: Check imports in `modules/{category}/default.nix`, ensure file is listed.

### Circular Dependency
```
error: infinite recursion encountered
```
**Fix**: Check for modules referencing each other. Use `lib.mkIf` to break cycles.

### Build Fails After Moving Module
```
error: option 'sinnix.old.path.enable' used but not defined
```
**Fix**: Search for old option path in host configs and bundles, update references.

---

## Recent Changes

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

---

## Philosophy

- **Explicit over implicit**: Document organizational rules, don't rely on intuition
- **Clear boundaries**: Top-level = infrastructure, features = user-facing, services = daemons
- **Consistent granularity**: One file per significant feature, group related small features
- **Maintenance discipline**: Update AGENTS.md with every structural change
- **Pattern enforcement**: Use decision trees, not ad-hoc placement
