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
      guest = enableLocker: {
        imports = [
          (import ../../hosts/sinnix-prime/desktop-login.nix {
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
          })
          inputs.noctalia.nixosModules.default
        ];
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
          normal = guest true;
          missingLocker = guest false;
        };
        testScript = ''
          runtime = "/run/user/1000"
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
              userctl = f"runuser -u fixture -- env XDG_RUNTIME_DIR={runtime} systemctl --user"
              compositor = r"wayland-wm@start\x2dhyprland.service"
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
