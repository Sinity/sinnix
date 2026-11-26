{ inputs, ... }:
{
  perSystem =
    { system, sinnixScriptRegistry, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      inherit (inputs.nixpkgs) lib;
      testLib = import ../test-lib.nix { inherit inputs lib; };
      snapshot = "sinnix-desktop-snapshot";
      restore = "sinnix-desktop-restore";
      graphical = "graphical-session.target";
      evaluated = testLib.evalTestSpec system (
        testLib.mkFeatureTest {
          name = "desktop-session";
          feature = "sinnix.machine.isDesktop";
          assertions =
            config:
            let
              user = config.systemd.user;
              timer = user.timers.${snapshot};
            in
            [
              {
                assertion =
                  timer.wantedBy == [ graphical ]
                  && timer.partOf == [ graphical ]
                  && timer.requisite == [ graphical ]
                  && timer.timerConfig.OnCalendar == "*:0/1";
                message = "Desktop snapshots must run once a minute only during the graphical session";
              }
              {
                assertion =
                  user.services.${snapshot}.partOf == [ graphical ]
                  && user.services.${snapshot}.requisite == [ graphical ]
                  && user.services.${restore}.wantedBy == [ graphical ]
                  && lib.elem "noctalia.service" user.services.${restore}.after
                  && lib.elem "${restore}.service" timer.after;
                message = "Restore must follow Noctalia and read the saved session before periodic capture";
              }
              (testLib.expect.persistedHomeDir config ".local/state/sinnix"
                "Desktop session snapshots must survive boot"
              )
            ];
        }
      );
      actual = evaluated.config.systemd.user;
      pythonWith =
        extras:
        pkgs.python3.withPackages (
          _:
          extras
          ++ [
            sinnixScriptRegistry.packageSet.sinnix-lib
            sinnixScriptRegistry.packageSet.sinnix-runtime
          ]
        );
      fixtureHyprctl = pkgs.writeShellScriptBin "hyprctl" "echo '[]'";
      fixtureAgentctl = pkgs.writeShellScriptBin "agentctl" "echo '[]'";
      dispatcher = import ../cli-dispatcher.nix {
        inherit lib pkgs;
        registry = { inherit (sinnixScriptRegistry.registry) sinnix-reboot; };
      };
    in
    {
      checks.desktop-session-suite =
        pkgs.runCommand "desktop-session-suite"
          {
            nativeBuildInputs = [
              (pythonWith [ pkgs.python3Packages.pytest ])
              pkgs.kitty
              pkgs.bash
            ];
          }
          ''
                mkdir -p scripts pkgs/sinnix-desktop-session/tests
                cp ${../../scripts/sinnix-desktop-session} scripts/sinnix-desktop-session
                cp ${../../scripts/sinnix-reboot} scripts/sinnix-reboot
                cp ${../../pkgs/sinnix-desktop-session/tests/test_restore.py} pkgs/sinnix-desktop-session/tests/test_restore.py
                export HOME="$TMPDIR/home"
                mkdir -m 700 "$HOME"
                python3 -m pytest -q pkgs/sinnix-desktop-session/tests
            ${dispatcher}/bin/sinnix reboot --help
                touch "$out"
          '';

      heavyChecks.desktop-session-vm = pkgs.testers.runNixOSTest {
        name = "desktop-session";
        nodes.machine =
          { ... }:
          {
            users.users.fixture = {
              isNormalUser = true;
              uid = 1000;
              linger = true;
            };
            virtualisation.memorySize = 1024;
            systemd.user.targets.fixture-graphical = {
              requires = [ graphical ];
              after = [ graphical ];
            };
            systemd.user.services.${snapshot} =
              let
                unit = actual.services.${snapshot};
              in
              {
                inherit (unit)
                  description
                  after
                  partOf
                  requisite
                  wantedBy
                  ;
                path = [
                  fixtureHyprctl
                  fixtureAgentctl
                  pkgs.systemd
                ];
                serviceConfig = unit.serviceConfig // {
                  ExecStart = "${pythonWith [ ]}/bin/python3 ${../../scripts/sinnix-desktop-session} snapshot";
                };
              };
            systemd.user.services.${restore} =
              let
                unit = actual.services.${restore};
              in
              {
                inherit (unit)
                  description
                  after
                  partOf
                  requisite
                  wantedBy
                  serviceConfig
                  ;
              };
            systemd.user.timers.${snapshot} =
              let
                unit = actual.timers.${snapshot};
              in
              {
                inherit (unit)
                  description
                  after
                  partOf
                  requisite
                  wantedBy
                  timerConfig
                  ;
              };
          };
        testScript = ''
          machine.wait_for_unit("user@1000.service")
          userctl = "runuser -u fixture -- env XDG_RUNTIME_DIR=/run/user/1000 systemctl --user"
          state = "/home/fixture/.local/state/sinnix/session"
          machine.fail(f"{userctl} start ${snapshot}.service")
          machine.fail(f"test -e {state}")
          machine.succeed(f"{userctl} start fixture-graphical.target")
          machine.wait_until_succeeds(f"grep -q no-previous-boot-snapshot {state}/restore.json")
          machine.wait_until_succeeds(f"test -n \"$(find {state} -maxdepth 1 -name 'snapshot-*.json' -print -quit)\"")
          machine.succeed(f"{userctl} is-active ${snapshot}.timer")
          journal = machine.succeed("journalctl --no-pager _SYSTEMD_USER_UNIT=${restore}.service")
          assert "No previous-boot desktop snapshot" in journal
          machine.succeed(f"{userctl} stop fixture-graphical.target ${graphical}")
          machine.wait_until_fails(f"{userctl} is-active ${snapshot}.timer")
          machine.fail(f"{userctl} start ${snapshot}.service")
        '';
      };
    };
}
