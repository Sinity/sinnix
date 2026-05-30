# Hardware configuration for sinnix-ethereal — Hetzner AX42 (bare metal).
#
# This file is the placeholder that nixos-anywhere will regenerate from
# `nixos-generate-config` on the target during install. The values below
# are the typical AX42 set (NVMe + igb/Intel NIC); keep them in sync with
# whatever nixos-anywhere lands during the real bootstrap.
{
  lib,
  ...
}:
{
  boot = {
    initrd = {
      # NVMe + USB HID + sd_mod cover the typical AX42 boot path; ahci is
      # kept for the off-chance of a board variant with SATA controllers.
      availableKernelModules = [
        "nvme"
        "xhci_pci"
        "ahci"
        "usbhid"
        "usb_storage"
        "sd_mod"
      ];
      kernelModules = [ ];
    };

    # Standard kvm-amd for the Ryzen 7600 AX42 SKU.
    kernelModules = [ "kvm-amd" ];
    extraModulePackages = [ ];
  };

  fileSystems."/" = {
    device = lib.mkDefault "/dev/disk/by-label/nixos-root";
    fsType = "ext4";
  };

  fileSystems."/boot" = {
    device = lib.mkDefault "/dev/disk/by-partlabel/ESP";
    fsType = "vfat";
    options = [ "umask=0077" ];
  };

  swapDevices = [ ];

  # Disk-IO bottleneck on a remote replica; let nix-daemon use both NVMe
  # devices' bandwidth. nixos-anywhere generation will rewrite this.
  nixpkgs.hostPlatform = lib.mkDefault "x86_64-linux";
}
