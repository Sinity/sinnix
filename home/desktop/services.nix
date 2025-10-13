{ pkgs, lib, ... }:
let
  logitechMaintenance = pkgs.writeShellScript "logitech-maintenance" ''
    #!/usr/bin/env bash
    set -uo pipefail

    SOLAAR="${pkgs.solaar}/bin/solaar"
    RATBAGCTL="${pkgs.libratbag}/bin/ratbagctl"
    MKTEMP="${pkgs.coreutils}/bin/mktemp"
    RM="${pkgs.coreutils}/bin/rm"

    tmp=$($MKTEMP 2>/dev/null || true)
    if [ -n "$tmp" ]; then
      if "$SOLAAR" show >"$tmp" 2>/dev/null; then
        for name in "Powerplay Wireless Charging System" "Wireless Charging System" "POWERPLAY" "Powerplay"; do
          "$SOLAAR" config "$name" charge_control_mode max >/dev/null 2>&1 && break
        done
        for name in "G502 Wireless" "G502" "Wireless Gaming Mouse"; do
          if "$SOLAAR" config "$name" battery_saver off >/dev/null 2>&1; then
            "$SOLAAR" config "$name" battery_alert_threshold 0 >/dev/null 2>&1 || true
            break
          fi
        done
      fi
      "$RM" -f "$tmp" >/dev/null 2>&1 || true
    fi

    if "$RATBAGCTL" list >/dev/null 2>&1; then
      "$RATBAGCTL" list | while IFS=: read -r dev desc; do
        case "$desc" in
          *G502*|*G-POWERPLAY*|*Powerplay*)
            for led in 0 1; do
              "$RATBAGCTL" "$dev" led "$led" set mode on >/dev/null 2>&1 || true
              "$RATBAGCTL" "$dev" led "$led" set color ff9900 >/dev/null 2>&1 || true
              "$RATBAGCTL" "$dev" led "$led" set brightness 8 >/dev/null 2>&1 || true
              "$RATBAGCTL" "$dev" led "$led" set duration 0 >/dev/null 2>&1 || true
            done
            ;;
        esac
      done
    fi

    exit 0
  '';
in
{
  services.activitywatch = {
    enable = true;
    package = pkgs.aw-server-rust;
    watchers.awatcher = {
      package = pkgs.awatcher;
      settings = {
        idle-timeout-seconds = 60;
        poll-time-idle-seconds = 1;
        poll-time-window-seconds = 1;
      };
    };
  };

  systemd.user.services = {
    activitywatch-watcher-awatcher =
      let
        target = "graphical-session.target";
      in
      {
        Unit = {
          After = [ target ];
          Requisite = [ target ];
          PartOf = [ target ];
        };
        Install.WantedBy = [ target ];
      };

    logitech-maintenance = {
      Unit = {
        Description = "Ensure Logitech G502/Powerplay charge and LED state";
        After = [
          "graphical-session.target"
          "ratbagd.service"
        ];
        Wants = [
          "graphical-session.target"
          "ratbagd.service"
        ];
      };
      Service = {
        Type = "oneshot";
        ExecStartPre = "${pkgs.coreutils}/bin/sleep 5";
        ExecStart = logitechMaintenance;
        Restart = "on-failure";
        RestartSec = 10;
      };
      Install = {
        WantedBy = [ "graphical-session.target" ];
      };
    };

    wl-clip-persist = {
      Unit = {
        Description = "Wayland clipboard persistence";
        After = [ "graphical-session.target" ];
        PartOf = [ "graphical-session.target" ];
      };
      Service = {
        Type = "simple";
        ExecStart = "${pkgs.wl-clip-persist}/bin/wl-clip-persist --clipboard both";
        Restart = "on-failure";
        RestartSec = 1;
      };
      Install = {
        WantedBy = [ "graphical-session.target" ];
      };
    };

    nm-applet = {
      Unit = {
        Description = "NetworkManager applet";
        After = [ "graphical-session.target" ];
        PartOf = [ "graphical-session.target" ];
      };
      Service = {
        Type = "simple";
        ExecStart = "${pkgs.networkmanagerapplet}/bin/nm-applet";
        Restart = "on-failure";
        RestartSec = 1;
      };
      Install = {
        WantedBy = [ "graphical-session.target" ];
      };
    };

    polkit-gnome-authentication-agent-1 = {
      Unit = {
        Description = "polkit-gnome-authentication-agent-1";
        After = [ "graphical-session.target" ];
        PartOf = [ "graphical-session.target" ];
      };
      Service = {
        Type = "simple";
        ExecStart = "${pkgs.polkit_gnome}/libexec/polkit-gnome-authentication-agent-1";
        Restart = "on-failure";
        RestartSec = 1;
      };
      Install = {
        WantedBy = [ "graphical-session.target" ];
      };
    };

    blueman-applet = {
      Unit = {
        Description = "Blueman applet";
        After = [ "graphical-session.target" ];
        PartOf = [ "graphical-session.target" ];
      };
      Service = {
        Type = "simple";
        ExecStart = "${pkgs.blueman}/bin/blueman-applet";
        Restart = "on-failure";
        RestartSec = 1;
      };
      Install = {
        WantedBy = [ "graphical-session.target" ];
      };
    };
  };

  systemd.user.timers.logitech-maintenance = {
    Unit.Description = "Keep Logitech G502 LEDs locked to the desired state";
    Timer = {
      OnBootSec = "45s";
      OnUnitActiveSec = "5m";
      RandomizedDelaySec = "30s";
      Unit = "logitech-maintenance.service";
      Persistent = true;
    };
    Install.WantedBy = [ "timers.target" ];
  };

  home.packages = lib.mkBefore (with pkgs; [
    aw-watcher-window-wayland
    aw-watcher-afk
  ]);
}
