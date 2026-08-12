# MPRIS media-player capture
#
# Watches org.mpris.MediaPlayer2.* players over the user D-Bus session bus
# via `playerctl --follow` and appends sinnix-capture-v1 envelopes (player
# identity, title, artist, album, position, status) to the `mpris` capture
# lane on every track/status change, plus a periodic heartbeat while a
# player's PlaybackStatus is "Playing" -- long single-track listening
# sessions still carry position markers between track boundaries instead of
# going silent for the whole session. See pkgs/capture-mpris/monitor.py for
# the daemon and its rationale (why the playerctl follow format excludes
# position, why writes shell out to the sinnix-capture CLI).
{
  mkServiceModule,
  lib,
  pkgs,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  capturesRoot = config.sinnix.paths.capturesRoot;
  mprisDir = "${capturesRoot}/mpris";

  monitor = pkgs.writeTextFile {
    name = "capture-mpris-monitor";
    destination = "/bin/capture-mpris-monitor";
    executable = true;
    text = ''
      #!${pkgs.python3}/bin/python3
    ''
    + builtins.readFile ../../pkgs/capture-mpris/monitor.py;
  };
in
mkServiceModule {
  name = "capture-mpris";
  description = "MPRIS media-player track/status capture with playback heartbeat";
  extraOptions = {
    heartbeatIntervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 60;
      description = ''
        Seconds between heartbeat writes while a player's PlaybackStatus is
        "Playing". Keeps a position marker flowing during a single long
        track/stream instead of relying solely on track-boundary events.
      '';
    };
  };
  surface = {
    unit = "capture-mpris.service";
    manager = "user";
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = true;
    };
    captures = [
      {
        name = "mpris";
        path = mprisDir;
        eventDriven = true;
        # Media listening is optional and intermittent -- unlike shell
        # sessions or window tracking, a fully quiet week is a legitimate
        # "the operator didn't play anything" outcome, not a broken daemon.
        # Budget generously (7 days, matching the screenshot lane in
        # capture-registry.nix) so staleness only fires on genuine capture
        # failure, not on an ordinary media-quiet stretch.
        staleAfterSeconds = 604800;
      }
    ];
  };
  configFn =
    { cfg, config, ... }:
    {
      systemd.tmpfiles.rules = [
        "d ${mprisDir} 0755 ${username} users -"
      ];

      home-manager.users.${username} =
        { ... }:
        {
          systemd.user.services.capture-mpris = {
            Unit = {
              Description = "MPRIS media-player track/status capture with playback heartbeat";
              After = [ "graphical-session.target" ];
              PartOf = [ "graphical-session.target" ];
            };
            Service = lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "capture-mpris.service";
              overrides = {
                Type = "simple";
                ExecStart = "${monitor}/bin/capture-mpris-monitor --capture-root ${capturesRoot} --lane mpris --playerctl-bin ${pkgs.playerctl}/bin/playerctl --sinnix-capture-bin ${scriptPkgs.sinnix-capture}/bin/sinnix-capture --heartbeat-interval ${toString cfg.heartbeatIntervalSec}";
                Restart = "on-failure";
                RestartSec = "5s";
                NoNewPrivileges = true;
                ProtectSystem = "strict";
                ProtectHome = "read-only";
                ReadWritePaths = [ mprisDir ];
              };
            };
            Install.WantedBy = [ "graphical-session.target" ];
          };
        };
    };
} args
