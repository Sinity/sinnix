# Continuous Wayland PRIMARY-selection capture lane
#
# `wl-paste --primary --watch` runs one long-lived user service that
# invokes a small event script on every PRIMARY-selection change (the
# X11-style "select-to-copy" buffer, distinct from the normal clipboard --
# populated by highlighting text, no explicit copy action, traditionally
# pasted with middle-click). The script hands its own wl-paste invocation
# to `sinnix-capture selection`, which owns everything shared with the
# clipboard lane: MIME preference, text/binary classification, the
# content-addressed blob store, the payload and the envelope write.
# PRIMARY is almost always plain text but can carry the same rich formats
# an explicit copy would.
#
# This lane's own policy is a debounce, and deliberately not content
# de-duplication: PRIMARY changes on every new selection during ordinary
# reading, and that volume/repetition is itself the signal (what the
# operator was reading and re-reading), not noise to suppress.
#
# The debounce exists because toolkits re-offer PRIMARY on every internal
# extend step rather than once at gesture end, so one logical selection
# fires the watch command several times within tens of milliseconds.
# `debounceMs` collapses each burst into one capture of the settled
# selection; two separate selections a few seconds apart still both land.
{
  mkServiceModule,
  mkCaptureLane,
  lib,
  pkgs,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  captureCli = scriptPkgs.sinnix-capture;

  laneDir = "${config.sinnix.paths.activityRoot}/primary";
  blobDir = "${laneDir}/blobs";
  stateDir = "${config.sinnix.paths.stateRoot}/cursors/capture-primary";

  primaryWatch = pkgs.writeShellApplication {
    name = "sinnix-capture-primary-watch";
    runtimeInputs = [
      pkgs.wl-clipboard
      pkgs.hyprland
      captureCli
    ];
    text = ''
      set -euo pipefail

      # Read from environment (set on the systemd unit below) rather than
      # baking a path in at build time -- keeps this script runnable
      # standalone against a fixture capture root (see flake/tests).
      capture_root="''${SINNIX_CAPTURE_ROOT:?SINNIX_CAPTURE_ROOT must be set}"
      state_dir="''${SINNIX_CAPTURE_PRIMARY_STATE_DIR:?SINNIX_CAPTURE_PRIMARY_STATE_DIR must be set}"
      debounce_ms="''${SINNIX_CAPTURE_PRIMARY_DEBOUNCE_MS:?SINNIX_CAPTURE_PRIMARY_DEBOUNCE_MS must be set}"

      # Commands are named rather than resolved to store paths, so a
      # fixture can substitute its own wl-paste/hyprctl on PATH.
      exec sinnix-capture selection \
        --capture-root "$capture_root" \
        --lane primary \
        --list-command "wl-paste --primary --list-types" \
        --paste-command "wl-paste --primary --no-newline --type" \
        --window-command "hyprctl activewindow -j" \
        --debounce-ms "$debounce_ms" \
        --debounce-state "$state_dir/last-trigger"
    '';
  };
  cfg = config.sinnix.services.capture-primary;
in
mkServiceModule (mkCaptureLane {
  name = "capture-primary";
  description = "Continuous Wayland PRIMARY-selection capture lane (wl-paste --primary --watch -> sinnix-capture)";
  extraOptions = {
    debounceMs = lib.mkOption {
      type = lib.types.ints.positive;
      default = 400;
      description = ''
        Milliseconds to wait after a PRIMARY-selection change before
        capturing, collapsing the multi-fire bursts a single selection
        gesture produces (see module header for the empirical basis) into
        one write of the settled selection.
      '';
    };
  };
  inherit username laneDir;
  mode = "stream";
  captureName = "primary";
  eventDriven = true;
  # PRIMARY activity depends entirely on whether the operator is doing
  # text-heavy reading/selecting -- genuinely intermittent, so a week-long
  # budget, same as the clipboard and mpris lanes.
  staleAfterSeconds = 604800;
  tmpfilesRules = [
    "d ${laneDir} 0700 ${username} users -"
    "d ${blobDir} 0700 ${username} users -"
    "d ${stateDir} 0700 ${username} users -"
  ];
  writablePaths = [
    laneDir
    blobDir
    stateDir
  ];
  execStart = "${pkgs.wl-clipboard}/bin/wl-paste --primary --watch ${primaryWatch}/bin/sinnix-capture-primary-watch";
  environment = [
    "SINNIX_CAPTURE_ROOT=${config.sinnix.paths.activityRoot}"
    "SINNIX_CAPTURE_PRIMARY_STATE_DIR=${stateDir}"
    "SINNIX_CAPTURE_PRIMARY_DEBOUNCE_MS=${toString cfg.debounceMs}"
  ];
  privateTmp = true;
  umask = "0077";
  unitDescription = "Wayland PRIMARY-selection capture lane";
}) args
