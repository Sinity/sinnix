{ pkgs, ... }:
{
  services.fstrim.enable = true; # periodically TRIM ssd storage devices
  services.gvfs.enable = true; # dynamic mount

  fileSystems."/" =
  { device = "/dev/disk/by-uuid/9fd1aa14-f137-4a90-8c00-e25770496374";
    fsType = "ext4";
    options = [ "strictatime" "lazytime" ];
  };
  fileSystems."/boot" =
  { device = "/dev/disk/by-uuid/91A2-0DC7";
    fsType = "vfat";
    options = [ "fmask=0077" "dmask=0077" ];
  };
  swapDevices = [ { device = "/dev/disk/by-uuid/9f79240e-f78e-4d8c-bdd0-4eafba396781"; } ];

  boot.supportedFilesystems = [ "btrfs" "ntfs" ];
  fileSystems."/mnt/ssd_storage" = {
    device = "/dev/disk/by-uuid/bd19092f-a195-47ab-9c0d-c923d1e5bfea";
    fsType = "btrfs";
    options = [
      "strictatime" "lazytime"
      "nofail"
    ];
   };
   fileSystems."/mnt/hdd_storage" = {
     device = "/dev/disk/by-uuid/5119B4113C747C42";
     fsType = "ntfs";
     options = [
       "strictatime" "lazytime"
       "nofail"
       "uid=1000" "gid=100" "umask=000"
       "big_writes"
     ];
   };
   fileSystems."/mnt/arch_root" = {
     device = "/dev/disk/by-uuid/481e214e-7bb6-49fa-bc87-ccb1f2c1e3c3";
     fsType = "ext4";
     options = [
       "strictatime" "lazytime"
       "nofail"
     ];
   };
}

