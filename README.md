# Sinnix

Personal NixOS and Home Manager configuration for a desktop workstation,
headless host, and OpenWrt router. It is the live deployment repository for
those machines, not a portable NixOS framework or a supported configuration
template.

The flake uses flake-parts for composition, Home Manager for user state, and
agenix for runtime secrets. Encrypted payloads and their recipient inventory
live outside the checkout; the public tree contains only the runtime path and
service contracts that consume them.

## How configuration is assembled

- `modules/default.nix` recursively discovers NixOS modules. `modules/lib/`
  contains helper functions and `modules/attic/` contains retired code, so both
  are excluded from auto-import.
- `hosts/` supplies machine-specific choices and enables the features,
  services, bundles, and profiles each host needs.
- `modules/features/` owns user-facing capabilities; `modules/services/` owns
  daemons and timers; top-level `modules/*.nix` owns platform infrastructure.
- `dots/` is linked into the operator's home through Home Manager.
- `flake/` owns host construction, package/overlay wiring, development
  commands, checks, and the OpenWrt router surface.

Auto-import removes registration boilerplate; it does not auto-enable optional
features. Host modules and typed options remain the explicit composition
boundary.

## Working with the repository

Enter the development shell first:

```bash
cd /realm/project/sinnix
direnv allow
# or: nix develop
```

The shell exposes the supported operations:

- `check` — build the curated default check tier sequentially.
- `lint` — run deadnix, statix, and shellcheck without changing files.
- `format` — format through treefmt/nixfmt.
- `switch` — build and activate the workstation configuration.
- `boot` — build and register the next boot generation without activating it.
- `test-system` — test activation without making it the boot default.
- `test-vm` — build and launch the NixOS VM smoke surface.

These wrappers own rebuild locking and resource containment. Direct `nh os
switch` invocations bypass that policy.

## Repository shape

```text
flake.nix       flake-parts entry point and inputs
flake/          host construction, dev shell, checks, packages, router
hosts/          per-machine configuration
modules/        auto-imported platform, feature, service, and profile modules
modules/lib/    module factories and shared Nix helpers
dots/           Home Manager-managed dotfiles and shared agent tooling
scripts/        packaged operational commands
archive/        retained historical source excluded from normal composition
```

The desktop configuration is intentionally specific: Hyprland and Noctalia,
qutebrowser/mpv integration, local capture and analysis services, explicit
storage/backup policy, and resource-scoped build and agent workflows are part
of the artifact.

Agent and contribution rules live in `CLAUDE.md`; `AGENTS.md` is a symlink to
that same file.
