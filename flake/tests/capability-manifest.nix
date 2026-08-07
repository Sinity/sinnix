{ inputs, ... }:
{
  perSystem = { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      script = ../../scripts/sinnix-capability-manifest;
      source = pkgs.runCommand "capability-manifest-fixture-source" { } ''
        mkdir -p $out/modules/features/desktop $out/modules/services $out/scripts $out/modules $out/hosts
        touch $out/modules/features/desktop/example.nix
        touch $out/modules/services/example.nix
        touch $out/scripts/example-tool
        mkdir -p $out/.git
      '';
      inventory = pkgs.writeText "capability-manifest-fixture-inventory.json" (builtins.toJSON {
        schema = "sinnix-runtime-inventory-v1";
        surfaces = {
          "example.service" = {
            unit = "example.service";
            manager = "system";
            kind = "service";
            resourceClass = "system";
            workload = { lifecycle = "persistent"; };
            observe = { enable = true; };
            captures = [ ];
          };
          "example.socket" = {
            unit = "example.socket";
            manager = "system";
            kind = "socket";
            resourceClass = "system";
            workload = { lifecycle = "transient"; };
            observe = { enable = false; };
            captures = [ ];
          };
        };
      });
      rendered = pkgs.runCommand "capability-manifest-fixture" {
        nativeBuildInputs = [ pkgs.bash pkgs.coreutils pkgs.findutils pkgs.jq pkgs.ripgrep ];
      } ''
        ${pkgs.bash}/bin/bash ${script} --source-root ${source} --inventory ${inventory} --output $out
        ${pkgs.jq}/bin/jq -e '
          .schema == "sinnix-capability-manifest-v1" and
          (.features | length) == 1 and
          (.services | length) == 1 and
          (.scripts | length) == 1 and
          (.runtimeSurfaces | length) == 2 and
          .dormantHosts[0].host == "sinnix-ethereal" and
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
