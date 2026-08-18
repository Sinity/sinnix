{
  mkFeatureModule,
  config,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "terminal"
  ];
  description = "Kitty terminal emulator";
  meta.dotfiles.configFile."kitty/unwrap-urls.py" = "kitty/unwrap-urls.py";
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
              scrollback_lines = 10000;
              enable_audio_bell = "no";
              mouse_hide_wait = 60;
              wheel_scroll_multiplier = 5.0;
              touch_scroll_multiplier = 5.0;
              # cursor_trail=0: off while the patched kitty build's idle
              # memory slope is baselined.
              cursor_trail = 0;
              confirm_os_window_close = 0;
              allow_remote_control = "socket-only";
              listen_on = "unix:$XDG_RUNTIME_DIR/kitty-${user}-{kitty_pid}";
              # Static background alpha; focus/unfocus fading is done natively
              # by Hyprland's kitty-focus-opacity windowrule (hyprland/rules.nix),
              # not by kitty remote-control.
              background_opacity = 0.90;
              open_url_with = "xdg-open";
              detect_urls = "yes";
              url_prefixes = "http https file ftp";
              url_style = "single";
              allow_hyperlinks = "yes";
              shell = captureShellCmd;
            };
            extraConfig = ''
              # Noctalia owns Kitty colors through its native wallpaper-derived
              # template: ~/.config/kitty/themes/noctalia.conf.
              include ~/.config/kitty/themes/noctalia.conf

              map ctrl+shift+f12 debug_config

              # detect_urls only sees one screen line at a time, so a URL a
              # TUI wrapped itself (newline + indent) opens truncated. This
              # rejoins those; see the kitten for the heuristic.
              map ctrl+shift+e kitten hints --customize-processing ~/.config/kitty/unwrap-urls.py --type url --program default

              # Terminal→editor handoff: pick a path[:line] from the screen
              # (compiler/test/rg output) and open it in nvim at that line,
              # as an overlay so quitting returns to the scrollback.
              map ctrl+shift+o kitten hints --type=linenum --linenum-action=overlay nvim +{line} {path}
            '';
          };
        };
    };
} args
