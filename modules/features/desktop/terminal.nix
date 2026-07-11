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
        { config, pkgs, ... }:
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
            # sinnix-878 phase 2: discriminate glibc arena bloat/fragmentation
            # from a true kitty leak — scoped to the kitty process itself (its
            # `env` directive would only affect children). Applies to
            # instances started after the next switch; compare telemetry
            # slopes across the fleet (process_memory_sample).
            package = pkgs.symlinkJoin {
              name = "kitty-malloc-capped";
              paths = [ pkgs.kitty ];
              nativeBuildInputs = [ pkgs.makeWrapper ];
              postBuild = ''
                wrapProgram $out/bin/kitty --set MALLOC_ARENA_MAX 2
              '';
            };
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
              scrollback_lines = 10000;
              enable_audio_bell = "no";
              mouse_hide_wait = 60;
              wheel_scroll_multiplier = 5.0;
              touch_scroll_multiplier = 5.0;
              # cursor_trail 3 -> 0 (2026-07-10, sinnix-878 phase 1). Phase 1
              # CONCLUDED 2026-07-11: telemetry over the 07-10..07-11 boot
              # shows 86 MB/h growth WITH the trail disabled — cursor_trail is
              # exonerated. Keeping it off pending the leak fix regardless (no
              # animation attachment). Evidence trail in sinnix-878; upstream
              # report filed against kitty 0.47.4.
              cursor_trail = 0;
              confirm_os_window_close = 0;
              allow_remote_control = "socket-only";
              listen_on = "unix:$XDG_RUNTIME_DIR/kitty-${user}-{kitty_pid}";
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
              include ~/.config/kitty/themes/noctalia.conf

              map ctrl+shift+f12 debug_config

              map ctrl+shift+enter launch --type=tab --cwd=current
            '';
          };
        };
    };
} args
