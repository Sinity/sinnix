# Noctalia — Quickshell/Qt Wayland desktop shell.
#
# Single shell surface that owns the bar, launcher, notifications, lock, OSD,
# and wallpaper, and acts as the live Material-You color authority (wallpaper
# palette -> app templates). Retires waybar, tofi, fnott, hyprlock, polkit-gnome.
#
# Config follows the repo's dots/ convention: config.toml, plugins.json, and
# local user templates are OUT-OF-STORE symlinks into dots/noctalia/ via
# meta.dotfiles below. Noctalia reads AND writes config.toml, so the GUI
# settings panel works and persists back into the repo — not a read-only store
# file. The runtime-fetched plugin *code* under ~/.config/noctalia/plugins lives
# in impermanence-persisted state.
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
    "noctalia/plugins.json" = "noctalia/plugins.json";
    "noctalia/templates".source = "noctalia/templates";
  };
  configFn =
    {
      pkgs,
      inputs,
      user,
      ...
    }:
    {
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

          home.packages = with pkgs; [
            nvibrant # digital vibrance (nvibrant plugin)
            gpu-screen-recorder # screen-recorder plugin backend
            linux-wallpaperengine # animated wallpaper engine (controller plugin)
            wlr-randr # display-settings plugin (read-only on Hyprland)
          ];

          # Noctalia persists interactive settings in XDG_STATE_HOME but still
          # reloads config.toml. Force this one mutable file back to the repo
          # symlink because the upstream HM module also declares it.
          xdg.configFile."noctalia/config.toml" = {
            source = mkDotsFile "/noctalia/config.toml";
            force = lib.mkForce true;
          };

          systemd.user.services.noctalia-hyprland-reload = {
            Unit = {
              Description = "Reload Hyprland after Noctalia updates generated colors";
              StartLimitIntervalSec = 0;
            };
            Service = {
              Type = "oneshot";
              ExecStart =
                let
                  reloadScript = pkgs.writeShellScript "noctalia-hyprland-reload" ''
                    set -euo pipefail

                    runtime_dir="''${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
                    hypr_dir="$runtime_dir/hypr"
                    latest=""
                    latest_mtime=0

                    if [ ! -d "$hypr_dir" ]; then
                      exit 0
                    fi

                    for dir in "$hypr_dir"/*; do
                      [ -S "$dir/.socket.sock" ] || continue
                      mtime="$(${pkgs.coreutils}/bin/stat -c %Y "$dir")"
                      if [ "$mtime" -ge "$latest_mtime" ]; then
                        latest="$dir"
                        latest_mtime="$mtime"
                      fi
                    done

                    [ -n "$latest" ] || exit 0
                    export HYPRLAND_INSTANCE_SIGNATURE="''${latest##*/}"
                    exec ${pkgs.hyprland}/bin/hyprctl reload
                  '';
                in
                "${reloadScript}";
            };
          };

          systemd.user.paths.noctalia-hyprland-reload = {
            Unit = {
              Description = "Watch Noctalia-generated Hyprland colors";
            };
            Path = {
              PathChanged = "${config.home.homeDirectory}/.config/hypr/noctalia.conf";
              Unit = "noctalia-hyprland-reload.service";
            };
            Install.WantedBy = [ "default.target" ];
          };

          home.activation.reconcileNoctaliaState = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
            settings="''${XDG_STATE_HOME:-$HOME/.local/state}/noctalia/settings.toml"
            if [ -f "$settings" ]; then
              ${pkgs.perl}/bin/perl -0pi -e 's/(\[wallpaper\.automation\][^\[]*?interval_seconds\s*=\s*)\d+/''${1}${toString 120}/s' "$settings"
            fi
          '';

          # Point Noctalia's lock at the dedicated PAM service below (avoids the
          # NixOS "PAM file not generated" gotcha; otherwise it probes login).
          home.sessionVariables.NOCTALIA_PAM_SERVICE = "noctalia";
        };

      # Lock-screen authentication. Noctalia has no native PAM module, so the
      # service file must exist on the system. Mirrors the default `login` stack.
      security.pam.services.noctalia = { };

      # Persist runtime-fetched plugin code + palette cache (config.toml and
      # plugins.json are out-of-store symlinks into the repo, not persisted here).
      sinnix.persistence.home.directories = [
        ".config/noctalia"
        ".local/state/noctalia"
        ".cache/noctalia/community-templates"
        ".cache/noctalia/community-palettes"
      ];
    };
} args
