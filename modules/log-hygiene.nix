# Log hygiene: suppress cosmetic warnings and quiet known-chatty services.
{
  pkgs,
  lib,
  config,
  ...
}:
{
  config = {
    # The NixOS default session config carries deprecated eavesdrop policies;
    # this drop-in replaces them so D-Bus stops warning about them.
    services.dbus.packages = [
      (pkgs.writeTextFile {
        name = "dbus-session-local";
        destination = "/share/dbus-1/session.d/nixos-log-hygiene.conf";
        text = ''
          <!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
           "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
          <busconfig>
            <!-- Empty: modern D-Bus ignores eavesdrop policies anyway. -->
          </busconfig>
        '';
      })
    ];

    home-manager.users.${config.sinnix.user.name} = {

      systemd.user.services = {
        # Hypridle logs every idle state change; keep errors only.
        hypridle.Service = {
          StandardOutput = "null";
          StandardError = "journal";
        };

      };
    };

    systemd.services = {
      NetworkManager-dispatcher.serviceConfig = {
        StandardOutput = lib.mkDefault "null";
        StandardError = lib.mkDefault "journal";
      };

      # udevmon logs JSON stats constantly (thousands of messages an hour).
      interception-tools.serviceConfig = {
        # mkForce: the keyboard/intercept-bounce stack re-enables journal
        # output via mkDefault.
        StandardOutput = lib.mkForce "null";
        StandardError = lib.mkDefault "journal";
      };
    };

    services.logind.settings.Login = {
      HandleLidSwitch = lib.mkDefault "ignore";
      HandleLidSwitchExternalPower = lib.mkDefault "ignore";
      HandleLidSwitchDocked = lib.mkDefault "ignore";
    };

    # Probe failures are expected when devices don't support all profiles.
    systemd.services.bluetooth.serviceConfig = {
      StandardOutput = lib.mkDefault "null";
      StandardError = lib.mkDefault "journal";
    };
  };
}
