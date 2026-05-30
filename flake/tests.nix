# Test director.
#
# Discovers `*.test.nix` specs co-located with the modules they exercise,
# routes them into the default and heavy check tiers, and wires up the
# router-config build check plus coverage manifest. Heavyweight runtime/VM/
# host build checks live in `./tests-runtime.nix` so this file stays narrow.
#
# Run all: nix flake check
# Run one: nix build .#checks.x86_64-linux.nixos-dev-shell
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
  pkgsFor = system: inputs.nixpkgs.legacyPackages.${system};
  coverage = import ./test-coverage.nix;
  checkTiers = import ./check-tiers.nix { inherit lib; };
  testDiscovery = import ./test-discovery.nix { inherit lib; };

  mkSpecChecks =
    system:
    let
      testLib = import ./test-lib.nix { inherit inputs lib; };
      inherit (testLib)
        mountTmpfsRoots
        baseTestConfig
        expect
        mkFeatureTest
        mkServiceTest
        mkSystemChecks
        hmFor
        sanitizedInputs
        ;

      hasCoverageLayer = layer: entry: builtins.elem layer (entry.layers or [ ]);
      smokeName = subject: "smoke-" + lib.replaceStrings [ "." ] [ "-" ] subject;
      semanticFeatureSubjects = checkTiers.semanticFeatureSubjects;
      semanticServiceSubjects = checkTiers.semanticServiceSubjects;

      desktopSmokeBaseline = {
        sinnix.machine.isDesktop = true;
        sinnix.features.desktop.ui.enable = lib.mkDefault true;
      };
      mkFeatureSmokeSpec =
        subject:
        mkFeatureTest {
          name = smokeName subject;
          feature = "sinnix.features.${subject}.enable";
          extraModules = lib.optionals (lib.hasPrefix "desktop." subject) [
            ({ ... }: desktopSmokeBaseline)
          ];
          assertions = _config: [ ];
        };
      mkServiceSmokeSpec =
        subject:
        mkServiceTest {
          name = smokeName subject;
          service = subject;
          assertions = _config: [ ];
        };
      coverageFeatureSmokeSpecs = map mkFeatureSmokeSpec (
        builtins.filter (
          subject:
          hasCoverageLayer "eval" coverage.features.${subject}
          && !(builtins.elem subject semanticFeatureSubjects)
        ) (builtins.attrNames coverage.features)
      );
      coverageServiceSmokeSpecs = map mkServiceSmokeSpec (
        builtins.filter (
          subject:
          hasCoverageLayer "eval" coverage.services.${subject}
          && !(builtins.elem subject semanticServiceSubjects)
        ) (builtins.attrNames coverage.services)
      );

      manualTestSpecs = testDiscovery.discoverTestSpecs {
        roots = [
          ../modules
          ../hosts
          ./.
        ];
        helpers = {
          inherit
            lib
            expect
            mkFeatureTest
            mkServiceTest
            hmFor
            mountTmpfsRoots
            baseTestConfig
            ;
          inputs = sanitizedInputs;
        };
      };

      specByName = lib.listToAttrs (
        map (spec: {
          name = spec.name;
          value = spec;
        }) (manualTestSpecs ++ coverageFeatureSmokeSpecs ++ coverageServiceSmokeSpecs)
      );
      selectSpecs = names: map (name: specByName.${name}) names;
    in
    {
      default = mkSystemChecks system (selectSpecs checkTiers.defaultSpecNames);
      heavy = mkSystemChecks system (selectSpecs checkTiers.heavySpecNames);
    };
in
{
  imports = [
    (inputs.flake-parts.lib.mkTransposedPerSystemModule {
      name = "heavyChecks";
      option = lib.mkOption {
        type = lib.types.lazyAttrsOf lib.types.package;
        default = { };
        description = "Heavy non-default check derivations that are intentionally excluded from nix flake check.";
      };
      file = ./tests.nix;
    })
    ./tests-runtime.nix
  ];

  perSystem =
    { system, ... }:
    let
      pkgs = pkgsFor system;
      testLib = import ./test-lib.nix { inherit inputs lib; };
      specCheckSets = mkSpecChecks system;
      inherit (testLib)
        autoDiscoveredCoverageSurfaces
        mkCoverageManifestCheck
        ;
      routerFlake = import ./router.nix { inherit inputs; };
      routerPerSystem = routerFlake.perSystem {
        inherit pkgs lib system;
      };
      availableDefaultCheckNames =
        map (name: "nixos-${name}") checkTiers.defaultSpecNames ++ checkTiers.defaultAuxCheckNames;
      availableHeavyCheckNames =
        map (name: "nixos-${name}") checkTiers.heavySpecNames
        ++ checkTiers.runtimeCheckNames
        ++ lib.optionals pkgs.stdenv.hostPlatform.isLinux checkTiers.vmCheckNames
        ++ lib.optionals (system == "x86_64-linux") checkTiers.hostBuildCheckNames;
      hostCommandNames = [
        "check-all"
        "check-heavy"
        "host-smoke-all"
        "host-smoke-terminal"
        "host-smoke-services"
      ];
      coverageEvidence = {
        features = {
          "cli.polylogue".runtime = [ "cli-polylogue-runtime" ];
          "cli.task-tracking".runtime = [ "cli-task-tracking-runtime" ];
          "desktop.terminal" = {
            runtime = [ "terminal-capture-runtime" ];
            pty = [ "terminal-capture-runtime" ];
            host = [ "host-smoke-terminal" ];
          };
          "dev.git".runtime = [ "dev-git-runtime" ];
          "dev.languages".runtime = [ "dev-languages-runtime" ];
          "dev.agentTools" = {
            runtime = [ "dev-agent-tools-runtime" ];
            pty = [ "dev-agent-tools-pty" ];
            host = [ "host-smoke-terminal" ];
          };
          "dev.mcp-servers".runtime = [ "dev-agent-tools-runtime" ];
        };
        services = {
          "below".vm = [ "below-vm" ];
          "machine-telemetry".host = [ "host-smoke-services" ];
          "polylogue".vm = [ "polylogue-vm" ];
          "sinex".build = [ "host-sinnix-prime-build" ];
          "terminal-capture" = {
            runtime = [
              "terminal-capture-runtime"
              "terminal-capture-runtime-failure"
            ];
            pty = [ "terminal-capture-runtime" ];
          };
          "transmission".vm = [ "transmission-vm" ];
        };
        hosts = {
          "sinnix-prime" = {
            build = [ "host-sinnix-prime-build" ];
            host = [ "host-smoke-all" ];
          };
          "sinnix-ethereal".build = [ "host-sinnix-ethereal-build" ];
        };
        outputs = {
          "router-config" = {
            eval = [ "nixos-router-config-evaluates" ];
            build = [ "router-config-build" ];
          };
        };
      };
      coverageManifest = mkCoverageManifestCheck system {
        name = "coverage-manifest";
        inherit coverage;
        discovered = autoDiscoveredCoverageSurfaces;
        evidence = coverageEvidence;
        availableChecks = availableDefaultCheckNames ++ availableHeavyCheckNames;
        availableCommands = hostCommandNames;
      };
      routerBuildChecks = {
        router-config-build =
          pkgs.runCommand "router-config-build-check"
            {
              routerConfig = routerPerSystem.packages.router-config;
            }
            ''
              touch "$out"
            '';
      };
    in
    {
      checks =
        specCheckSets.default
        // {
          coverage-manifest = coverageManifest;
        }
        // routerBuildChecks;

      heavyChecks = specCheckSets.heavy;
    };
}
