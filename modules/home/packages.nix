{ inputs, pkgs, ... }: 
{
  home.packages = (with pkgs; [
    floorp
    google-chrome

    # new
    # screen-pipe
    # code-cursor
    obsidian # obsidian-wrapper

    openai-whisper-cpp

    ueberzugpp

    # awatcher
    nix-diff

    zathura

    hydrus

    ## CLI utility
    ani-cli
    bitwise                           # cli tool for bit / hex manipulation
    caligula                          # User-friendly, lightweight TUI for disk imaging
    cliphist                          # clipboard manager
    eza                               # ls replacement
    entr                              # perform action when file change
    fd                                # find replacement
    ffmpeg
    file                              # Show file information 
    gtt                               # google translate TUI
    gifsicle                          # gif utility
    gtrash                            # rm replacement, put deleted files in system trash
    hexdump
    imv                               # image viewer
    killall
    lazygit
    libnotify
	  man-pages					            	  # extra man pages
    # mpv                               # video player
    ncdu                              # disk space
    nitch                             # systhem fetch util
    openssl
    onefetch                          # fetch utility for git repo
    pamixer                           # pulseaudio command line mixer
    playerctl                         # controller for media players
    poweralertd
    programmer-calculator
    qview                             # minimal image viewer
    ripgrep                           # grep replacement
    tdf                               # cli pdf viewer
    tldr
    todo                              # cli todo list
    toipe                             # typing test in the terminal
    ttyper                            # cli typing test
    unzip
    valgrind                          # c memory analyzer
    wl-clipboard                      # clipboard utils for wayland (wl-copy, wl-paste)
    wget
    yazi                              # terminal file manager
    # yt-dlp-light
    xdg-utils
    xxd

    ## CLI 
    cbonsai                           # terminal screensaver
    cmatrix
    pipes                             # terminal screensaver
    sl
    tty-clock                         # cli clock

    weechat 			      # IRC client

    ## GUI Apps
    audacity
    bleachbit                         # cache cleaner
    gimp
    libreoffice
    nix-prefetch-github
    pavucontrol                       # pulseaudio volume controle (GUI)
    qalculate-gtk                     # calculator
    soundwireserver                   # pass audio to android phone
    vlc
    winetricks
    wineWowPackages.wayland
    zenity

    # C / C++
    gcc
    gdb
    gnumake

    # Python
    python3
    python312Packages.ipython

    inputs.alejandra.defaultPackage.${system}
  ]);
}

#   home.packages = (with pkgs; [
#     ranger ueberzugpp
#
#     ## CLI utility
#     ani-cli
#     bitwise                           # cli tool for bit / hex manipulation
#     caligula                          # User-friendly, lightweight TUI for disk imaging
#     cliphist                          # clipboard manager
#     eza                               # ls replacement
#     entr                              # perform action when file change
#     fd                                # find replacement
#     ffmpeg
#     file                              # Show file information 
#     gtt                               # google translate TUI
#     gifsicle                          # gif utility
#     gtrash                            # rm replacement, put deleted files in system trash
#     hexdump
#     imv                               # image viewer
#     killall
#     lazygit
#     libnotify
# 	  man-pages					            	  # extra man pages
#     # mpv                               # video player
#     ncdu                              # disk space
#     nitch                             # systhem fetch util
#     openssl
#     onefetch                          # fetch utility for git repo
#     pamixer                           # pulseaudio command line mixer
#     playerctl                         # controller for media players
#     poweralertd
#     programmer-calculator
#     qview                             # minimal image viewer
#     ripgrep                           # grep replacement
#     tdf                               # cli pdf viewer
#     tldr
#     todo                              # cli todo list
#     toipe                             # typing test in the terminal
#     ttyper                            # cli typing test
#     unzip
#     valgrind                          # c memory analyzer
#     wl-clipboard                      # clipboard utils for wayland (wl-copy, wl-paste)
#     wget
#     yazi                              # terminal file manager
#     yt-dlp-light
#     xdg-utils
#     xxd
#
#     ## CLI 
#     cbonsai                           # terminal screensaver
#     cmatrix
#     pipes                             # terminal screensaver
#     sl
#     tty-clock                         # cli clock
#
#     weechat 			      # IRC client
#
#     ## GUI Apps
#     audacity
#     bleachbit                         # cache cleaner
#     gimp
#     libreoffice
#     nix-prefetch-github
#     pavucontrol                       # pulseaudio volume controle (GUI)
#     qalculate-gtk                     # calculator
#     soundwireserver                   # pass audio to android phone
#     vlc
#     winetricks
#     wineWowPackages.wayland
#     zenity
#
#     # C / C++
#     gcc
#     gdb
#     gnumake
#
#     # Python
#     python3
#     python312Packages.ipython
#
#     inputs.alejandra.defaultPackage.${system}
#
#     # mine
#     arbtt  # Automatic Rule-Based Time Tracker
#     at  # AT and batch delayed command scheduling utility and daemon
#     audacity  # A program that lets you manipulate digital audio waveforms
#     autoconf  # GNU tool for automatically configuring source code
#     automake  # A GNU tool for automatically creating Makefiles
#     # base  # Minimal package set to define a basic Arch Linux installation (Not applicable in NixOS)
#     bat  # Cat clone with syntax highlighting and git integration
#     bc  # An arbitrary precision calculator language
#     bluez  # Development and debugging utilities for the bluetooth protocol stack
#     broot  # Fuzzy Search + tree + cd
#     btrfs-progs  # Btrfs filesystem utilities
#     calc  # Arbitrary precision console calculator
#     clang  # C language family frontend for LLVM
#     clinfo  # Simple OpenCL application that enumerates all available platform and device properties
#     linuxPackages.cpupower  # Linux kernel tool to examine and tune power saving related features of your processor
#     csvkit  # A suite of utilities for converting to and working with CSV
#     ddcutil  # Query and change Linux monitor settings using DDC/CI and USB.
#     debugedit  # Tool to mangle source locations in .debug files
#     dhcpcd  # DHCP/ IPv4LL/ IPv6RA/ DHCPv6 client
#     discord  # All-in-one voice and text chat for gamers
#     dmidecode  # Desktop Management Interface table related utilities
#     dunst  # Customizable and lightweight notification-daemon
#     earlyoom  # Early OOM Daemon for Linux
#     efibootmgr  # Linux user-space application to modify the EFI Boot Manager
#     espeak-ng  # Multi-lingual software speech synthesizer
#     evtest  # Input device event monitor and query tool
#     # expac  # alpm data (pacman database) extraction utility (Not directly available in nixpkgs)
#     eza  # A modern replacement for ls (community fork of exa)
#     fakeroot  # Tool for simulating superuser privileges
#     fd  # Simple, fast and user-friendly alternative to find
#     feh  # Fast and light imlib2-based image viewer
#     ffmpegthumbnailer  # Lightweight video thumbnailer that can be used by file managers
#     file  # File type identification utility
#     findutils  # GNU utilities to locate files
#     flex  # A tool for generating text-scanning programs
#     fzf  # Command-line fuzzy finder
#     gamemode  # A daemon/lib combo that allows games to request a set of optimisations be temporarily applied to the host OS
#     gawk  # GNU version of awk
#     gcc  # The GNU Compiler Collection - C and C++ frontends
#     gettext  # GNU internationalization library
#     git  # the fast distributed version control system
#     glances  # CLI curses-based monitoring tool
#     gparted  # A Partition Magic clone, frontend to GNU Parted
#     grep  # A string search utility
#     groff  # GNU troff text-formatting system
#     grub2  # GNU GRand Unified Bootloader (2)
#     gzip  # GNU compression utility
#     haskellPackages.aeson  # A JSON parsing and encoding library optimized for ease of use and high performance
#     haskellPackages.conduit  # Streaming data processing library.
#     haskellPackages.terminal-progress-bar  # A progress bar in the terminal
#     haskellPackages.utf8-string  # Support for reading and writing UTF8 Strings
#     helvum  # GTK patchbay for PipeWire
#     highlight  # Fast and flexible source code highlighter (CLI version)
#     htop  # Interactive process viewer
#     httpie  # human-friendly CLI HTTP client for the API era
#     i3  # Improved dynamic tiling window manager
#     i3lock  # Improved screenlocker based upon XCB and PAM
#     i7z  # A better i7 (and now i3, i5) reporting tool for Linux
#     imwheel  # Mouse wheel configuration tool for XFree86/Xorg
#     inetutils  # A collection of common network programs
#     intel-ucode  # Microcode update files for Intel CPUs
#     # interception-caps2esc  # Interception plugin that transforms the most useless key ever in the most useful one (May need custom derivation)
#     # interception-tools  # A minimal composable infrastructure on top of libudev and libevdev (May need custom derivation)
#     inxi  # Full featured CLI system information tool
#     iotop  # View I/O usage of processes
#     iwd  # Internet Wireless Daemon
#     jp2a  # A small utility for converting JPG images to ASCII
#     jq  # Command-line JSON processor
#     kitty  # A modern, hackable, featureful, OpenGL-based terminal emulator
#     krita  # Edit and paint images
#     # lib32-gamemode  # A daemon/lib combo that allows games to request a set of optimisations be temporarily applied to the host OS (32-bit)
#     # lib32-pipewire  # Low-latency audio/video router and processor - 32-bit (May need custom derivation)
#     libldac  # LDAC Bluetooth encoder library
#     libratbag  # A DBus daemon to configure gaming mice
#     libtool  # A generic library support script
#     linuxPackages.kernel  # The Linux kernel and modules
#     linux-firmware  # Firmware files for Linux
#     linuxPackages.kernelHeaders  # Headers and scripts for building modules for the Linux kernel
#     # lostfiles  # Find orphaned files not owned by any Arch packages (May need custom derivation)
#     lshw  # A small tool to provide detailed information on the hardware configuration of the machine.
#     m4  # The GNU macro processor
#     gnumake  # GNU make utility to maintain groups of programs
#     man-db  # A utility for reading man pages
#     # mangohud  # A Vulkan overlay layer for monitoring FPS, temperatures, CPU/GPU load and more. (May need custom derivation)
#     mediainfo  # Supplies technical and tag information about media files (CLI interface)
#     meld  # Compare files, directories and working copies
#     glxinfo  # Mesa utilities (including glxinfo)
#     mkvtoolnix-gui  # Set of tools to create, edit and inspect Matroska files
#     mlocate  # Merging locate/updatedb implementation
#     # monero  # Monero: the secure, private, untraceable peer-to-peer currency (May need custom derivation)
#     mplayer  # Media player for Linux
#     mpv  # a free, open source, and cross-platform media player
#     mupdf  # Lightweight PDF and XPS viewer
#     ncdu  # Disk usage analyzer with an ncurses interface
#     neofetch  # A CLI system information tool written in BASH that supports displaying images.
#     neovim  # Fork of Vim aiming to improve user experience, plugins, and GUIs
#     nitrogen  # Background browser and setter for X windows
#     noto-fonts  # Google Noto TTF fonts
#     noto-fonts-cjk  # Google Noto CJK fonts
#     noto-fonts-emoji  # Google Noto emoji fonts
#     noto-fonts-extra  # Google Noto TTF fonts - additional variants
#     ntfs3g  # NTFS filesystem driver and utilities
#     ntp  # Network Time Protocol reference implementation
#     # nvidia  # NVIDIA drivers for linux (Use nixos.nvidia.package instead)
#     # nvidia-settings  # Tool for configuring the NVIDIA graphics driver (Use nixos.nvidia.package instead)
#     nvtop  # GPUs process monitoring for AMD, Intel and NVIDIA
#     obsidian  # A powerful knowledge base that works on top of a local folder of plain text Markdown files
#     ocl-icd  # OpenCL ICD Bindings
#     # opencl-nvidia  # OpenCL implemention for NVIDIA (Use nixos.nvidia.package instead)
#     openmpi  # High performance message passing library (MPI)
#     openssh  # SSH protocol implementation for remote login, command execution and file transfer
#     os-prober  # Utility to detect other OSes on a set of drives
#     latin-modern-math  # Improved version of Computer Modern fonts as used in LaTeX
#     pamixer  # Pulseaudio command-line mixer like amixer
#     patch  # A utility to apply patch files to original sources
#     pavucontrol  # PulseAudio Volume Control
#     pdfjs  # PDF reader in javascript
#     picom  # A lightweight compositor for X11
#     piper  # GTK application to configure gaming mice
#     pipewire  # Low-latency audio/video router and processor
#     pkgconf  # Package compiler and linker metadata toolkit
#     playerctl  # mpris media player controller and lib for spotify, vlc, audacious, bmp, xmms2, and others.
#     polybar  # A fast and easy-to-use status bar
#     poppler  # PDF rendering library based on xpdf 3.0
#     powerline-fonts  # patched fonts for powerline
#     pv  # A terminal-based tool for monitoring the progress of data through a pipeline
#     python3Packages.fastapi  # FastAPI framework, high performance, easy to learn, fast to code, ready for production
#     python3Packages.flit  # Simplified packaging of Python modules
#     python3Packages.flit-scm  # A PEP 518 backend using setuptools_scm to generate a version file, then flit to build
#     python3Packages.ipykernel  # The ipython kernel for Jupyter
#     python3Packages.lxml  # HTML cleaner from lxml project
#     python3Packages.mistletoe  # A fast, extensible Markdown parser in pure Python
#     python3Packages.numpy  # Scientific tools for Python
#     python3Packages.openai  # Python client library for the OpenAI API
#     python3Packages.pipx  # Install and Run Python Applications in Isolated Environments
#     python3Packages.pymupdf  # Python bindings for MuPDF's rendering library
#     python3Packages.pynvim  # Python client for Neovim
#     # python3Packages.pytube  # A lightweight, dependency-free Python library (and command-line utility) for downloading YouTube Videos (May need custom derivation)
#     python3Packages.pywal  # Generate and change colorschemes on the fly
#     # python3Packages.readability-lxml  # Fast html to text parser (article readability tool) python library (May need custom derivation)
#     python3Packages.tabulate  # Pretty-print tabular data in Python, a library and a command-line utility.
#     python3Packages.urwid  # Curses-based user interface library
#     qpwgraph  # PipeWire Graph Qt GUI Interface
#     qutebrowser  # A keyboard-driven, vim-like browser based on Python and Qt
#     ranger  # Simple, vim-like file manager
#     read-edid  # Program that can get information from a PNP monitor
#     redshift  # Adjusts the color temperature of your screen according to your surroundings.
#     ripgrep  # A search tool that combines the usability of ag with the raw speed of grep
#     # ripgrep-all  # rga: ripgrep, but also search in PDFs, E-Books, Office documents, zip, tar.gz, etc. (May need custom derivation)
#     rofi  # A window switcher, application launcher and dmenu replacement
#     rsync  # A fast and versatile file copying tool for remote and local files
#     rxvt-unicode  # Unicode enabled rxvt-clone terminal emulator (urxvt)
#     scrot  # Simple command-line screenshot utility for X
#     gnused  # GNU stream editor
#     skim  # Fuzzy Finder in Rust!
#     speedtest-cli  # Command line interface for testing internet bandwidth using speedtest.net
#     sqlitebrowser  # SQLite Database browser is a light GUI editor for SQLite databases, built on top of Qt
#     steam  # Valve's digital software delivery system
#     strace  # A diagnostic, debugging and instructional userspace tracer
#     sudo  # Give certain users the ability to run some commands as root
#     sxiv  # Simple X Image Viewer
#     taskwarrior  # Taskwarrior, a command-line todo list manager
#     texinfo  # GNU documentation system for on-line information and printed output
#     silver-searcher  # Code searching tool similar to Ack, but faster
#     timewarrior  # Timewarrior, A command line time tracking application
#     tldr  # Command line client for tldr, a collection of simplified man pages.
#     tor-browser-bundle-bin  # Securely and easily download, verify, install, and launch Tor Browser in Linux
#     transmission-gtk  # Fast, easy, and free BitTorrent client (GTK+ GUI)
#     tree  # A directory listing program displaying a depth indented list of files
#     anonymousPro  # Patched font Anonymous Pro (Anonymice) from nerd fonts library
#     arimo-nerdfont  # Patched font Arimo from nerd fonts library
#     carlito  # Google's Carlito font
#     corefonts  # Chrome OS core fonts
#     dejavu_fonts  # Font family based on the Bitstream Vera Fonts with a wider range of characters
#     dejavu-nerdfont  # Patched font Dejavu Sans Mono from nerd fonts library
#     envypn-font  # Patched font Envy Code R from nerd fonts library
#     fira-code  # Monospaced font with programming ligatures
#     fira-code-nerdfont  # Patched font Fira (Fura) Code from nerd fonts library
#     hack-font  # Patched font Hack from nerd fonts library
#     inconsolata-nerdfont  # Patched font Inconsolata Go from nerd fonts library
#     inconsolata-lgc-nerdfont  # Patched font Inconsolata LGC from nerd fonts library
#     inconsolata-nerdfont  # Patched font Inconsolata from nerd fonts library
#     nerdfonts  # High number of extra glyphs from popular 'iconic fonts'
#     noto-fonts-nerdfont  # Patched font Noto from nerd fonts library
#     roboto  # Google's signature family of fonts
#     source-code-pro-nerdfont  # Patched font Source Code Pro from nerd fonts library
#     terminus-nerdfont  # Patched font Terminus (Terminess) from nerd fonts library
#     ueberzug  # Command line util which allows to display images in combination with X11
#     unclutter-xfixes  # A small program for hiding the mouse cursor
#     unrar  # The RAR uncompression program
#     unzip  # For extracting and viewing files in .zip archives
#     viu  # Simple terminal image viewer
#     w3m  # Text-based Web browser as well as pager
#     weechat  # Fast, light and extensible IRC client (curses UI)
#     wget  # Network utility to retrieve files from the Web
#     which  # A utility to show the full path of commands
#     wine  # A compatibility layer for running Windows programs
#     winetricks  # Script to install various redistributable runtime libraries in Wine.
#     wireplumber  # Session / policy manager implementation for PipeWire
#     xclip  # Command line interface to the X11 clipboard
#     xdotool  # Command-line X11 automation tool
#     xorg.xdpyinfo  # Display information utility for X
#     xorg.xinit  # X.Org initialisation program
#     xorg.xinput  # Small commandline tool to configure devices
#     xorg.xrandr  # Primitive command line interface to RandR extension
#     xorg.xwininfo  # Command-line utility to print information about windows on an X server
#     yarn  # Fast, reliable, and secure dependency management
#     yt-dlp  # A youtube-dl fork with additional features and fixes
#     zathura  # Minimalistic document viewer
#     zathura-djvu  # DjVu support for Zathura
#     zathura-pdf-mupdf  # PDF support for Zathura (MuPDF backend) (Supports PDF, ePub, and OpenXPS)
#     zsh  # A very advanced and programmable command interpreter (shell) for UNIX
#
#     # Foreign packages (AUR equivalents)
#     # Note: Many of these may require custom derivations or alternatives in NixOS
#
#     # aconfmgr-git  # A configuration manager for Arch Linux
#     # activitywatch-bin  # Track how you spend time on your computer. Simple, extensible, no third parties.
#     # adwaita-qt5-git  # A style to bend Qt5 applications to look like they belong into GNOME Shell, git version
#     # adwaita-qt6-git  # A style to bend Qt6 applications to look like they belong into GNOME Shell, git version
#     androidenv.androidPkgs_9_0.platform-tools  # Platform-Tools for Google Android SDK (adb and fastboot)
#     bcftools  # A program for variant calling and manipulating files in the Variant Call Format (VCF) and its binary counterpart BCF
#     # clipboard  # Cut, copy, and paste anything in your terminal.
#     daemonize  # Run a program as a Unix daemon
#     # digimend-kernel-drivers-dkms  # Linux kernel modules (DKMS) for non-Wacom USB graphics tablets
#     dtach  # emulates the detach feature of screen
#     # epub2pdf  # epub2pdf is a command-line tool that quickly generates PDF files from EPUB ebooks.
#     # epy-ereader-git  # CLI Ebook Reader
#     # escrotum-git  # Screen capture using pygtk, inspired by scrot
#     # extundelete  # extundelete is a utility that can recover deleted files from an ext3 or ext4 partition.
#     # fanficfare  # A tool for downloading fanfiction to eBook formats
#     # googler  # Google from the command-line
#     # gpu-screen-recorder-gtk-git  # Gtk frontend to gpu-screen-recorder, a shadowplay-like screen recorder for Linux.
#     # gputest  # cross-platform GPU stress test and OpenGL benchmark. Contains FurMark, TessMark
#     hledger  # Command-line interface for the hledger accounting system
#     # imgbrd-grabber  # Very customizable imageboard/booru downloader with powerful filenaming features.
#     # imgur-screenshot  # Take screenshot selection, upload to imgur + more cool things
#     # ix  # A command line pastebin - shell
#     # jmtpfs  # FUSE and libmtp based filesystem for accessing MTP (Media Transfer Protocol) devices
#     # kindleunpack  # Extract text, images, and metadata from Kindle/Mobi files
#     # llm  # Run inference for Large Language Models on CPU, with Rust
#     # lnch  # A simple go binary that runs and disowns a command
#     # miniconda3  # Mini version of Anaconda Python distribution
#     mosh  # Mobile shell, surviving disconnects with local echo and line editing
#     # mullvad-vpn-cli  # The Mullvad VPN CLI client
#     ncpamixer  # ncurses PulseAudio Mixer
#     nodePackages.vue-language-server  # Vue language server (LSP)
#     # nohang  # A sophisticated low memory handler.
#     # nvim-packer-git  # A use-package inspired plugin manager for Neovim.
#     # otf-source-han-code-jp  # Japanese OpenType font for developers. Made by mixing SourceHanSans and SourceCodePro
#     # postlight-parser  # Extract meaningful content from the chaos of a web page (@postlight version)
#     python3Packages.beautifulsoup4  # Dummy package for BS4 name, because CME requires it.
#     python3Packages.ebooklib  # Python E-book library for handling books in EPUB2/EPUB3 format
#     # python3Packages.logzero  # Robust and effective logging for Python
#     # python3Packages.promnesia  # Enhancement of your browsing history
#     # raindrop  # All-in-one bookmark manager
#     # single-file-cli  # CLI tool for saving a faithful copy of a complete web page in a single HTML file
#     spotify  # A proprietary music streaming service
#     # svp-bin  # SmoothVideo Project 4 (SVP4)
#     # thorium-browser-bin  # Chromium fork focused on high performance and security
#     # todotxt  # Simple and extensible shell script for managing your todo.txt file
#     # trackma  # A lightweight and simple program for updating and using lists on several media tracking websites.
#     meslo-lgs-nf  # Meslo Nerd Font patched for Powerlevel10k
#     # unified-remote-server  # Unified Remote Server
#     # unigine-heaven  # Unigine Benchmark
#     # vapoursynth-git  # A video processing framework with simplicity in mind. (GIT version)
#     vscode  # Visual Studio Code (vscode): Editor for building and debugging modern web and cloud applications
#     # wallust  # generate colors from an image
#     # weechat-notify-send  # A WeeChat script that sends highlight and message notifications through notify-send
#     # xpadneo-dkms-git  # Advanced Linux Driver for Xbox One Wireless Gamepad
#     # yay  # Yet another yogurt. Pacman wrapper and AUR helper written in go.
#     zotero  # A free, easy-to-use tool to help you collect, organize, cite, and share your research sources.
#     # zsh-theme-powerlevel10k-git  # Powerlevel10k is a theme for Zsh. It emphasizes speed, flexibility and out-of-the-box experience.
#
#
#
#
#     # mine - redux
#     arbtt  # Automatic Rule-Based Time Tracker
#     at  # AT and batch delayed command scheduling utility and daemon
#     audacity  # A program that lets you manipulate digital audio waveforms
#     bat  # Cat clone with syntax highlighting and git integration
#     bc  # An arbitrary precision calculator language
#     broot  # Fuzzy Search + tree + cd
#     calc  # Arbitrary precision console calculator
#     clinfo  # Simple OpenCL application that enumerates all available platform and device properties
#     csvkit  # A suite of utilities for converting to and working with CSV
#     ddcutil  # Query and change Linux monitor settings using DDC/CI and USB.
#     dhcpcd  # DHCP/ IPv4LL/ IPv6RA/ DHCPv6 client
#     discord  # All-in-one voice and text chat for gamers
#     dmidecode  # Desktop Management Interface table related utilities
#     dunst  # Customizable and lightweight notification-daemon
#     earlyoom  # Early OOM Daemon for Linux
#     espeak-ng  # Multi-lingual software speech synthesizer
#     evtest  # Input device event monitor and query tool
#     eza  # A modern replacement for ls (community fork of exa)
#     fd  # Simple, fast and user-friendly alternative to find
#     feh  # Fast and light imlib2-based image viewer
#     ffmpegthumbnailer  # Lightweight video thumbnailer that can be used by file managers
#     fzf  # Command-line fuzzy finder
#     gamemode  # A daemon/lib combo that allows games to request a set of optimisations be temporarily applied to the host OS
#     git  # the fast distributed version control system
#     glances  # CLI curses-based monitoring tool
#     gparted  # A Partition Magic clone, frontend to GNU Parted
#     helvum  # GTK patchbay for PipeWire
#     highlight  # Fast and flexible source code highlighter (CLI version)
#     htop  # Interactive process viewer
#     httpie  # human-friendly CLI HTTP client for the API era
#     i3  # Improved dynamic tiling window manager
#     i3lock  # Improved screenlocker based upon XCB and PAM
#     i7z  # A better i7 (and now i3, i5) reporting tool for Linux
#     imwheel  # Mouse wheel configuration tool for XFree86/Xorg
#     inxi  # Full featured CLI system information tool
#     iotop  # View I/O usage of processes
#     iwd  # Internet Wireless Daemon
#     jp2a  # A small utility for converting JPG images to ASCII
#     jq  # Command-line JSON processor
#     kitty  # A modern, hackable, featureful, OpenGL-based terminal emulator
#     krita  # Edit and paint images
#     lshw  # A small tool to provide detailed information on the hardware configuration of the machine.
#     mediainfo  # Supplies technical and tag information about media files (CLI interface)
#     meld  # Compare files, directories and working copies
#     glxinfo  # Mesa utilities (including glxinfo)
#     mkvtoolnix-gui  # Set of tools to create, edit and inspect Matroska files
#     mlocate  # Merging locate/updatedb implementation
#     mplayer  # Media player for Linux
#     mpv  # a free, open source, and cross-platform media player
#     mupdf  # Lightweight PDF and XPS viewer
#     ncdu  # Disk usage analyzer with an ncurses interface
#     neofetch  # A CLI system information tool written in BASH that supports displaying images.
#     neovim  # Fork of Vim aiming to improve user experience, plugins, and GUIs
#     nitrogen  # Background browser and setter for X windows
#     ntp  # Network Time Protocol reference implementation
#     nvtop  # GPUs process monitoring for AMD, Intel and NVIDIA
#     obsidian  # A powerful knowledge base that works on top of a local folder of plain text Markdown files
#     pamixer  # Pulseaudio command-line mixer like amixer
#     pavucontrol  # PulseAudio Volume Control
#     picom  # A lightweight compositor for X11
#     piper  # GTK application to configure gaming mice
#     playerctl  # mpris media player controller and lib for spotify, vlc, audacious, bmp, xmms2, and others.
#     polybar  # A fast and easy-to-use status bar
#     pv  # A terminal-based tool for monitoring the progress of data through a pipeline
#     qpwgraph  # PipeWire Graph Qt GUI Interface
#     qutebrowser  # A keyboard-driven, vim-like browser based on Python and Qt
#     ranger  # Simple, vim-like file manager
#     redshift  # Adjusts the color temperature of your screen according to your surroundings.
#     ripgrep  # A search tool that combines the usability of ag with the raw speed of grep
#     rofi  # A window switcher, application launcher and dmenu replacement
#     rsync  # A fast and versatile file copying tool for remote and local files
#     rxvt-unicode  # Unicode enabled rxvt-clone terminal emulator (urxvt)
#     scrot  # Simple command-line screenshot utility for X
#     skim  # Fuzzy Finder in Rust!
#     speedtest-cli  # Command line interface for testing internet bandwidth using speedtest.net
#     sqlitebrowser  # SQLite Database browser is a light GUI editor for SQLite databases, built on top of Qt
#     steam  # Valve's digital software delivery system
#     sxiv  # Simple X Image Viewer
#     taskwarrior  # Taskwarrior, a command-line todo list manager
#     timewarrior  # Timewarrior, A command line time tracking application
#     tldr  # Command line client for tldr, a collection of simplified man pages.
#     tor-browser-bundle-bin  # Securely and easily download, verify, install, and launch Tor Browser in Linux
#     transmission-gtk  # Fast, easy, and free BitTorrent client (GTK+ GUI)
#     tree  # A directory listing program displaying a depth indented list of files
#     ueberzug  # Command line util which allows to display images in combination with X11
#     unclutter-xfixes  # A small program for hiding the mouse cursor
#     unrar  # The RAR uncompression program
#     unzip  # For extracting and viewing files in .zip archives
#     viu  # Simple terminal image viewer
#     w3m  # Text-based Web browser as well as pager
#     weechat  # Fast, light and extensible IRC client (curses UI)
#     wget  # Network utility to retrieve files from the Web
#     wine  # A compatibility layer for running Windows programs
#     winetricks  # Script to install various various redistributable runtime libraries in Wine.
#     xclip  # Command line interface to the X11 clipboard
#     xdotool  # Command-line X11 automation tool
#     yt-dlp  # A youtube-dl fork with additional features and fixes
#     zathura  # Minimalistic document viewer
#     zathura-djvu  # DjVu support for Zathura
#     zathura-pdf-mupdf  # PDF support for Zathura (MuPDF backend) (Supports PDF, ePub, and OpenXPS)
#     zsh  # A very advanced and programmable command interpreter (shell) for UNIX
#
#     # Selected foreign packages that have NixOS equivalents or are commonly used
#     androidenv.androidPkgs_9_0.platform-tools  # Platform-Tools for Google Android SDK (adb and fastboot)
#     bcftools  # A program for variant calling and manipulating files in the Variant Call Format (VCF) and its binary counterpart BCF
#     daemonize  # Run a program as a Unix daemon
#     dtach  # emulates the detach feature of screen
#     hledger  # Command-line interface for the hledger accounting system
#     mosh  # Mobile shell, surviving disconnects with local echo and line editing
#     ncpamixer  # ncurses PulseAudio Mixer
#     spotify  # A proprietary music streaming service
#     vscode  # Visual Studio Code (vscode): Editor for building and debugging modern web and cloud applications
#     zotero  # A free, easy-to-use tool to help you collect, organize, cite, and share your research sources
#   ]);
# }

