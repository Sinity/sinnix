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
  ];

in
{
  perSystem =
    { system, ... }:
    {
      checks = mkSystemChecks system testSpecs;
    };
}
