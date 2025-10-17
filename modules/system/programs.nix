{ pkgs, inputs, username, ... }:
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

  devPackages = with pkgs; [
    breakpad
    cargo-bloat
    cargo-deny
    cargo-depgraph
    cargo-expand
    cargo-flamegraph
    cargo-llvm-lines
    cargo-machete
    cargo-outdated
    cargo-udeps
    cbonsai
    cmake
    cocogitto
    d2
    drm_info
    dua
    duckdb
    flent
    fselect
    gcc
    gdb
    git-annex
    git-cliff
    gitstats
    glmark2
    glxinfo
    gnumake
    gnuplot
    google-cloud-sdk
    gource
    hyperfine
    intel-gpu-tools
    libva-utils
    linuxPackages.cpupower
    linuxPackages.turbostat
    lm_sensors
    man-pages
    man-pages-posix
    mesa-demos
    meson
    miller
    ncdu
    netperf
    ninja
    nitch
    nix-doc
    nix-fast-build
    nix-health
    nix-index
    nix-prefetch-git
    nix-tree
    perf
    phoronix-test-suite
    pikchr
    pipes
    plantuml
    ploticus
    powertop
    python312Packages.speedtest-cli
    rt-tests
    s-tui
    scc
    stress-ng
    stressapptest
    structurizr-cli
    sysbench
    sysstat
    toipe
    tty-clock
    ttyper
    uv
    visidata
    vulkan-tools
    vulkan-validation-layers
    wayland-utils
    xan
    zk
  ];
in
{
  config = {
    environment = {
      systemPackages =
        (with pkgs; [
          wget
          git

          hwinfo
          inxi
          dmidecode
          lshw
          pciutils
          usbutils

          btrfs-progs
          hdparm
          smartmontools
          nvme-cli

          iputils
          ethtool
          iftop
          iperf3

          mesa
          libGL
          libglvnd

          cpuid
          i7z
          mcelog
          memtester
          numactl
          hw-probe
          hwdata

          xfsprogs
          e2fsprogs
          lvm2
          parted
          fio
          ioping
          udisks2
          extundelete

          bpftrace
        ])
        ++ devPackages
        ++ [
          toggle_waybar
          perfScan
          kittyGrid
          visionModelsSync
        ];
      variables.REALM_ROOT = "/realm";
    };

    programs = {
      direnv = {
        enable = true;
        silent = true;
        enableZshIntegration = true;
        enableBashIntegration = true;
        nix-direnv.enable = true;
      };

      dconf.enable = true;

      zsh =
        let
          ttyAutostart = ''
            if [ "$(id -un)" = "${username}" ] && [ -z "$DISPLAY" ]; then
              current_tty=$(tty 2>/dev/null || true)
              if [ "$current_tty" = "/dev/tty1" ]; then
                exec uwsm start hyprland-uwsm.desktop
              fi
            fi
          '';
        in
        {
          enable = true;
          loginShellInit = ttyAutostart;
        };

      gnupg.agent = {
        enable = true;
        enableSSHSupport = true;
      };
    };

    systemd.coredump.enable = true;

    services = {
      dbus.enable = true;

      earlyoom = {
        enable = true;
        enableNotifications = true;
        freeMemThreshold = 5;
        freeSwapThreshold = 5;
        reportInterval = 5;
        extraArgs = [
          "-g"
          "-p"
          "--prefer"
          "(^|/)(java|chromium|obsidian|google-chrome(-stable)?)$"
          "--avoid"
          "(^|/)(init|systemd|sshd)$"
        ];
      };

      gnome.gnome-keyring.enable = true;
    };
  };
}
