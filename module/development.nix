# Development Domain Module
# Complete dev workflow (tools + environment)
# Consolidates: programming languages, dev tools, editors, git, overlays, nix-ld

{
  config,
  lib,
  pkgs,
  username,
  inputs,
  ...
}:
with lib;
{
  config = mkMerge [
    # System-level development configuration
    {
      # Domain identification
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

        # Build systems
        cmake
        meson
        ninja

        # Documentation
        man-pages
        man-pages-posix
      ];

      # Development-related overlays
      nixpkgs.overlays = [
        (final: prev: {
          # Override spacy to use a working version
          python3Packages = prev.python3Packages // {
            spacy = prev.python3Packages.spacy.overrideAttrs (old: rec {
              version = "3.8.4"; # last revision that still builds
              src = prev.fetchPypi {
                pname = "spacy";
                inherit version;
                sha256 = "sha256-G92R3l0MP2tqdnSX6uQyH3fF9qqoj4Tns5w8QAM3YCM=";
              };
              meta = old.meta // {
                broken = false;
              };
            });
          };

          # Disable the package causing the issue until a fix is available
          aider-chat-full = prev.aider-chat-full.override {
            pythonPackages = final.python3Packages;
          };

          claude-desktop-wayland = final.symlinkJoin {
            name = "claude-desktop-wayland";
            paths = [
              inputs.claude-desktop.packages.${pkgs.system}.claude-desktop-with-fhs
            ];
            buildInputs = [ final.makeWrapper ];
            postBuild = ''
              wrapProgram $out/bin/claude-desktop --add-flags "--enable-features=WaylandWindowDecorations --no-sandbox"
            '';
          };
        })
      ];

      # nix-ld configuration for running unpatched binaries
      programs.nix-ld = {
        enable = true;
        libraries = with pkgs; [
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
          # graphical
          freetype
          libglvnd
          libnotify
          SDL2
          vulkan-loader
          gdk-pixbuf
          # audio
          pipewire
          pulseaudio
          # other
        ];
      };
    }

    # User-level development configuration
    {
      home-manager.users.${username} = {
        imports = [
          inputs.claude-code-logger.homeManagerModules.default
        ];

        # Consolidate all home configuration
        home = {
          # Development environment variables
          sessionVariables = {
            DEVELOPMENT_DOMAIN = "v0.3";
            EDITOR = "nvim";
            VISUAL = "nvim";
            PAGER = lib.mkForce "less -R";
            MANPAGER = "nvim +Man!";
          };

          # Consolidated development packages
          packages = with pkgs; [
            # Language Servers, Formatters, Linters
            markdown-oxide # Used by obsidian.nvim
            nixfmt-rfc-style # Preferred Nix formatter
            nixd
            nil
            nix-diff

            # Rust development
            rustup
            cargo-fuzz
            cargo-bump
            cargo-audit

            # JavaScript/Node.js
            nodejs
            nodejs_latest

            # Python
            python3
            python3Packages.pip
            python312Packages.ipython

            # Database tools
            sqlite
            sqlitebrowser
            sqlite-vec
            sqlite-utils
            sqlitestudio

            # AI development tools
            aider-chat # aider-chat-full # Temporarily disabled due to spacy dependency issues
            claude-code
            inputs.claude-squad.packages.${pkgs.system}.default # Manage multiple AI coding assistants
            claude-desktop-wayland
            codex
            openai-whisper-cpp

            # Development utilities
            jq
            yq
            csvtool
            csvkit
            csvq
            httpie
            curlie
            websocat

            # Git tools
            gh # GitHub CLI
            delta
            lazygit # TUI for git
            onefetch # Git repo stats
            gitui

            # Editor
            neovim
          ];

          # Neovim configuration link
          activation.linkNeovimConfig =
            config.home-manager.users.${username}.lib.dag.entryAfter [ "writeBoundary" ]
              ''
                mkdir -p $HOME/.config
                echo "Creating symlink for Neovim configuration..."
                ln -sfn /realm/nixos-config/nvim $HOME/.config/nvim
              '';
        }; # End of home block

        # Configure the claude-code-logger
        programs.claude-code-logger = {
          enable = true;
          logDir = "/realm/observability/claude-code-api-log";
          enableSessionFolders = true;
          enableConversationGrouping = true;
          maxInteractionsPerFile = 100;
          maxLogSizeMB = 10;
          createAlias = true;
        };

        # Git configuration
        programs.git = {
          enable = true;
          delta.enable = true; # Installs delta and sets it as pager

          userName = "Sinity";
          userEmail = "ezo.dev@gmail.com";

          aliases = {
            a = "add";
            aa = "add --all";
            s = "status";
            b = "branch";
            m = "merge";
            d = "diff";
            pl = "pull";
            plo = "pull origin";
            ps = "push";
            pso = "push origin";
            pst = "push --follow-tags";
            cl = "clone";
            c = "commit";
            cm = "commit -m";
            tag = "tag -ma";
            ch = "checkout";
            chb = "checkout -b";
            log = "log --oneline --decorate --graph";
            lol = "log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%ar) %C(bold blue)<%an>%Creset'";
            lola = "log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%ar) %C(bold blue)<%an>%Creset' --all";
            lols = "log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%ar) %C(bold blue)<%an>%Creset' --stat";
          };

          extraConfig = {
            init.defaultBranch = "master";
            merge.conflictstyle = "diff3";
            diff.colorMoved = "default";

            # Delta specific settings
            delta = {
              line-numbers = true;
              side-by-side = true;
              navigate = true;
            };

            # Handle the shell command alias
            alias.cma = "!git add --all && git commit -m";
          };
        };
      };
    }
  ];
}
