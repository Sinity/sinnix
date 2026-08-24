# capture-calendar: vdirsyncer daily CalDAV -> .ics snapshots into the
# capture lake (sinnix-m0qt).
#
# Native-format doctrine, same as capture-mail.nix (same bead family,
# 2026-08-12 rigor pass): calendars land as plain .ics files under one
# directory tree, not sinnix-capture envelopes.
#
# Lives under activityRoot/calendar: the calendar mirror is an ambient
# record of the operator's own scheduled activity, which is activityRoot's
# subject (capturesRoot, the old undifferentiated root, was retired
# 2026-08-24).
#
# Sync shape: a single continuously-updated mirror (vdirsyncer's own
# status_path incremental sync state), not dated snapshot directories -- a
# second/Nth run is a no-op except for what actually changed upstream, which
# both satisfies "second run idempotent" and keeps a change's history
# reconstructable from btrbk snapshots of the mirror rather than from this
# lane inventing its own dating scheme.
#
# `read_only = true` on the CalDAV storage below is load-bearing, not
# incidental: vdirsyncer is a genuine two-way sync engine, and without it a
# corrupted or accidentally-deleted local .ics file would propagate that
# deletion back to the operator's real calendar on the next pass. This lane
# only ever reads from CalDAV and writes locally.
#
# Default-off (`sinnix.services.capture-calendar.enable`) with a NAMED
# secret slot, shared with capture-mail.nix's mail-app-password (same
# account family, per the bead's own "do 9dml first, reuse its auth work").
#
# Operator steps to go live (after capture-mail's secret already exists):
#   1. sinnix.services.capture-calendar = { enable = true; caldavUrl =
#      "https://<provider>/dav/"; caldavUser = "you@example.com"; }; on the
#      target host -- there is no sensible default URL, every provider's
#      CalDAV endpoint differs.
#   2. switch.
{
  mkServiceModule,
  mkCaptureLane,
  pkgs,
  lib,
  config,
  ...
}@args:
let
  username = config.sinnix.user.name;
  laneDir = "${config.sinnix.paths.activityRoot}/calendar";
  stateDir = "/realm/state/capture-calendar";
  secretPaths = config.sinnix.secrets.paths;
  cfg = config.sinnix.services.capture-calendar;

  vdirsyncerConfig = pkgs.writeText "sinnix-capture-calendar.vdirsyncer" ''
    [general]
    status_path = "${stateDir}/status/"

    # vdirsyncer pair/storage section names reject hyphens (confirmed live:
    # "contains invalid characters... only 0-9A-Za-z_ allowed") -- underscores
    # here, unlike every other identifier in this file.
    [pair capture_calendar]
    a = "capture_calendar_local"
    b = "capture_calendar_remote"
    collections = ["from b"]

    [storage capture_calendar_local]
    type = "filesystem"
    path = "${laneDir}/"
    fileext = ".ics"

    [storage capture_calendar_remote]
    type = "caldav"
    url = "${cfg.caldavUrl}"
    username = "${cfg.caldavUser}"
    password.fetch = ["command", "${pkgs.coreutils}/bin/cat", "${secretPaths.mail-app-password}"]
    read_only = true
  '';

  syncer = pkgs.writeShellApplication {
    name = "capture-calendar-sync";
    runtimeInputs = [
      pkgs.vdirsyncer
      pkgs.coreutils
    ];
    text = ''
      set -euo pipefail

      config_file="$1"
      lane_dir="$2"

      # Safe to run every pass: it only refreshes the pair's known-collection
      # list, never touches event content.
      vdirsyncer -c "$config_file" discover capture_calendar
      vdirsyncer -c "$config_file" sync capture_calendar

      date -u -Iseconds > "$lane_dir/.sinnix-last-sync"
    '';
  };
in
mkServiceModule (mkCaptureLane {
  name = "capture-calendar";
  description = "vdirsyncer CalDAV -> .ics calendar snapshot";
  inherit username laneDir;
  mode = "poll";
  captureName = "calendar";
  cadenceSeconds = cfg.intervalSec;
  staleAfterSeconds = 172800;
  execStart = "${syncer}/bin/capture-calendar-sync ${vdirsyncerConfig} ${laneDir}";
  environment = [ "TMPDIR=/tmp" ];
  privateTmp = true;
  tmpfilesRules = [
    "d ${laneDir} 0755 ${username} users -"
    "d ${stateDir} 0700 ${username} users -"
    "d ${stateDir}/status 0700 ${username} users -"
  ];
  writablePaths = [
    laneDir
    stateDir
  ];
  timer = {
    intervalSec = cfg.intervalSec;
    onBootSec = "5min";
    accuracySec = "10min";
  };
  unitDescription = "vdirsyncer CalDAV -> .ics snapshot pass";
  timerDescription = "Daily trigger for the calendar capture mirror";
  extraOptions = {
    caldavUrl = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "CalDAV principal/base URL. Must be set before enabling; no sensible default exists across providers.";
    };
    caldavUser = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "CalDAV username. Must be set before enabling.";
    };
    intervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 86400;
      description = "Seconds between sync passes -- daily by default, per the bead.";
    };
  };
  extraConfig = _: {
    assertions = [
      {
        assertion = cfg.caldavUrl != null && cfg.caldavUser != null;
        message = "sinnix.services.capture-calendar.enable requires caldavUrl and caldavUser to be set.";
      }
    ];
  };
}) args
