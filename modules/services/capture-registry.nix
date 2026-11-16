# Capture streams without an owning systemd unit still need a freshness budget.
{ config, ... }:
{
  sinnix.runtime.captures = [
    {
      # screenshot-color-lab.sh (desktop-control skill), fired from the
      # Hyprland "Show display capture status" binding and by ad-hoc operator
      # or agent screenshots. Never a daemon.
      name = "screenshot";
      path = "${config.sinnix.paths.capturePaths.screenshot}";
      eventDriven = true;
      staleAfterSeconds = 604800;
    }
  ];
}
