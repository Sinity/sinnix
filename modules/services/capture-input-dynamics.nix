# capture-input-dynamics: 1Hz aggregated pointer/keyboard timing features
#
# STRUCTURAL PRIVACY BOUNDARY -- read before touching this module or its
# collector. This lane observes libinput event TIMING ONLY, never keystroke
# CONTENT (keycodes/keysyms/text). Content capture is scribe-tap's job
# (hosts/sinnix-prime/input.nix's `keylog` lane, wired through
# interception-tools). This lane must remain structurally incapable of
# reconstructing what was typed:
#
#   - The collector (pkgs/capture-input-dynamics/collector.py) shells out to
#     `libinput debug-events` and parses only event TYPE, TIMESTAMP, and
#     press/release STATE off each line -- never the key-name/keycode
#     tokens. See that file's module docstring for the exact
#     token-by-token argument (which tokens are read vs. discarded) and
#     its pytest suite (pkgs/capture-input-dynamics/tests/) for a
#     mutation-style test that fails if a future change threads key
#     identity into the aggregated output.
#   - Aggregation happens before any per-key value could reach disk: raw
#     libinput lines never touch storage, only the derived 1Hz feature
#     window (counts + interval statistics + the focused-window
#     attribution from `hyprctl activewindow`) is written, via
#     `sinnix-capture write --lane input-dynamics`.
#
# DEPENDENCY STATUS (at authorship time): this module is written against
# the sinnix-mufn (pkgs/sinnix-capture writer/CLI, wired into
# `helpers.mkSinnixPackagesFor` as `scriptPkgs.sinnix-capture`) and
# sinnix-5o9z (`staleAfterSeconds` on the `sinnix.runtime.surfaces.*.captures`
# submodule in modules/runtime.nix) interfaces. Both were in flight in
# sibling worktrees, not yet merged, when this module was authored; it will
# not evaluate as part of the full flake until they land -- see sinnix-8k0t.
#
# Device access: `libinput debug-events` opens /dev/input/event* directly.
# NixOS's default udev rules tag those nodes `uaccess`, and systemd-logind
# grants the seat's active graphical session an ACL for its owning user --
# no dedicated "input" group membership is required as long as this runs
# as a systemd --user service tied to the user's active Hyprland session
# (`graphical-session.target`), which is why this is a user-manager surface
# rather than a system-level one.
{
  mkServiceModule,
  pkgs,
  lib,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  inherit (config.sinnix.paths) capturesRoot;
  laneDir = "${capturesRoot}/input-dynamics";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

  collector = pkgs.writeTextFile {
    name = "capture-input-dynamics";
    destination = "/bin/capture-input-dynamics";
    executable = true;
    text = ''
      #!${pkgs.python3}/bin/python3
    ''
    + builtins.readFile ../../pkgs/capture-input-dynamics/collector.py;
  };
in
mkServiceModule {
  name = "capture-input-dynamics";
  description = "Aggregated 1Hz pointer/keyboard timing features (event timing only -- never keystroke content)";
  surface = {
    unit = "sinnix-capture-input-dynamics.service";
    manager = "user";
    kind = "service";
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = true;
    };
    captures = [
      {
        name = "input-dynamics";
        path = laneDir;
        # The collector only flushes a window when it observed >=1 event
        # (see collector.py WindowAccumulator.has_activity) -- idle
        # stretches legitimately produce no writes, so this is
        # event-driven rather than a fixed cadence. staleAfterSeconds is
        # therefore the sentinel's only staleness signal for this lane;
        # 3600s matches the interception-tools keylog lane's budget
        # (hosts/sinnix-prime/input.nix), another bursty desktop-input
        # capture.
        eventDriven = true;
        staleAfterSeconds = 3600;
      }
    ];
  };
  configFn =
    { pkgs, lib, ... }:
    {
      systemd.tmpfiles.rules = [
        "d ${laneDir} 0700 ${username} users -"
      ];

      home-manager.users.${username} =
        { ... }:
        {
          systemd.user.services.sinnix-capture-input-dynamics = {
            Unit = {
              Description = "Aggregated input-dynamics timing capture (event timing only -- never keystroke content)";
              After = [ "graphical-session.target" ];
              PartOf = [ "graphical-session.target" ];
            };
            Service = lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "sinnix-capture-input-dynamics.service";
              overrides = {
                Type = "simple";
                ExecStart = lib.escapeShellArgs [
                  "${collector}/bin/capture-input-dynamics"
                  "--capture-root"
                  capturesRoot
                  "--libinput-bin"
                  "${pkgs.libinput}/bin/libinput"
                  "--hyprctl-bin"
                  "${pkgs.hyprland}/bin/hyprctl"
                  "--sinnix-capture-bin"
                  "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
                ];
                Restart = "on-failure";
                RestartSec = "5s";
                NoNewPrivileges = true;
                ProtectSystem = "strict";
                ProtectHome = "read-only";
                # Deliberately no PrivateDevices=true: this service's whole
                # purpose is reading real /dev/input/event* nodes via
                # libinput, granted through the logind seat ACL described
                # above.
                ReadWritePaths = [ laneDir ];
                UMask = "0077";
              };
            };
            Install.WantedBy = [ "graphical-session.target" ];
          };
        };
    };
} args
