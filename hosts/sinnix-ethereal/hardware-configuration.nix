{
  lib,
  modulesPath,
  ...
}:
{
  imports = [ (modulesPath + "/profiles/qemu-guest.nix") ];

  boot = {
    initrd = {
      availableKernelModules = [
        "virtio_pci"
        "virtio_blk"
        "virtio_scsi"
        "virtio_net"
      ];
      kernelModules = [ ];
    };
    kernelModules = [ ];
    extraModulePackages = [ ];
  };

  fileSystems."/" = {
    device = lib.mkDefault "/dev/disk/by-partlabel/disk-vda-root";
    fsType = "ext4";
  };

  fileSystems."/boot" = {
    device = lib.mkDefault "/dev/disk/by-partlabel/disk-vda-ESP";
    fsType = "vfat";
  };

  swapDevices = [ ];
}
