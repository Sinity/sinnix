{
  pkgs,
  inputs,
  lib,
  ...
}:
let
  barPath = "${inputs.self}/ironbar";
in
{
  home.packages = [ pkgs.ironbar pkgs.jq ];

  xdg.configFile = {
    "ironbar/config.toml".source = barPath + "/config.toml";
    "ironbar/style.css".source = barPath + "/style.css";
  };

  home.file = {
    ".local/bin/audio-output-status" = {
      source = inputs.self + "/scripts/audio-output-status";
      executable = true;
    };
    ".local/bin/toggle-audio-output" = {
      source = inputs.self + "/scripts/toggle-audio-output";
      executable = true;
    };
    ".local/bin/toggle-ironbar" = {
      source = inputs.self + "/scripts/toggle-ironbar";
      executable = true;
    };
    ".local/bin/mic-status" = {
      source = inputs.self + "/scripts/mic-status";
      executable = true;
    };
    ".local/bin/mic-toggle" = {
      source = inputs.self + "/scripts/mic-toggle";
      executable = true;
    };
  };

  systemd.user.services.ironbar = {
    Unit = {
      Description = "Ironbar Wayland bar";
      After = [ "graphical-session.target" ];
      PartOf = [ "graphical-session.target" ];
    };
    Service = {
      ExecStart = "${pkgs.ironbar}/bin/ironbar";
      Restart = "on-failure";
      RestartSec = 2;
    };
    Install.WantedBy = [ "graphical-session.target" ];
  };

  # Ensure scripts called from the bar are executable
  home.activation."ironbar-helpers" = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    for helper in \
      "$HOME/.local/bin/audio-output-status" \
      "$HOME/.local/bin/toggle-audio-output" \
      "$HOME/.local/bin/toggle-ironbar" \
      "$HOME/.local/bin/mic-status" \
      "$HOME/.local/bin/mic-toggle" \
      "$HOME/.local/bin/ocr-region" \
      "$HOME/.local/bin/screenshot-quick" \
      "$HOME/.local/bin/research-capture"
    do
      if [ -e "$helper" ]; then
        chmod +x "$helper" 2>/dev/null || true
      fi
    done
  '';
}
