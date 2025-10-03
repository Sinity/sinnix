# Host-specific storage configuration for sinnix-prime
_: {
  # Storage-related services
  services = {
    fstrim.enable = true; # periodically TRIM ssd storage devices
    gvfs.enable = true; # dynamic mount
  };

  # Filesystem configuration
  fileSystems = {
    "/" = {
      device = "/dev/disk/by-uuid/9fd1aa14-f137-4a90-8c00-e25770496374";
      fsType = "ext4";
      options = [
        "relatime"
        "lazytime"
      ];
    };

    "/boot" = {
      device = "/dev/disk/by-uuid/91A2-0DC7";
      fsType = "vfat";
      options = [
        "fmask=0022"
        "dmask=0022"
      ];
    };

    "/realm" = {
      device = "/dev/disk/by-uuid/bd19092f-a195-47ab-9c0d-c923d1e5bfea";
      fsType = "btrfs";
      options = [
        "relatime"
        "lazytime"
        "nofail"
      ];
    };

    "/var/log/journal" = {
      device = "/realm/data/syslog/journal";
      fsType = "none";
      options = [ "bind" ];
      depends = [ "/realm" ];
    };

    "/home/sinity" = {
      device = "/realm/home";
      fsType = "none";
      options = [ "bind" ];
      depends = [ "/realm" ];
    };

    "/outer-realm" = {
      device = "/dev/disk/by-uuid/5119B4113C747C42";
      fsType = "ntfs";
      options = [
        "strictatime"
        "lazytime"
        "nofail"
        "uid=1000"
        "gid=100"
        "umask=022"
        "big_writes"
      ];
    };

    # "/mnt/smol_ssd" = {
    #   device = "/dev/disk/by-uuid/481e214e-7bb6-49fa-bc87-ccb1f2c1e3c3";
    #   fsType = "btrfs";
    #   options = [
    #     "strictatime"
    #     "lazytime"
    #   ];
    # };
  };

  # Swap configuration
  swapDevices = [ { device = "/dev/disk/by-uuid/9f79240e-f78e-4d8c-bdd0-4eafba396781"; } ];

  # Additional filesystem support
  boot.supportedFilesystems = [
    "btrfs"
    "ntfs"
  ];
}
