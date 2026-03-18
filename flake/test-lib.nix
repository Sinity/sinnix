# Test Infrastructure Library
#
# Reusable helpers for NixOS configuration tests. Provides:
# - sanitizedInputs: Hermetic input sanitization for reproducible tests
# - mountTmpfsRoots: Mock filesystem roots for test VMs
# - baseTestConfig: Minimal test configuration (no desktop, no secrets)
# - Test DSL helpers for common test patterns
#
# Usage:
#   let testLib = import ./test-lib.nix { inherit inputs lib; };
#   in testLib.mkFeatureTest { ... }
{ inputs, lib }:
let
  libContext = import ./lib-context.nix { inherit inputs; };
  inherit (libContext)
    extendedLib
    mkBaseModules
    mkSharedSpecialArgs
    ;

  # Create a pure flake source for hermetic evaluation
  flakeSource = builtins.path {
    path = ../.;
    name = "sinnix-src";
  };

  # Sanitized inputs replace self with pure path for reproducible tests
  sanitizedInputs = {
    inherit (inputs)
      agenix
      home-manager
      nix-ai-tools
      lynchpin
      reboot-no-more
      sinex
      polylogue
      ;
    inherit (inputs)
      scribe-tap
      intercept-bounce
      stylix
      ;
    inherit (inputs) nix-vscode-extensions disko nixpkgs;
    self = inputs.self // {
      outPath = flakeSource;
    };
  };

  # Base modules required for all tests
  baseModules = (mkBaseModules inputs) ++ [ ../modules/default.nix ];

  # Shared special args for test evaluation
  sharedSpecialArgs = mkSharedSpecialArgs sanitizedInputs;

  # Mock filesystem roots for test VMs (prevents real FS dependencies)
  mountTmpfsRoots =
    { ... }:
    {
      fileSystems."/" = {
        device = "tmpfs";
        fsType = "tmpfs";
      };
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

  # Base test configuration: minimal, no desktop
  baseTestConfig =
    { lib, ... }:
    {
      # Minimal NixOS requirements for evaluation
      boot.loader.grub.enable = false;
      programs.zsh.enable = true;

      sinnix = {
        machine.isDesktop = lib.mkDefault false;
        bundles.desktop.enable = lib.mkDefault false;
      };
    };

  # Create a test for a single feature
  # Example: mkFeatureTest {
  #   name = "dev-shell";
  #   feature = "sinnix.features.dev.shell.enable";
  #   assertions = config: let hm = ... in [ { assertion = ...; message = ...; } ];
  # }
  mkFeatureTest =
    {
      name,
      feature,
      assertions,
      extraModules ? [ ],
    }:
    {
      inherit name;
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = name;
          }
          // lib.setAttrByPath (lib.splitString "." feature) true
        )
      ]
      ++ extraModules;
      inherit assertions;
    };

  # Create a test for a service
  mkServiceTest =
    {
      name,
      service,
      assertions,
      extraModules ? [ ],
    }:
    mkFeatureTest {
      inherit name assertions extraModules;
      feature = "sinnix.services.${service}.enable";
    };

  # Create a test for a bundle
  mkBundleTest =
    {
      name,
      bundle,
      assertions,
      extraModules ? [ ],
    }:
    mkFeatureTest {
      inherit name assertions extraModules;
      feature = "sinnix.bundles.${bundle}.enable";
    };

  # Build a test check derivation from a spec
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
              { config, ... }:
              {
                assertions = spec.assertions config;
              }
            )
          ];
        specialArgs = sharedSpecialArgs // {
          lib = extendedLib;
        };
      };
    in
    pkgs.runCommand "nixos-${spec.name}-config-check"
      {
        # Force evaluation of the NixOS config — this triggers assertion checks.
        # Without this reference, the nixosSystem call is dead code.
        systemDrv = evaluated.config.system.build.toplevel;
      }
      ''
        touch $out
      '';

  # Generate checks for all systems from a list of test specs
  mkSystemChecks =
    system: testSpecs:
    lib.listToAttrs (
      map (spec: {
        name = "nixos-${spec.name}";
        value = mkTestForSystem system spec;
      }) testSpecs
    );

in
{
  inherit sanitizedInputs baseModules sharedSpecialArgs;
  inherit mountTmpfsRoots baseTestConfig;
  inherit mkFeatureTest mkServiceTest mkBundleTest;
  inherit mkTestForSystem mkSystemChecks;
}
