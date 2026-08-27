{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    {
      checks.hyprland-lua-tools =
        pkgs.runCommand "hyprland-lua-tools-check"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.curl
              pkgs.jq
              pkgs.python3
              pkgs.shellcheck
              pkgs.websocat
            ];
          }
          ''
            chrome="$TMPDIR/sinnix-chrome-control"
            hypr="$TMPDIR/sinnix-hypr-control"
            keyboard="$TMPDIR/sinnix-keyboard-control"
            grid="$TMPDIR/kitty-grid"
            cp ${../../dots/_ai/skills/desktop-control-plane/scripts/chrome-control.sh} "$chrome"
            cp ${../../dots/_ai/skills/desktop-control-plane/scripts/hypr-control.sh} "$hypr"
            cp ${../../dots/_ai/skills/desktop-control-plane/scripts/keyboard-control.sh} "$keyboard"
            cp ${../../scripts/kitty-grid} "$grid"
            chmod +x "$chrome" "$hypr" "$keyboard" "$grid"
            patchShebangs "$chrome" "$hypr" "$keyboard" "$grid"
            shellcheck -S warning "$chrome" "$hypr" "$keyboard"
            ${pkgs.bash}/bin/bash ${./hyprland-lua-tools.sh} "$chrome" "$hypr" "$keyboard" "$grid"
            touch "$out"
          '';
    };
}
