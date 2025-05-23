{
  pkgs,
  ...
}:
{
  # System utilities and tools
  programs.btop = {
    enable = true;
    settings = {
      color_theme = "gruvbox_dark";
      vim_keys = true;
      update_ms = 2000;
      show_cpu_freq = true;
      show_gpu = true;
      mem_graphs = true;
      proc_sorting = "cpu direct";
      proc_filter = false;
      tree_view = false;
      proc_per_core = true;
      proc_mem_bytes = true;
      cpu_graph_upper = "total";
      cpu_graph_lower = "user";
      cpu_invert_lower = true;
    };
  };

  home.packages = with pkgs; [
    # Core system utilities
    killall
    procps
    psmisc
    iotop
    bpftrace # for quick 'iosnoop', 'funccount' etc.

    # CLI utilities
    asciinema
    eza # ls replacement
    entr # perform action when file change
    fd # find replacement
    file # Show file information
    libnotify
    man-pages # extra man pages
    ncdu # disk space
    nitch # system fetch util
    # playerctl # Moved to media domain
    ripgrep # grep replacement
    tldr
    toipe # typing test in the terminal
    ttyper # cli typing test
    unzip
    unrar
    # wget # Moved to communication domain
    xdg-utils
    xxd

    # Desktop utilities
    wl-clipboard # clipboard utils for wayland (wl-copy, wl-paste)
    cliphist # clipboard manager
    clipboard-jh # Cut, copy, and paste anything in your terminal.
    redshift # Adjust color temperature

    # Hardware management and diagnostics
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

    # Storage utilities
    btrfs-progs
    xfsprogs
    e2fsprogs
    lvm2
    hdparm
    parted
    fio
    ioping
    smartmontools
    nvme-cli
    udisks2
    extundelete

    # Networking
    iputils
    iproute2
    ethtool
    iftop
    iperf3
    nmap
    tcpdump
    wireshark-cli
    traceroute
    mtr

    # Graphics and display
    mesa
    libGL
    libglvnd
    mesa-demos
    vulkan-tools
    vulkan-validation-layers
    wayland-utils
    libva-utils
    glxinfo
    egl-wayland
    drm_info
    hw-probe
    hwdata
    graphicsmagick

    # Terminal toys and screensavers
    cbonsai
    pipes
    tty-clock

    # Nix utilities
    cachix
    nix-direnv
    nix-direnv-flakes
  ];
}
