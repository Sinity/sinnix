{pkgs, ...}: {
  services.fstrim.enable = true; # periodically TRIM ssd storage devices
  services.gvfs.enable = true; # dynamic mount

  fileSystems."/" = {
    device = "/dev/disk/by-uuid/481e214e-7bb6-49fa-bc87-ccb1f2c1e3c3";
    fsType = "ext4";
    options = ["strictatime" "lazytime"];
  };

  fileSystems."/boot" = {
    device = "/dev/disk/by-uuid/1C27-5679";
    fsType = "vfat";
    options = ["fmask=0022" "dmask=0022"];
  };

  swapDevices = [{device = "/dev/disk/by-uuid/9f79240e-f78e-4d8c-bdd0-4eafba396781";}];

  boot.supportedFilesystems = ["btrfs" "ntfs"];
  fileSystems."/realm" = {
    device = "/dev/disk/by-uuid/bd19092f-a195-47ab-9c0d-c923d1e5bfea";
    fsType = "btrfs";
    options = [
      "strictatime"
      "lazytime"
      "nofail"
    ];
  };

  fileSystems."/outer-realm" = {
    device = "/dev/disk/by-uuid/5119B4113C747C42";
    fsType = "ntfs";
    options = [
      "strictatime"
      "lazytime"
      "nofail"
      "uid=1000"
      "gid=100"
      "umask=000"
      "big_writes"
    ];
  };
}
