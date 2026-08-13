# Orphan capture-path registry
#
# Some capture lanes have no owning systemd unit in this repo: the write
# path is a manual hotkey script, an external cron/Takeout-style artifact,
# or a probe tool invoked ad hoc. Those lanes still need a runtime surface
# so the health sentinel (sinnix-health-sentinel) and introspection
# (/etc/sinnix/runtime-inventory.json) can see their write freshness --
# this module's sole job is registering those orphan paths. It does not
# run, own, or manage the underlying capture process; each capture's
# `unit` field here is a synthetic identity for the inventory, not a real
# systemd unit.
#
# Lanes covered:
# - webhistory: chrome-snapshot.sh (/realm/data/captures/webhistory), a
#   manually-scheduled Chrome History DB snapshot script that lives outside
#   this repo.
# - screenshot: screenshot-color-lab.sh (desktop-control-plane skill),
#   triggered via the Hyprland "Show display capture status" probe binding
#   and ad hoc agent/operator screenshot capture, not a daemon.
{ config, ... }:
let
  capturesRoot = config.sinnix.paths.capturesRoot;
in
{
  sinnix.runtime.surfaces = {
    capture-webhistory = {
      unit = "sinnix-capture-webhistory";
      kind = "capture";
      dynamic = true;
      resourceClass = "system";
      captures = [
        {
          name = "webhistory";
          path = "${capturesRoot}/webhistory";
          eventDriven = true;
          staleAfterSeconds = 172800;
        }
      ];
    };
    capture-screenshot = {
      unit = "sinnix-capture-screenshot";
      kind = "capture";
      dynamic = true;
      resourceClass = "system";
      captures = [
        {
          name = "screenshot";
          path = "${capturesRoot}/screenshot";
          eventDriven = true;
          staleAfterSeconds = 604800;
        }
      ];
    };
  };
}
