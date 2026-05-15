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
        assertion = !(config.services.fstrim.enable or false);
        message = "sinnix-prime must not schedule automatic fstrim while storage pressure is unresolved";
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
    ];
}
