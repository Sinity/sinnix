# Host-specific storage configuration for sinnix-prime
{
  lib,
  pkgs,
  config,
  ...
}:
let
  scrubServiceConfig = {
    Slice = "background.slice";
    IOWeight = 10;
    CPUWeight = 5;
  };
  # Each filesystem is on its own device (/ SATA SSD, /realm NVMe,
  # /outer-realm HDD), so their night passes run side by side.
  scrubTargets = {
    root = {
      mountpoint = "/";
      cycleDays = 30;
    };
    realm = {
      mountpoint = "/realm";
      cycleDays = 30;
    };
    outer-realm = {
      mountpoint = "/outer-realm";
      cycleDays = 91;
    };
  };
  mkScrubService = name: fs: {
    description = "Night-window btrfs scrub of ${fs.mountpoint}";
    path = [
      pkgs.btrfs-progs
      pkgs.coreutils
      pkgs.gnugrep
    ];
    serviceConfig = scrubServiceConfig // {
      StateDirectory = "sinnix-scrub";
      # Stopping the unit cancels the scrub; btrfs keeps its position.
      ExecStopPost = "-${pkgs.btrfs-progs}/bin/btrfs scrub cancel ${fs.mountpoint}";
    };
    script = ''
      stamp=/var/lib/sinnix-scrub/${name}.completed
      status=$(btrfs scrub status ${fs.mountpoint} || true)
      if printf '%s\n' "$status" | grep -qE 'Status:[[:space:]]+(aborted|interrupted)'; then
        btrfs scrub resume -B ${fs.mountpoint}
      elif [ ! -f "$stamp" ] || [ $(( $(date +%s) - $(date -r "$stamp" +%s) )) -ge ${
        toString (fs.cycleDays * 86400)
      } ]; then
        btrfs scrub start -B ${fs.mountpoint}
      else
        exit 0
      fi
      date -Iseconds > "$stamp"
    '';
  };
  scrubTimer = {
    wantedBy = [ "timers.target" ];
    timerConfig.OnCalendar = "*-*-* 01:00:00";
  };
  inherit (config.sinnix.paths)
    realmRoot
    outerRealm
    neoOuterRealm
    ;
  username = config.sinnix.user.name;
  primaryGroupName = config.users.users.${username}.group;
  # CLI, daemon, and XDG consumers share one archive directory.
  polylogueDbRoot = config.sinnix.services.polylogue.dataDir;
  polylogueShareMount = "/home/${username}/.local/share/polylogue";

  realmFsUuid = "43701cf7-7880-4e0c-9725-b6e12d91898a";
  realmFsDevice = "/dev/disk/by-uuid/${realmFsUuid}";

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

  fstrimJob =
    lib.sinnix.mkScheduledJob
      {
        inherit config;
        unitName = "sinnix-fstrim";
        description = "Trim canonical NVMe data filesystem";
        surface = config.sinnix.runtime.units.sinnix-fstrim;
      }
      {
        resourceClass = "background";
        execStart = "${fstrimCanonical}/bin/sinnix-fstrim-canonical";
        timer = {
          onCalendar = "weekly";
          randomizedDelaySec = "1h";
          persistent = true;
        };
      };
in
{
  sinnix.backup.genomeRoot = "${neoOuterRealm}/content/genome";

  # The /realm NVMe (Crucial P3 4 TB, QLC, 87% full). Coefficients from fio on
  # a No_COW 4 GiB file on /realm (O_DIRECT, 20 s each: 4M at depth 16 for
  # bytes, 4k at depth 64 for IOPS), taken 2026-11-01 under a build wave, so
  # they are a floor; the QoS lets the virtual rate rise to 6x while
  # latencies hold. Writes are what the drive cannot sustain (24 MB/s
  # direct 4M writes once its SLC cache is spent). With the kernel's
  # automatic SSD profile and no latency targets the virtual rate sat at
  # 243% while I/O pressure stayed above 80%, so no weight took effect.
  sinnix.machine.blockCost.CT4000P3SSD8 = {
    model = "rbps=1171981054 rseqiops=14123 rrandiops=26675 wbps=24114864 wseqiops=2633 wrandiops=924";
    qos = "rpct=90.00 rlat=10000 wpct=90.00 wlat=50000 min=50.00 max=600.00";
  };
  services = {
    # The 12 TB genome HDD is idle apart from snapshot cuts and the nightly
    # drain; it parks after 10 idle minutes instead of spinning (and
    # vibrating) all day. hdparm -S is a drive setting lost at power-off.
    udev.extraRules = ''
      ACTION=="add", SUBSYSTEM=="block", KERNEL=="sd*", ENV{DEVTYPE}=="disk", ENV{ID_SERIAL}=="OOS14000G_00064481", RUN+="${pkgs.hdparm}/bin/hdparm -S 120 /dev/%k"
    '';

    # Keep online discard disabled on this host; run batched trim from a
    # low-priority timer instead. Do not use the stock all-filesystems fstrim
    # unit: this host has many Btrfs bind mounts and snapshot mounts, and the
    # root/Nix MX500 has shown very long FITRIM latency even after backlog
    # cleanup. Scheduled trim therefore covers large extents on the NVMe realm
    # filesystem only; root trim remains an explicit off-hours maintenance
    # action.
    fstrim.enable = false;
    gvfs.enable = true; # dynamic mount

  };

  fileSystems = {
    # Keep the workspace namespace stable while its large data tree lives on
    # the HDD. The automount fails access when that disk is unavailable rather
    # than letting callers populate the underlying NVMe mountpoint.
    "${realmRoot}/health/genome" = {
      device = "${neoOuterRealm}/content/genome";
      fsType = "none";
      depends = [ neoOuterRealm ];
      options = [
        "bind"
        "nofail"
        "x-systemd.automount"
        "x-systemd.idle-timeout=10min"
        "x-systemd.mount-timeout=60s"
      ];
    };
    # Historical evidence keeps its canonical paths on the archive disk.
    # The automount fails access when that disk is unavailable.
    "${realmRoot}/archive/backup/polylogue/2026-08-16-live" = {
      device = "${neoOuterRealm}/archive/polylogue/2026-08-16-live";
      fsType = "none";
      depends = [ neoOuterRealm ];
      options = [
        "bind"
        "ro"
        "nofail"
        "x-systemd.automount"
        "x-systemd.idle-timeout=10min"
        "x-systemd.mount-timeout=60s"
      ];
    };
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

    # There is no @var subvol: /var is a plain dir inside @, populated by
    # /persist bind-mounts declared in modules/persistence.nix.

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

    # Dedicated /state/sinex subvolume on /realm NVMe, not the ephemeral @ root, so
    # Postgres data survives rollback. Per-file chattr +C (inherited, not a
    # whole-mount nodatacow) keeps database writes in place. Excluded from
    # btrbk (unsafe to block-snapshot a live database); recovery uses Sinex's
    # immutable core artifact and paired content/key Borg archives.
    "/var/lib/sinex" = {
      device = "/dev/disk/by-uuid/43701cf7-7880-4e0c-9725-b6e12d91898a";
      fsType = "btrfs";
      options = [
        "subvol=/state/sinex"
        "compress=zstd:3"
        "noatime"
        "nofail"
      ];
    };

    # Nix build directories hold whole build trees (crane builds write their
    # target dirs here); on the root SSD they were its largest writer.
    "/var/cache/nix-build" = {
      device = "${realmRoot}/state/cache/nix-build";
      fsType = "none";
      options = [
        "bind"
        "nofail"
      ];
      depends = [ "/realm" ];
    };

    # Retained Sinex cache mount. Its retirement belongs to the product's
    # storage migration. /realm/state/cache is excluded from backups
    # (regenerable caches, see modules/backup.nix realmExcludes).
    "/var/cache/sinex" = {
      device = "/realm/state/cache/sinex";
      fsType = "none";
      options = [
        "bind"
        "nofail"
      ];
      depends = [ "/realm" ];
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
      device = realmFsDevice;
      fsType = "btrfs";
      options = [
        "subvol=/"
        "compress=zstd"
        # Capture lake is write-heavy; atime writes on read are pure waste.
        "noatime"
        "lazytime"
        "nodiscard"
        "nofail"
      ];
    };

    # There is no /realm/home bind mount: /home/${username} is ephemeral (part
    # of @, wiped every boot by the rollback-root initrd script) and populated
    # from /persist bind-mounts plus Home Manager activation.

    # 6TB HGST
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

  systemd = {
    services.sinnix-fstrim = fstrimJob.systemd.services.sinnix-fstrim;

    # Btrfs owns a filesystem BDI, separate from the block device's BDI.
    # Resolve it through the mounted filesystem UUID; btrfs-N changes at boot.
    # Keep a soft 25% share of the global dirty budget for this filesystem.
    # Strict enforcement also shrinks each writeback cgroup's share and can
    # pause writers while the global budget remains mostly unused. The global
    # 1 GiB dirty limit bounds the combined backlog; IO-cost paces device work.
    services.sinnix-realm-writeback = {
      description = "Set Realm Btrfs buffered-write share";
      wantedBy = [ "multi-user.target" ];
      requires = [ "realm.mount" ];
      after = [
        "realm.mount"
        "systemd-sysctl.service"
      ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      };
      script = ''
        bdi=/sys/fs/btrfs/${realmFsUuid}/bdi
        printf '25\n' > "$bdi/max_ratio"
        printf '0\n' > "$bdi/strict_limit"
      '';
    };

    # Scrub runs only in a night window. On a single-device btrfs filesystem a
    # scrub detects corruption (metadata is DUP, data is not), so its value is
    # early warning to restore from backup, not repair. A full pass of /realm
    # (2.9 TiB on QLC NVMe) takes about 38 h at the rate the device sustains
    # under load; run around the clock at a throttled rate it competed with
    # builds and PostgreSQL for days. Each filesystem's pass therefore runs
    # 01:00-07:00 only; at 07:00 the unit is stopped, which cancels the scrub
    # with its progress kept, and the next night resumes it until it finishes.
    #   /            monthly    315 GiB   about one night
    #   /realm       monthly    2.9 TiB   about six nights
    #   /outer-realm quarterly  4.9 TiB   HDD (separate device), several nights
    # A new pass starts when the last completed one is older than the cycle;
    # completion dates live in /var/lib/sinnix-scrub.
    services.sinnix-scrub-root = mkScrubService "root" scrubTargets.root;
    services.sinnix-scrub-realm = mkScrubService "realm" scrubTargets.realm;
    services.sinnix-scrub-outer-realm = mkScrubService "outer-realm" scrubTargets.outer-realm;
    services.sinnix-scrub-window-end = {
      description = "End the night scrub window";
      serviceConfig.Type = "oneshot";
      script = "systemctl stop ${
        lib.concatMapStringsSep " " (n: "sinnix-scrub-${n}.service") (lib.attrNames scrubTargets)
      }";
    };
    timers.sinnix-scrub-root = scrubTimer;
    timers.sinnix-scrub-realm = scrubTimer;
    timers.sinnix-scrub-outer-realm = scrubTimer;
    timers.sinnix-scrub-window-end = {
      wantedBy = [ "timers.target" ];
      timerConfig.OnCalendar = "*-*-* 07:00:00";
    };

    timers.sinnix-fstrim = fstrimJob.systemd.timers.sinnix-fstrim;

    # Ensure the dedicated sinex subvolume exists on the /realm NVMe (not the
    # MX500) before /var/lib/sinex is mounted, creating it nodatacow;
    # idempotent, so this is a no-op on an already-provisioned host and only
    # matters for a fresh install/restore. /realm is the filesystem's top
    # level (subvol=/), so it works there. It used to mount subvolid=5 itself
    # with no other options; when that won the race against realm.mount it
    # was the filesystem's first mount, and btrfs kept its options for every
    # mount: no compression and async discard instead of /realm's declared
    # compress=zstd and nodiscard (observed through 2026-10-27).
    services.ensure-sinex-subvol = {
      description = "Ensure dedicated sinex nodatacow subvolume exists on the /realm NVMe";
      requires = [ "realm.mount" ];
      requiredBy = [ "var-lib-sinex.mount" ];
      before = [ "var-lib-sinex.mount" ];
      # Provisioning, needed before the mount, not a service of the running
      # host: restarting it at switch stops the mount and with it Postgres
      # and sinexd. An edited script takes effect at the next boot.
      restartIfChanged = false;
      after = [
        "local-fs-pre.target"
        "realm.mount"
      ];
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
        install -d ${realmRoot}/state
        root=${realmRoot}/state/sinex
        if ! btrfs subvolume show "$root" >/dev/null 2>&1; then
          btrfs subvolume create "$root"
          chattr +C "$root" || true
        fi
        # The roots the Sinex units need before their own tmpfiles rules
        # run (idempotent; ownership matches modules/services/sinex/bridge.nix).
        install -d -o postgres -g postgres -m 0700 "$root/postgresql"
        install -d -o sinex -g sinex -m 0750 "$root/daemon"
        # Postgres rewrites pages in place; under copy-on-write each rewrite
        # becomes a new extent (a 1 GB relation reached 49k). Files and
        # directories created inside inherit the attribute; files that exist
        # before it is set keep copy-on-write until copied.
        chattr +C "$root/postgresql"
      '';
    };

    services.ensure-journal-source = {
      description = "Provision the persistent journal bind source when absent";
      requires = [ "realm.mount" ];
      after = [ "realm.mount" ];
      requiredBy = [ "var-log-journal.mount" ];
      before = [ "var-log-journal.mount" ];
      unitConfig.DefaultDependencies = false;
      path = [
        pkgs.btrfs-progs
        pkgs.coreutils
      ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      };
      script = ''
        root=/realm/state/journal
        parent=/realm/state
        # Existing native stores retain their bytes and metadata. Converting
        # an ordinary directory to a subvolume needs a separate migration.
        if [ -L "$parent" ] || { [ -e "$parent" ] && [ ! -d "$parent" ]; }; then
          echo "Journal source parent is not a directory" >&2
          exit 1
        fi
        if [ -L "$root" ] || { [ -e "$root" ] && [ ! -d "$root" ]; }; then
          echo "Journal source is not a directory" >&2
          exit 1
        fi
        if [ -d "$root" ]; then
          exit 0
        fi
        if [ ! -d "$parent" ]; then
          install -d -o ${lib.escapeShellArg username} -g ${lib.escapeShellArg primaryGroupName} -m 0755 "$parent"
        fi
        btrfs subvolume create "$root"
        chown root:systemd-journal "$root"
        chmod 2755 "$root"
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
        if ! btrfs subvolume show ${lib.escapeShellArg polylogueDbRoot} >/dev/null 2>&1; then
          btrfs subvolume create ${lib.escapeShellArg polylogueDbRoot}
          chattr +C ${lib.escapeShellArg polylogueDbRoot} || true
        fi
        chown ${username}:${primaryGroupName} ${lib.escapeShellArg polylogueDbRoot}
        chmod 0700 ${lib.escapeShellArg polylogueDbRoot}
        chattr +C ${lib.escapeShellArg polylogueDbRoot} || true
      '';
    };

    tmpfiles.rules = lib.mkAfter [
      "d /swap 0750 root root -"
      "d ${polylogueDbRoot} 0700 ${username} ${primaryGroupName} -"
      "d /home/${username}/.local/share 0700 ${username} ${primaryGroupName} -"
      "d ${polylogueShareMount} 0700 ${username} ${primaryGroupName} -"
      # Bind-mount source for /var/cache/sinex, under the operator-owned
      # regenerable-cache root that modules/core.nix declares. Excluded from
      # btrbk→borg — never persist-grade data.
      "d ${realmRoot}/state/cache/sinex 0775 ${username} users -"
      "d ${realmRoot}/state/cache/nix-build 0755 root root -"
      "h ${realmRoot}/state/cache/nix-build - - - - +C"
      # The session producer fsyncs small appends; on CoW each one rewrote whole
      # extents (5.6 GB written for 44 MB of frames). New segments inherit No_COW.
      "H ${config.services.sinex.session.stateDir}/spool - - - - +C"
      # Stash's SQLite database is rewritten in place; new files inherit No_COW.
      "h ${realmRoot}/state/stashbox - - - - +C"
    ];

    # XDG consumers use the same archive as the configured daemon and MCP.
    # The bind mount keeps writes on the existing NVMe subvolume.
    mounts = [
      {
        what = polylogueDbRoot;
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

  sinnix.persistence.system.directories = [ "/var/lib/sinnix-scrub" ];
  sinnix.persistence.initrdScaffold.directories = lib.mkAfter [
    "/home/${username}/.local/share"
    polylogueShareMount
  ];

  sinnix.runtime.units.sinnix-fstrim = {
    unit = "sinnix-fstrim.service";
    resourceClass = "background";
    notifyOnFailure = true;
  };

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
      ${pkgs.btrfs-progs}/bin/btrfs subvolume snapshot -r /btrfs_tmp/@ "/btrfs_tmp/.snapshots/$SNAP_NAME"

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
