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
  polylogueDbRoot = "${realmRoot}/db/polylogue";
  polylogueDbFiles = [
    "index.db"
    "source.db"
    "embeddings.db"
    "user.db"
    "ops.db"
    "daemon_events.db"
  ];
  polylogueDbLinkScript = lib.concatMapStringsSep "\n" (
    name:
    let
      archivePath = "${polylogueArchiveRoot}/${name}";
      targetPath = "${polylogueDbRoot}/${name}";
    in
    ''
      if [ -L ${lib.escapeShellArg archivePath} ]; then
        current="$(readlink ${lib.escapeShellArg archivePath})"
        if [ "$current" != ${lib.escapeShellArg targetPath} ]; then
          echo "Refusing to replace unexpected Polylogue DB symlink ${archivePath} -> $current" >&2
          exit 1
        fi
      elif [ -e ${lib.escapeShellArg archivePath} ]; then
        for sidecar in ${lib.escapeShellArg "${archivePath}-wal"} ${lib.escapeShellArg "${archivePath}-shm"}; do
          if [ -e "$sidecar" ]; then
            echo "Refusing to migrate Polylogue DB while SQLite sidecar exists: $sidecar" >&2
            echo "Stop polylogued and checkpoint/truncate WAL before running realm-scaffold." >&2
            exit 1
          fi
        done
        if [ -e ${lib.escapeShellArg targetPath} ]; then
          echo "Refusing to overwrite existing Polylogue DB target ${targetPath}" >&2
          exit 1
        fi
        cp --reflink=never --preserve=mode,ownership,timestamps ${lib.escapeShellArg archivePath} ${lib.escapeShellArg "${targetPath}.tmp"}
        mv ${lib.escapeShellArg "${targetPath}.tmp"} ${lib.escapeShellArg targetPath}
        rm ${lib.escapeShellArg archivePath}
        ln -s ${lib.escapeShellArg targetPath} ${lib.escapeShellArg archivePath}
      elif [ -e ${lib.escapeShellArg targetPath} ]; then
        ln -s ${lib.escapeShellArg targetPath} ${lib.escapeShellArg archivePath}
      fi
    ''
  ) polylogueDbFiles;
  polylogueShareMount = "/home/${username}/.local/share/polylogue";

  # Disk swap removed (2026-06-12): both disk swapfiles were pure liability on
  # this host. A SATA-root swapfile froze the box under build load (2026-06-03
  # thrash livelock); moving it to the NVMe avoided the freeze but still wrote
  # the worn drives and never actually prevented OOM — earlyoom fires on the
  # memory threshold regardless. Freeze-prevention now comes from cgroup
  # MemoryMax caps on the build/nix-build slices (a runaway is killed inside its
  # slice, not by paging) plus a small zram cushion (see modules/performance.nix)
  # that absorbs sub-second spikes with zero disk I/O. No disk swap = no thrash
  # path and no swap-write wear on either SSD.
  realmFsDevice = "/dev/disk/by-uuid/43701cf7-7880-4e0c-9725-b6e12d91898a";

  # Initrd scaffold: early-boot placeholders derived from persistence config
  scaffoldCfg = config.sinnix.persistence.initrdScaffold;
  scaffoldDirs = lib.unique (scaffoldCfg.directories ++ map builtins.dirOf scaffoldCfg.files);
  scaffoldCmds = lib.concatStringsSep "\n" (
    map (d: "mkdir -p /btrfs_tmp/@${d}") scaffoldDirs
    ++ map (f: "touch /btrfs_tmp/@${f}") scaffoldCfg.files
  );
  fstrimCanonical = pkgs.writeShellApplication {
    name = "sinnix-fstrim-canonical";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.findutils
      pkgs.util-linux
    ];
    text = ''
      set -eu

      mountpoint=/realm
      if findmnt --mountpoint "$mountpoint" >/dev/null; then
        fstrim --minimum 64MiB --verbose "$mountpoint"
      fi
    '';
  };
in
{
  services = {
    # Keep online discard disabled on this host; run batched trim from a
    # low-priority timer instead. Do not use the stock all-filesystems fstrim
    # unit: this host has many Btrfs bind mounts and snapshot mounts, and the
    # root/Nix MX500 has shown very long FITRIM latency even after backlog
    # cleanup. Scheduled trim therefore covers large extents on the NVMe realm
    # filesystem only; root trim remains an explicit off-hours maintenance
    # action.
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
    # by /persist bind-mounts declared in modules/persistence.nix. (The historical
    # @var subvol is gone from disk as of 2026-06-12 — no top-level @var remains.)

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

    # sinex operational substrate (PostgreSQL + sinex home + state) on a dedicated
    # @sinex subvolume. Was previously a plain dir inside the EPHEMERAL @ root, so
    # the Postgres data dir was re-initdb'd on every boot (a durability bug — sinex
    # is meant to be durable). A dedicated top-level subvol survives the @-rollback,
    # and `nodatacow` makes the DB write in-place instead of CoW-amplifying every
    # random page write (~7× fewer writes, the dominant MX500 wear source). It is
    # deliberately NOT in btrbk's snapshot set (block-snapshotting a live DB is
    # unsafe). Durability is the persistent subvol itself; FOLLOW-UP: add a
    # logical pg_dump backup for disaster recovery, since nodatacow implies no
    # btrfs checksums (standard for DB volumes) and this subvol sits outside the
    # btrbk→borg path.
    "/var/lib/sinex" = {
      device = "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02";
      fsType = "btrfs";
      options = [
        "subvol=@sinex"
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

  # No disk swap on this host — see the comment in the `let` block above and
  # the zram cushion in modules/performance.nix.
  swapDevices = [ ];

  systemd = {
    services.sinnix-fstrim = {
      description = "Trim canonical NVMe data filesystem";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${fstrimCanonical}/bin/sinnix-fstrim-canonical";
        Nice = 10;
        IOSchedulingClass = "idle";
        IOSchedulingPriority = 7;
      };
    };

    services."btrfs-scrub--".serviceConfig = {
      Slice = "background.slice";
      IOWeight = 1;
      CPUWeight = 5;
    };

    services."btrfs-scrub-realm".serviceConfig = {
      Slice = "background.slice";
      IOWeight = 1;
      CPUWeight = 5;
    };

    services."btrfs-scrub-outer\\x2drealm".serviceConfig = {
      Slice = "background.slice";
      IOWeight = 1;
      CPUWeight = 5;
    };

    timers.sinnix-fstrim = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "weekly";
        RandomizedDelaySec = "1h";
        Persistent = true;
      };
    };

    # Ensure the dedicated @sinex subvolume exists before /var/lib/sinex is
    # mounted. The root btrfs top level (subvolid=5) is not normally mounted, so
    # mount it transiently to create the child subvol with nodatacow. Idempotent:
    # on an already-provisioned host @sinex already exists and this is a no-op;
    # the guard keeps a fresh install / bare-metal restore booting.
    services.ensure-sinex-subvol = {
      description = "Ensure dedicated @sinex nodatacow subvolume exists on the root btrfs";
      requiredBy = [ "var-lib-sinex.mount" ];
      before = [ "var-lib-sinex.mount" ];
      after = [ "local-fs-pre.target" ];
      unitConfig.DefaultDependencies = false;
      path = [
        pkgs.btrfs-progs
        pkgs.util-linux
        pkgs.e2fsprogs
        pkgs.coreutils
      ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      };
      script = ''
        dev=/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02
        tmp=$(mktemp -d)
        mount -o subvolid=5 "$dev" "$tmp"
        root="$tmp/@sinex"
        if ! btrfs subvolume show "$root" >/dev/null 2>&1; then
          btrfs subvolume create "$root"
          chattr +C "$root" || true
        fi
        # Pre-create the directory skeleton the sinex services' systemd mount
        # namespacing (ReadWritePaths) requires to PRE-EXIST. On the old layout
        # these were on @ and recreated each boot by tmpfiles; the bridge's
        # tmpfiles now run before this mount, so create them here directly on the
        # @sinex subvol (idempotent; ownership matches modules/services/sinex).
        install -d -o postgres -g postgres -m 0750 "$root/postgresql" "$root/postgresql/18"
        install -d -o sinex -g sinex -m 0711 "$root/home"
        install -d -o sinex -g sinex -m 0700 "$root/state" "$root/state/tls"
        install -d -o sinex -g sinex -m 0750 \
          "$root/state/run" "$root/state/logs" "$root/state/blob-repository" \
          "$root/state/spool" "$root/state/spool/event_engine"
        umount "$tmp"
        rmdir "$tmp"
      '';
    };

    services.realm-scaffold = {
      description = "Create /realm-backed bind mount source directories and DB subvolumes";
      requires = [ "realm.mount" ];
      after = [ "realm.mount" ];
      before = [
        "home-${username}-.local-share-polylogue.mount"
      ];
      unitConfig.DefaultDependencies = false;
      serviceConfig.Type = "oneshot";
      path = [
        pkgs.btrfs-progs
        pkgs.coreutils
        pkgs.e2fsprogs
      ];
      script = ''
        install -d -m 0700 -o ${username} -g ${primaryGroupName} ${polylogueArchiveRoot}
        install -d -m 0755 -o root -g root ${realmRoot}/db
        if ! btrfs subvolume show ${lib.escapeShellArg polylogueDbRoot} >/dev/null 2>&1; then
          btrfs subvolume create ${lib.escapeShellArg polylogueDbRoot}
          chattr +C ${lib.escapeShellArg polylogueDbRoot} || true
        fi
        chown ${username}:${primaryGroupName} ${lib.escapeShellArg polylogueDbRoot}
        chmod 0700 ${lib.escapeShellArg polylogueDbRoot}
        chattr +C ${lib.escapeShellArg polylogueDbRoot} || true

        ${polylogueDbLinkScript}
      '';
    };

    tmpfiles.rules = lib.mkAfter [
      "d ${polylogueArchiveRoot} 0700 ${username} ${primaryGroupName} -"
      "d ${realmRoot}/db 0755 root root -"
      "d /home/${username}/.local/share 0700 ${username} ${primaryGroupName} -"
      "d ${polylogueShareMount} 0700 ${username} ${primaryGroupName} -"
    ];

    # Polylogue's archive is an active SQLite/write-heavy workload. Keep the
    # default XDG path stable for CLI/MCP/service consumers, but place the
    # archive bytes on /realm's NVMe instead of the root/persist SATA SSD.
    # The six SQLite tier files are symlinked into a nested nodatacow subvolume
    # at ${polylogueDbRoot}; SQLite creates WAL/SHM files beside the symlink
    # target, so DB churn is excluded from /realm btrbk snapshots while blob/
    # and inbox/ remain in the snapshotted archive root.
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
