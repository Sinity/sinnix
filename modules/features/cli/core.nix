{ pkgs, mkFeatureModule, ... }@args:
mkFeatureModule {
  path = [
    "cli"
    "core"
  ];
  description = "Core CLI environment";
  configFn =
    {
      config,
      pkgs,
      lib,
      user,
      ...
    }:
    {
      environment.systemPackages = with pkgs; [
        git
        taskwarrior3
        timewarrior
        repomix
        difftastic
        bubblewrap
        unzip
        wget
        # Modern CLI replacements
        eza
        bat
        fd
        lnav
        dua
        bandwhich
        # Even more modern tools
        micro
        bottom
        gping
        doggo
        dust
      ];

      programs = {
        zsh.enable = true;

        gnupg.agent = {
          enable = true;
          enableSSHSupport = true;
        };
      };

      systemd.coredump = {
        enable = true;
        settings.Coredump = {
          Storage = "none";
          ProcessSizeMax = "128M";
          ExternalSizeMax = "0";
          JournalSizeMax = "8M";
        };
      };
      services.atd.enable = true;

      # Disable GNOME keyring - using GPG agent for SSH key management instead
      services.gnome.gnome-keyring.enable = lib.mkForce false;

      # Prevent PAM from starting keyring on login (conflicts with gpg-agent SSH)
      security.pam.services.login.enableGnomeKeyring = lib.mkForce false;

      home-manager.users.${user} =
        {
          lib,
          pkgs,
          config,
          ...
        }:
        {
          home.packages = lib.mkAfter (
            with pkgs;
            [
              nix-output-monitor
              nvd
              cachix
              nix-direnv
              killall
              procps
              procs
              psmisc
              iotop
              entr
              file
              tldr
              xdg-utils
              xxd
              jq
              fzf
              bc
              at
              speedtest-cli
              stress-ng
              glances
              fio
            ]
            ++ lib.filter (p: p != null) [
              (pkgs.tasksh or null)
              (pkgs.taskwarrior-tui or null)
            ]
          );

          programs.direnv = {
            enable = true;
            nix-direnv.enable = true;
            silent = true;
            config.global.warn_timeout = "30s";
          };

          xdg.configFile."direnv/direnvrc".text = ''
            _sinnix_project_root() {
              if command -v git >/dev/null 2>&1; then
                local git_root
                git_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
                if [ -n "$git_root" ]; then
                  printf '%s\n' "$git_root"
                  return 0
                fi
              fi

              case "$PWD" in
                /realm/project/*)
                  local rest
                  rest="''${PWD#/realm/project/}"
                  printf '/realm/project/%s\n' "''${rest%%/*}"
                  ;;
                *) return 1 ;;
              esac
            }

            _sinnix_project_kind() {
              local project_root
              project_root="$(_sinnix_project_root)" || return 1

              case "$project_root" in
                /realm/project/sinnix) printf '%s\n' sinnix ;;
                /realm/project/sinity-lynchpin) printf '%s\n' lynchpin ;;
                /realm/project/sinex | /realm/project/sinex-*) printf '%s\n' sinex ;;
                /realm/project/polylogue | /realm/project/polylogue-*) printf '%s\n' polylogue ;;
                /realm/project/scribe-tap) printf '%s\n' rust-project ;;
                /realm/project/intercept-bounce) printf '%s\n' rust-project ;;
                /realm/project/knowledge-extract) printf '%s\n' python-project ;;
                /realm/project/pwrank) printf '%s\n' web-project ;;
                /realm/data/knowledgebase) printf '%s\n' data-project ;;
                /realm/project/*)
                  if [ -e "$project_root/flake.nix" ] \
                    || [ -e "$project_root/Cargo.toml" ] \
                    || [ -e "$project_root/pyproject.toml" ] \
                    || [ -e "$project_root/package.json" ] \
                    || [ -e "$project_root/justfile" ] \
                    || [ -e "$project_root/Justfile" ]; then
                    printf '%s\n' realm-project
                  else
                    return 1
                  fi
                  ;;
                *) return 1 ;;
              esac
            }

            _sinnix_path_without() {
              local remove="$1"
              local old_ifs="$IFS"
              local part
              local next=""
              IFS=:
              for part in $PATH; do
                [ "$part" = "$remove" ] && continue
                next="$next''${next:+:}$part"
              done
              IFS="$old_ifs"
              printf '%s' "$next"
            }

            _sinnix_write_scope_wrapper() {
              local wrapper="$1"
              cat > "$wrapper" <<'SINNIX_SCOPE_WRAPPER'
            #!/usr/bin/env bash
            set -euo pipefail

            cmd="''${0##*/}"
            case "$cmd" in
              nix | nixos-rebuild) class="nix-build" ;;
              polylogue | sqlite3 | duckdb) class="background" ;;
              *) class="build" ;;
            esac

            _sinnix_scope_path_without_dir() {
              local drop_dir="$1"
              local input_path="$2"
              local old_ifs="$IFS"
              local part
              local next=""
              IFS=:
              for part in $input_path; do
                if [ "$part" = "$drop_dir" ]; then
                  continue
                fi
                if [ -z "$next" ]; then
                  next="$part"
                else
                  next="$next:$part"
                fi
              done
              IFS="$old_ifs"
              printf '%s' "$next"
            }

            wrapper_dir="''${SINNIX_SCOPE_WRAPPER_DIR:-}"
            if [ -z "$wrapper_dir" ]; then
              wrapper_dir="$(cd -P -- "$(dirname -- "$0")" && pwd)"
            fi
            export PATH="$(_sinnix_scope_path_without_dir "$wrapper_dir" "''${SINNIX_SCOPE_ORIGINAL_PATH:-$PATH}")"

            if [ -n "''${SINNIX_SCOPE_WRAPPER_ACTIVE:-}" ]; then
              cmd_path="$(command -v -- "$cmd" 2>/dev/null || true)"
              if [ -z "$cmd_path" ]; then
                echo "sinnix-scope wrapper: unable to locate unwrapped $cmd" >&2
                exit 127
              fi
              exec "$cmd_path" "$@"
            fi

            export SINNIX_SCOPE_WRAPPER_ACTIVE=1

            scope_bin="''${SINNIX_SCOPE_BIN:-}"
            if [ -z "$scope_bin" ]; then
              scope_bin="$(command -v sinnix-scope 2>/dev/null || true)"
            fi
            if [ -z "$scope_bin" ] && [ -x /realm/project/sinnix/scripts/sinnix-scope ]; then
              scope_bin=/realm/project/sinnix/scripts/sinnix-scope
            fi

            if [ -n "$scope_bin" ] && [ -x "$scope_bin" ]; then
              exec "$scope_bin" "$class" -- "$cmd" "$@"
            fi

            exec "$cmd" "$@"
            SINNIX_SCOPE_WRAPPER
              chmod +x "$wrapper"
            }

            # Project dev environments install transparent wrappers for heavy
            # commands. Agents and humans run normal commands; the commands land
            # in the Sinnix build/background slices when a recognized project
            # devshell is active.
            #
            # Keep this broad for active /realm/project work, not only for
            # projects with bespoke cache policy. The observed failure mode was
            # an agent in an unrecognized repo launching plain `nix build`; the
            # root nix-daemon was weighted, but the user-side command inherited
            # the agent/background cgroup and attribution became split.
            _sinnix_project_scope_setup() {
              local project_kind
              project_kind="$(_sinnix_project_kind)" || return 0

              local project_root
              project_root="$(_sinnix_project_root)" || return 0

              local wrapper_dir
              wrapper_dir="$(direnv_layout_dir)/sinnix-scope/bin"
              mkdir -p "$wrapper_dir"
              _sinnix_write_scope_wrapper "$wrapper_dir/.sinnix-scope-wrapper"

              local commands=()
              case "$project_kind" in
                sinex)
                  commands=(
                    cargo cargo-nextest nextest
                    pytest py.test
                    nix nixos-rebuild
                    ninja cmake meson make just
                    git-annex xtask
                    sqlite3 duckdb
                  )
                  ;;
                polylogue)
                  commands=(
                    pytest py.test uv
                    nix nixos-rebuild
                    make just
                    sqlite3 duckdb
                    polylogue
                  )
                  ;;
                sinnix)
                  commands=(
                    nix nixos-rebuild
                    check just make
                    sqlite3 duckdb
                  )
                  ;;
                lynchpin)
                  commands=(
                    pytest py.test uv
                    nix nixos-rebuild
                    make just
                    sqlite3 duckdb
                  )
                  ;;
                rust-project)
                  commands=(
                    cargo cargo-nextest nextest
                    nix nixos-rebuild
                    make just ninja cmake meson
                    sqlite3 duckdb
                  )
                  ;;
                python-project)
                  commands=(
                    pytest py.test uv
                    nix nixos-rebuild
                    make just
                    sqlite3 duckdb
                  )
                  ;;
                web-project)
                  commands=(
                    npm pnpm yarn bun
                    nix nixos-rebuild
                    make just
                    sqlite3 duckdb
                  )
                  ;;
                data-project | realm-project)
                  commands=(
                    nix nixos-rebuild
                    cargo cargo-nextest nextest
                    pytest py.test uv
                    npm pnpm yarn bun
                    make just ninja cmake meson
                    sqlite3 duckdb
                  )
                  ;;
              esac

              local command_name
              for command_name in "''${commands[@]}"; do
                ln -sfn .sinnix-scope-wrapper "$wrapper_dir/$command_name"
              done

              export SINNIX_SCOPE_ORIGINAL_PATH="$(_sinnix_path_without "$wrapper_dir")"
              export SINNIX_SCOPE_WRAPPER_DIR="$wrapper_dir"
              export PATH="$SINNIX_SCOPE_ORIGINAL_PATH"
              if declare -F PATH_add >/dev/null 2>&1; then
                PATH_add "$wrapper_dir"
              else
                export PATH="$wrapper_dir:$PATH"
              fi
              export SINNIX_SCOPE_WRAPPER_PROJECT="$project_kind"
              export SINNIX_SCOPE_WRAPPER_PROJECT_ROOT="$project_root"
            }

            if declare -F use_flake >/dev/null 2>&1 && ! declare -F _sinnix_original_use_flake >/dev/null 2>&1; then
              eval "$(declare -f use_flake | sed '1s/use_flake/_sinnix_original_use_flake/')"
              use_flake() {
                _sinnix_project_scope_setup
                _sinnix_original_use_flake "$@"
                local status=$?
                if [ "$status" -eq 0 ]; then
                  _sinnix_project_scope_setup
                fi
                return "$status"
              }
            fi
          '';

          programs.ssh = {
            enable = true;
            enableDefaultConfig = false;
            matchBlocks = {
              "*".addKeysToAgent = "yes";
              # Router: `ssh sinnix-gw` just works
              "sinnix-gw" = {
                hostname = "192.168.1.1";
                user = "root";
              };
              "sinnix-gw.lan" = {
                hostname = "192.168.1.1";
                user = "root";
              };
            };
          };

          programs.bat = {
            enable = true;
            config.pager = "less -FR";
            # theme: set by stylix (stylix.targets.bat)
          };

          programs.broot = {
            enable = true;
            enableZshIntegration = true;
            # Home Manager owns ~/.config/broot now. Keep the custom skin, modal
            # mode, special paths, and verbs in the canonical dots JSON source.
            settings = builtins.fromJSON (builtins.readFile ../../../dots/broot/conf.hjson);
          };

          programs.btop = {
            enable = true;
            settings = {
              vim_keys = true;
              update_ms = 2000;
              show_cpu_freq = true;
              show_gpu = true;
              mem_graphs = true;
              proc_sorting = "cpu descending";
              proc_filter = true;
              tree_view = true;
              proc_gradient = true;
              proc_per_core = true;
              proc_mem_bytes = true;
              proc_left = true;
              proc_aggregate = true;
              cpu_graph_upper = "total";
              cpu_graph_lower = "user";
              cpu_invert_lower = true;
              show_uptime = true;
              check_temp = true;
            };
          };
        };
    };
} args
