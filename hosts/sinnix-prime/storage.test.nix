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
        "/swap"
        config.sinnix.paths.realmRoot
      ];
      optionsFor = mount: lib.attrByPath [ "fileSystems" mount "options" ] [ ] config;
      isOnlineDiscard = option: option == "discard" || option == "discard=async";
      polylogueShareMount = "/home/${config.sinnix.user.name}/.local/share/polylogue";
      polylogueMounts = builtins.filter (mount: mount.where == polylogueShareMount) config.systemd.mounts;
      persistedHomeDirs = map (
        entry: if builtins.isAttrs entry then entry.directory else entry
      ) config.sinnix.persistence.home.directories;
      storageModule = builtins.readFile (inputs.self + "/hosts/sinnix-prime/storage.nix");
      swapDevice = builtins.head config.swapDevices;
      udevRules = config.services.udev.extraRules;
      rollbackScript = config.boot.initrd.systemd.services.rollback-root.script;
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
          && lib.hasInfix "for mountpoint in /realm" storageModule
          && lib.hasInfix "fstrim --minimum 64MiB --verbose" storageModule;
        message = "sinnix-prime must trim large extents on the canonical NVMe data filesystem at idle priority instead of using all-mount fstrim";
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
          builtins.length config.swapDevices == 1
          && swapDevice.device == "/swap/swapfile"
          && swapDevice.size == 8 * 1024
          && builtins.elem "subvol=@swap" (optionsFor "/swap")
          && builtins.elem "nodatacow" (optionsFor "/swap");
        message = "swapfile must live on a dedicated non-snapshotted btrfs subvolume";
      }
      {
        # Swap must ride the NVMe realm filesystem, not the slower SATA root SSD
        # that froze the box under build-load swap thrash on 2026-06-03.
        assertion =
          config.fileSystems."/swap".device == config.fileSystems.${config.sinnix.paths.realmRoot}.device
          && config.fileSystems."/swap".device != config.fileSystems."/".device;
        message = "swap must live on the realm NVMe filesystem, not the SATA root device";
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
