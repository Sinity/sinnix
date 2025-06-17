# Media and Entertainment Scripts
# Scripts for audio, video, and multimedia management

{ pkgs, ... }:
let
  lofi = pkgs.writeScriptBin "lofi" ''
    #!/usr/bin/env bash
    ${pkgs.libnotify}/bin/notify-send "起動 Lofi Music" "Enjoy!"
    ${pkgs.mpv}/bin/mpv "https://www.youtube.com/watch?v=jfKfPfyJRdk" --no-video --loop-playlist=inf
  '';
in
{
  config = {
    environment.systemPackages = [
      lofi
    ];
  };
}
