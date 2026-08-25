{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    {
      checks.lane-toolbelt =
        pkgs.runCommand "lane-toolbelt-check"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.git
              pkgs.gnugrep
            ];
          }
          ''
            lane="$TMPDIR/lane"
            cp ${../../dots/_ai/skills/agent-runtime/scripts/lane} "$lane"
            patchShebangs "$lane"
            chmod +x "$lane"
                ${pkgs.bash}/bin/bash ${./lane-toolbelt.sh} "$lane"
                touch "$out"
          '';
    };
}
