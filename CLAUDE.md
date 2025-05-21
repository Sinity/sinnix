# NIXOS-CONFIG CONTEXT FOR CLAUDE

## ARCHITECTURE OVERVIEW

This repository implements a modular NixOS configuration built with flake-parts. The core architectural pattern is:

1. `flake.nix` - Entry point and dependency declaration
2. `flake/*.nix` - Modular flake outputs (development, apps, system config)
3. `module/system/*.nix` - System-level NixOS modules
4. `module/home/*.nix` - User-level home-manager modules (includes desktop and shell config)
5. `host/sinnix-prime/*.nix` - Host-specific hardware configuration

Critical design relationships:
- nixos.nix references system modules and host-specific configuration
- system modules import each other with explicit dependencies
- home-manager modules are imported within system/user.nix

## MODULE DEPENDENCY GRAPH

```
flake.nix
├─ flake/nixos.nix → module/system/overlays.nix (MUST LOAD FIRST)
├─ flake/nixos.nix → host/sinnix-prime/default.nix (HOST-SPECIFIC)
│  ├─ host/sinnix-prime/audio.nix
│  ├─ host/sinnix-prime/boot.nix
│  ├─ host/sinnix-prime/display.nix
│  ├─ host/sinnix-prime/hardware.nix
│  └─ host/sinnix-prime/storage.nix
└─ flake/nixos.nix → module/system/default.nix
   ├─ module/system/network.nix
   ├─ module/system/security.nix (HANDLES SECRETS)
   ├─ module/system/services.nix
   ├─ module/system/system.nix
   ├─ module/system/nginx.nix
   ├─ module/system/nix-ld.nix
   └─ module/system/user.nix → module/home/default.nix
      ├─ module/home/desktop/default.nix (CONSOLIDATED DESKTOP)
      │  ├─ module/home/desktop/hyprland/
      │  ├─ module/home/desktop/waybar/
      │  ├─ module/home/desktop/swaync/
      │  ├─ module/home/desktop/rofi.nix
      │  └─ module/home/desktop/themes.nix
      ├─ module/home/environment.nix (SHELL CONFIG)
      ├─ module/home/kitty.nix
      ├─ module/home/git.nix
      ├─ module/home/ssh.nix
      ├─ module/home/neovim.nix
      ├─ module/home/development.nix
      ├─ module/home/media.nix
      ├─ module/home/desktop-apps.nix
      ├─ module/home/packages.nix
      ├─ module/home/system.nix
      ├─ module/home/activity_watch.nix
      ├─ module/home/hydrus.nix
      ├─ module/home/scripts/scripts.nix
      └─ module/home/xdg-mimes.nix
```

## KEY IMPLEMENTATION PATTERNS

1. **Secret Management**: 
   - Secrets stored in `secret/*.age` 
   - Automatically discovered via `module/system/security.nix`
   - Environment variables created using pattern: `dash-case-name.age` → `DASH_CASE_NAME`
   - Access pattern: `config.age.secrets.<name>.path`

2. **Import Pattern**:
   - Module files are explicitly imported in their parent module
   - Overlay dependencies are loaded first via explicit ordering

3. **Package Management**:
   - System packages: `module/core/system.nix` in `environment.systemPackages`
   - User packages: `module/home/packages.nix` in `home.packages`
   - Critical distinction: system packages available to all users, home packages only to sinity

4. **Options Convention**:
   - Options defined with types using `lib.mkOption`
   - Conditional configurations use `lib.mkIf` not `if then else`
   - Option merging uses `lib.mkMerge` for complex cases

5. **Dependency Management**:
   - Core dependencies centralized in flake.nix inputs
   - Dependencies are pinned via flake.lock
   - Nixpkgs pinned to nixos-unstable
   - Custom repos use a dedicated input (e.g., claude-squad)

6. **Error Handling**:
   - Shells enforce `set -euo pipefail` for strict error handling
   - User feedback commands include clear error messages
   - Application exit codes propagate to calling context

## IMPORTANT GLOBAL VARIABLES

- `username = "sinity"` - Primary user account, defined in flake.nix
- `host = "desktop"` - Current hostname, passed to modules
- `intercept-bounce` - Custom package directly passed to modules
- `FLAKE` - Environment variable pointing to `/realm/nixos-config`
- `NIX_BUILD_HOOK` - Set to nix-output-monitor for enhanced build output

## CRITICAL SYSTEM PATHS

- `/realm/nixos-config` - Repository location, also exposed as FLAKE in shell
- `/realm/observability/claude-code-api-log` - Claude Code logs from module/home/development.nix
- `~/.config` - User configuration directory
- `/nix/var/nix/profiles/system` - System generations profile
- `/etc/nixos` - Traditional NixOS configuration location (not used in flake approach)

## SHELL ENVIRONMENT

Shell aliases defined in `module/home/shell.nix`:
- `nix-switch = "nix run $FLAKE#switch"`
- `nix-test = "nix run $FLAKE#test"`
- `nix-check = "nix run $FLAKE#check"`

Custom prompt configured via Starship in `module/home/starship.nix` with:
- Git status integration
- Directory information
- Command duration
- Nix shell indicator
- Customized with Gruvbox Dark theme

Shell environments configured:
- Zsh (primary shell with various plugins)
- Nushell (alternative shell with compatible aliases)

## CRITICAL SERVICES

The following services must function for the system to operate properly:
- Boot loader (module/core/bootloader.nix)
- Network configuration (module/core/network.nix)
- User services (module/core/user.nix)

## EXTENSION POINTS

When adding new functionality, follow these patterns:

1. **New Package**:
   - System-wide: Add to `module/core/system.nix` in `environment.systemPackages`
   - User-only: Add to `module/home/packages.nix` in `home.packages`

2. **New Service**:
   - Create module in appropriate location (core/ or home/)
   - Import in respective default.nix
   - Use conditional activation with `lib.mkIf` if situational

3. **New Module**:
   - Create file in appropriate directory
   - Import in respective default.nix

4. **New Flake Input**:
   - Add to inputs section in flake.nix
   - Consider adding follows directive to share nixpkgs

5. **New Host**:
   - Would require implementing a hosts/ directory structure
   - Define new nixosConfigurations entry in flake/nixos.nix
   - Create host-specific modules for hardware, etc.

## IMPORTANT DESIGN DECISIONS

1. **Flake-Parts**: Used to modularize flake.nix rather than traditional single-file approach
2. **Home-Manager**: Used for user configuration rather than system-wide settings
3. **Agenix**: Used for secret management with automatic discovery
4. **Devenv**: Used for development environment instead of shell.nix
5. **Modular Structure**: Split functionality into focused modules rather than monolithic approach
6. **Explicit Imports**: Modules explicitly imported rather than auto-discovered
7. **Host-Specific**: Current design focused on single host (desktop)

## KNOWN LIMITATIONS

- System currently supports only single host (desktop)
- Hardware configuration is specific to desktop hardware
- Some modules may have hardcoded paths
- No automatic testing infrastructure for configuration changes
- Secret management requires key presence for decryption
- No VM/container-based testing environment configured

## CUSTOM DEVELOPMENT ENVIRONMENT

Development environment configured through devenv in `flake/dev-shell.nix`:
- Git hooks for code quality (formerly pre-commit hooks)
- Helper scripts for common operations
- Environment variables and package dependencies

Key features:
- Direnv integration via .envrc
- Code formatting via nixfmt-rfc-style
- Linting via statix
- Dead code detection via deadnix
- Shell script checking via shellcheck

## FLAKE APP COMMANDS

The repository provides several commands via `nix run .#<command>`:

| Command | Purpose | Implementation |
|---------|---------|----------------|
| check   | Validate configuration | Runs nix flake check and syntax validation |
| format  | Format Nix code | Runs nixfmt-rfc-style on all .nix files |
| lint    | Check code quality | Runs statix on codebase |
| test    | Test configuration | Runs nixos-rebuild test with nom output |
| switch  | Apply configuration | Runs nixos-rebuild switch with nom output |
| update  | Update flake inputs | Runs nix flake update |
| clean   | Clean old generations | Removes old system generations |
| agenix  | Manage secrets | Provides access to agenix command |

Implementation details in flake/apps.nix.

## CLAUDE-SPECIFIC SERVICES

The following Claude-related services are configured:
- `claude-code-logger` in `module/home/development.nix`
- `claude-squad` and `claude-desktop` in various modules

This setup enables:
- Logging of Claude API interactions
- Structured storage of conversations
- Improved debugging and analysis of AI workflows

## HARDWARE CONTEXT

This configuration is for a desktop machine with:
- x86_64 architecture
- Specific hardware modules loaded in module/core/hardware.nix
- Graphics configuration in module/core/x.nix

Hardware-specific components:
- Storage and filesystem configuration in module/core/storage.nix
- Network interfaces in module/core/network.nix
- Audio configuration in module/core/audio.nix
- X11/Wayland setup in module/core/x.nix

## USER INTERFACE

The system uses a graphical environment with:
- Hyprland as the window manager (module/home/hyprland/)
- Custom themes and configurations for GTK (module/home/gtk.nix)
- Waybar for status information (module/home/waybar/)
- Rofi as application launcher (module/home/rofi.nix)
- Kitty as terminal emulator (module/home/kitty.nix)

UI customization focuses on:
- Consistent theming (predominantly Gruvbox Dark)
- Keyboard-centric workflow
- Minimal but informative status indicators

## DEVELOPMENT TOOLS

The system is configured with multiple development toolchains:
- Rust via rustup
- Python with multiple versions
- Node.js (both stable and latest)
- Various language servers and formatters

Editor setup:
- Neovim as primary editor (configured in ./nvim/)
- LazyVim as framework with custom plugins
- Language-specific extensions

## CUSTOM USER SCRIPTS

Custom user scripts in `module/home/scripts/scripts/`:
- Various utility scripts for daily operations
- Available in PATH through module/home/scripts/scripts.nix

Notable scripts:
- power-menu.sh - Power management operations
- wall-change.sh - Wallpaper management
- keybinds.sh - Keyboard shortcut documentation
- extract.sh/compress.sh - Archive management

## PACKAGE OVERLAY SYSTEM

Package overlays are defined in `module/core/overlays.nix` and provide:
- Custom package versions
- Patched packages
- Local packages from pkgs/ directory

This mechanism allows for packages to be modified or added without
forking nixpkgs.

## NIX-LD CONFIGURATION

The nix-ld system in `module/core/nix-ld.nix` configures runtime
library loading for non-NixOS binaries, enabling compatibility with:
- Proprietary software
- Binaries expecting traditional Linux paths
- Applications expecting specific library locations

## MEDIA MANAGEMENT

Media applications and services in `module/home/media.nix`:
- Video players and libraries
- Audio tools and codecs
- Image processing applications

Notable features:
- Hardware acceleration configurations
- Codec support for various formats
- Integration with system audio services

## STORAGE CONFIGURATION

Storage setup in `module/core/storage.nix`:
- Filesystem mounts
- LUKS encryption (if used)
- Auto-mounting rules
- Backup configurations (if implemented)

## CORE REPOSITORY ANALYSIS

This repository represents a desktop NixOS system with:
- Development tooling focus
- GUI applications and media
- AI/LLM integration (Claude services)
- Shell environment optimization

Typical workflow:
1. Edit appropriate modules
2. Run checks (check/lint/format)
3. Apply with switch

## VERSION CONTROL INTEGRATION

Git configuration in `module/home/git.nix`:
- User identity and preferences
- Aliases for common operations
- Integration with GitHub via gh CLI

Code quality automation:
- Git hooks applied via devenv's git-hooks system
- Automated formatting on commit
- Linting and dead code detection

## NEOVIM CONFIGURATION

Neovim setup in `/nvim/` directory:
- LazyVim as framework
- Custom plugin configuration
- Language-specific settings
- Integration with system tools

Key plugins:
- LSP support for multiple languages
- Treesitter for syntax highlighting
- Telescope for fuzzy finding
- Git integration

## SECURITY MODEL

Security configuration in `module/core/security.nix`:
- Secret management via agenix
- System hardening settings
- SSH configuration
- Firewall rules

The key security pattern is isolation of secrets via age encryption
with automatic environment variable generation.

## MULTI-HOST EXTENSION PATTERN

While not currently implemented, extending to multiple hosts would follow:
1. Create hosts/ directory with subdirectories per host
2. Define host-specific modules for hardware, etc.
3. Add entries to nixosConfigurations in flake/nixos.nix
4. Parametrize shared modules with hostname conditions

## AUTHENTICATION PATTERN

User authentication in `module/core/user.nix`:
- Local user account creation
- Authentication methods
- Authorization (sudo access, etc.)
- Home directory configuration

## NETWORKING ARCHITECTURE

Network configuration in `module/core/network.nix`:
- Interface setup
- DNS configuration
- Firewall rules
- Network services

## BOOTLOADER CONFIGURATION

Boot process in `module/core/bootloader.nix`:
- Bootloader selection and configuration
- Boot parameters
- Kernel selection
- Initrd configuration