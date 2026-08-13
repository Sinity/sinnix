{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      script = ../../scripts/sinnix-capability-manifest;
      source = pkgs.runCommand "capability-manifest-fixture-source" { } ''
        mkdir -p $out/modules/features/desktop $out/modules/services $out/scripts $out/modules \
          $out/hosts/sinnix-ethereal $out/hosts/sinnix-gw $out/flake
        touch $out/modules/features/desktop/example.nix
        touch $out/modules/services/example.nix
        touch $out/scripts/example-tool
        mkdir -p $out/.git
        # Only sinnix-ethereal is a real nixosConfigurations member in this
        # fixture -- sinnix-gw (OpenWrt, no mkHost entry) must NOT surface as a
        # dormant host despite having a hosts/ directory. The real build
        # sandbox's ambient `hostname` never coincides with "sinnix-ethereal",
        # so it deterministically comes out dormant here regardless of host.
        cat > $out/flake/nixos.nix <<'NIX'
        {
          flake.nixosConfigurations = {
            sinnix-ethereal = mkHost { };
          };
        }
        NIX
      '';
      inventory = pkgs.writeText "capability-manifest-fixture-inventory.json" (
        builtins.toJSON {
          schema = "sinnix-runtime-inventory-v1";
          surfaces = {
            "example.service" = {
              unit = "example.service";
              manager = "system";
              kind = "service";
              resourceClass = "system";
              workload = {
                lifecycle = "persistent";
              };
              observe = {
                enable = true;
              };
              captures = [ ];
            };
            "example.socket" = {
              unit = "example.socket";
              manager = "system";
              kind = "socket";
              resourceClass = "system";
              workload = {
                lifecycle = "transient";
              };
              observe = {
                enable = false;
              };
              captures = [ ];
            };
          };
        }
      );
      rendered =
        pkgs.runCommand "capability-manifest-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.findutils
              pkgs.jq
              pkgs.ripgrep
            ];
          }
          ''
            ${pkgs.bash}/bin/bash ${script} --source-root ${source} --inventory ${inventory} --output $out
            ${pkgs.jq}/bin/jq -e '
              .schema == "sinnix-capability-manifest-v1" and
              (.features | length) == 1 and
              (.services | length) == 1 and
              (.scripts | length) == 1 and
              (.runtimeSurfaces | length) == 2 and
              # Derived, not a hardcoded literal -- sinnix-ethereal
              # is the fixtures only real nixosConfigurations member, and
              # sinnix-gw (hosts/ dir, no mkHost entry) must be excluded.
              (.dormantHosts | any(.host == "sinnix-ethereal")) and
              (.dormantHosts | all(.host != "sinnix-gw")) and
              (.dormantHosts | all(has("host") and has("state"))) and
              (.unknowns | length) == 1
            ' $out
          '';
    in
    {
      checks.capability-manifest = pkgs.runCommand "capability-manifest-check" { inherit rendered; } ''
        test -s $rendered
        touch $out
      '';
    };
}
