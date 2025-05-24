# CLAUDE WORKFLOW SYSTEM

## 🔄 SYSTEMATIC WORK PATTERN

1. **📋 Map Possibilities** - Use TodoWrite to outline all approaches before acting
2. **🎯 Plan Optimal Path** - Select best approach with clear rationale documented
3. **⚙️ Execute Incrementally** - Implement with validation at each step, mark todos complete immediately

## 🔗 GIT & GITHUB PRACTICES

- **🌿 Branching**: Create feature branches for non-trivial changes (`claude/feature-name`)
- **📝 Issues**: Track work via GitHub issues for complex features (break into sub-issues)
- **🔀 PRs**: Use pull requests for review-worthy changes with clear context
- **💫 Commits**: Atomic, descriptive commits with `Co-authored-by: Claude <noreply@anthropic.com>`
- **✅ Testing**: Validate with `nix run .#test` before switching, `nix flake check` always

## 👤 IDENTITY PATTERN

- **Commits**: Co-authorship trailers for attribution clarity
- **Branches**: `claude/feature-description` for Claude-initiated work
- **Issues**: Claude-authored with clear automation context
- **Communication**: Direct, technical, no artificial humanness masking

## 🏗️ DOMAIN-UNIFIED ARCHITECTURE PRINCIPLES

- **🎯 Domain Ownership**: Eliminate system/user cognitive splits via unified domain modules
- **🔗 Sinity Alias**: Use `sinity.programs.X` instead of `home-manager.users.sinity.programs.X`
- **🎨 Stylix Integration**: System-wide theming, no custom abstractions
- **📈 Incremental Migration**: Validate each phase, preserve functionality always
- **🧪 Bottom-up Design**: Solve real friction, avoid over-abstraction trap

## 📊 MULTI-TURN TASK MANAGEMENT

- **📝 TodoWrite Proactively**: Break complex requests into trackable sub-tasks immediately
- **✅ Complete Immediately**: Mark todos done as soon as finished, don't batch
- **🎯 Single Focus**: Only one todo `in_progress` at a time
- **📋 Context Preservation**: Use GitHub issues for work spanning multiple sessions

## 🔧 TECHNICAL VALIDATION STACK

```bash
nix flake check                                    # Syntax validation
sudo nixos-rebuild test --flake .#sinnix-prime   # Functional validation
# Test: login, desktop, audio, development, networking, automation
```

## 🏛️ ARCHITECTURE OVERVIEW

This repository implements domain-unified NixOS configuration:

1. `flake.nix` - Entry point and dependency declaration
2. `flake/*.nix` - Modular flake outputs (development, apps, system config)
3. `module/foundation.nix` - Core system bootstrap, users, security
4. `module/interface.nix` - Complete UI experience (system + desktop)
5. `module/development.nix` - Complete dev workflow (tools + environment)
6. `module/media.nix` - Complete audio/video (system + applications)
7. `module/communication.nix` - Complete connectivity (network + apps)
8. `module/automation.nix` - Complete orchestration (services + scripts)
9. `host/sinnix-prime/*.nix` - Hardware-specific configuration only

## 🔑 CRITICAL PATTERNS

**Secret Management**:

- Secrets in `secret/*.age`, auto-discovered via `module/foundation.nix`
- Environment variables: `dash-case-name.age` → `DASH_CASE_NAME`
- Access: `config.age.secrets.<name>.path`

**Package Management**:

- System packages: `environment.systemPackages` in appropriate domain
- User packages: `sinity.home.packages` in appropriate domain

**Extension Points**:

- New functionality goes in appropriate domain module
- Host-specific config only in `host/sinnix-prime/`
- Cross-cutting concerns handled by stylix + domain extension points

## 🎯 SUCCESS CRITERIA

- Zero cognitive overhead asking "is this system or user config?"
- Single source of truth for each functional domain
- All changes follow domain boundaries, not implementation layers
- System ready for Blueprint 0.5+ extensions

---
*Domain-unified architecture eliminates implementation detail leakage via functional organization*

# Information regarding refactoring issues

**2. Lost Configurations and Functionality:**

- **Hyprlock Background Image**: The specific `forest.jpg` for `hyprlock` is deleted. The `hyprlock` configuration itself is commented out in `interface.nix` and references a placeholder path (`/tmp/nixos-fallback-background.png`).
- **Rofi Configuration**: The `programs.rofi` block from the deleted `module/home/desktop/rofi.nix` (which configured theme, font, extra Rofi settings) has not been reintegrated into `module/interface.nix` or elsewhere. The `rofi-wayland` package is also not explicitly added to `home.packages` in `interface.nix` or `automation.nix`.
- **SwayNC Customization**: The `config.json` and `style.css` for `swaynotificationcenter` (from `module/home/desktop/swaync/`) are deleted and not reintegrated. The package is installed via `interface.nix`, but will use default settings.
- **`vm-start.sh` Script**: This script (for starting a VM with virsh/virt-viewer) was deleted from `module/home/scripts/scripts/` and its functionality was not inlined or moved. Dependencies like `virt-manager` or `virt-viewer` would also be implicitly lost if not pulled in elsewhere.
- **Specific Package Removals/Non-Migrations**:
  - **Dependencies for inlined scripts**:
    - `extract.sh` (now in `automation.nix`) requires `unzip`, `unrar`, `p7zip`. These were in the deleted `module/home/system.nix` but not re-added to `automation.nix`'s `home.packages`.
    - `record.sh` (now in `automation.nix`) requires `zenity`. This package was not present previously and was not added.
    - `rofi-wayland` for `wallpaper-picker.sh` and `show-keybinds.sh` (as noted above).
  - **From `module/home/system.nix`**:
    - `bpftrace`
    - `entr` (perform action when file changes)
    - `file` (Show file information)
    - `tldr`
    - `xdg-utils`
    - `xxd`
    - Wayland/desktop utilities: `wl-clipboard` (though `wl-clip-persist` is added), `clipboard-jh` (Cut, copy, and paste anything in your terminal), `redshift` (Adjust color temperature). `cliphist` is installed via `home.packages` in `interface.nix`.
    - Hardware diagnostics: `cpuid`, `i7z`, `mcelog`, `memtester`, `numactl`.
    - Storage utilities: `xfsprogs`, `e2fsprogs`, `lvm2`, `parted`, `fio`, `ioping`, `udisks2`, `extundelete`.
    - Networking utility: `mtr`. (Note: `iproute2` is generally a core part of NixOS. `nmap`, `tcpdump`, `traceroute` are in `communication.nix -> home.packages`).
    - System-level graphics packages: `mesa`, `libGL`, `libglvnd` (these are often implicitly pulled by drivers or compositors, but explicit system-wide installation is gone).
    - Graphics/HW utils: `hw-probe`, `hwdata`, `graphicsmagick`.
  - **From `module/home/desktop-apps.nix`**:
    - Commented-out Factorio setup.
    - `evtest` (Input device event monitor)
    - `meld` (Diff tool)
    - `piper` (Mouse configuration)
    - `android-tools`, `android-file-transfer`
    - `hledger` (Accounting)
    - `llm` (CLI for LLMs)
    - `single-file-cli` (Save web pages)
    - `programmer-calculator`, `bc`, `calc`
  - **From `module/home/packages.nix`** (misc utilities not fitting other categories):
    - `imgur-screenshot`
    - `usbview`
    - `strace`, `ltrace` (Debugging tools)
    - `nvitop` (NVIDIA GPU monitoring)
    - `cage` (Wayland kiosk)
    - `wayland-protocols` (often a build input, explicit install might be for development)
    - `vkmark` (Vulkan benchmark)
    - `dtach` (Screen alternative)
    - `lnch` (Application launcher)
    - `at` (Job scheduler)
    - `soundwireserver`: This package was installed via the deleted `module/home/packages.nix`. A Hyprland keybind `SUPER SHIFT, S, exec, hyprctl dispatch exec '[workspace 5 silent] SoundWireServer'` exists. If `soundwireserver` is not re-added (e.g., in `automation.nix` or `media.nix` `home.packages`), this keybind will fail. It's currently missing.

