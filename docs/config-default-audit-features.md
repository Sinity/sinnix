# Feature default audit

Audit date: 2026-08-07. Scope: `modules/features/`, the `mkFeatureModule` factory, and the current `sinnix-prime` evaluation.

The factory's top-level feature default is an intentional Sinnix contract: `mkFeatureModule` supplies `enable.default = true`, and the current evaluated feature tree contains 31 user-facing feature options across the CLI, desktop, development, and system subtrees. The audit therefore treats a top-level `enable = true` as policy, not redundant syntax. The composite Hyprland module has its own explicit default-on option and is audited as one desktop feature.

## Matrix

| Subtree | Source declarations reviewed | Effective feature options | Classification | Action |
| --- | ---: | ---: | --- | --- |
| `modules/features/cli` | 7 files | 6 | default-on user surface | Retain. Explicit nested package and shell settings are feature behavior, not factory defaults. |
| `modules/features/desktop` | 25 files | 16 | default-on user surface | Retain. Desktop outputs, dotfile ownership, and physical-display behavior make broad upstream-default comparison unsafe without a generated before/after evaluation. |
| `modules/features/dev` | 14 files | 8 | default-on user surface | Retain. Agent, shell, editor, language, and workbench settings define the workstation contract. |
| `modules/features/system` | 2 files | 1 | default-on system capability | Retain. `nix-ld` is a deliberate compatibility capability, not an upstream default claim. |
| `modules/features/hyprland` composite | 5 files | included in desktop | explicit composite module | Retain. Its module boundary is an established exception and its option default is explicit for the desktop profile. |

## Per-file disposition

Every feature source file was inspected. `default.nix`, helper files, and composite Hyprland files are source wiring rather than independent top-level options. No setting was removed because no candidate had both pinned upstream-default evidence and no Sinnix policy meaning.

| Area | Files |
| --- | --- |
| CLI | `default.nix`, `aichat.nix`, `core.nix`, `image-tools.nix`, `polylogue.nix`, `task-tracking.nix`, `yt-polisher.nix` |
| Desktop | `default.nix`, `activitywatch.nix`, `audio-capture.nix`, `audio.nix`, `base.nix`, `browser.nix`, `common-apps.nix`, `gaming.nix`, `hyprland-animations.nix`, `media.nix`, `mime.nix`, `noctalia.nix`, `storage.nix`, `terminal.nix`, `theming.nix`, `ui.nix` |
| Desktop composite | `hyprland/default.nix`, `hyprland/bindings.nix`, `hyprland/idle.nix`, `hyprland/rules.nix`, `hyprland/scratchpads.nix` |
| Development | `default.nix`, `agents/default.nix`, `agents/backends.nix`, `agents/browser.nix`, `agents/client-profiles.nix`, `agents/clis.nix`, `agents/hooks.nix`, `agents/mcp-tools.nix`, `agents/mcp.nix`, `agents/serena.nix`, `editors.nix`, `git.nix`, `interp-lab.nix`, `languages.nix`, `shell.nix`, `workbench.nix` |
| System | `default.nix`, `nix-ld.nix` |

## Evidence and invariants

- `nix eval --json .#nixosConfigurations.sinnix-prime.config.sinnix.features` returned the four expected subtrees. The evaluated tree contained 31 feature options and 50 nested boolean values set true, with the false values belonging to explicit feature-local choices.
- The `mkFeatureModule` implementation in `modules/lib/features.nix` rejects caller-defined top-level `enable`, preserving one default-on authority and preventing silent option shadowing.
- The feature audit makes no dotfile ownership changes. Noctalia, Kitty, shell, agent, and Hyprland files remain repository-owned through the existing Home Manager out-of-store path.
- Default-valued cleanup remains separate from behavior changes. Any future deletion must capture evaluated option metadata, compare generated Home Manager and desktop output, and retain the change only when the result is byte-equivalent or the intended policy is explicitly preserved.

## Verification boundary

The CLI and Noctalia focused checks are the relevant executable feature checks. This audit records no speculative deletion, so it does not claim that a source-text absence proves behavior. The parent `sinnix-ow0` still owns the broader module-tree audit and final check gate.
