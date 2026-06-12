{ lib, inputs, ... }:
{
  name = "host-sinnix-prime-storage-discard-policy";
  modules = [
    { imports = [ (inputs.self + "/hosts/sinnix-prime") ]; }
  ];
  assertions =
    config:
    let
      ssdBtrfsMounts = [
        "/"
        "/nix"
        "/persist"
        config.sinnix.paths.realmRoot
      ];
      optionsFor = mount: lib.attrByPath [ "fileSystems" mount "options" ] [ ] config;
      isOnlineDiscard = option: option == "discard" || option == "discard=async";
      polylogueShareMount = "/home/${config.sinnix.user.name}/.local/share/polylogue";
      polylogueMounts = builtins.filter (mount: mount.where == polylogueShareMount) config.systemd.mounts;
      polylogueDbRoot = "${config.sinnix.paths.realmRoot}/db/polylogue";
      realmScaffoldScript = config.systemd.services.realm-scaffold.script;
      persistedHomeDirs = map (
        entry: if builtins.isAttrs entry then entry.directory else entry
      ) config.sinnix.persistence.home.directories;
      storageModule = builtins.readFile (inputs.self + "/hosts/sinnix-prime/storage.nix");
      udevRules = config.services.udev.extraRules;
      rollbackScript = config.boot.initrd.systemd.services.rollback-root.script;
      scrubServices = [
        config.systemd.services."btrfs-scrub--".serviceConfig
        config.systemd.services."btrfs-scrub-realm".serviceConfig
        config.systemd.services."btrfs-scrub-outer\\x2drealm".serviceConfig
      ];
    in
    [
      {
        assertion = builtins.all (mount: builtins.elem "nodiscard" (optionsFor mount)) ssdBtrfsMounts;
        message = "sinnix-prime SSD btrfs mounts must explicitly disable online discard";
      }
      {
        assertion = builtins.all (mount: !(builtins.any isOnlineDiscard (optionsFor mount))) ssdBtrfsMounts;
        message = "sinnix-prime SSD btrfs mounts must not enable online discard";
      }
      {
        assertion =
          !(config.services.fstrim.enable or false)
          && config.systemd.services.sinnix-fstrim.serviceConfig.IOSchedulingClass == "idle"
          && config.systemd.timers.sinnix-fstrim.timerConfig.OnCalendar == "weekly"
          && lib.hasInfix "mountpoint=/realm" storageModule
          && lib.hasInfix "fstrim --minimum 64MiB --verbose" storageModule;
        message = "sinnix-prime must trim large extents on the canonical NVMe data filesystem at idle priority instead of using all-mount fstrim";
      }
      {
        assertion = builtins.all (
          service: service.Slice == "background.slice" && service.IOWeight == 1 && service.CPUWeight == 5
        ) scrubServices;
        message = "sinnix-prime btrfs scrubs must run in the background resource class";
      }
      {
        assertion =
          lib.hasInfix ''ID_SERIAL_SHORT}=="2247E6897FB8"'' udevRules
          && lib.hasInfix ''ATTR{queue/wbt_lat_usec}="0"'' udevRules
          && lib.hasInfix ''ATTR{queue/nr_requests}="64"'' udevRules
          && !(lib.hasInfix ''KERNEL=="nvme[0-9]n[0-9]"'' udevRules);
        message = "sinnix-prime Crucial P3 queue policy must be model-specific and conservative";
      }
      {
        assertion =
          lib.hasInfix ''ID_SERIAL_SHORT}=="2003E282E456"'' udevRules
          && lib.hasInfix ''ATTR{queue/nr_requests}="256"'' udevRules;
        message = "sinnix-prime root/Nix MX500 queue must leave enough request tags for builds and journald";
      }
      {
        assertion =
          polylogueMounts != [ ]
          && (builtins.head polylogueMounts).what == "${config.sinnix.paths.capturesRoot}/polylogue"
          && (builtins.head polylogueMounts).type == "none";
        message = "Polylogue archive path must bind to /realm captures, not root/persist SATA storage";
      }
      {
        assertion = !(builtins.elem ".local/share/polylogue" persistedHomeDirs);
        message = "Polylogue archive bytes must not be impermanence-mounted from /persist";
      }
      {
        assertion =
          lib.hasInfix "btrfs subvolume show ${polylogueDbRoot}" realmScaffoldScript
          && lib.hasInfix "btrfs subvolume create ${polylogueDbRoot}" realmScaffoldScript
          && lib.hasInfix "chattr +C ${polylogueDbRoot}" realmScaffoldScript
          && lib.hasInfix "d ${config.sinnix.paths.realmRoot}/db 0755 root root -" (
            lib.concatStringsSep "\n" config.systemd.tmpfiles.rules
          );
        message = "Polylogue SQLite DB root must be a dedicated nodatacow subvolume under /realm/db";
      }
      {
        assertion =
          lib.hasInfix "index.db-wal" realmScaffoldScript
          && lib.hasInfix "index.db-shm" realmScaffoldScript
          && lib.hasInfix "Refusing to migrate Polylogue DB while SQLite sidecar exists" realmScaffoldScript
          && lib.hasInfix "cp --reflink=never" realmScaffoldScript;
        message = "Polylogue DB migration must avoid splitting live SQLite WAL/SHM state and must rewrite into nodatacow extents";
      }
      {
        assertion =
          builtins.all
            (
              name:
              lib.hasInfix "${config.sinnix.paths.capturesRoot}/polylogue/${name}" realmScaffoldScript
              && lib.hasInfix "${polylogueDbRoot}/${name}" realmScaffoldScript
              && lib.hasInfix "ln -s ${polylogueDbRoot}/${name}" realmScaffoldScript
            )
            [
              "index.db"
              "source.db"
              "embeddings.db"
              "user.db"
              "ops.db"
              "daemon_events.db"
            ];
        message = "Every known Polylogue SQLite tier must be symlinked from the archive root into the DB subvolume";
      }
      {
        # Disk swap deleted 2026-06-12: both swapfiles were liability-only on
        # this host. Freeze-prevention is cgroup MemoryMax caps + earlyoom; a
        # 4 GiB zram cushion (modules/performance.nix) replaces disk swap.
        assertion = config.swapDevices == [ ] && !(builtins.hasAttr "/swap" config.fileSystems);
        message = "sinnix-prime must carry no disk swap (zram-only)";
      }
      {
        # sinex Postgres durability fix (2026-06-12): the operational substrate
        # rides a dedicated @sinex subvolume (survives the @-rollback) with
        # nodatacow (no CoW write-amplification on the DB). Previously it lived
        # on the ephemeral @ and was re-initdb'd every boot.
        assertion =
          builtins.hasAttr "/var/lib/sinex" config.fileSystems
          && builtins.elem "subvol=@sinex" (optionsFor "/var/lib/sinex")
          && builtins.elem "nodatacow" (optionsFor "/var/lib/sinex")
          && config.fileSystems."/var/lib/sinex".device == config.fileSystems."/".device;
        message = "sinex substrate must be a durable nodatacow @sinex subvol on the root device";
      }
      {
        assertion =
          lib.hasInfix "for path in nix swap persist realm outer-realm neo-outer-realm" rollbackScript
          && lib.hasInfix "/btrfs_tmp/@/home/*/.cache" rollbackScript
          && lib.hasInfix "btrfs subvolume snapshot /btrfs_tmp/@" rollbackScript;
        message = "root rollback snapshots must exclude hidden mountpoint payloads and caches before capture";
      }
    ];
}
