{ pkgs, ... }:
{
  boot = {
    loader = {
      systemd-boot.enable = true;
      efi = {
        canTouchEfiVariables = false;
        efiSysMountPoint = "/boot";
      };
      timeout = 5;
    };

    kernelPackages = pkgs.linuxPackages;
    kernelParams = [
      "console=tty0"
      "console=ttyS0,115200n8"
      "boot.shell_on_fail"
    ];
  };
}
