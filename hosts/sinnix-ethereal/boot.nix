{ pkgs, lib, ... }:
{
  boot = {
    loader = {
      systemd-boot.enable = false;
      efi.canTouchEfiVariables = false;
      grub = {
        enable = true;
        devices = [ "/dev/vda" ];
        # why mkForce: the shared boot module assumes the sinnix-prime
        # mirrored-boot layout (two NVMe devices). VPS only has /dev/vda.
        mirroredBoots = lib.mkForce (
          lib.singleton {
            path = "/boot";
            efiSysMountPoint = "/boot";
            efiBootloaderId = null;
            devices = [ "/dev/vda" ];
          }
        );
      };
    };

    loader.timeout = 5;

    kernelPackages = pkgs.linuxPackages;
    kernelParams = [
      "console=tty0"
      "console=ttyS0,115200n8"
      "boot.shell_on_fail"
    ];
  };
}
