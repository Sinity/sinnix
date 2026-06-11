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

              # Keep Kitty self-contained instead of re-enabling Stylix's
              # generated include. The palette follows Noctalia's dark
              # Material-style surfaces: near-black chrome, soft text, blue
              # primary, and teal/rose accents.
              foreground = "#e6e1e5";
              background = "#101014";
              background_opacity = "0.96";
              selection_foreground = "#101014";
              selection_background = "#c9c2dc";
              cursor = "#d0bcff";
              cursor_text_color = "#101014";
              url_color = "#8ecaff";

              active_tab_foreground = "#101014";
              active_tab_background = "#d0bcff";
              inactive_tab_foreground = "#cac4d0";
              inactive_tab_background = "#1d1b20";
              tab_bar_background = "#101014";

              color0 = "#1d1b20";
              color1 = "#ffb4ab";
              color2 = "#b5f0b5";
              color3 = "#f3d58c";
              color4 = "#a8c7fa";
              color5 = "#d0bcff";
              color6 = "#8fd8d2";
              color7 = "#cac4d0";
              color8 = "#49454f";
              color9 = "#ffdad6";
              color10 = "#d1f8d1";
              color11 = "#ffe7a8";
              color12 = "#d3e3ff";
              color13 = "#eaddff";
              color14 = "#a7f0e9";
              color15 = "#f4eff4";

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
              map ctrl+shift+f12 debug_config

              map ctrl+shift+enter launch --type=tab --cwd=current
            '';
          };
        };
    };
} args
