# Development Domain Module - Entry Point
# Complete dev workflow (tools + environment)
# Consolidates: programming languages, dev tools, editors, git, nix-ld

{
  config,
  lib,
  pkgs,
  inputs,
  ...
}:
{
  imports = [
    ./shell.nix
    ./languages.nix
    ./git.nix
  ];

  config = {
    system.nixos.tags = [ "development-domain-v0.3" ];

    # Core development packages available system-wide
    environment.systemPackages = with pkgs; [
      # Essential development tools
      git
      gnumake
      gcc
      gdb

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
      imports = [
        inputs.claude-code-logger.homeManagerModules.default
      ];

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
          LD_LIBRARY_PATH = "$(nix build --print-out-paths --no-link nixpkgs#libGL)/lib";
        };

        # Neovim configuration link
        activation.linkNeovimConfig =
          config.home-manager.users.sinity.lib.dag.entryAfter [ "writeBoundary" ]
            ''
              mkdir -p $HOME/.config
              echo "Creating symlink for Neovim configuration..."
              ln -sfn ''${FLAKE:-/realm/project/sinnix}/nvim $HOME/.config/nvim
            '';
      };

      programs = {
        claude-code-logger = {
          enable = false;
          logDir = "/realm/data/claude-code-api-log";
          enableSessionFolders = true;
          enableConversationGrouping = true;
          maxInteractionsPerFile = 100;
          maxLogSizeMB = 10;
          createAlias = true;
        };
      };
    };
  };
}
