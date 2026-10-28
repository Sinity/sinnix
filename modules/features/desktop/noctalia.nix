# Noctalia — native Wayland desktop shell (no Qt/GTK; Luau plugins).
#
# Single shell surface that owns the bar, launcher, notifications, lock, OSD,
# and wallpaper, and acts as the live Material-You color authority (wallpaper
# palette -> app templates).
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
  helpers,
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
      sinnix.runtime.units.noctalia = {
        unit = "noctalia.service";
        manager = "user";
        resourceClass = "ordinary";
        resources.Slice = "desktop-shell.slice";
        workload = {
          class = "interactive";
          rationale = "Visible desktop shell must remain responsive while remaining cgroup-containable.";
          processMatchers = [ "noctalia" ];
          earlyoomAvoid = true;
        };
        notifyOnFailure = true;
        operatorRestart = true;
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
          scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
          noctalia = pkgs.noctalia.overrideAttrs (old: {
            patches = (old.patches or [ ]) ++ [
              ./noctalia-notification-prewarm.patch
              # Keep policy in Noctalia's typed state boundary. These patches
              # are pinned to the flake's upstream source and verified below.
              ./noctalia-automation-ipc.patch
              ./noctalia-memory-stats.patch
            ];
            postPatch = (old.postPatch or "") + ''
              patch -p1 < ${./noctalia-pipewire-reconnect.patch}
            '';
          });
          officialPlugins = pkgs.fetchFromGitHub {
            owner = "noctalia-dev";
            repo = "official-plugins";
            rev = "6bd77f8f202941f44b24585fe563916563009a49";
            hash = "sha256-VtL2YhxxKNn+Mtj5vhWnnkEsOYS9zz+AUwS/mqiwwqs=";
          };
        in
        {
          imports = [ inputs.noctalia.homeModules.default ];

          # No `settings` here on purpose: setting programs.noctalia.settings
          # would serialize a read-only store config.toml and fight the GUI.
          # config.toml is provided as a writable dots/ symlink (meta.dotfiles).
          programs.noctalia = {
            enable = true;
            package = noctalia;
            systemd.enable = true;
          };

          systemd.user.services.noctalia.Service =
            (lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = nixosConfig.sinnix.runtime.inventory;
              unit = "noctalia.service";
              manager = "user";
            })
            // {
              # A lost Wayland connection can exit successfully; restore the shell
              # while the graphical session remains active. Explicit stops stay stopped.
              Restart = lib.mkForce "always";
              RestartSec = 2;
            };

          home.file.".local/share/noctalia/pinned/official/timer".source = "${officialPlugins}/timer";
          home.file.".local/share/noctalia/local/sinnix-hub".source =
            ../../../dots/noctalia/plugins/sinnix-hub;
          home.file.".local/share/noctalia/local/sinnix-bar".source =
            ../../../dots/noctalia/plugins/sinnix-bar;
          # The bar reading-stack widget dispatches the picker by a stable path.
          home.file.".local/bin/sinnix-picker".source = "${scriptPkgs.sinnix-picker}/bin/sinnix-picker";

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

          # Noctalia's native Hyprland template owns the Lua palette. It writes
          # ~/.config/hypr/noctalia.lua and appends its require/apply hook to
          # hyprland.lua, so no second color watcher is needed here.

        };

      # Persist Noctalia's app-owned settings and palette cache. Curated TOML
      # fragments are out-of-store symlinks into the repository.
      sinnix.persistence.home.directories = [
        ".local/state/noctalia"
        ".cache/noctalia/community-templates"
        ".cache/noctalia/community-palettes"
        # Rendered template outputs (noctalia.css, themes/noctalia.conf,
        # hypr/noctalia.lua; ~/.config/yazi is persisted elsewhere). gtk.css imports noctalia.css
        # unconditionally, so early GTK clients (nm-applet, blueman) error
        # until Noctalia re-renders unless the files survive the reboot.
        ".config/gtk-3.0"
        ".config/gtk-4.0"
        ".config/kitty/themes"
        ".config/hypr"
        ".config/qt5ct"
        ".config/qt6ct"
      ];
    };
} args
