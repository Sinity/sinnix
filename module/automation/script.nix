# Scripts

{ pkgs, ... }:
let

  toggle_waybar = pkgs.writeScriptBin "toggle_waybar" ''
    #!/usr/bin/env bash
    if ${pkgs.procps}/bin/pgrep -x waybar > /dev/null; then
        ${pkgs.procps}/bin/pkill waybar
    else
        ${pkgs.waybar}/bin/waybar &
    fi
  '';
in
{
  config = {
    environment.systemPackages = [
      toggle_waybar
    ];
  };
}
