{
  pkgs,
  lib,
  config,
  ...
}:
let
  inherit (config.sinnix.machine) isDesktop;
  coreCliPackages = with pkgs; [
    git
    taskwarrior3
    timewarrior
    unzip
    wget
  ];

  optionalCliPackages = lib.filter (pkg: pkg != null) [
    (pkgs.tasksh or null)
    (pkgs.taskwarrior-tui or null)
    (pkgs.bugwarrior or null)
    (pkgs.timewarrior-all-reports or null)
  ];
in
{
  config = lib.mkMerge [
    {
      environment.systemPackages = lib.mkAfter (coreCliPackages ++ optionalCliPackages);

      programs = {
        zsh.enable = true;

        gnupg.agent = {
          enable = true;
          enableSSHSupport = true;
        };
      };

      systemd.coredump.enable = true;

      services = {
        dbus = {
          enable = true;
          implementation = "broker";
          brokerPackage = pkgs.dbus-broker;
        };

        gnome.gnome-keyring.enable = lib.mkForce false;
      };

      security.pam.services.login.enableGnomeKeyring = lib.mkForce false;
    }
    (lib.mkIf isDesktop {
      programs.steam = {
        enable = true;
        gamescopeSession.enable = true;
      };
      programs.gamemode.enable = true;
    })
  ];
}
