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
      persistedHomeDirs = map (
        entry: if builtins.isAttrs entry then entry.directory else entry
      ) config.sinnix.persistence.home.directories;
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
          && config.systemd.services ? sinnix-fstrim
          && config.systemd.timers ? sinnix-fstrim;
        message = "sinnix-prime must trim large extents on the canonical NVMe data filesystem at idle priority instead of using all-mount fstrim";
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
    ];
}
