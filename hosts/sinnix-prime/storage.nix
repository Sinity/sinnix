# Host-specific storage configuration for sinnix-prime
{
  lib,
  pkgs,
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
  polylogueArchiveRoot = "${capturesRoot}/polylogue";
  polylogueShareMount = "/home/${username}/.local/share/polylogue";
  swapFile = "/swap/swapfile";
  swapSizeGiB = 64;

  # Initrd scaffold: early-boot placeholders derived from persistence config
  scaffoldCfg = config.sinnix.persistence.initrdScaffold;
  scaffoldDirs = lib.unique (scaffoldCfg.directories ++ map builtins.dirOf scaffoldCfg.files);
  scaffoldCmds = lib.concatStringsSep "\n" (
    map (d: "mkdir -p /btrfs_tmp/@${d}") scaffoldDirs
    ++ map (f: "touch /btrfs_tmp/@${f}") scaffoldCfg.files
  );
in
{
  services = {
    # Keep discard off the hot path. Continuous discard previously produced
    # D-state btrfs workers during desktop pressure, and the replacement
    # scheduled fstrim window itself saturated the root_btrfs SSD (sdb2) with
    # discard I/O on 2026-05-03.
    fstrim.enable = false;
    gvfs.enable = true; # dynamic mount

    # Monthly btrfs scrub on always-mounted filesystems. Scrub re-reads every
    # data + metadata block and verifies checksums against the DUP copy; for
    # single-device btrfs this is the only defence against silent bit rot.
    # /neo-outer-realm is deliberately excluded — it is a manual maintenance
    # mount, and scrubbing would pin the disk awake for hours.
    # Cadence is monthly (NixOS default) rather than weekly because each scrub
    # walks the entire used capacity (1.0 TB on root, ~0.7 TB on /realm,
    # multi-TB on /outer-realm) and the read load is meaningful.
    btrfs.autoScrub = {
      enable = true;
      fileSystems = [
        "/"
        "/realm"
        "/outer-realm"
      ];
    };

    # Disable block-layer writeback throttle on all storage. wbt parks writers
    # in `wbt_wait` when observed completion latency exceeds wbt_lat_usec
    # (default 75ms). Combined with btrfs holding the log-tree mutex during
    # `btrfs_commit_transaction` (especially under btrbk snapshot creation),
    # any writer doing fdatasync (postgres, sinex, polylogue) can block long
    # enough to trip khungtaskd → kernel panic. Observed 2026-04-28 23:11:
    # btrbk snapshot of /persist stalled in wbt_wait while holding the log
    # mutex; postgres + tokio fsync tasks stacked behind it and the 122s
    # hung-task threshold fired. wbt is widely disabled on btrfs+NVMe setups
    # (Fedora ships it off on btrfs); block-layer throttling is the wrong
    # mechanism when the FS itself coordinates ordering.
    udev.extraRules = ''
      ACTION=="add|change", KERNEL=="nvme[0-9]n[0-9]", ATTR{queue/wbt_lat_usec}="0"
      ACTION=="add|change", KERNEL=="sd[a-z]", ATTR{queue/wbt_lat_usec}="0"
    '';
  };

  fileSystems = {
    "/" = {
      device = "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02";
      fsType = "btrfs";
      options = [
        "subvol=@"
        "compress=zstd"
        "noatime"
        "nodiscard"
      ];
    };

    "/nix" = {
      device = "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02";
      fsType = "btrfs";
      options = [
        "subvol=@nix"
        "compress=zstd"
        "noatime"
        "nodiscard"
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
        "nodiscard"
      ];
      neededForBoot = true;
    };

    "/swap" = {
      device = "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02";
      fsType = "btrfs";
      options = [
        "subvol=@swap"
        "nodatacow"
        "noatime"
        "nodiscard"
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

    # /cache mount on Samsung 960 EVO (nvme1n1p2) removed 2026-05-12 after the
    # drive started throwing sustained I/O errors: NVMe queue timeouts at
    # 06:52, then btrfs flipped /cache read-only and the kernel logged hundreds
    # of Read-/Write-error events on swap-device 259:0 (nvme1n1p1). Codex/exec
    # syscalls began returning EIO ("env: 'bash': Input/output error") because
    # paged-out binary pages could not be read back. Drive is staying unused
    # until it is physically replaced. Cache consumers fall back to their
    # default locations or root-backed /var/tmp scratch.

    "${realmRoot}" = {
      device = "/dev/disk/by-uuid/43701cf7-7880-4e0c-9725-b6e12d91898a";
      fsType = "btrfs";
      options = [
        "subvol=/"
        "compress=zstd"
        "relatime"
        "lazytime"
        "nodiscard"
        "nofail"
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
        "noauto"
        "nofail"
        "x-systemd.automount"
        "x-systemd.idle-timeout=10min"
      ];
    };

  };

  # Swap on nvme1n1p1 (Samsung 960 EVO) was removed 2026-05-12 after the drive
  # started returning I/O errors. Use a prepared Btrfs swapfile on a dedicated
  # @swap subvolume instead: it survives impermanent-root rollback, stays out
  # of btrbk's /persist and /realm snapshots, and is created through
  # `btrfs filesystem mkswapfile` so CoW/compression/holes are not
  # accidentally enabled.
  swapDevices = [
    {
      device = swapFile;
      size = swapSizeGiB * 1024;
    }
  ];

  systemd = {
    services.realm-scaffold = {
      description = "Create /realm-backed bind mount source directories";
      requires = [ "realm.mount" ];
      after = [ "realm.mount" ];
      before = [
        "home-${username}-.local-share-polylogue.mount"
      ];
      unitConfig.DefaultDependencies = false;
      serviceConfig.Type = "oneshot";
      path = [ pkgs.coreutils ];
      script = ''
        install -d -m 0700 -o ${username} -g ${primaryGroupName} ${polylogueArchiveRoot}
      '';
    };

    tmpfiles.rules = lib.mkAfter [
      "d ${polylogueArchiveRoot} 0700 ${username} ${primaryGroupName} -"
      "d /home/${username}/.local/share 0700 ${username} ${primaryGroupName} -"
      "d ${polylogueShareMount} 0700 ${username} ${primaryGroupName} -"
    ];

    # Polylogue's archive is an active SQLite/write-heavy workload. Keep the
    # default XDG path stable for CLI/MCP/service consumers, but place the
    # bytes on /realm's NVMe instead of the root/persist SATA SSD shared with
    # PostgreSQL.
    mounts = [
      {
        what = polylogueArchiveRoot;
        where = polylogueShareMount;
        type = "none";
        options = "bind,x-systemd.requires-mounts-for=${realmRoot}";
        wantedBy = [ "local-fs.target" ];
        requires = [
          "realm.mount"
          "realm-scaffold.service"
        ];
        after = [
          "realm.mount"
          "realm-scaffold.service"
        ];
      }
      {
        what = "/dev/disk/by-uuid/36213474-7e7f-4df7-8fb6-264d9a2e9643";
        where = "/mnt/pendrv";
        type = "btrfs";
        options = "nofail,compress=zstd,x-systemd.device-timeout=5s";
      }
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

  };

  sinnix.persistence.initrdScaffold.directories = lib.mkAfter [
    "/home/${username}/.local/share"
    polylogueShareMount
  ];

  boot.supportedFilesystems = [
    "btrfs"
    "ntfs"
  ];

  # Initrd rollback: on every boot, snapshot current @, then replace with a
  # fresh empty subvolume. All persistent state lives in @persist and is
  # bind-mounted back by impermanence; HM activation recreates config symlinks.
  # Safety net: pre-wipe @ saved to .snapshots/root.TIMESTAMP (never auto-pruned).
  boot.initrd.systemd.storePaths = with pkgs; [
    btrfs-progs
    coreutils
    findutils
    gawk
    util-linux
  ];

  boot.initrd.systemd.services.rollback-root = {
    description = "Rollback btrfs root subvolume";
    wantedBy = [ "initrd.target" ];
    requires = [ "dev-disk-by\\x2duuid-f4782d9f\\x2daabe\\x2d408e\\x2db18b\\x2d2f2baa9e9a02.device" ];
    after = [ "dev-disk-by\\x2duuid-f4782d9f\\x2daabe\\x2d408e\\x2db18b\\x2d2f2baa9e9a02.device" ];
    before = [ "sysroot.mount" ];
    unitConfig.DefaultDependencies = "no";
    path = with pkgs; [
      btrfs-progs
      coreutils
      findutils
      gawk
      util-linux
    ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
    };
    script = ''
      ${pkgs.coreutils}/bin/mkdir -p /btrfs_tmp
      ${pkgs.util-linux}/bin/mount -o subvol=/,nodiscard /dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02 /btrfs_tmp
      ${pkgs.coreutils}/bin/mkdir -p /btrfs_tmp/.snapshots
      if [ ! -e /btrfs_tmp/@swap ]; then
        ${pkgs.btrfs-progs}/bin/btrfs subvolume create /btrfs_tmp/@swap
      fi

      # Save pre-wipe @ — never auto-pruned, manual cleanup only
      SNAP_NAME="root.$(${pkgs.coreutils}/bin/date +%Y%m%dT%H%M%S)"
      ${pkgs.btrfs-progs}/bin/btrfs subvolume snapshot /btrfs_tmp/@ "/btrfs_tmp/.snapshots/$SNAP_NAME"

      # Delete nested child subvolumes of @ (required before deleting @)
      ${pkgs.btrfs-progs}/bin/btrfs subvolume list -o /btrfs_tmp/@ \
        | ${pkgs.gawk}/bin/awk '{print $NF}' \
        | ${pkgs.coreutils}/bin/sort -r \
        | while IFS= read -r child; do
            ${pkgs.btrfs-progs}/bin/btrfs subvolume delete "/btrfs_tmp/$child" 2>/dev/null || true
          done
      ${pkgs.btrfs-progs}/bin/btrfs subvolume delete /btrfs_tmp/@

      # Fresh empty root — impermanence and HM populate everything declaratively.
      ${pkgs.btrfs-progs}/bin/btrfs subvolume create /btrfs_tmp/@

      # Scaffold: early-boot placeholders derived from sinnix.persistence.initrdScaffold.
      ${scaffoldCmds}

      ${pkgs.coreutils}/bin/echo "Rolled back @ (saved to .snapshots/$SNAP_NAME)"

      ${pkgs.util-linux}/bin/umount /btrfs_tmp
    '';
  };
}
