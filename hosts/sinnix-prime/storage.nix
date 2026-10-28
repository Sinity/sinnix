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
    # btrbk (unsafe to block-snapshot a live database); recovery is the daily
    # dump and the content-store Borg job (modules/services/sinex/bridge.nix).
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
    # The 2026-10-28 interactive IO sample found the raw NVMe at 25/1 but
    # /realm's btrfs BDI at 100/0 (max_ratio/strict_limit). The old block udev
    # rule therefore never bounded /realm's buffered writes. Resolve the BDI
    # through the mounted filesystem UUID; btrfs-N changes between boots.
    # This restores the intended 256 MiB share of the global 1 GiB dirty
    # budget, reserving headroom for writers on the desktop's other SSD.
    # It does not remove shared Btrfs transaction or synchronous IO waits.
    services.sinnix-realm-writeback = {
      description = "Bound Realm Btrfs dirty writeback independently of the desktop SSD";
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
        printf '1\n' > "$bdi/strict_limit"
      '';
    };

    # One scrub a week rather than all three on the 1st at midnight, where they
    # met the snapshot and the realm Borg run.
    services."btrfs-scrub--".serviceConfig = scrubServiceConfig;
    services."btrfs-scrub-realm".serviceConfig = scrubServiceConfig;
    services."btrfs-scrub-outer\\x2drealm".serviceConfig = scrubServiceConfig;
    timers."btrfs-scrub--".timerConfig.OnCalendar = lib.mkForce "*-*-01 02:30:00";
    timers."btrfs-scrub-realm".timerConfig.OnCalendar = lib.mkForce "*-*-08 02:30:00";
    timers."btrfs-scrub-outer\\x2drealm".timerConfig.OnCalendar = lib.mkForce "*-*-15 02:30:00";

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
