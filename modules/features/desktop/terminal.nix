{ mkFeatureModule, config, ... }@args:
mkFeatureModule {
  path = [
    "desktop"
    "terminal"
  ];
  description = "Kitty terminal emulator";
  configFn =
    {
      config,
      lib,
      user,
      ...
    }:
    {
      home-manager.users.${user} =
        { config, ... }:
        let
          captureShellCmd = "${config.home.homeDirectory}/.local/bin/sinnix-captured-shell";
        in
        {
          home.sessionVariables.TERMINAL = "kitty";
          # Stylix injects an include pointing at a generated Nix-store color
          # file. Kitty's config watcher can fan that into huge inotify watch
          # counts, which breaks Hyprland-spawned app scopes.
          stylix.targets.kitty.enable = false;

          programs.kitty = {
            enable = true;
            # Keep Kitty's shell helpers, but turn off the prompt/title/cursor
            # subfeatures that collide with the custom zsh prompt pipeline.
            shellIntegration.mode = "no-prompt-mark no-title no-cursor";
            settings = {
              font_family = "SauceCodePro Nerd Font Mono";
              bold_font = "auto";
              italic_font = "auto";
              bold_italic_font = "auto";
              font_size = 16;
              disable_ligatures = "never";
              # Kitty's config watcher follows the Home Manager/Nix store
              # symlink path and can allocate millions of inotify watches.
              # Manual reload remains available via ctrl+shift+f5.
              auto_reload_config = -1;

              window_padding_width = 10;
              scrollback_lines = 50000;
              enable_audio_bell = "no";
              mouse_hide_wait = 60;
              wheel_scroll_multiplier = 5.0;
              touch_scroll_multiplier = 5.0;
              cursor_trail = 3;
              confirm_os_window_close = 0;
              allow_remote_control = "socket-only";
              listen_on = "unix:" + "\${XDG_RUNTIME_DIR}/kitty-" + "\${USER}";
              open_url_with = "xdg-open";
              detect_urls = "yes";
              url_prefixes = "http https file ftp";
              url_style = "single";
              allow_hyperlinks = "yes";
              tab_title_template = "{title}";
              active_tab_font_style = "normal";
              inactive_tab_font_style = "normal";
              tab_bar_style = "powerline";
              tab_powerline_style = "angled";
              shell = captureShellCmd;
            };
            extraConfig = ''
              # Noctalia owns Kitty colors through its native wallpaper-derived
              # template: ~/.config/kitty/themes/noctalia.conf.
              globinclude ~/.config/kitty/themes/noctalia.conf

              map ctrl+shift+f12 debug_config

              map ctrl+shift+enter launch --type=tab --cwd=current
            '';
          };
        };
    };
} args
