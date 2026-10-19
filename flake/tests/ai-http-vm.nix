# Keep this lifecycle test isolated from workstation applications and weights.
# The actual activation module and upstream Caddy units run unchanged. Only
# the CLI package (not used here) and registry input are synthetic.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      inherit (pkgs) lib;
      fixture = name: publicPort: backendPort: {
        unit = "${name}.service";
        ai = {
          backendKind = "native";
          requiresCuda = false;
          browserRequests = "loopback";
        };
        activation = {
          mode = "socket-proxy";
          publicEndpoint = "127.0.0.1:${toString publicPort}";
          backendEndpoint = "127.0.0.1:${toString backendPort}";
          idleTimeout = "3s";
          readinessTimeout = 10;
          exclusiveResource = "fixture-gpu";
        };
      };
      backendSource = pkgs.writeText "ai-http-fake-backend.py" (
        builtins.readFile ./ai_http_fake_backend.py
      );
      pinSource = pkgs.writeText "ai-http-fixture-pin.py" ''
        import socket
        with socket.socket(socket.AF_UNIX) as connection:
            connection.connect("/run/sinnix-ai/fixture-one-proxy.sock")
            connection.recv(1)
      '';
      backend = name: port: {
        serviceConfig.ExecStart = "${pkgs.python3}/bin/python3 ${backendSource} ${toString port} /run/${name}-starts";
      };
    in
    {
      heavyChecks.ai-http-activation-vm = pkgs.testers.runNixOSTest {
        name = "ai-http-activation";
        nodes.machine = { lib, ... }: {
          imports = [ ../../modules/services/ai-control.nix ];
          options.sinnix.user.name = lib.mkOption {
            type = lib.types.str;
            default = "fixture";
          };
          options.sinnix.runtime.units = lib.mkOption {
            type = lib.types.attrsOf lib.types.anything;
            default = { };
          };
          config = {
            _module.args.helpers.mkSinnixPackagesFor = _: { sinnix-ai = pkgs.emptyDirectory; };
            sinnix.runtime.units = {
              fixture-one = fixture "fixture-one" 24821 24822;
              fixture-two = fixture "fixture-two" 24823 24824;
              fixture-native = lib.recursiveUpdate (fixture "fixture-native" 24825 24826) {
                ai.browserRequests = "native-only";
                activation.exclusiveResource = null;
                activation.consumers = [ { unit = "fixture-consumer"; } ];
              };
            };
            systemd.services = {
              fixture-one = backend "fixture-one" 24822;
              fixture-two = backend "fixture-two" 24824;
              fixture-native = backend "fixture-native" 24826;
              fixture-consumer.serviceConfig = {
                Type = "oneshot";
                ExecStart = "${pkgs.curl}/bin/curl --fail --max-time 15 -sS http://127.0.0.1:24825/";
              };
            };
            users.users.fixture.isNormalUser = true;
            virtualisation.memorySize = 1024;
            virtualisation.cores = 2;
            environment.systemPackages = [
              pkgs.curl
              pkgs.python3
            ];
          };
        };
        testScript =
          { nodes, ... }:
          let
            socketOf = proxy: lib.head nodes.machine.systemd.services.${proxy}.serviceConfig.Sockets;
          in
          ''
            start_all()
            machine.wait_for_unit("caddy.service")
            machine.wait_for_unit("${socketOf "fixture-one-proxy"}")
            machine.fail("systemctl is-active --quiet fixture-one.service")
            machine.fail("test -e /run/fixture-one-starts")
            # A connection by itself is harmless. An incomplete, foreign POST
            # must return before it gets a body or starts the backend.
            machine.succeed("python3 - <<'PY'\nimport socket\ns=socket.create_connection(('127.0.0.1',24821),timeout=2);s.close()\ns=socket.create_connection(('127.0.0.1',24821),timeout=2)\ns.sendall(b'POST / HTTP/1.1\\r\\nHost: 127.0.0.1:24821\\r\\nOrigin: https://foreign.invalid\\r\\nContent-Length: 1000000\\r\\n\\r\\n')\nassert b'403' in s.recv(4096);s.close()\nPY")
            machine.fail("test -e /run/fixture-one-starts")
            machine.fail("systemctl is-active --quiet fixture-one.service")
            machine.succeed("test $(stat -c %a /run/sinnix-ai/fixture-one-proxy.sock) = 660")
            machine.succeed("test $(stat -c %U /run/sinnix-ai/fixture-one-proxy.sock) = fixture")
            assert not machine.succeed("ss -H -ltn 'sport = :2019'").strip()
            machine.succeed("systemctl daemon-reexec")
            # Manual backend startup must pull in an actual listening socket,
            # not a socket-proxyd process with no inherited file descriptors.
            machine.succeed("systemctl start fixture-one.service")
            machine.wait_for_unit("fixture-one-proxy.service")
            machine.succeed("test $(wc -l < /run/fixture-one-starts) = 1")
            assert "native fixture response" in machine.succeed("curl --fail --max-time 15 -sS http://127.0.0.1:24821/")
            machine.wait_until_fails("systemctl is-active --quiet fixture-one.service", timeout=15)
            assert "native fixture response" in machine.succeed("curl --fail --max-time 15 -sS http://127.0.0.1:24821/")
            machine.succeed("test $(wc -l < /run/fixture-one-starts) = 2")
            machine.wait_until_fails("systemctl is-active --quiet fixture-one.service", timeout=15)
            machine.fail("systemctl is-active --quiet fixture-one-proxy.service")
            # Admission persists after idle-out and does not restart the model.
            assert machine.succeed("curl -s -o /dev/null -w '%{http_code}' -H 'Origin: null' http://127.0.0.1:24821/").strip() == "403"
            machine.succeed("test $(wc -l < /run/fixture-one-starts) = 2")
            # The operator can deliberately hold the private socket. Its
            # transient systemd lifetime releases the native pin automatically.
            machine.succeed("systemd-run --unit=fixture-pin --property=User=fixture --property=RuntimeMaxSec=6s ${pkgs.python3}/bin/python3 ${pinSource}")
            machine.wait_for_unit("fixture-one.service")
            import time
            time.sleep(4)
            machine.succeed("systemctl is-active --quiet fixture-one.service")
            machine.wait_until_fails("systemctl is-active --quiet fixture-pin.service", timeout=10)
            machine.wait_until_fails("systemctl is-active --quiet fixture-one.service", timeout=15)
            machine.succeed("test $(wc -l < /run/fixture-one-starts) = 3")
            machine.succeed("curl --no-buffer -sS http://127.0.0.1:24821/hold </dev/null >/run/held-stream 2>/run/held-errors &")
            machine.wait_until_succeeds("grep -q 'still running' /run/held-stream")
            machine.succeed("systemctl is-active --quiet fixture-one.service")
            assert "native fixture response" in machine.succeed("curl --fail --max-time 15 -sS http://127.0.0.1:24823/")
            machine.fail("systemctl is-active --quiet fixture-one.service")
            machine.fail("systemctl is-active --quiet fixture-one-proxy.service")
            machine.succeed("test $(wc -l < /run/fixture-one-starts) = 4")
            machine.succeed("test $(wc -l < /run/fixture-two-starts) = 1")
            machine.wait_until_fails("systemctl is-active --quiet fixture-two.service", timeout=15)
            machine.succeed("systemctl reload caddy.service")
            assert machine.succeed("curl -s -o /dev/null -w '%{http_code}' -H 'Origin: null' http://127.0.0.1:24823/").strip() == "403"
            machine.succeed("test $(wc -l < /run/fixture-two-starts) = 1")
            machine.succeed("curl --no-buffer -sS http://127.0.0.1:24823/hold </dev/null >/run/held-two 2>/run/held-two-errors &")
            machine.wait_until_succeeds("grep -q 'still running' /run/held-two")
            previous_pid = machine.succeed("systemctl show fixture-two.service -p MainPID --value").strip()
            machine.succeed("systemctl restart ${socketOf "fixture-two-proxy"}")
            # A deliberate socket restart may restart its active dependent.
            # It must release the old backend and serve through the new socket.
            assert "native fixture response" in machine.succeed("curl --fail --max-time 15 -sS http://127.0.0.1:24823/")
            current_pid = machine.succeed("systemctl show fixture-two.service -p MainPID --value").strip()
            assert previous_pid != current_pid, (previous_pid, current_pid)
            machine.succeed(f"test ! -e /proc/{previous_pid}")
            machine.succeed("test $(wc -l < /run/fixture-two-starts) = 3")
            machine.wait_until_fails("systemctl is-active --quiet fixture-two.service", timeout=15)
            assert machine.succeed("curl -s -o /dev/null -w '%{http_code}' -H 'Origin: null' http://127.0.0.1:24823/").strip() == "403"
            machine.succeed("test $(wc -l < /run/fixture-two-starts) = 3")
            # Match the native-only STT receiver before starting its backend,
            # including a nominally same-origin browser request.
            assert machine.succeed("curl -s -o /dev/null -w '%{http_code}' -H 'Origin: http://127.0.0.1:24825' http://127.0.0.1:24825/").strip() == "403"
            assert machine.succeed("curl -s -o /dev/null -w '%{http_code}' -H 'Sec-Fetch-Site: same-origin' http://127.0.0.1:24825/").strip() == "403"
            machine.fail("test -e /run/fixture-native-starts")
            assert "native fixture response" in machine.succeed("curl --fail --max-time 15 -sS http://127.0.0.1:24825/")
            machine.succeed("test $(wc -l < /run/fixture-native-starts) = 1")
            machine.wait_until_fails("systemctl is-active --quiet fixture-native.service", timeout=15)
            machine.succeed("systemctl stop caddy.service")
            machine.succeed("systemctl start fixture-consumer.service")
            machine.succeed("systemctl is-active --quiet caddy.service")
            machine.succeed("test $(wc -l < /run/fixture-native-starts) = 2")
            machine.wait_until_fails("systemctl is-active --quiet fixture-native.service", timeout=15)
          '';
      };
    };
}
