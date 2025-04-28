{pkgs, ...}: let
  poker = pkgs.writeShellApplication {
    name = "poke";
    runtimeInputs = [pkgs.ddcutil];
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      MODEL="AORUS FO48U"
      VPCCODE=0x10

      out=$(ddcutil --model="$MODEL" getvcp $VPCCODE)
      cur=$(grep -oP 'current value\s*=\s*\K\d+' <<<"$out")
      new=$((cur - 10))

      echo "bump brightness: $cur → $new"
      ddcutil --model="$MODEL" setvcp $VPCCODE "$new"

      sleep 1.5

      echo "revert brightness: $new → $cur"
      ddcutil --model="$MODEL" setvcp $VPCCODE "$cur"
    '';
  };
in {
  systemd.services.asbl-no-moar = {
    description = "FO48U anti-ASBL brightness poke";
    wants = ["timers.target"];
    after = ["timers.target" "graphical.target"];
    serviceConfig = {
      Type = "simple";
      ExecStart = "${poker}/bin/poke";
      TimeoutSec = "10s";
      StandardOutput = "journal";
      StandardError = "journal";
      # Fix for cache warnings
      Environment = "XDG_CACHE_HOME=/var/cache/ddcutil";
      RuntimeDirectory = "ddcutil"; # Creates /run/ddcutil at service start
    };
  };
  systemd.timers.asbl-no-moar = {
    wantedBy = ["timers.target"];
    timerConfig = {
      OnBootSec = "120s";
      OnUnitActiveSec = "57s";
      AccuracySec = "1s";
    };
    unitConfig = {
      Description = "Timer for AORUS FO48U anti-ASBL brightness poke";
      Unit = "asbl-no-moar.service";
    };
  };
}
