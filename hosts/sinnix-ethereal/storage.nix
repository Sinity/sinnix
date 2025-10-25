{ pkgs, lib, ... }:
let
  swapFile = "/swap/swapfile";
  swapSizeGiB = 4;

  prepareSwapfile = pkgs.writeShellApplication {
    name = "prepare-swapfile";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.util-linux
    ];
    text = ''
      set -euo pipefail

      swap_dir="$(dirname ${swapFile})"
      desired_size=$(( ${toString swapSizeGiB} * 1024 * 1024 * 1024 ))

      mkdir -p "$swap_dir"
      chmod 700 "$swap_dir"

      current_size=0
      if [ -f "${swapFile}" ]; then
        current_size=$(stat --printf=%s "${swapFile}" 2>/dev/null || echo 0)
      fi

      if [ "$current_size" -ne "$desired_size" ]; then
        swapoff "${swapFile}" >/dev/null 2>&1 || true
        rm -f "${swapFile}"
        fallocate -l ${toString swapSizeGiB}G "${swapFile}"
        chmod 600 "${swapFile}"
        mkswap "${swapFile}" >/dev/null 2>&1
      else
        chmod 600 "${swapFile}"
      fi
    '';
  };
in
{
  swapDevices = [
    {
      device = swapFile;
    }
  ];

  systemd.tmpfiles.rules = lib.mkAfter [
    "d /swap 0750 root root -"
  ];

  systemd.services.prepare-swapfile = {
    description = "Create and maintain swapfile for sinnix-ethereal";
    requiredBy = [ "swap-swapfile.swap" ];
    before = [ "swap-swapfile.swap" ];
    after = [
      "systemd-remount-fs.service"
      "local-fs.target"
    ];
    unitConfig.DefaultDependencies = false;
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${prepareSwapfile}/bin/prepare-swapfile";
    };
  };
}
