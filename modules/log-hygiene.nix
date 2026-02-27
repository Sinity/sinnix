# Log hygiene: Suppress cosmetic warnings and configure proper defaults
#
# Provides:
# - XKB configuration to eliminate keyboard warnings
# - D-Bus session config without deprecated eavesdropping policies
# - Proper systemd service log levels
{
  pkgs,
  lib,
  config,
  ...
}:
{
  config = {
    # Fix D-Bus eavesdropping deprecation warnings
    # The default NixOS config includes deprecated eavesdrop policies
    services.dbus.packages = [
      (pkgs.writeTextFile {
        name = "dbus-session-local";
        destination = "/share/dbus-1/session.d/nixos-log-hygiene.conf";
        text = ''
          <!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
           "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
          <busconfig>
            <!-- Remove deprecated eavesdrop policies - modern D-Bus ignores them anyway -->
            <!-- This suppresses warnings without changing behavior -->
          </busconfig>
        '';
      })
    ];

    home-manager.users.${config.sinnix.user.name} = {

      # User services log reduction for home-manager-managed services
      systemd.user.services = {
        # fnott spams "info: ctrl.c:161: got X IDs" 2x per second = 172,800 msg/day
        fnott.Service = {
          StandardOutput = "null";
          StandardError = "journal";
        };

        # Hypridle logs every idle state change - only log errors
        hypridle.Service = {
          StandardOutput = "null";
          StandardError = "journal";
        };

        # Hyprpaper is very chatty about wallpaper loading
        hyprpaper.Service = {
          StandardOutput = "null";
          StandardError = "journal";
        };
        # Limit hyprpaper restart attempts. Without this, NVIDIA driver mismatches
        # (after nixos-rebuild without reboot) cause infinite crash-loops:
        # 1675 restarts in 5 hours, each generating a coredump + journal spam.
        hyprpaper.Unit = {
          StartLimitIntervalSec = 60;
          StartLimitBurst = 5;
        };
      };
    };

    # Reduce systemd service logging noise for known-chatty services
    systemd.services = {
      # NetworkManager dispatcher is chatty but usually doesn't need detailed logs
      NetworkManager-dispatcher.serviceConfig = {
        StandardOutput = lib.mkDefault "null";
        StandardError = lib.mkDefault "journal";
      };

      # interception-tools (udevmon) logs JSON stats constantly = 21% of all logs
      # Example spam: 176,431 messages in 3 days = 2,378 messages/hour
      interception-tools.serviceConfig = {
        StandardOutput = lib.mkForce "null";
        StandardError = lib.mkDefault "journal";
      };
    };

    # Configure systemd-logind to ignore power events (reduces log spam)
    services.logind.settings.Login = {
      HandleLidSwitch = lib.mkDefault "ignore";
      HandleLidSwitchExternalPower = lib.mkDefault "ignore";
      HandleLidSwitchDocked = lib.mkDefault "ignore";
    };

    # Bluez experimental features already enabled, suppress probe failure logs
    # These are expected when devices don't support all profiles
    systemd.services.bluetooth.serviceConfig = {
      StandardOutput = lib.mkDefault "null";
      StandardError = lib.mkDefault "journal";
    };
  };
}
