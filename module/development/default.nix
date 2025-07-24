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

    # Add user scripts directory to PATH
    environment.sessionVariables = {
      PATH = "$PATH:$HOME/scripts";
    };

    # Core development packages available system-wide
    environment.systemPackages = with pkgs; [
      # Essential development tools
      git
      git-annex
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

      # Claude tooling
      claude-code-usage-monitor

      # Development session management
      dtach
      mprocs
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

      # Sinex development tools service
      systemd.user.services.sinex-devtools = {
        Unit = {
          Description = "Sinex Development Tools Dashboard";
          PartOf = [ "graphical-session.target" ];
          After = [ "graphical-session.target" ];
          # Only start if the project directory exists
          ConditionPathExists = "/realm/project/sinex";
        };

        Service = {
          Type = "oneshot";
          RemainAfterExit = true;
          WorkingDirectory = "/realm/project/sinex";
          Environment = [
            "DATABASE_NAME=sinex_dev"
            "DATABASE_URL=postgresql:///sinex_dev?host=/run/postgresql"
            "SINEX_TEST_OPTIMIZATIONS=true"
          ];
          ExecStartPre = "${pkgs.writeShellScript "sinex-devtools-pre" ''
            # Ensure database exists
            if command -v pg_isready >/dev/null 2>&1 && pg_isready -h /run/postgresql >/dev/null 2>&1; then
              if ! psql -h /run/postgresql -lqt | cut -d \| -f 1 | grep -qw "sinex_dev"; then
                createdb -h /run/postgresql "sinex_dev" || true
              fi
            fi
          ''}";
          ExecStart = "${pkgs.writeShellScript "sinex-devtools-start" ''
            cd /realm/project/sinex
            echo "🚀 Setting up Sinex development environment..."
            # Check if database exists and run migrations
            if [ -n "$DATABASE_URL" ]; then
              echo "🗄️  Running migrations..."
              nix develop --command just migrate || true
              echo "✅ Database $DATABASE_NAME ready at $DATABASE_URL"
            fi
            # Kill any existing tmux session first
            tmux kill-session -t sinex-mprocs 2>/dev/null || true
            # Enter nix develop shell and start tmux with mprocs
            cd /realm/project/sinex
            # Run tmux directly within nix develop environment
            # Create tmux session with custom config for 'q' to detach
            export TMUX_TMPDIR=/tmp
            cat > /tmp/sinex-tmux.conf << 'EOF'
# Custom tmux config for sinex-mprocs session
# Bind 'q' key to detach (without prefix)
bind-key -n q detach-client
# Keep other tmux defaults
set-option -g default-terminal "screen-256color"
EOF
            nix develop --command tmux -f /tmp/sinex-tmux.conf new-session -d -s sinex-mprocs "mprocs --config mprocs.yaml"
            echo "📦 Sinex devShell ready. Run sinex-attach to connect."
          ''}";
          ExecStop = "${pkgs.writeShellScript "sinex-devtools-stop" ''
            # Kill the tmux session
            if tmux has-session -t sinex-mprocs 2>/dev/null; then
              echo "Stopping Sinex development tools..."
              # Send quit command to mprocs
              tmux send-keys -t sinex-mprocs C-q
              sleep 1
              tmux kill-session -t sinex-mprocs 2>/dev/null || true
            fi
          ''}";
          Restart = "on-failure";
          RestartSec = "10s";
        };

        Install = {
          WantedBy = [ "default.target" ];
        };
      };

    };
  };
}
