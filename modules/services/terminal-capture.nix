# Integrated Terminal Capture and Session Telemetry
#
# Provides:
# - Automatic shell recording via asciinema
# - Enriched metadata capture (Git context, system load, active workspace)
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
  inherit (config.sinnix.paths) capturesRoot;
  recordingsDir = "${capturesRoot}/asciinema";
in
{
  options.sinnix.services.terminal-capture = {
    enable = lib.mkEnableOption "Advanced terminal session recording and telemetry";
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ pkgs.asciinema_3 ];

    systemd.tmpfiles.rules = [
      "d ${recordingsDir} 0755 ${username} users -"
    ];

    home-manager.users.${username} = { lib, pkgs, ... }: {
      programs.zsh.initContent = lib.mkBefore ''
        # Metadata and hooks logic for enriched capture
        if [[ -n ''${SINNIX_ASCIINEMA_ACTIVE:-} ]]; then
          if [[ -n ''${SINNIX_ASCIINEMA_META:-} && -z ''${SINNIX_ASCIINEMA_HOOKED:-} ]]; then
            export SINNIX_ASCIINEMA_HOOKED=1
            autoload -Uz add-zsh-hook
            zmodload zsh/datetime 2>/dev/null || true

            _sinnix_log_event() {
              local type="$1"; shift
              printf '{"type":"%s","time":"%s",%s}
' "$type" "$(date -Is)" "$*" >>"$SINNIX_ASCIINEMA_META"
            }

            _sinnix_preexec() {
              export SINNIX_CMD_START=$EPOCHREALTIME
              _sinnix_log_event "command_start" ""cmd":$(printf '%q' "$1"),"pwd":$(printf '%q' "$PWD")"
            }

            _sinnix_precmd() {
              local status=$?
              local duration=0
              [[ -n $SINNIX_CMD_START ]] && duration=$(( (EPOCHREALTIME - SINNIX_CMD_START) * 1000 ))
              _sinnix_log_event "command_end" ""status":$status,"duration_ms":$duration"
            }

            add-zsh-hook preexec _sinnix_preexec
            add-zsh-hook precmd _sinnix_precmd
          fi
        elif [[ -z ''${SINNIX_ASCIINEMA_DISABLE:-} && $- == *i* && -t 0 && "$(tty)" != "/dev/tty1" ]]; then
          export SINNIX_ASCIINEMA_ACTIVE=1
          local ts=$(date -u +%Y%m%dT%H%M%SZ)
          local cast_path="${recordingsDir}/$(hostname)-$(tty | tr / _)-''${ts}.cast"
          export SINNIX_ASCIINEMA_FILE="$cast_path"
          export SINNIX_ASCIINEMA_META="$cast_path.meta"
          
          exec ${pkgs.asciinema_3}/bin/asciinema rec --stdin --quiet --command "$SHELL" "$cast_path"
        fi
      '';
    };
  };
}
