# Noctalia v5 plugin lint and bounded bridge contract.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      noctalia = inputs.noctalia.packages.${system}.default;
    in
    {
      checks.noctalia-ops-bridge =
        pkgs.runCommand "noctalia-ops-bridge-check"
          {
            nativeBuildInputs = [
              noctalia
              pkgs.bash
              pkgs.coreutils
              pkgs.gnugrep
            ];
          }
          ''
            NOCTALIA_OPS_PLUGIN=${../../dots/noctalia/plugins/sinnix-ops} \
              ${pkgs.bash}/bin/bash ${../../flake/tests/noctalia-ops-bridge.sh}
            touch "$out"
          '';
    };
}
