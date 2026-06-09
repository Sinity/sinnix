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
  # OOM burst buffer — not a normal pressure sink. swappiness=10 keeps anon
  # resident and reclaims file cache first, so this space is only consumed under
  # genuine memory exhaustion. It must be large enough that earlyoom (which fires
  # on AND: mem<10% AND swap<25%) has reaction time before the system runs dry.
  #
  # 8 GiB proved insufficient (2026-06-08): ~7 GiB accumulated from idle paging
  # left only ~1 GiB of burst headroom; a nix build + substrate promote consumed
  # that in seconds, filling swap completely and causing an NVMe I/O storm that
  # froze all three terminal windows before earlyoom could react.
  #
  # 32 GiB gives earlyoom's 25% threshold (= 8 GiB free) room to fire ~14 GiB
  # above the idle-paging residue baseline before the system locks up. The old
  # 64 GiB was wrong because it enabled the 17 GiB swap-thrash (swappiness=60,
  # now fixed); 32 GiB is right because swappiness=10 won't fill it lazily.
  swapSizeGiB = 32;

  # The realm btrfs lives on the Crucial P3 NVMe. Swap and /realm share this one
  # physical filesystem (swap rides a dedicated nested @swap subvolume), so they
  # are bound to a single symbol to keep the two mounts from drifting apart.
  realmFsDevice = "/dev/disk/by-uuid/43701cf7-7880-4e0c-9725-b6e12d91898a";

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
    # Keep discard as explicit manual maintenance on this host. The active
    # workstation baseline favors predictable foreground I/O over automatic
    # discard bursts on the root and realm SSDs.
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

    # Btrfs on this workstation coordinates write ordering itself; block-layer
    # WBT adds another latency throttle in front of fsync-heavy workloads.
    # Keep the Crucial P3 NVMe conservative while giving the root/Nix MX500
    # enough request tags for store writes, build scratch, and journald.
    udev.extraRules = ''
      ACTION=="add|change", SUBSYSTEM=="block", ENV{DEVTYPE}=="disk", ENV{ID_SERIAL_SHORT}=="2003E282E456", ATTR{queue/wbt_lat_usec}="0", ATTR{queue/nr_requests}="256"
      ACTION=="add|change", SUBSYSTEM=="block", ENV{DEVTYPE}=="disk", ENV{ID_SERIAL_SHORT}=="2247E6897FB8", ATTR{queue/wbt_lat_usec}="0", ATTR{queue/nr_requests}="64"
      ACTION=="add|change", SUBSYSTEM=="block", ENV{DEVTYPE}=="disk", KERNEL=="sd[b-z]", ATTR{queue/wbt_lat_usec}="0"
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

    # Swap lives on the NVMe (realm) filesystem, not the slower SATA root SSD.
    # A disk swapfile on the contended SATA root froze the box under build load
    # (2026-06-03 swap-thrash livelock); the NVMe's far lower latency and deeper
    # queue keep heavy eviction from stalling interactive work. The dedicated
    # @swap subvolume (created by realm-swap-subvol.service) stays out of the
    # 15-minute btrbk realm snapshots, so the swapfile's extents are never
    # CoW-shared. nofail keeps boot resilient if the subvolume is ever absent.
    "/swap" = {
      device = realmFsDevice;
      fsType = "btrfs";
      options = [
        "subvol=@swap"
        "nodatacow"
        "noatime"
        "nodiscard"
        "nofail"
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

    # The old Samsung 960 EVO cache/swap device is not part of the active
    # storage topology. Cache consumers use root-backed defaults instead.

    "${realmRoot}" = {
      device = realmFsDevice;
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

    # 14TB Seagate Exos X18 - torrent/media bulk storage. Keep it out of
    # Btrfs CoW/compression; torrent payloads are large, random-write, and
    # usually already compressed.
    "${neoOuterRealm}" = {
      device = "/dev/disk/by-uuid/2e20423b-bc3a-4953-8662-393f8aea9f2b";
      fsType = "btrfs";
      options = [
        "subvol=@data"
        "nodatacow"
        "noatime"
        "noauto"
        "nofail"
        "x-systemd.automount"
        "x-systemd.idle-timeout=10min"
      ];
    };

  };

  # Swap lives on a dedicated Btrfs subvolume so it survives root rollback,
  # stays out of snapshots, and is created without CoW/compression/holes.
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

    # Swap rides a dedicated @swap subvolume on the realm btrfs so it stays out
    # of btrbk's recursive-free realm snapshots. Realm is never rolled back, so
    # in practice this creates the subvolume once; the guard keeps boot working
    # if realm is ever restored from backup without it. Ordered after the realm
    # mount (its top level is where the child subvolume is created) and before
    # the /swap mount that consumes it.
    services.realm-swap-subvol = {
      description = "Ensure dedicated @swap subvolume exists on the realm NVMe btrfs";
      requiredBy = [ "swap.mount" ];
      before = [ "swap.mount" ];
      requires = [ "realm.mount" ];
      after = [ "realm.mount" ];
      unitConfig.DefaultDependencies = false;
      path = [ pkgs.btrfs-progs ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      };
      script = ''
        if ! btrfs subvolume show ${realmRoot}/@swap >/dev/null 2>&1; then
          btrfs subvolume create ${realmRoot}/@swap
        fi
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

      # Hidden payloads under mountpoint directories are out of scope for the
      # root rollback snapshot. The live mounts for these paths are separate
      # subvolumes/devices; anything under @ here is stale pre-mount data.
      for path in nix swap persist realm outer-realm neo-outer-realm; do
        if [ -d "/btrfs_tmp/@/$path" ]; then
          ${pkgs.findutils}/bin/find "/btrfs_tmp/@/$path" -mindepth 1 -xdev -exec ${pkgs.coreutils}/bin/rm -rf -- {} +
        fi
      done
      for cache_path in /btrfs_tmp/@/root/.cache /btrfs_tmp/@/var/cache /btrfs_tmp/@/home/*/.cache; do
        if [ -d "$cache_path" ]; then
          ${pkgs.findutils}/bin/find "$cache_path" -mindepth 1 -xdev -exec ${pkgs.coreutils}/bin/rm -rf -- {} +
        fi
      done

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
