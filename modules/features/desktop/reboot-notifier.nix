{ mkFeatureModule, pkgs, config, ... }@args:
mkFeatureModule {
  path = [ "desktop" "reboot-notifier" ];
  description = "System reboot notifier";
  configFn =
    { config, pkgs, ... }:
    let
      user = config.sinnix.user.name;
    in
    {
      home-manager.users.${user} = { pkgs, ... }:
        let
          checkScript = pkgs.writeShellScript "check-reboot-needed" ''
            set -euo pipefail

            log() { echo "[$0] $*" >&2; }
            error() { echo "[$0] ERROR: $*" >&2; }

            needs_reboot=0
            reasons=""

            log "Starting reboot check..."

            state_dir="''${XDG_STATE_HOME:-$HOME/.local/state}/reboot-notifier"
            state_file="$state_dir/last-notified"
            mkdir -p "$state_dir"

            booted_kernel=$(readlink /run/booted-system/kernel || echo "unknown")
            current_kernel=$(readlink /run/current-system/kernel || echo "unknown")
            current_system=$(readlink /run/current-system || echo "unknown")
            last_notified=$(cat "$state_file" 2>/dev/null || echo "")

            log "Booted kernel: $booted_kernel"
            log "Current kernel: $current_kernel"
            log "Current system: $current_system"

            if [[ "$booted_kernel" != "unknown" && "$current_kernel" != "unknown" && "$booted_kernel" != "$current_kernel" ]]; then
              log "Kernel update detected."
              needs_reboot=1
              reasons="Kernel updated"
            fi

            if [[ -f /proc/driver/nvidia/version ]]; then
              log "NVIDIA driver found."
              loaded_nvidia=$(${pkgs.gawk}/bin/awk '/NVRM version:/ {print $10}' /proc/driver/nvidia/version || echo "")
              log "Loaded NVIDIA version: $loaded_nvidia"

              current_nvidia="check-failed"
              if command -v nvidia-smi >/dev/null 2>&1; then
                if output=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>&1); then
                   current_nvidia=$(echo "$output" | head -1)
                else
                   error "nvidia-smi failed: $output"
                fi
              else
                error "nvidia-smi not found in path"
              fi

              log "Current NVIDIA version: $current_nvidia"

              if [[ "$current_nvidia" == "check-failed" ]]; then
                needs_reboot=1
                msg="NVIDIA driver mismatch (tool failed)"
                if [[ -n "$reasons" ]]; then reasons="$reasons, $msg"; else reasons="$msg"; fi
                error "$msg"
              elif [[ -n "$loaded_nvidia" && -n "$current_nvidia" && "$loaded_nvidia" != "$current_nvidia" ]]; then
                needs_reboot=1
                msg="NVIDIA driver ($loaded_nvidia → $current_nvidia)"
                if [[ -n "$reasons" ]]; then reasons="$reasons, $msg"; else reasons="$msg"; fi
                log "$msg"
              fi
            else
              log "No NVIDIA driver detected in /proc/driver/nvidia/version"
            fi

            if [[ "$needs_reboot" -eq 1 ]]; then
              if [[ -n "$current_system" && "$current_system" == "$last_notified" ]]; then
                log "Notification for $current_system already sent; skipping."
                exit 0
              fi

              log "Reboot required: $reasons"
              ${pkgs.libnotify}/bin/notify-send \
                --urgency=critical \
                --app-name="System" \
                --icon=system-reboot \
                "Reboot Required" \
                "$reasons - system may be unstable"

              if [[ "$current_system" != "unknown" ]]; then
                echo "$current_system" > "$state_file"
              fi
            else
              log "No reboot needed."
              rm -f "$state_file"
            fi
          '';
        in
        {
          systemd.user.services.reboot-notifier = {
            Unit = {
              Description = "Check if system reboot is needed and notify";
              After = [ "graphical-session.target" ];
            };
            Service = {
              Type = "oneshot";
              ExecStart = "${checkScript}";
              Environment = [
                "PATH=${pkgs.coreutils}/bin:${pkgs.gawk}/bin"
              ];
            };
            Install.WantedBy = [ "default.target" ];
          };

          systemd.user.paths.reboot-notifier-watch = {
            Unit.Description = "Watch for system updates";
            Path = {
              PathChanged = "/run/current-system";
              Unit = "reboot-notifier.service";
            };
            Install.WantedBy = [ "paths.target" ];
          };
        };
    };
} args
