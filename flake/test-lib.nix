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
  featureLib = import ../modules/lib/features.nix { inherit lib; };
  overlayLib = import ../modules/lib/overlay-helpers.nix { inherit lib; };

  # Create a pure flake source for hermetic evaluation
  flakeSource = builtins.path {
    path = ../.;
    name = "sinnix-src";
  };

  # Sanitized inputs replace self with pure path for reproducible tests
  sanitizedInputs = {
    inherit (inputs) agenix home-manager nix-ai-tools sinex polylogue;
    inherit (inputs) scribe-tap intercept-bounce devenv nur stylix;
    inherit (inputs) nix-vscode-extensions disko nixpkgs;
    self = flakeSource;
  };

  # Base modules required for all tests
  baseModules = [
    inputs.agenix.nixosModules.default
    inputs.stylix.nixosModules.stylix
    inputs.sinex.nixosModules.default
    inputs.polylogue.nixosModules.default
    (import ./overlay { inherit inputs overlayLib; })
    ../modules/default.nix
  ];

  # Shared special args for test evaluation
  sharedSpecialArgs = {
    inputs = sanitizedInputs;
    inherit (featureLib) mkFeatureModule mkServiceModule;
    helpers = {
      inherit (featureLib) mkDotsLink mkDotsFile;
    };
  };

  # Mock filesystem roots for test VMs (prevents real FS dependencies)
  mountTmpfsRoots = { config, ... }: {
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

  # Base test configuration: minimal, no desktop, no secrets
  baseTestConfig = { ... }: {
    sinnix = {
      machine.isDesktop = false;
      secrets.enable = false;
      bundles.desktop.enable = false;
    };
  };

  # Create a test for a single feature
  # Example: mkFeatureTest {
  #   name = "dev-shell";
  #   feature = "sinnix.features.dev.shell.enable";
  #   assertions = config: let hm = ... in [ { assertion = ...; message = ...; } ];
  # }
  mkFeatureTest = { name, feature, assertions, extraModules ? [] }:
    {
      inherit name;
      modules = [
        mountTmpfsRoots
        baseTestConfig
        ({ ... }: {
          networking.hostName = name;
        } // lib.setAttrByPath (lib.splitString "." feature) true)
      ] ++ extraModules;
      inherit assertions;
    };

  # Create a test for a service
  mkServiceTest = { name, service, assertions, extraModules ? [] }:
    mkFeatureTest {
      inherit name assertions extraModules;
      feature = "sinnix.services.${service}.enable";
    };

  # Create a test for a bundle
  mkBundleTest = { name, bundle, assertions, extraModules ? [] }:
    mkFeatureTest {
      inherit name assertions extraModules;
      feature = "sinnix.bundles.${bundle}.enable";
    };

  # Build a test check derivation from a spec
  mkTestForSystem = system: spec:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      evaluated = lib.nixosSystem {
        inherit system;
        modules = baseModules ++ spec.modules ++ [
          ({ config, lib, ... }: {
            assertions = spec.assertions config;
          })
        ];
        specialArgs = sharedSpecialArgs;
      };
    in
    pkgs.runCommand "nixos-${spec.name}-config-check" { } ''
      touch $out
    '';

  # Generate checks for all systems from a list of test specs
  mkSystemChecks = system: testSpecs:
    lib.listToAttrs (map (spec: {
      name = "nixos-${spec.name}";
      value = mkTestForSystem system spec;
    }) testSpecs);

in
{
  inherit sanitizedInputs baseModules sharedSpecialArgs;
  inherit mountTmpfsRoots baseTestConfig;
  inherit mkFeatureTest mkServiceTest mkBundleTest;
  inherit mkTestForSystem mkSystemChecks;
}
