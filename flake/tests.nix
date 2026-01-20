{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
  systems = [ "x86_64-linux" ];
  featureLib = import ../modules/lib/features.nix { inherit lib; };
  flakeSource = builtins.path {
    path = ../.;
    name = "sinnix-src";
  };
  sanitizedInputs = {
    agenix = inputs.agenix;
    home-manager = inputs.home-manager;
    nix-ai-tools = inputs.nix-ai-tools;
    sinex = inputs.sinex;
    polylogue = inputs.polylogue;
    scribe-tap = inputs.scribe-tap;
    intercept-bounce = inputs.intercept-bounce;
    devenv = inputs.devenv;
    nur = inputs.nur;
    stylix = inputs.stylix;
    nix-vscode-extensions = inputs.nix-vscode-extensions;
    disko = inputs.disko;
    nixpkgs = inputs.nixpkgs;
    self = flakeSource;
  };
  baseModules = [
    inputs.agenix.nixosModules.default
    inputs.stylix.nixosModules.stylix
    inputs.sinex.nixosModules.default
    (import ./overlay { inherit inputs; })
    ../modules/default.nix
  ];
  sharedSpecialArgs = {
    inputs = sanitizedInputs;
    inherit (featureLib) mkFeatureModule;
    helpers = {
      inherit (featureLib) mkDotsSymlink;
    };
  };

  mountTmpfsRoots =
    { config, ... }:
    {
      fileSystems."/realm" = {
        device = "tmpfs";
        fsType = "tmpfs";
        neededForBoot = true;
      };
      fileSystems."/outer-realm" = {
        device = "tmpfs";
        fsType = "tmpfs";
        neededForBoot = true;
      };
    };

  testSpecs = [
    {
      name = "dev-shell";
      modules = [
        mountTmpfsRoots
        (
          {
            ...
          }:
          {
            networking.hostName = "dev-shell";
            sinnix = {
              machine.isDesktop = false;
              secrets.enable = false;
              bundles.desktop.enable = false;
              bundles.dev.enable = true;
              services.asciinema.enable = true;
              features = {
                dev.shell.enable = true;
                cli.asciinema.enable = true;
              };
            };
          }
        )
      ];
      assertions = config:
        let
          user = config.sinnix.user.name;
        in
        [
          {
            assertion = config.home-manager.users.${user}.programs.zsh.enable;
            message = "Zsh must be enabled for the primary user.";
          }
          {
            assertion = config.home-manager.users.${user}.programs.starship.enable;
            message = "Starship prompt must be enabled in the dev shell.";
          }
          {
            assertion = config.home-manager.users.${user}.home.file ? ".local/bin/claude";
            message = "Claude CLI wrapper must be provisioned in the dev shell.";
          }
        ];
    }
    {
      name = "services-transmission";
      modules = [
        mountTmpfsRoots
        (
          {
            ...
          }:
          {
            networking.hostName = "services";
            sinnix = {
              machine.isDesktop = false;
              secrets.enable = false;
              bundles.desktop.enable = false;
              bundles.dev.enable = true;
              services = {
                transmission.enable = true;
                asciinema.enable = true;
              };
            };
          }
        )
      ];
      assertions = config: [
        {
          assertion = config.services.transmission.enable;
          message = "Transmission service should be enabled.";
        }
        {
          assertion = config.systemd.services.transmission.serviceConfig.RequiresMountsFor != [ ];
          message = "Transmission service must declare required mounts.";
        }
        {
          assertion = builtins.any (
            rule: builtins.match ".*captures/asciinema.*" rule != null
          ) config.systemd.tmpfiles.rules;
          message = "Asciinema captures directory tmpfiles entry missing.";
        }
      ];
    }
  ];

  mkTestForSystem =
    system: spec:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      evaluated = lib.nixosSystem {
        inherit system;
        modules =
          baseModules
          ++ spec.modules
          ++ [
            (
              {
                config,
                lib,
                ...
              }:
              {
                assertions = spec.assertions config;
              }
            )
          ];
        specialArgs = sharedSpecialArgs;
      };
    in
    pkgs.runCommand "nixos-${spec.name}-config-check" { } ''
      touch $out
    '';

  mkSystemChecks =
    system:
    lib.listToAttrs (
      map (spec: {
        name = "nixos-${spec.name}";
        value = mkTestForSystem system spec;
      }) testSpecs
    );
in
{
  perSystem =
    { system, ... }:
    {
      checks = mkSystemChecks system;
    };

  flake.nixosTests = lib.listToAttrs (
    map (spec: {
      name = spec.name;
      value = lib.genAttrs systems (system: mkTestForSystem system spec);
    }) testSpecs
  );
}
