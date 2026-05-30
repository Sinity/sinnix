# Hetzner AX42 dual-NVMe layout.
#
# nvme0n1 — NixOS root (ESP + ext4 root, no RAID, no LUKS)
# nvme1n1 — data volume mounted at /var/lib/data (ext4)
#
# Hetzner dedicated supports UEFI, so we use systemd-boot via a small ESP.
# No swap partition here; storage.nix prepares a swapfile on the root fs.
#
# TODO: decide with operator whether /var/lib/data should mirror prime's
# btrfs/zfs layout for snapshots, or stay simple ext4 for replica workload.
_: {
  disko.devices.disk = {
    nvme0n1 = {
      type = "disk";
      device = "/dev/nvme0n1";
      content = {
        type = "gpt";
        partitions = {
          ESP = {
            size = "512M";
            type = "EF00";
            content = {
              type = "filesystem";
              format = "vfat";
              mountpoint = "/boot";
              mountOptions = [ "umask=0077" ];
            };
          };
          root = {
            size = "100%";
            content = {
              type = "filesystem";
              format = "ext4";
              mountpoint = "/";
              mountOptions = [
                "noatime"
                "discard"
              ];
              extraArgs = [
                "-L"
                "nixos-root"
              ];
            };
          };
        };
      };
    };

    nvme1n1 = {
      type = "disk";
      device = "/dev/nvme1n1";
      content = {
        type = "gpt";
        partitions = {
          data = {
            size = "100%";
            content = {
              type = "filesystem";
              format = "ext4";
              mountpoint = "/var/lib/data";
              mountOptions = [
                "noatime"
                "discard"
              ];
              extraArgs = [
                "-L"
                "nixos-data"
              ];
            };
          };
        };
      };
    };
  };
}
