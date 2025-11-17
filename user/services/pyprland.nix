# Pyprland - Advanced scratchpad management for Hyprland
{
  pkgs,
  inputs,
  lib,
  config,
  ...
}:
let
  inherit (config.sinnix.paths) realmRoot;
  pyprlandCleanup = pkgs.writeShellScript "pyprland-sock-cleanup" ''
    set -eu
    HYPR_RUNTIME="/run/user/$UID/hypr"
    if [ -d "$HYPR_RUNTIME" ]; then
      ${pkgs.findutils}/bin/find "$HYPR_RUNTIME" -maxdepth 2 -name ".pyprland.sock" -delete || true
    fi
  '';
in
{
  systemd.user.services.pyprland = {
    Unit = {
      Description = "Pyprland daemon for advanced scratchpad management";
      After = [ "graphical-session.target" ];
      PartOf = [ "graphical-session.target" ];
      Wants = [ "graphical-session.target" ];
    };
    Service = {
      Type = "simple";
      ExecStart = "${pkgs.pyprland}/bin/pypr";
      ExecReload = "${pkgs.coreutils}/bin/kill -HUP $MAINPID";
      Restart = "on-failure";
      RestartSec = 2;
      KillMode = "mixed";
      TimeoutStopSec = 5;
      ExecStartPre = pyprlandCleanup;
      RuntimeDirectory = "pyprland";
      RuntimeDirectoryMode = "0700";
    };
    Install = {
      WantedBy = [ "graphical-session.target" ];
    };
  };

  xdg.configFile."hypr/pyprland.toml".text =
    lib.replaceStrings
      [ "/home/sinity" "/realm/knowledgebase" ]
      [ config.home.homeDirectory "${realmRoot}/knowledgebase" ]
      (builtins.readFile "${inputs.self}/assets/pyprland.toml");

  home.packages = [ pkgs.pyprland ];
}
