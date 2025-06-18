# Terminal Configuration (Kitty)
# Terminal emulator with Sinex integration and custom settings

{ ... }:
{
  config = {
    home-manager.users.sinity = {
      programs.kitty = {
        enable = true;
        settings = {
          window_padding_width = 10;
          scrollback_lines = 9999999;
          enable_audio_bell = "no";
          mouse_hide_wait = 60;
          wheel_scroll_multiplier = 0.5;
          touch_scroll_multiplier = 0.5;
          cursor_trail = 3;
          confirm_os_window_close = 0;
          # Enable remote control for Sinex integration
          allow_remote_control = "yes";
          listen_on = "unix:/tmp/kitty";
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
        };
        extraConfig = ''
          map ctrl+shift+f12 debug_config

          # Shell integration for command tracking
          shell_integration enabled
        '';
        keybindings = {
          "alt+1" = "goto_tab 1";
          "alt+2" = "goto_tab 2";
          "alt+3" = "goto_tab 3";
          "alt+4" = "goto_tab 4";
          "ctrl+shift+left" = "no_op";
          "ctrl+shift+right" = "no_op";
        };
      };
    };
  };
}