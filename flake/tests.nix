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
    ./tests/backup.nix
    ./tests/observability.nix
    ./tests/cli.nix
    ./tests/git-languages.nix
    ./tests/vm.nix
    ./tests/host-build.nix
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
