{ pkgs, inputs, username, lib, ... }:
let
  baseCli = with pkgs; [
    wget
    git
  ];

  hardwareDiagnostics = with pkgs; [
    hwinfo
    inxi
    dmidecode
    lshw
    pciutils
    usbutils
    cpuid
    i7z
    mcelog
    memtester
    numactl
    hw-probe
    hwdata
  ];

  storageMaintenance = with pkgs; [
    btrfs-progs
    hdparm
    smartmontools
    nvme-cli
    parted
    fio
    ioping
    udisks2
    extundelete
    lvm2
    xfsprogs
    e2fsprogs
  ];

  networkingTools = with pkgs; [
    iputils
    ethtool
    iftop
    iperf3
  ];

  graphicsStacks = with pkgs; [
    mesa
    libGL
    libglvnd
  ];

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

in
{
  config = {
    environment = {
      systemPackages =
        lib.unique (
          baseCli
          ++ hardwareDiagnostics
          ++ storageMaintenance
          ++ networkingTools
          ++ graphicsStacks
          ++ (with pkgs; [ bpftrace ])
        )
        ++ [
          perfScan
        ];
    };

    programs = {
      direnv = {
        enable = true;
        silent = true;
        enableZshIntegration = true;
        enableBashIntegration = true;
        nix-direnv.enable = true;
      };

      steam = {
        enable = true;
        gamescopeSession.enable = true;
      };

      gamemode.enable = true;

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
