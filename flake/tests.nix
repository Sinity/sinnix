# Test director.
#
# Runtime/VM/host build checks live in `./tests-runtime.nix`. This file keeps
# only non-config-duplication flake checks.
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
    ./tests-runtime.nix
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
