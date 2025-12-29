{
  pkgs,
  lib,
  config,
  ... 
}: 
let
  cfg = config.sinnix.features.cli.asciinema;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.cli.asciinema = {
    enable = lib.mkEnableOption "Asciinema Shell Integration";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} = { config, pkgs, lib, sinnix, ... }:
      let
        inherit (sinnix.paths) dataRoot;
        recordingsDir = "${dataRoot}/asciinema_recording";
        asciinemaBin = "${pkgs.asciinema_3}/bin/asciinema";
        fallbackShell = "${pkgs.zsh}/bin/zsh";
      in
      {
        programs.zsh.initContent = lib.mkBefore ''
          # When already running under the recorder, install metadata hooks once.
          if [[ -n ''${SINNIX_ASCIINEMA_ACTIVE:-} ]]; then
            if [[ -n ''${SINNIX_ASCIINEMA_META:-} && -z ''${SINNIX_ASCIINEMA_HOOKED:-} ]]; then
              export SINNIX_ASCIINEMA_HOOKED=1
              autoload -Uz add-zsh-hook
              zmodload zsh/datetime 2>/dev/null || true

              typeset -gi SINNIX_ASCIINEMA_CMD_COUNT=0
              typeset -gi SINNIX_ASCIINEMA_LAST_CMD_ID=0
              typeset -F SINNIX_ASCIINEMA_CMD_START_REALTIME=0
              typeset SINNIX_ASCIINEMA_LAST_CMD=""
              typeset SINNIX_ASCIINEMA_LAST_REPO_ROOT=""
              typeset SINNIX_ASCIINEMA_LAST_REPO_BRANCH=""
              typeset SINNIX_ASCIINEMA_LAST_REPO_COMMIT=""
              typeset SINNIX_ASCIINEMA_LAST_REPO_DIRTY=""

              if command -v hyprctl >/dev/null 2>&1; then
                SINNIX_ASCIINEMA_HAS_HYPRCTL=1
              else
                SINNIX_ASCIINEMA_HAS_HYPRCTL=0
              fi
              if command -v git >/dev/null 2>&1; then
                SINNIX_ASCIINEMA_HAS_GIT=1
              else
                SINNIX_ASCIINEMA_HAS_GIT=0
              fi

              _sinnix_asciinema_log_command_start() {
                local now cmd
                now="$(date -Is)"
                cmd="$1"
                (( SINNIX_ASCIINEMA_CMD_COUNT += 1 ))
                SINNIX_ASCIINEMA_LAST_CMD_ID=$SINNIX_ASCIINEMA_CMD_COUNT
                SINNIX_ASCIINEMA_LAST_CMD="$cmd"
                SINNIX_ASCIINEMA_CMD_START_REALTIME=$EPOCHREALTIME
                printf '{"type":"command_start","id":%d,"time":"%s","cmd":%q,"pwd":%q}\n'
                  "$SINNIX_ASCIINEMA_LAST_CMD_ID" "$now" "$cmd" "$PWD" >>"$SINNIX_ASCIINEMA_META"
              }

              _sinnix_asciinema_log_command_end() {
                local last_status="$1"
                if [[ -z ''${SINNIX_ASCIINEMA_LAST_CMD_ID:-} || ''${SINNIX_ASCIINEMA_LAST_CMD_ID:-0} -eq 0 ]]; then
                  return
                fi
                local now duration_ms
                now="$(date -Is)"
                if [[ -n ''${SINNIX_ASCIINEMA_CMD_START_REALTIME:-} && ''${SINNIX_ASCIINEMA_CMD_START_REALTIME} -ne 0 ]]; then
                  duration_ms=$(( (EPOCHREALTIME - SINNIX_ASCIINEMA_CMD_START_REALTIME) * 1000 ))
                else
                  duration_ms=0
                fi
                printf '{"type":"command_end","time":"%s","status":%d,"id":%d,"duration_ms":%.3f,"cmd":%q}\n'
                  "$now" "$last_status" "$SINNIX_ASCIINEMA_LAST_CMD_ID" "$duration_ms" "$SINNIX_ASCIINEMA_LAST_CMD" >>"$SINNIX_ASCIINEMA_META"
                SINNIX_ASCIINEMA_CMD_START_REALTIME=0
              }

              _sinnix_asciinema_log_history() {
                  printf '{"type":"history","time":"%s","line":%q,"cmd_id":%d}\n'
                    "$(date -Is)" "$1" "''${SINNIX_ASCIINEMA_LAST_CMD_ID:-0}" >>"$SINNIX_ASCIINEMA_META"
                  return 0
              }

              _sinnix_asciinema_log_repo_context() {
                if [[ ''${SINNIX_ASCIINEMA_HAS_GIT:-0} -ne 1 ]]; then
                  return
                fi
                local root branch commit dirty_flag=0 dirty=""
                if root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
                  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
                  commit="$(git rev-parse --short HEAD 2>/dev/null)"
                  if git status --porcelain --untracked-files=no 2>/dev/null | read -r; then
                    dirty_flag=1
                  fi
                  dirty="$dirty_flag"
                else
                  root=""
                  branch=""
                  commit=""
                  dirty=""
                fi
                if [[ "$root" != "$SINNIX_ASCIINEMA_LAST_REPO_ROOT" || "$branch" != "$SINNIX_ASCIINEMA_LAST_REPO_BRANCH" || "$commit" != "$SINNIX_ASCIINEMA_LAST_REPO_COMMIT" || "$dirty" != "$SINNIX_ASCIINEMA_LAST_REPO_DIRTY" ]]; then
                  SINNIX_ASCIINEMA_LAST_REPO_ROOT="$root"
                  SINNIX_ASCIINEMA_LAST_REPO_BRANCH="$branch"
                  SINNIX_ASCIINEMA_LAST_REPO_COMMIT="$commit"
                  SINNIX_ASCIINEMA_LAST_REPO_DIRTY="$dirty"
                  printf '{"type":"repo","time":"%s","root":%q,"branch":%q,"commit":%q,"dirty":%q}\n'
                    "$(date -Is)" "$root" "$branch" "$commit" "$dirty_flag" >>"$SINNIX_ASCIINEMA_META"
                fi
              }

              _sinnix_asciinema_log_chpwd() {
                printf '{"type":"cwd","time":"%s","pwd":%q}\n' "$(date -Is)" "$PWD" >>"$SINNIX_ASCIINEMA_META"
                _sinnix_asciinema_log_repo_context
              }

              _sinnix_asciinema_log_precmd() {
                local last_status=$?
                _sinnix_asciinema_log_command_end "$last_status"
                local ws="{}"
                if [[ ''${SINNIX_ASCIINEMA_HAS_HYPRCTL:-0} -eq 1 ]]; then
                  ws="$(hyprctl -j activeworkspace 2>/dev/null || printf '{}')"
                fi
                printf '{"type":"prompt","time":"%s","status":%d,"pwd":%q,"workspace":%q}\n'
                  "$(date -Is)" "$last_status" "$PWD" "$ws" >>"$SINNIX_ASCIINEMA_META"
              }

              _sinnix_asciinema_log_periodic() {
                local loadavg="" uptime="" cpu="" mem="" ps_out="" _rest
                if read -r loadavg _rest < /proc/loadavg; then
                  : 
                fi
                if read -r uptime _rest < /proc/uptime; then
                  : 
                fi
                if ps_out="$(ps -p $$ -o pcpu= -o pmem= 2>/dev/null)"; then
                  read -r cpu mem <<<"$ps_out"
                fi
                printf '{"type":"heartbeat","time":"%s","pwd":%q,"load":%q,"uptime":%q,"cpu":%q,"mem":%q}\n'
                  "$(date -Is)" "$PWD" "$loadavg" "$uptime" "$cpu" "$mem" >>"$SINNIX_ASCIINEMA_META"
              }

              _sinnix_asciinema_log_exit() {
                local last_status=$?
                local end now elapsed
                end="$(date -Is)"
                now=$(date +%s)
                if [[ -n ''${SINNIX_ASCIINEMA_START_EPOCH:-} ]]; then
                  elapsed=$(( now - SINNIX_ASCIINEMA_START_EPOCH ))
                else
                  elapsed=0
                fi
                printf '{"type":"session_end","time":"%s","status":%d,"elapsed":%d,"commands":%d}\n'
                  "$end" "$last_status" "$elapsed" "''${SINNIX_ASCIINEMA_CMD_COUNT:-0}" >>"$SINNIX_ASCIINEMA_META"
                if command -v sha256sum >/dev/null 2>&1; then
                  if read -r hash _ < <(sha256sum "$SINNIX_ASCIINEMA_FILE" 2>/dev/null); then
                    printf '{"type":"digest","time":"%s","algo":"sha256","hash":%q}\n'
                      "$end" "$hash" >>"$SINNIX_ASCIINEMA_META"
                  fi
                fi
              }

              add-zsh-hook preexec _sinnix_asciinema_log_command_start
              add-zsh-hook zshaddhistory _sinnix_asciinema_log_history
              add-zsh-hook chpwd _sinnix_asciinema_log_chpwd
              add-zsh-hook precmd _sinnix_asciinema_log_precmd
              add-zsh-hook periodic _sinnix_asciinema_log_periodic
              add-zsh-hook zshexit _sinnix_asciinema_log_exit

              _sinnix_asciinema_log_repo_context
              if [[ -z ''${PERIOD:-} || ''${PERIOD} -gt 15 ]]; then
                PERIOD=15
              fi
            fi
          # Wrap every interactive TTY shell in an asciinema recorder unless explicitly disabled.
          # Exclude tty1 because it is used for the graphical session (Hyprland) auto-start.
          elif [[ -z ''${SINNIX_ASCIINEMA_DISABLE:-} && $- == *i* && -t 0 && -t 1 && "$(tty)" != "/dev/tty1" ]]; then
            export SINNIX_ASCIINEMA_ACTIVE=1

            record_dir="${recordingsDir}"
            mkdir -p "$record_dir"

            ts="$(date -u +%Y%m%dT%H%M%SZ)"
            start_epoch="$(date +%s)"
            host="$(hostname 2>/dev/null || printf 'unknown-host')"
            tty_path="$(tty 2>/dev/null || printf 'unknown-tty')"
            tty_name="''${tty_path#/}"
            tty_name="''${tty_name//
ltk/}"
            tty_name="''${tty_name//[^A-Za-z0-9._-]/_}"
            tty_name="''${tty_name:-unknown-tty}"
            parent_pid="$PPID"
            shell_pid="$$"
            tmux_context=""
            if [[ -n ''${TMUX:-} ]]; then
              tmux_context="$(tmux display-message -p '#{session_name}:#{window_index}.#{pane_index}' 2>/dev/null || printf "%s" "")"
            fi
            ssh_conn="''${SSH_CONNECTION:-}"
            ssh_tty="''${SSH_TTY:-}"
            term_env="''${TERM:-}"
            display_env="''${DISPLAY:-}"
            wayland_env="''${WAYLAND_DISPLAY:-}"
            session_type="''${XDG_SESSION_TYPE:-}"
            project_root="''${PRJ_ROOT:-}"
            flake_root="''${FLAKE:-}"
            devshell_root="''${DEVSHELL_DIR:-}"
            cast_file="''${host}-''${USER}-''${tty_name}-''${ts}-$$-''${RANDOM}.cast"
            cast_path="$record_dir/$cast_file"
            meta_path="$cast_path.meta"
            export SINNIX_ASCIINEMA_FILE="$cast_path"
            export SINNIX_ASCIINEMA_META="$meta_path"
            export SINNIX_ASCIINEMA_START_EPOCH="$start_epoch"

            printf '{"type":"session_start","time":"%s","host":%q,"user":%q,"tty":%q,"pwd":%q,"shell_pid":%q,"parent_pid":%q,"term":%q,"tmux":%q,"ssh_connection":%q,"ssh_tty":%q,"display":%q,"wayland":%q,"session_type":%q,"project_root":%q,"flake":%q,"devenv":%q}\n'
              "$ts" "$host" "$USER" "$tty_path" "$PWD" "$shell_pid" "$parent_pid" "$term_env" "$tmux_context" "$ssh_conn" "$ssh_tty" "$display_env" "$wayland_env" "$session_type" "$project_root" "$flake_root" "$devshell_root" >"$meta_path"
            printf '{"type":"recorder","time":"%s","file":%q,"pid":%d}\n'
              "$ts" "$cast_path" "$$" >>"$meta_path"

            shell_bin="''${SHELL:-${fallbackShell}}"
            record_cmd=$(printf '%q' "$shell_bin")
            for arg in "$@"; do
              record_cmd="$record_cmd $(printf '%q' "$arg")"
            done
            if [[ -o login ]]; then
              record_cmd="$record_cmd -l"
            fi

            exec ${asciinemaBin} rec \
              --stdin \
              --quiet \
              --command "$record_cmd" \
              "$cast_path"
          fi
        '';
      };
  };
}
