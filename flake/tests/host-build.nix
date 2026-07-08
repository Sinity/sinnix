# Full host toplevel build checks (sinnix-prime, sinnix-ethereal).
#
# Split out of the former flake/tests-runtime.nix monolith (sinnix-7bu).
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib) mkHostBuildCheck;

      hostBuildChecks = lib.optionalAttrs (system == "x86_64-linux") {
        host-sinnix-prime-build = mkHostBuildCheck system {
          name = "sinnix-prime";
          modules = [
            { imports = [ ../../hosts/sinnix-prime ]; }
          ];
        };
        host-sinnix-ethereal-build = mkHostBuildCheck system {
          name = "sinnix-ethereal";
          modules = [
            inputs.disko.nixosModules.disko
            { imports = [ ../../hosts/sinnix-ethereal ]; }
          ];
        };
      };
    in
    {
      heavyChecks = hostBuildChecks;
    };
}
