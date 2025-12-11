# Host-specific storage configuration for sinnix-prime
{
  pkgs,
  lib,
  config,
  ...
}:
let
  inherit (config.sinnix.paths) realmRoot dataRoot outerRealm;
  username = config.sinnix.user.name;
  swapFileSizeGiB = 32;
  userCfg = config.users.users.${username} or { };
  userUid = builtins.toString (userCfg.uid or 1000);
  primaryGroupName = userCfg.group or "users";
  groupCfg = lib.attrByPath [ "users" "groups" primaryGroupName ] config { };
  primaryGroupId = builtins.toString (groupCfg.gid or 100);

  prepareSwapfile = pkgs.writeShellApplication {
    name = "prepare-swapfile";
    runtimeInputs = [
      pkgs.btrfs-progs
      pkgs.coreutils
      pkgs.e2fsprogs
      pkgs.util-linux
    ];
    text = ''
      set -euo pipefail

      swap_dir="/swap"
      swap_file="/swap/swapfile"
      desired_size=$(( ${toString swapFileSizeGiB} * 1024 * 1024 * 1024 ))

      mkdir -p "$swap_dir"
      chmod 700 "$swap_dir"
      chattr +C "$swap_dir" >/dev/null 2>&1 || true
      btrfs property set -ts "$swap_dir" compression none >/dev/null 2>&1 || true

      create_swap=0

      if [ -e "$swap_file" ]; then
        current_size=$(stat --printf=%s "$swap_file" 2>/dev/null || echo 0)
        if [ "$current_size" -ne "$desired_size" ]; then
          swapoff "$swap_file" >/dev/null 2>&1 || true
          rm -f "$swap_file"
          create_swap=1
        fi
      else
        create_swap=1
      fi

      if [ "$create_swap" -eq 1 ]; then
        btrfs filesystem mkswapfile --size ${toString swapFileSizeGiB}g "$swap_file"
        chmod 600 "$swap_file"
        mkswap "$swap_file" >/dev/null 2>&1
      else
        chmod 600 "$swap_file"
      fi
    '';
  };
in
{
  services = {
    fstrim.enable = true; # periodically TRIM ssd storage devices
    gvfs.enable = true; # dynamic mount
  };

  fileSystems = {
    "/" = {
      device = "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02";
      fsType = "btrfs";
      options = [
        "subvol=@"
        "compress=zstd"
        "noatime"
      ];
    };

    "/nix" = {
      device = "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02";
      fsType = "btrfs";
      options = [
        "subvol=@nix"
        "compress=zstd"
        "noatime"
      ];
    };

    "/var" = {
      device = "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02";
      fsType = "btrfs";
      options = [
        "subvol=@var"
        "compress=zstd"
        "noatime"
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

    "${realmRoot}" = {
      device = "/dev/disk/by-uuid/bd19092f-a195-47ab-9c0d-c923d1e5bfea";
      fsType = "btrfs";
      options = [
        "relatime"
        "lazytime"
        "nofail"
      ];
    };

    "/home/${username}" = {
      device = "${realmRoot}/home";
      fsType = "none";
      options = [ "bind" ];
      depends = [ realmRoot ];
    };

    "${outerRealm}" = {
      device = "/dev/disk/by-uuid/5119B4113C747C42";
      fsType = "ntfs";
      options = [
        "strictatime"
        "lazytime"
        "nofail"
        "uid=${userUid}"
        "gid=${primaryGroupId}"
        "umask=022"
        "big_writes"
      ];
    };

    # "/mnt/smol_ssd" = {
    #   device = "/dev/disk/by-uuid/481e214e-7bb6-49fa-bc87-ccb1f2c1e3c3";
    #   fsType = "btrfs";
    #   options = [
    #     "strictatime"
    #     "lazytime"
    #   ];
    # };
  };

  swapDevices = [
    {
      device = "/swap/swapfile";
    }
  ];

  systemd = {
    tmpfiles.rules = lib.mkAfter [
      "d /mnt/pendrv 0755 root root -"
      "d ${realmRoot}/knowledgebase 0755 ${username} users -"
      "d ${realmRoot}/inbox 0755 ${username} users -"
      "d ${dataRoot}/screenshot 0755 ${username} users -"
      "d ${dataRoot}/screenshot/mpv 0755 ${username} users -"
    ];

    services.prepare-swapfile = {
      description = "Prepare Btrfs swapfile";
      requiredBy = [ "swap-swapfile.swap" ];
      before = [
        "swap-swapfile.swap"
        "swap.target"
      ];
      after = [ "systemd-remount-fs.service" ];
      unitConfig = {
        # Avoid sysinit ↔ swap.target ordering cycles by taking explicit deps.
        DefaultDependencies = false;
      };
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${prepareSwapfile}/bin/prepare-swapfile";
      };
    };

    automounts = [
      {
        where = "/mnt/pendrv";
        wantedBy = [ "multi-user.target" ];
        automountConfig = {
          TimeoutIdleSec = "600s";
        };
      }
    ];

    mounts = lib.mkAfter (
      [
        {
          what = "${dataRoot}/syslog/journal";
          where = "/var/log/journal";
          type = "none";
          options = "bind,x-systemd.requires-mounts-for=${realmRoot}";
          wantedBy = [ "local-fs.target" ];
          requires = [ "realm.mount" ];
          after = [ "realm.mount" ];
        }
      ]
      ++ [
        {
          what = "/dev/disk/by-uuid/36213474-7e7f-4df7-8fb6-264d9a2e9643";
          where = "/mnt/pendrv";
          type = "btrfs";
          options = "nofail,compress=zstd,x-systemd.device-timeout=5s";
        }
      ]
    );
  };

  boot.supportedFilesystems = [
    "btrfs"
    "ntfs"
  ];
}
