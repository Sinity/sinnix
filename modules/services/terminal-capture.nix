# Integrated Terminal Capture and Session Telemetry
#
# Provides:
# - Automatic shell recording via asciinema
# - Shell-native session and command metadata
# - Unified directory management for terminal artifacts
{
  pkgs,
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix.services.terminal-capture;
  username = config.sinnix.user.name;
  repoRoot = config.sinnix.paths.projectRoot;
  inherit (config.sinnix.paths) capturesRoot;
  recordingsDir = "${capturesRoot}/asciinema";
in
{
  options.sinnix.services.terminal-capture = {
    enable = lib.mkEnableOption "Advanced terminal session recording and telemetry";
  };

  config = lib.mkIf cfg.enable {
    sinnix.runtime.surfaces.terminal-capture = {
      unit = "sinnix-captured-shell";
      manager = "user";
      kind = "capture";
      resourceClass = "capture-runtime";
      captures = [
        {
          name = "asciinema";
          path = recordingsDir;
          eventDriven = true;
        }
      ];
    };

    environment.systemPackages = [
      pkgs.asciinema
      pkgs.jq
    ];

    systemd.tmpfiles.rules = [
      "d ${recordingsDir} 0755 ${username} users -"
    ];

    home-manager.users.${username} =
      {
        lib,
        config,
        ...
      }:
      {
        home.file.".local/bin/sinnix-captured-shell" = {
          source = config.lib.file.mkOutOfStoreSymlink "${repoRoot}/scripts/sinnix-captured-shell";
          force = true;
        };

        home.activation."terminal-capture-script-perms" = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
          if [ -e "$HOME/.local/bin/sinnix-captured-shell" ]; then
            chmod +x "$HOME/.local/bin/sinnix-captured-shell" 2>/dev/null || true
          fi
        '';

        home.sessionVariables.SINNIX_CAPTURE_ROOT = recordingsDir;
        home.sessionVariables.SINNIX_CAPTURE_TERMINAL = "kitty";

        programs.zsh.initContent = lib.mkBefore ''
          if [[ -n ''${SINNIX_CAPTURE_SESSION_ID:-} ]]; then
            source ${repoRoot}/scripts/sinnix-terminal-capture-hooks.zsh
          fi
        '';
      };
  };
}
