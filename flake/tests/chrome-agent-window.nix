# Behavioral CDP fixture for `sinnix-chrome-control agent-window`.  This is a
# separate check because it drives a fake Chrome transport and compositor; the
# agent-tools check only proves Home Manager installs the helper.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    {
      checks.chrome-agent-window =
        pkgs.runCommand "chrome-agent-window-check"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.gnugrep
              pkgs.gnused
              pkgs.jq
              pkgs.shellcheck
              pkgs.util-linux
            ];
          }
          ''
            helper="$TMPDIR/sinnix-chrome-control"
            cp ${../../dots/_ai/skills/desktop-control-plane/scripts/chrome-control.sh} "$helper"
            chmod +x "$helper"
            patchShebangs "$helper"
            shellcheck -S warning "$helper" ${./chrome-agent-window.sh}
            bash -n "$helper" ${./chrome-agent-window.sh}
            ${pkgs.bash}/bin/bash ${./chrome-agent-window.sh} "$helper"
            touch "$out"
          '';
    };
}
