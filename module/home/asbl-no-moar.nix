# modules/home/asbl-no-moar.nix
{ pkgs, ... }:
let
  asbl-fooler = pkgs.writeShellApplication {
    name = "asbl-no-moar";
    runtimeInputs = [
      pkgs.wl-gammactl
      pkgs.coreutils
    ]; # Use wl-gammactl and coreutils (for sleep)
    text = ''
      #!/usr/bin/env bash

      # Set gamma high
      echo "Setting gamma to 1.2"
      timeout -p 3500ms ${pkgs.wl-gammactl}/bin/wl-gammactl -g 1.2 || true

      # Revert gamma to default
      echo "Gamma is back to 1.0"

      # The timer will trigger the next run after the specified interval
    '';
  };
in
{
  systemd.user.services.asbl-no-moar = {
    Unit = {
      Description = "Wayland gamma poke to mitigate ASBL";
      After = [ "graphical-session.target" ]; # Ensure graphical session is ready
    };
    Service = {
      Type = "simple";
      ExecStart = "${asbl-fooler}/bin/asbl-no-moar";
      # Environment = "WAYLAND_DISPLAY=wayland-1"; # Usually not needed for user services
      Restart = "no"; # Timer handles restarting
    };
    Install = {
      WantedBy = [ "default.target" ]; # Start automatically with user session
    };
  };

  systemd.user.timers.asbl-no-moar = {
    Unit = {
      Description = "Timer for asbl-no-moar service";
    };
    Timer = {
      OnBootSec = "2min"; # Start 2 minutes after user session starts
      OnUnitActiveSec = "150s"; # Run every 90 seconds after the service completes
      AccuracySec = "1s";
      Persistent = true; # Remember last run time across reboots if needed
    };
    Install = {
      WantedBy = [ "timers.target" ]; # Enable the timer
    };
  };
}
