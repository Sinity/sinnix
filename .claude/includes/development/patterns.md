## Module Development Patterns

### Boilerplate

#### Feature Module

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

#### Service Module

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

### Architectural Patterns

| Pattern                    | Location                    | Purpose                                                                    |
| -------------------------- | --------------------------- | -------------------------------------------------------------------------- |
| **Module Factories**       | `lib/features.nix`          | `mkFeatureModule`, `mkServiceModule` — eliminate option/config scaffolding |
| **DSLs**                   | `lib/hyprland-rules.nix`    | `mkRule`, `mkScratchpad` → transform declarative data to config syntax     |
| **Systemd Hardening**      | `lib/systemd-hardening.nix` | `mkHardenedService { level = "strict" }` — preset security profiles        |
| **Bundles**                | `bundles/*.nix`             | Pure composition — only enable other features, no direct config            |
| **Out-of-Store Symlinks**  | `lib/features.nix`          | `mkDotsFile` — instant dotfile propagation without rebuild                 |
| **Conditional Merge**      | `services/sinex.nix`        | `lib.mkMerge [ base (lib.mkIf cond extra) ]` — layered composition         |
| **Config Assertion Tests** | `flake/tests.nix`           | Fast checks via `assertions` — no VM boot, just evaluation                 |
| **Package Registry**       | `flake/packages.nix`        | Centralize custom scripts with `writeShellApplication`                     |
| **Input Sanitization**     | `flake/tests.nix`           | `sanitizedInputs` — clone inputs with `self` as path for hermetic tests    |
| **Mount Mocking**          | `flake/tests.nix`           | `mountTmpfsRoots` — simulate `/realm` in tests without real FS             |

---

### Conditional Merge (most versatile)

When a module has multiple activation paths:

```nix
config = lib.mkMerge [
  { /* always applied */ }
  (lib.mkIf condA { /* only if A */ })
  (lib.mkIf condB { /* only if B */ })
];
```

Example: sinex has db-only provisioning vs full service mode.

---

### Layered Abstraction (the pyramid)

```
Host config → Bundle → Feature → lib helper
   (what)      (preset)  (how)    (util)
```

Each layer focuses on one job:

- **Hosts** say "desktop" or "server"
- **Bundles** wire related features together
- **Features** implement user-facing capabilities
- **Libs** provide building blocks

---

### Hermetic Testing

Three-part pattern for isolated test evaluation:

1. **`sanitizedInputs`** — Replace `self` with pure path (`builtins.path`)
2. **`mountTmpfsRoots`** — Mock filesystem expectations via tmpfs
3. **`baseTestConfig`** — Disable desktop/secrets for minimal isolated tests
