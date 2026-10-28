# Real signal delivery in a small guest. Host meminfo and PSI readings are
# deterministic fixtures; this does not claim real swap/IO-stall reproduction.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      inherit (pkgs) lib;
      host = inputs.self.nixosConfigurations.sinnix-prime.config;
      shim = pkgs.runCommand "earlyoom-vm-meminfo-shim" { nativeBuildInputs = [ pkgs.stdenv.cc ]; } ''
        mkdir -p "$out/lib"
        $CC -shared -fPIC -Wall -Wextra -Werror ${./earlyoom_meminfo.c} -o "$out/lib/meminfo.so" -ldl
      '';
      fixture = pkgs.writeText "earlyoom-vm-fixture.py" (builtins.readFile ./earlyoom_vm_fixture.py);
      fixtureEnvironment = {
        LD_PRELOAD = "${shim}/lib/meminfo.so";
        EARLYOOM_TEST_MEMINFO = "/run/earlyoom-fixtures/meminfo";
        EARLYOOM_PSI_PATH = "/run/earlyoom-fixtures/pressure";
      };
      victim = name: size: slice: {
        serviceConfig = {
          ExecStart = "${pkgs.python3}/bin/python3 ${fixture} victim ${name} ${toString size} %t/${name}.ready";
          OOMScoreAdjust = 1000;
          Slice = slice;
          TimeoutStopSec = "1s";
        };
      };
    in
    {
      heavyChecks.earlyoom-emergency-vm = pkgs.testers.runNixOSTest {
        name = "earlyoom-emergency";
        nodes.machine =
          { lib, ... }:
          {
            virtualisation.memorySize = 1024;
            virtualisation.cores = 2;
            users.users.fixture = {
              isNormalUser = true;
              uid = 1000;
              linger = true;
            };
            environment.systemPackages = [ pkgs.python3 ];
            services.earlyoom = {
              enable = true;
              inherit (host.services.earlyoom) package enableNotifications;
            };
            systemd.services.earlyoom = {
              wantedBy = lib.mkForce [ ];
              environment = fixtureEnvironment // {
                EARLYOOM_ARGS = lib.mkForce host.systemd.services.earlyoom.environment.EARLYOOM_ARGS;
              };
            };
            # Replay the previous threshold with the same executable. The
            # current case below uses the upstream hardened earlyoom unit.
            systemd.services.earlyoom-previous = {
              serviceConfig.ExecStart = "${host.services.earlyoom.package}/bin/earlyoom $EARLYOOM_ARGS";
              path = [ pkgs.dbus ];
              environment = fixtureEnvironment // {
                EARLYOOM_ARGS =
                  lib.replaceStrings [ "-m5,5" ] [ "-m5" ]
                    host.systemd.services.earlyoom.environment.EARLYOOM_ARGS;
              };
            };
            systemd.user.slices.agent-tool.sliceConfig = host.systemd.user.slices.agent-tool.sliceConfig;
            systemd.user.services = {
              fixture-runaway = victim "fixture-agent" 16 "agent-tool.slice";
              fixture-protected = victim "kitty" 32 "app.slice";
            };
          };
        testScript = ''
          import json
          import time

          start_all()
          machine.wait_for_unit("multi-user.target")
          machine.wait_for_unit("user@1000.service")
          user = "runuser -u fixture -- env XDG_RUNTIME_DIR=/run/user/1000 systemctl --user"
          machine.succeed("mkdir -p /run/earlyoom-fixtures")
          machine.succeed("printf 'MemTotal: 1000000 kB\\nMemAvailable: 49000 kB\\nAnonPages: 800000 kB\\nSwapTotal: 400000 kB\\nSwapFree: 0 kB\\n' > /run/earlyoom-fixtures/meminfo")
          machine.succeed("printf 'some avg10=3.00 avg60=0.00 avg300=0.00 total=1\\nfull avg10=3.00 avg60=0.00 avg300=0.00 total=1\\n' > /run/earlyoom-fixtures/pressure")
          machine.succeed(f"{user} start fixture-runaway.service fixture-protected.service")
          machine.wait_until_succeeds("test -f /run/user/1000/fixture-agent.ready -a -f /run/user/1000/kitty.ready")
          runaway = machine.succeed("cat /run/user/1000/fixture-agent.ready").strip()
          protected = machine.succeed("cat /run/user/1000/kitty.ready").strip()
          # The protected process would win the normal oom_score ranking.
          scores = [int(machine.succeed(f"cat /proc/{pid}/oom_score")) for pid in (runaway, protected)]
          assert scores[1] > scores[0], scores
          assert "/agent-tool.slice/" in machine.succeed(f"cat /proc/{runaway}/cgroup")

          with subtest("calm pressure suppresses real kills"):
              machine.succeed("systemctl start earlyoom.service")
              machine.wait_until_succeeds("journalctl -u earlyoom.service -o cat --no-pager | grep -q 'not killing'")
              for unit in ("fixture-runaway.service", "fixture-protected.service"):
                  machine.succeed(f"{user} is-active --quiet {unit}")
              machine.succeed("systemctl stop earlyoom.service")

          machine.succeed("printf 'some avg10=25.00 avg60=0.00 avg300=0.00 total=1\\nfull avg10=25.00 avg60=0.00 avg300=0.00 total=1\\n' > /run/earlyoom-fixtures/pressure")
          with subtest("previous policy leaves the TERM-resistant victim alive"):
              machine.succeed("systemctl start earlyoom-previous.service")
              machine.wait_until_succeeds(f"journalctl -u earlyoom-previous.service -o cat --no-pager | grep -q 'process {runaway} did not exit'", timeout=20)
              for unit in ("fixture-runaway.service", "fixture-protected.service"):
                  machine.succeed(f"{user} is-active --quiet {unit}")
              old_log = machine.succeed("journalctl -u earlyoom-previous.service -o cat --no-pager")
              assert f"sending SIGTERM to process {runaway}" in old_log, old_log
              assert "sending SIGKILL" not in old_log, old_log
              machine.succeed("systemctl stop earlyoom-previous.service")

          with subtest("current policy kills the tool and preserves the avoided process"):
              machine.succeed(f"systemd-run --unit=fixture-recovery ${pkgs.python3}/bin/python3 ${fixture} recover {runaway} /run/earlyoom-fixtures /run/fixture-recovery.ready")
              machine.wait_until_succeeds("test -f /run/fixture-recovery.ready")
              started = time.monotonic()
              machine.succeed("systemctl start earlyoom.service")
              machine.wait_until_fails(f"{user} is-active --quiet fixture-runaway.service", timeout=15)
              elapsed = time.monotonic() - started
              machine.succeed("systemctl stop earlyoom.service")
              machine.succeed(f"{user} is-active --quiet fixture-protected.service")
              status = machine.succeed(f"{user} show fixture-runaway.service -p ExecMainCode -p ExecMainStatus -p Result")
              assert "ExecMainStatus=9" in status, status
              assert "Result=signal" in status, status
              current_log = machine.succeed("journalctl -u earlyoom.service -o cat --no-pager")
              assert f"sending SIGKILL to process {runaway}" in current_log, current_log
              assert f"sending SIGKILL to process {protected}" not in current_log, current_log
              machine.succeed("systemctl show fixture-recovery.service -p ExecMainStatus --value | grep -x 0")
              print(json.dumps({"synthetic_pressure": True, "actual_signal": "SIGKILL", "tool_killed": True, "avoided_process_survived": True, "seconds": elapsed}))

          machine.succeed(f"{user} kill --signal=SIGKILL fixture-protected.service")
          machine.copy_from_machine("/run/earlyoom-fixtures", "sensors")
          machine.succeed("journalctl -u earlyoom.service -u earlyoom-previous.service --no-pager > /run/earlyoom-journal.log")
          machine.copy_from_machine("/run/earlyoom-journal.log")
        '';
      };
    };
}
