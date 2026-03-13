# Script Registry
#
# Central registry for scripts that need packaging (PATH, dependencies).
# Scripts in scripts/ are referenced directly by hyprland bindings via
# ${repoRoot}/scripts/... and don't need packaging unless they:
#   1. Need to be in PATH for shell use
#   2. Have runtime dependencies that must be in PATH
#
# Module-scoped scripts (mcp-*, crypto, storage) remain inline in their
# modules as they're tightly coupled to that configuration.
{ inputs, pkgs }:
let
  scriptPath = name: "${inputs.self}/scripts/${name}";

  # Helper to create a script wrapper
  mkScript =
    name:
    {
      description,
      runtimeInputs ? [ ],
      bashArgs ? "",
      runner ? null,
    }:
    {
      inherit description runtimeInputs;
      package = pkgs.writeShellApplication {
        inherit name runtimeInputs;
        text = ''
          RUNNER="${if runner != null then runner else ""}"
          if [ -n "$RUNNER" ]; then
            exec "$RUNNER" ${scriptPath name} "$@"
          fi
          exec ${pkgs.bash}/bin/bash ${bashArgs} ${scriptPath name} "$@"
        '';
      };
    };

  # Registry of scripts needing packaging
  registry = {
    # System utilities
    asbl-no-moar = mkScript "asbl-no-moar" {
      description = "Disable ASBL (Automatic Screen Brightness Limiting) on monitors";
      runtimeInputs = with pkgs; [
        coreutils
        procps
      ];
    };

    hogkill = mkScript "hogkill" {
      description = "Interactive memory hog killer with gum UI";
      runtimeInputs = with pkgs; [
        coreutils
        gum
        procps
        gawk
        gnugrep
        gnused
      ];
    };

    nuke-builds = mkScript "nuke-builds" {
      description = "Kill runaway build processes (cargo, nix-daemon, ninja)";
      runtimeInputs = with pkgs; [
        coreutils
        procps
        gnugrep
      ];
    };

    # Diagnostics
    perf-scan = mkScript "perf-scan" {
      description = "Comprehensive system performance benchmarking";
      runtimeInputs = with pkgs; [
        bash
        coreutils
        cpuid
        dmidecode
        ethtool
        fio
        flent
        gawk
        gnugrep
        gnused
        gum
        hw-probe
        hwdata
        i7z
        intel-gpu-tools
        inxi
        iperf3
        iproute2
        iw
        linuxPackages.turbostat
        lm_sensors
        mcelog
        memtester
        ncurses
        netperf
        nvme-cli
        numactl
        pciutils
        perf
        phoronix-test-suite
        powertop
        procps
        python3
        python3Packages.speedtest-cli
        rt-tests
        s-tui
        smartmontools
        stress-ng
        stressapptest
        sysbench
        sysstat
        usbutils
        util-linux
        glmark2
      ];
    };

    stability-lab = mkScript "stability-lab" {
      description = "Focused hardware stability runner with persistent reboot forensics";
      runtimeInputs = with pkgs; [
        bash
        below
        coreutils
        findutils
        gawk
        gnugrep
        gnused
        linuxPackages.turbostat
        lm_sensors
        nvme-cli
        procps
        smartmontools
        stress-ng
        stressapptest
        sudo
        systemd
        util-linux
      ];
    };

    launch-trigger-capture = mkScript "launch-trigger-capture" {
      description = "Capture granular launch-boundary telemetry for suspected reboot triggers";
      runtimeInputs = with pkgs; [
        bash
        coreutils
        findutils
        gawk
        gnugrep
        gnused
        lm_sensors
        pciutils
        procps
        strace
        systemd
        udev
        util-linux
      ];
    };

    # Audio control
    audio = mkScript "audio" {
      description = "Audio device and volume control with gum UI";
      runtimeInputs = with pkgs; [
        coreutils
        gum
        pulseaudio
        pamixer
      ];
    };

    media-preview-cache = mkScript "media-preview-cache" {
      description = "Precompute and query cached media preview thumbnails";
      runtimeInputs = with pkgs; [
        bash
        coreutils
        fd
        ffmpegthumbnailer
        findutils
        util-linux
      ];
    };

    # Rawlog utilities
    rawlog = mkScript "rawlog" {
      description = "Append and browse knowledgebase raw thought logs";
      runtimeInputs = with pkgs; [
        coreutils
        less
        gnused
        tofi
        libnotify
      ];
    };

    rawlog-capture = mkScript "rawlog-capture" {
      description = "Capture rawlog entries via gum UI";
      runtimeInputs = with pkgs; [
        coreutils
        gum
      ];
    };

    # Development helpers
    repo-map = mkScript "repo-map" {
      description = "Generate repository structure map";
      runtimeInputs = with pkgs; [
        coreutils
        fd
        gnused
        tree
      ];
    };

    lsp-root = mkScript "lsp-root" {
      description = "Find project root and exec command from there";
      runtimeInputs = with pkgs; [ coreutils ];
    };

    render-agents = mkScript "render-agents" {
      description = "Render CLAUDE.md @includes into generated AGENTS.md";
      runtimeInputs = with pkgs; [
        coreutils
        python3
      ];
      runner = "${pkgs.python3}/bin/python3";
    };

    normalize-agent-projects = mkScript "normalize-agent-projects" {
      description = "Normalize CLAUDE/AGENTS instruction docs across project repos";
      runtimeInputs = with pkgs; [
        coreutils
        findutils
        git
        gnugrep
      ];
    };

    verify-agent-topology = mkScript "verify-agent-topology" {
      description = "Verify CLAUDE/AGENTS topology and sync invariants across project repos";
      runtimeInputs = with pkgs; [
        coreutils
        findutils
        git
        gnugrep
        python3
      ];
    };

    # Storage utilities
    encrypt-folder = mkScript "encrypt-folder" {
      description = "Encrypt a folder using gocryptfs";
      runtimeInputs = with pkgs; [
        coreutils
        gocryptfs
        rsync
        util-linux
      ];
    };

    decrypt-folder = mkScript "decrypt-folder" {
      description = "Decrypt/mount a gocryptfs folder";
      runtimeInputs = with pkgs; [
        coreutils
        gocryptfs
      ];
    };

    mount-nextcloud = mkScript "mount-nextcloud" {
      description = "Mount Nextcloud WebDAV share";
      runtimeInputs = with pkgs; [
        coreutils
        util-linux
      ];
    };

    umount-nextcloud = mkScript "umount-nextcloud" {
      description = "Unmount Nextcloud WebDAV share";
      runtimeInputs = with pkgs; [
        coreutils
        util-linux
      ];
    };

    # System health
    sinnix-sentinel = mkScript "sinnix-sentinel" {
      description = "System health monitor with auto-derived checks";
      runtimeInputs = with pkgs; [
        coreutils
        findutils
        gawk
        python3
        jq
        systemd
        util-linux
        gnugrep
        procps
        sudo
        libnotify
        smartmontools
        borgbackup
      ];
    };
  };
in
{
  # Export packages for flake outputs
  packages = builtins.mapAttrs (_: v: v.package) registry;

  # Export registry metadata for documentation/tooling
  inherit registry;

  # List available scripts
  list = builtins.attrNames registry;
}
