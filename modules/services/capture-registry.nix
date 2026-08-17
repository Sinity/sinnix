# Capture lanes with no owning systemd unit.
#
# Some lanes are written by things that are not units: a hotkey script, an
# ad-hoc probe, an artifact dropped in by hand. They still need a freshness
# budget, because "nothing has written this lane in a week" is a failure that
# looks exactly like a quiet week.
#
# They used to be declared as runtime SURFACES with a synthetic `unit` string,
# which meant a field typed "systemd unit name" held a shell script's name for
# a whole category, guarded by a `kind = "capture"` carve-out in the assertion
# that checks unit names and re-checked in every consumer that walks surfaces.
# sinnix.runtime.captures exists so a lane can simply be a lane.
{ config, ... }:
{
  sinnix.runtime.captures = [
    {
      # screenshot-color-lab.sh (desktop-control-plane skill), fired from the
      # Hyprland "Show display capture status" binding and by ad-hoc operator
      # or agent screenshots. Never a daemon.
      name = "screenshot";
      path = "${config.sinnix.paths.activityRoot}/screenshot";
      eventDriven = true;
      staleAfterSeconds = 604800;
    }
  ];
}
