{
  pkgs,
  lib,
  inputs,
  config,
  ...
}:
let
  keylogRoot = "${config.sinnix.paths.capturesRoot}/keylog";
  username = config.sinnix.user.name;
  interceptTools = pkgs.interception-tools;
  capsPlugin = pkgs.interception-tools-plugins.caps2esc;
  interceptBouncePkg =
    inputs.intercept-bounce.packages.${pkgs.stdenv.hostPlatform.system}.intercept-bounce;
  scribePkg = inputs.scribe-tap.packages.${pkgs.stdenv.hostPlatform.system}.default;
  interceptCmd = "${interceptTools}/bin/intercept -g $DEVNODE";
  bounceCmd = lib.escapeShellArgs [
    "${interceptBouncePkg}/bin/intercept-bounce"
    "--debounce-time"
    "40ms"
    "--log-interval"
    "6h"
    "--log-bounces"
    "--stats-json"
  ];
  scribeCmd = lib.escapeShellArgs [
    "${scribePkg}/bin/scribe-tap"
    "--data-dir"
    "${keylogRoot}"
    "--log-dir"
    "${keylogRoot}/logs"
    "--log-mode"
    "events"
    "--context"
    "hyprland"
    "--translate"
    "xkb"
    "--hypr-user"
    username
    "--xkb-layout"
    "pl"
  ];
  capsCmd = lib.escapeShellArgs [
    "${capsPlugin}/bin/caps2esc"
    "-m"
    "1"
  ];
  uinputCmd = "${interceptTools}/bin/uinput -d $DEVNODE";
  pipeline = lib.concatStringsSep " | " [
    interceptCmd
    bounceCmd
    scribeCmd
    capsCmd
    uinputCmd
  ];

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
  services = {
    interception-tools = {
      enable = true;
      udevmonConfig = ''
        - JOB: "${pipeline}"
          DEVICE:
            LINK: "/dev/input/by-id/.*Logitech.*event-kbd"
            NAME: ".*Logitech.*"
      '';
    };
    ratbagd.enable = true;
    udev.packages = [ pkgs.solaar ];
  };
  programs.dconf.enable = true;

  systemd = {
    tmpfiles.rules = [
      "d ${keylogRoot} 0700 ${username} users -"
      "d ${keylogRoot}/logs 0700 ${username} users -"
      "d ${keylogRoot}/snapshots 0700 ${username} users -"
    ];

    user = {
      services.logitech-maintenance = {
        description = "Ensure Logitech G502/Powerplay charge and LED state";
        after = [
          "graphical-session.target"
          "ratbagd.service"
        ];
        wants = [
          "graphical-session.target"
          "ratbagd.service"
        ];
        serviceConfig = {
          Type = "oneshot";
          ExecStartPre = "${pkgs.coreutils}/bin/sleep 5";
          ExecStart = logitechMaintenance;
          Restart = "on-failure";
          RestartSec = 10;
        };
        wantedBy = [ "graphical-session.target" ];
      };

      # DISABLED: Timer causes Solaar to recreate virtual keyboard ~8 times per run
      # Over hours this creates 200+ input devices, potentially causing kernel resource exhaustion.
      # Investigation needed: why does `solaar config` trigger device recreation?
      # See: journalctl -k --grep="solaar-keyboard" for device creation pattern
      #
      # timers.logitech-maintenance = {
      #   description = "Keep Logitech G502 LEDs locked to the desired state";
      #   timerConfig = {
      #     OnBootSec = "45s";
      #     OnUnitActiveSec = "5m";
      #     RandomizedDelaySec = "30s";
      #     Unit = "logitech-maintenance.service";
      #     Persistent = true;
      #   };
      #   wantedBy = [ "timers.target" ];
      # };
    };
  };

  systemd.services.interception-tools = {
    unitConfig.RequiresMountsFor = [ keylogRoot ];
    serviceConfig = {
      Slice = "recovery.slice";
      ExecStartPre = [
        (pkgs.writeShellScript "interception-tools-init" ''
          #!/usr/bin/env bash
          set -euo pipefail
          install -d -m700 -o ${username} -g users "${keylogRoot}"
          install -d -m700 -o ${username} -g users "${keylogRoot}/logs"
          install -d -m700 -o ${username} -g users "${keylogRoot}/snapshots"
        '')
      ];
    };
  };
}
