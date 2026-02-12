# Host-specific storage configuration for sinnix-prime
{
  lib,
  config,
  ...
}:
let
  inherit (config.sinnix.paths)
    realmRoot
    dataRoot
    capturesRoot
    outerRealm
    neoOuterRealm
    ;
  username = config.sinnix.user.name;
  userCfg = config.users.users.${username};
  # NixOS auto-assigns UIDs; .uid can be null so use explicit fallback
  userUid = builtins.toString (if userCfg.uid != null then userCfg.uid else 1000);
  primaryGroupName = userCfg.group;
  groupCfg = config.users.groups.${primaryGroupName};
  primaryGroupId = builtins.toString (if groupCfg.gid != null then groupCfg.gid else 100);
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

    # 6TB HGST - reformatted from NTFS to btrfs
    "${outerRealm}" = {
      device = "/dev/disk/by-uuid/250683a9-c13f-4546-a29b-a743f3babb43";
      fsType = "btrfs";
      options = [
        "compress=zstd"
        "noatime"
        "nofail"
      ];
    };

    # 14TB Seagate Exos X18 - btrfs with @data subvolume
    "${neoOuterRealm}" = {
      device = "/dev/disk/by-uuid/2e20423b-bc3a-4953-8662-393f8aea9f2b";
      fsType = "btrfs";
      options = [
        "subvol=@data"
        "compress=zstd"
        "noatime"
        "nofail"
      ];
    };

  };

  # No disk swap — zram + earlyoom in modules/performance.nix
  swapDevices = [ ];

  systemd = {
    tmpfiles.rules = lib.mkAfter [
      "d /mnt/pendrv 0755 root root -"
      "d ${realmRoot}/knowledgebase 0755 ${username} ${primaryGroupName} -"
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
