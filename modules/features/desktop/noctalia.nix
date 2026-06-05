# Noctalia — Quickshell/Qt Wayland desktop shell.
#
# Single shell surface that owns the bar, launcher, notifications, lock, OSD,
# and wallpaper, and acts as the live Material-You color authority: it extracts
# a palette from the current wallpaper and renders color templates into other
# apps (gtk/qt/kitty/vscode). This retires waybar, tofi, fnott, hyprlock, and
# stylix's color role (stylix keeps fonts + cursor only — see ui.nix).
#
# Plugin model: enablement is declared here (plugins.json); Noctalia fetches the
# plugin code from its GitHub registry at startup. ~/.config/noctalia is
# persisted (impermanence) so fetched plugin code + palette cache survive
# reboots. Per-plugin *settings* live in config.toml (programs.noctalia.settings)
# or are tuned in the GUI and persisted.
#
# NOTE: v5 is alpha. The `settings` keys below are best-effort from upstream
# docs; Noctalia ignores unknown keys, so this evaluates regardless. Validate
# the live effect against the running shell (`qs -c noctalia-shell ipc …`) and
# adjust. The Nix structure (input, module, package, persistence) is verified.
{
  mkFeatureModule,
  lib,
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
  configFn =
    {
      config,
      pkgs,
      lib,
      inputs,
      user,
      ...
    }:
    let
      wallpaperDir = "/home/${user}/wallpaper";
      replayDir = "${config.sinnix.paths.capturesRoot}/replay";
      recordingDir = "${config.sinnix.paths.capturesRoot}/screen";
      # Wallpaper Engine workshop content (appid 431960). Empty until the
      # operator installs Wallpaper Engine and subscribes to Workshop items.
      wallpaperEngineDir = "/home/${user}/.local/share/Steam/steamapps/workshop/content/431960";

      # Plugins enabled declaratively. Noctalia auto-installs missing plugin
      # code from its registry on startup; the plugins dir is persisted.
      enabledPlugins = [
        "polkit-agent"
        "screen-recorder"
        "nvibrant"
        "model-usage"
        "keybind-cheatsheet"
        "timer"
        "display-settings"
        "linux-wallpaperengine-controller"
      ];
      pluginsJson = lib.listToAttrs (
        map (id: {
          name = id;
          value = {
            enabled = true;
          };
        }) enabledPlugins
      );
    in
    {
      home-manager.users.${user} =
        {
          pkgs,
          lib,
          config,
          ...
        }:
        {
          imports = [ inputs.noctalia.homeModules.default ];

          programs.noctalia = {
            enable = true;
            package = inputs.noctalia.packages.${pkgs.stdenv.hostPlatform.system}.default;
            systemd.enable = true;

            settings = {
              # Wallpaper as the live color source (Material-You).
              colorScheme = {
                useWallpaperColors = true;
                darkMode = true;
              };

              # Static wallpaper cycle from the persisted ~/wallpaper set, with
              # transitions. Wallhaven + Wallpaper Engine are additional sources
              # configured via their respective panels/plugin.
              wallpaper = {
                enabled = true;
                directory = wallpaperDir;
                randomEnabled = true;
                randomIntervalSec = 1800;
                transitionType = "fade";
                transitionDuration = 800;
              };

              # Render generated colors into other applications.
              appTheming = {
                gtk = true;
                qt = true;
                kitty = true;
                vscode = true;
              };

              bar = {
                position = "top";
              };

              # Per-plugin essentials (best-effort; tune live).
              plugins = {
                "screen-recorder" = {
                  outputDirectory = recordingDir;
                  replayDirectory = replayDir;
                  replayDurationSec = 60;
                  fps = 60;
                  codec = "hevc";
                  audioSource = "system";
                };
                "nvibrant" = {
                  vibrance = 512;
                  displayCount = 1;
                };
                "model-usage" = {
                  providers = [
                    "claude"
                    "codex"
                  ];
                  metric = "usage";
                };
                "linux-wallpaperengine-controller" = {
                  workshopDirectory = wallpaperEngineDir;
                  syncWallpaperColors = true;
                };
              };
            };
          };

          # Declarative plugin enablement. Code is fetched at runtime and
          # persisted; this only declares *which* plugins are on.
          xdg.configFile."noctalia/plugins.json".text = builtins.toJSON pluginsJson;

          home.packages = with pkgs; [
            nvibrant # digital vibrance (nvibrant plugin)
            gpu-screen-recorder # screen-recorder plugin backend
            linux-wallpaperengine # animated wallpaper engine (controller plugin)
            wlr-randr # display-settings plugin (read-only on Hyprland)
          ];

          # Point Noctalia's lock at the dedicated PAM service below (avoids the
          # NixOS "PAM file not generated" gotcha; otherwise it probes login).
          home.sessionVariables.NOCTALIA_PAM_SERVICE = "noctalia";
        };

      # Lock-screen authentication. Noctalia has no native PAM module, so the
      # service file must exist on the system. Mirrors the default `login` stack.
      security.pam.services.noctalia = { };

      # Persist fetched plugin code, palette cache, and runtime shell state.
      sinnix.persistence.home.directories = [ ".config/noctalia" ];
    };
} args
