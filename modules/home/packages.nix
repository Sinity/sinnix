{
  inputs,
  pkgs,
  config,
  lib,
  ...
}: {
  home.packages = with pkgs; [
    # GTK Themeing Packages (moved from gtk.nix)
    (gruvbox-gtk-theme.override {colorVariants = ["dark"];})
    (papirus-icon-theme.override {color = "black";})
    bibata-cursors

    # Gaming packages
    mangohud
    steam-run

    # Commented out gaming packages
    # steam-tui
    # protonup
    # bottles

    # Factorio with authentication token
    # (factorio.override {
    #   username = "Sinityy";
    #   token = "$FACTORIO_TOKEN";
    # })
    # (pkgs.writeShellScriptBin "factorio-steam" ''
    #   exec ${steam-run}/bin/steam-run ${factorio}/bin/factorio "$@"
    # '')

    inputs.browser-previews.packages.${pkgs.system}.google-chrome-beta
    inputs.browser-previews.packages.${pkgs.system}.google-chrome-dev
    # google-chrome
    #
    qutebrowser # A keyboard-driven, vim-like browser based on Python and Qt
    tor-browser-bundle-bin # Securely and easily download, verify, install, and launch Tor Browser in Linux
    yt-dlp

    obsidian # obsidian-wrapper
    taskwarrior3 # Taskwarrior, a command-line todo list manager
    timewarrior # Timewarrior, A command line time tracking application

    spotify
    mpv # media player
    mpvc # mpc-like controls for mpv
    svp # SmoothVideo Project 4 (SVP4)

    kitty # terminal emulator
    btop # system monitor
    rofi-wayland # application launcher
    wallust # generate colors from an image

    # ai
    # aider-chat-full # Temporarily disabled due to spacy dependency issues
    aider-chat # Use minimal version without problematic dependencies
    inputs.claude-desktop.packages.${system}.claude-desktop-with-fhs
    claude-code
    codex
    openai-whisper-cpp

    # temp, for building screen-pipe
    # crane
    # openssl
    # pkg-config
    # oniguruma
    # gcc
    # screen-pipe

    gpu-screen-recorder
    gpu-screen-recorder-gtk
    wf-recorder

    # Language Servers, Formatters, Linters (ensure these are needed outside nvim)
    markdown-oxide # Used by obsidian.nvim
    alejandra
    nixd
    nil
    nix-diff
    nixfmt-classic
    rustup
    # rust-analyzer # incompatible with rustup
    cargo-fuzz
    cargo-bump
    cargo-audit
    nodejs # Needed for some LSPs/Linters
    nodejs_latest

    # Database
    sqlite
    sqlitebrowser # SQLite Database browser is a light GUI editor for SQLite databases, built on top of Qt
    sqlite-vec
    sqlite-utils
    sqlitestudio

    tdf # cli pdf viewer
    zathura
    epy # CLI Ebook Reader
    nautilus
    transmission_3-gtk
    zotero # A free, easy-to-use tool to help you collect, organize, cite, and share your research sources.

    ani-cli
    trackma # A lightweight and simple program for updating and using lists on several media tracking websites.
    fanficfare # A tool for downloading fanfiction to eBook formats
    # imgbrd-grabber # Very customizable imageboard/booru downloader with powerful filenaming features.
    imgur-screenshot # Take screenshot selection, upload to imgur + more cool things

    ## CLI utility
    neovim
    asciinema
    eza # ls replacement
    entr # perform action when file change
    fd # find replacement
    ffmpeg
    file # Show file information
    killall
    libnotify
    man-pages # extra man pages
    ncdu # disk space
    nitch # systhem fetch util
    playerctl # controller for media players
    ripgrep # grep replacement
    tldr
    toipe # typing test in the terminal
    ttyper # cli typing test
    unzip
    unrar
    wl-clipboard # clipboard utils for wayland (wl-copy, wl-paste)
    cliphist # clipboard manager
    clipboard-jh # Cut, copy, and paste anything in your terminal.
    wget
    xdg-utils
    xxd
    weechat # IRC client
    cbonsai # terminal screensaver
    pipes # terminal screensaver
    tty-clock
    jq
    yq
    csvtool
    csvkit
    csvq
    procps
    psmisc
    evemu
    iotop
    bpftrace # for quick 'iosnoop', 'funccount' etc.
    chrome-export
    android-tools
    android-file-transfer

    # graphics stuff
    mesa-demos
    vulkan-tools # For `vulkaninfo`, `vkcube`
    vulkan-validation-layers # For validating Vulkan API usage
    wayland-utils # For `wayland-info`, `weston-info`
    libva-utils # For VAAPI diagnostics
    glxinfo # OpenGL info
    egl-wayland
    drm_info # Detailed info about Direct Rendering Manager
    sysstat # GPU memory usage and system stats
    usbview
    hw-probe
    hwdata
    graphicsmagick
    strace # For tracing system calls
    ltrace # For tracing library calls
    htop # For monitoring GPU utilization
    extundelete # extundelete is a utility that can recover deleted files from an ext3 or ext4 partition.
    nvitop
    cage
    wayland-protocols
    vkmark

    # other hw stuff Suggested By GPT ###
    # Core Hardware Diagnostics
    pciutils
    usbutils
    hwinfo
    inxi
    dmidecode
    lshw
    smartmontools
    nvme-cli
    udisks2

    # CPU and Memory
    cpuid
    i7z # A better i7 (and now i3, i5) reporting tool for Linux
    mcelog
    memtester
    numactl

    # Storage
    btrfs-progs
    xfsprogs
    e2fsprogs
    lvm2
    hdparm
    parted
    fio
    ioping
    bonnie

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

    # Peripheral & Input
    evtest
    libinput
    powertop
    fwupd
    acpi

    # Benchmarking
    sysbench
    stress-ng
    fio
    glmark2
    phoronix-test-suite
    ### END
    ###
    #########

    # nix stuff
    cachix
    nix-direnv
    nix-direnv-flakes

    ## GUI Apps
    audacity
    bleachbit # cache cleaner
    gimp
    libreoffice
    nix-prefetch-github
    soundwireserver # pass audio to android phone
    vlc

    # Python
    python3
    python3Packages.pip
    python312Packages.ipython

    # Dotfiles related
    stow # dotfiles management

    # Git related
    git
    gh # GitHub CLI
    delta
    lazygit # TUI for git
    onefetch # Git repo stats

    # Zsh related
    zsh
    oh-my-zsh
    zoxide # Managed via programs.zoxide in shell.nix
    fzf # Managed via programs.fzf in shell.nix
    skim # Fuzzy Finder in Rust!
    bat # Managed via programs.bat in shell.nix

    openssl

    # Arch ones
    daemonize # Run a program as a Unix daemon
    dtach # emulates the detach feature of screen
    lnch # A simple go binary that runs and disowns a command
    at # AT and batch delayed command scheduling utility and daemon

    programmer-calculator
    bc # An arbitrary precision calculator language
    calc # Arbitrary precision console calculator

    ddcutil # Query and change Linux monitor settings using DDC/CI and USB.
    evtest # Input device event monitor and query tool
    flex # A tool for generating text-scanning programs
    glances # CLI curses-based monitoring tool
    highlight # Fast and flexible source code highlighter (CLI version)
    httpie # human-friendly CLI HTTP client for the API era
    # imwheel  # Mouse wheel configuration tool for XFree86/Xorg
    # unclutter-xfixes  # A small program for hiding the mouse cursor
    inxi # Full featured CLI system information tool
    iotop # View I/O usage of processes
    libratbag # A DBus daemon to configure gaming mice

    meld # Compare files, directories and working copies
    # nvtop  # GPUs process monitoring for AMD, Intel and NVIDIA
    piper # GTK application to configure gaming mice
    pv # A terminal-based tool for monitoring the progress of data through a pipeline

    read-edid # Program that can get information from a PNP monitor
    redshift # Adjusts the color temperature of your screen according to your surroundings.

    rsync # A fast and versatile file copying tool for remote and local files

    fira-code # Monospaced font with programming ligatures
    # fira-code-nerdfont # Patched font Fira (Fura) Code from nerd fonts library
    hack-font # Patched font Hack from nerd fonts library
    # inconsolata-nerdfont # Patched font Inconsolata Go from nerd fonts library

    # digimend-kernel-drivers-dkms  # Linux kernel modules (DKMS) for non-Wacom USB graphics tablets
    # googler  # Google from the command-line
    hledger # Command-line interface for the hledger accounting system
    llm # Run inference for Large Language Models on CPU, with Rust
    mosh # Mobile shell, surviving disconnects with local echo and line editing
    single-file-cli # CLI tool for saving a faithful copy of a complete web page in a single HTML file
    # thorium-browser-bin  # Chromium fork focused on high performance and security
  ];
}
