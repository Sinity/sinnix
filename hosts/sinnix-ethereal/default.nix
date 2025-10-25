{
  lib,
  ...
}:
{
  imports = [
    ./hardware-configuration.nix
    ./boot.nix
    ./networking.nix
    ./disko.nix
  ];

  networking.hostName = "sinnix-ethereal";

  services = {
    qemuGuest.enable = true;

    openssh = {
      enable = true;
      settings = {
        PermitRootLogin = "prohibit-password";
        PasswordAuthentication = false;
        KbdInteractiveAuthentication = false;
        LogLevel = "VERBOSE";
      };
    };

    # Keep the desktop stack disabled on the VPS
    xserver.enable = lib.mkForce false;
  };

  systemd.services."serial-getty@ttyS0".enable = true;

  home-manager.users.sinity.imports = [
    ../../user/core.nix
    ../../user/dev/core.nix
    ../../user/dev/shell.nix
  ];

  programs.hyprland.enable = lib.mkForce false;
}
