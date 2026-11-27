{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      inherit (pkgs) lib;
      host = inputs.self.nixosConfigurations.sinnix-prime.config;
      hyprland = host.programs.hyprland.package;
      noctalia = host.home-manager.users.${host.sinnix.user.name}.programs.noctalia.package;
      login = import ../../hosts/sinnix-prime/desktop-login.nix {
        inherit
          pkgs
          lib
          hyprland
          noctalia
          ;
        user = "fixture";
        sessionEnvironment = pkgs.writeText "fixture-session-environment" ''
          export FIXTURE_DESKTOP=started
        '';
      };
      guest = enableLocker: {
        imports = [ inputs.noctalia.nixosModules.default ];
        virtualisation = {
          graphics = true;
          qemu.options = [ "-vga virtio" ];
          memorySize = 2048;
          cores = 2;
        };
        boot.kernelModules = [ "virtio_gpu" ];
        hardware.graphics.enable = true;
        users.users.fixture = {
          isNormalUser = true;
          uid = 1000;
          password = "fixture";
        };
        programs = {
          hyprland = {
            enable = true;
            withUWSM = true;
            package = hyprland;
          };
          noctalia = {
            enable = enableLocker;
            package = noctalia;
            systemd.enable = enableLocker;
          };
        };
        systemd.tmpfiles.rules = [
          "d /home/fixture/.config 0755 fixture users -"
          "d /home/fixture/.config/hypr 0755 fixture users -"
          "L /home/fixture/.config/hypr/hyprland.lua - - - - ${pkgs.writeText "fixture.lua" ''
            hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })
            hl.bind("SUPER + Return", hl.dsp.exec_cmd("echo $FIXTURE_DESKTOP > /tmp/desktop-shortcut"))
            hl.on("hyprland.start", function()
              hl.exec_cmd("${pkgs.uwsm}/bin/uwsm finalize")
            end)
          ''}"
        ];
      };
    in
    {
      heavyChecks.desktop-login-vm = pkgs.testers.runNixOSTest {
        name = "desktop-login";
        nodes = {
          normal.imports = [
            (guest true)
            login
          ];
          missingLocker.imports = [
            (guest false)
            login
          ];
          legacy = {
            imports = [ (guest true) ];
            systemd.defaultUnit = "graphical.target";
            specialisation = {
              locked-desktop.configuration.imports = [ login ];
              direct-login.configuration = {
                imports = [ login ];
                systemd.services.greetd = {
                  aliases = lib.mkOverride 10 [ "display-manager.service" ];
                  wantedBy = lib.mkOverride 10 [ "graphical.target" ];
                };
              };
            };
          };
        };
        testScript = ''
          runtime = "/run/user/1000"
          userctl = f"runuser -u fixture -- env XDG_RUNTIME_DIR={runtime} systemctl --user"
          compositor = r"wayland-wm@start\x2dhyprland.service"
          hyprctl = (
              f'instance=$(basename "$(find {runtime}/hypr -name .socket.sock -printf "%h" -quit)")'
              f'; runuser -u fixture -- env XDG_RUNTIME_DIR={runtime} '
              f'HYPRLAND_INSTANCE_SIGNATURE=$instance ${hyprland}/bin/hyprctl'
          )
          def expect_locked(machine):
              machine.wait_for_unit("graphical.target")
              machine.wait_until_succeeds(f"{hyprctl} locked | grep -qx true")
              machine.succeed("loginctl list-sessions --no-legend | grep -E 'fixture .*tty1'")
              machine.fail("systemctl is-active --quiet getty@tty1.service")
              machine.send_key("meta_l-ret")
              machine.fail("test -e /tmp/desktop-shortcut")

          def activate(machine, name):
              machine.succeed(f"/run/booted-system/specialisation/{name}/bin/switch-to-configuration test >&2")

          def main_pid(machine, manager, unit):
              pid = int(machine.succeed(f"{manager} show -p MainPID --value '{unit}'"))
              assert pid > 0, f"{unit} has no running process"
              return pid

          legacy.start()
          with subtest("live activation keeps the existing tty1 login"):
              legacy.wait_for_unit("graphical.target")
              legacy.wait_for_unit("getty@tty1.service")
              getty_pid = main_pid(legacy, "systemctl", "getty@tty1.service")
              activate(legacy, "locked-desktop")
              assert main_pid(legacy, "systemctl", "getty@tty1.service") == getty_pid
              legacy.fail("systemctl is-active --quiet greetd.service")
          with subtest("live activation keeps a desktop that greetd already started"):
              activate(legacy, "direct-login")
              expect_locked(legacy)
              greetd_pid = main_pid(legacy, "systemctl", "greetd.service")
              compositor_pid = main_pid(legacy, userctl, compositor)
              activate(legacy, "locked-desktop")
              assert main_pid(legacy, "systemctl", "greetd.service") == greetd_pid
              assert main_pid(legacy, userctl, compositor) == compositor_pid
              expect_locked(legacy)
          legacy.shutdown()

          normal.start()
          with subtest("Noctalia requires the user's password"):
              expect_locked(normal)
              normal.wait_until_succeeds("journalctl -b _SYSTEMD_USER_UNIT=noctalia.service | grep -q 'session is locked'")
              for key in ["x", "ret"]:
                  normal.send_key(key)
              normal.wait_until_succeeds("journalctl -b _SYSTEMD_USER_UNIT=noctalia.service | grep -q 'authentication failed'")
              normal.succeed(f"{hyprctl} locked | grep -qx true")
              for key in [*"fixture", "ret"]:
                  normal.send_key(key)
              normal.wait_until_succeeds(f"{hyprctl} locked | grep -qx false")
              normal.send_key("meta_l-ret")
              normal.wait_for_file("/tmp/desktop-shortcut")
              normal.succeed("grep -qx started /tmp/desktop-shortcut")
              normal.send_key("ctrl-alt-f2")
              normal.wait_for_unit("getty@tty2.service")
              normal.fail("loginctl list-sessions --no-legend | grep tty2")
          with subtest("UWSM stops Hyprland before the final stop timeout"):
              normal.succeed(f"{userctl} is-active --quiet '{compositor}'")
              normal.succeed(f"timeout 9s {userctl} stop '{compositor}'")
              normal.fail(f"{userctl} is-active --quiet '{compositor}'")
              normal.fail("journalctl -b | grep -F 'final-sigterm' | grep wayland-wm")
          normal.shutdown()

          missingLocker.start()
          with subtest("a missing locker leaves the compositor locked"):
              expect_locked(missingLocker)
              missingLocker.wait_until_succeeds(
                  "journalctl -b -t noctalia-startup-lock -o cat | grep -Fxq "
                  "'Noctalia did not accept the startup lock. The compositor remains locked.'",
                  timeout=150,
              )
              expect_locked(missingLocker)
          missingLocker.shutdown()
        '';
      };
    };
}
