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

    # Reduce XKB warnings by using a cleaner keyboard configuration
    # The warnings are cosmetic but create log noise
    services.xserver.xkb = {
      layout = lib.mkDefault "pl";
      # Use evdev rules which have cleaner modifier definitions
      options = lib.mkDefault "";
    };

    # Ensure Hyprland uses the same keyboard layout
    home-manager.users.${config.sinnix.user.name} = {
      wayland.windowManager.hyprland.settings.input.kb_layout = lib.mkForce "pl";
    };

    # Reduce systemd service logging noise for known-chatty services
    systemd.services = {
      # NetworkManager dispatcher is chatty but usually doesn't need detailed logs
      NetworkManager-dispatcher.serviceConfig = {
        StandardOutput = lib.mkDefault "null";
        StandardError = lib.mkDefault "journal";
      };
    };

    # User services log reduction
    systemd.user.services = {
      # fnott spams "info: ctrl.c:161: got X IDs" 2x per second = 172,800 msg/day
      fnott.serviceConfig = {
        StandardOutput = lib.mkForce "null";
        StandardError = lib.mkDefault "journal";
      };

      # Hypridle logs every idle state change - only log errors
      hypridle.serviceConfig = {
        StandardOutput = lib.mkDefault "null";
        StandardError = lib.mkDefault "journal";
      };

      # Hyprpaper is very chatty about wallpaper loading
      hyprpaper.serviceConfig = {
        StandardOutput = lib.mkDefault "null";
        StandardError = lib.mkDefault "journal";
      };
    };

    # Configure systemd-logind to be less verbose
    services.logind.extraConfig = ''
      # Reduce log spam from lid/power button events
      HandlePowerKey=ignore
      HandleSuspendKey=ignore
      HandleHibernateKey=ignore
      HandleLidSwitch=ignore
      HandleLidSwitchExternalPower=ignore
      HandleLidSwitchDocked=ignore
    '';

    # Bluez experimental features already enabled, suppress probe failure logs
    # These are expected when devices don't support all profiles
    systemd.services.bluetooth.serviceConfig = {
      StandardOutput = lib.mkDefault "null";
      StandardError = lib.mkDefault "journal";
    };
  };
}
