{ pkgs, lib, ... }:
let
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

  aiDesktopPackages = with pkgs; [
    aionui
  ];
in
{
  config = {
    environment.systemPackages = lib.mkAfter (coreCliPackages ++ aiDesktopPackages);
    sinnix.optionalPackages.cli = optionalCliPackages;
    sinnix.optionalPackages.aiDesktop = aiDesktopPackages;

    programs = {
      zsh.enable = true;
      steam = {
        enable = true;
        gamescopeSession.enable = true;
      };

      gamemode.enable = true;

      gnupg.agent = {
        enable = true;
        enableSSHSupport = true;
      };
    };

    systemd.coredump.enable = true;

    services = {
      dbus.enable = true;

      earlyoom = {
        enable = true;
        enableNotifications = true;
        freeMemThreshold = 5;
        freeSwapThreshold = 5;
        reportInterval = 5;
        extraArgs = [
          "-g"
          "-p"
          "--prefer"
          "(^|/)(java|chromium|obsidian|google-chrome(-stable)?)$"
          "--avoid"
          "(^|/)(init|systemd|sshd)$"
        ];
      };

      gnome.gnome-keyring.enable = true;
    };
  };
}
