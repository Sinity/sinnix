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

    openssh = {
      enable = true;
      settings = {
        PermitRootLogin = "prohibit-password";
        PasswordAuthentication = false;
        KbdInteractiveAuthentication = false;
        LogLevel = "VERBOSE";
      };
    };

    # mkForce: Headless VPS has no graphics hardware; override any module defaults
    xserver.enable = lib.mkForce false;
  };

  systemd.services."serial-getty@ttyS0".enable = true;

  sinnix.features.cli.core.enable = true;

  # mkForce: Redundant with isDesktop=false, but explicit host-level override for clarity
  programs.hyprland.enable = lib.mkForce false;
  programs.zsh.enable = true;
}
