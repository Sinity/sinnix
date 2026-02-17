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
  sinnix.machine.isDesktop = false;

  services = {
    qemuGuest.enable = true;

    # Override the default "no" from networking.nix to allow root SSH on VPS
    openssh.settings.PermitRootLogin = "prohibit-password";

    xserver.enable = lib.mkForce false;
  };

  systemd.services."serial-getty@ttyS0".enable = true;

  sinnix.features.cli.core.enable = true;
  programs.zsh.enable = true;
}
