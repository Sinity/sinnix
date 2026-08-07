# Noctalia — Quickshell/Qt Wayland desktop shell.
#
# Single shell surface that owns the bar, launcher, notifications, lock, OSD,
# and wallpaper, and acts as the live Material-You color authority (wallpaper
# palette -> app templates). Retires waybar, tofi, fnott, hyprlock, polkit-gnome.
#
# Config follows the repo's dots/ convention: config.toml, plugins.toml, and
# hooks.toml are curated fragments, while settings.toml is app-owned state.
# local user templates are OUT-OF-STORE symlinks into dots/noctalia/ via
# meta.dotfiles below. Noctalia reads AND writes config.toml, so the GUI
# settings panel works and persists back into the repo — not a read-only store
# file. The pinned plugin trees are immutable Nix path sources.
{
  mkFeatureModule,
  pkgs,
  inputs,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "noctalia"
  ];
  description = "Noctalia Wayland shell (bar, launcher, notifications, lock, OSD, wallpaper, dynamic color)";
  meta.dotfiles.configFile = {
    "noctalia/config.toml" = "noctalia/config.toml";
    "noctalia/plugins.toml" = "noctalia/plugins.toml";
    "noctalia/hooks.toml" = "noctalia/hooks.toml";
    "noctalia/templates".source = "noctalia/templates";
  };
  configFn =
    {
      config,
      pkgs,
      inputs,
      user,
      ...
    }:
    let
      nixosConfig = config;
    in
    {
      sinnix.runtime.surfaces.noctalia = {
        unit = "noctalia.service";
        manager = "user";
        resourceClass = "desktop-shell";
        workload = {
          kind = "frontend";
          lifecycle = "persistent";
          expendability = "protected";
          operatorProtection = "operator";
          class = "interactive";
          rationale = "Visible desktop shell must remain responsive while remaining cgroup-containable.";
          processMatchers = [ "noctalia" ];
        };
        observe = {
          enable = true;
          restartable = true;
        };
      };

      home-manager.users.${user} =
        {
          config,
          lib,
          mkDotsFileFor,
          pkgs,
          ...
        }:
        let
          mkDotsFile = mkDotsFileFor config;
          officialPlugins = pkgs.fetchFromGitHub {
            owner = "noctalia-dev";
            repo = "official-plugins";
            rev = "c1369385bd71cfad30614dbc6679eb7df752bc94";
            hash = "sha256-6QDLMbYqlSL643XQk+h8x7ltHPdTIaC4K2AjT8dHuDA=";
          };
          communityPlugins = pkgs.fetchFromGitHub {
            owner = "noctalia-dev";
            repo = "community-plugins";
            rev = "2a697bea88502513b7efe851ac7d33584d34bd69";
            hash = "sha256-eGUtF9j975ONBMzktCNwAxMQA8/YgKIexqAZjlvKECc=";
          };
        in
        {
          imports = [ inputs.noctalia.homeModules.default ];

          # No `settings` here on purpose: setting programs.noctalia.settings
          # would serialize a read-only store config.toml and fight the GUI.
          # config.toml is provided as a writable dots/ symlink (meta.dotfiles).
          programs.noctalia = {
            enable = true;
            package = inputs.noctalia.packages.${pkgs.stdenv.hostPlatform.system}.default;
            systemd.enable = true;
          };

          systemd.user.services.noctalia.Service = lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = nixosConfig.sinnix.runtime.inventory;
            unit = "noctalia.service";
          };

          home.file.".local/share/noctalia/pinned/official/timer".source = "${officialPlugins}/timer";
          home.file.".local/share/noctalia/pinned/community/keybind-cheatsheet".source = "${communityPlugins}/keybind-cheatsheet";
          home.file.".local/share/noctalia/local/sinnix-ops".source = mkDotsFile "/noctalia/plugins/sinnix-ops";

          home.packages = with pkgs; [
            nvibrant # digital vibrance (nvibrant plugin)
            gpu-screen-recorder # screen-recorder plugin backend
            linux-wallpaperengine # animated wallpaper engine (controller plugin)
            wlr-randr # display-settings plugin (read-only on Hyprland)
          ];

          # Keep the curated config writable and repository-owned. The upstream
          # module declares the same path when validation is enabled.
          xdg.configFile."noctalia/config.toml" = {
            source = lib.mkForce (mkDotsFile "/noctalia/config.toml");
            force = lib.mkForce true;
          };

          systemd.user.services.noctalia-hyprland-colors = {
            Unit = {
              Description = "Apply Noctalia-generated Hyprland colors";
              StartLimitIntervalSec = 0;
            };
            Service = {
              Type = "oneshot";
              ExecStart =
                let
                  applyScript = pkgs.writeShellScript "noctalia-hyprland-colors" ''
                    set -euo pipefail

                    config_file="''${XDG_CONFIG_HOME:-$HOME/.config}/hypr/noctalia.conf"
                    [ -r "$config_file" ] || exit 0

                    color_for() {
                      ${pkgs.gawk}/bin/awk -v name="$1" '
                        $1 == "$" name && $2 == "=" {
                          print $3
                          found = 1
                          exit
                        }
                        END { exit found ? 0 : 1 }
                      ' "$config_file"
                    }

                    primary="$(color_for primary || true)"
                    surface="$(color_for surface || true)"
                    secondary="$(color_for secondary || true)"
                    error="$(color_for error || true)"

                    [ -n "$primary" ] || exit 0
                    [ -n "$surface" ] || exit 0
                    [ -n "$secondary" ] || exit 0
                    [ -n "$error" ] || exit 0

                    ${pkgs.hyprland}/bin/hyprctl eval "
                    hl.config({
                      general = {
                        col = {
                          active_border = \"$primary\",
                          inactive_border = \"$surface\",
                        },
                      },
                      group = {
                        col = {
                          border_active = \"$secondary\",
                          border_inactive = \"$surface\",
                          border_locked_active = \"$error\",
                          border_locked_inactive = \"$surface\",
                        },
                        groupbar = {
                          col = {
                            active = \"$secondary\",
                            inactive = \"$surface\",
                            locked_active = \"$error\",
                            locked_inactive = \"$surface\",
                          },
                        },
                      },
                    })
                    "
                  '';
                in
                "${applyScript}";
            };
          };

          systemd.user.paths.noctalia-hyprland-colors = {
            Unit = {
              Description = "Watch Noctalia-generated Hyprland colors";
            };
            Path = {
              PathChanged = "${config.home.homeDirectory}/.config/hypr/noctalia.conf";
              Unit = "noctalia-hyprland-colors.service";
            };
            Install.WantedBy = [ "default.target" ];
          };

        };

      # Persist Noctalia's app-owned settings and palette cache. Curated TOML
      # fragments are out-of-store symlinks into the repository.
      sinnix.persistence.home.directories = [
        ".local/state/noctalia"
        ".cache/noctalia/community-templates"
        ".cache/noctalia/community-palettes"
      ];
    };
} args
