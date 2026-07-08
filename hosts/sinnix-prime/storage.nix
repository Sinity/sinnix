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
  # The one-time copy-and-symlink migration (archive DB -> db/polylogue subvol)
  # completed (sinnix-qs7, verified 2026-07-08: all polylogueDbFiles are live
  # symlinks to polylogueDbRoot). Retired the WAL/sidecar-checking migration
  # dance; kept only the steady-state sanity check + fresh-bootstrap symlink
  # creation, which is all realm-scaffold needs going forward.
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
      elif [ ! -e ${lib.escapeShellArg archivePath} ] && [ -e ${lib.escapeShellArg targetPath} ]; then
        ln -s ${lib.escapeShellArg targetPath} ${lib.escapeShellArg archivePath}
      fi
    ''
  ) polylogueDbFiles;
  polylogueShareMount = "/home/${username}/.local/share/polylogue";

  swapFile = "/swap/swapfile";
  swapSizeGiB = 4;

  # Keep swap as a small file-backed overflow signal, not an extension of RAM.
  # zram is disabled in modules/profiles/workstation.nix because compressed-RAM swap
  # competes with the real working set and can leave stale pressure after build
  # bursts. The 4 GiB file below gives the kernel a bounded emergency landing
  # zone while earlyoom kills once meaningful swap is occupied.
  prepareSwapfile = pkgs.writeShellApplication {
    name = "sinnix-prime-prepare-swapfile";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.e2fsprogs
      pkgs.util-linux
    ];
    text = ''
      set -euo pipefail

      swap_dir="$(dirname ${swapFile})"
      desired_size=$(( ${toString swapSizeGiB} * 1024 * 1024 * 1024 ))

      mkdir -p "$swap_dir"
      chmod 700 "$swap_dir"

      if [ ! -e "${swapFile}" ]; then
        chattr +C "$swap_dir" 2>/dev/null || true
      fi

      current_size=0
      if [ -f "${swapFile}" ]; then
        current_size=$(stat --printf=%s "${swapFile}" 2>/dev/null || echo 0)
      fi

      if [ "$current_size" -ne "$desired_size" ]; then
        swapoff "${swapFile}" >/dev/null 2>&1 || true
        rm -f "${swapFile}"
        touch "${swapFile}"
        chattr +C "${swapFile}" 2>/dev/null || true
        fallocate -l ${toString swapSizeGiB}G "${swapFile}"
        chmod 600 "${swapFile}"
        mkswap "${swapFile}" >/dev/null
      else
        chmod 600 "${swapFile}"
      fi
    '';
  };
  drainSwapfile = pkgs.writeShellApplication {
    name = "sinnix-prime-drain-swapfile";
    runtimeInputs = [
      pkgs.gawk
      pkgs.util-linux
    ];
    text = ''
      set -euo pipefail

      swap_file=${lib.escapeShellArg swapFile}
      min_headroom_kib=$(( 2 * 1024 * 1024 ))

      if ! swapon --noheadings --raw --show=NAME | awk -v swap_file="$swap_file" '$1 == swap_file { found = 1 } END { exit found ? 0 : 1 }'; then
        exit 0
      fi

      read -r mem_available_kib swap_total_kib swap_free_kib < <(
        awk '
          $1 == "MemAvailable:" { mem = $2 }
          $1 == "SwapTotal:" { total = $2 }
          $1 == "SwapFree:" { free = $2 }
          END { print mem + 0, total + 0, free + 0 }
        ' /proc/meminfo
      )

      swap_used_kib=$(( swap_total_kib - swap_free_kib ))
      if [ "$swap_used_kib" -le 0 ]; then
        exit 0
      fi

      if [ "$mem_available_kib" -le "$(( swap_used_kib + min_headroom_kib ))" ]; then
        echo "Leaving swap resident: MemAvailable=''${mem_available_kib}KiB SwapUsed=''${swap_used_kib}KiB" >&2
        exit 0
      fi

      swapoff "$swap_file"
      swapon "$swap_file"
    '';
  };

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
        # Capture lake is write-heavy; atime writes on read are pure waste.
        # Matches root's noatime (was relatime — an unintentional divergence).
        "noatime"
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

  swapDevices = [
    {
      device = swapFile;
      priority = 10;
    }
  ];

  systemd = {
    services.prepare-swapfile = {
      description = "Create and maintain the bounded sinnix-prime swapfile";
      requiredBy = [ "swap-swapfile.swap" ];
      before = [ "swap-swapfile.swap" ];
      after = [
        "systemd-remount-fs.service"
      ];
      unitConfig.DefaultDependencies = false;
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${prepareSwapfile}/bin/sinnix-prime-prepare-swapfile";
      };
    };

    services.sinnix-drain-swapfile = {
      description = "Drain resident pages from the bounded sinnix-prime swapfile";
      after = [
        "swap-swapfile.swap"
        "multi-user.target"
      ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${drainSwapfile}/bin/sinnix-prime-drain-swapfile";
        Nice = 10;
        IOSchedulingClass = "idle";
        IOSchedulingPriority = 7;
      };
    };

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

    timers.sinnix-drain-swapfile = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "2min";
        OnUnitActiveSec = "5min";
        AccuracySec = "30s";
        Persistent = false;
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
      "d /swap 0750 root root -"
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
          ${pkgs.findutils}/bin/find "/btrfs_tmp/@/$path" -mindepth 1 -xdev -ignore_readdir_race -exec ${pkgs.coreutils}/bin/rm -rf -- {} + || true
        fi
      done
      for cache_path in /btrfs_tmp/@/root/.cache /btrfs_tmp/@/var/cache /btrfs_tmp/@/home/*/.cache; do
        if [ -d "$cache_path" ]; then
          ${pkgs.findutils}/bin/find "$cache_path" -mindepth 1 -xdev -ignore_readdir_race -exec ${pkgs.coreutils}/bin/rm -rf -- {} + || true
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
