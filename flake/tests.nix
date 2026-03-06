# Config Assertion Tests
#
# Fast tests that verify NixOS configurations evaluate correctly.
# No VM boot - just checks that options are set as expected.
#
# Run all: nix flake check
# Run one: nix build .#checks.x86_64-linux.nixos-dev-shell
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;

  # Import test infrastructure
  testLib = import ./test-lib.nix { inherit inputs lib; };
  inherit (testLib)
    mountTmpfsRoots
    baseTestConfig
    mkFeatureTest
    mkServiceTest
    mkBundleTest
    mkSystemChecks
    ;

  # Helper to get HM config for assertions
  hmFor = config: config.home-manager.users.${config.sinnix.user.name};

  testSpecs = [
    # === Feature Tests (using DSL) ===
    (mkFeatureTest {
      name = "dev-shell";
      feature = "sinnix.features.dev.shell.enable";
      assertions =
        config:
        let
          hm = hmFor config;
        in
        [
          {
            assertion = hm.programs.zsh.enable;
            message = "Zsh must be enabled";
          }
          {
            assertion = hm.programs.starship.enable;
            message = "Starship must be enabled";
          }
          {
            assertion = hm.programs.atuin.enable;
            message = "Atuin must be enabled";
          }
          {
            assertion = hm.programs.fzf.enable;
            message = "FZF must be enabled";
          }
          {
            assertion = hm.programs.zoxide.enable;
            message = "Zoxide must be enabled";
          }
          {
            assertion = hm.home.file ? ".local/bin/claude";
            message = "Claude wrapper must exist";
          }
          {
            assertion = hm.home.file ? ".local/bin/codex";
            message = "Codex wrapper must exist";
          }
          {
            assertion = hm.xdg.configFile ? "claude/skills";
            message = "Claude skills symlink must exist";
          }
          {
            assertion = hm.home.activation ? renderGlobalCodexAgents;
            message = "Global Codex AGENTS render activation must exist";
          }
        ];
    })

    (mkFeatureTest {
      name = "dev-git";
      feature = "sinnix.features.dev.git.enable";
      assertions =
        config:
        let
          hm = hmFor config;
        in
        [
          {
            assertion = hm.programs.git.enable;
            message = "Git must be enabled";
          }
          {
            assertion = hm.programs.delta.enable;
            message = "Delta must be enabled";
          }
        ];
    })

    (mkFeatureTest {
      name = "dev-mcp-servers";
      feature = "sinnix.features.dev.mcp-servers.enable";
      assertions =
        config:
        let
          hm = hmFor config;
        in
        [
          {
            assertion = hm.home.file ? ".codex/config.toml";
            message = "Codex config must be linked";
          }
          {
            assertion = hm.home.file ? ".codex/skills";
            message = "Codex skills must be linked from shared agent-skills";
          }
        ];
    })

    (mkFeatureTest {
      name = "desktop-hyprland";
      feature = "sinnix.features.desktop.hyprland.enable";
      extraModules = [
        (
          { lib, ... }:
          {
            hardware.graphics.enable = lib.mkForce false;
          }
        )
      ];
      assertions = config: [
        {
          assertion = config.programs.hyprland.enable;
          message = "Hyprland must be enabled";
        }
        {
          assertion = config.programs.hyprland.withUWSM;
          message = "UWSM must be enabled";
        }
      ];
    })

    # === Service Tests (using DSL) ===
    (mkServiceTest {
      name = "services-below";
      service = "below";
      assertions = config: [
        {
          assertion = config.systemd.services ? below;
          message = "Below service must exist";
        }
        {
          assertion = config.environment.systemPackages != [ ];
          message = "Below package must be installed";
        }
      ];
    })

    (mkServiceTest {
      name = "services-power-watchdog";
      service = "power-watchdog";
      assertions = config: [
        {
          assertion = config.systemd.services ? power-watchdog;
          message = "power-watchdog service must exist";
        }
      ];
    })

    (mkServiceTest {
      name = "services-transmission";
      service = "transmission";
      assertions = config: [
        {
          assertion = config.services.transmission.enable;
          message = "Transmission must be enabled";
        }
        {
          assertion = config.systemd.services.transmission.unitConfig ? RequiresMountsFor;
          message = "Transmission must declare required mounts";
        }
      ];
    })

    (mkServiceTest {
      name = "services-terminal-capture";
      service = "terminal-capture";
      assertions = config: [
        {
          assertion = builtins.any (
            rule: builtins.match ".*captures/asciinema.*" rule != null
          ) config.systemd.tmpfiles.rules;
          message = "Asciinema captures directory tmpfiles entry must exist";
        }
      ];
    })

    (mkServiceTest {
      name = "services-sentinel";
      service = "sentinel";
      assertions = config: [
        {
          assertion = config.systemd.services ? sinnix-sentinel;
          message = "sinnix-sentinel oneshot service must exist";
        }
        {
          assertion = config.systemd.timers ? sinnix-sentinel;
          message = "sinnix-sentinel timer must exist";
        }
        {
          assertion = config.environment.etc ? "sinnix/health-policy.json";
          message = "health-policy.json must be generated (from introspection.nix)";
        }
        {
          assertion = config.environment.etc ? "sinnix/config.json";
          message = "config.json must be generated (from introspection.nix)";
        }
        {
          assertion = builtins.any (
            rule: builtins.match ".*sinnix-sentinel.*" rule != null
          ) config.systemd.tmpfiles.rules;
          message = "sentinel event log directory must be created via tmpfiles";
        }
      ];
    })

    # Note: sinex service test omitted — sinex requires PostgreSQL, TLS certs,
    # and agenix secrets which are too heavyweight for config-only assertion tests.
    # The sinex service is verified via the full sinnix-prime build.

    # === Bundle Tests (using DSL) ===
    (mkBundleTest {
      name = "bundle-dev";
      bundle = "dev";
      assertions =
        config:
        let
          hm = hmFor config;
        in
        [
          {
            assertion = hm.programs.zsh.enable;
            message = "Dev bundle must enable zsh";
          }
          {
            assertion = hm.programs.git.enable;
            message = "Dev bundle must enable git";
          }
          {
            assertion = hm.programs.tmux.enable;
            message = "Dev bundle must enable tmux";
          }
        ];
    })

    (mkBundleTest {
      name = "bundle-desktop";
      bundle = "desktop";
      extraModules = [
        (
          { lib, pkgs, ... }:
          {
            hardware.graphics.enable = lib.mkForce false;
            # Provide dummy graphics package for headless test evaluation
            hardware.graphics.package = lib.mkForce pkgs.mesa;
            hardware.graphics.package32 = lib.mkForce pkgs.pkgsi686Linux.mesa;
          }
        )
      ];
      assertions = config: [
        {
          assertion = config.programs.hyprland.enable or false;
          message = "Desktop must enable hyprland";
        }
        {
          assertion = config.services.pipewire.enable or false;
          message = "Desktop must enable audio";
        }
      ];
    })

    # === Manual Tests (need custom module logic) ===
    {
      name = "minimal-no-features";
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = "minimal";
            sinnix.bundles.dev.enable = false;
          }
        )
      ];
      assertions =
        config:
        let
          hm = hmFor config;
        in
        [
          {
            assertion = !(hm.programs.starship.enable or false);
            message = "Starship should not be enabled in minimal";
          }
          {
            assertion = !(config.services.transmission.enable or false);
            message = "Transmission should not be enabled in minimal";
          }
        ];
    }

    {
      name = "paths-configured";
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = "paths-test";
          }
        )
      ];
      assertions = config: [
        {
          assertion = config.sinnix.paths.realmRoot == "/realm";
          message = "realmRoot must be /realm";
        }
        {
          assertion = config.sinnix.paths.dataRoot == "/realm/data";
          message = "dataRoot must be /realm/data";
        }
        {
          assertion = config.sinnix.paths.capturesRoot == "/realm/data/captures";
          message = "capturesRoot must be correct";
        }
        {
          assertion = config.sinnix.user.name == "sinity";
          message = "Default user must be sinity";
        }
      ];
    }

    # === Password/Secrets Safety Tests ===
    {
      name = "password-secrets-wiring";
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = "password-test";
          }
        )
      ];
      assertions = config: [
        {
          assertion = config.users.mutableUsers == false;
          message = "mutableUsers must be false (declarative passwords)";
        }
        {
          assertion = config.users.users.${config.sinnix.user.name} ? hashedPasswordFile;
          message = "User must have hashedPasswordFile set (not inline hash)";
        }
        {
          assertion = config.users.users.root ? hashedPasswordFile;
          message = "Root must have hashedPasswordFile set (not inline hash)";
        }
        {
          assertion =
            config.users.users.${config.sinnix.user.name}.hashedPasswordFile
            == config.sinnix.secrets.paths."${config.sinnix.user.name}-password";
          message = "User password file must point to agenix secret path";
        }
        {
          assertion = config.users.users.root.hashedPasswordFile == config.sinnix.secrets.paths.root-password;
          message = "Root password file must point to agenix secret path";
        }
        {
          assertion = config.system.activationScripts ? passwordSafetyNet;
          message = "Password safety net activation script must exist";
        }
        {
          assertion = config.age.secrets ? "${config.sinnix.user.name}-password";
          message = "Agenix must have user password secret configured";
        }
        {
          assertion = config.age.secrets ? "root-password";
          message = "Agenix must have root password secret configured";
        }
      ];
    }

    # === Router Config Tests ===
    # Verify sinnix-gw OpenWrt config evaluates without errors
    # (no NixOS VM needed — just checks the Nix expressions)
    {
      name = "router-config-evaluates";
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = "router-test";
          }
        )
      ];
      assertions =
        _config:
        let
          routerCfg = import ../hosts/sinnix-gw/default.nix { inherit lib; };
          openwrtLib = import ../modules/lib/openwrt.nix { inherit lib; };
          uciScript = openwrtLib.mkUciScript routerCfg.uci;
          pkgScript = openwrtLib.mkOpkgScript routerCfg.packages;

          # Helper: check if string contains a substring
          contains = haystack: needle: builtins.match ".*${lib.escapeRegex needle}.*" haystack != null;
          # Helper: check if string matches regex (multiline via [\s\S])
          matchesRegex = haystack: regex: builtins.match regex haystack != null;
        in
        [
          # ── Basic metadata ──
          {
            assertion = routerCfg.hostname == "sinnix-gw";
            message = "Router hostname must be sinnix-gw";
          }
          {
            assertion = routerCfg.address == "192.168.1.1";
            message = "Router address must be 192.168.1.1";
          }
          {
            assertion = builtins.length routerCfg.packages > 0;
            message = "Router must have packages to install";
          }
          {
            assertion = builtins.stringLength uciScript > 100;
            message = "UCI script must generate non-trivial output";
          }
          {
            assertion = builtins.stringLength pkgScript > 10;
            message = "Package script must generate output";
          }
          {
            assertion = builtins.stringLength routerCfg.postCommands > 100;
            message = "Post-commands must be non-empty";
          }

          # ── Ash compatibility (no pipefail) ──
          {
            assertion = !(contains uciScript "pipefail");
            message = "UCI script must not contain pipefail (ash incompatible)";
          }
          {
            assertion = !(contains pkgScript "pipefail");
            message = "Package script must not contain pipefail (ash incompatible)";
          }

          # ── UCI script is a fragment (no embedded shebang) ──
          {
            assertion = !(contains uciScript "#!/bin/sh");
            message = "UCI script must not contain shebang (it's a fragment, not standalone)";
          }

          # ── Critical UCI sections exist ──
          {
            assertion = contains uciScript "network.lan=";
            message = "UCI script must configure LAN interface";
          }
          {
            assertion = contains uciScript "network.wan=";
            message = "UCI script must configure WAN interface";
          }
          {
            assertion = contains uciScript "wireless.radio0=";
            message = "UCI script must configure radio0 (2.4GHz)";
          }
          {
            assertion = contains uciScript "wireless.radio1=";
            message = "UCI script must configure radio1 (5GHz)";
          }
          {
            assertion = contains uciScript "sqm.wan_qos=";
            message = "UCI script must configure SQM";
          }
          {
            assertion = contains uciScript "firewall.defaults=";
            message = "UCI script must configure firewall defaults";
          }
          {
            assertion = contains uciScript "dhcp.dnsmasq=";
            message = "UCI script must configure dnsmasq";
          }

          # ── UCI commit commands present ──
          {
            assertion = contains uciScript "uci commit network";
            message = "UCI script must commit network package";
          }
          {
            assertion = contains uciScript "uci commit wireless";
            message = "UCI script must commit wireless package";
          }
          {
            assertion = contains uciScript "uci commit firewall";
            message = "UCI script must commit firewall package";
          }

          # ── postCommands content ──
          {
            assertion = contains routerCfg.postCommands "authorized_keys";
            message = "Post-commands must deploy SSH authorized key";
          }
          {
            assertion = contains routerCfg.postCommands "https-dns-proxy";
            message = "Post-commands must configure https-dns-proxy (DoH)";
          }
          {
            assertion = contains routerCfg.postCommands "network reload";
            message = "Post-commands must reload network";
          }
          {
            assertion = contains routerCfg.postCommands "nf_conntrack_max";
            message = "Post-commands must tune conntrack table";
          }
        ];
    }

    # === Backup Tests ===
    {
      name = "backup-btrbk";
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = "backup-test";
          }
        )
      ];
      assertions =
        config:
        let
          hasConf = config.environment.etc ? "btrbk/btrbk.conf";
          conf = if hasConf then config.environment.etc."btrbk/btrbk.conf".text else "";
        in
        [
          # Core service
          {
            assertion = config.systemd.services ? btrbk;
            message = "btrbk service must exist";
          }
          {
            assertion = config.systemd.timers ? btrbk;
            message = "btrbk timer must exist";
          }
          # Config deployed
          {
            assertion = hasConf;
            message = "btrbk config must be deployed to /etc";
          }
          # Config contains correct paths (guarded — conf is "" if etc file missing)
          {
            assertion = hasConf && builtins.match ".*volume /realm.*" conf != null;
            message = "btrbk config must include /realm volume";
          }
          {
            assertion = hasConf && builtins.match ".*volume /neo-outer-realm.*" conf != null;
            message = "btrbk config must include neo-outer-realm volume";
          }
          {
            assertion = hasConf && builtins.match ".*volume /\n.*" conf != null;
            message = "btrbk config must include root volume for rollback snapshots";
          }
          # Retention policy present
          {
            assertion = hasConf && builtins.match ".*snapshot_preserve.*14d.*52w.*" conf != null;
            message = "btrbk config must include long-horizon daily/weekly retention";
          }
          # Snapshot dirs created by tmpfiles
          {
            assertion = builtins.any (
              rule: builtins.match ".*\\.snapshot.*" rule != null
            ) config.systemd.tmpfiles.rules;
            message = "Snapshot directories must be created via tmpfiles";
          }
        ];
    }
  ];

in
{
  perSystem =
    { system, ... }:
    {
      checks = mkSystemChecks system testSpecs;
    };
}
