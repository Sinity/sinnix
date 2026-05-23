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
      swapDevice = builtins.head config.swapDevices;
      udevRules = config.services.udev.extraRules;
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
        assertion = !(config.services.fstrim.enable or false);
        message = "sinnix-prime must not schedule automatic fstrim while storage pressure is unresolved";
      }
      {
        assertion =
          lib.hasInfix ''KERNEL=="nvme[0-9]n[0-9]"'' udevRules
          && lib.hasInfix ''ATTR{queue/wbt_lat_usec}="0"'' udevRules
          && lib.hasInfix ''ATTR{queue/nr_requests}="64"'' udevRules;
        message = "sinnix-prime NVMe queues must be bounded while nvme0 write timeouts are unresolved";
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
          && swapDevice.size == 64 * 1024
          && builtins.elem "subvol=@swap" (optionsFor "/swap")
          && builtins.elem "nodatacow" (optionsFor "/swap");
        message = "swapfile must live on a dedicated non-snapshotted btrfs subvolume";
      }
    ];
}
