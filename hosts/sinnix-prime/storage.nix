# Host-specific storage configuration for sinnix-prime
{
  lib,
  config,
  ...
}:
let
  inherit (config.sinnix.paths) realmRoot dataRoot capturesRoot outerRealm;
  username = config.sinnix.user.name;
  userCfg = config.users.users.${username} or { };
	  getAttrOrFallback =
	    set: attr: fallback:
	    let
	      value = set.${attr} or null;
	    in
	    if value == null then fallback else value;
  userUid = builtins.toString (getAttrOrFallback userCfg "uid" 1000);
  primaryGroupName = getAttrOrFallback userCfg "group" "users";
  groupCfg = lib.attrByPath [ "users" "groups" primaryGroupName ] config { };
  primaryGroupId = builtins.toString (getAttrOrFallback groupCfg "gid" 100);

in
{
  services = {
    fstrim.enable = true; # periodically TRIM ssd storage devices
    gvfs.enable = true; # dynamic mount
  };

  fileSystems = {
    "/" = {
      device = "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02";
      fsType = "btrfs";
      options = [
        "subvol=@"
        "compress=zstd"
        "noatime"
      ];
    };

    "/nix" = {
      device = "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02";
      fsType = "btrfs";
      options = [
        "subvol=@nix"
        "compress=zstd"
        "noatime"
      ];
    };

    "/var" = {
      device = "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02";
      fsType = "btrfs";
      options = [
        "subvol=@var"
        "compress=zstd"
        "noatime"
      ];
    };

    "/boot" = {
      device = "/dev/disk/by-uuid/9E84-C199";
      fsType = "vfat";
      options = [
        "fmask=0077"
        "dmask=0077"
      ];
    };

    "${realmRoot}" = {
      device = "/dev/disk/by-uuid/bd19092f-a195-47ab-9c0d-c923d1e5bfea";
      fsType = "btrfs";
      options = [
        "relatime"
        "lazytime"
        "nofail"
      ];
    };

    "/home/${username}" = {
      device = "${realmRoot}/home";
      fsType = "none";
      options = [ "bind" ];
      depends = [ realmRoot ];
    };

    "${outerRealm}" = {
      device = "/dev/disk/by-uuid/5119B4113C747C42";
      fsType = "ntfs";
      options = [
        "strictatime"
        "lazytime"
        "nofail"
        "uid=${userUid}"
        "gid=${primaryGroupId}"
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

  swapDevices = [
    {
      device = "/dev/nvme1n1p1";
    }
  ];

  systemd = {
    tmpfiles.rules = lib.mkAfter [
      "d /mnt/pendrv 0755 root root -"
      "d ${realmRoot}/knowledgebase 0755 ${username} users -"
    ];

    automounts = [
      {
        where = "/mnt/pendrv";
        wantedBy = [ "multi-user.target" ];
        automountConfig = {
          TimeoutIdleSec = "600s";
        };
      }
    ];

    mounts = lib.mkAfter (
      [
        {
          what = "${capturesRoot}/syslog/journal";
          where = "/var/log/journal";
          type = "none";
          options = "bind,x-systemd.requires-mounts-for=${realmRoot}";
          wantedBy = [ "local-fs.target" ];
          requires = [ "realm.mount" ];
          after = [ "realm.mount" ];
        }
      ]
      ++ [
        {
          what = "/dev/disk/by-uuid/36213474-7e7f-4df7-8fb6-264d9a2e9643";
          where = "/mnt/pendrv";
          type = "btrfs";
          options = "nofail,compress=zstd,x-systemd.device-timeout=5s";
        }
      ]
    );
  };

  boot.supportedFilesystems = [
    "btrfs"
    "ntfs"
  ];
}
