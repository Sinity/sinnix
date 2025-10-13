# Scripts

{ pkgs, inputs, ... }:
let
  toggle_waybar = pkgs.writeScriptBin "toggle_waybar" ''
    #!/usr/bin/env bash
    set -euo pipefail

    if systemctl --user --quiet is-active waybar.service; then
      systemctl --user stop waybar.service
    else
      systemctl --user start waybar.service
    fi
  '';

  perfScan = pkgs.writeShellApplication {
    name = "perf-scan";
    runtimeInputs = with pkgs; [
      bash
      bc
      coreutils
      findutils
      gawk
      gnugrep
      gum
      hdparm
      intel-gpu-tools
      inxi
      iperf3
      iproute2
      jq
      ethtool
      flent
      lm_sensors
      memtester
      netperf
      nvme-cli
      pciutils
      perf
      linuxPackages.turbostat
      phoronix-test-suite
      powertop
      procps
      python3
      python312Packages.speedtest-cli
      rt-tests
      s-tui
      smartmontools
      stress-ng
      stressapptest
      sysbench
      sysstat
      util-linux
      vkmark
      glmark2
    ];
    text = builtins.readFile "${inputs.self}/scripts/perf-scan";
  };

  kittyGrid = pkgs.writeShellApplication {
    name = "kitty-image-grid";
    runtimeInputs = with pkgs; [
      coreutils
      findutils
      file
      kitty
      python3
    ];
    text = builtins.readFile "${inputs.self}/assets/kitty-image-grid.sh";
  };

  visionModelsSync = pkgs.writeShellApplication {
    name = "sync-vision-models";
    runtimeInputs = with pkgs; [
      bash
      coreutils
      curl
      openssl
    ];
    text = builtins.readFile "${inputs.self}/scripts/sync-vision-models";
  };
in
{
  environment.systemPackages = [
    toggle_waybar
    perfScan
    kittyGrid
    visionModelsSync
  ];
}
