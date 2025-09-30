# Development Domain Module - Entry Point
# Complete dev workflow (tools + environment)
# Consolidates: programming languages, dev tools, editors, git, nix-ld

{
  config,
  lib,
  pkgs,
  inputs,
  flakeRoot,
  ...
}:
{
  imports = [
    ./shell.nix
    ./languages.nix
    ./git.nix
    ./starship.nix
  ];

  config = {
    system.nixos.tags = [ "development-domain-v0.3" ];

    # Core development packages available system-wide
    environment.systemPackages = with pkgs; [
      # Essential development tools
      git
      git-annex
      gnumake
      gcc
      gdb

      # Git analysis and visualization
      scc # Accurate source code counter
      gource # Software version control visualization

      # Rust-specific analysis tools
      cargo-audit # Audit Cargo.lock for security vulnerabilities
      cargo-outdated # Display when dependencies are out of date
      cargo-deny # Cargo plugin to help you manage large dependency graphs
      cargo-bloat # Find out what takes most space in executables
      cargo-expand # Expand macros in your source code
      cargo-flamegraph # Generate flamegraphs for Rust
      cargo-llvm-lines # Count lines of LLVM IR per function
      cargo-udeps # Find unused dependencies
      cargo-depgraph # Generate dependency graphs
      # cargo-geiger # Detect unsafe code usage (temporarily disabled due to build failure)
      cargo-machete # Remove unused dependencies

      # General code analysis
      tokei # Count code, fast (better than scc for some cases)
      onefetch # Git repo summary in terminal
      git-cliff # Changelog generator
      cocogitto # Conventional commit tooling
      hyperfine # Command-line benchmarking tool

      # Advanced visualization and analysis
      gitui # Terminal UI for git
      lazygit # Another terminal UI for git with graphs
      # git-stats # Local git statistics generator (not in nixpkgs)
      gitstats # Generate git history statistics (generates HTML reports)

      # Diagram generation
      graphviz # Graph visualization software
      plantuml # UML diagram generator
      d2 # Modern diagram scripting language
      mermaid-cli # Generate diagrams from Mermaid definitions
      pikchr # Diagram markup language
      structurizr-cli # C4 architecture diagrams

      # Time-series and plotting tools
      gnuplot # Plotting tool
      ploticus # Script-driven plotting

      # Code structure visualization
      # codevis # Code visualization tool (not in nixpkgs)
      # codecharta # 3D visualization of code metrics (not in nixpkgs)

      # Database for metrics storage
      sqlite # For storing historical metrics
      duckdb # Analytics database

      # Data analysis
      jq # JSON processor
      miller # CSV/JSON/etc data processing
      xan # CSV command line toolkit (xsv replacement)
      visidata # Interactive data exploration

      # Nix development
      nix-diff
      nix-tree
      nix-prefetch-git
      nix-health
      nix-zsh-completions
      nix-fast-build
      nix-doc
      nix-index

      # Build systems
      cmake
      meson
      ninja
      uv

      # Documentation
      man-pages
      man-pages-posix

      # Claude tooling
      claude-code-usage-monitor

      # Development session management
      dtach
      mprocs

      # System monitoring and performance tools
      btop
      ncdu # disk space analyzer
      nitch # system fetch util
      dua # Disk usage analyzer (like ncdu but faster)
      yazi # Terminal file manager
      fselect # SQL-like file search
      zk # Plain text Zettelkasten CLI

      # CLI utilities
      toipe # typing test in the terminal
      ttyper # cli typing test

      # Terminal toys
      cbonsai
      pipes
      tty-clock

      # Graphics diagnostic tools
      mesa-demos
      vulkan-tools
      vulkan-validation-layers
      wayland-utils
      libva-utils
      glxinfo
      drm_info

      # System diagnostics and benchmarking
      inxi
      hwinfo
      dmidecode
      lm_sensors
      nvme-cli
      smartmontools
      powertop
      stressapptest
      sysbench
      phoronix-test-suite
      glmark2
      vkmark
      fio
      perf
      sysstat
      linuxPackages.cpupower
    ];

    # nix-ld configuration for running unpatched binaries
    programs.nix-ld = {
      enable = true;
      libraries = with pkgs; [
        # Original libraries
        stdenv.cc.cc
        openssl
        curl
        glib
        util-linux
        glibc
        icu
        libunwind
        libuuid
        zlib
        libsecret
        freetype
        libglvnd
        libnotify
        SDL2
        vulkan-loader
        gdk-pixbuf
        pipewire
        pulseaudio

        alsa-lib
        at-spi2-atk
        at-spi2-core
        atk
        cairo
        cups
        dbus
        expat
        fontconfig
        fuse3
        gtk3
        libGL
        libappindicator-gtk3
        libdrm
        libpulseaudio
        libuuid
        nspr
        nss
        pango
        systemd
        xorg.libX11
        xorg.libXScrnSaver
        xorg.libXcomposite
        xorg.libXcursor
        xorg.libXdamage
        xorg.libXext
        xorg.libXfixes
        xorg.libXi
        xorg.libXrandr
        xorg.libXrender
        xorg.libXtst
        xorg.libxcb
        xorg.libxkbfile
        xorg.libxshmfence
      ];
    };

    home-manager.users.sinity = {
      # Consolidate all home configuration
      home = {
        # Development environment variables
        sessionVariables = {
          DEVELOPMENT_DOMAIN = "v0.3";

          # Development settings from environment.nix
          EDITOR = "nvim";
          VISUAL = "nvim";
          PAGER = lib.mkForce "less -R";
          MANPAGER = "nvim +Man!";
          PYTHONDONTWRITEBYTECODE = "1";
          SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS = "0";
          MICRO_TRUECOLOR = "1";
          LD_LIBRARY_PATH = lib.makeLibraryPath [
            pkgs.libGL
            pkgs.libglvnd
          ];
        };

        # Neovim configuration link
        activation.linkNeovimConfig =
          config.home-manager.users.sinity.lib.dag.entryAfter [ "writeBoundary" ]
            ''
              mkdir -p $HOME/.config
              echo "Creating symlink for Neovim configuration..."
              ln -sfn ''${FLAKE:-${flakeRoot}}/dots/nvim $HOME/.config/nvim
            '';
        activation.ensureClaudeDir =
          config.home-manager.users.sinity.lib.dag.entryAfter [ "linkNeovimConfig" ]
            ''
              if [ -L "$HOME/.claude" ] && [ "$(readlink "$HOME/.claude")" = ".config/claude" ]; then
                rm "$HOME/.claude"
              fi
              mkdir -p "$HOME/.claude"
            '';
      };

      programs = {
        # btop - system monitor configuration
        btop = {
          enable = true;
          settings = {
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
      };

    };
  };
}
