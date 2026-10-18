{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    {
      checks.phone-bcr =
        pkgs.runCommand "sinnix-phone-bcr-check"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.gawk
              pkgs.gnugrep
              pkgs.jq
              pkgs.ffmpeg
              pkgs.python3
              pkgs.util-linux
            ];
          }
          ''
            python ${./phone-bcr.py} ${../../scripts/sinnix-phone} ${../../scripts/sinnix-remote-command}
            python ${./phone-wireless.py} ${../../scripts/sinnix-phone} ${../../scripts/sinnix-remote-command}
            python ${./phone-status.py} ${../../scripts/sinnix-phone}
            touch "$out"
          '';
    };
}
