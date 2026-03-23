# Host-specific storage configuration for sinnix-prime
{
  lib,
  config,
  ...
}:
let
  inherit (config.sinnix.paths)
    realmRoot
    capturesRoot
    outerRealm
    neoOuterRealm
    ;
  username = config.sinnix.user.name;
  primaryGroupName = config.users.users.${username}.group;

  # Initrd scaffold: early-boot placeholders derived from persistence config
  scaffoldCfg = config.sinnix.persistence.initrdScaffold;
  scaffoldDirs = lib.unique (
    scaffoldCfg.directories
    ++ map builtins.dirOf scaffoldCfg.files
  );
  scaffoldCmds = lib.concatStringsSep "\n" (
    map (d: "mkdir -p /btrfs_tmp/@${d}") scaffoldDirs
    ++ map (f: "touch /btrfs_tmp/@${f}") scaffoldCfg.files
  );
in
{
  services = {
    # fstrim disabled: using discard=async on SSD mounts instead.
    # Weekly batch TRIM caused 1.5h+ I/O saturation on multi-TB BTRFS volumes,
    # blocking all processes. discard=async coalesces discards continuously in
    # the background without a stall.
    fstrim.enable = false;
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
        "discard=async"
      ];
    };

    "/nix" = {
      device = "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02";
      fsType = "btrfs";
      options = [
        "subvol=@nix"
        "compress=zstd"
        "noatime"
        "discard=async"
      ];
    };

    # @var subvolume removed (B6): /var is now a plain dir inside @, populated
    # by /persist bind-mounts declared in modules/persistence.nix.
    # @var remains on disk as a historical archive — not yet deleted.

    "/persist" = {
      device = "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02";
      fsType = "btrfs";
      options = [
        "subvol=@persist"
        "compress=zstd"
        "noatime"
        "discard=async"
      ];
      neededForBoot = true;
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
        "subvol=/"
        "compress=zstd"
        "relatime"
        "lazytime"
        "nofail"
        "discard=async"
      ];
    };

    # B9: /realm/home bind mount removed. /home/${username} is now ephemeral
    # (part of @, wiped on every boot by B8 initrd script). Populated entirely
    # from /persist bind-mounts (impermanence) + Home Manager activation.

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

  # No disk swap. Zram-only (in modules/performance.nix) as a brief buffer
  # before earlyoom kills runaway processes. Large disk swap causes the system
  # to crawl for minutes instead of quickly killing the offender.
  swapDevices = [ ];

  systemd = {
    tmpfiles.rules = lib.mkAfter [
      "d /mnt/pendrv 0755 root root -"
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

  # Initrd rollback: on every boot, snapshot current @, then replace with a
  # fresh empty subvolume. All persistent state lives in @persist and is
  # bind-mounted back by impermanence; HM activation recreates config symlinks.
  # Safety net: pre-wipe @ saved to .snapshots/root.TIMESTAMP (never auto-pruned).
  boot.initrd.postDeviceCommands = lib.mkAfter ''
    mkdir /btrfs_tmp
    mount -o subvol=/ /dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02 /btrfs_tmp
    mkdir -p /btrfs_tmp/.snapshots

    # Save pre-wipe @ — never auto-pruned, manual cleanup only
    SNAP_NAME="root.$(date +%Y%m%dT%H%M%S)"
    btrfs subvolume snapshot /btrfs_tmp/@ "/btrfs_tmp/.snapshots/$SNAP_NAME"

    # Delete nested child subvolumes of @ (required before deleting @)
    btrfs subvolume list -o /btrfs_tmp/@ \
      | awk '{print $NF}' \
      | sort -r \
      | while IFS= read -r child; do
          btrfs subvolume delete "/btrfs_tmp/$child" 2>/dev/null || true
        done
    btrfs subvolume delete /btrfs_tmp/@

    # Fresh empty root — impermanence and HM populate everything declaratively.
    btrfs subvolume create /btrfs_tmp/@

    # Scaffold: early-boot placeholders derived from sinnix.persistence.initrdScaffold.
    ${scaffoldCmds}

    echo "Rolled back @ (saved to .snapshots/$SNAP_NAME)"

    umount /btrfs_tmp
  '';
}
