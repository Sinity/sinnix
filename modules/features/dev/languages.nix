{
  mkFeatureModule,
  pkgs,
  lib,
  ...
}@args:
mkFeatureModule {
  path = [
    "dev"
    "languages"
  ];
  description = "Programming language toolchains";
  subFeatures = {
    nix = {
      description = "Nix language tooling (nixfmt, nixd, nix-diff)";
      default = true;
    };
    python = {
      description = "Python 3 with common packages";
      default = true;
    };
    nodejs = {
      description = "Node.js runtime";
      default = true;
    };
    database = {
      description = "Database clients (sqlite, pgcli)";
      default = true;
    };
    ai = {
      default = true;
    };
  };
  configFn =
    {
      config,
      pkgs,
      lib,
      cfg,
      user,
      helpers,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
    in
    lib.mkMerge [
      {
        # A nested subvolume keeps compiler outputs out of the Realm snapshot.
        # Never turn an existing directory into an unbacked cache implicitly.
        systemd.services.sinnix-cargo-cache = {
          description = "Provision the regenerable Cargo cache subvolume";
          wantedBy = [ "multi-user.target" ];
          unitConfig.RequiresMountsFor = [ config.sinnix.paths.realmRoot ];
          after = [ "systemd-tmpfiles-setup.service" ];
          path = [
            pkgs.btrfs-progs
            pkgs.coreutils
          ];
          environment = {
            CARGO_CACHE_ROOT = "${config.sinnix.paths.realmRoot}/state/cache/cargo";
            CARGO_CACHE_USER = user;
          };
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
          };
          script = ''
            set -euo pipefail
            if [ -L "$CARGO_CACHE_ROOT" ]; then
              echo "Cargo cache root is a symlink: $CARGO_CACHE_ROOT" >&2
              exit 1
            fi
            if [ -e "$CARGO_CACHE_ROOT" ]; then
              if ! btrfs subvolume show "$CARGO_CACHE_ROOT" >/dev/null 2>&1; then
                echo "Cargo cache root already exists as an ordinary path; preserve it for reconciliation: $CARGO_CACHE_ROOT" >&2
                exit 1
              fi
            else
              btrfs subvolume create "$CARGO_CACHE_ROOT"
            fi
            chown "$CARGO_CACHE_USER:users" "$CARGO_CACHE_ROOT"
            chmod 0700 "$CARGO_CACHE_ROOT"
          '';
        };
        home-manager.users.${user}.home.packages = [ scriptPkgs.sinnix-cargo-target ];
      }

      # Nix tooling
      (lib.mkIf cfg.nix.enable {
        # nixd (not nil): both editors' Nix LSP. Mason cannot provide a working
        # nixd on NixOS, and nixd's flake-aware option completion is the point
        # of an LSP on this machine; nil remains in the sinnix devshell only.
        home-manager.users.${user}.home.packages = with pkgs; [
          nixfmt
          nixd
          nix-diff
        ];
      })

      # Seeded 2026-09-28 from ~/.cache/uv (built wheels and the archive
      # entries they point at, including the source-built free-threaded
      # duckdb); a fresh worktree then provisions with no wheel build.
      (lib.mkIf cfg.python.enable {
        home-manager.users.${user}.home.sessionVariables = {
          UV_CACHE_DIR = "/realm/state/cache/uv";
          UV_LINK_MODE = "clone";
        };
      })

      # Python with common packages
      (lib.mkIf cfg.python.enable {
        # The uv cache lives on /realm beside the worktrees so venvs clone
        # (reflink) from it instead of copying ~450 MB across devices per
        # worktree. The directory exists before any variable points at it;
        # it is seeded from the warm cache before uv is switched over, since
        # an empty cache source-builds wheels with no published build (the
        # free-threaded duckdb) and that build nearly took the host down.
        systemd.tmpfiles.rules = [ "d /realm/state/cache/uv 0755 ${user} users -" ];
        home-manager.users.${user}.home.packages = [
          (pkgs.python3.withPackages (
            ps: with ps; [
              pip
              ipython
              rich
              click
              questionary
              typer
              tqdm
              tabulate
              httpx
              requests
              beautifulsoup4
              fastapi
              uvicorn
              pydantic
              pydantic-settings
              python-dotenv
              pyyaml
              tiktoken
              gitpython
              black
              mypy
              pytest
              marimo
              litellm
              llm
              openai
              anthropic
              google-genai
            ]
          ))
        ];
      })

      # Node.js
      (lib.mkIf cfg.nodejs.enable {
        home-manager.users.${user}.home.packages = with pkgs; [
          nodejs
        ];
      })

      # Database tools
      (lib.mkIf cfg.database.enable {
        home-manager.users.${user}.home.packages = with pkgs; [
          sqlite
          sqlite-vec
          turso
          pgcli
        ];
      })

      # AI coding tools
      (lib.mkIf cfg.ai.enable {
        home-manager.users.${user}.home.packages = [
          pkgs.gh
          pkgs.delta
          pkgs.jetbrains-mono
        ];
      })
    ];
} args
