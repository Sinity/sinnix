# Continuous Wayland clipboard capture lane
#
# `wl-paste --watch` runs one long-lived user service (this host's
# compositor is Hyprland/wlroots) that invokes a small event script on
# every clipboard selection change. The script hands its own wl-paste
# invocation to `sinnix-capture selection`, which owns everything shared
# with the PRIMARY lane: MIME preference, text/binary classification, the
# content-addressed blob store, the payload and the envelope write.
#
# This lane's own policy is de-duplication of consecutive identical
# content. wl-paste --watch fires on every selection-change protocol
# event, not only on content changes -- this host also runs wl-clip-persist
# (clipboard persistence across window close, see desktop/base.nix), whose
# re-offers are exactly the kind of no-op re-selection that would otherwise
# double-write.
#
# This lane captures everything copied, secrets included, by design:
# sensitivity is handled at consumption time. Do not add redaction here.
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

  laneDir = "${config.sinnix.paths.activityRoot}/clipboard";
  blobDir = "${laneDir}/blobs";
  stateDir = "${config.sinnix.paths.stateRoot}/cursors/capture-clipboard";

  clipboardWatch = pkgs.writeShellApplication {
    name = "sinnix-capture-clipboard-watch";
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
      state_dir="''${SINNIX_CAPTURE_CLIPBOARD_STATE_DIR:?SINNIX_CAPTURE_CLIPBOARD_STATE_DIR must be set}"

      # Commands are named rather than resolved to store paths, so a
      # fixture can substitute its own wl-paste/hyprctl on PATH.
      exec sinnix-capture selection \
        --capture-root "$capture_root" \
        --lane clipboard \
        --list-command "wl-paste --list-types" \
        --paste-command "wl-paste --no-newline --type" \
        --window-command "hyprctl activewindow -j" \
        --dedup-state "$state_dir/last-selection"
    '';
  };
in
mkServiceModule (mkCaptureLane {
  name = "capture-clipboard";
  defaultOnDesktop = true;
  description = "Continuous Wayland clipboard capture lane (wl-paste --watch -> sinnix-capture)";
  inherit username laneDir;
  mode = "stream";
  captureName = "clipboard";
  eventDriven = true;
  # Genuinely bursty/idle-tolerant: an operator can go a full week without
  # copying anything new (travel, laptop-only stretches).
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
  execStart = "${pkgs.wl-clipboard}/bin/wl-paste --watch ${clipboardWatch}/bin/sinnix-capture-clipboard-watch";
  environment = [
    "SINNIX_CAPTURE_ROOT=${config.sinnix.paths.activityRoot}"
    "SINNIX_CAPTURE_CLIPBOARD_STATE_DIR=${stateDir}"
  ];
  privateTmp = true;
  umask = "0077";
  unitDescription = "Wayland clipboard capture lane";
}) args
