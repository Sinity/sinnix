{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      lib = inputs.nixpkgs.lib;
      testLib = import ../test-lib.nix { inherit inputs lib; };
      privacy = testLib.evalTestSpec system {
        name = "capture-lane-privacy";
        modules = [
          testLib.mountTmpfsRoots
          testLib.baseTestConfig
          {
            sinnix.services.terminal-capture.enable = true;
            sinnix.services.capture-kitty-scrollback.enable = true;
            sinnix.services.capture-mpris.enable = true;
            sinnix.services.capture-audio.enable = true;
            sinnix.services.capture-netflow.enable = true;
            sinnix.services.xiaomi-witness.enable = true;
            sinnix.services.video-resolve.enable = true;
            sinnix.services.url-ledger.enable = true;
            sinnix.services.lynchpin.enable = true;
            sinnix.features.desktop.browser.enable = true;
            sinnix.services.steering.enable = true;
            sinnix.services.sandbox-audit.enable = true;
            sinnix.services.stt.enable = true;
            sinnix.services.hub.enable = true;
            sinnix.services.tailscale.enable = true;
            sinnix.services.ops-reducer.enable = true;
          }
        ];
        assertions = config: [
          {
            assertion =
              let
                rules = builtins.filter (rule: lib.hasPrefix "d /realm/worktree " rule) config.systemd.tmpfiles.rules;
                expected = "d /realm/worktree 0700 ${config.sinnix.user.name} users -";
              in
              rules != [ ] && builtins.all (rule: rule == expected) rules;
            message = "Shared worktrees must retain an owner-only entrance before any checkout producer runs.";
          }
          {
            assertion = builtins.elem "d ${config.sinnix.paths.activityRoot}/shared/ranking 0700 ${config.sinnix.user.name} ${config.users.users.${config.sinnix.user.name}.group} -" config.systemd.tmpfiles.rules;
            message = "Raw ranking evidence must have an owner-only entrance.";
          }
          {
            assertion =
              builtins.all (name: config.systemd.user.services.${name}.serviceConfig.UMask == "0077")
                [
                  "sinnix-steering-morning"
                  "sinnix-steering-evening"
                  "sinnix-steering-export"
                ];
            message = "Steering jobs must create owner-only evidence.";
          }
          {
            assertion = config.systemd.services.sinnix-url-ledger.serviceConfig.UMask == "0077";
            message = "URL evidence jobs must create owner-only output.";
          }
          {
            assertion =
              config.home-manager.users.${config.sinnix.user.name}.systemd.user.services.sinnix-nav-capture.Service.UMask
              == "0077";
            message = "Browser capture must create owner-only output.";
          }
          {
            assertion =
              builtins.all
                (
                  path:
                  builtins.elem "d ${path} 0700 ${config.sinnix.user.name} ${config.sinnix.user.name} -" config.systemd.tmpfiles.rules
                )
                [
                  config.sinnix.paths.capturePaths.browser-nav-edges
                  config.sinnix.paths.capturePaths.reading-stack
                ];
            message = "Browser evidence must retain private entrances owned by its writer.";
          }
          {
            assertion = config.systemd.services.sinnix-stt-lake.serviceConfig.UMask == "0077";
            message = "Transcript writers must create owner-only output.";
          }
          {
            assertion = config.systemd.services.sinnix-video-resolve.serviceConfig.UMask == "0077";
            message = "Video recovery writers must create owner-only output.";
          }
          {
            assertion = config.systemd.user.services.sinnix-xiaomi-witness.serviceConfig.UMask == "0077";
            message = "Health witness writers must create owner-only output.";
          }
          {
            assertion = config.systemd.services.sinnix-capture-netflow.serviceConfig.UMask == "0077";
            message = "System capture writers must create owner-only output.";
          }
          {
            assertion =
              config.systemd.user.services.sinnix-capture-kitty-scrollback.serviceConfig.UMask == "0077";
            message = "Poll captures must create owner-only output.";
          }
          {
            assertion =
              config.home-manager.users.${config.sinnix.user.name}.systemd.user.services.sinnix-capture-mpris.Service.UMask
              == "0077";
            message = "Stream captures must create owner-only output.";
          }
          {
            assertion =
              builtins.all
                (
                  path:
                  let
                    rules = builtins.filter (rule: lib.hasPrefix "d ${path} " rule) config.systemd.tmpfiles.rules;
                    expected = "d ${path} 0700 ${config.sinnix.user.name} users -";
                  in
                  rules != [ ] && builtins.all (rule: rule == expected) rules
                )
                [
                  config.sinnix.paths.capturePaths.webhistory
                  config.sinnix.paths.capturePaths.url-ledger
                  config.sinnix.paths.capturePaths.irc
                  config.sinnix.paths.capturePaths.shell
                  config.sinnix.paths.capturePaths.steering
                  config.sinnix.paths.capturePaths.audit
                  config.sinnix.paths.capturePaths.activitywatch
                  "${config.sinnix.paths.capturePaths.activitywatch}/raw"
                  config.sinnix.paths.capturePaths.screenshot
                  "${config.sinnix.paths.capturePaths.screenshot}/mpv"
                  config.sinnix.paths.capturePaths.asciinema
                  config.sinnix.paths.capturePaths.kitty-scrollback
                  config.sinnix.paths.capturePaths.mpris
                  config.sinnix.paths.capturePaths.audio
                  "${config.sinnix.paths.capturePaths.audio}/raw"
                  "${config.sinnix.paths.capturePaths.audio}/archive"
                  config.sinnix.paths.capturePaths.audio-devices
                  config.sinnix.paths.capturePaths.audio-topology
                  config.sinnix.paths.capturePaths.audio-index
                  config.sinnix.paths.capturePaths.transcripts
                  "${config.sinnix.paths.machineRoot}/netflow"
                  "/realm/health/xiaomi-cloud"
                  "${config.sinnix.paths.stateRoot}/sinnix-phone"
                  "${config.sinnix.paths.stateRoot}/sinnix-phone/inbox"
                  "${config.sinnix.paths.stateRoot}/sinnix-phone/inbox/receipts"
                  "${config.sinnix.paths.stateRoot}/sinnix-phone/inbox/notify"
                  "${config.sinnix.paths.stateRoot}/sinnix-phone/inbox/decks"
                  "${config.sinnix.paths.stateRoot}/sinnix-phone/tokens"
                ];
            message = "Private capture entrances must be owner-only.";
          }
        ];
      };
      sinnix-lib = pkgs.callPackage ../../pkgs/sinnix-lib/pkg.nix { };
      python = pkgs.python3.withPackages (ps: [
        sinnix-lib
        ps.dbus-next
      ]);
    in
    {
      # Exercise both factory routes through their real unit renderers.
      # Explicit lane overrides must not hide a regression in the defaults.
      checks.capture-lane-privacy =
        assert builtins.seq privacy true;
        pkgs.runCommand "capture-lane-privacy-check" { } ''touch "$out"'';
      checks.capture-router =
        pkgs.runCommand "capture-router-check"
          {
            nativeBuildInputs = [
              pkgs.python3
              pkgs.bash
              pkgs.coreutils
              pkgs.gawk
              pkgs.gnused
              pkgs.gnugrep
              pkgs.jq
            ];
            ROUTER_PERIODS_SCRIPT = ../../pkgs/capture-router/remote-periods.sh;
            ROUTER_POLL_SCRIPT = ../../pkgs/capture-router/poll.sh;
            ROUTER_REMOTE_POLL_SCRIPT = ../../pkgs/capture-router/remote-poll.sh;
          }
          ''
            python3 ${../../pkgs/capture-router/tests/test_periods.py}
            touch "$out"
          '';
      checks.kitty-scrollback =
        pkgs.runCommand "kitty-scrollback-capture-check"
          {
            nativeBuildInputs = [
              pkgs.python3
              pkgs.bash
              pkgs.coreutils
              pkgs.findutils
              pkgs.hostname
              pkgs.jq
              pkgs.gnused
            ];
            KITTY_CAPTURE_SCRIPT = ../../scripts/kitty-scrollback-capture;
          }
          ''
            python3 ${../../scripts/tests/test_kitty_scrollback_capture.py}
            touch "$out"
          '';
      checks.capture-mpris =
        pkgs.runCommand "capture-mpris-check"
          {
            nativeBuildInputs = [
              python
              pkgs.dbus
            ];
            PLAYERCTL_BIN = "${pkgs.playerctl}/bin/playerctl";
          }
          ''
            dbus-run-session --config-file=${pkgs.dbus}/share/dbus-1/session.conf -- python3 -m unittest discover -v \
              -s ${../../pkgs/capture-mpris} -p 'test_monitor.py'
            touch "$out"
          '';
    };
}
