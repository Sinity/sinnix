# Test director.
#
# Runtime/VM/host build checks live in `./tests/<domain>.nix`, one file per
# logical domain (agent-tools, terminal-capture, backup, observability, cli,
# git-languages, vm, host-build). This file keeps only non-config-duplication
# flake checks plus the transposed `heavyChecks` option definition, and
# imports every domain file so their `checks`/`heavyChecks` contributions
# merge into the flake's outputs.
#
# Run all: nix flake check
# Run one: nix build .#checks.x86_64-linux.router-config-build
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
  pkgsFor = system: inputs.nixpkgs.legacyPackages.${system};
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
    ./tests/agent-tools.nix
    ./tests/terminal-capture.nix
    ./tests/capture-clipboard.nix
    ./tests/capture-primary.nix
    ./tests/backup.nix
    ./tests/agent-environment.nix
    ./tests/agent-parity.nix
    ./tests/swarm-fixture.nix
    ./tests/observability.nix
    ./tests/cli.nix
    ./tests/git-languages.nix
    ./tests/polylogue.nix
    ./tests/vm.nix
    ./tests/host-build.nix
    ./tests/runtime.nix
    ./tests/health-sentinel.nix
    ./tests/capability-manifest.nix
    ./tests/ops-reducer.nix
    ./tests/quota.nix
    ./tests/noctalia.nix
    ./tests/memory-audit.nix
    ./tests/sinex-nats-security.nix
  ];

  perSystem =
    { system, ... }:
    let
      pkgs = pkgsFor system;
      routerFlake = import ./router.nix { inherit inputs; };
      routerPerSystem = routerFlake.perSystem {
        inherit pkgs lib system;
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
      checks = routerBuildChecks;

      heavyChecks = { };
    };
}
