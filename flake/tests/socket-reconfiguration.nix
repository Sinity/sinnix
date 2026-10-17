{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      overlay = import ../overlay/package/switch-to-configuration.nix { };
      patched = overlay pkgs pkgs;
      helper = pkgs.writeText "socket-reconfiguration-fixture.py" (
        builtins.readFile ./socket_reconfiguration_fixture.py
      );
      command = "${pkgs.python3}/bin/python3 ${helper}";
    in
    {
      checks.socket-reconfiguration-package = patched.switch-to-configuration-ng;
      heavyChecks.socket-reconfiguration-vm = pkgs.testers.runNixOSTest {
        name = "socket-reconfiguration";
        node.pkgsReadOnly = false;
        nodes.machine = { lib, ... }: {
          nixpkgs.overlays = [ overlay ];
          environment.systemPackages = [ pkgs.python3 ];
          virtualisation.memorySize = 1024;
          virtualisation.cores = 2;
          users.groups.vmone = { };
          users.groups.vmtwo = { };
          users.users.vmone = {
            isNormalUser = true;
            linger = true;
            group = "vmone";
          };
          users.users.vmtwo = {
            isSystemUser = true;
            group = "vmtwo";
          };
          systemd.sockets = {
            primary = {
              wantedBy = [ "sockets.target" ];
              listenStreams = [
                "127.0.0.1:24901"
                "/run/socket-reconfiguration/a.sock"
              ];
              socketConfig = {
                SocketUser = "vmone";
                SocketGroup = "vmone";
                SocketMode = "0660";
                RemoveOnStop = true;
              };
            };
            control = {
              wantedBy = [ "sockets.target" ];
              listenStreams = [ "127.0.0.1:25001" ];
            };
            accepted = {
              wantedBy = [ "sockets.target" ];
              listenStreams = [ "127.0.0.1:25101" ];
              socketConfig.Accept = true;
            };
          };
          systemd.services = {
            primary.serviceConfig = {
              ExecStart = "${command} activated";
              Sockets = [ "primary.socket" ];
            };
            control.serviceConfig = {
              ExecStart = "${command} activated";
              Sockets = [ "control.socket" ];
            };
            "accepted@".serviceConfig = {
              ExecStart = "${command} accepted";
              StandardInput = "socket";
              StandardOutput = "inherit";
            };
            hold-control.serviceConfig.ExecStart = "${command} hold 25001 /run/control-progress";
            hold-accepted.serviceConfig.ExecStart = "${command} hold 25101 /run/accepted-progress";
          };
          systemd.user.sockets.userfixture = {
            wantedBy = [ "sockets.target" ];
            listenStreams = [ "127.0.0.1:24911" ];
          };
          systemd.user.services.userfixture.serviceConfig = {
            ExecStart = "${command} activated";
            Sockets = [ "userfixture.socket" ];
          };
          specialisation = {
            moved.configuration.systemd.user.sockets.userfixture.listenStreams = lib.mkForce [
              "127.0.0.1:24912"
            ];
            moved.configuration.systemd.sockets = {
              primary = {
                listenStreams = lib.mkForce [
                  "127.0.0.1:24902"
                  "/run/socket-reconfiguration/b.sock"
                ];
                socketConfig = {
                  SocketUser = lib.mkForce "vmtwo";
                  SocketGroup = lib.mkForce "vmtwo";
                  SocketMode = lib.mkForce "0600";
                };
              };
              accepted.listenStreams = lib.mkForce [ "127.0.0.1:25201" ];
            };
            permissions.configuration.systemd.sockets.primary.socketConfig = {
              SocketUser = lib.mkForce "vmtwo";
              SocketGroup = lib.mkForce "vmtwo";
              SocketMode = lib.mkForce "0600";
            };
            protected.configuration = {
              systemd.services.primary.restartIfChanged = lib.mkForce false;
              systemd.sockets.primary.listenStreams = lib.mkForce [
                "127.0.0.1:24902"
                "/run/socket-reconfiguration/b.sock"
              ];
            };
            broken.configuration.systemd.sockets.primary.listenStreams = lib.mkForce [
              "/proc/socket-reconfiguration-invalid"
            ];
          };
        };
        testScript = ''
          from datetime import timedelta
          start_all()
          machine.wait_for_unit("multi-user.target")
          machine.wait_for_unit("primary.socket")
          original = machine.succeed("readlink -f /run/current-system").strip()
          uid = machine.succeed("id -u vmone").strip()
          machine.wait_for_unit(f"user@{uid}.service")
          machine.succeed(f"runuser -u vmone -- env XDG_RUNTIME_DIR=/run/user/{uid} systemctl --user is-active --quiet userfixture.socket")
          def activate(path, fails=False):
              status, output = machine.execute(f"{path}/bin/switch-to-configuration test 2>&1", timeout=timedelta(seconds=90))
              print(output)
              assert (status != 0) if fails else (status == 0), (status, output)
              return output
          def probe(address):
              reply = machine.succeed("${command} probe " + str(address)).strip()
              assert reply.endswith(":probe"), reply
              return reply.split(":")[0]
          def progress(name):
              return machine.succeed(f"cat /run/{name}-progress").strip().split()
          def continuous():
              for name in ["control", "accepted"]:
                  machine.succeed(f"systemctl is-active --quiet hold-{name}.service")
                  before, server = progress(name)
                  machine.wait_until_succeeds(f"test $(cut -d' ' -f1 /run/{name}-progress) -gt {before}", timeout=timedelta(seconds=10))
                  assert progress(name)[1] == continuity[name], (name, server, progress(name))
          machine.fail("systemctl is-active --quiet primary.service")
          machine.succeed("systemctl start hold-control.service hold-accepted.service")
          machine.wait_until_succeeds("test -s /run/control-progress -a -s /run/accepted-progress")
          continuity = {name: progress(name)[1] for name in ["control", "accepted"]}
          control_listener = machine.succeed("systemctl show control.socket -p ActiveEnterTimestampMonotonic --value").strip()
          activate(original + "/specialisation/moved")
          machine.succeed("test -S /run/socket-reconfiguration/b.sock")
          machine.fail("test -e /run/socket-reconfiguration/a.sock")
          assert machine.succeed("stat -c %a /run/socket-reconfiguration/b.sock").strip() == "600"
          assert machine.succeed("stat -c %U /run/socket-reconfiguration/b.sock").strip() == "vmtwo"
          moved_pid = probe(24902)
          moved_user_pid = probe(24912)
          machine.fail("${command} probe 24911")
          assert probe("/run/socket-reconfiguration/b.sock") == moved_pid
          machine.fail("${command} probe 24901")
          probe(25201)
          machine.fail("${command} probe 25101")
          continuous()
          assert machine.succeed("systemctl show control.socket -p ActiveEnterTimestampMonotonic --value").strip() == control_listener
          activate(original)
          base_pid = probe(24901)
          assert probe(24911) != moved_user_pid
          machine.fail("${command} probe 24912")
          assert base_pid != moved_pid
          machine.succeed(f"test ! -e /proc/{moved_pid}")
          machine.fail("${command} probe 24902")
          machine.fail("test -e /run/socket-reconfiguration/b.sock")
          continuous()
          activate(original + "/specialisation/permissions")
          assert machine.succeed("stat -c %a /run/socket-reconfiguration/a.sock").strip() == "600"
          assert machine.succeed("stat -c %U /run/socket-reconfiguration/a.sock").strip() == "vmtwo"
          machine.fail("runuser -u vmone -- ${command} probe /run/socket-reconfiguration/a.sock")
          machine.succeed("runuser -u vmtwo -- ${command} probe /run/socket-reconfiguration/a.sock")
          continuous()
          activate(original)
          protected_pid = probe(24901)
          output = activate(original + "/specialisation/protected", fails=True)
          assert "opts out of automatic restart" in output, output
          assert probe(24901) == protected_pid
          machine.fail("${command} probe 24902")
          continuous()
          activate(original + "/specialisation/broken", fails=True)
          continuous()
          activate(original)
          probe(24901)
          assert machine.succeed("stat -c %a /run/socket-reconfiguration/a.sock").strip() == "660"
          assert machine.succeed("stat -c %U /run/socket-reconfiguration/a.sock").strip() == "vmone"
          continuous()
        '';
      };
    };
}
