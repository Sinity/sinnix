# Runtime inventory schema checks for typed effective per-surface policy.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib) evalTestSpec mkFeatureTest;
      spec = mkFeatureTest {
        name = "runtime-surface-policy";
        feature = "sinnix.features.cli.polylogue.enable";
        extraModules = [
          ({ ... }: {
            sinnix.runtime.surfaces = {
              runtime-policy-system = {
                unit = "runtime-policy-system.service";
                resourceClass = "background-maintenance";
                resources = {
                  MemoryMax = "900M";
                  Nice = 7;
                };
              };
              runtime-policy-user = {
                unit = "runtime-policy-user.service";
                manager = "user";
                resourceClass = "desktop-shell";
                resources = {
                  MemoryLow = "768M";
                };
              };
            };
          })
        ];
        assertions = config: [
          {
            assertion =
              config.sinnix.runtime.inventory.surfaces.runtime-policy-system.effectiveResources.MemoryMax
              == "900M";
            message = "system surface overrides must appear in effective runtime policy";
          }
          {
            assertion =
              config.sinnix.runtime.inventory.surfaces.runtime-policy-system.effectiveResources.Nice == 7;
            message = "system surface Nice override must be preserved";
          }
          {
            assertion =
              config.sinnix.runtime.inventory.surfaces.runtime-policy-user.effectiveResources.MemoryLow == "768M";
            message = "user surface overrides must appear in effective runtime policy";
          }
          {
            assertion =
              config.sinnix.runtime.inventory.surfaces.runtime-policy-user.effectiveResources.CPUWeight == 400;
            message = "resource-class defaults must remain under user overrides";
          }
        ];
      };
      evaluated = evalTestSpec system spec;
      inventoryJson = builtins.toJSON evaluated.config.sinnix.runtime.inventory;
    in
    {
      checks.runtime-surface-policy =
        pkgs.runCommand "runtime-surface-policy-check"
          {
            nativeBuildInputs = [ pkgs.jq ];
          }
          ''
            cat > inventory.json <<'EOF_INVENTORY'
            ${inventoryJson}
            EOF_INVENTORY
            jq -e '.surfaces["runtime-policy-system"].effectiveResources.MemoryMax == "900M" and .surfaces["runtime-policy-user"].effectiveResources.MemoryLow == "768M"' inventory.json >/dev/null
            touch "$out"
          '';
    };
}
